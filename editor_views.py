import ui

from constants import EDITOR_BG, EDITOR_BORDER, PADDING
from ui_utils import clamp, get_point, pt_xy


class _EditorOverlay(ui.View):
    def __init__(self, board):
        super().__init__()
        self.board = board
        self.background_color = (0, 0, 0, 0)
        self.flex = 'WH'
        self.frame = (0, 0, board.width, board.height)

    def touch_began(self, touch):
        popup = getattr(self.board, 'tile_editor', None)
        if not popup:
            self.board.dismiss_editor()
            return
        pt = get_point(touch, in_view=self)
        x, y = pt_xy(pt)
        if not popup.frame.contains_point((x, y)):
            self.board.dismiss_editor()


class TileEditorPopup(ui.View):
    BTN = 42
    GAP = 6
    PAD = 6

    def __init__(self, board):
        super().__init__()
        self.board = board
        self.tile = None
        self.background_color = EDITOR_BG
        self.corner_radius = 10
        self.border_width = 1
        self.border_color = EDITOR_BORDER
        self.flex = ''

        self.alt_btn = ui.Button()
        self.alt_btn.font = ('<System-Bold>', 15)
        self.alt_btn.corner_radius = 8
        self.alt_btn.action = self._on_alt
        self.add_subview(self.alt_btn)

        self.sd_btn = ui.Button()
        self.sd_btn.title = 'S↔D'
        self.sd_btn.font = ('<System-Bold>', 10)
        self.sd_btn.background_color = '#FFB347'
        self.sd_btn.tint_color = '#000000'
        self.sd_btn.corner_radius = 8
        self.sd_btn.action = self._on_sd
        self.add_subview(self.sd_btn)

        self.pin_btn = ui.Button()
        self.pin_btn.font = ('<System>', 18)
        self.pin_btn.corner_radius = 8
        self.pin_btn.action = self._on_pin
        self.add_subview(self.pin_btn)

        self.ungroup_btn = ui.Button()
        self.ungroup_btn.title = '⊘'
        self.ungroup_btn.font = ('<System-Bold>', 18)
        self.ungroup_btn.background_color = '#FF9F0A'
        self.ungroup_btn.tint_color = '#000000'
        self.ungroup_btn.corner_radius = 8
        self.ungroup_btn.action = self._on_ungroup
        self.add_subview(self.ungroup_btn)

        self.del_btn = ui.Button()
        self.del_btn.title = '🗑'
        self.del_btn.font = ('<System>', 18)
        self.del_btn.background_color = '#FF453A'
        self.del_btn.tint_color = '#FFFFFF'
        self.del_btn.corner_radius = 8
        self.del_btn.action = self._on_delete
        self.add_subview(self.del_btn)

    def _get_visible_buttons(self):
        if not self.tile:
            return []
        kind = getattr(self.tile, 'kind', 'generic')
        expr = getattr(self.tile, 'expr_str', '').strip()
        is_grouped = bool(getattr(self.tile, 'group_id', None))
        is_sticky = getattr(self.tile, '_sticky', False)

        btns = []

        alt_info = None
        if not is_grouped:
            if kind == 'op' and expr == '-':
                alt_info = ('±', '#F87171', '#FFF')
            elif kind == 'op' and expr == '/':
                alt_info = ('¹/₁', '#FFB347', '#000')
            elif kind == 'negate':
                alt_info = ('−', '#6B9FFF', '#FFF')
            elif kind == 'fraction' and getattr(self.tile, 'numer', None) is None and getattr(self.tile, 'denom', None) is None:
                alt_info = ('÷', '#6B9FFF', '#FFF')
            elif kind == 'expr':
                alt_info = ('x=', '#A78BFA', '#FFF')
            elif kind == 'subst' and getattr(self.tile, 'subst_val', None) is None:
                alt_info = ('x', '#7ED6A8', '#000')
            elif kind == 'split':
                alt_info = ('✂✂', '#FDA4AF', '#FFF')
            elif kind == 'supersplit':
                alt_info = ('✂', '#FDA4AF', '#FFF')

        if alt_info:
            self.alt_btn.title = alt_info[0]
            self.alt_btn.background_color = alt_info[1]
            self.alt_btn.tint_color = alt_info[2]
            btns.append(self.alt_btn)

        if not is_grouped:
            try:
                if self.board.can_toggle_simple_decimal(self.tile):
                    btns.append(self.sd_btn)
            except:
                pass

        if is_grouped:
            btns.append(self.ungroup_btn)

        self.pin_btn.title = '📌' if is_sticky else '📍'
        self.pin_btn.background_color = '#34C759' if is_sticky else '#3A3A3C'
        self.pin_btn.tint_color = '#FFFFFF'
        btns.append(self.pin_btn)

        btns.append(self.del_btn)
        return btns

    def layout(self):
        btns = self._get_visible_buttons()
        all_btns = [self.alt_btn, self.sd_btn, self.pin_btn, self.ungroup_btn, self.del_btn]
        for b in all_btns:
            b.hidden = (b not in btns)
        n = len(btns)
        if n == 0:
            self.width = 60
            self.height = 54
            return
        w = self.PAD * 2 + n * self.BTN + (n - 1) * self.GAP
        h = self.PAD * 2 + self.BTN
        self.width = w
        self.height = h
        x = self.PAD
        for b in btns:
            b.frame = (x, self.PAD, self.BTN, self.BTN)
            x += self.BTN + self.GAP

    def present_for_tile(self, tile):
        self.tile = tile
        self.layout()
        self._position_near_tile(tile)
        self.bring_to_front()

    def _position_near_tile(self, tile):
        bx, by, bw, bh = tile.frame
        pw, ph = self.width, self.height
        gap = 4
        candidates = [
            (bx + (bw - pw) / 2, by - ph - gap),
            (bx + (bw - pw) / 2, by + bh + gap),
            (bx + bw + gap, by + (bh - ph) / 2),
            (bx - pw - gap, by + (bh - ph) / 2),
        ]
        board_w, board_h = self.board.width, self.board.height
        chosen = None
        for x, y in candidates:
            if x >= PADDING and y >= PADDING and x + pw <= board_w - PADDING and y + ph <= board_h - PADDING:
                chosen = (x, y)
                break
        if not chosen:
            x, y = candidates[0]
            x = clamp(x, PADDING, board_w - pw - PADDING)
            y = clamp(y, PADDING, board_h - ph - PADDING)
            chosen = (x, y)
        self.x, self.y = chosen

    def _on_alt(self, sender):
        if not self.tile:
            return
        kind = getattr(self.tile, 'kind', '')
        expr = getattr(self.tile, 'expr_str', '').strip()
        try:
            if kind == 'op' and expr == '-':
                self.board.save_state()
                self.tile.kind = 'negate'
                self.tile.expr_str = '±'
                self.tile.set_label('±')
                self.tile.set_tile_color('#F87171')
                try:
                    self.tile.label.text_color = '#FFFFFF'
                except:
                    pass
            elif kind == 'op' and expr == '/':
                self.board.convert_to_fraction(self.tile)
            elif kind == 'negate':
                self.board.save_state()
                self.tile.kind = 'op'
                self.tile.expr_str = '-'
                self.tile.set_label('-')
                self.tile.set_tile_color('#6B9FFF')
                try:
                    self.tile.label.text_color = '#FFFFFF'
                except:
                    pass
            elif kind == 'fraction':
                self.board.convert_from_fraction(self.tile)
            elif kind == 'expr':
                self.board.save_state()
                self.tile.kind = 'subst'
                self.tile.subst_val = None
                self.tile.expr_str = 'x='
                self.tile.set_label('x=')
                self.tile.set_tile_color('#A78BFA')
                try:
                    self.tile.label.text_color = '#FFFFFF'
                except:
                    pass
            elif kind == 'subst':
                self.board.save_state()
                self.tile.kind = 'expr'
                self.tile.subst_val = None
                self.tile.expr_str = 'x'
                self.tile.set_label('x')
                self.tile.set_tile_color('#7ED6A8')
                try:
                    self.tile.label.text_color = '#000000'
                except:
                    pass
            elif kind == 'split':
                self.board.save_state()
                self.tile.kind = 'supersplit'
                self.tile.expr_str = '✂✂'
                self.tile.set_label('✂✂')
                self.tile.set_tile_color('#E879A0')
                try:
                    self.tile.label.text_color = '#FFFFFF'
                except:
                    pass
            elif kind == 'supersplit':
                self.board.save_state()
                self.tile.kind = 'split'
                self.tile.expr_str = '✂'
                self.tile.set_label('✂')
                self.tile.set_tile_color('#FDA4AF')
                try:
                    self.tile.label.text_color = '#FFFFFF'
                except:
                    pass
            self.board.dismiss_editor()
        except Exception as e:
            print('Alt error:', e)

    def _on_sd(self, sender):
        if not self.tile:
            return
        try:
            self.board.toggle_simple_decimal(self.tile)
            self.board.dismiss_editor()
        except Exception as e:
            print('S↔D error:', e)

    def _on_pin(self, sender):
        if not self.tile:
            return
        is_sticky = getattr(self.tile, '_sticky', False)
        self.tile._sticky = not is_sticky
        if self.tile._sticky:
            self.tile.border_width = 3
            self.tile.border_color = '#FFFFFF'
        else:
            self.tile.border_width = 0
            self.tile.border_color = None
        self.board.dismiss_editor()

    def _on_ungroup(self, sender):
        if not self.tile:
            return
        try:
            self.board.ungroup_tiles(self.tile)
            self.board.dismiss_editor()
        except Exception as e:
            print('Ungroup error:', e)

    def _on_delete(self, sender):
        if not self.tile:
            self.board.dismiss_editor()
            return
        self.board.delete_tile(self.tile)
