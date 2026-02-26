import ui


class SettingsMenu(ui.View):
    """
    Dropdown menu triggered by gear icon.
    Anchors to top-right of board.
    """

    ITEMS = [
        ('🎨', 'Colors', 'colors'),
    ]

    def __init__(self, board, on_select):
        self.board = board
        self.on_select = on_select

        item_h = 44
        w = 140
        h = len(self.ITEMS) * item_h + 8

        super().__init__(frame=(0, 0, w, h))
        self.background_color = '#1C1C1E'
        self.corner_radius = 10
        self.border_width = 1
        self.border_color = '#3A3A3C'
        self.alpha = 0.97

        for i, (icon, label, action) in enumerate(self.ITEMS):
            row = ui.View(frame=(4, 4 + i * item_h, w - 8, item_h))
            row.background_color = 'clear'
            row.corner_radius = 8
            row.name = action

            icon_lbl = ui.Label(frame=(8, 0, 28, item_h))
            icon_lbl.text = icon
            icon_lbl.font = ('<System>', 18)
            icon_lbl.alignment = ui.ALIGN_CENTER
            icon_lbl.touch_enabled = False

            text_lbl = ui.Label(frame=(40, 0, w - 52, item_h))
            text_lbl.text = label
            text_lbl.font = ('<System>', 15)
            text_lbl.text_color = '#FFFFFF'
            text_lbl.alignment = ui.ALIGN_LEFT
            text_lbl.touch_enabled = False

            row.add_subview(icon_lbl)
            row.add_subview(text_lbl)

            # Capture action for closure
            def make_touch(a=action):
                def touch_ended(touch):
                    self.dismiss()
                    # Delay to next UI tick so the menu's touch doesn't pollute the next panel's touch coords
                    ui.delay(lambda: self.on_select(a), 0)
                return touch_ended

            row.touch_ended = make_touch()
            self.add_subview(row)

        self._position()

    def _position(self):
        board = self.board
        gear_size = 36
        margin = 8
        x = board.width - self.width - margin
        y = margin + gear_size + 4
        self.frame = (x, y, self.width, self.height)

    def dismiss(self):
        try:
            if self.superview:
                self.superview.remove_subview(self)
        except Exception:
            pass


class GearButton(ui.View):
    """
    Gear icon button — sits top-right of board permanently.
    """
    def __init__(self, board, on_tap):
        size = 36
        margin = 8
        super().__init__(frame=(board.width - size - margin, margin, size, size))
        self.board = board
        self.on_tap = on_tap
        self.background_color = '#2C2C2E'
        self.corner_radius = 10
        self.border_width = 1
        self.border_color = '#3A3A3C'
        self.alpha = 0.9

        lbl = ui.Label(frame=(0, 0, size, size))
        lbl.text = '⚙️'
        lbl.font = ('<System>', 18)
        lbl.alignment = ui.ALIGN_CENTER
        lbl.touch_enabled = False
        self.add_subview(lbl)

    def touch_ended(self, touch):
        self.on_tap()
