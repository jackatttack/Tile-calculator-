import ui

from constants import BG_COLOR, BUTTON_OFF_COLOR
from board import Board
from widgets import DraggableActionButton


class DragTestApp(ui.View):
    def __init__(self):
        super().__init__()
        self.background_color = BG_COLOR
        self.flex = 'WH'

        self.board = Board()
        self.board.on_state_changed = self.update_undo_button
        self.add_subview(self.board)

        self.undo_fab = DraggableActionButton('↶', '#6B9FFF', '#FFFFFF', on_tap=self._fab_undo, size=54)
        self.redo_fab = DraggableActionButton('↷', '#3A3A3C', '#FFFFFF', on_tap=self._fab_redo, size=54)
        self.add_subview(self.undo_fab)
        self.add_subview(self.redo_fab)

        self._fab_positions_set = False

    def _fab_undo(self):
        try:
            self.board.undo()
        except Exception as e:
            print('FAB undo error:', e)
        self.update_undo_button()
        self._update_redo_fab()

    def _fab_redo(self):
        try:
            self.board.redo()
        except Exception as e:
            print('FAB redo error:', e)
        self.update_undo_button()
        self._update_redo_fab()

    def _update_redo_fab(self):
        has_redo = bool(getattr(self.board, 'redo_history', []))
        self.redo_fab.background_color = '#6B9FFF' if has_redo else BUTTON_OFF_COLOR
        self.redo_fab.alpha = 1.0 if has_redo else 0.65

    def update_undo_button(self):
        has_history = bool(self.board.history)
        self.undo_fab.background_color = '#6B9FFF' if has_history else BUTTON_OFF_COLOR
        self.undo_fab.alpha = 1.0 if has_history else 0.65
        self._update_redo_fab()

    def layout(self):
        if not hasattr(self, 'board'):
            return
        w, h = self.width, self.height
        pad = 10
        self.board.frame = (pad, pad, w - 2 * pad, h - 2 * pad)

        if not self._fab_positions_set:
            self.undo_fab.x = self.board.x + 10
            self.undo_fab.y = self.board.y + 10
            self.redo_fab.x = self.undo_fab.x + self.undo_fab.width + 10
            self.redo_fab.y = self.undo_fab.y
            self._fab_positions_set = True

        self.update_undo_button()


def run_app():
    app = DragTestApp()
    app.present('fullscreen', hide_title_bar=False)


if __name__ == '__main__':
    run_app()
