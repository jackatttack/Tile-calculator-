import math
import time
import uuid

import ui

from constants import (
    BOARD_COLOR,
    GRID_COLOR,
    GRID_SIZE,
    OP_COLORS,
    PADDING,
    RESULT_COLOR,
    RESULT_TEXT_COLOR,
    TILE_COLOR,
    TILE_SIZE,
)
from ui_utils import clamp, get_point, pt_xy
from board_menus import BoardContextMenu, TrashBin, TrashMenu
from editor_views import TileEditorPopup, _EditorOverlay
from tile_models import FractionTile, SourceTile, Tile, TokenSpawner


class Board(ui.View):
    def __init__(self):
        super().__init__()
        self.background_color = BOARD_COLOR
        self.corner_radius = 12
        self.flex = ''

        self.show_grid = True
        self.snap_enabled = True
        self.show_spawners = True

        self.tiles = []
        self.history = []
        self.max_history = 20
        self.on_state_changed = None

        # --- UI chrome inside board ---
        self.trash = TrashBin()
        self.add_subview(self.trash)

        self.source = SourceTile(self)
        self.add_subview(self.source)

        self.digit_spawners = []
        for i in range(10):
            sp = TokenSpawner(self, str(i), kind='number', color=TILE_COLOR)
            self.digit_spawners.append(sp)
            self.add_subview(sp)

        self.op_spawners = []
        for token in ['+', '-', '*', '/', '^']:
            sp = TokenSpawner(self, token, kind='op',
                              color=OP_COLORS.get(token, '#0A84FF'),
                              text_color='#FFFFFF')
            self.op_spawners.append(sp)
            self.add_subview(sp)

        # "=" spawner (tool tile)
        self.equals_spawner = TokenSpawner(self, '=', kind='equals', color='#34C759', text_color='#000000')
        self.add_subview(self.equals_spawner)

        self.frac_spawner = TokenSpawner(self, '⅟', kind='fraction', color='#5AC8FA', text_color='#000000')
        self.add_subview(self.frac_spawner)

        self.factor_spawner = TokenSpawner(self, 'F', kind='factor', color='#BF5AF2', text_color='#FFFFFF')
        self.add_subview(self.factor_spawner)

        self._editor_overlay = None
        self.tile_editor = None
        self._board_context_menu = None

        self._board_tap_dragged = False
        self._trash_menu = None
        self._board_menu_spawn_point = None

        # Keyboard zone metrics (computed in layout)
        self._keyboard_rows = 1
        self._keyboard_height = GRID_SIZE
        self._keyboard_top_y = 0

    # ----------------------------------------------------------
    # Spawner visibility
    # ----------------------------------------------------------


    def set_spawners_visible(self, is_on):
        self.show_spawners = bool(is_on)
        spawner_list = self._all_spawners()
        for sp in spawner_list:
            try:
                sp.hidden = (not self.show_spawners)
            except:
                pass
        try:
            self.set_needs_layout()
        except:
            pass

    # ----------------------------------------------------------
    # Layout (keyboard feel)
    # ----------------------------------------------------------

    def layout(self):
        # Move trash OUT of the keyboard zone (top-right like a HUD)
        self.trash.x = self.width - self.trash.width - PADDING
        self.trash.y = PADDING

        # Spawners: packed into a bottom keyboard strip across full width
        spawner_list = self._all_spawners()
        spawner_list = self._all_spawners()

        if self.show_spawners:
            step = GRID_SIZE
            half = step * 0.5

            usable_w = max(1, (self.width - 2 * PADDING))
            tiles_per_row = max(1, int(usable_w // step))

            total = len(spawner_list)
            rows = max(1, int(math.ceil(total / float(tiles_per_row))))
            self._keyboard_rows = rows
            self._keyboard_height = rows * step
            self._keyboard_top_y = (self.height - PADDING) - (rows * step)

            col = 0
            row = 0
            for sp in spawner_list:
                try:
                    sp.hidden = False
                except:
                    pass

                cx = PADDING + half + col * step
                # Bottom row is row=0, stacked upward
                cy = (self.height - PADDING - half) - row * step

                sp.x = cx - (TILE_SIZE * 0.5)
                sp.y = cy - (TILE_SIZE * 0.5)

                col += 1
                if col >= tiles_per_row:
                    col = 0
                    row += 1
        else:
            self._keyboard_rows = 0
            self._keyboard_height = 0
            self._keyboard_top_y = self.height
            for sp in spawner_list:
                try:
                    sp.hidden = True
                    sp.x = -1000
                    sp.y = -1000
                except:
                    pass

        if self._editor_overlay:
            self._editor_overlay.frame = (0, 0, self.width, self.height)

    def draw(self):
        if not self.show_grid:
            return
        w, h = self.width, self.height
        path = ui.Path()
        x = PADDING
        while x <= w - PADDING:
            path.move_to(x, PADDING)
            path.line_to(x, h - PADDING)
            x += GRID_SIZE
        y = PADDING
        while y <= h - PADDING:
            path.move_to(PADDING, y)
            path.line_to(w - PADDING, y)
            y += GRID_SIZE
        ui.set_color(GRID_COLOR)
        path.line_width = 1
        path.stroke()

    # ----------------------------------------------------------
    # Board tap: palette toggle
    # ----------------------------------------------------------

    def touch_began(self, touch):
        self._board_tap_dragged = False
        self._dismiss_tile_editor_only()

    def touch_moved(self, touch):
        self._board_tap_dragged = True

    def touch_ended(self, touch):
        if self._board_tap_dragged:
            return

        if getattr(self, '_board_context_menu', None):
            self.dismiss_board_context_menu()
            return

        pt = get_point(touch, in_view=self)
        x, y = pt_xy(pt)
        self.show_board_context_menu(x, y)

    # ----------------------------------------------------------
    # Board context menu
    # ----------------------------------------------------------

    def show_board_context_menu(self, x, y):
        self._dismiss_tile_editor_only()
        self.dismiss_trash_menu()
        self.dismiss_board_context_menu()

        self._board_menu_spawn_point = (x, y)

        menu = BoardContextMenu(self)
        menu.x = clamp(x - menu.width / 2, PADDING, self.width - menu.width - PADDING)
        menu.y = clamp(y - menu.height - 10, PADDING, self.height - menu.height - PADDING)
        self.add_subview(menu)
        menu.bring_to_front()
        self._board_context_menu = menu

    def dismiss_board_context_menu(self):
        menu = getattr(self, '_board_context_menu', None)
        if menu:
            try:
                self.remove_subview(menu)
            except:
                pass
            self._board_context_menu = None

    def dismiss_trash_menu(self):
        menu = getattr(self, '_trash_menu', None)
        if menu:
            try:
                self.remove_subview(menu)
            except:
                pass
            self._trash_menu = None

    # ----------------------------------------------------------
    # Editor
    # ----------------------------------------------------------

    def _dismiss_tile_editor_only(self):
        if self.tile_editor:
            try:
                self._editor_overlay.remove_subview(self.tile_editor)
            except:
                pass
            self.tile_editor = None
        if self._editor_overlay:
            try:
                self.remove_subview(self._editor_overlay)
            except:
                pass
            self._editor_overlay = None

    def show_editor_for_tile(self, tile):
        if not self._editor_overlay:
            self._editor_overlay = _EditorOverlay(self)
            self.add_subview(self._editor_overlay)
        if not self.tile_editor:
            self.tile_editor = TileEditorPopup(self)
            self._editor_overlay.add_subview(self.tile_editor)
        self._editor_overlay.bring_to_front()
        self.tile_editor.present_for_tile(tile)

    def dismiss_editor(self):
        self.dismiss_board_context_menu()
        self._dismiss_tile_editor_only()

    # ----------------------------------------------------------
    # Trash / deletion
    # ----------------------------------------------------------

    def is_over_trash(self, tile):
        return not (tile.x > self.trash.x + self.trash.width or
                    tile.x + tile.width < self.trash.x or
                    tile.y > self.trash.y + self.trash.height or
                    tile.y + tile.height < self.trash.y)

    def delete_tile(self, tile):
        self.save_state()
        self.dismiss_editor()
        self.dismiss_trash_menu()

        tiles_to_delete = (self.get_group_tiles(tile)
                           if getattr(tile, 'group_id', None)
                           else [tile])

        for t in tiles_to_delete:
            if t in self.tiles:
                self.tiles.remove(t)

            def make_anim(tv):
                def anim():
                    tv.alpha = 0
                    tv.transform = ui.Transform.scale(0.1, 0.1)
                return anim

            def make_done(tv):
                def done():
                    try:
                        self.remove_subview(tv)
                    except:
                        pass
                return done

            ui.animate(make_anim(t), duration=0.2, completion=make_done(t))

    # ----------------------------------------------------------
    # Undo / state
    # ----------------------------------------------------------

    def save_state(self):
        if not hasattr(self, 'redo_history'):
            self.redo_history = []
        else:
            self.redo_history[:] = []

        state = self._capture_state()
        self.history.append(state)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        if self.on_state_changed:
            try:
                self.on_state_changed()
            except:
                pass

    def undo(self):
        if not hasattr(self, 'redo_history'):
            self.redo_history = []

        if not self.history:
            return

        try:
            self.redo_history.append(self._capture_state())
            if len(self.redo_history) > self.max_history:
                self.redo_history.pop(0)
        except Exception as e:
            print('Undo capture error:', e)

        state = self.history.pop()
        self.dismiss_editor()
        self.dismiss_board_context_menu()
        self._restore_state(state)

        try:
            if getattr(self, 'snap_enabled', True):
                for t in self.tiles:
                    try:
                        t.snap_to_grid()
                    except:
                        pass
            self._spread_out_tiles()
        except Exception as e:
            print('Undo spread error:', e)

        if self.on_state_changed:
            try:
                self.on_state_changed()
            except:
                pass

    def redo(self):
        if not hasattr(self, 'redo_history'):
            self.redo_history = []
        if not self.redo_history:
            return

        try:
            self.history.append(self._capture_state())
            if len(self.history) > self.max_history:
                self.history.pop(0)
        except Exception as e:
            print('Redo capture error:', e)

        state = self.redo_history.pop()
        self.dismiss_editor()
        self.dismiss_board_context_menu()
        self._restore_state(state)

        try:
            if getattr(self, 'snap_enabled', True):
                for t in self.tiles:
                    try:
                        t.snap_to_grid()
                    except:
                        pass
            self._spread_out_tiles()
        except Exception as e:
            print('Redo spread error:', e)

        if self.on_state_changed:
            try:
                self.on_state_changed()
            except:
                pass



    def _capture_state(self):
        state = {'tiles': []}
        for t in self.tiles:
            if t.superview is None:
                continue
            kind = getattr(t, 'kind', 'generic')
            td = {
                'x': t.x, 'y': t.y,
                'width': t.width, 'height': t.height,
                'label_text': getattr(t, 'label_text', ''),
                'tile_color': getattr(t, 'tile_color', '#FFD60A'),
                'kind': kind,
                'expr_str': getattr(t, 'expr_str', ''),
                'pending_op': getattr(t, 'pending_op', None),
                'group_id': getattr(t, 'group_id', None),
                '_sticky': getattr(t, '_sticky', False),
            }
            if kind == 'fraction':
                td['numer'] = getattr(t, 'numer', None)
                td['denom'] = getattr(t, 'denom', None)
            if kind == 'subst':
                sv = getattr(t, 'subst_val', None)
                td['subst_val'] = str(sv) if sv is not None else None
            try:
                td['label_text_color'] = t.label.text_color
            except:
                pass
            state['tiles'].append(td)
        return state


    def _restore_state(self, state):
        for t in list(self.tiles):
            try:
                self.tiles.remove(t)
            except:
                pass
            try:
                self.remove_subview(t)
            except:
                pass

        for td in state.get('tiles', []):
            kind = td.get('kind', 'generic')

            if kind == 'fraction' and 'FractionTile' in globals():
                t = FractionTile(self)
                t.x = td.get('x', PADDING)
                t.y = td.get('y', PADDING)
                t.width = td.get('width', getattr(t, 'width', TILE_SIZE))
                t.height = td.get('height', getattr(t, 'height', TILE_SIZE + GRID_SIZE))
                t.kind = 'fraction'
                t.group_id = td.get('group_id', None)
                t._sticky = td.get('_sticky', False)
                try:
                    t.set_tile_color(td.get('tile_color', '#FFB347'))
                except:
                    t.background_color = td.get('tile_color', '#FFB347')
                numer = td.get('numer', None)
                denom = td.get('denom', None)
                try:
                    if numer is not None:
                        t.set_fraction_numer(int(numer))
                    if denom is not None:
                        t.set_fraction_denom(int(denom))
                except:
                    pass
                try:
                    if getattr(t, 'numer', None) is not None and getattr(t, 'denom', None) is not None:
                        t.expr_str = f'({int(t.numer)}/{int(t.denom)})'
                except:
                    pass
                if t.group_id:
                    try:
                        t.set_grouped(True)
                    except:
                        pass
                if t._sticky:
                    t.border_width = 3
                    t.border_color = '#FFFFFF'
                try:
                    lc = td.get('label_text_color', None)
                    if lc:
                        t.label.text_color = lc
                except:
                    pass
                self.add_subview(t)
                self.tiles.append(t)
                continue

            t = Tile(self)
            t.x = td.get('x', PADDING)
            t.y = td.get('y', PADDING)
            t.width = td.get('width', TILE_SIZE)
            t.height = td.get('height', TILE_SIZE)
            t.kind = kind
            t.expr_str = td.get('expr_str', '')
            t.pending_op = td.get('pending_op', None)
            t.group_id = td.get('group_id', None)
            t._sticky = td.get('_sticky', False)
            if kind == 'subst':
                sv = td.get('subst_val', None)
                if sv is not None:
                    t.subst_val = self._sympy_parse(sv)
                else:
                    t.subst_val = None
            t.set_label(td.get('label_text', ''))
            t.set_tile_color(td.get('tile_color', '#FFD60A'))
            if t._sticky:
                t.border_width = 3
                t.border_color = '#FFFFFF'
            try:
                lc = td.get('label_text_color', None)
                if lc:
                    t.label.text_color = lc
            except:
                pass
            if t.group_id:
                t.set_grouped(True)
            self.add_subview(t)
            self.tiles.append(t)

    def _rect_overlaps_any(self, rect, rects):
        x, y, w, h = rect
        for (ox, oy, ow, oh) in rects:
            if not (x + w <= ox or ox + ow <= x or y + h <= oy or oy + oh <= y):
                return True
        return False

    def _aligned_positions_around(self, x0, y0, max_r=6):
        bx = PADDING + round((x0 - PADDING) / GRID_SIZE) * GRID_SIZE
        by = PADDING + round((y0 - PADDING) / GRID_SIZE) * GRID_SIZE

        yield (bx, by)

        for r in range(1, max_r + 1):
            for dx in range(-r, r + 1):
                dy = r - abs(dx)
                for sy in (-1, 1):
                    cx = bx + dx * GRID_SIZE
                    cy = by + sy * dy * GRID_SIZE
                    yield (cx, cy)

    def _spread_out_tiles(self):
        live = [t for t in self.tiles if t.superview is not None]
        if len(live) < 2:
            return

        live.sort(key=lambda t: (t.y, t.x))

        placed_rects = []
        pad = 0.0

        for t in live:
            t.x = clamp(t.x, PADDING, self.width - t.width - PADDING)
            t.y = clamp(t.y, PADDING, self.height - t.height - PADDING)

            rect = (t.x - pad, t.y - pad, t.width + 2 * pad, t.height + 2 * pad)

            if not self._rect_overlaps_any(rect, placed_rects):
                placed_rects.append(rect)
                continue

            found = False
            for cx, cy in self._aligned_positions_around(t.x, t.y, max_r=10):
                nx = clamp(cx, PADDING, self.width - t.width - PADDING)
                ny = clamp(cy, PADDING, self.height - t.height - PADDING)
                test = (nx - pad, ny - pad, t.width + 2 * pad, t.height + 2 * pad)
                if not self._rect_overlaps_any(test, placed_rects):
                    t.x, t.y = nx, ny
                    placed_rects.append(test)
                    found = True
                    break

            if not found:
                nx = clamp(t.x + GRID_SIZE, PADDING, self.width - t.width - PADDING)
                ny = clamp(t.y + GRID_SIZE, PADDING, self.height - t.height - PADDING)
                test = (nx - pad, ny - pad, t.width + 2 * pad, t.height + 2 * pad)
                if not self._rect_overlaps_any(test, placed_rects):
                    t.x, t.y = nx, ny
                    placed_rects.append(test)
                else:
                    placed_rects.append(rect)

        if getattr(self, 'snap_enabled', True):
            for t in live:
                try:
                    t.snap_to_grid()
                except:
                    pass

    # ----------------------------------------------------------
    # Grouping
    # ----------------------------------------------------------

    def get_group_tiles(self, tile):
        if not tile or not getattr(tile, 'group_id', None):
            return []
        gid = tile.group_id
        return [t for t in self.tiles if getattr(t, 'group_id', None) == gid]

    def group_adjacent_tiles(self, tile):
        if not tile or tile not in self.tiles:
            return

        if getattr(tile, 'kind', '') == 'fraction' and (getattr(tile, 'numer', None) is None or getattr(tile, 'denom', None) is None):
            print('Group: Finish the fraction first')
            return

        self.save_state()
        cluster = self.flood_fill_cluster(tile)
        if len(cluster) < 2:
            print('Group: Need at least 2 connected tiles')
            return

        for t in cluster:
            if getattr(t, 'kind', '') == 'fraction' and (getattr(t, 'numer', None) is None or getattr(t, 'denom', None) is None):
                print('Group: Cluster has incomplete fraction')
                return

        gid = str(uuid.uuid4())
        for t in cluster:
            t.group_id = gid
            t.set_grouped(True)

    def ungroup_tiles(self, tile):
        if not tile or not getattr(tile, 'group_id', None):
            return
        self.save_state()
        for t in self.get_group_tiles(tile):
            t.set_grouped(False)

    # ----------------------------------------------------------
    # Adjacency helpers
    # ----------------------------------------------------------

    def tile_center(self, t):
        try:
            return t.center.x, t.center.y
        except:
            return t.x + t.width * 0.5, t.y + t.height * 0.5

    def get_adjacent_tiles_4way(self, center_tile):
        if not center_tile or center_tile.superview is None:
            return {'left': None, 'top': None, 'right': None, 'bottom': None}

        cx, cy = center_tile.x, center_tile.y
        cw, ch = center_tile.width, center_tile.height
        ccx, ccy = self.tile_center(center_tile)

        pos_tol = GRID_SIZE * 0.8
        align_tol = GRID_SIZE * 0.8

        adj = {'left': None, 'top': None, 'right': None, 'bottom': None}

        for t in self.tiles:
            if t is center_tile or t.superview is None:
                continue
            tx, ty, tw, th = t.x, t.y, t.width, t.height
            tcx, tcy = self.tile_center(t)

            if abs((tx + tw) - cx) <= pos_tol and abs(tcy - ccy) <= align_tol:
                adj['left'] = t
            elif abs(tx - (cx + cw)) <= pos_tol and abs(tcy - ccy) <= align_tol:
                adj['right'] = t
            elif abs((ty + th) - cy) <= pos_tol and abs(tcx - ccx) <= align_tol:
                adj['top'] = t
            elif abs(ty - (cy + ch)) <= pos_tol and abs(tcx - ccx) <= align_tol:
                adj['bottom'] = t

        return adj

    def get_adjacent_tiles_8way(self, center_tile):
        if not center_tile or center_tile.superview is None:
            return []

        ccx, ccy = self.tile_center(center_tile)
        tol = GRID_SIZE * 0.6
        result = []

        for t in self.tiles:
            if t is center_tile or t.superview is None:
                continue
            tcx, tcy = self.tile_center(t)
            dx = abs(tcx - ccx)
            dy = abs(tcy - ccy)
            if dx <= GRID_SIZE + tol and dy <= GRID_SIZE + tol and (dx > 0.1 or dy > 0.1):
                result.append(t)

        return result

    def flood_fill_cluster(self, start_tile):
        if not start_tile or start_tile not in self.tiles:
            return set()
        visited = set()
        stack = [start_tile]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            for nb in self.get_adjacent_tiles_8way(cur):
                if nb not in visited and nb in self.tiles:
                    stack.append(nb)
        return visited

    # ----------------------------------------------------------
    # Overlap helper used by Factor tile
    # ----------------------------------------------------------

    def find_all_overlapping_tiles(self, dropped):
        if dropped is None or dropped.superview is None:
            return []

        dx, dy, dw, dh = dropped.x, dropped.y, dropped.width, dropped.height
        hits = []

        for t in self.tiles:
            if t is dropped or t.superview is None or t.superview is not self:
                continue
            if getattr(t, 'group_id', None):
                continue

            ix1 = max(dx, t.x)
            iy1 = max(dy, t.y)
            ix2 = min(dx + dw, t.x + t.width)
            iy2 = min(dy + dh, t.y + t.height)

            if ix2 > ix1 and iy2 > iy1:
                area = (ix2 - ix1) * (iy2 - iy1)
                hits.append((area, t))

        hits.sort(key=lambda p: p[0], reverse=True)
        return [t for _, t in hits]

    def _best_overlap(self, dropped, allowed_kinds=None):
        dx, dy, dw, dh = dropped.x, dropped.y, dropped.width, dropped.height
        best, best_area = None, 0.0

        for t in self.tiles:
            if t is dropped or t.superview is None or t.superview is not self:
                continue
            if getattr(t, 'group_id', None):
                continue
            if allowed_kinds is not None and getattr(t, 'kind', '') not in allowed_kinds:
                continue

            ix1 = max(dx, t.x)
            iy1 = max(dy, t.y)
            ix2 = min(dx + dw, t.x + t.width)
            iy2 = min(dy + dh, t.y + t.height)

            if ix2 > ix1 and iy2 > iy1:
                area = (ix2 - ix1) * (iy2 - iy1)
                if area > best_area:
                    best_area = area
                    best = t

        if best is None:
            return None, 0.0

        min_tile_area = min(dw * dh, best.width * best.height)
        if min_tile_area <= 0 or (best_area / min_tile_area) < 0.25:
            return None, 0.0

        return best, best_area


    def _is_decimal_numeric(self, s):
        """Check if s is a decimal-eligible numeric string (must contain at least one digit)."""
        if not s:
            return False
        import re
        if not any(c.isdigit() for c in s):
            return False
        return bool(re.match(r'^-?(\d*\.\d*|\d+)$', s))





    def _consume_tile(self, tile):
        """Remove tile from board unless it's sticky."""
        if getattr(tile, '_sticky', False):
            return
        if tile in self.tiles:
            self.tiles.remove(tile)
        try:
            self.remove_subview(tile)
        except:
            pass

    def _spawn_fraction_result_tile(self, numer, denom, x, y):
        """Spawn a FractionTile as a result (orange)."""
        ft = FractionTile(self)
        self.add_subview(ft)
        self.tiles.append(ft)
        ft.set_tile_color('#FFB347')
        ft.set_fraction_numer(int(numer))
        ft.set_fraction_denom(int(denom))
        ft.x = clamp(x, PADDING, self.width - ft.width - PADDING)
        ft.y = clamp(y, PADDING, self.height - ft.height - PADDING)
        if self.snap_enabled:
            try:
                ft.snap_to_grid()
            except:
                pass
        ft.bring_to_front()
        return ft

    def _spawn_eval_result(self, val, x, y):
        """Spawn appropriate result tile with type-aware coloring."""
        from fractions import Fraction
        import sympy

        # Expression with free symbols → green expr tile
        if hasattr(val, 'free_symbols') and val.free_symbols:
            rt = Tile(self)
            self.add_subview(rt)
            self.tiles.append(rt)
            rt.kind = 'expr'
            rt.expr_str = str(val)
            rt.set_label(self._sympy_pretty_label(val))
            rt.set_tile_color('#7ED6A8')
            try:
                rt.label.text_color = '#000000'
            except:
                pass
            rt.x = clamp(x, PADDING, self.width - rt.width - PADDING)
            rt.y = clamp(y, PADDING, self.height - rt.height - PADDING)
            if self.snap_enabled:
                try:
                    rt.snap_to_grid()
                except:
                    pass
            rt.bring_to_front()
            return rt

        # Sympy Rational with non-1 denom → orange fraction
        if isinstance(val, sympy.Rational) and val.q != 1:
            return self._spawn_fraction_result_tile(int(val.p), int(val.q), x, y)

        # Convert sympy numeric to python
        if hasattr(val, 'is_number') and val.is_number:
            try:
                if val == int(val):
                    val = int(val)
                else:
                    val = float(val)
            except:
                val = float(val)

        # Python Fraction → orange fraction
        if isinstance(val, Fraction) and val.denominator != 1:
            return self._spawn_fraction_result_tile(val.numerator, val.denominator, x, y)

        # Determine display text and color
        if isinstance(val, bool):
            text = '1' if val else '0'
        elif isinstance(val, int):
            text = str(val)
        elif isinstance(val, float):
            if abs(val - round(val)) < 1e-12:
                text = str(int(round(val)))
            else:
                text = '{:.10g}'.format(val)
        else:
            text = str(val)

        # Decimal results → orange, integer → yellow
        is_decimal = isinstance(val, float) and abs(val - round(val)) >= 1e-12
        tile_color = '#FFB347' if is_decimal else '#FFD60A'

        rt = Tile(self)
        self.add_subview(rt)
        self.tiles.append(rt)
        rt.kind = 'result'
        rt.expr_str = text
        rt.set_label(text)
        rt.set_tile_color(tile_color)
        try:
            rt.label.text_color = '#000000'
        except:
            pass
        rt.x = clamp(x, PADDING, self.width - rt.width - PADDING)
        rt.y = clamp(y, PADDING, self.height - rt.height - PADDING)
        if self.snap_enabled:
            try:
                rt.snap_to_grid()
            except:
                pass
        rt.bring_to_front()
        return rt

    def _eval_expr_smart(self, expr):
        """Evaluate expression with automatic fraction and algebra support via sympy."""
        import sympy
        import re
        expr = (expr or '').strip()
        if not expr:
            return None
        expr = re.sub(r'\((-?\d+)/(-?\d+)\)', r'Rational(\1,\2)', expr)
        expr = expr.replace('^', '**')
        try:
            result = sympy.sympify(expr, locals={'Rational': sympy.Rational})
            if hasattr(result, 'free_symbols') and result.free_symbols:
                return sympy.expand(result)
            if result.is_number:
                if isinstance(result, sympy.Rational) and result.q != 1:
                    from fractions import Fraction
                    return Fraction(int(result.p), int(result.q))
                try:
                    if result == int(result):
                        return int(result)
                except:
                    pass
                return float(result)
            return result
        except:
            pass
        try:
            return eval(expr, {"__builtins__": {}}, {})
        except:
            return None

    def _sympy_parse(self, s):
        """Parse a tile expr_str into a sympy expression."""
        import sympy
        import re
        s = (s or '').strip()
        if not s:
            return None
        s = re.sub(r'\((-?\d+)/(-?\d+)\)', r'Rational(\1,\2)', s)
        s = s.replace('^', '**')
        try:
            return sympy.sympify(s, locals={'Rational': sympy.Rational})
        except:
            return None


    def _sympy_pretty_label(self, expr):
        """Convert sympy expression to a clean display string."""
        import sympy
        import re
        try:
            s = sympy.sstr(expr)
        except:
            s = str(expr)
        supers = {'**2': '²', '**3': '³', '**4': '⁴', '**5': '⁵',
                  '**6': '⁶', '**7': '⁷', '**8': '⁸', '**9': '⁹'}
        for k, v in supers.items():
            s = s.replace(k, v)
        s = re.sub(r'(\d)\*([a-zA-Z])', r'\1\2', s)
        s = re.sub(r'([a-zA-Z²³⁴⁵⁶⁷⁸⁹])\*([a-zA-Z])', r'\1\2', s)
        return s



    def convert_to_fraction(self, tile):
        """Convert a / operator tile into a FractionTile."""
        if not tile or getattr(tile, 'kind', '') != 'op':
            return
        if getattr(tile, 'expr_str', '').strip() != '/':
            return
        self.save_state()
        x, y = tile.x, tile.y
        if tile in self.tiles:
            self.tiles.remove(tile)
        try:
            self.remove_subview(tile)
        except:
            pass
        ft = FractionTile(self)
        self.add_subview(ft)
        self.tiles.append(ft)
        ft.set_tile_color('#FFB347')
        ft.x = clamp(x, PADDING, self.width - ft.width - PADDING)
        ft.y = clamp(y, PADDING, self.height - ft.height - PADDING)
        if self.snap_enabled:
            try:
                ft.snap_to_grid()
            except:
                pass
        ft.bring_to_front()



    def convert_from_fraction(self, frac_tile):
        """Convert an empty FractionTile back to a / operator tile."""
        if not frac_tile or getattr(frac_tile, 'kind', '') != 'fraction':
            return
        if getattr(frac_tile, 'numer', None) is not None or getattr(frac_tile, 'denom', None) is not None:
            return
        self.save_state()
        x, y = frac_tile.x, frac_tile.y
        sticky = getattr(frac_tile, '_sticky', False)
        if frac_tile in self.tiles:
            self.tiles.remove(frac_tile)
        try:
            self.remove_subview(frac_tile)
        except:
            pass
        t = Tile(self)
        self.add_subview(t)
        self.tiles.append(t)
        t.kind = 'op'
        t.expr_str = '/'
        t.set_label('/')
        t.set_tile_color('#6B9FFF')
        t._sticky = sticky
        if sticky:
            t.border_width = 3
            t.border_color = '#FFFFFF'
        try:
            t.label.text_color = '#FFFFFF'
        except:
            pass
        t.x = clamp(x, PADDING, self.width - t.width - PADDING)
        t.y = clamp(y, PADDING, self.height - t.height - PADDING)
        if self.snap_enabled:
            try:
                t.snap_to_grid()
            except:
                pass

    def _all_spawners(self):
        """Return all spawners with correct colors applied."""
        # Hide legacy spawners
        try:
            self.source.hidden = True
        except:
            pass
        try:
            self.frac_spawner.hidden = True
        except:
            pass

        # Recolor ops to unified slate blue
        for sp in self.op_spawners:
            sp.tile_color = '#6B9FFF'
            sp.background_color = '#6B9FFF'
            try:
                sp.label.text_color = '#FFFFFF'
            except:
                pass

        # Recolor equals to lavender
        self.equals_spawner.tile_color = '#C4B5FD'
        self.equals_spawner.background_color = '#C4B5FD'
        try:
            self.equals_spawner.label.text_color = '#000000'
        except:
            pass

        # Recolor factor to soft purple
        self.factor_spawner.tile_color = '#C084FC'
        self.factor_spawner.background_color = '#C084FC'
        try:
            self.factor_spawner.label.text_color = '#FFFFFF'
        except:
            pass

        # Lazy create special spawners
        if not hasattr(self, 'dot_spawner'):
            self.dot_spawner = TokenSpawner(self, '.', kind='number', color='#FFB347', text_color='#000000')
            self.add_subview(self.dot_spawner)
        if not hasattr(self, 'expr_spawner'):
            self.expr_spawner = TokenSpawner(self, 'x', kind='expr', color='#7ED6A8', text_color='#000000')
            self.add_subview(self.expr_spawner)
        if not hasattr(self, 'split_spawner'):
            self.split_spawner = TokenSpawner(self, '✂', kind='split', color='#FDA4AF', text_color='#FFFFFF')
            self.add_subview(self.split_spawner)

        return (self.digit_spawners +
                self.op_spawners +
                [self.equals_spawner, self.factor_spawner,
                 self.dot_spawner, self.expr_spawner, self.split_spawner])


    def _capture_tile_snapshot(self, tile):
        """Capture a single tile's state for split undo."""
        kind = getattr(tile, 'kind', 'generic')
        d = {
            'x': tile.x, 'y': tile.y,
            'width': tile.width, 'height': tile.height,
            'label_text': getattr(tile, 'label_text', ''),
            'tile_color': getattr(tile, 'tile_color', '#FFD60A'),
            'kind': kind,
            'expr_str': getattr(tile, 'expr_str', ''),
            'pending_op': getattr(tile, 'pending_op', None),
            'group_id': getattr(tile, 'group_id', None),
            '_sticky': getattr(tile, '_sticky', False),
        }
        if kind == 'fraction':
            d['numer'] = getattr(tile, 'numer', None)
            d['denom'] = getattr(tile, 'denom', None)
        if kind == 'subst':
            sv = getattr(tile, 'subst_val', None)
            d['subst_val'] = str(sv) if sv is not None else None
        try:
            d['label_text_color'] = tile.label.text_color
        except:
            pass
        return d

    def split_tile(self, tile):
        """Reverse a merge: remove tile, respawn its pre-merge components."""
        snapshot = getattr(tile, '_split_snapshot', None)
        if not snapshot:
            return
        self.save_state()
        if tile in self.tiles:
            self.tiles.remove(tile)
        try:
            self.remove_subview(tile)
        except:
            pass
        for td in snapshot:
            kind = td.get('kind', 'generic')
            if kind == 'fraction':
                t = FractionTile(self)
                t.x = td.get('x', PADDING)
                t.y = td.get('y', PADDING)
                t.width = td.get('width', TILE_SIZE)
                t.height = td.get('height', TILE_SIZE + GRID_SIZE)
                t.kind = 'fraction'
                t.group_id = td.get('group_id', None)
                try:
                    t.set_tile_color(td.get('tile_color', TILE_COLOR))
                except:
                    pass
                numer = td.get('numer', None)
                denom = td.get('denom', None)
                if numer is not None:
                    try:
                        t.set_fraction_numer(int(numer))
                    except:
                        pass
                if denom is not None:
                    try:
                        t.set_fraction_denom(int(denom))
                    except:
                        pass
                if t.group_id:
                    try:
                        t.set_grouped(True)
                    except:
                        pass
            else:
                t = Tile(self)
                t.x = td.get('x', PADDING)
                t.y = td.get('y', PADDING)
                t.width = td.get('width', TILE_SIZE)
                t.height = td.get('height', TILE_SIZE)
                t.kind = kind
                t.expr_str = td.get('expr_str', '')
                t.pending_op = td.get('pending_op', None)
                t.group_id = td.get('group_id', None)
                t.set_label(td.get('label_text', ''))
                t.set_tile_color(td.get('tile_color', TILE_COLOR))
                try:
                    lc = td.get('label_text_color', None)
                    if lc:
                        t.label.text_color = lc
                except:
                    pass
                if t.group_id:
                    t.set_grouped(True)
            self.add_subview(t)
            self.tiles.append(t)
            if self.snap_enabled:
                try:
                    t.snap_to_grid()
                except:
                    pass
        try:
            self._spread_out_tiles()
        except Exception as e:
            print('Split spread error:', e)

    # ----------------------------------------------------------
    # Fraction merge
    # ----------------------------------------------------------

    def _parse_int_tile(self, t):
        s = str(getattr(t, 'expr_str', getattr(t, 'label_text', '')) or '').strip()
        if not s:
            return None
        if s.startswith('-'):
            core = s[1:]
            if not core.isdigit():
                return None
            return -int(core)
        if not s.isdigit():
            return None
        return int(s)

    def try_fraction_merge(self, dropped):
        if dropped is None or dropped.superview is None:
            return False
        if getattr(dropped, 'group_id', None):
            return False

        dk = getattr(dropped, 'kind', '')

        if dk == 'fraction':
            best, _ = self._best_overlap(dropped)
            if not best:
                return False
            if getattr(best, 'kind', '') not in ('number', 'generic', 'result'):
                return False
            if getattr(best, 'group_id', None):
                return False
            n = self._parse_int_tile(best)
            if n is None:
                return False
            return self._fraction_absorb_number(dropped, best, n)

        if dk in ('number', 'generic', 'result'):
            best, _ = self._best_overlap(dropped, allowed_kinds=('fraction',))
            if not best:
                return False
            n = self._parse_int_tile(dropped)
            if n is None:
                return False
            return self._fraction_absorb_number(best, dropped, n)

        return False



    def _fraction_absorb_number(self, frac_tile, num_tile, n):
        if getattr(frac_tile, 'kind', '') != 'fraction':
            return False
        if getattr(frac_tile, 'group_id', None):
            return False

        numer = getattr(frac_tile, 'numer', None)
        denom = getattr(frac_tile, 'denom', None)
        if numer is not None and denom is not None:
            return False

        self.save_state()
        if numer is None:
            frac_tile.set_fraction_numer(n)
        else:
            if n == 0:
                print('Fraction: Denominator cannot be 0')
                return False
            frac_tile.set_fraction_denom(n)

        self._consume_tile(num_tile)

        if getattr(frac_tile, 'numer', None) is not None and getattr(frac_tile, 'denom', None) is not None:
            frac_tile.expr_str = f'({frac_tile.numer}/{frac_tile.denom})'

        frac_tile.set_tile_color('#FFB347')
        if self.snap_enabled:
            try:
                frac_tile.snap_to_grid()
            except:
                pass
        frac_tile.bring_to_front()
        return True

    # ----------------------------------------------------------
    # Combine (menu-based, for single operator)
    # ----------------------------------------------------------



    def combine_operation(self, op_tile):
        if not op_tile or getattr(op_tile, 'kind', '') != 'op':
            return

        adjacent = self.get_adjacent_tiles_4way(op_tile)

        ordered = []
        for d in ['left', 'top', 'right', 'bottom']:
            t = adjacent[d]
            if t:
                ordered.append(t)

        if len(ordered) < 2:
            print('Combine: Need at least 2 adjacent tiles')
            return

        self.save_state()

        op_str = getattr(op_tile, 'expr_str', getattr(op_tile, 'label_text', '')).strip()
        parts = []
        for t in ordered:
            s = getattr(t, 'expr_str', getattr(t, 'label_text', '')).strip()
            if s:
                parts.append(f'({s})')

        if not parts:
            return

        expr = f' {op_str} '.join(parts)
        val = self._eval_expr_smart(expr)
        if val is None:
            return

        rx, ry = op_tile.x, op_tile.y

        for t in ordered:
            if t in self.tiles:
                self.tiles.remove(t)
            try:
                self.remove_subview(t)
            except:
                pass
        if op_tile in self.tiles:
            self.tiles.remove(op_tile)
        try:
            self.remove_subview(op_tile)
        except:
            pass

        rt = self._spawn_eval_result(val, rx, ry)

    # ----------------------------------------------------------
    # Factorize
    # ----------------------------------------------------------

    def get_prime_factors(self, n):
        try:
            n = int(abs(float(n)))
        except:
            return None
        if n <= 1:
            return []
        factors = []
        d = 2
        while d * d <= n:
            while n % d == 0:
                factors.append(d)
                n //= d
            d += 1
        if n > 1:
            factors.append(n)
        return factors

    def combine_factors_to_fit(self, factors, max_tiles=8):
        if len(factors) <= max_tiles:
            return factors
        from collections import Counter
        pc = Counter(factors)
        result = []
        for p in sorted(pc):
            c = pc[p]
            while c > 0 and len(result) < max_tiles:
                left = max_tiles - len(result)
                if left == 1:
                    result.append(p ** c)
                    c = 0
                elif c >= 3:
                    result.append(p ** 3); c -= 3
                elif c >= 2:
                    result.append(p ** 2); c -= 2
                else:
                    result.append(p); c -= 1
        return result

    def _spawn_factor_tiles(self, tile, factors):
        display = self.combine_factors_to_fit(factors, max_tiles=8)
        cx, cy = tile.x, tile.y

        if tile in self.tiles:
            self.tiles.remove(tile)
        try:
            self.remove_subview(tile)
        except:
            pass

        positions = []
        for dy in [-GRID_SIZE, 0, GRID_SIZE]:
            for dx in [-GRID_SIZE, 0, GRID_SIZE]:
                if dx == 0 and dy == 0:
                    continue
                positions.append((
                    clamp(cx + dx, PADDING, self.width - TILE_SIZE - PADDING),
                    clamp(cy + dy, PADDING, self.height - TILE_SIZE - PADDING),
                ))

        for i, val in enumerate(display):
            if i >= len(positions):
                break
            x, y = positions[i]
            t = Tile(self)
            self.add_subview(t)
            self.tiles.append(t)
            t.kind = 'number'
            t.expr_str = str(val)
            t.set_label(str(val))
            t.set_tile_color(TILE_COLOR)
            t.x, t.y = x, y
            if self.snap_enabled:
                try:
                    t.snap_to_grid()
                except:
                    pass




    def factorize_tile(self, factor_tile):
        if not factor_tile or getattr(factor_tile, 'kind', '') != 'factor':
            return

        hits = self.find_all_overlapping_tiles(factor_tile)
        target = hits[0] if hits else None
        if not target:
            print('Factor: No adjacent tile detected')
            return
        if getattr(target, 'group_id', None):
            print('Factor: Cannot factor grouped tiles')
            return

        target_kind = getattr(target, 'kind', '')

        if target_kind == 'expr':
            import sympy
            parsed = self._sympy_parse(getattr(target, 'expr_str', ''))
            if parsed is None:
                print('Factor: Could not parse expression')
                return
            try:
                factored = sympy.factor(parsed)
            except:
                print('Factor: sympy.factor failed')
                return
            if factored == parsed:
                print('Factor: Already in factored form')
                return
            factors = []
            for arg in sympy.Mul.make_args(factored):
                base, exp = arg.as_base_exp()
                if exp.is_integer and exp > 0:
                    for _ in range(int(exp)):
                        factors.append(base)
                else:
                    factors.append(arg)
            if len(factors) < 2:
                self.save_state()
                target.expr_str = str(factored)
                target.set_label(self._sympy_pretty_label(factored))
                self._consume_tile(factor_tile)
                return
            self.save_state()
            cx, cy = target.x, target.y
            self._consume_tile(factor_tile)
            if target in self.tiles:
                self.tiles.remove(target)
            try:
                self.remove_subview(target)
            except:
                pass
            max_cols = max(1, int((self.width - 2 * PADDING) / GRID_SIZE))
            row, col = 0, 0
            for f in factors:
                f_str = str(f)
                f_label = self._sympy_pretty_label(f)
                t = Tile(self)
                self.add_subview(t)
                self.tiles.append(t)
                if f.is_number:
                    t.kind = 'number'
                    try:
                        if f == int(f):
                            f_str = str(int(f))
                            f_label = f_str
                    except:
                        pass
                    t.set_tile_color('#FFD60A')
                else:
                    t.kind = 'expr'
                    t.set_tile_color('#7ED6A8')
                    try:
                        t.label.text_color = '#000000'
                    except:
                        pass
                t.expr_str = f_str
                t.set_label(f_label)
                tx = cx + col * GRID_SIZE
                ty = cy + row * GRID_SIZE
                t.x = clamp(tx, PADDING, self.width - t.width - PADDING)
                t.y = clamp(ty, PADDING, self.height - t.height - PADDING)
                if self.snap_enabled:
                    try:
                        t.snap_to_grid()
                    except:
                        pass
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
            try:
                self._spread_out_tiles()
            except:
                pass
            return

        if target_kind not in ('number', 'generic', 'result'):
            print('Factor: Target must be a number or expression')
            return
        num_str = getattr(target, 'expr_str', getattr(target, 'label_text', '')).strip()
        try:
            num = float(num_str)
            if num != int(num):
                print('Factor: Only integers'); return
            num = int(num)
        except:
            print('Factor: Not a valid number'); return
        factors = self.get_prime_factors(num)
        if not factors:
            print('Factor: Cannot factor 0 or 1'); return
        if len(factors) == 1 and factors[0] == abs(num):
            print(f'Factor: {num} is prime'); return
        self.save_state()
        self._consume_tile(factor_tile)
        self._spawn_factor_tiles(target, factors)

    def factorize_tile_direct(self, tile):
        if not tile or tile not in self.tiles:
            return

        kind = getattr(tile, 'kind', '')
        if kind not in ('number', 'generic', 'result'):
            return
        if getattr(tile, 'group_id', None):
            print('Factor: Cannot factor grouped tiles')
            return

        num_str = getattr(tile, 'expr_str', getattr(tile, 'label_text', '')).strip()
        try:
            num = float(num_str)
            if num != int(num):
                print('Factor: Only integers'); return
            num = int(num)
        except:
            print('Factor: Not a valid number'); return

        factors = self.get_prime_factors(num)
        if not factors:
            print('Factor: Cannot factor 0 or 1'); return
        if len(factors) == 1 and factors[0] == abs(num):
            print(f'Factor: {num} is prime'); return

        self.save_state()
        self._spawn_factor_tiles(tile, factors)

    # ----------------------------------------------------------
    # Compound operator tiles (num_op)
    # ----------------------------------------------------------



    def try_compound_merge(self, dropped):
        if dropped is None or dropped.superview is None:
            return False

        dk = getattr(dropped, 'kind', '')

        if dk == 'equals':
            return False

        if dk not in ('op', 'num_op', 'number', 'generic', 'result', 'fraction', 'expr'):
            return False
        if getattr(dropped, 'group_id', None):
            return False
        if dk == 'fraction' and (getattr(dropped, 'numer', None) is None or getattr(dropped, 'denom', None) is None):
            return False

        dx, dy, dw, dh = dropped.x, dropped.y, dropped.width, dropped.height
        best, best_area = None, 0.0

        for t in self.tiles:
            if t is dropped or t.superview is None or t.superview is not self:
                continue
            if getattr(t, 'group_id', None):
                continue

            if getattr(t, 'kind', '') == 'equals':
                continue

            if getattr(t, 'kind', '') == 'fraction' and (getattr(t, 'numer', None) is None or getattr(t, 'denom', None) is None):
                continue

            ix1 = max(dx, t.x)
            iy1 = max(dy, t.y)
            ix2 = min(dx + dw, t.x + t.width)
            iy2 = min(dy + dh, t.y + t.height)

            if ix2 > ix1 and iy2 > iy1:
                area = (ix2 - ix1) * (iy2 - iy1)
                if area > best_area:
                    best_area = area
                    best = t

        if best is None:
            return False

        min_tile_area = min(dw * dh, best.width * best.height)
        if min_tile_area <= 0 or (best_area / min_tile_area) < 0.25:
            return False

        tk = getattr(best, 'kind', '')

        num_kinds = ('number', 'generic', 'result', 'fraction', 'expr')

        if dk == 'op' and tk in num_kinds:
            return self._create_compound_tile(best, dropped)

        if dk in num_kinds and tk == 'op':
            return self._create_compound_tile(dropped, best)

        if dk in num_kinds and tk == 'num_op':
            return self._evaluate_compound(best, dropped)

        if dk == 'num_op' and tk in num_kinds:
            return self._evaluate_compound(dropped, best)

        return False



    def try_decimal_merge(self, dropped):
        """Handle decimal point tile merges (dot as string modifier)."""
        if dropped is None or dropped.superview is None:
            return False
        if getattr(dropped, 'group_id', None):
            return False

        dk = getattr(dropped, 'kind', '')
        if dk in ('op', 'factor', 'fraction', 'equals', 'num_op', 'negate', 'split', 'subst'):
            return False

        d_expr = str(getattr(dropped, 'expr_str', '') or '').strip()

        best, _ = self._best_overlap(dropped)
        if not best:
            return False

        bk = getattr(best, 'kind', '')
        if bk in ('op', 'factor', 'fraction', 'equals', 'num_op', 'negate', 'split', 'subst'):
            return False
        if getattr(best, 'group_id', None):
            return False

        b_expr = str(getattr(best, 'expr_str', '') or '').strip()

        if d_expr == '.':
            if not self._is_decimal_numeric(b_expr):
                return False
            if '.' in b_expr:
                return False
            self.save_state()
            best.expr_str = b_expr + '.'
            best.set_label(best.expr_str)
            best.set_tile_color('#FFB347')
            self._consume_tile(dropped)
            return True

        if b_expr == '.':
            if not self._is_decimal_numeric(d_expr):
                return False
            if '.' in d_expr:
                return False
            self.save_state()
            merged = '.' + d_expr
            best.expr_str = merged
            best.set_label(merged)
            best.kind = dk
            best.set_tile_color('#FFB347')
            try:
                best.label.text_color = '#000000'
            except:
                pass
            self._consume_tile(dropped)
            return True

        return False


    def try_negate_merge(self, dropped):
        if dropped is None or dropped.superview is None:
            return False
        if getattr(dropped, 'group_id', None):
            return False

        dk = getattr(dropped, 'kind', '')
        d_expr = str(getattr(dropped, 'expr_str', '') or '').strip()
        best, _ = self._best_overlap(dropped)
        if not best:
            return False
        bk = getattr(best, 'kind', '')
        b_expr = str(getattr(best, 'expr_str', '') or '').strip()
        if getattr(best, 'group_id', None):
            return False

        if dk == 'negate' and bk == 'expr':
            import sympy
            parsed = self._sympy_parse(b_expr)
            if parsed is None:
                return False
            negated = sympy.expand(-parsed)
            self.save_state()
            best.expr_str = str(negated)
            best.set_label(self._sympy_pretty_label(negated))
            self._consume_tile(dropped)
            return True

        if dk == 'negate' and bk in ('number', 'result', 'generic'):
            if not self._is_decimal_numeric(b_expr):
                return False
            self.save_state()
            toggled = b_expr[1:] if b_expr.startswith('-') else '-' + b_expr
            best.expr_str = toggled
            best.set_label(toggled)
            self._consume_tile(dropped)
            return True

        if bk == 'negate' and dk == 'expr':
            import sympy
            parsed = self._sympy_parse(d_expr)
            if parsed is None:
                return False
            negated = sympy.expand(-parsed)
            self.save_state()
            best.expr_str = str(negated)
            best.set_label(self._sympy_pretty_label(negated))
            best.kind = 'expr'
            best.set_tile_color('#7ED6A8')
            try:
                best.label.text_color = '#000000'
            except:
                pass
            self._consume_tile(dropped)
            return True

        if bk == 'negate' and dk in ('number', 'result', 'generic'):
            if not self._is_decimal_numeric(d_expr):
                return False
            self.save_state()
            toggled = d_expr[1:] if d_expr.startswith('-') else '-' + d_expr
            best.expr_str = toggled
            best.set_label(toggled)
            best.kind = dk
            best.set_tile_color(getattr(dropped, 'tile_color', '#FFD60A'))
            try:
                best.label.text_color = '#000000'
            except:
                pass
            self._consume_tile(dropped)
            return True

        return False


    def try_expr_merge(self, dropped):
        """Direct overlap between expr and number/expr tiles means multiply."""
        if dropped is None or dropped.superview is None:
            return False
        if getattr(dropped, 'group_id', None):
            return False

        dk = getattr(dropped, 'kind', '')
        best, _ = self._best_overlap(dropped)
        if not best:
            return False
        bk = getattr(best, 'kind', '')
        if getattr(best, 'group_id', None):
            return False

        if dk != 'expr' and bk != 'expr':
            return False
        allowed = ('number', 'result', 'generic', 'expr')
        if dk not in allowed or bk not in allowed:
            return False

        d_parsed = self._sympy_parse(getattr(dropped, 'expr_str', ''))
        b_parsed = self._sympy_parse(getattr(best, 'expr_str', ''))
        if d_parsed is None or b_parsed is None:
            return False

        import sympy
        result = sympy.expand(d_parsed * b_parsed)

        self.save_state()
        rx = min(best.x, dropped.x)
        ry = min(best.y, dropped.y)
        self._consume_tile(best)
        self._consume_tile(dropped)
        rt = self._spawn_eval_result(result, rx, ry)
        return True


    def try_subst_merge(self, dropped):
        """Handle substitution tile (x=) merges. Non-destructive on expr."""
        if dropped is None or dropped.superview is None:
            return False
        if getattr(dropped, 'group_id', None):
            return False

        dk = getattr(dropped, 'kind', '')
        best, _ = self._best_overlap(dropped)
        if not best:
            return False
        bk = getattr(best, 'kind', '')
        if getattr(best, 'group_id', None):
            return False

        if dk != 'subst' and bk != 'subst':
            return False

        import sympy

        # Unbound subst (x=) + number → bind value (x=3)
        if dk == 'subst' and getattr(dropped, 'subst_val', None) is None and bk in ('number', 'result', 'generic'):
            val = self._sympy_parse(getattr(best, 'expr_str', ''))
            if val is None:
                return False
            self.save_state()
            dropped.subst_val = val
            label = f'x={self._sympy_pretty_label(val)}'
            dropped.expr_str = f'x={val}'
            dropped.set_label(label)
            dropped.set_tile_color('#A78BFA')
            self._consume_tile(best)
            return True

        if bk == 'subst' and getattr(best, 'subst_val', None) is None and dk in ('number', 'result', 'generic'):
            val = self._sympy_parse(getattr(dropped, 'expr_str', ''))
            if val is None:
                return False
            self.save_state()
            best.subst_val = val
            label = f'x={self._sympy_pretty_label(val)}'
            best.expr_str = f'x={val}'
            best.set_label(label)
            best.set_tile_color('#A78BFA')
            self._consume_tile(dropped)
            return True

        # Bound subst (x=3) + expr → evaluate (expr survives)
        if dk == 'subst' and getattr(dropped, 'subst_val', None) is not None and bk == 'expr':
            parsed = self._sympy_parse(getattr(best, 'expr_str', ''))
            if parsed is None:
                return False
            x = sympy.Symbol('x')
            result = parsed.subs(x, dropped.subst_val)
            try:
                result = sympy.simplify(result)
            except:
                pass
            self.save_state()
            rx = clamp(best.x + GRID_SIZE, PADDING, self.width - TILE_SIZE - PADDING)
            ry = best.y
            self._consume_tile(dropped)
            rt = self._spawn_eval_result(result, rx, ry)
            try:
                self._spread_out_tiles()
            except:
                pass
            return True

        if bk == 'subst' and getattr(best, 'subst_val', None) is not None and dk == 'expr':
            parsed = self._sympy_parse(getattr(dropped, 'expr_str', ''))
            if parsed is None:
                return False
            x = sympy.Symbol('x')
            result = parsed.subs(x, best.subst_val)
            try:
                result = sympy.simplify(result)
            except:
                pass
            self.save_state()
            rx = clamp(dropped.x + GRID_SIZE, PADDING, self.width - TILE_SIZE - PADDING)
            ry = dropped.y
            self._consume_tile(best)
            rt = self._spawn_eval_result(result, rx, ry)
            try:
                self._spread_out_tiles()
            except:
                pass
            return True

        return False


    def try_split_merge(self, split_tile):
        """Split/Supersplit tile: structural decomposition of target tile."""
        if not split_tile:
            return False
        s_kind = getattr(split_tile, 'kind', '')
        if s_kind not in ('split', 'supersplit'):
            return False

        is_super = (s_kind == 'supersplit')

        hits = self.find_all_overlapping_tiles(split_tile)
        target = hits[0] if hits else None
        if not target:
            return False
        if getattr(target, 'group_id', None):
            return False

        tk = getattr(target, 'kind', '')

        # --- Numbers ---
        if tk in ('number', 'generic', 'result'):
            expr = str(getattr(target, 'expr_str', '') or '').strip()
            if not expr or len(expr) < 2:
                return False

            if is_super:
                # All digits/chars individually
                chars = list(expr)
                if len(chars) < 2:
                    return False
                self.save_state()
                rx, ry = target.x, target.y
                if target in self.tiles:
                    self.tiles.remove(target)
                try:
                    self.remove_subview(target)
                except:
                    pass
                self._consume_tile(split_tile)
                col = 0
                for ch in chars:
                    t = Tile(self)
                    self.add_subview(t)
                    self.tiles.append(t)
                    if ch == '.':
                        t.kind = 'number'
                        t.expr_str = '.'
                        t.set_label('.')
                        t.set_tile_color('#FFB347')
                    elif ch == '-':
                        t.kind = 'negate'
                        t.expr_str = '±'
                        t.set_label('±')
                        t.set_tile_color('#F87171')
                        try:
                            t.label.text_color = '#FFFFFF'
                        except:
                            pass
                    else:
                        t.kind = 'number'
                        t.expr_str = ch
                        t.set_label(ch)
                        t.set_tile_color('#FFD60A')
                    t.x = clamp(rx + col * GRID_SIZE, PADDING, self.width - t.width - PADDING)
                    t.y = ry
                    if self.snap_enabled:
                        try:
                            t.snap_to_grid()
                        except:
                            pass
                    col += 1
                try:
                    self._spread_out_tiles()
                except:
                    pass
                return True
            else:
                # Peel last digit
                if not expr[-1].isdigit():
                    return False
                remaining = expr[:-1]
                peeled = expr[-1]
                if not remaining or remaining == '-':
                    return False
                self.save_state()
                target.expr_str = remaining
                target.set_label(remaining)
                self._consume_tile(split_tile)
                t = Tile(self)
                self.add_subview(t)
                self.tiles.append(t)
                t.kind = 'number'
                t.expr_str = peeled
                t.set_label(peeled)
                t.set_tile_color('#FFD60A')
                t.x = clamp(target.x + GRID_SIZE, PADDING, self.width - t.width - PADDING)
                t.y = target.y
                if self.snap_enabled:
                    try:
                        t.snap_to_grid()
                    except:
                        pass
                try:
                    self._spread_out_tiles()
                except:
                    pass
                return True

        # --- num_op ---
        if tk == 'num_op':
            num_str = getattr(target, 'expr_str', '').strip()
            op_str = getattr(target, 'pending_op', '').strip()
            if not num_str or not op_str:
                return False
            self.save_state()
            rx, ry = target.x, target.y
            if target in self.tiles:
                self.tiles.remove(target)
            try:
                self.remove_subview(target)
            except:
                pass
            self._consume_tile(split_tile)
            parsed = self._sympy_parse(num_str)
            is_expr = parsed is not None and hasattr(parsed, 'free_symbols') and parsed.free_symbols
            nt = Tile(self)
            self.add_subview(nt)
            self.tiles.append(nt)
            if is_expr:
                nt.kind = 'expr'
                nt.expr_str = num_str
                nt.set_label(self._sympy_pretty_label(parsed))
                nt.set_tile_color('#7ED6A8')
            else:
                nt.kind = 'number'
                nt.expr_str = num_str
                nt.set_label(num_str)
                nt.set_tile_color('#FFD60A')
            try:
                nt.label.text_color = '#000000'
            except:
                pass
            nt.x = rx
            nt.y = ry
            ot = Tile(self)
            self.add_subview(ot)
            self.tiles.append(ot)
            ot.kind = 'op'
            ot.expr_str = op_str
            ot.set_label(op_str)
            ot.set_tile_color('#6B9FFF')
            try:
                ot.label.text_color = '#FFFFFF'
            except:
                pass
            ot.x = clamp(rx + GRID_SIZE, PADDING, self.width - ot.width - PADDING)
            ot.y = ry
            if self.snap_enabled:
                try:
                    nt.snap_to_grid()
                    ot.snap_to_grid()
                except:
                    pass
            try:
                self._spread_out_tiles()
            except:
                pass
            return True

        # --- Fraction ---
        if tk == 'fraction':
            denom = getattr(target, 'denom', None)
            numer = getattr(target, 'numer', None)
            if denom is not None:
                self.save_state()
                val = int(denom)
                target.denom = None
                target.expr_str = ''
                target._refresh_display()
                self._consume_tile(split_tile)
                t = Tile(self)
                self.add_subview(t)
                self.tiles.append(t)
                t.kind = 'number'
                t.expr_str = str(val)
                t.set_label(str(val))
                t.set_tile_color('#FFD60A')
                t.x = clamp(target.x + GRID_SIZE, PADDING, self.width - t.width - PADDING)
                t.y = target.y
                if self.snap_enabled:
                    try:
                        t.snap_to_grid()
                    except:
                        pass
                try:
                    self._spread_out_tiles()
                except:
                    pass
                return True
            if numer is not None:
                self.save_state()
                val = int(numer)
                target.numer = None
                target.expr_str = ''
                target._refresh_display()
                self._consume_tile(split_tile)
                t = Tile(self)
                self.add_subview(t)
                self.tiles.append(t)
                t.kind = 'number'
                t.expr_str = str(val)
                t.set_label(str(val))
                t.set_tile_color('#FFD60A')
                t.x = clamp(target.x + GRID_SIZE, PADDING, self.width - t.width - PADDING)
                t.y = target.y
                if self.snap_enabled:
                    try:
                        t.snap_to_grid()
                    except:
                        pass
                try:
                    self._spread_out_tiles()
                except:
                    pass
                return True
            return False

        # --- Expr ---
        if tk == 'expr':
            import sympy
            parsed = self._sympy_parse(getattr(target, 'expr_str', ''))
            if parsed is None:
                return False
            terms = list(sympy.Add.make_args(parsed))
            if len(terms) < 2:
                return False

            if is_super:
                # Full decomposition: all terms with op tiles between
                self.save_state()
                rx, ry = target.x, target.y
                if target in self.tiles:
                    self.tiles.remove(target)
                try:
                    self.remove_subview(target)
                except:
                    pass
                self._consume_tile(split_tile)
                col = 0
                for i, term in enumerate(terms):
                    # Insert op tile between terms (after first)
                    if i > 0:
                        is_neg = term.could_extract_minus_sign()
                        if is_neg:
                            op_t = Tile(self)
                            self.add_subview(op_t)
                            self.tiles.append(op_t)
                            op_t.kind = 'op'
                            op_t.expr_str = '-'
                            op_t.set_label('-')
                            op_t.set_tile_color('#6B9FFF')
                            try:
                                op_t.label.text_color = '#FFFFFF'
                            except:
                                pass
                            op_t.x = clamp(rx + col * GRID_SIZE, PADDING, self.width - op_t.width - PADDING)
                            op_t.y = ry
                            if self.snap_enabled:
                                try:
                                    op_t.snap_to_grid()
                                except:
                                    pass
                            col += 1
                            term = -term
                        else:
                            op_t = Tile(self)
                            self.add_subview(op_t)
                            self.tiles.append(op_t)
                            op_t.kind = 'op'
                            op_t.expr_str = '+'
                            op_t.set_label('+')
                            op_t.set_tile_color('#6B9FFF')
                            try:
                                op_t.label.text_color = '#FFFFFF'
                            except:
                                pass
                            op_t.x = clamp(rx + col * GRID_SIZE, PADDING, self.width - op_t.width - PADDING)
                            op_t.y = ry
                            if self.snap_enabled:
                                try:
                                    op_t.snap_to_grid()
                                except:
                                    pass
                            col += 1

                    t_str = str(term)
                    t_label = self._sympy_pretty_label(term)
                    tt = Tile(self)
                    self.add_subview(tt)
                    self.tiles.append(tt)
                    if term.is_number:
                        tt.kind = 'number'
                        try:
                            if term == int(term):
                                t_str = str(int(term))
                                t_label = t_str
                        except:
                            pass
                        tt.set_tile_color('#FFD60A')
                    else:
                        tt.kind = 'expr'
                        tt.set_tile_color('#7ED6A8')
                    try:
                        tt.label.text_color = '#000000'
                    except:
                        pass
                    tt.expr_str = t_str
                    tt.set_label(t_label)
                    tt.x = clamp(rx + col * GRID_SIZE, PADDING, self.width - tt.width - PADDING)
                    tt.y = ry
                    if self.snap_enabled:
                        try:
                            tt.snap_to_grid()
                        except:
                            pass
                    col += 1
                try:
                    self._spread_out_tiles()
                except:
                    pass
                return True
            else:
                # Peel last additive term
                last_term = terms[-1]
                remaining = sympy.Add(*terms[:-1])
                self.save_state()
                remaining_str = str(remaining)
                remaining_parsed = remaining
                if hasattr(remaining_parsed, 'free_symbols') and remaining_parsed.free_symbols:
                    target.kind = 'expr'
                    target.expr_str = remaining_str
                    target.set_label(self._sympy_pretty_label(remaining_parsed))
                    target.set_tile_color('#7ED6A8')
                    try:
                        target.label.text_color = '#000000'
                    except:
                        pass
                else:
                    target.kind = 'result'
                    target.expr_str = remaining_str
                    target.set_label(self._sympy_pretty_label(remaining_parsed))
                    target.set_tile_color('#FFD60A')
                    try:
                        target.label.text_color = '#000000'
                    except:
                        pass
                self._consume_tile(split_tile)
                term_str = str(last_term)
                display = self._sympy_pretty_label(last_term)
                ct = Tile(self)
                self.add_subview(ct)
                self.tiles.append(ct)
                ct.kind = 'num_op'
                ct.expr_str = term_str
                ct.pending_op = '+'
                ct.set_label(display + '+')
                ct.set_tile_color('#6B9FFF')
                try:
                    ct.label.text_color = '#FFFFFF'
                except:
                    pass
                ct.x = clamp(target.x + GRID_SIZE, PADDING, self.width - ct.width - PADDING)
                ct.y = target.y
                if self.snap_enabled:
                    try:
                        ct.snap_to_grid()
                    except:
                        pass
                try:
                    self._spread_out_tiles()
                except:
                    pass
                return True

        # --- Subst: unbind value ---
        if tk == 'subst' and getattr(target, 'subst_val', None) is not None:
            self.save_state()
            import sympy
            val = target.subst_val
            target.subst_val = None
            target.expr_str = 'x='
            target.set_label('x=')
            self._consume_tile(split_tile)
            t = Tile(self)
            self.add_subview(t)
            self.tiles.append(t)
            t.kind = 'number'
            val_str = str(val)
            try:
                if val == int(val):
                    val_str = str(int(val))
            except:
                pass
            t.expr_str = val_str
            t.set_label(self._sympy_pretty_label(val))
            t.set_tile_color('#FFD60A')
            t.x = clamp(target.x + GRID_SIZE, PADDING, self.width - t.width - PADDING)
            t.y = target.y
            if self.snap_enabled:
                try:
                    t.snap_to_grid()
                except:
                    pass
            try:
                self._spread_out_tiles()
            except:
                pass
            return True

        return False

    def _create_compound_tile(self, num_tile, op_tile):
        num_str = getattr(num_tile, 'expr_str', getattr(num_tile, 'label_text', '')).strip()
        op_str = getattr(op_tile, 'expr_str', getattr(op_tile, 'label_text', '')).strip()
        if not num_str or not op_str:
            return False
        if self._sympy_parse(num_str) is None:
            return False

        self.save_state()
        rx, ry = num_tile.x, num_tile.y
        self._consume_tile(num_tile)
        self._consume_tile(op_tile)

        ct = Tile(self)
        self.add_subview(ct)
        self.tiles.append(ct)
        ct.kind = 'num_op'
        ct.expr_str = num_str
        ct.pending_op = op_str

        display_num = num_str
        parsed = self._sympy_parse(num_str)
        if parsed is not None and hasattr(parsed, 'free_symbols') and parsed.free_symbols:
            display_num = self._sympy_pretty_label(parsed)
            s = str(parsed)
            core = s[1:] if s.startswith('-') else s
            if '+' in core or '-' in core:
                display_num = f'({display_num})'

        ct.set_label(display_num + op_str)
        ct.set_tile_color('#6B9FFF')
        try:
            ct.label.text_color = '#FFFFFF'
        except:
            pass
        ct.x = clamp(rx, PADDING, self.width - ct.width - PADDING)
        ct.y = clamp(ry, PADDING, self.height - ct.height - PADDING)
        if self.snap_enabled:
            try:
                ct.snap_to_grid()
            except:
                pass
        ct.bring_to_front()
        return True


    def _evaluate_compound(self, compound_tile, number_tile):
        comp_num = getattr(compound_tile, 'expr_str', '').strip()
        comp_op = getattr(compound_tile, 'pending_op', '').strip()
        other_num = getattr(number_tile, 'expr_str',
                            getattr(number_tile, 'label_text', '')).strip()
        if not comp_num or not comp_op or not other_num:
            return False

        expr = f'({comp_num}) {comp_op} ({other_num})'
        val = self._eval_expr_smart(expr)
        if val is None:
            return False

        self.save_state()
        rx = min(compound_tile.x, number_tile.x)
        ry = min(compound_tile.y, number_tile.y)
        self._consume_tile(compound_tile)
        self._consume_tile(number_tile)
        rt = self._spawn_eval_result(val, rx, ry)
        rt.bring_to_front()
        return True

    # ----------------------------------------------------------
    # Overlay merge (digit concatenation)
    # ----------------------------------------------------------






    def try_overlay_merge(self, dropped):
        if dropped is None or dropped.superview is None:
            return False
        if getattr(dropped, 'kind', '') in ('equals', 'op', 'factor', 'num_op', 'fraction', 'negate', 'split', 'subst'):
            return False
        if getattr(dropped, 'group_id', None):
            return False

        dx, dy, dw, dh = dropped.x, dropped.y, dropped.width, dropped.height
        best, best_area = None, 0.0

        for t in self.tiles:
            if t is dropped or t.superview is None or t.superview is not self:
                continue
            if getattr(t, 'kind', '') in ('equals', 'op', 'factor', 'num_op', 'fraction', 'negate', 'split', 'subst'):
                continue
            if getattr(t, 'group_id', None):
                continue
            ix1, iy1 = max(dx, t.x), max(dy, t.y)
            ix2, iy2 = min(dx + dw, t.x + t.width), min(dy + dh, t.y + t.height)
            if ix2 > ix1 and iy2 > iy1:
                area = (ix2 - ix1) * (iy2 - iy1)
                if area > best_area:
                    best_area = area
                    best = t

        if best is None:
            return False
        min_tile_area = min(dw * dh, best.width * best.height)
        if min_tile_area <= 0 or (best_area / min_tile_area) < 0.25:
            return False

        a = str(getattr(best, 'expr_str', '') or '').strip()
        b = str(getattr(dropped, 'expr_str', '') or '').strip()
        if not (self._is_decimal_numeric(a) and self._is_decimal_numeric(b)):
            return False
        if '.' in a and '.' in b:
            return False
        merged = a + b
        if not self._is_decimal_numeric(merged):
            return False

        self.save_state()
        best.expr_str = merged
        try:
            best.set_label(merged)
        except:
            pass
        best.set_tile_color('#FFB347' if '.' in merged else '#FFD60A')
        try:
            best.label.text_color = '#000000'
        except:
            pass
        self._consume_tile(dropped)
        return True

    # ----------------------------------------------------------
    # "=" tool behavior (copy / evaluate -> spawn result nearby)
    # ----------------------------------------------------------

    def _in_keyboard_zone(self, y_top):
        # y_top is tile's top-left y
        if not self.show_spawners:
            return False
        # Keep at least one grid step above the keyboard top for visibility
        return (y_top + TILE_SIZE) > (self._keyboard_top_y - 2)

    def _grid_aligned_top_left_from_center(self, cx, cy, w, h):
        step = GRID_SIZE
        half = step * 0.5
        grid_cx = PADDING + half + round((cx - (PADDING + half)) / step) * step
        grid_cy = PADDING + half + round((cy - (PADDING + half)) / step) * step
        x = grid_cx - w * 0.5
        y = grid_cy - h * 0.5
        x = clamp(x, PADDING, self.width - w - PADDING)
        y = clamp(y, PADDING, self.height - h - PADDING)
        return x, y

    def _occupied_at(self, x, y, w, h, ignore=None):
        # Simple overlap test against existing tiles (ignore optional tile)
        for t in self.tiles:
            if t is ignore or t.superview is None:
                continue
            if not (x + w <= t.x or t.x + t.width <= x or y + h <= t.y or t.y + t.height <= y):
                return True
        return False

    def _find_spawn_spot_near_equals(self, eq_tile, w=TILE_SIZE, h=TILE_SIZE):
        # Preference order: right, left, below, above
        step = GRID_SIZE
        cx, cy = self.tile_center(eq_tile)
        offsets = [(step, 0), (-step, 0), (0, step), (0, -step)]

        for dx, dy in offsets:
            nx, ny = self._grid_aligned_top_left_from_center(cx + dx, cy + dy, w, h)
            if self._in_keyboard_zone(ny):
                continue
            if not self._occupied_at(nx, ny, w, h, ignore=None):
                return nx, ny

        # Fallback: spiral around equals
        base_x = eq_tile.x
        base_y = eq_tile.y
        for px, py in self._aligned_positions_around(base_x, base_y, max_r=10):
            nx = clamp(px, PADDING, self.width - w - PADDING)
            ny = clamp(py, PADDING, self.height - h - PADDING)
            if self._in_keyboard_zone(ny):
                continue
            if not self._occupied_at(nx, ny, w, h, ignore=None):
                return nx, ny

        return None

    def _is_numeric_like(self, t):
        if t is None or t.superview is None:
            return False
        k = getattr(t, 'kind', '')
        if k == 'fraction':
            return (getattr(t, 'numer', None) is not None and getattr(t, 'denom', None) is not None)
        return k in ('number', 'generic', 'result', 'num_op')

    def _clone_tile_like(self, src):
        k = getattr(src, 'kind', 'generic')
        if k == 'fraction':
            nt = FractionTile(self)
            nt.set_tile_color(getattr(src, 'tile_color', TILE_COLOR))
            n = getattr(src, 'numer', None)
            d = getattr(src, 'denom', None)
            if n is not None:
                try: nt.set_fraction_numer(int(n))
                except: pass
            if d is not None:
                try: nt.set_fraction_denom(int(d))
                except: pass
            if getattr(nt, 'numer', None) is not None and getattr(nt, 'denom', None) is not None:
                nt.expr_str = f'({int(nt.numer)}/{int(nt.denom)})'
            return nt

        nt = Tile(self)
        nt.kind = k
        nt.expr_str = getattr(src, 'expr_str', '')
        nt.pending_op = getattr(src, 'pending_op', None)
        nt.set_label(getattr(src, 'label_text', ''))
        nt.set_tile_color(getattr(src, 'tile_color', TILE_COLOR))
        try:
            nt.label.text_color = src.label.text_color
        except:
            pass
        return nt

    def _spawn_result_tile(self, text, x, y):
        rt = Tile(self)
        self.add_subview(rt)
        self.tiles.append(rt)
        rt.kind = 'result'
        rt.expr_str = text
        rt.set_label(text)
        rt.set_tile_color(RESULT_COLOR)
        try:
            rt.label.text_color = RESULT_TEXT_COLOR
        except:
            pass
        rt.x = clamp(x, PADDING, self.width - rt.width - PADDING)
        rt.y = clamp(y, PADDING, self.height - rt.height - PADDING)
        if self.snap_enabled:
            try:
                rt.snap_to_grid()
            except:
                pass
        rt.bring_to_front()
        return rt

    def equals_action(self, eq_tile):
        if eq_tile is None or eq_tile.superview is None:
            return False
        if getattr(eq_tile, 'group_id', None):
            # Keep "=" out of groups for sanity
            return False

        adj = self.get_adjacent_tiles_4way(eq_tile)
        neighbors = [t for t in (adj.get('left'), adj.get('top'), adj.get('right'), adj.get('bottom')) if t and t.superview is not None]
        neighbors = [t for t in neighbors if getattr(t, 'group_id', None) is None]

        if not neighbors:
            return False

        # If exactly one neighbor and it's numeric-like -> COPY
        if len(neighbors) == 1 and self._is_numeric_like(neighbors[0]) and getattr(neighbors[0], 'kind', '') != 'num_op':
            spot = self._find_spawn_spot_near_equals(eq_tile)
            if not spot:
                return False
            self.save_state()
            nt = self._clone_tile_like(neighbors[0])
            self.add_subview(nt)
            self.tiles.append(nt)
            nt.x, nt.y = spot
            if self.snap_enabled:
                try:
                    nt.snap_to_grid()
                except:
                    pass
            nt.bring_to_front()
            return True

        # Prefer: compound evaluation if we can find (num_op + number)
        comp = None
        other = None
        for t in neighbors:
            if getattr(t, 'kind', '') == 'num_op':
                comp = t
                break
        if comp is not None:
            for t in neighbors:
                if t is comp:
                    continue
                if getattr(t, 'kind', '') in ('number', 'generic', 'result', 'fraction'):
                    if getattr(t, 'kind', '') == 'fraction':
                        if getattr(t, 'numer', None) is None or getattr(t, 'denom', None) is None:
                            continue
                    other = t
                    break
            if other is not None:
                spot = self._find_spawn_spot_near_equals(eq_tile)
                if not spot:
                    return False

                comp_num = getattr(comp, 'expr_str', '').strip()
                comp_op = getattr(comp, 'pending_op', '').strip()
                other_num = getattr(other, 'expr_str', getattr(other, 'label_text', '')).strip()
                if not comp_num or not comp_op or not other_num:
                    return False

                try:
                    a = eval(comp_num.replace('^', '**'), {"__builtins__": {}}, {})
                    b = eval(other_num.replace('^', '**'), {"__builtins__": {}}, {})
                    a = float(a) if isinstance(a, (int, float)) else None
                    b = float(b) if isinstance(b, (int, float)) else None
                    if a is None or b is None:
                        return False
                except:
                    return False

                # Compute without deleting the operands (tool-style)
                if comp_op == '+':
                    result = a + b
                elif comp_op == '-':
                    result = a - b
                elif comp_op == '*':
                    result = a * b
                elif comp_op == '/':
                    result = a / b if b != 0 else a
                elif comp_op == '^':
                    result = a ** b
                else:
                    return False

                if isinstance(result, float) and abs(result - round(result)) < 1e-12:
                    result_text = str(int(round(result)))
                elif isinstance(result, float):
                    result_text = '{:.10g}'.format(result)
                else:
                    result_text = str(result)

                self.save_state()
                self._spawn_result_tile(result_text, spot[0], spot[1])
                return True

        # Fallback: operator tile nearby -> evaluate operator with its own adjacent operands (like Combine) but tool-style
        op = None
        for t in neighbors:
            if getattr(t, 'kind', '') == 'op':
                op = t
                break
        if op is not None:
            op_adj = self.get_adjacent_tiles_4way(op)
            ordered = []
            for d in ['left', 'top', 'right', 'bottom']:
                t = op_adj.get(d)
                if t and t is not eq_tile and getattr(t, 'group_id', None) is None:
                    k = getattr(t, 'kind', '')
                    if k == 'fraction' and (getattr(t, 'numer', None) is None or getattr(t, 'denom', None) is None):
                        continue
                    if k in ('number', 'generic', 'result', 'fraction'):
                        ordered.append(t)

            if len(ordered) >= 2:
                op_str = getattr(op, 'expr_str', getattr(op, 'label_text', '')).strip()
                parts = []
                for t in ordered[:2]:
                    s = getattr(t, 'expr_str', getattr(t, 'label_text', '')).strip()
                    if s:
                        parts.append(s)
                if len(parts) < 2 or not op_str:
                    return False

                expr = f'{parts[0]} {op_str} {parts[1]}'
                _, result_text = self.evaluate_expression(expr)
                if not result_text:
                    return False

                spot = self._find_spawn_spot_near_equals(eq_tile)
                if not spot:
                    return False

                self.save_state()
                self._spawn_result_tile(result_text, spot[0], spot[1])
                return True

        return False

    # ----------------------------------------------------------
    # Finalize drop
    # ----------------------------------------------------------









    def finalize_drop(self, tile):
        if tile is None or tile.superview is None:
            return

        if getattr(tile, 'kind', '') == 'factor':
            try:
                self.factorize_tile(tile)
            except Exception as e:
                print('finalize_drop factor error:', e)
            return

        if getattr(tile, 'kind', '') in ('split', 'supersplit'):
            try:
                self.try_split_merge(tile)
            except Exception as e:
                print('finalize_drop split error:', e)
            return

        if getattr(tile, 'kind', '') == 'equals':
            try:
                self.apply_equals(tile)
            except Exception as e:
                print('finalize_drop equals error:', e)
            return

        if self.snap_enabled and tile.superview is not None:
            try:
                tile.snap_to_grid()
            except:
                pass

        if tile.superview is not None:
            try:
                if self.try_fraction_merge(tile):
                    return
            except Exception as e:
                print('finalize_drop fraction error:', e)

        if tile.superview is not None:
            try:
                if self.try_compound_merge(tile):
                    return
            except Exception as e:
                print('finalize_drop compound error:', e)

        if tile.superview is not None:
            try:
                if self.try_decimal_merge(tile):
                    return
            except Exception as e:
                print('finalize_drop decimal error:', e)

        if tile.superview is not None:
            try:
                if self.try_negate_merge(tile):
                    return
            except Exception as e:
                print('finalize_drop negate error:', e)

        if tile.superview is not None:
            try:
                if self.try_expr_merge(tile):
                    return
            except Exception as e:
                print('finalize_drop expr error:', e)

        if tile.superview is not None:
            try:
                if self.try_subst_merge(tile):
                    return
            except Exception as e:
                print('finalize_drop subst error:', e)

        if tile.superview is not None:
            try:
                self.try_overlay_merge(tile)
            except Exception as e:
                print('finalize_drop overlay error:', e)

    def apply_equals(self, eq_tile):
        """
        '=' behaviour:
        1) If touching grouped tile -> copy that group (never evaluate)
        2) Solve equation if expr tile(s) present as 4-way neighbors
        3) Try evaluate a left-to-right chain next to '='
        4) Copy single 4-way neighbor (excluding expr tiles)
        '=' tile stays.
        """
        if eq_tile is None or eq_tile.superview is None:
            return False

        if self.snap_enabled:
            try:
                eq_tile.snap_to_grid()
            except:
                pass

        # 1) Group copy override (4-way only)
        g_hit = self._equals_touching_group_tile(eq_tile)
        if g_hit is not None:
            self.save_state()
            gid = getattr(g_hit, 'group_id', None)
            group = [t for t in self.tiles if getattr(t, 'group_id', None) == gid and t.superview is not None]
            if not group:
                return False

            for (sx, sy) in self._equals_slot_centers(eq_tile):
                group_sorted = sorted(group, key=lambda t: (t.y, t.x))
                ref = group_sorted[0]
                dx = sx - ref.x
                dy = sy - ref.y

                ok = True
                for t in group:
                    nx = t.x + dx
                    ny = t.y + dy
                    if nx < PADDING or ny < PADDING or nx + t.width > self.width - PADDING or ny + t.height > self.height - PADDING:
                        ok = False
                        break
                if not ok:
                    continue

                for t in group:
                    if not self._slot_is_free(t.x + dx, t.y + dy, t.width, t.height, ignore_tile=eq_tile):
                        ok = False
                        break
                if not ok:
                    continue

                new_gid = str(uuid.uuid4())
                for src in group:
                    nt = self._clone_tile_like(src)
                    self.add_subview(nt)
                    self.tiles.append(nt)
                    nt.x = src.x + dx
                    nt.y = src.y + dy
                    nt.group_id = new_gid
                    try:
                        nt.set_grouped(True)
                    except:
                        pass
                    if self.snap_enabled:
                        try:
                            nt.snap_to_grid()
                        except:
                            pass
                return True

            self.duplicate_tile_or_group(g_hit)
            return True

        # 2) Solve equation if expr tile(s) found in 4-way neighbors
        adj = self.get_adjacent_tiles_4way(eq_tile)
        neighbors_4way = {}
        for d in ['left', 'right', 'top', 'bottom']:
            t = adj.get(d)
            if t and t.superview is not None and getattr(t, 'group_id', None) is None:
                neighbors_4way[d] = t

        expr_tiles = []
        value_tiles = []
        for d, t in neighbors_4way.items():
            k = getattr(t, 'kind', '')
            if k == 'expr':
                expr_tiles.append((d, t))
            elif k in ('number', 'generic', 'result', 'fraction', 'num_op'):
                value_tiles.append((d, t))

        if expr_tiles:
            import sympy

            if len(expr_tiles) == 1 and value_tiles:
                e_tile = expr_tiles[0][1]
                v_tile = value_tiles[0][1]
                lhs = self._sympy_parse(getattr(e_tile, 'expr_str', ''))
                rhs = self._sympy_parse(getattr(v_tile, 'expr_str', getattr(v_tile, 'label_text', '')))
                if lhs is not None and rhs is not None:
                    try:
                        solutions = sympy.solve(lhs - rhs)
                    except:
                        solutions = None
                    if solutions:
                        self.save_state()
                        slots = self._equals_slot_centers(eq_tile)
                        used_slots = set()
                        for sol in solutions:
                            for i, (sx, sy) in enumerate(slots):
                                if i in used_slots:
                                    continue
                                h = TILE_SIZE
                                if hasattr(sol, 'free_symbols') and sol.free_symbols:
                                    pass
                                elif hasattr(sol, 'is_rational') and sol.is_rational and sol.q != 1:
                                    h = TILE_SIZE + GRID_SIZE
                                if self._slot_is_free(sx, sy, TILE_SIZE, h, ignore_tile=eq_tile):
                                    self._spawn_eval_result(sol, sx, sy)
                                    used_slots.add(i)
                                    break
                            else:
                                self._spawn_eval_result(sol, eq_tile.x, eq_tile.y + GRID_SIZE)
                        return True

            elif len(expr_tiles) >= 2:
                lhs = self._sympy_parse(getattr(expr_tiles[0][1], 'expr_str', ''))
                rhs = self._sympy_parse(getattr(expr_tiles[1][1], 'expr_str', ''))
                if lhs is not None and rhs is not None:
                    try:
                        solutions = sympy.solve(lhs - rhs)
                    except:
                        solutions = None
                    if solutions:
                        self.save_state()
                        slots = self._equals_slot_centers(eq_tile)
                        used_slots = set()
                        for sol in solutions:
                            for i, (sx, sy) in enumerate(slots):
                                if i in used_slots:
                                    continue
                                h = TILE_SIZE
                                if hasattr(sol, 'free_symbols') and sol.free_symbols:
                                    pass
                                elif hasattr(sol, 'is_rational') and sol.is_rational and sol.q != 1:
                                    h = TILE_SIZE + GRID_SIZE
                                if self._slot_is_free(sx, sy, TILE_SIZE, h, ignore_tile=eq_tile):
                                    self._spawn_eval_result(sol, sx, sy)
                                    used_slots.add(i)
                                    break
                            else:
                                self._spawn_eval_result(sol, eq_tile.x, eq_tile.y + GRID_SIZE)
                        return True

            elif len(expr_tiles) == 1 and not value_tiles:
                pass

        # 3) Try calculation chain (fraction-aware)
        chain = self._equals_collect_chain_lr(eq_tile)
        expr = self._equals_build_expr_from_chain(chain)
        if expr:
            val = self._eval_expr_smart(expr)
            if val is not None:
                from fractions import Fraction
                import sympy as _sp
                is_frac = False
                if isinstance(val, Fraction) and val.denominator != 1:
                    is_frac = True
                elif isinstance(val, _sp.Rational) and val.q != 1:
                    is_frac = True
                elif hasattr(val, 'free_symbols') and val.free_symbols:
                    pass
                slot_h = (TILE_SIZE + GRID_SIZE) if is_frac else TILE_SIZE
                self.save_state()
                for (sx, sy) in self._equals_slot_centers(eq_tile):
                    if self._slot_is_free(sx, sy, TILE_SIZE, slot_h, ignore_tile=eq_tile):
                        self._spawn_eval_result(val, sx, sy)
                        return True
                self._spawn_eval_result(val, eq_tile.x + GRID_SIZE, eq_tile.y)
                return True

        # 4) Copy single 4-way neighbor (excluding expr and grouped tiles)
        target = None
        for d in ['left', 'right', 'top', 'bottom']:
            t = neighbors_4way.get(d)
            if t and getattr(t, 'kind', '') != 'expr':
                target = t
                break

        if target is None:
            return False

        self.save_state()
        for (sx, sy) in self._equals_slot_centers(eq_tile):
            if self._slot_is_free(sx, sy, TILE_SIZE, TILE_SIZE, ignore_tile=eq_tile):
                self._spawn_copy_tile(target, sx, sy)
                return True

        self._spawn_copy_tile(target, eq_tile.x + GRID_SIZE, eq_tile.y)
        return True

    def _equals_build_expr_from_chain(self, chain):
        """
        Convert tiles -> expression string.
        Supports number, generic, result, fraction, expr, op, and num_op tiles.
        """
        if not chain:
            return None

        tokens = []

        for t in chain:
            k = getattr(t, 'kind', '')
            if k == 'num_op':
                n = str(getattr(t, 'expr_str', '') or '').strip()
                op = str(getattr(t, 'pending_op', '') or '').strip()
                if not n or not op:
                    return None
                tokens.append(f'({n})')
                tokens.append(op)
                continue

            if k == 'op':
                op = str(getattr(t, 'expr_str', getattr(t, 'label_text', '')) or '').strip()
                if op not in ('+', '-', '*', '/', '^'):
                    return None
                tokens.append(op)
                continue

            if k == 'expr':
                s = str(getattr(t, 'expr_str', '') or '').strip()
                if not s:
                    return None
                tokens.append(f'({s})')
                continue

            if k in ('number', 'generic', 'result', 'fraction'):
                s = str(getattr(t, 'expr_str', getattr(t, 'label_text', '')) or '').strip()
                if not s:
                    return None
                tokens.append(s)
                continue

            return None

        has_op = any(tok in ('+', '-', '*', '/', '^') for tok in tokens)
        if not has_op:
            return None

        if tokens[0] in ('+', '-', '*', '/', '^') or tokens[-1] in ('+', '-', '*', '/', '^'):
            return None

        return ' '.join(tokens)

    def _equals_collect_chain_lr(self, eq_tile):
        """
        Find a contiguous chain of tiles next to '=' in the same row (prefer),
        and return them in left-to-right order.

        We look for a neighbor left/right of '=' and then walk outward by GRID_SIZE.
        """
        step = GRID_SIZE
        tol = step * 0.55

        # Helper: find tile whose center is near a target center
        def find_at_center(cx, cy):
            for t in self.tiles:
                if t is None or t.superview is None or t is eq_tile:
                    continue
                tcx, tcy = self.tile_center(t)
                if abs(tcx - cx) <= tol and abs(tcy - cy) <= tol:
                    return t
            return None

        eq_cx, eq_cy = self.tile_center(eq_tile)

        # Try to anchor on immediate left or right tile
        left = find_at_center(eq_cx - step, eq_cy)
        right = find_at_center(eq_cx + step, eq_cy)

        anchor = left or right
        if anchor is None:
            return []

        # Walk left from anchor
        chain = [anchor]
        cur = anchor
        while True:
            ccx, ccy = self.tile_center(cur)
            nxt = find_at_center(ccx - step, ccy)
            if nxt is None:
                break
            chain.insert(0, nxt)
            cur = nxt

        # Walk right from anchor (start from original anchor)
        cur = anchor
        while True:
            ccx, ccy = self.tile_center(cur)
            nxt = find_at_center(ccx + step, ccy)
            if nxt is None:
                break
            chain.append(nxt)
            cur = nxt

        # Filter out '=' tiles if any and anything weird
        cleaned = []
        for t in chain:
            if getattr(t, 'kind', '') == 'equals':
                continue
            cleaned.append(t)

        return cleaned


    def _equals_touching_group_tile(self, eq_tile):
        """Check 4-way neighbors for grouped tiles."""
        adj = self.get_adjacent_tiles_4way(eq_tile)
        for d in ['left', 'right', 'top', 'bottom']:
            t = adj.get(d)
            if t and getattr(t, 'group_id', None):
                return t
        return None

    def _spawn_copy_tile(self, src_tile, x, y):
        nt = self._clone_tile_like(src_tile)
        self.add_subview(nt)
        self.tiles.append(nt)

        nt.x = clamp(x, PADDING, self.width - nt.width - PADDING)
        nt.y = clamp(y, PADDING, self.height - nt.height - PADDING)

        if self.snap_enabled:
            try:
                nt.snap_to_grid()
            except:
                pass
        nt.bring_to_front()
        return nt

    def _spawn_result_tile(self, text, x, y):
        rt = Tile(self)
        self.add_subview(rt)
        self.tiles.append(rt)
        rt.kind = 'result'
        rt.expr_str = str(text)
        rt.set_label(str(text))
        rt.set_tile_color(RESULT_COLOR)
        try:
            rt.label.text_color = RESULT_TEXT_COLOR
        except:
            pass

        rt.x = clamp(x, PADDING, self.width - rt.width - PADDING)
        rt.y = clamp(y, PADDING, self.height - rt.height - PADDING)

        if self.snap_enabled:
            try:
                rt.snap_to_grid()
            except:
                pass
        rt.bring_to_front()
        return rt

    def _slot_is_free(self, x, y, w=TILE_SIZE, h=TILE_SIZE, ignore_tile=None):
        # Simple AABB overlap check with a small tolerance
        tol = 0.5
        rx1, ry1 = x + tol, y + tol
        rx2, ry2 = x + w - tol, y + h - tol

        for t in self.tiles:
            if t is None or t.superview is None:
                continue
            if ignore_tile is not None and t is ignore_tile:
                continue

            tx1, ty1 = t.x, t.y
            tx2, ty2 = t.x + t.width, t.y + t.height

            if not (rx2 <= tx1 or tx2 <= rx1 or ry2 <= ty1 or ty2 <= ry1):
                return False
        return True

    def _equals_slot_centers(self, eq_tile):
        # Order: right, left, down, up (as requested)
        step = GRID_SIZE
        ex, ey = eq_tile.x, eq_tile.y
        ew, eh = eq_tile.width, eq_tile.height

        # Use eq tile's top-left as grid anchor; keep it consistent with your grid snapping
        # Candidate top-left positions:
        return [
            (ex + step, ey),        # right
            (ex - step, ey),        # left
            (ex, ey + step),        # down
            (ex, ey - step),        # up
        ]

    # ----------------------------------------------------------
    # Expression evaluation helper
    # ----------------------------------------------------------

    def evaluate_expression(self, expr):
        expr = (expr or '').strip()
        if not expr:
            return None, None
        expr = expr.replace('^', '**')
        try:
            val = eval(expr, {"__builtins__": {}}, {})
        except:
            return None, None
        if isinstance(val, bool):
            s = '1' if val else '0'
        elif isinstance(val, int):
            s = str(val)
        elif isinstance(val, float):
            s = str(int(round(val))) if abs(val - round(val)) < 1e-12 else '{:.10g}'.format(val)
        else:
            s = str(val)
        return val, s

    def can_toggle_simple_decimal(self, tile):
        if tile is None or tile.superview is None:
            return False
        if getattr(tile, 'group_id', None):
            return False

        k = getattr(tile, 'kind', '')
        if k == 'fraction':
            numer = getattr(tile, 'numer', None)
            denom = getattr(tile, 'denom', None)
            return (numer is not None and denom is not None and int(denom) != 0)

        if k in ('number', 'generic', 'result'):
            s = str(getattr(tile, 'expr_str', getattr(tile, 'label_text', '')) or '').strip()
            if not s:
                return False
            import re
            return bool(re.match(r'^-?\d+(\.\d+)?$', s))

        return False

    def _tile_copy_text(self, t):
        k = getattr(t, 'kind', '')
        if k == 'fraction':
            n = getattr(t, 'numer', None)
            d = getattr(t, 'denom', None)
            if n is not None and d is not None:
                return f'{int(n)}/{int(d)}'
            if n is not None:
                return f'{int(n)}/_'
            return '_/_'
        s = str(getattr(t, 'expr_str', getattr(t, 'label_text', '')) or '').strip()
        return s

    def copy_tile_or_group(self, tile):
        if tile is None or tile.superview is None:
            return

        import clipboard

        gid = getattr(tile, 'group_id', None)
        if gid:
            group = [t for t in self.tiles if getattr(t, 'group_id', None) == gid and t.superview is not None]
            group.sort(key=lambda t: (round(t.y / GRID_SIZE, 3), round(t.x / GRID_SIZE, 3), t.y, t.x))

            parts = []
            for t in group:
                txt = self._tile_copy_text(t)
                if txt:
                    parts.append(txt)

            text = ' '.join(parts).strip()
            if not text:
                text = ''
            clipboard.set(text)
            return

        text = self._tile_copy_text(tile)
        clipboard.set(text or '')

    def _can_place_group_with_offset(self, group_tiles, dy):
        for t in group_tiles:
            nx = t.x
            ny = t.y + dy
            nx = clamp(nx, PADDING, self.width - t.width - PADDING)
            ny = clamp(ny, PADDING, self.height - t.height - PADDING)
            if abs(nx - t.x) > 0.01 or abs(ny - (t.y + dy)) > 0.01:
                return False
        return True

    def duplicate_tile_or_group(self, tile):
        if tile is None or tile.superview is None:
            return

        self.save_state()

        gid = getattr(tile, 'group_id', None)

        if gid:
            group = [t for t in self.tiles if getattr(t, 'group_id', None) == gid and t.superview is not None]
            if not group:
                return

            group.sort(key=lambda t: (t.y, t.x))

            dy_down = GRID_SIZE
            dy_up = -GRID_SIZE

            if self._can_place_group_with_offset(group, dy_down):
                dy = dy_down
            elif self._can_place_group_with_offset(group, dy_up):
                dy = dy_up
            else:
                dy = dy_down

            new_gid = str(uuid.uuid4())

            for src in group:
                nt = self._clone_tile_like(src)
                self.add_subview(nt)
                self.tiles.append(nt)

                nt.x = clamp(src.x, PADDING, self.width - nt.width - PADDING)
                nt.y = clamp(src.y + dy, PADDING, self.height - nt.height - PADDING)

                nt.group_id = new_gid
                try:
                    nt.set_grouped(True)
                except:
                    pass

                if self.snap_enabled:
                    try:
                        nt.snap_to_grid()
                    except:
                        pass

            return

        dy_down = GRID_SIZE
        dy_up = -GRID_SIZE

        def fits_at(dy):
            ny = tile.y + dy
            return (ny >= PADDING and (ny + tile.height) <= (self.height - PADDING))

        dy = dy_down if fits_at(dy_down) else dy_up

        nt = self._clone_tile_like(tile)
        self.add_subview(nt)
        self.tiles.append(nt)

        nt.x = clamp(tile.x, PADDING, self.width - nt.width - PADDING)
        nt.y = clamp(tile.y + dy, PADDING, self.height - nt.height - PADDING)

        if self.snap_enabled:
            try:
                nt.snap_to_grid()
            except:
                pass
        nt.bring_to_front()

    def _gcd_int(self, a, b):
        a = abs(int(a)); b = abs(int(b))
        while b:
            a, b = b, a % b
        return a or 1


    def _parse_decimal_to_fraction(self, s):
        from fractions import Fraction
        s = (s or '').strip()
        if not s:
            return None
        try:
            f = Fraction(s).limit_denominator(10000)
        except (ValueError, ZeroDivisionError):
            try:
                f = Fraction(float(s)).limit_denominator(10000)
            except:
                return None
        if f.denominator == 0:
            return None
        return f.numerator, f.denominator

    def _format_decimal(self, val):
        try:
            f = float(val)
        except:
            return None
        if abs(f - round(f)) < 1e-12:
            return str(int(round(f)))
        return '{:.12g}'.format(f)

    def toggle_simple_decimal(self, tile):
        if not self.can_toggle_simple_decimal(tile):
            return

        self.save_state()

        k = getattr(tile, 'kind', '')
        x, y = tile.x, tile.y

        if k == 'fraction':
            numer = int(getattr(tile, 'numer', 0))
            denom = int(getattr(tile, 'denom', 1))
            if denom == 0:
                print('S↔D: Denominator cannot be 0')
                return

            val = numer / denom
            s = self._format_decimal(val)
            if not s:
                return

            if tile in self.tiles:
                self.tiles.remove(tile)
            try:
                self.remove_subview(tile)
            except:
                pass

            nt = Tile(self)
            self.add_subview(nt)
            self.tiles.append(nt)
            nt.kind = 'number'
            nt.expr_str = s
            nt.set_label(s)
            nt.set_tile_color(TILE_COLOR)
            nt.x = clamp(x, PADDING, self.width - nt.width - PADDING)
            nt.y = clamp(y, PADDING, self.height - nt.height - PADDING)
            if self.snap_enabled:
                try:
                    nt.snap_to_grid()
                except:
                    pass
            nt.bring_to_front()
            return

        if k in ('number', 'generic', 'result'):
            s = str(getattr(tile, 'expr_str', getattr(tile, 'label_text', '')) or '').strip()
            frac = self._parse_decimal_to_fraction(s)
            if not frac:
                print('S↔D: Not a finite decimal/integer')
                return
            numer, denom = frac
            if denom == 0:
                print('S↔D: Denominator cannot be 0')
                return

            if tile in self.tiles:
                self.tiles.remove(tile)
            try:
                self.remove_subview(tile)
            except:
                pass

            ft = FractionTile(self)
            self.add_subview(ft)
            self.tiles.append(ft)
            ft.set_tile_color(TILE_COLOR)
            ft.set_fraction_numer(int(numer))
            ft.set_fraction_denom(int(denom))
            ft.x = clamp(x, PADDING, self.width - ft.width - PADDING)
            ft.y = clamp(y, PADDING, self.height - ft.height - PADDING)
            if self.snap_enabled:
                try:
                    ft.snap_to_grid()
                except:
                    pass
            ft.bring_to_front()
            return

    # ----------------------------------------------------------
    # Clear / misc
    # ----------------------------------------------------------

    def clear_all_tiles(self):
        if self.tiles:
            self.save_state()
        self.dismiss_editor()
        self.dismiss_trash_menu()
        for t in list(self.tiles):
            try:
                self.tiles.remove(t)
            except:
                pass
            try:
                self.remove_subview(t)
            except:
                pass

    def duplicate_tile(self, tile):
        if tile is None or tile.superview is None:
            return None
        t = Tile(self)
        self.add_subview(t)
        self.tiles.append(t)
        t.kind = getattr(tile, 'kind', 'generic')
        t.expr_str = getattr(tile, 'expr_str', '')
        t.pending_op = getattr(tile, 'pending_op', None)
        t.set_label(getattr(tile, 'label_text', ''))
        t.set_tile_color(getattr(tile, 'tile_color', TILE_COLOR))

        dy = GRID_SIZE if self.snap_enabled else (TILE_SIZE + 10)
        t.x = clamp(tile.x, PADDING, self.width - t.width - PADDING)
        y_below = clamp(tile.y + dy, PADDING, self.height - t.height - PADDING)
        y_above = clamp(tile.y - dy, PADDING, self.height - t.height - PADDING)
        t.y = y_below if abs(y_below - tile.y) >= 1 else y_above
        t.bring_to_front()
        if self.snap_enabled:
            try:
                t.snap_to_grid()
            except:
                pass
        return t


# ==========================================================
    # TILECALC — Equals & Decimal Helpers (namespaced)
    # ==========================================================

    def tilecalc_spawn_near(self, x, y, w, h):
        """Find a free grid-aligned spot near (x,y) for a tile of size (w,h)."""
        for cx, cy in self._aligned_positions_around(x, y, max_r=8):
            nx = clamp(cx, PADDING, self.width - w - PADDING)
            ny = clamp(cy, PADDING, self.height - h - PADDING)
            rect = (nx, ny, w, h)
            hit = False
            for t in self.tiles:
                if t.superview is None:
                    continue
                if not (nx + w <= t.x or t.x + t.width <= nx or
                        ny + h <= t.y or t.y + t.height <= ny):
                    hit = True
                    break
            if not hit:
                return nx, ny
        return clamp(x, PADDING, self.width - w - PADDING), clamp(y, PADDING, self.height - h - PADDING)

    def tilecalc_duplicate_group_at(self, group_tiles, x, y):
        """Duplicate a grouped set near (x,y) preserving offsets."""
        if not group_tiles:
            return
        self.save_state()
        base = group_tiles[0]
        bx, by = base.x, base.y
        new_gid = str(uuid.uuid4())

        for src in group_tiles:
            nt = self._clone_tile_like(src)
            self.add_subview(nt)
            self.tiles.append(nt)

            dx = src.x - bx
            dy = src.y - by
            nx, ny = self.tilecalc_spawn_near(x + dx, y + dy, nt.width, nt.height)
            nt.x, nt.y = nx, ny
            nt.group_id = new_gid
            try:
                nt.set_grouped(True)
            except:
                pass
            if self.snap_enabled:
                try: nt.snap_to_grid()
                except: pass

    def tilecalc_copy_single_at(self, src, x, y):
        self.save_state()
        nt = self._clone_tile_like(src)
        self.add_subview(nt)
        self.tiles.append(nt)
        nx, ny = self.tilecalc_spawn_near(x, y, nt.width, nt.height)
        nt.x, nt.y = nx, ny
        if self.snap_enabled:
            try: nt.snap_to_grid()
            except: pass

    def tilecalc_equals_action(self, eq_tile):
        """Implements = behavior: group copy > calc > single copy."""
        adj = self.get_adjacent_tiles_4way(eq_tile)
        neighbors = [t for t in adj.values() if t and t.superview is not None]
        if not neighbors:
            return False

        # --- Priority 1: grouped copy ---
        for t in neighbors:
            gid = getattr(t, 'group_id', None)
            if gid:
                group = [g for g in self.tiles if getattr(g, 'group_id', None) == gid]
                self.tilecalc_duplicate_group_at(group, eq_tile.x, eq_tile.y)
                self.delete_tile(eq_tile)
                return True

        # --- Priority 2: try compound evaluation ---
        for t in neighbors:
            if getattr(t, 'kind', '') == 'num_op':
                other = [n for n in neighbors if n is not t]
                if other:
                    if self._evaluate_compound(t, other[0]):
                        self.delete_tile(eq_tile)
                        return True

        # --- Priority 3: operator combine ---
        for t in neighbors:
            if getattr(t, 'kind', '') == 'op':
                self.combine_operation(t)
                self.delete_tile(eq_tile)
                return True

        # --- Priority 4: single copy fallback ---
        self.tilecalc_copy_single_at(neighbors[0], eq_tile.x, eq_tile.y)
        self.delete_tile(eq_tile)
        return True

    def tilecalc_decimal_merge(self, dropped):
        """Handle decimal point merges like 4 + . → 4. and 4. + 3 → 4.3"""
        if getattr(dropped, 'expr_str', '') != '.':
            return False

        best, _ = self._best_overlap(dropped)
        if not best:
            return False

        s = str(getattr(best, 'expr_str', '') or '')
        if not s:
            return False

        if '.' not in s and s.lstrip('-').isdigit():
            self.save_state()
            best.expr_str = s + '.'
            best.set_label(best.expr_str)
            self.delete_tile(dropped)
            return True

        if '.' in s and s.replace('.', '').lstrip('-').isdigit():
            # decimal tile + digit tile case handled by overlay merge later
            return False

        return False
