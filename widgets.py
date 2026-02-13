import ui

from constants import BUTTON_COLOR, BUTTON_OFF_COLOR, TEXT_COLOR
from ui_utils import clamp, get_point, pt_xy


def ToggleButton(title, on_toggle):
    btn = ui.Button()
    btn.title = title
    btn.is_on = True
    btn.on_toggle = on_toggle
    btn.corner_radius = 8
    btn.font = ('<System-Bold>', 14)
    btn.background_color = BUTTON_COLOR
    btn.tint_color = TEXT_COLOR

    def toggle_action(sender):
        sender.is_on = not sender.is_on
        sender.background_color = BUTTON_COLOR if sender.is_on else BUTTON_OFF_COLOR
        if sender.on_toggle:
            sender.on_toggle(sender.is_on)

    btn.action = toggle_action
    return btn


class DraggableActionButton(ui.View):
    """
    A draggable, tappable floating button.
    - Tap (no drag) calls on_tap()
    - Drag moves it around the parent view
    """
    def __init__(self, title, bg, fg, on_tap=None, size=52):
        super().__init__()
        self.width = size
        self.height = size
        self.corner_radius = 14
        self.background_color = bg
        self.flex = ''
        self.on_tap = on_tap

        self._touch_start = None
        self._view_start = None
        self._dragged = False
        self._drag_threshold = 6

        self.lbl = ui.Label()
        self.lbl.text = title
        self.lbl.font = ('<System-Bold>', 20)
        self.lbl.text_color = fg
        self.lbl.alignment = ui.ALIGN_CENTER
        self.add_subview(self.lbl)

    def layout(self):
        self.lbl.frame = (0, 0, self.width, self.height)

    def _clamp_to_parent(self):
        p = self.superview
        if not p:
            return
        self.x = clamp(self.x, 0, p.width - self.width)
        self.y = clamp(self.y, 0, p.height - self.height)

    def touch_began(self, touch):
        self.bring_to_front()
        self._touch_start = get_point(touch, in_view=self.superview) if self.superview else get_point(touch, in_view=self)
        self._view_start = (self.x, self.y)
        self._dragged = False

    def touch_moved(self, touch):
        if not self.superview:
            return
        cur = get_point(touch, in_view=self.superview)
        sx, sy = pt_xy(self._touch_start)
        cx, cy = pt_xy(cur)
        dx = cx - sx
        dy = cy - sy
        if abs(dx) + abs(dy) > self._drag_threshold:
            self._dragged = True

        vx, vy = self._view_start
        self.x = vx + dx
        self.y = vy + dy
        self._clamp_to_parent()

    def touch_ended(self, touch):
        if not self._dragged and self.on_tap:
            try:
                self.on_tap()
            except Exception as e:
                print('ActionButton tap error:', e)
