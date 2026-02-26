# tile.py (replacement)
# Pythonista-compatible
import ui
import uuid


def _darker(hex_color, factor=0.85):
    h = str(hex_color or '').lstrip('#')
    if len(h) != 6:
        return hex_color
    try:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
    except Exception:
        return hex_color
    r = int(r * factor)
    g = int(g * factor)
    b = int(b * factor)
    return '#%02x%02x%02x' % (max(0, min(255, r)),
                               max(0, min(255, g)),
                               max(0, min(255, b)))


def _lighter(hex_color, factor=1.15):
    h = str(hex_color or '').lstrip('#')
    if len(h) != 6:
        return hex_color
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return hex_color
    return '#%02x%02x%02x' % (min(255, int(r * factor)),
                               min(255, int(g * factor)),
                               min(255, int(b * factor)))


def _hex_to_rgba(hex_color, alpha=1.0):
    h = str(hex_color or '').lstrip('#')
    if len(h) != 6:
        return (0.8, 0.8, 0.8, float(alpha))
    try:
        return (int(h[0:2], 16) / 255.0,
                int(h[2:4], 16) / 255.0,
                int(h[4:6], 16) / 255.0,
                float(alpha))
    except Exception:
        return (0.8, 0.8, 0.8, float(alpha))


_KIND_COLORS_DEFAULT = {
    'number':     '#FDFD96',
    'result':     '#FFD60A',
    'num_op':     '#FDFD96',
    'num_tool':   '#80EF80',
    'fraction':   '#FF9F0A',
    'op':         '#AEC6CF',
    'expr':       '#D198B7',
    'expr_tool':  '#80EF80',
    'irrational': '#FF8C42',
    'eq':         '#32ADE6',
    'armed_eq':   '#32ADE6',
    'symbol':     '#34C759',
    'tool':       '#80EF80',
    'puck':       '#8E8E93',
}

# UI border/selection theme — single source of truth for all border colors.
BORDER_DEFAULT  = '#3A3A3C'   # resting tile border
BORDER_SELECTED = '#0A84FF'   # individual selection (blue)
BORDER_STICKY   = '#FF9F0A'   # sticky tile (amber)
BORDER_GROUP    = '#FF3B30'   # group / lasso selection (red)


def _load_kind_colors():
    import json
    import os
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, 'tile_colors.json')
        with open(path, 'r') as f:
            data = json.load(f) or {}
        merged = dict(_KIND_COLORS_DEFAULT)
        if isinstance(data, dict):
            merged.update(data)
        return merged
    except Exception:
        return dict(_KIND_COLORS_DEFAULT)


def _save_kind_colors(colors):
    import json
    import os
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, 'tile_colors.json')
        with open(path, 'w') as f:
            json.dump(colors, f, indent=2)
        return True
    except Exception as e:
        print(f"[TILE_COLORS] save failed: {e}")
        return False


KIND_COLORS = _load_kind_colors()


class Tile(ui.View):
    DEFAULT_CELL_SIZE = 60
    DEFAULT_GUTTER = 4

    # -----
    # IMPORTANT: draw() owns all background rendering - keep views transparent.
    # We defensively ignore external background_color sets via an overridden property.
    # -----

    def __init__(
        self,
        text='1',
        kind='number',
        color='#FFD60A',
        size=56,
        data=None,
        w_cells=1,
        h_cells=1,
        cell_size=None,
        gutter=None,
        is_result=False,
        **kwargs
    ):
        super().__init__(**kwargs)

        # Local fallback TileData if not provided elsewhere.
        try:
            TD = TileData  # noqa: F821
        except Exception:
            class TD:
                __slots__ = ("tile_id", "kind", "display", "expr_str", "meta")
                def __init__(self, tile_id, kind, display, expr_str=None, meta=None):
                    self.tile_id = tile_id
                    self.kind = kind
                    self.display = display
                    self.expr_str = display if expr_str is None else expr_str
                    self.meta = {} if meta is None else dict(meta)
            Tile.TileData = TD

        if data is None:
            data = TD(
                tile_id=str(uuid.uuid4()),
                kind=kind,
                display=str(text),
                expr_str=str(text),
                meta={},
            )

        self.data = data
        if not hasattr(self.data, 'meta') or self.data.meta is None:
            self.data.meta = {}

        self.label_text = str(text)
        self.is_result = bool(is_result)

        # Sizing model
        self.w_cells = int(w_cells) if w_cells else 1
        self.h_cells = int(h_cells) if h_cells else 1
        self.cell_size = int(cell_size) if cell_size is not None else int(Tile.DEFAULT_CELL_SIZE)
        self.gutter = int(gutter) if gutter is not None else Tile.DEFAULT_GUTTER

        # Rendering / style
        self.corner_radius = 16
        self.border_width = 2
        self.border_color = BORDER_DEFAULT

        # draw() owns background — force clear (defensively, even if someone sets it elsewhere)
        self._force_view_bg_clear()

        try:
            self.touch_enabled = False
        except Exception:
            pass

        self._selected = False
        self._dragging = False
        self._group_selected = False
        self._sticky = False

        self._label_inset = 6
        self._font_max = 20
        self._font_min = 10

        # Fraction subviews
        self._frac_numer = None
        self._frac_denom = None
        self._frac_line = None
        self.content_view = None

        # If you ever need to freeze size behavior
        self._fixed_size = False

        # Apply size first
        self._apply_size(size=size)

        # Colors from kind
        resolved_color = KIND_COLORS.get(self.data.kind, color)
        self.base_color = resolved_color
        self.drag_color = _darker(resolved_color, 0.80)

        # Main label (non-fraction)
        self.label = ui.Label(frame=self.bounds)
        self.label.flex = 'WH'
        self.label.alignment = ui.ALIGN_CENTER
        self.label.text_color = '#3b3b3b'
        self.label.number_of_lines = 1
        self.label.font = ('<System-Bold>', self._font_max)
        self.label.text = self.data.display
        try:
            self.label.line_break_mode = ui.LB_CLIP
        except Exception:
            pass
        try:
            self.label.touch_enabled = False
        except Exception:
            pass
        self.add_subview(self.label)

        # Fraction setup (if needed)
        if self.data.kind == 'fraction':
            self._ensure_fraction_views()
            self._sync_fraction_from_meta()

        self._refresh_mode()
        self.set_needs_layout()
        try:
            self.set_needs_display()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Background defense (tile draw owns background)
    # ------------------------------------------------------------------

    def _force_view_bg_clear(self):
        """Best-effort: set the *real* ui.View background_color to clear without relying on our overridden property."""
        try:
            # Pythonista ui.View typically exposes background_color as a property descriptor
            # that supports fset or __set__.
            prop = ui.View.background_color
            try:
                prop.fset(self, 'clear')
                return
            except Exception:
                pass
            try:
                prop.__set__(self, 'clear')
                return
            except Exception:
                pass
        except Exception:
            pass
        # If we can't set it, draw() still paints everything. This is just a defensive cleanup.

    @property
    def background_color(self):
        return 'clear'

    @background_color.setter
    def background_color(self, v):
        # draw() owns this - ignore external sets
        pass

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def tile_id(self):
        return self.data.tile_id

    @property
    def kind(self):
        return self.data.kind

    @kind.setter
    def kind(self, v):
        self.data.kind = v
        new_color = KIND_COLORS.get(v)
        if new_color:
            # Per instructions: only update base_color + drag_color, no background assignments.
            self.base_color = new_color
            self.drag_color = _darker(new_color, 0.80)
        self._refresh_mode()
        try:
            self.set_needs_display()
        except Exception:
            pass

    @property
    def text(self):
        return self.data.display

    @text.setter
    def text(self, v):
        self.set_label(str(v))

    @property
    def display(self):
        return self.data.display

    @display.setter
    def display(self, v):
        self.set_label(str(v))

    @property
    def expr_str(self):
        return self.data.expr_str

    @expr_str.setter
    def expr_str(self, v):
        self.data.expr_str = str(v)

    # ------------------------------------------------------------------
    # Label + sizing
    # ------------------------------------------------------------------

    def set_label(self, text):
        try:
            self.label_text = text or ''
            if self.label:
                self.label.text = self.label_text
            self.data.display = self.label_text
            if not self.expr_str:
                self.expr_str = self.label_text
            self.ensure_legible()
            self._fit_label()
        except Exception as e:
            print(f"[SET_LABEL] CRASHED: {e}")
            import traceback
            traceback.print_exc()

    def _fit_label(self):
        if not self.label:
            return
        text = self.label.text or ''
        if not text.strip():
            self.label.font = ('<System-Bold>', self._font_max)
            return

        max_w = max(1.0, float(self.label.width) * 0.94)
        max_h = max(1.0, float(self.label.height) * 0.98)

        try:
            measure = ui.measure_string
        except Exception:
            measure = None

        for size in range(self._font_max, self._font_min - 1, -1):
            self.label.font = ('<System-Bold>', size)
            if measure is None:
                # rough fallback
                if len(text) <= 3 and size >= 18:
                    return
                if len(text) <= 6 and size >= 14:
                    return
                if size <= 12:
                    return
            else:
                w, h = measure(text, font=self.label.font)
                if (w * 1.06) <= max_w and (h * 1.02) <= max_h:
                    return

        self.label.font = ('<System-Bold>', self._font_min)

    def _fit_label_to_bounds(self, lbl, max_w, max_h, font_max=18, font_min=10):
        text = lbl.text or ''
        if not text.strip():
            lbl.font = ('<System-Bold>', font_max)
            return

        max_w = max(1.0, float(max_w) * 0.92)
        max_h = max(1.0, float(max_h) * 0.98)

        try:
            measure = ui.measure_string
        except Exception:
            measure = None

        for sz in range(int(font_max), int(font_min) - 1, -1):
            lbl.font = ('<System-Bold>', sz)
            if measure is None:
                if len(text) <= 3 and sz >= 16:
                    return
                if len(text) <= 6 and sz >= 12:
                    return
                if sz <= 12:
                    return
            else:
                w, h = measure(text, font=lbl.font)
                if (w * 1.06) <= max_w and (h * 1.02) <= max_h:
                    return

        lbl.font = ('<System-Bold>', int(font_min))

    def _apply_size(self, size=None):
        if self.cell_size is not None:
            cs = float(self.cell_size)
            g = float(self.gutter)
            self.width = max(10.0, self.w_cells * cs - g)
            self.height = max(10.0, self.h_cells * cs - g)
        else:
            s = float(size if size is not None else 56)
            self.width = s
            self.height = s

    def set_cell_size(self, w_cells=None, h_cells=None, cell_size=None, gutter=None):
        if w_cells is not None:
            self.w_cells = max(1, int(w_cells))
        if h_cells is not None:
            self.h_cells = max(1, int(h_cells))
        if cell_size is not None:
            self.cell_size = int(cell_size)
        if gutter is not None:
            self.gutter = int(gutter)

        self._apply_size()
        self.ensure_legible()
        self.set_needs_layout()

    def ensure_legible(self, max_w_cells=4):
        if not self.label:
            return
        if self.kind == 'fraction':
            return
        if self.cell_size is None or self._fixed_size:
            return

        text = self.label.text or ''
        if not text.strip():
            return

        border = int(self.border_width)
        padding = (border + 4) * 2

        if self.kind in ('expr', 'symbol', 'fx'):
            comfortable_min = max(self._font_min, self._font_max - 8)
        else:
            comfortable_min = max(self._font_min, self._font_max - 4)

        try:
            tw, _ = ui.measure_string(text, font=('<System-Bold>', self._font_max))
        except Exception:
            tw = len(text) * (self._font_max * 0.6)

        needed_cells = max_w_cells
        for w in range(1, max_w_cells + 1):
            tile_w = w * float(self.cell_size) - float(self.gutter)
            usable_w = tile_w - padding
            if (tw * 1.06) <= usable_w:
                needed_cells = w
                break

        if needed_cells != self.w_cells:
            self.set_cell_size(
                w_cells=needed_cells,
                h_cells=self.h_cells,
                cell_size=self.cell_size,
                gutter=self.gutter
            )

        current_usable = float(self.width) - padding

        try:
            for font_size in range(self._font_max, comfortable_min - 1, -1):
                tw2, _ = ui.measure_string(text, font=('<System-Bold>', font_size))
                if (tw2 * 1.06) <= current_usable:
                    return
        except Exception:
            return

        if self.w_cells < max_w_cells:
            self.set_cell_size(
                w_cells=self.w_cells + 1,
                h_cells=self.h_cells,
                cell_size=self.cell_size,
                gutter=self.gutter
            )

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def layout(self):
        border = int(self.border_width)
        inset_x = border + 1
        inset_y = border + 4

        # Sticky dot (optional)
        dot = None
        try:
            dot = getattr(self, '_sticky_dot', None)
            if dot is None:
                dot = ui.View()
                dot.background_color = '#000000'
                dot.corner_radius = 4
                dot.hidden = True
                try:
                    dot.touch_enabled = False
                except Exception:
                    pass
                self._sticky_dot = dot
                self.add_subview(dot)
        except Exception:
            dot = None

        if self.label:
            self.label.frame = (
                inset_x,
                inset_y,
                max(1.0, self.width - inset_x * 2),
                max(1.0, self.height - inset_y * 2)
            )

        try:
            if dot is not None:
                size = 8
                dx = inset_x + 4
                dy = inset_y + 2
                dot.frame = (dx, dy, size, size)
                dot.hidden = not bool(getattr(self, '_sticky', False))
        except Exception:
            pass

        if self.kind == 'fraction' and self._frac_numer is not None and self.content_view is not None:
            # content_view covers full bounds, but remains transparent (draw() shows through).
            self.content_view.frame = self.bounds

            inner_w = max(1.0, self.width - inset_x * 2)
            inner_h = max(1.0, self.height - inset_y * 2)
            line_h = 2.0
            half_h = max(1.0, (inner_h - line_h) * 0.5)
            y0 = float(inset_y)

            self._frac_numer.frame = (inset_x, y0, inner_w, half_h)
            self._frac_line.frame = (inset_x, y0 + half_h, inner_w, line_h)
            self._frac_denom.frame = (inset_x, y0 + half_h + line_h, inner_w, half_h)

            self._fit_label_to_bounds(self._frac_numer, inner_w, half_h, font_max=18, font_min=10)
            self._fit_label_to_bounds(self._frac_denom, inner_w, half_h, font_max=18, font_min=10)

            self._frac_numer.bring_to_front()
            self._frac_line.bring_to_front()
            self._frac_denom.bring_to_front()
        else:
            self.ensure_legible()
            self._fit_label()

        try:
            if dot is not None:
                dot.bring_to_front()
        except Exception:
            pass

    def set_needs_layout(self):
        try:
            self.set_needs_display()
        except Exception:
            pass
        try:
            if self.superview:
                self.superview.set_needs_display()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Rendering (draw owns background)
    # ------------------------------------------------------------------

    def draw(self):
        w = self.width
        h = self.height
        cr = self.corner_radius
        bw = self.border_width
        if w < 1 or h < 1:
            return

        color = self.drag_color if self._dragging else self.base_color

        # 1) Base fill
        base = ui.Path.rounded_rect(0, 0, w, h, cr)
        ui.set_color(_hex_to_rgba(color))
        base.fill()

        # 2) Top highlight band
        with ui.GState():
            clip = ui.Path.rounded_rect(0, 0, w, h, cr)
            clip.add_clip()
            highlight = ui.Path()
            highlight.move_to(0, 0)
            highlight.line_to(w, 0)
            highlight.line_to(w, h * 0.38)
            highlight.add_curve(w * 0.5, h * 0.48, 0, h * 0.42, 0, 0)
            highlight.close()
            ui.set_color((1, 1, 1, 0.22))
            highlight.fill()

        # 3) Bottom shadow band
        with ui.GState():
            clip2 = ui.Path.rounded_rect(0, 0, w, h, cr)
            clip2.add_clip()
            shadow = ui.Path()
            shadow.move_to(0, h)
            shadow.line_to(w, h)
            shadow.line_to(w, h * 0.68)
            shadow.add_curve(w * 0.5, h * 0.58, 0, h * 0.64, 0, h)
            shadow.close()
            ui.set_color((0, 0, 0, 0.08))
            shadow.fill()

        # 4) Inner glow border
        inset = bw + 0.5
        inner = ui.Path.rounded_rect(
            inset, inset, w - inset * 2, h - inset * 2, max(0, cr - inset)
        )
        inner.line_width = 1.0
        ui.set_color((1, 1, 1, 0.30))
        inner.stroke()

        # 5) Outer border
        border_color = self.border_color or '#3A3A3C'
        border = ui.Path.rounded_rect(
            bw * 0.5, bw * 0.5, w - bw, h - bw, max(0, cr - bw * 0.5)
        )
        border.line_width = bw
        ui.set_color(_hex_to_rgba(border_color))
        border.stroke()

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------

    def _normalize_display(self, raw):
        """Pretty-print a raw sympy expression string using shared formatter when available."""
        try:
            from merge_engine import _pretty
            return _pretty(raw)
        except Exception:
            return str(raw)

    def normalize(self):
        """
        Enforce consistency between kind, size, color, and display.
        Per instructions: do NOT set self.background_color or content_view.background_color.
        """
        try:
            kind = getattr(self, 'kind', 'number') or 'number'

            # Color (base_color + drag_color only)
            try:
                if kind == 'fraction':
                    meta = getattr(self.data, 'meta', {}) or {}
                    is_expr = bool(meta.get('is_expr', False))
                    frac_kind = 'expr' if is_expr else 'fraction'
                    color = KIND_COLORS.get(frac_kind, KIND_COLORS.get('fraction', '#FF9F0A'))
                else:
                    color = KIND_COLORS.get(kind, '#FFD60A')

                self.base_color = color
                self.drag_color = _darker(color, 0.80)
            except Exception as e:
                print(f"[NORMALIZE_COLOR] {e}")

            # Size
            try:
                if kind == 'fraction':
                    if getattr(self, 'h_cells', 1) != 2:
                        self.set_cell_size(
                            w_cells=getattr(self, 'w_cells', 1),
                            h_cells=2,
                            cell_size=self.cell_size,
                            gutter=self.gutter
                        )
                else:
                    if getattr(self, 'h_cells', 1) != 1:
                        self.set_cell_size(
                            w_cells=getattr(self, 'w_cells', 1),
                            h_cells=1,
                            cell_size=self.cell_size,
                            gutter=self.gutter
                        )
            except Exception as e:
                print(f"[NORMALIZE_SIZE] {e}")

            # Display
            try:
                if kind == 'fraction':
                    self._ensure_fraction_views()
                    self._sync_fraction_from_meta()
                    self._refresh_mode()
                    self.layout()
                else:
                    raw = str(
                        getattr(self, 'expr_str', None)
                        or getattr(self.data, 'display', None)
                        or getattr(self, 'text', '')
                        or ''
                    ).strip()
                    if raw:
                        pretty = self._normalize_display(raw)
                        if self.label:
                            self.label.text = pretty
                        self.data.display = pretty

                    self._refresh_mode()
                    self.ensure_legible()
                    self._fit_label()
            except Exception as e:
                print(f"[NORMALIZE_DISPLAY] {e}")

            try:
                self.set_needs_display()
            except Exception:
                pass

        except Exception as e:
            print(f"[NORMALIZE] {e}")

    # ------------------------------------------------------------------
    # Fraction views
    # ------------------------------------------------------------------

    def _ensure_fraction_views(self):
        if self._frac_numer is not None:
            return

        # content_view sits ABOVE draw() — it MUST be transparent so draw() shows through.
        if self.content_view is None:
            self.content_view = ui.View(frame=self.bounds)
            self.content_view.flex = 'WH'
            # REQUIRED CHANGE #1
            self.content_view.background_color = 'clear'
            self.content_view.corner_radius = 0  # tile's own draw() handles corners
            try:
                self.content_view.touch_enabled = False
            except Exception:
                pass
            self.add_subview(self.content_view)

        self._frac_numer = ui.Label()
        self._frac_denom = ui.Label()
        self._frac_line = ui.View()

        for lbl in (self._frac_numer, self._frac_denom):
            lbl.alignment = ui.ALIGN_CENTER
            lbl.text_color = '#000000'
            lbl.number_of_lines = 1
            lbl.font = ('<System-Bold>', 18)
            lbl.background_color = (0, 0, 0, 0)
            try:
                lbl.touch_enabled = False
                lbl.line_break_mode = ui.LB_CLIP
            except Exception:
                pass
            self.content_view.add_subview(lbl)

        # GOTCHA: keep this as-is (it should render on top of draw())
        self._frac_line.background_color = (0, 0, 0, 0.55)
        try:
            self._frac_line.touch_enabled = False
        except Exception:
            pass
        self.content_view.add_subview(self._frac_line)

        # Initial frames (layout() will update)
        pad = float(getattr(self, '_label_inset', 6))
        w = float(self.content_view.width)
        h = float(self.content_view.height)
        inner_w = max(1.0, w - pad * 2)
        inner_h = max(1.0, h - pad * 2)
        line_h = 2.0
        half_h = max(1.0, (inner_h - line_h) * 0.5)
        y0 = pad

        self._frac_numer.frame = (pad, y0, inner_w, half_h)
        self._frac_line.frame = (pad, y0 + half_h, inner_w, line_h)
        self._frac_denom.frame = (pad, y0 + half_h + line_h, inner_w, half_h)

        self._frac_numer.bring_to_front()
        self._frac_line.bring_to_front()
        self._frac_denom.bring_to_front()

        # REQUIRED DEFENSE (as requested): draw() owns all background rendering
        self._force_view_bg_clear()

    def _sync_fraction_from_meta(self):
        m = getattr(self.data, 'meta', {}) or {}
        n_disp = m.get('numer_disp', self.data.display)
        d_disp = m.get('denom_disp', '')

        # Pretty-print display strings (optional)
        try:
            from merge_engine import _pretty
            n_disp = _pretty(n_disp) if n_disp else ''
            d_disp = _pretty(d_disp) if d_disp else ''
        except Exception:
            pass

        if self._frac_numer is not None:
            self._frac_numer.text = str(n_disp) if n_disp is not None else ''
        if self._frac_denom is not None:
            self._frac_denom.text = str(d_disp) if d_disp is not None else ''

        # Optional width growth for longer numer/denom displays
        try:
            max_text_w = 0
            for label in (self._frac_numer, self._frac_denom):
                if label and label.text:
                    size = ui.measure_string(label.text, font=label.font)
                    text_w = size[0] if hasattr(size, '__getitem__') else getattr(size, 'width', 0)
                    max_text_w = max(max_text_w, text_w)

            current_w = self.width - 12
            current_cells = getattr(self, 'w_cells', 1)
            g = getattr(self, 'cell_size', 60)

            if max_text_w > current_w:
                if max_text_w <= g * 2 - 16:
                    needed_cells = 2
                elif max_text_w <= g * 3 - 16:
                    needed_cells = 3
                else:
                    needed_cells = 4
                if needed_cells > current_cells:
                    self.set_cell_size(
                        w_cells=needed_cells,
                        h_cells=getattr(self, 'h_cells', 2),
                        cell_size=g,
                        gutter=getattr(self, 'gutter', 4)
                    )
                    self.layout()
        except Exception as e:
            print(f"[FRAC_RESIZE_ERROR] {e}")

    def set_fraction(self, numer_disp, denom_disp, numer_expr=None, denom_expr=None):
        """
        Per instructions: do NOT assign background_color on self or content_view.
        """
        if not hasattr(self.data, 'meta') or self.data.meta is None:
            self.data.meta = {}

        self.data.meta['numer_disp'] = str(numer_disp)
        self.data.meta['denom_disp'] = str(denom_disp)
        self.data.meta['numer_expr'] = str(numer_expr if numer_expr is not None else numer_disp)
        self.data.meta['denom_expr'] = str(denom_expr if denom_expr is not None else denom_disp)

        self.expr_str = f"({self.data.meta['numer_expr']})/({self.data.meta['denom_expr']})"

        # Ensure kind and shape
        self.kind = 'fraction'
        if self.cell_size is not None:
            self.set_cell_size(
                w_cells=getattr(self, 'w_cells', 1),
                h_cells=2,
                cell_size=self.cell_size,
                gutter=self.gutter
            )

        self._ensure_fraction_views()
        self._sync_fraction_from_meta()
        self._refresh_mode()

        try:
            self.layout()
        except Exception:
            pass
        try:
            self.set_needs_display()
        except Exception:
            pass
        try:
            if self.superview:
                self.superview.set_needs_display()
        except Exception:
            pass

    def _refresh_mode(self):
        is_frac = (self.data.kind == 'fraction')

        if self.content_view is not None:
            self.content_view.hidden = not is_frac

        if self.label:
            self.label.hidden = bool(is_frac)

        if self._frac_numer is not None:
            self._frac_numer.hidden = not is_frac
        if self._frac_denom is not None:
            self._frac_denom.hidden = not is_frac
        if self._frac_line is not None:
            self._frac_line.hidden = not is_frac

        if is_frac and self._frac_numer is not None:
            self._frac_numer.bring_to_front()
            self._frac_line.bring_to_front()
            self._frac_denom.bring_to_front()

        if not is_frac:
            self._fit_label()

    # ------------------------------------------------------------------
    # Selection / border
    # ------------------------------------------------------------------

    def set_group_selected(self, on):
        self._group_selected = bool(on)
        try:
            self._apply_border_style()
        except Exception:
            pass

    def _apply_border_style(self):
        selected = bool(getattr(self, '_selected', False))
        sticky = bool(getattr(self, '_sticky', False))
        grouped = bool(getattr(self, '_group_selected', False))

        if selected:
            self.border_color = BORDER_SELECTED
            self.border_width = 3
        elif sticky:
            self.border_color = BORDER_STICKY
            self.border_width = 3
        elif grouped:
            self.border_color = BORDER_GROUP
            self.border_width = 3
        else:
            self.border_color = BORDER_DEFAULT
            self.border_width = 2

        try:
            self.layout()
        except Exception:
            pass
        try:
            self.set_needs_display()
        except Exception:
            pass

    def set_selected(self, on):
        self._selected = bool(on)

        try:
            b = getattr(self, '_sticky_badge', None)
            if b is not None:
                b.hidden = not bool(getattr(self, '_sticky', False))
                b.bring_to_front()
        except Exception:
            pass

        group_on = bool(getattr(self, '_group_selected', False))
        sticky_on = bool(getattr(self, '_sticky', False))

        if group_on:
            self.border_color = BORDER_GROUP
            self.border_width = 4
        elif self._selected:
            self.border_color = BORDER_SELECTED
            self.border_width = 3
        elif sticky_on:
            self.border_color = BORDER_STICKY
            self.border_width = 3
        else:
            self.border_color = BORDER_DEFAULT
            self.border_width = 2

        try:
            self.layout()
        except Exception:
            pass
        try:
            self.set_needs_display()
        except Exception:
            pass

    def set_dragging(self, on):
        """
        Per instructions: remove content_view.background_color toggles.
        Just flip state and redraw.
        """
        self._dragging = bool(on)
        try:
            self.set_needs_display()
        except Exception:
            pass

    @property
    def sticky(self):
        return bool(getattr(self, '_sticky', False))

    @sticky.setter
    def sticky(self, v):
        self._sticky = bool(v)

        if not bool(getattr(self, '_selected', False)):
            if self._sticky:
                self.border_color = BORDER_STICKY
                self.border_width = 3
            else:
                self.border_color = BORDER_DEFAULT
                self.border_width = 2

        try:
            b = getattr(self, '_sticky_badge', None)
            if b is not None:
                b.hidden = not self._sticky
                b.bring_to_front()
        except Exception:
            pass

        try:
            self.layout()
        except Exception:
            pass
        try:
            self.set_needs_display()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Colors API
    # ------------------------------------------------------------------

    @staticmethod
    def color_for_kind(kind):
        return KIND_COLORS.get(kind, '#FDFD96')

    @staticmethod
    def set_kind_color(kind, color):
        """Update a kind's color, persist to JSON, return success."""
        KIND_COLORS[kind] = color
        return _save_kind_colors(KIND_COLORS)
