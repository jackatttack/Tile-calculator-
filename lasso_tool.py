import ui

class LassoOverlay(ui.View):
    def __init__(self):
        super().__init__(frame=(0, 0, 10, 10))
        self.background_color = (0, 0, 0, 0)
        self.user_interaction_enabled = False
        self._rect = None  # (x, y, w, h)

    def set_rect(self, rect):
        self._rect = rect
        self.set_needs_display()

    def clear(self):
        self._rect = None
        self.set_needs_display()

    def draw(self):
        r = self._rect
        if not r:
            return
        x, y, w, h = r
        if w < 0:
            x, w = x + w, -w
        if h < 0:
            y, h = y + h, -h

        ui.set_color((0.55, 0.70, 1.00, 0.12))
        ui.Path.rect(x, y, w, h).fill()

        ui.set_color((0.55, 0.70, 1.00, 0.70))
        p = ui.Path.rect(x, y, w, h)
        p.line_width = 2
        p.stroke()


class LassoTool:
    """
    Owns lasso state + overlay.
    TouchHandler decides when to call begin/update/end/cancel.
    """
    def __init__(self, board):
        self.board = board
        self.active = False
        self.locked = False
        self.start = None
        self.current = None
        self.rect = None
        self.selected_tiles = []

        self.overlay = LassoOverlay()
        self.overlay.frame = board.bounds
        self.overlay.user_interaction_enabled = False
        board.add_subview(self.overlay)
        try:
            self.overlay.send_to_back()
        except Exception:
            pass

    def _rect_from_points(self, a, b):
        ax, ay = a
        bx, by = b
        return (ax, ay, bx - ax, by - ay)

    def _normalize_rect(self, r):
        x, y, w, h = r
        if w < 0:
            x, w = x + w, -w
        if h < 0:
            y, h = y + h, -h
        return (x, y, w, h)

    def begin(self, p):
        # Ensure overlay exists (it may have been removed after previous selection)
        if getattr(self, 'overlay', None) is None or getattr(self.overlay, 'superview', None) is None:
            try:
                self.overlay = LassoOverlay()
                self.overlay.frame = self.board.bounds
                self.overlay.user_interaction_enabled = False
                self.board.add_subview(self.overlay)
            except Exception:
                pass

        self.active = True
        self.locked = False
        self.start = p
        self.current = p
        self.rect = self._rect_from_points(self.start, self.current)
        try:
            self.overlay.frame = self.board.bounds
            self.overlay.set_rect(self.rect)
        except Exception:
            pass

    def update(self, p):
        if not self.active or self.locked:
            return
        self.current = p
        self.rect = self._rect_from_points(self.start, self.current)
        self.overlay.set_rect(self.rect)

    def end(self):
        if not self.active:
            return
        self.active = False
        self.locked = True

        r = self._normalize_rect(self.rect or (0, 0, 0, 0))
        self.selected_tiles = self._tiles_in_rect(r)

        # Persist selection on the board, then tear down lasso visuals completely.
        try:
            self.board.set_lasso_selection(self.selected_tiles)
        except Exception:
            pass

        # Remove overlay so it cannot interfere with touch routing.
        try:
            if getattr(self, 'overlay', None) is not None and self.overlay.superview is not None:
                self.overlay.superview.remove_subview(self.overlay)
        except Exception:
            pass

        # Clear internal lasso state (selection now lives on board.lasso_selected_tiles)
        self.locked = False
        self.start = None
        self.current = None
        self.rect = None

        print(f"[LASSO] selected {len(self.selected_tiles)} tiles (overlay removed)")

    def cancel(self):
        self.active = False
        self.locked = False
        self.start = None
        self.current = None
        self.rect = None
        self.selected_tiles = []
        self.overlay.clear()
        try:
            self.overlay.send_to_back()
        except Exception:
            pass
        print("[LASSO] cancelled")

    def _tiles_in_rect(self, r):
        x, y, w, h = r
        x2 = x + w
        y2 = y + h
        hits = []
        for t in getattr(self.board, 'tiles', []):
            try:
                f = t.frame
                if (f.x < x2 and (f.x + f.width) > x and
                    f.y < y2 and (f.y + f.height) > y):
                    hits.append(t)
            except Exception:
                pass
        return hits
