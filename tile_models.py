import math
import time
import uuid

import ui

from constants import (
    DOUBLE_TAP_WINDOW,
    DRAG_THRESHOLD,
    GRID_SIZE,
    PADDING,
    TILE_COLOR,
    TILE_DRAG_COLOR,
    TILE_SIZE,
)
from ui_utils import clamp, get_point, pt_xy


class Tile(ui.View):
    def __init__(self, board):
        super().__init__()
        self.board = board
        self.width = TILE_SIZE
        self.height = TILE_SIZE
        self.corner_radius = 8
        self.flex = ''

        self.dragging = False
        self.touch_offset = (0, 0)

        self._touch_start_pt = None
        self._dragged = False

        self.label_text = ''
        self.tile_color = TILE_COLOR
        self.kind = 'generic'
        self.expr_str = ''
        self.pending_op = None
        self.group_id = None
        self._group_start_positions = {}
        self._my_start_position = None

        self._font_max = 16
        self._font_min = 8
        self._wide_mode = False

        self.background_color = self.tile_color
        self.border_width = 0
        self.border_color = '#00FF0040'

        self.label = ui.Label()
        self.label.text = ''
        self.label.font = ('<System-Bold>', self._font_max)
        self.label.text_color = '#000000'
        self.label.alignment = ui.ALIGN_CENTER
        self.label.number_of_lines = 1
        self.add_subview(self.label)

    def layout(self):
        self.label.frame = (0, 0, self.width, self.height)

    def set_grouped(self, is_grouped):
        if is_grouped:
            self.border_width = 2
            self.border_color = '#00FF0080'
        else:
            self.border_width = 0
            self.group_id = None

    def set_label(self, text):
        self.label_text = text or ''
        self.label.text = self.label_text
        if not self.expr_str:
            self.expr_str = self.label_text
        self._fit_label_and_size()

    def set_tile_color(self, c):
        self.tile_color = c
        self.background_color = TILE_DRAG_COLOR if self.dragging else self.tile_color

    def _desired_widths(self):
        return TILE_SIZE, TILE_SIZE + GRID_SIZE

    def _text_width(self, s, font_size):
        try:
            w, _ = ui.measure_string(s, font=('<System-Bold>', font_size))
            return w
        except:
            return len(s) * (font_size * 0.6)

    def _set_wide_mode(self, wide_on):
        normal_w, wide_w = self._desired_widths()
        self._wide_mode = bool(wide_on)
        self.width = wide_w if self._wide_mode else normal_w
        try:
            self.set_needs_display()
        except:
            pass

    def _fit_label_and_size(self):
        s = self.label_text or ''
        if not s:
            self._set_wide_mode(False)
            self.label.font = ('<System-Bold>', self._font_max)
            return

        pad = 8
        normal_w, _ = self._desired_widths()

        if self._text_width(s, self._font_max) > normal_w - pad:
            self._set_wide_mode(True)
        else:
            self._set_wide_mode(False)

        avail = self.width - pad
        fs = self._font_max
        while fs > self._font_min and self._text_width(s, fs) > avail:
            fs -= 1
        self.label.font = ('<System-Bold>', fs)

    def touch_began(self, touch):
        self.bring_to_front()
        self.board.dismiss_editor()

        pt = get_point(touch, in_view=self)
        self.touch_offset = pt_xy(pt)

        self._touch_start_pt = get_point(touch, in_view=self.board)
        self._dragged = False
        self.dragging = True
        self.background_color = TILE_DRAG_COLOR

        self._my_start_position = (self.x, self.y)

        if self.group_id:
            group_tiles = self.board.get_group_tiles(self)
            self._group_start_positions = {
                t: (t.x, t.y) for t in group_tiles if t is not self
            }

    def touch_moved(self, touch):
        if not self.dragging:
            return

        cur = get_point(touch, in_view=self.board)
        cx, cy = pt_xy(cur)
        ss = self._touch_start_pt
        if ss is not None:
            sx, sy = pt_xy(ss)
            if (abs(cx - sx) + abs(cy - sy)) > DRAG_THRESHOLD:
                self._dragged = True

        tx, ty = pt_xy(touch.location)
        new_x = self.x + tx - self.touch_offset[0]
        new_y = self.y + ty - self.touch_offset[1]
        new_x = clamp(new_x, PADDING, self.board.width - self.width - PADDING)
        new_y = clamp(new_y, PADDING, self.board.height - self.height - PADDING)

        self.x = new_x
        self.y = new_y

        if self.group_id and self._group_start_positions and self._my_start_position:
            dx = self.x - self._my_start_position[0]
            dy = self.y - self._my_start_position[1]
            for t, (ox, oy) in self._group_start_positions.items():
                t.x = clamp(ox + dx, PADDING, self.board.width - t.width - PADDING)
                t.y = clamp(oy + dy, PADDING, self.board.height - t.height - PADDING)

    def touch_ended(self, touch):
        self.dragging = False
        self.background_color = self.tile_color
        self._group_start_positions = {}
        self._my_start_position = None

        if self.board.is_over_trash(self):
            self.board.delete_tile(self)
            return

        if not self._dragged:
            self.board.show_editor_for_tile(self)
            return

        try:
            self.board.finalize_drop(self)
        except Exception as e:
            print('touch_ended finalize_drop error:', e)


    def snap_to_grid(self):
        """
        Center-snap with size awareness:
        - Normal tiles (1 cell): center snaps to cell center
        - Wide tiles (2 cells): center snaps to grid line (cell boundary)
        - Tall tiles (2 cells): center snaps to grid line (cell boundary)
        This keeps multi-cell tiles aligned across exactly 2 cells.
        """
        step = GRID_SIZE
        half = step * 0.5

        cx = self.x + self.width * 0.5
        cy = self.y + self.height * 0.5

        # Horizontal: wide tiles snap center to grid line, normal to cell center
        if self.width > TILE_SIZE + 2:
            grid_cx = PADDING + round((cx - PADDING) / step) * step
        else:
            grid_cx = PADDING + half + round((cx - (PADDING + half)) / step) * step

        # Vertical: tall tiles snap center to grid line, normal to cell center
        if self.height > TILE_SIZE + 2:
            grid_cy = PADDING + round((cy - PADDING) / step) * step
        else:
            grid_cy = PADDING + half + round((cy - (PADDING + half)) / step) * step

        new_x = grid_cx - self.width * 0.5
        new_y = grid_cy - self.height * 0.5

        new_x = clamp(new_x, PADDING, self.board.width - self.width - PADDING)
        new_y = clamp(new_y, PADDING, self.board.height - self.height - PADDING)

        delta_x = new_x - self.x
        delta_y = new_y - self.y

        def anim():
            self.x = new_x
            self.y = new_y

            if self.group_id:
                for t in self.board.get_group_tiles(self):
                    if t is self:
                        continue

                    tcx = (t.x + delta_x) + t.width * 0.5
                    tcy = (t.y + delta_y) + t.height * 0.5

                    if t.width > TILE_SIZE + 2:
                        t_grid_cx = PADDING + round((tcx - PADDING) / step) * step
                    else:
                        t_grid_cx = PADDING + half + round((tcx - (PADDING + half)) / step) * step

                    if t.height > TILE_SIZE + 2:
                        t_grid_cy = PADDING + round((tcy - PADDING) / step) * step
                    else:
                        t_grid_cy = PADDING + half + round((tcy - (PADDING + half)) / step) * step

                    tx = clamp(t_grid_cx - t.width * 0.5, PADDING, self.board.width - t.width - PADDING)
                    ty = clamp(t_grid_cy - t.height * 0.5, PADDING, self.board.height - t.height - PADDING)

                    t.x = tx
                    t.y = ty

        ui.animate(anim, duration=0.15)


class FractionTile(Tile):
    """
    A 1x2 (vertical) fraction tile.
    - Initially shows only a bar.
    - First integer merged becomes numerator.
    - Second integer merged becomes denominator.
    - After complete: expr_str becomes "(n/d)" so it behaves like a normal numeric tile.
    """
    def __init__(self, board):
        super().__init__(board)
        # Make it "1 x 2" tall (TILE_SIZE + one grid step)
        self.width = TILE_SIZE
        self.height = TILE_SIZE + GRID_SIZE
        self.kind = 'fraction'

        self.numer = None
        self.denom = None

        # Base look
        self.set_tile_color(TILE_COLOR)
        try:
            self.label.hidden = True
        except:
            pass

        # Two line labels + bar
        self.num_label = ui.Label()
        self.num_label.text = ''
        self.num_label.font = ('<System-Bold>', 14)
        self.num_label.text_color = '#000000'
        self.num_label.alignment = ui.ALIGN_CENTER
        self.add_subview(self.num_label)

        self.den_label = ui.Label()
        self.den_label.text = ''
        self.den_label.font = ('<System-Bold>', 14)
        self.den_label.text_color = '#000000'
        self.den_label.alignment = ui.ALIGN_CENTER
        self.add_subview(self.den_label)

        self.bar = ui.View()
        self.bar.background_color = '#000000'
        self.add_subview(self.bar)

        self._refresh_display()

    def layout(self):
        # override Tile.layout
        w, h = self.width, self.height
        pad_x = 4
        top_h = int(h * 0.45)
        bot_h = int(h * 0.45)
        bar_h = 2

        self.num_label.frame = (pad_x, 0, w - 2 * pad_x, top_h)
        self.den_label.frame = (pad_x, h - bot_h, w - 2 * pad_x, bot_h)
        self.bar.frame = (pad_x, (h - bar_h) / 2, w - 2 * pad_x, bar_h)

    def _refresh_display(self):
        # Show numerator/denominator if present
        self.num_label.text = '' if self.numer is None else str(self.numer)
        self.den_label.text = '' if self.denom is None else str(self.denom)

        # expr_str is only "numeric" when complete
        if self.numer is not None and self.denom is not None:
            self.expr_str = f'({self.numer}/{self.denom})'
            self.label_text = f'{self.numer}/{self.denom}'
        else:
            self.expr_str = ''  # not evaluatable until complete
            self.label_text = ''

        try:
            self.set_needs_layout()
        except:
            pass

    def set_fraction_numer(self, n):
        self.numer = int(n)
        self._refresh_display()

    def set_fraction_denom(self, d):
        self.denom = int(d)
        self._refresh_display()


class SpawnerDragMixin:
    """Shared drag/tap lifecycle for tile spawners."""

    def _init_spawner_drag_state(self):
        self.dragging = False
        self.touch_offset = (0, 0)
        self.clone = None
        self._touch_start_pt = None
        self._drag_started = False

    def touch_began(self, touch):
        self.spawner_touch_began(touch)

    def touch_moved(self, touch):
        self.spawner_touch_moved(touch)

    def touch_ended(self, touch):
        self.spawner_touch_ended(touch)

    def _add_clone_to_tiles_on_drag_start(self):
        return False

    def _on_spawner_tap(self):
        raise NotImplementedError

    def _drop_clone(self, clone):
        if self.board.is_over_trash(clone):
            self.board.delete_tile(clone)
            return

        try:
            self.board.finalize_drop(clone)
        except Exception as e:
            print('spawner finalize_drop error:', e)

    def spawner_touch_began(self, touch):
        self.board.dismiss_editor()
        self._touch_start_pt = get_point(touch, in_view=self.board)
        self._drag_started = False
        self.clone = None
        self.touch_offset = pt_xy(get_point(touch, in_view=self))
        self.dragging = True

    def spawner_touch_moved(self, touch):
        if not self.dragging:
            return

        if not self._drag_started:
            cur = get_point(touch, in_view=self.board)
            cx, cy = pt_xy(cur)
            sx, sy = pt_xy(self._touch_start_pt)
            if (abs(cx - sx) + abs(cy - sy)) > DRAG_THRESHOLD:
                self._drag_started = True
                self.clone = self._spawn_clone()
                if self._add_clone_to_tiles_on_drag_start() and self.clone not in self.board.tiles:
                    self.board.tiles.append(self.clone)
                self.clone.x = self.x
                self.clone.y = self.y
                self.clone.dragging = True
                self.clone.touch_offset = self.touch_offset
                self.clone.background_color = TILE_DRAG_COLOR

        if self._drag_started and self.clone:
            tx, ty = pt_xy(touch.location)
            self.clone.x = clamp(self.x + tx - self.touch_offset[0],
                                 PADDING, self.board.width - self.clone.width - PADDING)
            self.clone.y = clamp(self.y + ty - self.touch_offset[1],
                                 PADDING, self.board.height - self.clone.height - PADDING)

    def spawner_touch_ended(self, touch):
        if self.dragging and not self._drag_started:
            self._on_spawner_tap()
            self.dragging = False
            return

        if self.clone:
            self.clone.dragging = False
            try:
                self.clone.background_color = self.clone.tile_color
            except:
                pass

            self._drop_clone(self.clone)
            self.clone = None

        self.dragging = False
        self._drag_started = False


class SourceTile(ui.View, SpawnerDragMixin):
    def __init__(self, board):
        super().__init__()
        self.board = board
        self.width = TILE_SIZE
        self.height = TILE_SIZE
        self.corner_radius = 8
        self.flex = ''

        self.label_text = ''
        self.tile_color = TILE_COLOR
        self.background_color = self.tile_color

        self._init_spawner_drag_state()

        self.plus = ui.Label()
        self.plus.text = '+'
        self.plus.font = ('<System-Bold>', 24)
        self.plus.text_color = '#000000'
        self.plus.alignment = ui.ALIGN_CENTER
        self.add_subview(self.plus)

        self.preview = ui.Label()
        self.preview.text = ''
        self.preview.font = ('<System-Bold>', 10)
        self.preview.text_color = '#000000'
        self.preview.alignment = ui.ALIGN_CENTER
        self.preview.number_of_lines = 1
        self.add_subview(self.preview)

    def layout(self):
        self.plus.frame = (0, 0, self.width, self.height)
        self.preview.frame = (4, self.height - 14, self.width - 8, 12)

    def set_label(self, text):
        self.label_text = text or ''
        self.preview.text = self.label_text

    def set_tile_color(self, c):
        self.tile_color = c
        self.background_color = self.tile_color

    def _spawn_clone(self):
        t = Tile(self.board)
        self.board.add_subview(t)
        t.kind = 'generic'
        t.expr_str = self.label_text or ''
        t.set_label(self.label_text or '')
        t.set_tile_color(self.tile_color)
        return t

    def _on_spawner_tap(self):
        self.board.show_editor_for_tile(self)

    def _drop_clone(self, clone):
        if clone not in self.board.tiles:
            self.board.tiles.append(clone)
        try:
            super()._drop_clone(clone)
        except Exception as e:
            print('SourceTile finalize_drop error:', e)


class TokenSpawner(ui.View, SpawnerDragMixin):
    def __init__(self, board, token, kind='generic', color=TILE_COLOR, text_color='#000000'):
        super().__init__()
        self.board = board
        self.token = str(token)
        self.kind = kind
        self.tile_color = color
        self._text_color = text_color

        self.width = TILE_SIZE
        self.height = TILE_SIZE
        self.corner_radius = 8
        self.flex = ''
        self.background_color = self.tile_color

        self._init_spawner_drag_state()

        self.label = ui.Label()
        self.label.text = self.token
        self.label.font = ('<System-Bold>', 18)
        self.label.text_color = text_color
        self.label.alignment = ui.ALIGN_CENTER
        self.label.frame = (0, 0, TILE_SIZE, TILE_SIZE)
        self.add_subview(self.label)

    def layout(self):
        self.label.frame = (0, 0, self.width, self.height)

    def _spawn_clone(self):
        if self.kind == 'fraction':
            t = FractionTile(self.board)
            self.board.add_subview(t)
            self.board.tiles.append(t)
            return t

        t = Tile(self.board)
        self.board.add_subview(t)
        t.kind = self.kind
        t.expr_str = self.token
        t.set_label(self.token)
        t.set_tile_color(self.tile_color)
        try:
            t.label.text_color = self._text_color
        except:
            pass
        return t

    def _find_board_center_spot(self):
        b = self.board
        kbd_top = getattr(b, '_keyboard_top_y', b.height)
        play_h = kbd_top - PADDING
        center_x = b.width * 0.5
        center_y = PADDING + play_h * 0.5

        w = TILE_SIZE
        h = TILE_SIZE + GRID_SIZE if self.kind == 'fraction' else TILE_SIZE

        for cx, cy in b._aligned_positions_around(center_x, center_y, max_r=12):
            nx = clamp(cx, PADDING, b.width - w - PADDING)
            ny = clamp(cy, PADDING, kbd_top - h - PADDING)
            if ny < PADDING:
                continue
            if not b._occupied_at(nx, ny, w, h):
                return nx, ny

        return clamp(center_x - w * 0.5, PADDING, b.width - w - PADDING), clamp(center_y - h * 0.5, PADDING, kbd_top - h - PADDING)

    def _tap_spawn(self):
        t = self._spawn_clone()
        if t not in self.board.tiles:
            self.board.tiles.append(t)

        x, y = self._find_board_center_spot()
        t.x = x
        t.y = y

        if self.board.snap_enabled:
            try:
                t.snap_to_grid()
            except:
                pass

        t.bring_to_front()
        if self.board.on_state_changed:
            try:
                self.board.on_state_changed()
            except:
                pass

    def _add_clone_to_tiles_on_drag_start(self):
        return True

    def _on_spawner_tap(self):
        self._tap_spawn()
