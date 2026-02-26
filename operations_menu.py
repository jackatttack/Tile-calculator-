import ui


class OperationsMenu(ui.View):
    """
    Operations menu - appears to the left of tile.
    Shows: +, -, ×, ^, ÷ in 2 columns
    """
    
    ITEM_SIZE = 36  # Smaller buttons
    PADDING = 4
    CORNER = 8
    BG = '#1C1C1E'
    ITEM_BG = '#2C2C2E'
    ITEM_ACTIVE = '#3A3A3C'
    
    def __init__(self, tile, board, **kwargs):
        super().__init__(**kwargs)
        self.tile = tile
        self.board = board
        self._buttons = []
        self._highlighted_button = None
        
        from tile_menu import _get_current_armed_op, _action_arm_op
        
        current_op = _get_current_armed_op(tile)
        
        ops = [
            ('+', '+', '+'),
            ('-', '-', '-'),
            ('×', '*', '×'),
            ('^', '^', '^'),
            ('÷', '/', '÷'),
        ]
        
        # 2 columns, 3 rows
        cols = 2
        rows = 3  # Ceil(5/2)
        
        total_w = cols * self.ITEM_SIZE + (cols + 1) * self.PADDING
        total_h = rows * self.ITEM_SIZE + (rows + 1) * self.PADDING
        
        self.frame = (0, 0, total_w, total_h)
        self.background_color = self.BG
        self.corner_radius = self.CORNER
        self.border_width = 1
        self.border_color = '#3A3A3C'
        
        try:
            self.touch_enabled = True
        except Exception:
            pass
        
        # Build buttons in 2-column grid
        for i, (icon, op, op_disp) in enumerate(ops):
            col = i % 2
            row = i // 2
            
            x = self.PADDING + col * (self.ITEM_SIZE + self.PADDING)
            y = self.PADDING + row * (self.ITEM_SIZE + self.PADDING)
            
            btn = ui.Button(frame=(x, y, self.ITEM_SIZE, self.ITEM_SIZE))
            btn.title = icon
            btn.font = ('<System>', 18)
            
            is_armed = (current_op == op)
            btn.background_color = self.ITEM_ACTIVE if is_armed else self.ITEM_BG
            btn.tint_color = '#FFFFFF'
            btn.corner_radius = 6
            btn.border_width = 0
            
            def make_handler(operation, operation_display):
                def handler(sender):
                    print(f"[OPS_MENU] arm op {operation}")
                    self.dismiss()
                    try:
                        _action_arm_op(self.tile, self.board, operation, operation_display)
                    except Exception as e:
                        print(f"[OPS_MENU_ERROR] {e}")
                return handler
            
            btn.action = make_handler(op, op_disp)
            btn._menu_action = btn.action
            self.add_subview(btn)
            self._buttons.append(btn)
        
        self._position_to_left_of_tile()
    
    def _position_to_left_of_tile(self):
            tile = self.tile
            board = self.board
            tx, ty = tile.frame.x, tile.frame.y

            x = tx - self.width - 8
            y = ty

            # If would go off left edge, position BELOW tile instead
            if x < 4:
                x = tx
                y = ty + tile.frame.height + 8

            # Clamp
            x = max(4, min(x, board.width - self.width - 4))
            y = max(4, min(y, board.height - self.height - 4))

            self.frame = (x, y, self.width, self.height)
            print(f"[OPS_MENU] positioned at ({x:.0f}, {y:.0f})")
    
    def highlight_at_point(self, x, y):
        """Highlight button at menu-relative coords (x, y)."""
        new_highlight = None
        for btn in self._buttons:
            try:
                bx, by, bw, bh = btn.frame
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    new_highlight = btn
                    break
            except Exception:
                pass
        
        if new_highlight != self._highlighted_button:
            if self._highlighted_button:
                try:
                    self._highlighted_button.background_color = self.ITEM_BG
                except Exception:
                    pass
            
            self._highlighted_button = new_highlight
            if self._highlighted_button:
                try:
                    self._highlighted_button.background_color = '#5A5A5C'
                    print(f"[OPS_MENU_HIGHLIGHT] {self._highlighted_button.title}")
                except Exception:
                    pass
    
    def get_highlighted_action(self):
        """Return the action callback for highlighted button, or None."""
        if self._highlighted_button:
            return getattr(self._highlighted_button, '_menu_action', None)
        return None
    
    def dismiss(self):
        print(f"[OPS_MENU] dismissing")
        self._highlighted_button = None
        try:
            if self.superview:
                self.superview.remove_subview(self)
        except Exception as e:
            print(f"[OPS_MENU_DISMISS_ERROR] {e}")
    
    def touch_began(self, touch):
        pass
    
    def touch_moved(self, touch):
        pass
    
    def touch_ended(self, touch):
        pass


