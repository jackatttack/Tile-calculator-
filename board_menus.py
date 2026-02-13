import ui

from constants import BUTTON_OFF_COLOR, EDITOR_BG, EDITOR_BORDER, EDITOR_TEXT, GRID_SIZE, PADDING, TEXT_COLOR, TILE_SIZE
from ui_utils import clamp
from tile_models import Tile


class TrashBin(ui.View):
    def __init__(self):
        super().__init__()
        self.width = TILE_SIZE + 10
        self.height = TILE_SIZE + 10
        self.background_color = '#FF453A'
        self.corner_radius = 8
        self.flex = ''

        self._touch_start = None
        self._view_start = None
        self._dragged = False
        self._drag_threshold = 6

        self.label = ui.Label()
        self.label.text = '🗑'
        self.label.font = ('<System>', 28)
        self.label.alignment = ui.ALIGN_CENTER
        self.label.frame = (0, 0, self.width, self.height)
        self.add_subview(self.label)

    def layout(self):
        self.label.frame = (0, 0, self.width, self.height)

    def touch_began(self, touch):
        self.bring_to_front()
        p = self.superview
        if not p:
            return
        try:
            p.dismiss_editor()
        except:
            pass
        try:
            p.dismiss_board_context_menu()
        except:
            pass
        self._touch_start = get_point(touch, in_view=p)
        self._view_start = (self.x, self.y)
        self._dragged = False

    def touch_moved(self, touch):
        p = self.superview
        if not p:
            return
        cur = get_point(touch, in_view=p)
        sx, sy = pt_xy(self._touch_start)
        cx, cy = pt_xy(cur)
        dx = cx - sx
        dy = cy - sy
        if abs(dx) + abs(dy) > self._drag_threshold:
            self._dragged = True
        vx, vy = self._view_start
        self.x = clamp(vx + dx, PADDING, p.width - self.width - PADDING)
        self.y = clamp(vy + dy, PADDING, p.height - self.height - PADDING)

    def touch_ended(self, touch):
        if self._dragged:
            return
        board = self.superview
        if board is None:
            return
        existing = getattr(board, '_trash_menu', None)
        if existing is not None:
            try:
                board.remove_subview(existing)
            except:
                pass
            board._trash_menu = None
            return
        menu = TrashMenu(board)
        menu_x = clamp(self.x + (self.width - menu.width) / 2, PADDING, board.width - menu.width - PADDING)
        menu_y = clamp(self.y + menu.height + 8, PADDING, board.height - menu.height - PADDING)
        menu.x = menu_x
        menu.y = menu_y
        board.add_subview(menu)
        menu.bring_to_front()
        board._trash_menu = menu


class TrashMenu(ui.View):
    def __init__(self, board):
        super().__init__()
        self.board = board
        self.background_color = EDITOR_BG
        self.corner_radius = 10
        self.border_width = 1
        self.border_color = EDITOR_BORDER
        self.width = 170
        self.height = 96

        self.title = ui.Label()
        self.title.text = 'Trash'
        self.title.font = ('<System-Bold>', 13)
        self.title.text_color = EDITOR_TEXT
        self.title.alignment = ui.ALIGN_LEFT
        self.add_subview(self.title)

        self.clear_btn = ui.Button()
        self.clear_btn.title = 'Clear Board'
        self.clear_btn.font = ('<System-Bold>', 14)
        self.clear_btn.background_color = '#FF453A'
        self.clear_btn.tint_color = TEXT_COLOR
        self.clear_btn.corner_radius = 8
        self.clear_btn.action = self._on_clear
        self.add_subview(self.clear_btn)

        self.cancel_btn = ui.Button()
        self.cancel_btn.title = 'Cancel'
        self.cancel_btn.font = ('<System-Bold>', 14)
        self.cancel_btn.background_color = BUTTON_OFF_COLOR
        self.cancel_btn.tint_color = TEXT_COLOR
        self.cancel_btn.corner_radius = 8
        self.cancel_btn.action = self._on_cancel
        self.add_subview(self.cancel_btn)

    def layout(self):
        pad = 8
        y = 6
        self.title.frame = (pad, y, self.width - 2 * pad, 18)
        y += 22
        self.clear_btn.frame = (pad, y, self.width - 2 * pad, 34)
        y += 38
        self.cancel_btn.frame = (pad, y, self.width - 2 * pad, 28)

    def _dismiss(self):
        if self.superview is not None:
            try:
                self.superview.remove_subview(self)
            except:
                pass
        try:
            if getattr(self.board, '_trash_menu', None) is self:
                self.board._trash_menu = None
        except:
            pass

    def _on_clear(self, sender):
        try:
            self.board.clear_all_tiles()
        except:
            pass
        self._dismiss()

    def _on_cancel(self, sender):
        self._dismiss()


class BoardContextMenu(ui.View):
    """Scrollable board menu: Undo + a tap-to-spawn tile palette (rows of 2)."""
    def __init__(self, board):
        super().__init__()
        self.board = board
        self.background_color = EDITOR_BG
        self.corner_radius = 10
        self.border_width = 1
        self.border_color = EDITOR_BORDER
        self.width = 190
        self.height = 320

        self.scroll = ui.ScrollView()
        self.scroll.background_color = (0, 0, 0, 0)
        self.scroll.shows_vertical_scroll_indicator = True
        self.scroll.always_bounce_vertical = True
        self.add_subview(self.scroll)

        self.content = ui.View()
        self.content.background_color = (0, 0, 0, 0)
        self.scroll.add_subview(self.content)

        self.undo_btn = ui.Button()
        self.undo_btn.title = 'Undo'
        self.undo_btn.font = ('<System-Bold>', 14)
        self.undo_btn.background_color = '#6B9FFF'
        self.undo_btn.tint_color = '#FFFFFF'
        self.undo_btn.corner_radius = 8
        self.undo_btn.action = self._on_undo
        self.content.add_subview(self.undo_btn)

        self._palette_buttons = []
        self._build_palette()
        self._content_h = self.height

    def _build_palette(self):
        def add_btn(title, kind, bg, fg='#000000'):
            b = ui.Button()
            b.title = str(title)
            b.font = ('<System-Bold>', 16)
            b.background_color = bg
            b.tint_color = fg
            b.corner_radius = 8
            b.action = self._on_spawn
            b._spawn_token = str(title)
            b._spawn_kind = kind
            b._spawn_bg = bg
            b._spawn_fg = fg
            self.content.add_subview(b)
            self._palette_buttons.append(b)

        for i in range(10):
            add_btn(str(i), 'number', '#FFD60A', '#000000')
        for op in ['+', '-', '*', '/', '^']:
            add_btn(op, 'op', '#6B9FFF', '#FFFFFF')
        add_btn('.', 'number', '#FFB347', '#000000')
        add_btn('=', 'equals', '#C4B5FD', '#000000')
        add_btn('F', 'factor', '#C084FC', '#FFFFFF')
        add_btn('x', 'expr', '#7ED6A8', '#000000')
        add_btn('✂', 'split', '#FDA4AF', '#FFFFFF')

    def layout(self):
        self.scroll.frame = (0, 0, self.width, self.height)
        pad = 10
        y = 8

        self.undo_btn.frame = (pad, y, self.width - 2 * pad, 40)
        y += 48

        has_history = bool(getattr(self.board, 'history', None))
        self.undo_btn.enabled = has_history
        self.undo_btn.background_color = '#6B9FFF' if has_history else BUTTON_OFF_COLOR

        col_gap = 10
        row_gap = 10
        btn_w = (self.width - 2 * pad - col_gap) / 2
        btn_h = 40

        col = 0
        x = pad
        for b in self._palette_buttons:
            b.frame = (x, y, btn_w, btn_h)
            col += 1
            if col >= 2:
                col = 0
                x = pad
                y += btn_h + row_gap
            else:
                x += btn_w + col_gap

        self._content_h = max(y + 4, self.height + 1)
        self.content.frame = (0, 0, self.width, self._content_h)
        self.scroll.content_size = (self.width, self._content_h)

    def _spawn_tile_at_point(self, token, kind, bg, fg):
        pt = getattr(self.board, '_board_menu_spawn_point', None)
        if pt:
            px, py = pt
        else:
            px = self.x + self.width * 0.5
            py = self.y + self.height * 0.5
        t = Tile(self.board)
        self.board.add_subview(t)
        self.board.tiles.append(t)
        t.kind = kind
        t.expr_str = str(token)
        t.pending_op = None
        t.set_label(str(token))
        t.set_tile_color(bg)
        try:
            t.label.text_color = fg
        except:
            pass
        t.x = clamp(px - t.width / 2, PADDING, self.board.width - t.width - PADDING)
        t.y = clamp(py - t.height / 2, PADDING, self.board.height - t.height - PADDING)
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

    def _on_spawn(self, sender):
        try:
            self.board.save_state()
        except:
            pass
        self._spawn_tile_at_point(sender._spawn_token, sender._spawn_kind, sender._spawn_bg, sender._spawn_fg)
        self.board.dismiss_board_context_menu()

    def _on_undo(self, sender):
        self.board.undo()
        self.board.dismiss_board_context_menu()
        if self.board.on_state_changed:
            try:
                self.board.on_state_changed()
            except:
                pass
