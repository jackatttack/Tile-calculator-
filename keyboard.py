import ui
from tile import Tile


class KeyboardItem(ui.View):
    DRAG_THRESHOLD = 10

    def __init__(self, board, spec, size):
        super().__init__(frame=(0, 0, size, size))
        self.board = board
        self.spec = dict(spec or {})
        self.size = float(size)

        self._spawned_tile = None
        self._dragging = False
        self._moved = False
        self._start = (0.0, 0.0)

        display_kind = 'op' if self.spec.get('spawn_kind') == 'fraction' else self.spec.get('kind', 'generic')

        preview = Tile(
            text=self.spec.get('text', '?'),
            kind=display_kind,
            color=self.spec.get('color', '#FFD60A'),
            cell_size=int(size),
            w_cells=1,
            h_cells=1,
            gutter=4,
        )
        try:
            preview.touch_enabled = False
        except Exception:
            pass

        preview.frame = (0, 0, size, size)
        preview._fixed_size = True
        self.add_subview(preview)
        self.preview = preview

    # ----------------------------
    # Touch coordinate helpers
    # ----------------------------

    @staticmethod
    def _xy(loc):
        try:
            return float(loc.x), float(loc.y)
        except Exception:
            return float(loc[0]), float(loc[1])

    @staticmethod
    def _abs_origin(view):
        ax, ay = 0.0, 0.0
        v = view
        while v is not None:
            ax += float(getattr(v, 'x', 0.0))
            ay += float(getattr(v, 'y', 0.0))
            v = getattr(v, 'superview', None)
        return ax, ay

    def _board_point_from_touch(self, touch):
        lx, ly = self._xy(touch.location)
        sx, sy = self._abs_origin(self)
        bx, by = self._abs_origin(self.board)
        return (sx + lx - bx, sy + ly - by)

    # ----------------------------
    # Touch events
    # ----------------------------

    def touch_began(self, touch):
        self._start = self._xy(touch.location)
        self._moved = False
        self._dragging = False
        self._spawned_tile = None

    def touch_moved(self, touch):
        px, py = self._xy(touch.location)
        sx, sy = self._start
        dx = px - sx
        dy = py - sy

        if (not self._dragging) and ((dx * dx + dy * dy) > (self.DRAG_THRESHOLD ** 2)):
            self._dragging = True
            bp = self._board_point_from_touch(touch)
            t = self.board.create_tile_from_spec(self.spec)
            self.board.add_tile(t, center=bp, snap=False)
            self.board.begin_drag_tile(t, point=bp)
            self._spawned_tile = t

        if self._dragging and self._spawned_tile is not None:
            bp = self._board_point_from_touch(touch)
            self.board.drag_tile_to_point(self._spawned_tile, point=bp)
            self._moved = True

    def touch_ended(self, touch):
        if (not self._moved) and (not self._dragging):
            self._tap_spawn()
            return

        if self._spawned_tile is not None:
            self.board.end_drag_tile(self._spawned_tile)

        self._spawned_tile = None
        self._dragging = False

    # ----------------------------
    # Tap spawn / typing logic
    # ----------------------------

    def _tap_spawn(self):
        board = self.board

        spec_kind = self.spec.get('kind', '')
        spec_expr = self.spec.get('expr_str', '')
        is_frac_key = (self.spec.get('spawn_kind') == 'fraction')

        def _apply_pending_neg(tile):
            try:
                if getattr(board, '_keyboard_pending_neg', False):
                    # A little defensive: some togglers inspect meta['neg']
                    try:
                        m = getattr(tile.data, 'meta', {}) or {}
                        m['neg'] = False
                    except Exception:
                        pass

                    try:
                        board._handle_toggle_tile(tile)
                    except Exception:
                        try:
                            tile.data.meta['neg'] = True
                        except Exception:
                            pass

                    board._keyboard_pending_neg = False
            except Exception:
                pass

        # ------------------------------------------------------------
        # Fraction mode typing (denominator editing)
        # ------------------------------------------------------------
        if getattr(board, '_keyboard_frac_mode', False):
            if spec_kind == 'op':
                board._close_frac_mode()
                return

            denom = getattr(board, '_keyboard_denom_tile', None)
            new_tile = board.create_tile_from_spec(self.spec)
            _apply_pending_neg(new_tile)

            if denom is None:
                board._keyboard_denom_tile = new_tile
                board._sync_denom_to_frac()
                board._capture_undo_snapshot()
                return

            ctx = {
                'board': board,
                'spawn_direction': 'right',
                'return_direction': 'left',
            }
            res = board.merge_engine.try_merge(new_tile, denom, ctx)
            if res is None:
                print("[FRAC_MODE] denom merge failed, ignoring key")
                return

            replace = getattr(res, 'replace_tile', None)
            if replace is denom:
                if getattr(res, 'new_display', None) is not None:
                    try:
                        denom.set_label(res.new_display)
                    except Exception:
                        denom.text = res.new_display
                    try:
                        denom.data.display = res.new_display
                    except Exception:
                        pass
                if getattr(res, 'new_expr_str', None) is not None:
                    try:
                        denom.expr_str = res.new_expr_str
                    except Exception:
                        pass

            board._sync_denom_to_frac()
            board._capture_undo_snapshot()
            return

        # ------------------------------------------------------------
        # Resolve active tile (typing target)
        # ------------------------------------------------------------
        active = getattr(board, '_keyboard_active_tile', None)
        if active is not None:
            try:
                if active not in board.tiles or active.superview is None:
                    active = None
                    board._keyboard_active_tile = None
            except Exception:
                active = None
                board._keyboard_active_tile = None

         #MINUS KEY - arm subtract on active, or pend neg if no active
        # ------------------------------------------------------------
        if spec_kind == 'op' and str(spec_expr) == '-':
            if active is not None:
                # Arm active tile with subtract so next typed tile subtracts
                board._capture_undo_snapshot()
                try:
                    from tile_menu import _action_arm_op
                    _action_arm_op(active, board, '-', '-')
                except Exception as e:
                    print(f"[KB_MINUS_ARM_ERROR] {e}")
                board.select_tile(active)
                board._keyboard_active_tile = active
                board._capture_undo_snapshot()
                print(f"[KB_MINUS] armed subtract on active -> {getattr(active,'tile_id','?')[:6]}")
            else:
                try:
                    board._keyboard_pending_neg = True
                except Exception:
                    pass
                board._capture_undo_snapshot()
                print("[KB_MINUS] armed pending neg for next tile")
            return
         #------------------------------------------------------------
        # MINUS KEY - negate active or arm pending neg
        # ------------------------------------------------------------
        
        
        '''
        if spec_kind == 'op' and str(spec_expr) == '-':
            if active is not None:
                board._capture_undo_snapshot()
                try:
                    board._handle_toggle_tile(active)
                except Exception as e:
                    print(f"[KB_NEG_TOGGLE_ERROR] {e}")
                try:
                    board.select_tile(active)
                except Exception:
                    pass
                board._keyboard_active_tile = active
                board._capture_undo_snapshot()
                try:
                    print(f"[KB_NEG] toggled active -> {getattr(active, 'tile_id', '?')[:6]}")
                except Exception:
                    print("[KB_NEG] toggled active")
            else:
                try:
                    board._keyboard_pending_neg = True
                except Exception:
                    pass
                board._capture_undo_snapshot()
                print("[KB_NEG] armed pending neg for next tile")
            return'''

        # ------------------------------------------------------------
        # Fraction key
        # ------------------------------------------------------------
        if is_frac_key:
            if active is not None:
                board._capture_undo_snapshot()
                board._enter_frac_mode(active)
                board._capture_undo_snapshot()
                return

            new_tile = board.create_tile_from_spec(self.spec)
            _apply_pending_neg(new_tile)

            cx = board.width * 0.5
            cy = board.height * 0.5
            try:
                if board.exclusion_bottom_y is not None:
                    cy = min(cy, board.exclusion_bottom_y - board.grid)
            except Exception:
                pass

            board.add_tile(new_tile, center=(cx, cy), snap=True)
            board.select_tile(new_tile)
            board._keyboard_active_tile = new_tile
            board._capture_undo_snapshot()
            return

        # ------------------------------------------------------------
        # Typing into an existing active tile (merge)
        # ------------------------------------------------------------
        if active is not None:
            new_tile = board.create_tile_from_spec(self.spec)
            _apply_pending_neg(new_tile)

            ctx = {
                'board': board,
                'spawn_direction': 'right',
                'return_direction': 'left',
            }
            res = board.merge_engine.try_merge(new_tile, active, ctx)
            if res is not None:
                board._capture_undo_snapshot()
                merged = board._apply_merge_result(res, dragged=new_tile, target=active)
                if merged:
                    result_tile = getattr(res, 'replace_tile', None) or active
                    board._keyboard_active_tile = result_tile
                    board.select_tile(result_tile)
                    try:
                        print(f"[KB_TYPING] merged -> active={result_tile.tile_id[:6]}")
                    except Exception:
                        print("[KB_TYPING] merged -> active")
                    return

        # ------------------------------------------------------------
        # Spawn fresh tile
        # ------------------------------------------------------------
        new_tile = board.create_tile_from_spec(self.spec)
        _apply_pending_neg(new_tile)

        cx = board.width * 0.5
        cy = board.height * 0.5
        try:
            if board.exclusion_bottom_y is not None:
                cy = min(cy, board.exclusion_bottom_y - board.grid)
        except Exception:
            pass

        board.add_tile(new_tile, center=(cx, cy), snap=True)
        board.select_tile(new_tile)
        board._keyboard_active_tile = new_tile
        board._capture_undo_snapshot()
        try:
            print(f"[KB_TYPING] spawned fresh -> active={new_tile.tile_id[:6]}")
        except Exception:
            print("[KB_TYPING] spawned fresh -> active")


class Keyboard(ui.View):
    GAP = 4
    SIDE_PAD = 6
    TOP_PAD = 6
    INDICATOR_H = 26
    INDICATOR_GAP = 6
    BOTTOM_PAD = 4
    KEY_SCALE = 0.82
    SWIPE_THRESHOLD = 40

    PAGES = [
        {
            'label': '123',
            'rows': [
                [
                    {'text': 'x',    'kind': 'expr',       'color': '#D198B7', 'expr_str': 'x',         'display': 'x'},
                    {'text': 'pi',   'kind': 'irrational', 'color': '#FF8C42', 'expr_str': 'pi',        'display': 'pi',
                     '_meta': {'exact_expr': 'pi', 'showing_decimal': False}},
                    {'text': 'fact', 'kind': 'tool',       'color': '#80EF80', 'expr_str': 'factor',    'display': 'fact'},
                    {'text': 'rand', 'kind': 'tool',       'color': '#80EF80', 'expr_str': 'random',    'display': 'rand'},
                    {'text': 'sqrt', 'kind': 'tool',       'color': '#80EF80', 'expr_str': 'sqrt',      'display': 'sqrt'},
                ],
                [
                    {'text': '7',  'kind': 'number', 'color': '#FFD60A', 'expr_str': '7',  'display': '7'},
                    {'text': '8',  'kind': 'number', 'color': '#FFD60A', 'expr_str': '8',  'display': '8'},
                    {'text': '9',  'kind': 'number', 'color': '#FFD60A', 'expr_str': '9',  'display': '9'},
                    {'text': '+',  'kind': 'op',     'color': '#AEC6CF', 'expr_str': '+',  'display': '+'},
                    {'text': '-',  'kind': 'op',     'color': '#AEC6CF', 'expr_str': '-',  'display': '-'},
                ],
                [
                    {'text': '4',  'kind': 'number', 'color': '#FFD60A', 'expr_str': '4',  'display': '4'},
                    {'text': '5',  'kind': 'number', 'color': '#FFD60A', 'expr_str': '5',  'display': '5'},
                    {'text': '6',  'kind': 'number', 'color': '#FFD60A', 'expr_str': '6',  'display': '6'},
                    {'text': 'x',  'kind': 'op',     'color': '#AEC6CF', 'expr_str': '*',  'display': 'x'},
                    {'text': '//', 'kind': 'op',     'color': '#AEC6CF', 'expr_str': '/',  'display': '//'},
                ],
                [
                    {'text': '1', 'kind': 'number', 'color': '#FFD60A', 'expr_str': '1', 'display': '1'},
                    {'text': '2', 'kind': 'number', 'color': '#FFD60A', 'expr_str': '2', 'display': '2'},
                    {'text': '3', 'kind': 'number', 'color': '#FFD60A', 'expr_str': '3', 'display': '3'},
                    {'text': '^', 'kind': 'op',     'color': '#AEC6CF', 'expr_str': '^', 'display': '^'},
                    {'text': '=', 'kind': 'eq',     'color': '#32ADE6', 'expr_str': '=', 'display': '='},
                ],
                [
                    {'text': '0', 'kind': 'number',     'color': '#FFD60A', 'expr_str': '0',         'display': '0'},
                    {'text': 'e', 'kind': 'irrational', 'color': '#FF8C42', 'expr_str': 'E',         'display': 'e',
                     '_meta': {'exact_expr': 'E', 'showing_decimal': False}},
                    {'text': 'log', 'kind': 'tool', 'color': '#80EF80', 'expr_str': 'log',       'display': 'log'},
                    {'text': 'ln',  'kind': 'tool', 'color': '#80EF80', 'expr_str': 'ln',        'display': 'ln'},
                    {'text': '!',   'kind': 'tool', 'color': '#80EF80', 'expr_str': 'factorial', 'display': '!'},
                ],
            ],
        },
        {
            'label': 'fn',
            'rows': [
                [
                    {'text': 'sin',  'kind': 'tool', 'color': '#80EF80', 'expr_str': 'sin',       'display': 'sin'},
                    {'text': 'cos',  'kind': 'tool', 'color': '#80EF80', 'expr_str': 'cos',       'display': 'cos'},
                    {'text': 'tan',  'kind': 'tool', 'color': '#80EF80', 'expr_str': 'tan',       'display': 'tan'},
                    {'text': 'int',  'kind': 'tool', 'color': '#80EF80', 'expr_str': 'integrate', 'display': 'int'},
                    {'text': 'd/dx', 'kind': 'tool', 'color': '#80EF80', 'expr_str': 'diff',      'display': 'd/dx'},
                ],
                [
                    {'text': '|x|', 'kind': 'tool', 'color': '#80EF80', 'expr_str': 'abs',    'display': '|x|'},
                    {'text': '+-',  'kind': 'tool', 'color': '#80EF80', 'expr_str': 'negate', 'display': '+-'},
                    {'text': '%',   'kind': 'op',   'color': '#AEC6CF', 'expr_str': '%',      'display': '%'},
                    {'text': 'sum', 'kind': 'tool', 'color': '#80EF80', 'expr_str': 'sum',    'display': 'sum'},
                    {'text': 'RAD', 'kind': 'tool', 'color': '#5E5CE6', 'expr_str': 'deg_rad','display': 'RAD'},
                ],
                [
                    {'text': '(',    'kind': 'op',   'color': '#64D2FF', 'expr_str': '(',            'display': '('},
                    {'text': ')',    'kind': 'op',   'color': '#64D2FF', 'expr_str': ')',            'display': ')'},
                    {'text': 'mod',  'kind': 'op',   'color': '#AEC6CF', 'expr_str': '%',            'display': 'mod'},
                    {'text': 'rand', 'kind': 'tool', 'color': '#80EF80', 'expr_str': 'random',       'display': 'rand'},
                    {'text': 'a-b',  'kind': 'tool', 'color': '#80EF80', 'expr_str': 'random_range', 'display': 'a-b'},
                ],
            ],
        },
    ]

    def __init__(self, board, **kwargs):
        super().__init__(**kwargs)
        self.board = board
        self.background_color = None
        self.current_page = 0

        self._key_items = []
        self._indicator_rects = []
        self._swipe_start = None
        self._swipe_active = False

    # ----------------------------
    # Height / layout
    # ----------------------------

    @property
    def preferred_height(self):
        try:
            return self._preferred_height()
        except Exception:
            return 0

    def _preferred_height(self):
        key_size = int(self.board.grid * self.KEY_SCALE)
        max_rows = max(len(pg['rows']) for pg in self.PAGES)
        return (
            self.TOP_PAD
            + self.INDICATOR_H
            + self.INDICATOR_GAP
            + max_rows * key_size
            + (max_rows - 1) * self.GAP
            + self.BOTTOM_PAD
        )

    def layout(self):
        self._rebuild_keys()

    def _rebuild_keys(self):
        for item in self._key_items:
            try:
                if item.superview:
                    self.remove_subview(item)
            except Exception:
                pass

        self._key_items = []
        self._indicator_rects = []

        key_size = int(self.board.grid * self.KEY_SCALE)
        page_data = self.PAGES[self.current_page]

        # Indicator pills
        n_pages = len(self.PAGES)
        pill_w = 36
        pill_gap = 8
        total_pill_w = n_pages * pill_w + (n_pages - 1) * pill_gap
        pill_x0 = (self.width - total_pill_w) / 2
        ind_y = self.TOP_PAD

        for i in range(n_pages):
            rx = pill_x0 + i * (pill_w + pill_gap)
            self._indicator_rects.append((i, (rx, ind_y, pill_w, self.INDICATOR_H)))

        keys_top = self.TOP_PAD + self.INDICATOR_H + self.INDICATOR_GAP

        for row_idx, row_specs in enumerate(page_data['rows']):
            n = len(row_specs)
            row_w = n * key_size + (n - 1) * self.GAP
            row_x0 = (self.width - row_w) / 2
            row_y = keys_top + row_idx * (key_size + self.GAP)

            for col_idx, spec in enumerate(row_specs):
                x = row_x0 + col_idx * (key_size + self.GAP)
                item = KeyboardItem(self.board, spec, size=key_size)
                item.frame = (x, row_y, key_size, key_size)
                self.add_subview(item)
                self._key_items.append(item)

        self.set_needs_display()

    # ----------------------------
    # Drawing
    # ----------------------------

    def draw(self):
        # Pills
        for page_idx, rect in self._indicator_rects:
            rx, ry, rw, rh = rect
            active = (page_idx == self.current_page)

            bg = '#3A3A3C' if active else '#2C2C2E'
            path = ui.Path.rounded_rect(rx, ry, rw, rh, 6)
            ui.set_color(bg)
            path.fill()

            label = self.PAGES[page_idx]['label']
            text_color = '#FFFFFF' if active else '#636366'
            ui.draw_string(
                label,
                rect=(rx, ry, rw, rh),
                font=('<System-Bold>', 12),
                color=text_color,
                alignment=ui.ALIGN_CENTER,
                line_break_mode=ui.LB_CLIP,
            )

        # Edge arrows
        n = len(self.PAGES)
        if n > 1:
            arrow_y = self.TOP_PAD
            arrow_h = self.INDICATOR_H
            if self.current_page > 0:
                ui.draw_string(
                    '<',
                    rect=(0, arrow_y, 20, arrow_h),
                    font=('<System-Bold>', 13),
                    color='#636366',
                    alignment=ui.ALIGN_CENTER,
                    line_break_mode=ui.LB_CLIP
                )
            if self.current_page < n - 1:
                ui.draw_string(
                    '>',
                    rect=(self.width - 20, arrow_y, 20, arrow_h),
                    font=('<System-Bold>', 13),
                    color='#636366',
                    alignment=ui.ALIGN_CENTER,
                    line_break_mode=ui.LB_CLIP
                )

    # ----------------------------
    # Swipe + tap on pills
    # ----------------------------

    @staticmethod
    def _xy(loc):
        try:
            return float(loc.x), float(loc.y)
        except Exception:
            return float(loc[0]), float(loc[1])

    def touch_began(self, touch):
        px, py = self._xy(touch.location)
        if py <= (self.TOP_PAD + self.INDICATOR_H):
            self._swipe_start = (px, py)
            self._swipe_active = False
        else:
            self._swipe_start = None
            self._swipe_active = False

    def touch_moved(self, touch):
        if self._swipe_start is None:
            return
        px, py = self._xy(touch.location)
        dx = px - self._swipe_start[0]
        dy = py - self._swipe_start[1]

        if (not self._swipe_active) and (abs(dx) > abs(dy)) and (abs(dx) > 10):
            self._swipe_active = True

    def touch_ended(self, touch):
        px, py = self._xy(touch.location)

        # Swipe
        if self._swipe_start is not None and self._swipe_active:
            dx = px - self._swipe_start[0]
            if abs(dx) >= self.SWIPE_THRESHOLD:
                n = len(self.PAGES)
                if dx < 0 and self.current_page < n - 1:
                    self.current_page += 1
                    self._rebuild_keys()
                elif dx > 0 and self.current_page > 0:
                    self.current_page -= 1
                    self._rebuild_keys()

                self._swipe_start = None
                self._swipe_active = False
                return

        self._swipe_start = None
        self._swipe_active = False

        # Tap pills
        for page_idx, rect in self._indicator_rects:
            rx, ry, rw, rh = rect
            if rx <= px <= rx + rw and ry <= py <= ry + rh:
                if page_idx != self.current_page:
                    self.current_page = page_idx
                    self._rebuild_keys()
                return


# Backwards compat
TileMenu = Keyboard
