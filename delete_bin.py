import ui
import threading


class DeleteBin(ui.View):
    """
    Fixed trash icon in top-right corner.
    - Drag tiles onto it to delete them
    - Long-press (0.4s) to clear all tiles with confirmation
    """
    
    SIZE = 50
    PADDING = 12
    BG_COLOR = '#FF453A'
    BG_HOVER = '#FF6961'
    
    def __init__(self, board, **kwargs):
        super().__init__(**kwargs)
        self.board = board
        self.background_color = self.BG_COLOR
        self.corner_radius = 12
        self.border_width = 2
        self.border_color = '#FFFFFF22'
        
        # Trash icon label
        self.label = ui.Label()
        self.label.text = '🗑️'
        self.label.font = ('<System>', 28)
        self.label.alignment = ui.ALIGN_CENTER
        self.label.frame = (0, 0, self.SIZE, self.SIZE)
        self.add_subview(self.label)
        
        # Long-press state
        self._long_press_timer = None
        self._long_press_start = None
        
        self.touch_enabled = True
    
    def position_in_parent(self, board):
        """Position in bottom-right corner of VISIBLE board area (above keyboard)."""
        # Don't position relative to full board height - use visible area
        app = board.superview
        if not app:
            return

        # Get keyboard position
        keyboard = getattr(app, 'kb', None)
        if not keyboard:
            # Fallback: bottom-right of board
            x = board.x + board.width - self.SIZE - self.PADDING
            y = board.y + board.height - self.SIZE - self.PADDING
        else:
            # Position just above keyboard, in bottom-right
            x = board.x + board.width - self.SIZE - self.PADDING
            y = keyboard.y - self.SIZE - self.PADDING

        self.frame = (x, y, self.SIZE, self.SIZE)
    def overlaps_tile(self, tile):
            """Check if tile's frame overlaps this bin (works for any tile size)."""
            try:
                board = self.board
                # Convert tile frame from board coords to app coords
                tx = tile.x + board.x
                ty = tile.y + board.y
                tw = tile.width
                th = tile.height

                # Axis-aligned bounding box overlap
                return (tx < self.x + self.width and
                        tx + tw > self.x and
                        ty < self.y + self.height and
                        ty + th > self.y)
            except Exception:
                return False
    
    def delete_tile(self, tile):
        """Delete a single tile."""
        try:
            self.board.remove_tile(tile)
            print(f"[DELETE_BIN] deleted tile {tile.tile_id[:6]}")
        except Exception as e:
            print(f"[DELETE_BIN_ERROR] {e}")
    
    def clear_all(self):
        """Delete all tiles on the board."""
        try:
            import console
            choice = console.alert(
                "Clear All",
                "Delete all tiles on the board?",
                "Clear All",
                "Cancel"
            )
            if choice == 1:
                tiles_copy = list(self.board.tiles)
                for tile in tiles_copy:
                    self.board.remove_tile(tile)
                print(f"[DELETE_BIN] cleared {len(tiles_copy)} tiles")
        except Exception as e:
            print(f"[DELETE_BIN_CLEAR_ERROR] {e}")
    
    def touch_began(self, touch):
        """Start long-press timer for clear-all."""
        self.background_color = self.BG_HOVER
        self._long_press_start = touch.location
        
        def fire():
            print("[DELETE_BIN] long press fired - clear all")
            self._long_press_timer = None
            self._long_press_start = None
            self.clear_all()
        
        self._long_press_timer = threading.Timer(0.4, fire)
        self._long_press_timer.start()
    
    def touch_moved(self, touch):
        """Cancel if moved too far."""
        if self._long_press_timer and self._long_press_start:
            p = touch.location
            dx = p[0] - self._long_press_start[0]
            dy = p[1] - self._long_press_start[1]
            dist = (dx*dx + dy*dy) ** 0.5
            if dist > 10:
                self._long_press_timer.cancel()
                self._long_press_timer = None
                self._long_press_start = None
    
    def touch_ended(self, touch):
        """Cancel timer, restore color."""
        if self._long_press_timer:
            self._long_press_timer.cancel()
            self._long_press_timer = None
            self._long_press_start = None
        self.background_color = self.BG_COLOR





