import ui
import threading
from tile import Tile


DEBUG_TOUCH = False  # flip True if you want verbose state logs



class PopPreviewView(ui.View):
    """
    Ghost tile preview for pop gesture.
    On init: only left ghost (what pops off) is shown.
    When finger enters left ghost: remain ghost fades in over original tile,
    original tile fades to dim.
    When finger retreats: remain ghost gone, original tile restored.
    """
    GHOST_ALPHA  = 0.55
    DIM_ALPHA    = 0.20
    SCALE        = 0.85

    def __init__(self, tile, board):
        super().__init__(frame=(0, 0, 1, 1))
        self.touch_enabled = False
        self._tile         = tile
        self._board        = board
        self._left_ghost   = None
        self._remain_ghost = None
        self._remain_shown = False

        try:
            from tile_menu import _compute_pop_specs
            self._left_spec, self._remain_spec = _compute_pop_specs(tile)
        except Exception as e:
            print(f"[POP_PREVIEW_ERROR] {e}")
            self._left_spec = self._remain_spec = None
            return

        if self._left_spec:
            g = board.grid
            cx, cy = tile.center
            self._left_ghost = self._make_ghost(self._left_spec, cx - g, cy, g)

    def _make_ghost(self, spec, gx, gy, grid):
        from tile import Tile as _Tile
        size = int(grid * self.SCALE)
        try:
            t = _Tile(
                text=spec['text'], kind=spec['kind'], color=spec['color'],
                w_cells=1, h_cells=1, cell_size=size, gutter=2,
            )
            t.touch_enabled = False
            t.alpha = 0.0
            t.center = (gx, gy)
            self._board.add_subview(t)
            ui.animate(lambda: setattr(t, 'alpha', self.GHOST_ALPHA), duration=0.18)
            return t
        except Exception as e:
            print(f"[POP_GHOST_ERROR] {e}")
            return None

    def is_over_left_ghost(self, board_point):
        """Return True if board_point is within the left ghost tile bounds."""
        g = self._left_ghost
        if g is None:
            return False
        try:
            fx, fy, fw, fh = g.frame
            # Expand hit area slightly
            pad = 8
            return (fx - pad <= board_point[0] <= fx + fw + pad and
                    fy - pad <= board_point[1] <= fy + fh + pad)
        except Exception:
            return False

    def show_remain(self):
        if self._remain_shown or self._remain_spec is None:
            return
        self._remain_shown = True
        # Dim original tile
        try:
            ui.animate(lambda: setattr(self._tile, 'alpha', self.DIM_ALPHA), duration=0.15)
        except Exception:
            pass
        # Spawn remain ghost over original tile position
        cx, cy = self._tile.center
        g = self._board.grid
        self._remain_ghost = self._make_ghost(self._remain_spec, cx, cy, g)

    def hide_remain(self):
        if not self._remain_shown:
            return
        self._remain_shown = False
        # Restore original tile
        try:
            ui.animate(lambda: setattr(self._tile, 'alpha', 1.0), duration=0.15)
        except Exception:
            pass
        # Remove remain ghost
        if self._remain_ghost is not None:
            rg = self._remain_ghost
            self._remain_ghost = None
            def _remove():
                try:
                    if rg.superview:
                        rg.superview.remove_subview(rg)
                except Exception:
                    pass
            ui.animate(lambda: setattr(rg, 'alpha', 0.0),
                       duration=0.12, completion=_remove)

    def dismiss(self):
        # Restore tile alpha unconditionally
        try:
            self._tile.alpha = 1.0
        except Exception:
            pass
        for ghost in [self._left_ghost, self._remain_ghost]:
            if ghost is None:
                continue
            try:
                gg = ghost
                def _remove(v=gg):
                    try:
                        if v.superview:
                            v.superview.remove_subview(v)
                    except Exception:
                        pass
                ui.animate(lambda v=gg: setattr(v, 'alpha', 0.0),
                           duration=0.10, completion=lambda v=gg: _remove(v))
            except Exception:
                pass
        self._left_ghost   = None
        self._remain_ghost = None
        self._remain_shown = False
        try:
            if self.superview:
                self.superview.remove_subview(self)
        except Exception:
            pass

class MergePreviewOverlay(ui.View):
    """
    A ghost tile that spans two merging tiles, showing the pending operation.
    Horizontal merges: 2×1 wide. Vertical merges: 1×2 tall.
    Never mutates the underlying tile labels.
    """

    def __init__(self, text, frame, orientation='horizontal'):
        super().__init__(frame=frame)
        self.background_color = (0.15, 0.15, 0.18, 0.82)
        self.corner_radius    = 14
        self.border_width     = 1.5
        self.border_color     = (1, 1, 1, 0.18)
        self.alpha            = 0.0

        if orientation == 'vertical':
            font_size = 13
        else:
            font_size = 15

        lbl = ui.Label(frame=(0, 0, frame[2], frame[3]))
        lbl.text            = text
        lbl.font            = ('<System-Bold>', font_size)
        lbl.text_color      = (1, 1, 1, 0.92)
        lbl.alignment       = ui.ALIGN_CENTER
        lbl.number_of_lines = 0
        self.add_subview(lbl)
        self._lbl = lbl

    def update_text(self, text):
        self._lbl.text = text

    def show(self):
        ui.animate(lambda: setattr(self, 'alpha', 1.0), duration=0.12)

    def dismiss(self):
        ui.animate(lambda: setattr(self, 'alpha', 0.0), duration=0.1)

import ui
import threading
from tile import Tile

DEBUG_TOUCH = False  # flip True if you want verbose touch state logs


class TouchHandler:
    """
    Owns all touch interaction for the board.

    Modes:
      - 'idle'
      - 'tile_drag'
      - 'group_drag'
      - 'menu_drag'
      - 'lasso'
      - 'tap_pending'
    """

    def __init__(self, board):
        self.board = board

        self._mode = 'idle'
        self._group_dragging = False
        self._drag_tile = None

        self._lp_timer = None
        self._lp_start = None
        self._lp_tile = None
        self._lp_kind = None
        self._long_press_threshold = 0.35
        self._long_press_move_limit = 10

        self._menu_drag_mode = False
        self._active_actions_menu = None
        self._active_ops_menu = None
        self._active_scrubber = None
        self._active_variant_picker = None
        self._ops_dragging = False
        self._scrubber_eligible = False
        self._pop_eligible = False
        self._variant_eligible = False
        self._in_pop_zone = False
        self._menu_handles = []

        self._preview_tile = None
        self._preview_original = None
        self._preview_overlay = None

        self._braced_tile = None
        self._op_hint_label = None
        self._result_ghost = None

        self._pop_preview = None

        self._lasso = None
        try:
            from lasso_tool import LassoTool
            self._lasso = LassoTool(board)
            print("[LASSO] ready")
        except Exception as e:
            self._lasso = None
            print(f"[LASSO_INIT_ERROR] {e}")

    def _dbg(self, tag, p=None):
        if not DEBUG_TOUCH:
            return
        board = self.board
        group = getattr(board, 'lasso_selected_tiles', None) or []
        print(
            f"[TOUCH] {tag} mode={self._mode} menu_drag={self._menu_drag_mode} "
            f"lp={self._lp_kind} drag_tile={'YES' if board._drag_tile else 'NO'} "
            f"group={len(group)} p={p}"
        )

    # ------------------------------------------------------------------
    # Central cleanup
    # ------------------------------------------------------------------

    def _reset_to_neutral(self, reason=''):
        board = self.board
        self._cancel_long_press()
        self._dismiss_all_popups()
        self._clear_merge_preview()
        self._menu_drag_mode = False
        self._ops_dragging = False

        try:
            if board._drag_tile:
                board._drag_tile.set_dragging(False)
        except Exception:
            pass

        board._drag_tile = None
        board._drag_start_center = None
        self._drag_tile = None

        try:
            if hasattr(board, 'clear_typing_state'):
                board.clear_typing_state()
            else:
                board._keyboard_active_tile = None
                board._keyboard_frac_mode = False
                board._keyboard_frac_tile = None
                board._keyboard_denom_tile = None
        except Exception:
            pass

        try:
            if hasattr(board, 'select_tile'):
                board.select_tile(None)
        except Exception:
            pass

        self._clear_group_selection()
        self._mode = 'idle'
        self._group_dragging = False

        if reason:
            print(f"[NEUTRAL] {reason}")

    def _clear_group_selection(self):
        board = self.board
        sel = getattr(board, 'lasso_selected_tiles', None) or []
        if not sel:
            return

        for t in list(sel):
            try:
                t.set_selected(False)
            except Exception:
                pass

        try:
            board.lasso_selected_tiles = []
        except Exception:
            pass

        try:
            if hasattr(board, 'clear_lasso_selection'):
                board.clear_lasso_selection()
        except Exception:
            pass

        print("[LASSO] cleared selection")

    # ------------------------------------------------------------------
    # Long press
    # ------------------------------------------------------------------

    def _cancel_long_press(self):
        if self._lp_timer is not None:
            try:
                self._lp_timer.cancel()
            except Exception:
                pass
        self._lp_timer = None
        self._lp_start = None
        self._lp_tile = None
        self._lp_kind = None

    def _arm_long_press(self, kind, start_p, tile=None):
        self._cancel_long_press()
        self._lp_kind = kind
        self._lp_start = start_p
        self._lp_tile = tile

        def fire():
            if self._lp_timer is None:
                return
            self._lp_timer = None

            if self._lp_kind == 'tile_menu' and self._lp_tile is not None:
                t = self._lp_tile
                self._lp_kind = None
                self._lp_start = None
                self._lp_tile = None
                try:
                    print(f"[LONG_PRESS] tile_menu tile={t.tile_id[:6]}")
                except Exception:
                    print("[LONG_PRESS] tile_menu")
                self._show_menu(t)
                self._menu_drag_mode = True
                self._mode = 'menu_drag'
                return

            if self._lp_kind == 'lasso' and self._lasso is not None and self._lp_start is not None:
                start = self._lp_start
                self._lp_kind = None
                self._lp_start = None
                self._lp_tile = None
                try:
                    print("[LASSO] begin")
                    self._mode = 'lasso'
                    self._lasso.begin(start)
                except Exception as e:
                    print(f"[LASSO_BEGIN_ERROR] {e}")
                    self._mode = 'idle'
                return

        self._lp_timer = threading.Timer(self._long_press_threshold, fire)
        self._lp_timer.start()

    # ------------------------------------------------------------------
    # Popup dismiss
    # ------------------------------------------------------------------

    def _dismiss_all_popups(self):
        self._dismiss_pop_preview()

        if self._active_actions_menu:
            try:
                self._active_actions_menu.dismiss()
            except Exception:
                pass
            self._active_actions_menu = None

        if self._active_ops_menu:
            try:
                self._active_ops_menu.dismiss()
            except Exception:
                pass
            self._active_ops_menu = None

        if self._active_scrubber:
            try:
                self._active_scrubber.dismiss()
            except Exception:
                pass
            self._active_scrubber = None

        if self._active_variant_picker:
            try:
                self._active_variant_picker.dismiss()
            except Exception:
                pass
            self._active_variant_picker = None

        self._dismiss_menu_handles()

    # ------------------------------------------------------------------
    # Touch events
    # ------------------------------------------------------------------

    def touch_began(self, touch):
        board = self.board
        p = board._touch_point(touch, in_view=board)
        self._dbg("began", p)

        if self._mode == 'lasso':
            return

        self._dismiss_all_popups()
        self._menu_drag_mode = False
        self._ops_dragging = False

        hint = getattr(board, '_merge_hint_view', None)
        if hint is not None:
            try:
                hint.dismiss()
            except Exception:
                pass
            board._merge_hint_view = None

        t = board.tile_at_point(p)

        if t is not None:
            try:
                if hasattr(board, 'clear_typing_state'):
                    board.clear_typing_state()
                else:
                    board._keyboard_active_tile = None
                    board._keyboard_frac_mode = False
                    board._keyboard_frac_tile = None
                    board._keyboard_denom_tile = None
            except Exception:
                pass

            try:
                board.select_tile(t)
            except Exception:
                pass

            board._drag_tile = t
            try:
                board._drag_tile.set_dragging(True)
            except Exception:
                pass

            board._drag_start_center = getattr(t, 'center', (0.0, 0.0))
            self._drag_tile = t

            try:
                c = t.center
            except Exception:
                c = (0.0, 0.0)

            board._drag_last_center = c
            board._drag_prev_center = c

            try:
                cx, cy = t.center
            except Exception:
                cx, cy = c

            px, py = p
            board._drag_offset = (px - cx, py - cy)

            group = getattr(board, 'lasso_selected_tiles', None) or []
            self._group_dragging = bool(group and (t in group))
            self._mode = 'group_drag' if self._group_dragging else 'tile_drag'

            self._arm_long_press('tile_menu', start_p=p, tile=t)
            return

        group = getattr(board, 'lasso_selected_tiles', None) or []
        if group:
            self._clear_group_selection()
            try:
                board.select_tile(None)
            except Exception:
                pass
            self._mode = 'idle'
            return

        try:
            board.select_tile(None)
        except Exception:
            pass

        if self._lasso is None:
            self._mode = 'idle'
            return

        print("[LASSO_ARM] empty-board long press armed")
        self._mode = 'tap_pending'
        self._arm_long_press('lasso', start_p=p, tile=None)

    def touch_moved(self, touch):
        board = self.board
        p = board._touch_point(touch, in_view=board)
        self._dbg("moved", p)

        if self._mode == 'lasso' and self._lasso is not None:
            try:
                self._lasso.update(p)
            except Exception as e:
                print(f"[LASSO_UPDATE_ERROR] {e}")
            return

        if self._lp_timer is not None and self._lp_start is not None:
            dx = p[0] - self._lp_start[0]
            dy = p[1] - self._lp_start[1]
            if (dx * dx + dy * dy) ** 0.5 > self._long_press_move_limit:
                self._cancel_long_press()

        hint = getattr(board, '_merge_hint_view', None)
        if hint is not None:
            try:
                hint.dismiss()
            except Exception:
                pass
            board._merge_hint_view = None

        if self._mode == 'menu_drag' and self._menu_drag_mode:
            self._handle_menu_drag(p)
            return

        if self._mode not in ('tile_drag', 'group_drag'):
            return

        if board._drag_tile is None:
            return

        px, py = p
        offx, offy = board._drag_offset
        cx = px - offx
        cy = py - offy
        cx, cy = board._clamp_center(cx, cy, board._drag_tile)

        if self._mode == 'group_drag':
            group = getattr(board, 'lasso_selected_tiles', None) or []
            if group and (board._drag_tile in group):
                prev = getattr(board, '_drag_last_center', None)
                if prev is None:
                    prev = board._drag_tile.center
                dx = cx - prev[0]
                dy = cy - prev[1]

                board._drag_tile.center = (cx, cy)
                for t in group:
                    if t is None or t is board._drag_tile:
                        continue
                    try:
                        tcx, tcy = t.center
                        ncx, ncy = board._clamp_center(tcx + dx, tcy + dy, t)
                        t.center = (ncx, ncy)
                    except Exception:
                        pass

                board._drag_last_center = (cx, cy)
                return

            self._mode = 'tile_drag'

        board._drag_tile.center = (cx, cy)
        board._drag_last_center = (cx, cy)

        try:
            board._drag_tile.bring_to_front()
        except Exception:
            pass

        self._update_brace(board._drag_tile)

    def touch_ended(self, touch):
        board = self.board
        self._dbg("ended", None)

        if self._mode == 'lasso' and self._lasso is not None:
            try:
                self._lasso.end()
            except Exception as e:
                print(f"[LASSO_END_ERROR] {e}")
            self._mode = 'idle'
            self._cancel_long_press()
            return

        self._cancel_long_press()

        if self._mode == 'menu_drag' and self._menu_drag_mode:
            self._menu_drag_mode = False
            self._dismiss_menu_handles()
            self._ops_dragging = False

            if self._in_pop_zone and self._pop_eligible:
                ref_tile = (self._active_actions_menu.tile
                            if self._active_actions_menu else self._lp_tile)
                self._in_pop_zone = False
                self._dismiss_all_popups()
                if ref_tile is not None:
                    print("[POP_ZONE] released - firing pop")
                    try:
                        from tile_menu import _action_pop
                        _action_pop(ref_tile, board)
                    except Exception as e:
                        print(f"[POP_ZONE_ERROR] {e}")
                        import traceback
                        traceback.print_exc()

                try:
                    if board._drag_tile:
                        board._drag_tile.set_dragging(False)
                except Exception:
                    pass

                board._drag_tile = None
                board._drag_start_center = None
                self._drag_tile = None
                self._mode = 'idle'
                return

            self._in_pop_zone = False
            action = None

            if self._active_actions_menu:
                try:
                    action = self._active_actions_menu.get_highlighted_action()
                except Exception:
                    action = None
                try:
                    self._active_actions_menu.dismiss()
                except Exception:
                    pass
                self._active_actions_menu = None

            if self._active_scrubber:
                try:
                    self._active_scrubber.commit()
                except Exception:
                    pass
                try:
                    self._active_scrubber.dismiss()
                except Exception:
                    pass
                self._active_scrubber = None

            if self._active_variant_picker:
                try:
                    self._active_variant_picker.commit()
                except Exception:
                    pass
                try:
                    self._active_variant_picker.dismiss()
                except Exception:
                    pass
                self._active_variant_picker = None

            self._dismiss_pop_preview()

            if action:
                print("[MENU_DRAG] triggering action")
                try:
                    action(None)
                except Exception as e:
                    print(f"[MENU_DRAG_ACTION_ERROR] {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("[MENU_DRAG] cancelled - no highlight")

            try:
                if board._drag_tile:
                    board._drag_tile.set_dragging(False)
            except Exception:
                pass

            board._drag_tile = None
            board._drag_start_center = None
            self._drag_tile = None
            self._mode = 'idle'
            return

        if self._active_actions_menu is not None or self._active_ops_menu is not None:
            self._mode = 'idle'
            return

        if self._mode == 'group_drag' and board._drag_tile is not None:
            group = getattr(board, 'lasso_selected_tiles', None) or []
            if group and (board._drag_tile in group):
                moved = False
                try:
                    if board._drag_start_center:
                        sx, sy = board._drag_start_center
                        cx, cy = board._drag_tile.center
                        moved = ((cx - sx) ** 2 + (cy - sy) ** 2) ** 0.5 > 5
                except Exception:
                    moved = True

                for t in list(group):
                    if t is None:
                        continue
                    try:
                        cx, cy = t.center
                        cx, cy = board.snap_center(cx, cy, t)
                        t.center = (cx, cy)
                    except Exception:
                        pass

                if moved:
                    try:
                        board._capture_undo_snapshot()
                    except Exception:
                        pass

                try:
                    board._drag_tile.set_dragging(False)
                except Exception:
                    pass

                board._drag_tile = None
                board._drag_start_center = None
                self._drag_tile = None
                self._mode = 'idle'
                return

            self._mode = 'tile_drag'

        if self._mode == 'tile_drag' and board._drag_tile is not None:
            self._handle_tile_drop(touch, board._drag_tile)
            self._clear_merge_preview()
            self._mode = 'idle'
            return

        self._handle_tap(touch)
        self._mode = 'idle'

    # ------------------------------------------------------------------
    # Brace + ghost preview
    # ------------------------------------------------------------------

    def _update_brace(self, dragged):
        board = self.board
        target = board.tile_at_point_excluding(dragged.center, dragged)

        if target is self._braced_tile:
            if target is not None:
                self._update_result_ghost(dragged, target)
            return

        if self._braced_tile is not None:
            prev = self._braced_tile
            self._braced_tile = None
            ui.animate(lambda: setattr(prev, 'transform', ui.Transform()), duration=0.12)

        self._clear_result_ghost()

        if target is not None:
            self._braced_tile = target
            ui.animate(
                lambda: setattr(target, 'transform', ui.Transform.scale(0.92, 0.92)),
                duration=0.12
            )
            self._update_result_ghost(dragged, target)

    def _clear_brace(self):
        if self._braced_tile is not None:
            prev = self._braced_tile
            self._braced_tile = None
            ui.animate(lambda: setattr(prev, 'transform', ui.Transform()), duration=0.12)
        self._clear_result_ghost()

    def _update_result_ghost(self, dragged, target):
        board      = self.board
        grid       = board.grid
        drag_start = board._drag_start_center
        if drag_start is None:
            return

        try:
            if not target.frame.contains_point(dragged.center):
                self._clear_result_ghost()
                return
        except Exception:
            pass

        direction = board._drag_direction(dragged)
        if direction is None:
            self._clear_result_ghost()
            return

        ctx = {
            'board':             board,
            'spawn_direction':   direction,
            'drag_start_center': drag_start,
            'target_original':   (getattr(target.data, 'display', None) or
                                  getattr(target, 'text', '') or ''),
        }

        result = board.merge_engine.find_preview(dragged, target, ctx)
        if result is None:
            self._clear_result_ghost()
            return

        if len(result) == 3:
            disp, kind, extra = result
        else:
            disp, kind = result
            extra = None

        if kind == 'fraction' and extra is not None:
            nd = extra.get('numer_disp', '?')
            dd = extra.get('denom_disp', '?')
            disp = f"{nd}/{dd}"
            kind = 'number'

        tx, ty = target.center
        gx, gy = tx, ty - grid

        from tile import Tile as _Tile
        color = _Tile.color_for_kind(kind)
        size  = int(grid * 0.85)

        existing = getattr(self, '_result_ghost', None)
        if existing is not None:
            try:
                existing.center = (gx, gy)
            except Exception:
                pass
            return

        try:
            ghost = _Tile(
                text=disp, kind=kind, color=color,
                w_cells=1, h_cells=1, cell_size=size, gutter=2,
            )
            ghost._is_ghost     = True   # bulletproof tag — checked in tile_at_point
            ghost.touch_enabled = False
            ghost.alpha         = 0.0
            ghost.center        = (gx, gy)
            board.add_subview(ghost)
            ghost.bring_to_front()
            self._result_ghost = ghost
            ui.animate(lambda: setattr(ghost, 'alpha', 0.55), duration=0.15)
        except Exception as e:
            print(f"[RESULT_GHOST_ERROR] {e}")

    def _clear_result_ghost(self):
        ghost = getattr(self, '_result_ghost', None)
        if ghost is not None:
            self._result_ghost = None
            try:
                if ghost.superview:
                    ghost.superview.remove_subview(ghost)
            except Exception:
                pass

    def _clear_op_hint(self):
        pass  # superseded by _clear_result_ghost

    def _op_symbol(self, dragged, target):
        board = self.board
        drag_start = board._drag_start_center
        if drag_start is None:
            return None

        direction = board._drag_direction(dragged)
        if direction is None:
            return None

        ctx = {
            'board': board,
            'spawn_direction': direction,
            'drag_start_center': drag_start,
            'target_original': (getattr(target.data, 'display', None) or getattr(target, 'text', '') or ''),
        }
        rule = board.merge_engine.find_rule(dragged, target, ctx)
        if rule is None:
            return None

        symbol_map = {
            'DirectionalAddRule': '+',
            'DirectionalSubtractRule': '-',
            'DirectionalMultiplyRule': 'x',
            'VerticalDivideRule': '/',
        }
        return symbol_map.get(rule.__class__.__name__)

    # ------------------------------------------------------------------
    # Tile drop
    # ------------------------------------------------------------------

    def _handle_tile_drop(self, touch, t):
        board = self.board
        try:
            board._dbg_tile("drop_start", t)
        except Exception:
            pass

        cx, cy = t.center
        cx, cy = board.snap_center(cx, cy, t)
        t.center = (cx, cy)
        try:
            board._enforce_exclusion(t)
        except Exception:
            pass

        tile_moved = False
        if board._drag_start_center:
            sx, sy = board._drag_start_center
            tile_moved = ((cx - sx) ** 2 + (cy - sy) ** 2) ** 0.5 > 5

        try:
            parent     = board.superview
            delete_bin = getattr(parent, 'delete_bin', None)
            if delete_bin and delete_bin.overlaps_tile(t):
                delete_bin.delete_tile(t)
                board._capture_undo_snapshot()
                t.set_dragging(False)
                board._drag_tile         = None
                board._drag_start_center = None
                self._drag_tile          = None
                return
        except Exception as e:
            print(f"[DBG delete_bin_check_error] {e}")

        if getattr(t, 'kind', '') == 'eq':
            try:
                board._eq_chain_scan(t)
            except Exception:
                pass
            try:
                board._capture_undo_snapshot()
            except Exception:
                pass
            t.set_dragging(False)
            board._drag_tile         = None
            board._drag_start_center = None
            self._drag_tile          = None
            return

        drop_p = t.center
        target = board.tile_at_point_excluding(drop_p, t)

        if target is not None:
            spawn_direction = board._drag_direction(t)
            ctx = {
                'board':             board,
                'spawn_direction':   spawn_direction,
                'drag_start_center': board._drag_start_center,
            }

            # Use preview as a non-mutating can_merge check.
            # Actual try_merge is deferred to _do_merge so tiles
            # are not mutated before fly_to animation completes.
            preview = board.merge_engine.find_preview(t, target, ctx)
            merge_likely = (preview is not None)

            # For rules that don't support preview, fall back to try_merge
            # immediately (legacy behaviour — these rules don't mutate eagerly).
            if not merge_likely:
                res = board.merge_engine.try_merge(t, target, ctx)
            else:
                res = True  # sentinel — real merge happens in _do_merge

            if res is not None:
                target_cx,  target_cy  = target.center
                dragged_cx, dragged_cy = t.center
                replace_tile = target  # best guess for burst position

                t.set_dragging(False)
                board._drag_tile         = None
                board._drag_start_center = None
                self._drag_tile          = None

                def _do_merge():
                    from tile_anim import merge_burst, spawn_from
                    self._clear_result_ghost()
                    self._clear_brace()

                    if merge_likely:
                        # Now safe to mutate — animation already finished
                        actual_res = board.merge_engine.try_merge(t, target, ctx)
                    else:
                        actual_res = res  # already computed above

                    if actual_res is None or actual_res is True:
                        return

                    if getattr(actual_res, 'spawn_direction', None) is None:
                        actual_res.spawn_direction = spawn_direction

                    is_tool_merge = bool(getattr(actual_res, 'no_sticky', False))
                    rt = getattr(actual_res, 'replace_tile', None) or target
                    rt_cx, rt_cy = rt.center if rt else (target_cx, target_cy)

                    merged, spawned_tile = board._apply_merge_result(
                        actual_res, dragged=t, target=target)

                    if merged:
                        result_center = (spawned_tile.center
                                         if spawned_tile else (rt_cx, rt_cy))
                        action = {
                            'type':            'tool_merge' if is_tool_merge else 'merge',
                            'dragged_center':  (dragged_cx, dragged_cy),
                            'target_center':   (target_cx,  target_cy),
                            'replace_center':  (rt_cx, rt_cy),
                            'spawn_direction': spawn_direction,
                            'result_center':   result_center,
                        }
                        board._capture_undo_snapshot(action=action)
                        result_tile = spawned_tile or rt or target
                        burst_color = getattr(result_tile, 'base_color', None) or '#FFD60A'
                        merge_burst(result_tile, color=burst_color)
                        if spawned_tile is not None:
                            spawn_from(spawned_tile,
                                       origin_center=(target_cx, target_cy),
                                       final_center=spawned_tile.center)

                from tile_anim import fly_to
                fly_to(t, target_center=(target_cx, target_cy),
                       completion=lambda: _do_merge())
                return

        if tile_moved:
            try:
                board._capture_undo_snapshot()
            except Exception:
                pass
        t.set_dragging(False)
        board._drag_tile         = None
        board._drag_start_center = None
        self._drag_tile          = None

    def _handle_tap(self, touch):
        board = self.board
        tstamp = touch.timestamp
        p = board._touch_point(touch, in_view=board)

        dt = tstamp - getattr(board, '_last_tap_time', 0.0)
        last = getattr(board, '_last_tap_pos', (0.0, 0.0))
        dx = p[0] - last[0]
        dy = p[1] - last[1]

        is_double = dt < 0.30 and (dx * dx + dy * dy) < (30 * 30)

        if is_double:
            t = board.tile_at_point(p)
            if t is None:
                print("[DBG] double-tap undo")
                try:
                    board.undo()
                except Exception:
                    pass
                board._last_tap_time = 0.0
            else:
                new_tile = Tile(
                    text='1',
                    kind='number',
                    color='#FFD60A',
                    cell_size=board.grid,
                    w_cells=1,
                    h_cells=1,
                    gutter=4
                )
                board.add_tile(new_tile, center=p, snap=True)
                try:
                    board._enforce_exclusion(new_tile)
                except Exception:
                    pass
                try:
                    board._capture_undo_snapshot()
                except Exception:
                    pass
                board._last_tap_time = 0.0
        else:
            board._last_tap_time = tstamp
            board._last_tap_pos = (p[0], p[1])

    # ------------------------------------------------------------------
    # Merge preview (legacy label system - disabled)
    # ------------------------------------------------------------------

    def _update_merge_preview(self, dragged):
        board = self.board
        drag_start = board._drag_start_center
        drag_current = dragged.center if dragged else None

        if drag_start is None or drag_current is None:
            self._clear_merge_preview()
            return

        target = board.tile_at_point_excluding(drag_current, dragged)
        if target is None:
            self._clear_merge_preview()
            return

        if self._preview_tile is not target:
            self._clear_merge_preview()
            try:
                original = (getattr(target.data, 'display', None) or getattr(target, 'text', '') or '')
                self._preview_original = original
                self._preview_tile = target
                ui.animate(lambda: setattr(target, 'transform', ui.Transform.scale(0.92, 0.92)), duration=0.12)
            except Exception:
                return

        spawn_direction = board._drag_direction(dragged)
        ctx = {
            'board': board,
            'spawn_direction': spawn_direction,
            'drag_start_center': drag_start,
            'target_original': self._preview_original,
        }
        rule = board.merge_engine.find_rule(dragged, target, ctx)
        if rule is None:
            self._clear_merge_preview()
            return

        preview = rule.preview_label(dragged, target, ctx)
        if preview is None:
            self._clear_merge_preview()
            return

        try:
            target.set_label(preview)
        except Exception:
            self._clear_merge_preview()

    def _dismiss_pop_preview(self):
        if self._pop_preview is not None:
            try:
                self._pop_preview.dismiss()
            except Exception:
                pass
            self._pop_preview = None

    def _clear_merge_preview(self):
        if self._preview_tile is not None:
            try:
                if self._preview_original is not None:
                    self._preview_tile.set_label(self._preview_original)
                pt = self._preview_tile
                ui.animate(lambda: setattr(pt, 'transform', ui.Transform()), duration=0.12)
            except Exception:
                pass

        if getattr(self, '_preview_overlay', None) is not None:
            try:
                ov = self._preview_overlay

                def _remove():
                    try:
                        if ov.superview:
                            ov.superview.remove_subview(ov)
                    except Exception:
                        pass

                ov.dismiss()
                ui.animate(_remove, duration=0.12)
            except Exception:
                pass
            self._preview_overlay = None

        self._preview_tile = None
        self._preview_original = None

    # ------------------------------------------------------------------
    # Menu drag
    # ------------------------------------------------------------------

    def _handle_menu_drag(self, p):
        board = self.board

        if self._active_scrubber is not None:
            tile = self._active_scrubber.tile
            if p[0] <= tile.frame.x + tile.frame.width:
                self._active_scrubber.dismiss()
                self._active_scrubber = None
                self._scrubber_eligible = True
                from tile_menu import ActionsMenu
                actions_menu = ActionsMenu(tile, board)
                self._active_actions_menu = actions_menu
                board.add_subview(actions_menu)
                actions_menu.bring_to_front()
                self._show_menu_handles(tile)
                print("[SCRUBBER] dismissed - actions restored")
            else:
                try:
                    self._active_scrubber.update_from_board_y(p[1])
                except Exception as e:
                    print(f"[SCRUBBER_DRAG_ERROR] {e}")
            return

        if self._active_variant_picker is not None:
            tile = self._active_variant_picker.tile
            if p[0] <= tile.frame.x + tile.frame.width:
                self._active_variant_picker.dismiss()
                self._active_variant_picker = None
                self._variant_eligible = True
                from tile_menu import ActionsMenu
                actions_menu = ActionsMenu(tile, board)
                self._active_actions_menu = actions_menu
                board.add_subview(actions_menu)
                actions_menu.bring_to_front()
                self._show_menu_handles(tile)
                print("[VARIANT_PICKER] dismissed - actions restored")
            else:
                try:
                    self._active_variant_picker.update_from_board_y(p[1])
                except Exception as e:
                    print(f"[VARIANT_PICKER_DRAG_ERROR] {e}")
            return

        ref_tile = self._lp_tile
        if ref_tile is None and self._active_actions_menu is not None:
            ref_tile = self._active_actions_menu.tile

        if ref_tile is not None:
            tile_right = ref_tile.frame.x + ref_tile.frame.width
            tile_top = ref_tile.frame.y
            tile_bottom = ref_tile.frame.y + ref_tile.frame.height
            tile_mid_y = (tile_top + tile_bottom) / 2

            in_tile_row = (tile_top - 10) <= p[1] <= (tile_bottom + 10)
            in_right_col = (tile_right + 10) < p[0] <= (tile_right + board.grid)

            if self._variant_eligible and in_right_col and in_tile_row:
                if self._active_actions_menu:
                    self._active_actions_menu.dismiss()
                    self._active_actions_menu = None
                self._dismiss_menu_handles()
                from tile_menu import TileVariantPicker
                picker = TileVariantPicker(ref_tile, board)
                self._active_variant_picker = picker
                board.add_subview(picker)
                picker._position()
                picker.bring_to_front()
                print("[VARIANT_PICKER] activated")
                try:
                    picker.update_from_board_y(p[1])
                except Exception:
                    pass
                return

            if self._scrubber_eligible and in_right_col and p[1] >= tile_mid_y:
                if self._active_actions_menu:
                    self._active_actions_menu.dismiss()
                    self._active_actions_menu = None
                self._dismiss_menu_handles()
                from tile_menu import NumberScrubber
                scrubber = NumberScrubber(ref_tile, board)
                self._active_scrubber = scrubber
                board.add_subview(scrubber)
                scrubber.bring_to_front()
                print("[SCRUBBER] activated")
                try:
                    scrubber.update_from_board_y(p[1])
                except Exception:
                    pass
                return

            if self._pop_eligible and self._pop_preview is not None:
                over_ghost = self._pop_preview.is_over_left_ghost(p)
                if over_ghost and not self._in_pop_zone:
                    self._in_pop_zone = True
                    self._pop_preview.show_remain()
                    print("[POP_ZONE] entered")
                elif (not over_ghost) and self._in_pop_zone:
                    self._in_pop_zone = False
                    self._pop_preview.hide_remain()
                    print("[POP_ZONE] exited")

        if self._active_actions_menu:
            try:
                self._active_actions_menu.highlight_at_point(
                    p[0] - self._active_actions_menu.x,
                    p[1] - self._active_actions_menu.y
                )
            except Exception as e:
                print(f"[ACTIONS_MENU_DRAG_ERROR] {e}")

    # ------------------------------------------------------------------
    # Menu show + handles
    # ------------------------------------------------------------------

    def _show_menu(self, tile):
        board = self.board
        from tile_menu import _is_poppable, ActionsMenu

        self._pop_eligible = _is_poppable(tile)
        self._variant_eligible = False
        self._scrubber_eligible = False

        try:
            from tile_menu import _has_variants
            self._variant_eligible = _has_variants(tile)
        except Exception:
            pass

        try:
            if tile.kind == 'number':
                expr = str(getattr(tile, 'expr_str', tile.text) or '').strip()
                self._scrubber_eligible = expr.lstrip('-').isdigit()
        except Exception:
            pass

        menu = ActionsMenu(tile, board)
        board.add_subview(menu)
        self._active_actions_menu = menu
        self._show_menu_handles(tile)

        if self._pop_eligible:
            self._dismiss_pop_preview()
            try:
                pv = PopPreviewView(tile, board)
                board.add_subview(pv)
                self._pop_preview = pv
            except Exception as e:
                print(f"[POP_PREVIEW_SHOW_ERROR] {e}")

    def _show_menu_handles(self, tile):
        board = self.board
        self._dismiss_menu_handles()

        g = board.grid
        tx, ty = tile.frame.x, tile.frame.y
        tw, th = tile.frame.width, tile.frame.height

        handles = []
        if self._scrubber_eligible or self._variant_eligible:
            handles.append((tx + tw + g * 0.6 - 20, ty + th / 2 - 14, 20, 28, '>'))

        for hx, hy, hw, hh, symbol in handles:
            v = ui.View(frame=(hx, hy, hw, hh))
            v.background_color = '#3A3A3C'
            v.corner_radius = 5
            v.alpha = 0.85

            lbl = ui.Label(frame=(0, 0, hw, hh))
            lbl.text = symbol
            lbl.font = ('<System-Bold>', 11)
            lbl.text_color = '#AEAEB2'
            lbl.alignment = ui.ALIGN_CENTER

            v.add_subview(lbl)
            board.add_subview(v)
            self._menu_handles.append(v)

    def _dismiss_menu_handles(self):
        for h in self._menu_handles:
            try:
                if h.superview:
                    h.superview.remove_subview(h)
            except Exception:
                pass
        self._menu_handles = []
