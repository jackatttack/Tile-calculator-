REPLACE tile.py::Tile._ensure_fraction_views
    def _ensure_fraction_views(self):
        if self._frac_numer is not None:
            return

        if not hasattr(self, 'content_view') or self.content_view is None:
            self.content_view = ui.View(frame=self.bounds)
            self.content_view.flex = 'WH'
            self.content_view.background_color = 'clear'
            self.content_view.corner_radius = 0
            try:
                self.content_view.touch_enabled = False
            except Exception:
                pass
            self.add_subview(self.content_view)
REPLACE tile.py::Tile.kind.setter
    @kind.setter
    def kind(self, v):
        self.data.kind = v
        new_color = KIND_COLORS.get(v)
        if new_color:
            self.base_color = new_color
            self.drag_color = _darker(new_color, 0.80)
        self._refresh_mode()
        try:
            self.set_needs_display()
        except Exception:
            pass
            
            
REPLACE tile.py::Tile.set_dragging
    def set_dragging(self, on):
        self._dragging = bool(on)
        try:
            self.set_needs_display()
        except Exception:
            pass
        try:
            if self.superview:
                self.superview.set_needs_display()
        except Exception:
            pass



