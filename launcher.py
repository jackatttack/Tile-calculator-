import ui
from board import Board
from tile import Tile
from keyboard import Keyboard



class App(ui.View):
    def __init__(self):
            super().__init__()

            GRID_SIZE = 60

            self.name = "Tile Calc Prototype"
            self.background_color = "#1C1C1E"

            self.bottom_inset = 16
            self.side_pad = 12
            self.top_pad = 12

            self.board = Board(frame=(0, 0, 10, 10), grid=GRID_SIZE, padding=12)
            self.add_subview(self.board)

            self.kb = Keyboard(self.board, frame=(0, 0, 10, 10))
            self.add_subview(self.kb)

            from delete_bin import DeleteBin
            self.delete_bin = DeleteBin(self.board)
            self.add_subview(self.delete_bin)

            self.board.add_tile(self.board.create_tile_from_spec(
                {'text': '1', 'kind': 'number', 'color': '#FFD60A', 'expr_str': '1', 'display': '1'}
            ), center=(160, 160))
            self.board.add_tile(self.board.create_tile_from_spec(
                {'text': '2', 'kind': 'number', 'color': '#FFD60A', 'expr_str': '2', 'display': '2'}
            ), center=(220, 160))
    
    def layout(self):
            w, h = self.width, self.height

            kb_h = self.kb.preferred_height
            kb_y = h - kb_h - self.bottom_inset

            self.board.frame = (self.side_pad, self.top_pad, w - self.side_pad * 2, h - self.top_pad)
            self.kb.frame = (0, kb_y, w, kb_h)

            keyboard_top_in_board = self.kb.y - self.board.y
            keyboard_top_in_board = max(0, min(self.board.height, keyboard_top_in_board))
            try:
                self.board.set_exclusion_bottom_y(keyboard_top_in_board)
            except Exception:
                pass

            self.delete_bin.position_in_parent(self.board)
    
    
def main():
    v = App()
    v.present("fullscreen")


if __name__ == "__main__":
    main()
