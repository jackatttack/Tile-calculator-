# settings_colors.py
# Fresh color settings implementation for Pythonista (no coordinate-math touch handling).
#
# Design goals:
# - Reliable taps (uses ui.Button actions, not manual hit-testing)
# - Works best as a modal sheet/popover (recommended)
# - Still provides a panel-style view you can add as a subview if you want
#
# Expected external APIs:
# - Tile.color_for_kind(kind)  (optional)
# - Tile.set_kind_color(kind, color) (optional)
# - Board.refresh_tile_colors() (optional)

import ui
from tile import Tile, KIND_COLORS


# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------

EDITABLE_KINDS = [
    ('number',     '7'),
    ('op',         '+'),
    ('expr',       'x²'),
    ('tool',       'sin'),
    ('fraction',   '½'),
    ('irrational', 'π'),
    ('eq',         '='),
]

TOOL_MIRROR_KINDS = ('tool', 'num_tool', 'expr_tool')

PALETTE = [
    '#FDFD96', '#FFD60A', '#FFE066', '#FFC300',
    '#FF9F0A', '#FF8C42', '#FF6B35', '#E55934',
    '#80EF80', '#34C759', '#30D158', '#5AC8FA',
    '#D198B7', '#BF5AF2', '#9B59B6', '#C77DFF',
    '#32ADE6', '#0A84FF', '#64D2FF', '#007AFF',
    '#AEC6CF', '#8E8E93', '#AEAEB2', '#FFFFFF',
]


# --------------------------------------------------------------------
# Helpers (safe across refactors)
# --------------------------------------------------------------------

def _get_kind_color(kind: str) -> str:
    # Prefer Tile API if available, else fall back to KIND_COLORS.
    try:
        return Tile.color_for_kind(kind)
    except Exception:
        return (KIND_COLORS.get(kind) or '#FFD60A')


def _set_kind_color(kind: str, color: str) -> None:
    # Prefer Tile API if available, else mutate KIND_COLORS dict.
    try:
        Tile.set_kind_color(kind, color)
        return
    except Exception:
        pass
    try:
        KIND_COLORS[kind] = color
    except Exception:
        pass


def _kinds_to_update(selected_kind: str):
    if selected_kind in TOOL_MIRROR_KINDS:
        return list(TOOL_MIRROR_KINDS)
    return [selected_kind]


# --------------------------------------------------------------------
# Core UI (shared logic)
# --------------------------------------------------------------------

class _ColorPickerCore(ui.View):
    """
    Core view that renders kind buttons + palette buttons + done.
    You can either:
      - present it modally (recommended) via ColorPickerModal
      - add it as a subview (ColorPickerPanel)

    Taps are handled via ui.Button.action -> stable (no coordinate hacks).
    """
    def __init__(self, board):
        self.board = board
        self.selected_kind = None

        self._kind_buttons = {}     # kind -> ui.Button
        self._swatch_buttons = []   # list[ui.Button]
        self._done_button = None

        # sizing: will be refined in _build
        super().__init__(frame=(0, 0, 380, 520))
        self.background_color = '#1C1C1E'
        self._build()

    # ----------------------------
    # Build
    # ----------------------------

    def _build(self):
        # Clear any previous UI if _build is called again (prevents stacked/overlapping controls).
        try:
            for v in list(self.subviews):
                try:
                    self.remove_subview(v)
                except Exception:
                    pass
        except Exception:
            pass
        w = self.width
        pad = 14

        # Card styling (if used as panel/subview)
        self.corner_radius = 14
        self.border_width = 1
        self.border_color = '#3A3A3C'

        title = ui.Label(frame=(0, 12, w, 24))
        title.text = 'Tile Colors'
        title.font = ('<System-Bold>', 16)
        title.text_color = '#FFFFFF'
        title.alignment = ui.ALIGN_CENTER
        title.touch_enabled = False
        self.add_subview(title)

        kinds_label = ui.Label(frame=(pad, 44, w - pad * 2, 18))
        kinds_label.text = 'Select tile type'
        kinds_label.font = ('<System>', 12)
        kinds_label.text_color = '#8E8E93'
        kinds_label.touch_enabled = False
        self.add_subview(kinds_label)

        # Kind buttons row (centered)
        tile_size = 36
        tile_gap = 6
        n = len(EDITABLE_KINDS)
        total_w = n * tile_size + (n - 1) * tile_gap
        start_x = (w - total_w) / 2
        tile_y = 66

        self._kind_buttons.clear()

        for i, (kind, label) in enumerate(EDITABLE_KINDS):
            x = start_x + i * (tile_size + tile_gap)

            b = ui.Button(frame=(x, tile_y, tile_size, tile_size))
            b.title = label
            b.font = ('<System-Bold>', 14)
            b.tint_color = '#000000'
            b.background_color = _get_kind_color(kind)
            b.corner_radius = 8
            b.border_width = 0
            b.name = kind
            b.action = self._on_kind
            self.add_subview(b)

            self._kind_buttons[kind] = b

        div1 = ui.View(frame=(pad, tile_y + tile_size + 10, w - pad * 2, 1))
        div1.background_color = '#3A3A3C'
        self.add_subview(div1)

        pal_label_y = tile_y + tile_size + 18
        pal_label = ui.Label(frame=(pad, pal_label_y, w - pad * 2, 18))
        pal_label.text = 'Choose color'
        pal_label.font = ('<System>', 12)
        pal_label.text_color = '#8E8E93'
        pal_label.touch_enabled = False
        self.add_subview(pal_label)

        # Palette (buttons)
        swatch_size = 32
        swatch_gap = 8
        cols = 8
        pal_y = pal_label_y + 24

        self._swatch_buttons = []

        for i, color in enumerate(PALETTE):
            col = i % cols
            row = i // cols
            sx = pad + col * (swatch_size + swatch_gap)
            sy = pal_y + row * (swatch_size + swatch_gap)

            sb = ui.Button(frame=(sx, sy, swatch_size, swatch_size))
            sb.background_color = color
            sb.corner_radius = 8
            sb.border_width = 1
            sb.border_color = '#3A3A3C'
            sb.name = color
            sb.action = self._on_swatch
            self.add_subview(sb)

            self._swatch_buttons.append(sb)

        rows = (len(PALETTE) + cols - 1) // cols
        pal_bottom = pal_y + rows * (swatch_size + swatch_gap)

        div2 = ui.View(frame=(pad, pal_bottom + 8, w - pad * 2, 1))
        div2.background_color = '#3A3A3C'
        self.add_subview(div2)

        btn_y = pal_bottom + 16
        done = ui.Button(frame=(pad, btn_y, w - pad * 2, 40))
        done.title = 'Done'
        done.font = ('<System-Bold>', 15)
        done.tint_color = '#FFFFFF'
        done.background_color = '#32ADE6'
        done.corner_radius = 10
        done.action = self._on_done
        self.add_subview(done)

        self._done_button = done

        # Fit height
        self.height = btn_y + 40 + pad

        print(f"[COLOR_PANEL] built: w={w:.0f} start_x={start_x:.0f} tile_size={tile_size} pal_y={pal_y:.0f} btn_y={btn_y:.0f}")

    # ----------------------------
    # Actions
    # ----------------------------

    def _on_kind(self, sender):
        kind = getattr(sender, 'name', None)
        if not kind:
            return
        self.selected_kind = kind

        # Highlight selected kind
        for k, b in self._kind_buttons.items():
            if k == kind:
                b.border_width = 2.5
                b.border_color = '#FFFFFF'
            else:
                b.border_width = 0

        print(f"[COLOR_PICKER] selected kind: {kind}")

    def _on_swatch(self, sender):
        color = getattr(sender, 'name', None)
        if not color:
            return

        if not self.selected_kind:
            print("[COLOR_PICKER] no kind selected")
            return

        kinds = _kinds_to_update(self.selected_kind)
        for k in kinds:
            _set_kind_color(k, color)
            kb = self._kind_buttons.get(k)
            if kb is not None:
                kb.background_color = color

        # Highlight selected swatch
        for b in self._swatch_buttons:
            try:
                if b.name == color:
                    b.border_color = '#FFFFFF'
                    b.border_width = 2
                else:
                    b.border_color = '#3A3A3C'
                    b.border_width = 1
            except Exception:
                pass

        print(f"[COLOR_PICKER] applied {color} to {kinds}")

        # Refresh live tiles
        try:
            self.board.refresh_tile_colors()
        except Exception:
            pass

    def _on_done(self, sender):
        self._close()

    # ----------------------------
    # Close hook (overridden by modal/panel wrappers)
    # ----------------------------

    def _close(self):
        # Default: remove from superview if embedded
        try:
            if self.superview:
                self.superview.remove_subview(self)
        except Exception:
            pass


# --------------------------------------------------------------------
# Public Views
# --------------------------------------------------------------------

class ColorPickerModal(_ColorPickerCore):
    """
    Recommended: present as a sheet/popover so it is isolated from your Board
    touch plumbing.
    """
    def __init__(self, board, present_style='sheet'):
        self._present_style = present_style
        super().__init__(board)

    def present_picker(self):
        try:
            # Centering is handled by present; keep fixed size.
            self.present(self._present_style)
        except Exception as e:
            print(f"[COLOR_MODAL_ERROR] {e}")

    def _close(self):
        try:
            self.dismiss_modal()
        except Exception:
            # fallback
            try:
                if self.superview:
                    self.superview.remove_subview(self)
            except Exception:
                pass


class ColorPickerPanel(_ColorPickerCore):
    """
    Optional: panel you can add as a subview on the board (overlay style).
    Still uses button actions (no manual coordinate hit testing).
    """
    def __init__(self, board):
        # Size tuned to your earlier panel feel
        super().__init__(board)
        # Position as a centered card at top (similar to old panel)
        try:
            bw = float(getattr(board, 'width', 0) or 0)
            w = min(bw - 32, 340) if bw > 0 else 340
            self.width = w
            self._build()  # rebuild layout to new width
            x = (bw - self.width) / 2 if bw > 0 else 20
            y = 20
            self.frame = (x, y, self.width, self.height)
        except Exception:
            pass

    def dismiss(self):
        self._close()


# --------------------------------------------------------------------
# Convenience API
# --------------------------------------------------------------------

def show_color_picker(board, style='sheet'):
    """
    One-liner to open the picker. Use from Board._on_gear_tapped, etc.

    style: 'sheet' (default) or 'popover'
    """
    v = ColorPickerModal(board, present_style=style)
    v.present_picker()
    return v
