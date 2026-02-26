# merge_engine.py

class MergeResult:
    def __init__(self,
                 replace_tile=None,
                 delete_tile=None,
                 new_display=None,
                 new_expr_str=None,
                 keep_both=False,
                 spawn_direction=None,
                 spawn_spec=None,
                 return_tile=None,
                 return_direction=None,
                 no_sticky=False,
                 mutate_a=None,
                 mutate_target=None):
        self.replace_tile     = replace_tile
        self.delete_tile      = delete_tile
        self.new_display      = new_display
        self.new_expr_str     = new_expr_str
        self.keep_both        = keep_both
        self.spawn_direction  = spawn_direction
        self.spawn_spec       = spawn_spec
        self.return_tile      = return_tile
        self.return_direction = return_direction
        self.no_sticky        = no_sticky
        self.mutate_a         = mutate_a
        self.mutate_target    = mutate_target
            



def _started_adjacent(drag_start_center, target, grid):
    """Was drag_start adjacent to target in any of the four directions?"""
    for d in ('above', 'below', 'left', 'right'):
        if _adjacent_in_direction(drag_start_center, target, grid, d):
            return True
    return False

def _tile_border_zones(target, grid):
    """
    Border zones around a tile.
    Name = where drag STARTED (intuitive):
      'left'   = zone to the LEFT  (drag starts left,  moves right into tile)
      'right'  = zone to the RIGHT (drag starts right, moves left into tile)
      'above'  = zone ABOVE tile   (drag starts above, moves down into tile)
      'below'  = zone BELOW tile   (drag starts below, moves up into tile)
    """
    try:
        fx, fy, fw, fh = target.frame.x, target.frame.y, target.frame.width, target.frame.height
    except Exception:
        tx, ty = target.center
        fw = getattr(target, 'w_cells', 1) * grid
        fh = getattr(target, 'h_cells', 1) * grid
        fx = tx - fw / 2
        fy = ty - fh / 2

    left   = fx
    right  = fx + fw
    top    = fy
    bottom = fy + fh
    cx     = fx + fw / 2
    cy     = fy + fh / 2

    return {
        'left':         (left   - grid/2, cy,             grid/2,           fh/2 + grid*0.1),
        'right':        (right  + grid/2, cy,             grid/2,           fh/2 + grid*0.1),
        'above':        (cx,              top    - grid/2, fw/2 + grid*0.1, grid/2),
        'below':        (cx,              bottom + grid/2, fw/2 + grid*0.1, grid/2),
        'top_left':     (left   - grid/2, top    - grid/2, grid/2,          grid/2),
        'top_right':    (right  + grid/2, top    - grid/2, grid/2,          grid/2),
        'bottom_left':  (left   - grid/2, bottom + grid/2, grid/2,          grid/2),
        'bottom_right': (right  + grid/2, bottom + grid/2, grid/2,          grid/2),
    }

def _point_in_zone(px, py, zone_cx, zone_cy, half_w, half_h, soft=True):
    """
    Check if point (px,py) is in a rectangular zone.
    soft=True uses circular falloff at corners for a softer feel.
    """
    dx = abs(px - zone_cx)
    dy = abs(py - zone_cy)
    if dx > half_w or dy > half_h:
        return False
    if not soft:
        return True
    # Soften corners: in corner region, use circular check
    corner_dx = dx - half_w * 0.6
    corner_dy = dy - half_h * 0.6
    if corner_dx > 0 and corner_dy > 0:
        r = max(half_w, half_h) * 0.5
        return (corner_dx**2 + corner_dy**2) <= r**2
    return True


def _classify_drag_start(drag_start, target, grid):
    """
    Classify where drag_start sits relative to target's border zones.
    Returns zone name string or None.
    Diagonals checked first (they're a subset of cardinal zones geometrically).
    """
    if drag_start is None or target is None:
        return None
    px, py = drag_start
    zones = _tile_border_zones(target, grid)
    # Diagonals first — more specific
    for name in ('top_left', 'top_right', 'bottom_left', 'bottom_right'):
        cx, cy, hw, hh = zones[name]
        if _point_in_zone(px, py, cx, cy, hw, hh, soft=True):
            return name
    # Cardinals
    for name in ('left', 'right', 'above', 'below'):
        cx, cy, hw, hh = zones[name]
        if _point_in_zone(px, py, cx, cy, hw, hh, soft=True):
            return name
    return None


def _adjacent_in_direction(drag_start_center, target, grid, direction):
    """Check if drag started in a specific border zone."""
    zone = _classify_drag_start(drag_start_center, target, grid)
    return zone == direction


def _started_adjacent(drag_start_center, target, grid):
    """Was drag_start in any border zone around target?"""
    return _classify_drag_start(drag_start_center, target, grid) is not None

''''
class MergeRule:
    priority = 100  # lower = earlier

    def can_apply(self, a, b, ctx):
        return False

    def apply(self, a, b, ctx):
        return None'''


class MergeRule:
    priority = 50

    def can_apply(self, a, b, ctx):
        return False

    def apply(self, a, b, ctx):
        return None

    def preview_label(self, a, b, ctx):
        """
        Return a preview string to show on the target tile during drag.
        Must be pure — no side effects, no tile mutation.
        Return None if this rule has no meaningful preview.
        """
        return None


class DirectionalSubtractRule(MergeRule):
    priority = 6

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _disp(self, t):
        d = getattr(t.data, 'display', None) if getattr(t, 'data', None) else None
        return str(d or self._expr(t)).strip()

    def can_apply(self, a, b, ctx):
        if ctx.get('spawn_direction') != 'left':
            return False
        from merge_engine import tile_state
        if tile_state(a) in ('armed_num', 'armed_expr', 'armed_frac', 'armed_frac_expr'):
            return False
        if tile_state(b) in ('armed_num', 'armed_expr', 'armed_frac', 'armed_frac_expr'):
            return False
        bad_kinds = ('op', 'eq', 'tool', 'num_tool', 'expr_tool')
        if getattr(a, 'kind', '') in bad_kinds:
            return False
        if getattr(b, 'kind', '') in bad_kinds:
            return False
        if not self._expr(a) or not self._expr(b):
            return False
        board = ctx.get('board')
        grid = board.grid if board else 60
        if not _started_adjacent(ctx.get('drag_start_center'), b, grid):
            return False
        return True

    def preview_result(self, a, b, ctx):
        import sympy
        from merge_engine import _pretty
        try:
            result = sympy.simplify(sympy.sympify(self._expr(b)) - sympy.sympify(self._expr(a)))
            if result.free_symbols:
                return (_pretty(result), 'expr')
            elif result.is_integer:
                return (str(int(result)), 'number')
            else:
                return (_pretty(result), 'number' if result.is_rational else 'irrational')
        except Exception:
            return None

    def preview_label(self, a, b, ctx):
        b_disp = ctx.get('target_original') or self._disp(b)
        return f"{b_disp} − {self._disp(a)}"

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile
        from merge_engine import _pretty
        a_expr = self._expr(a)
        b_expr = self._expr(b)
        try:
            result = sympy.simplify(sympy.sympify(b_expr) - sympy.sympify(a_expr))
            has_symbols = bool(result.free_symbols)
            if has_symbols:
                disp = _pretty(result)
                kind = 'expr'
            elif result.is_integer:
                disp = str(int(result))
                kind = 'number'
            else:
                disp = _pretty(result)
                kind = 'number' if result.is_rational else 'irrational'
            color = _Tile.color_for_kind(kind)
            print(f"[DIR_SUB] {b_expr} - {a_expr} -> {str(result)}")
            b.kind = kind
            b.set_label(disp)
            b.expr_str = str(result)
            b.set_cell_size(w_cells=1, h_cells=1,
                cell_size=b.cell_size, gutter=b.gutter)
            try:
                b.data.display = disp
            except Exception:
                pass
            b.base_color = color
            b.background_color = color
            b.drag_color = color
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[DIR_SUB_ERROR] {e}")
            return None



class DirectionalMultiplyRule(MergeRule):
    priority = 6

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _disp(self, t):
        d = getattr(t.data, 'display', None) if getattr(t, 'data', None) else None
        return str(d or self._expr(t)).strip()

    def can_apply(self, a, b, ctx):
        if ctx.get('spawn_direction') != 'below':
            return False
        from merge_engine import tile_state
        if tile_state(a) in ('armed_num', 'armed_expr', 'armed_frac', 'armed_frac_expr'):
            return False
        if tile_state(b) in ('armed_num', 'armed_expr', 'armed_frac', 'armed_frac_expr'):
            return False
        bad_kinds = ('op', 'eq', 'tool', 'num_tool', 'expr_tool', 'fraction')
        if getattr(a, 'kind', '') in bad_kinds:
            return False
        if getattr(b, 'kind', '') in bad_kinds:
            return False
        if not self._expr(a) or not self._expr(b):
            return False
        board = ctx.get('board')
        grid = board.grid if board else 60
        if not _started_adjacent(ctx.get('drag_start_center'), b, grid):
            return False
        return True

    def preview_result(self, a, b, ctx):
        import sympy
        from merge_engine import _pretty
        try:
            result = sympy.simplify(sympy.sympify(self._expr(a)) * sympy.sympify(self._expr(b)))
            if result.free_symbols:
                return (_pretty(result), 'expr')
            elif result.is_integer:
                return (str(int(result)), 'number')
            else:
                return (_pretty(result), 'number' if result.is_rational else 'irrational')
        except Exception:
            return None

    def preview_label(self, a, b, ctx):
        b_disp = ctx.get('target_original') or self._disp(b)
        return f"{b_disp} × {self._disp(a)}"

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile
        from merge_engine import _pretty
        a_expr = self._expr(a)
        b_expr = self._expr(b)
        try:
            result = sympy.simplify(sympy.sympify(a_expr) * sympy.sympify(b_expr))
            has_symbols = bool(result.free_symbols)
            if has_symbols:
                disp = _pretty(result)
                kind = 'expr'
            elif result.is_integer:
                disp = str(int(result))
                kind = 'number'
            else:
                disp = _pretty(result)
                kind = 'number' if result.is_rational else 'irrational'
            color = _Tile.color_for_kind(kind)
            print(f"[DIR_MUL] {a_expr} * {b_expr} -> {str(result)}")
            b.kind = kind
            b.set_label(disp)
            b.expr_str = str(result)
            b.set_cell_size(w_cells=1, h_cells=1,
                cell_size=b.cell_size, gutter=b.gutter)
            try:
                b.data.display = disp
            except Exception:
                pass
            b.base_color = color
            b.background_color = color
            b.drag_color = color
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[DIR_MUL_ERROR] {e}")
            return None



class DirectionalAddRule(MergeRule):
    priority = 6

    def _expr(self, t):
        if getattr(t, 'kind', '') == 'fraction':
            m = getattr(t.data, 'meta', {}) or {}
            n = m.get('numer_expr') or m.get('numer_disp', '0')
            d = m.get('denom_expr') or m.get('denom_disp', '1')
            return f"({n})/({d})"
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _disp(self, t):
        if getattr(t, 'kind', '') == 'fraction':
            m = getattr(t.data, 'meta', {}) or {}
            n = m.get('numer_disp', '?')
            d = m.get('denom_disp', '?')
            return f"{n}/{d}"
        d = getattr(t.data, 'display', None) if getattr(t, 'data', None) else None
        return str(d or self._expr(t)).strip()

    def can_apply(self, a, b, ctx):
        if ctx.get('spawn_direction') != 'right':
            return False
        from merge_engine import tile_state
        if tile_state(a) in ('armed_num', 'armed_expr', 'armed_frac', 'armed_frac_expr'):
            return False
        if tile_state(b) in ('armed_num', 'armed_expr', 'armed_frac', 'armed_frac_expr'):
            return False
        bad_kinds = ('op', 'eq', 'tool', 'num_tool', 'expr_tool')
        if getattr(a, 'kind', '') in bad_kinds:
            return False
        if getattr(b, 'kind', '') in bad_kinds:
            return False
        if not self._expr(a) or not self._expr(b):
            return False
        board = ctx.get('board')
        grid = board.grid if board else 60
        if not _started_adjacent(ctx.get('drag_start_center'), b, grid):
            return False
        return True

    def preview_result(self, a, b, ctx):
        import sympy
        from merge_engine import _pretty
        try:
            result = sympy.simplify(sympy.sympify(self._expr(a)) + sympy.sympify(self._expr(b)))
            if result.free_symbols:
                return (_pretty(result), 'expr', None)
            elif result.is_integer:
                return (str(int(result)), 'number', None)
            else:
                return (_pretty(result), 'number' if result.is_rational else 'irrational', None)
        except Exception:
            return None

    def preview_label(self, a, b, ctx):
        b_disp = ctx.get('target_original') or self._disp(b)
        return f"{b_disp} + {self._disp(a)}"

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile
        from merge_engine import _pretty
        a_expr = self._expr(a)
        b_expr = self._expr(b)
        try:
            result = sympy.simplify(sympy.sympify(a_expr) + sympy.sympify(b_expr))
            if result.free_symbols:
                disp = _pretty(result)
                kind = 'expr'
            elif result.is_integer:
                disp = str(int(result))
                kind = 'number'
            else:
                disp = _pretty(result)
                kind = 'number' if result.is_rational else 'irrational'
            color = _Tile.color_for_kind(kind)
            print(f"[DIR_ADD] {a_expr} + {b_expr} -> {str(result)}")
            b.kind = kind
            b.set_label(disp)
            b.expr_str = str(result)
            b.set_cell_size(w_cells=1, h_cells=1, cell_size=b.cell_size, gutter=b.gutter)
            try:
                b.data.display = disp
            except Exception:
                pass
            b.base_color = color
            b.background_color = color
            b.drag_color = color
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[DIR_ADD_ERROR] {e}")
            return None



class DiagonalLogRule(MergeRule):
    priority = 7

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _disp(self, t):
        d = getattr(t.data, 'display', None) if getattr(t, 'data', None) else None
        return str(d or self._expr(t)).strip()

    def can_apply(self, a, b, ctx):
        bad_kinds = ('op', 'eq', 'tool', 'num_tool', 'expr_tool', 'fraction')
        if getattr(a, 'kind', '') in bad_kinds:
            return False
        if getattr(b, 'kind', '') in bad_kinds:
            return False
        if not self._expr(a) or not self._expr(b):
            return False
        board = ctx.get('board')
        grid = board.grid if board else 60
        drag_start = ctx.get('drag_start_center')
        if drag_start is None:
            return False
        # Top-left diagonal cell of target
        tx, ty = b.center
        target_x = tx - grid
        target_y = ty - grid
        dist = ((drag_start[0] - target_x) ** 2 + (drag_start[1] - target_y) ** 2) ** 0.5
        return dist < grid * 0.8

    def preview_result(self, a, b, ctx):
        import sympy
        from merge_engine import _pretty
        try:
            base   = sympy.sympify(self._expr(a))
            arg    = sympy.sympify(self._expr(b))
            result = sympy.simplify(sympy.log(arg, base))
            if result.free_symbols:
                return (_pretty(result), 'expr', None)
            elif result.is_integer:
                return (str(int(result)), 'number', None)
            elif result.is_rational:
                return (_pretty(result), 'number', None)
            else:
                return (_pretty(result), 'irrational', None)
        except Exception:
            return None

    def preview_label(self, a, b, ctx):
        return f"log_{self._disp(a)}({self._disp(b)})"

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile
        from merge_engine import _pretty
        a_expr = self._expr(a)
        b_expr = self._expr(b)
        try:
            base   = sympy.sympify(a_expr)
            arg    = sympy.sympify(b_expr)
            result = sympy.simplify(sympy.log(arg, base))
            print(f"[DIAG_LOG] log_{a_expr}({b_expr}) -> {str(result)}")

            if result.free_symbols:
                disp = _pretty(result)
                kind = 'expr'
            elif result.is_integer:
                disp = str(int(result))
                kind = 'number'
            elif result.is_rational:
                disp = _pretty(result)
                kind = 'number'
            else:
                disp = _pretty(result)
                kind = 'irrational'

            color = _Tile.color_for_kind(kind)
            b.kind = kind
            b.set_label(disp)
            b.expr_str = str(result)
            b.set_cell_size(w_cells=1, h_cells=1, cell_size=b.cell_size, gutter=b.gutter)
            try:
                b.data.display = disp
            except Exception:
                pass
            b.base_color = color
            b.background_color = color
            b.drag_color = color
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[DIAG_LOG_ERROR] {e}")
            return None


class DiagonalPowerRule(MergeRule):
    priority = 7

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _disp(self, t):
        d = getattr(t.data, 'display', None) if getattr(t, 'data', None) else None
        return str(d or self._expr(t)).strip()

    def can_apply(self, a, b, ctx):
        bad_kinds = ('op', 'eq', 'tool', 'num_tool', 'expr_tool', 'fraction')
        if getattr(a, 'kind', '') in bad_kinds:
            return False
        if getattr(b, 'kind', '') in bad_kinds:
            return False
        if not self._expr(a) or not self._expr(b):
            return False
        board = ctx.get('board')
        grid = board.grid if board else 60
        drag_start = ctx.get('drag_start_center')
        if drag_start is None:
            return False
        # Check drag started from top-right diagonal cell of target
        tx, ty = b.center
        target_x = tx + grid
        target_y = ty - grid
        dist = ((drag_start[0] - target_x) ** 2 + (drag_start[1] - target_y) ** 2) ** 0.5
        return dist < grid * 0.8

    def preview_result(self, a, b, ctx):
        import sympy
        from merge_engine import _pretty
        try:
            base = sympy.sympify(self._expr(b))
            exp  = sympy.sympify(self._expr(a))
            result = sympy.simplify(base ** exp)
            if result.free_symbols:
                return (_pretty(result), 'expr', None)
            elif result.is_integer:
                return (str(int(result)), 'number', None)
            elif result.is_rational:
                return (_pretty(result), 'number', None)
            else:
                return (_pretty(result), 'irrational', None)
        except Exception:
            return None

    def preview_label(self, a, b, ctx):
        return f"{self._disp(b)} ^ {self._disp(a)}"

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile
        from merge_engine import _pretty
        a_expr = self._expr(a)
        b_expr = self._expr(b)
        try:
            base   = sympy.sympify(b_expr)
            exp    = sympy.sympify(a_expr)
            result = sympy.simplify(base ** exp)
            print(f"[DIAG_POW] {b_expr} ^ {a_expr} -> {str(result)}")

            if result.free_symbols:
                disp = _pretty(result)
                kind = 'expr'
            elif result.is_integer:
                disp = str(int(result))
                kind = 'number'
            elif result.is_rational:
                disp = _pretty(result)
                kind = 'number'
            else:
                disp = _pretty(result)
                kind = 'irrational'

            color = _Tile.color_for_kind(kind)
            b.kind = kind
            b.set_label(disp)
            b.expr_str = str(result)
            b.set_cell_size(w_cells=1, h_cells=1, cell_size=b.cell_size, gutter=b.gutter)
            try:
                b.data.display = disp
            except Exception:
                pass
            b.base_color = color
            b.background_color = color
            b.drag_color = color
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[DIAG_POW_ERROR] {e}")
            return None

class VerticalDivideRule(MergeRule):
    priority = 5

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _disp(self, t):
        d = getattr(t.data, 'display', None) if getattr(t, 'data', None) else None
        return str(d or self._expr(t)).strip()

    def _tile_kind(self, expr_str, tile):
        k = getattr(tile, 'kind', 'number')
        if k in ('expr', 'irrational', 'number'):
            return k
        try:
            import sympy
            sym = sympy.sympify(expr_str)
            if sym.free_symbols:
                return 'expr'
            if not sym.is_rational:
                return 'irrational'
            return 'number'
        except Exception:
            return 'number'

    def can_apply(self, a, b, ctx):
        if ctx.get('spawn_direction') != 'above':
            return False
        bad_kinds = ('op', 'eq', 'tool', 'num_tool', 'expr_tool', 'fraction')
        if getattr(a, 'kind', '') in bad_kinds:
            return False
        if getattr(b, 'kind', '') in bad_kinds:
            return False
        if not self._expr(a) or not self._expr(b):
            return False
        board = ctx.get('board')
        grid = board.grid if board else 60
        if not _started_adjacent(ctx.get('drag_start_center'), b, grid):
            return False
        return True

    def preview_result(self, a, b, ctx):
        import sympy
        from merge_engine import _pretty
        try:
            n = sympy.sympify(self._expr(b))
            d = sympy.sympify(self._expr(a))
            if not n.free_symbols and not d.free_symbols and d != 0:
                result = sympy.Rational(n) / sympy.Rational(d)
                if result.is_integer:
                    return (str(int(result)), 'number')
            nd = self._disp(b)
            dd = self._disp(a)
            return (f"{nd}/{dd}", 'fraction')
        except Exception:
            return None

    def preview_label(self, a, b, ctx):
        b_disp = ctx.get('target_original') or self._disp(b)
        return f"{b_disp} ÷ {self._disp(a)}"

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile
        numer_tile = b
        denom_tile = a
        numer_expr = self._expr(numer_tile)
        denom_expr = self._expr(denom_tile)
        numer_disp = self._disp(numer_tile)
        denom_disp = self._disp(denom_tile)
        try:
            n_sym = sympy.sympify(numer_expr)
            d_sym = sympy.sympify(denom_expr)
            if not n_sym.free_symbols and not d_sym.free_symbols and d_sym != 0:
                result = sympy.Rational(n_sym) / sympy.Rational(d_sym)
                if result.is_integer:
                    disp = str(int(result))
                    print(f"[VERT_DIV] {numer_expr}/{denom_expr} -> {disp} (integer)")
                    numer_tile.kind = 'number'
                    numer_tile.set_label(disp)
                    numer_tile.expr_str = disp
                    numer_tile.set_cell_size(w_cells=1, h_cells=1,
                        cell_size=numer_tile.cell_size, gutter=numer_tile.gutter)
                    return MergeResult(replace_tile=numer_tile, delete_tile=denom_tile)
        except Exception:
            pass
        n_kind = self._tile_kind(numer_expr, numer_tile)
        d_kind = self._tile_kind(denom_expr, denom_tile)
        kind_priority = {'expr': 2, 'irrational': 1, 'number': 0}
        frac_kind = n_kind if kind_priority.get(n_kind, 0) >= kind_priority.get(d_kind, 0) else d_kind
        is_expr = frac_kind in ('expr', 'irrational')
        # Always use fraction color regardless of content kind
        color = _Tile.color_for_kind(frac_kind)
        numer_tile.kind = 'fraction'
        numer_tile.set_cell_size(w_cells=1, h_cells=2,
            cell_size=numer_tile.cell_size, gutter=numer_tile.gutter)
        numer_tile.data.meta['numer_disp'] = numer_disp
        numer_tile.data.meta['denom_disp'] = denom_disp
        numer_tile.data.meta['numer_expr'] = numer_expr
        numer_tile.data.meta['denom_expr'] = denom_expr
        numer_tile.data.meta['is_expr']    = is_expr
        numer_tile.base_color       = color
        numer_tile.drag_color       = color
        numer_tile.background_color = color
        if hasattr(numer_tile, 'content_view') and numer_tile.content_view:
            numer_tile.content_view.background_color = color
        try:
            numer_tile._ensure_fraction_views()
            numer_tile._sync_fraction_from_meta()
            numer_tile.layout()
        except Exception as e:
            print(f"[VERT_DIV_FRAC_ERROR] {e}")
        print(f"[VERT_DIV] {numer_expr}/{denom_expr} -> fraction kind={frac_kind}")
        return MergeResult(replace_tile=numer_tile, delete_tile=denom_tile)


class DiagonalDecimalConcatRule(MergeRule):
    priority = 7

    def _is_plain_number(self, t):
        if getattr(t, 'kind', '') not in ('number', 'irrational'):
            return False
        expr = str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()
        try:
            float(expr)
            return True
        except ValueError:
            return False

    def _disp(self, t):
        d = getattr(t.data, 'display', None) if getattr(t, 'data', None) else None
        return str(d or getattr(t, 'text', '')).strip()

    def _compute(self, a_disp, b_disp):
        """Append a's digits after b's decimal point."""
        a_str = a_disp.lstrip('-')  # strip sign for appending
        if '.' in b_disp:
            result_str = f"{b_disp}{a_str}"
        else:
            result_str = f"{b_disp}.{a_str}"
        return result_str

    def can_apply(self, a, b, ctx):
        if not self._is_plain_number(a):
            return False
        if not self._is_plain_number(b):
            return False
        board = ctx.get('board')
        grid = board.grid if board else 60
        drag_start = ctx.get('drag_start_center')
        if drag_start is None:
            return False
        # Bottom-right diagonal cell of target
        tx, ty = b.center
        target_x = tx + grid
        target_y = ty + grid
        dist = ((drag_start[0] - target_x) ** 2 + (drag_start[1] - target_y) ** 2) ** 0.5
        return dist < grid * 0.8

    def preview_result(self, a, b, ctx):
        try:
            result_str = self._compute(self._disp(a), self._disp(b))
            float(result_str)  # validate
            return (result_str, 'number', None)
        except Exception:
            return None

    def preview_label(self, a, b, ctx):
        return self._compute(self._disp(a), self._disp(b))

    def apply(self, a, b, ctx):
        from tile import Tile as _Tile
        try:
            result_str = self._compute(self._disp(a), self._disp(b))
            float(result_str)  # validate
            print(f"[DIAG_DEC] {self._disp(b)} . {self._disp(a)} -> {result_str}")
            kind  = 'number'
            color = _Tile.color_for_kind(kind)
            b.kind = kind
            b.set_label(result_str)
            b.expr_str = result_str
            b.set_cell_size(w_cells=1, h_cells=1, cell_size=b.cell_size, gutter=b.gutter)
            try:
                b.data.display = result_str
            except Exception:
                pass
            b.base_color = color
            b.background_color = color
            b.drag_color = color
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[DIAG_DEC_ERROR] {e}")
            return None

class NegateOpRule(MergeRule):
    """
    '-' op tile merged with any value tile -> negate it directly.
    Uses sympy for clean display on expr/irrational tiles.
    - number -> -8 (or if already -8 -> 8)
    - expr   -> -x2 using sympy+_pretty
    - fraction -> negate numerator
    - num_op (+8) -> strip arm, negate -> -8 as number
    """
    priority = 8

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _is_minus_op(self, t):
        return getattr(t, 'kind', '') == 'op' and self._expr(t) == '-'

    def _negate_str(self, s):
        s = s.strip()
        if s.startswith('-'):
            return s[1:].strip()
        return f"-{s}"

    def can_apply(self, a, b, ctx):
        if self._is_minus_op(a):
            return tile_state(b) in ('number', 'expr', 'frac_num', 'frac_expr',
                                     'irrational', 'armed_num')
        if self._is_minus_op(b):
            return tile_state(a) in ('number', 'expr', 'frac_num', 'frac_expr',
                                     'irrational', 'armed_num')
        return False

    def apply(self, a, b, ctx):
        import sympy
        op     = a if self._is_minus_op(a) else b
        target = b if self._is_minus_op(a) else a
        st     = tile_state(target)

        # Strip armed op, negate the number part
        if st == 'armed_num':
            raw_expr = self._expr(target)
            num_str = raw_expr
            for suffix in ('+', '-', '*', '^', '/'):
                if raw_expr.endswith(suffix):
                    num_str = raw_expr[:-1].strip()
                    break
            neg_str = self._negate_str(num_str)
            try:
                target.kind = 'number'
                target.is_result = False
            except Exception:
                pass
            try:
                target.set_label(neg_str)
            except Exception:
                target.text = neg_str
            try:
                target.data.display = neg_str
                target.expr_str = neg_str
            except Exception:
                pass
            print(f"[NEG_OP] stripped arm, negated -> {neg_str}")
            return MergeResult(replace_tile=target, new_display=neg_str,
                               new_expr_str=neg_str, delete_tile=op)

        # Fraction: negate numerator display/expr
        if st in ('frac_num', 'frac_expr'):
            m = getattr(target.data, 'meta', {}) or {}
            nd = m.get('numer_disp', '') or ''
            ne = m.get('numer_expr', '') or ''
            m['numer_disp'] = self._negate_str(nd)
            m['numer_expr'] = self._negate_str(ne)
            denom_e = m.get('denom_expr') or m.get('denom_disp', '1')
            target.expr_str = f"({m['numer_expr']})/({denom_e})"
            try:
                target._sync_fraction_from_meta()
                target.layout()
            except Exception:
                pass
            print(f"[NEG_OP] fraction numerator negated")
            return MergeResult(replace_tile=target, new_display=None,
                               new_expr_str=target.expr_str, delete_tile=op)

        # number or expr: use sympy for clean pretty display
        raw = self._expr(target)
        try:
            sym     = sympy.sympify(raw)
            neg_sym = -sym
            neg_expr = str(neg_sym)
            neg_disp = _pretty(neg_sym)
        except Exception:
            neg_expr = self._negate_str(raw)
            neg_disp = neg_expr

        try:
            target.set_label(neg_disp)
        except Exception:
            target.text = neg_disp
        try:
            target.data.display = neg_disp
            target.expr_str = neg_expr
        except Exception:
            pass
        print(f"[NEG_OP] {raw} -> {neg_disp}")
        return MergeResult(replace_tile=target, new_display=neg_disp,
                           new_expr_str=neg_expr, delete_tile=op)


class ConcatNumbersRule(MergeRule):
    priority = 10

    def can_apply(self, a, b, ctx):
        def is_plain_number(t):
            if getattr(t, 'kind', '') != 'number':
                return False
            txt = str(getattr(t, 'text', '') or '').strip()
            return txt.lstrip('-').isdigit()
        if not (is_plain_number(a) and is_plain_number(b)):
            return False
        board = ctx.get('board')
        drag_start = ctx.get('drag_start_center')
        if board and drag_start:
            if _started_adjacent(drag_start, b, board.grid):
                return False
        return True

    def preview_label(self, a, b, ctx):
        ta = str(getattr(a, 'text', '') or '').strip()
        tb = ctx.get('target_original') or str(getattr(b, 'text', '') or '').strip()
        return f"{tb}{ta}"

    def apply(self, a, b, ctx):
        ta = str(getattr(a, 'text', '') or '').strip()
        tb = str(getattr(b, 'text', '') or '').strip()
        combined = tb + ta
        b.text = combined
        b.expr_str = combined
        try:
            b.set_label(combined)
        except Exception:
            pass
        try:
            b.data.display = combined
        except Exception:
            pass
        print(f"[CONCAT] {tb} + {ta} -> {combined}")
        return MergeResult(replace_tile=b, delete_tile=a)


class AppendNumberToExprRule(MergeRule):
    """
    number onto expr -> extend expression (only if expr ends with an operator)

    Example:
      4 onto "3 +" -> display: "3 + 4"  expr: "3+4"
    """
    priority = 30

    def _disp(self, t):
        return str(getattr(t, 'display', getattr(t, 'text', '')) or '').strip()

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def can_apply(self, a, b, ctx):
        if getattr(a, 'kind', '') != 'number':
            return False

        b_kind = getattr(b, 'kind', '')
        if b_kind != 'expr':
            return False

        bexpr = self._expr(b)
        return len(bexpr) > 0 and bexpr[-1] in ('+', '-', '*', '/', '(')

    def apply(self, a, b, ctx):
        disp = f"{self._disp(b)} {self._disp(a)}"
        expr = f"{self._expr(b)}{self._expr(a)}"

        return MergeResult(
            replace_tile=b,
            new_display=disp,
            new_expr_str=expr,
            delete_tile=a
        )
# FractionFromDivisionRule removed - ÷ button now spawns blank fraction directly

class ToolWrapSqrtRule(MergeRule):
    # Replaced by SqrtRule - kept as dead stub so existing imports don't break
    priority = 999
    def can_apply(self, a, b, ctx): return False
    def apply(self, a, b, ctx): return None
class SqrtRule(MergeRule):
    """
    √  + number/expr  -> evaluate or wrap symbolically
    ∛  + number/expr  -> cube root
    ⁿ√ + number       -> arm with n (display ⁿ√, consume number)
    ⁿ√:n + number/expr -> evaluate nth root

    Sticky: snaps back, result spawns opposite side, armed state persists.
    """
    priority = 39

    SUP = str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _is_sqrt_tool(self, t):
        if getattr(t, 'kind', '') != 'tool':
            return False
        e = self._expr(t)
        return e in ('sqrt', 'cbrt', 'nthrt') or e.startswith('nthrt:')

    def _parse(self, t):
        """Returns (variant, n) where variant is 'sqrt','cbrt','nthrt' and n is int or None."""
        e = self._expr(t)
        if e == 'sqrt':
            return 'sqrt', None
        if e == 'cbrt':
            return 'cbrt', None
        if e == 'nthrt':
            return 'nthrt', None
        if e.startswith('nthrt:'):
            try:
                return 'nthrt', int(e.split(':')[1])
            except Exception:
                return 'nthrt', None
        return None, None

    def can_apply(self, a, b, ctx):
        if self._is_sqrt_tool(a):
            return tile_state(b) in ('number', 'expr', 'frac_num', 'frac_expr')
        if self._is_sqrt_tool(b):
            return tile_state(a) in ('number', 'expr', 'frac_num', 'frac_expr')
        return False

    def _to_sym(self, t):
        import sympy
        if getattr(t, 'kind', '') == 'fraction':
            m = getattr(t.data, 'meta', {}) or {}
            if m.get('is_expr'):
                return sympy.sympify(str(getattr(t, 'expr_str', '') or ''))
            try:
                n = int(float(m.get('numer_expr') or m.get('numer_disp', '0')))
                d = int(float(m.get('denom_expr') or m.get('denom_disp', '1')))
                return sympy.Rational(n, d)
            except Exception:
                return sympy.sympify(str(getattr(t, 'expr_str', '') or ''))
        return sympy.sympify(str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip())

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile
        sqrt_tile = a if self._is_sqrt_tool(a) else b
        arg_tile  = b if self._is_sqrt_tool(a) else a
        variant, n = self._parse(sqrt_tile)

        if variant == 'nthrt' and n is None and tile_state(arg_tile) == 'number':
            try:
                n_val = int(str(arg_tile.data.display or self._expr(arg_tile)).strip())
                if n_val < 2:
                    return None
            except Exception:
                return None
            sup_disp = str(n_val).translate(self.SUP)
            new_disp = f"{sup_disp}√"
            new_expr = f"nthrt:{n_val}"
            try:
                sqrt_tile.expr_str = new_expr
            except Exception:
                pass
            try:
                sqrt_tile.set_label(new_disp)
            except Exception:
                sqrt_tile.text = new_disp
            try:
                sqrt_tile.data.display = new_disp
            except Exception:
                pass
            print(f"[SQRT] armed nth root: {new_disp}")
            return MergeResult(no_sticky=True, replace_tile=sqrt_tile, delete_tile=arg_tile)

        arg_sym = self._to_sym(arg_tile)

        try:
            if variant == 'sqrt':
                result = sympy.simplify(sympy.sqrt(arg_sym))
                disp_prefix = '√'
            elif variant == 'cbrt':
                result = sympy.simplify(sympy.root(arg_sym, 3))
                disp_prefix = '∛'
            elif variant == 'nthrt' and n is not None:
                result = sympy.simplify(sympy.root(arg_sym, n))
                sup_disp = str(n).translate(self.SUP)
                disp_prefix = f"{sup_disp}√"
            else:
                return None

            arg_disp = _tile_disp(arg_tile)
            new_disp = f"{disp_prefix}({arg_disp})"
            try:
                sqrt_tile.set_label(new_disp)
            except Exception:
                sqrt_tile.text = new_disp
            try:
                sqrt_tile.data.display = new_disp
            except Exception:
                pass

            if result.free_symbols:
                disp = _pretty(result)
                spawn_spec = {
                    'text': disp, 'kind': 'expr',
                    'color': _Tile.color_for_kind('expr'),
                    'expr_str': str(result), 'display': disp,
                }
            else:
                spawn_spec = _make_numeric_spec(result)

            return MergeResult(
                no_sticky=True,
                replace_tile=sqrt_tile,
                delete_tile=arg_tile,
                spawn_spec=spawn_spec,
                spawn_direction=ctx.get('spawn_direction', 'right'),
            )

        except Exception as e:
            print(f"[SQRT_ERROR] {e}")
            import traceback
            traceback.print_exc()
            return None
    
class LogRule(MergeRule):
    """
    log + number  -> arm with base: display log₂, expr_str log:2
    log:n + number/expr -> evaluate log base n
    ln + number/expr    -> evaluate natural log directly (no arming)
    """
    priority = 41

    SUB = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _is_log_tool(self, t):
        if getattr(t, 'kind', '') != 'tool':
            return False
        e = self._expr(t)
        return e in ('log', 'ln') or e.startswith('log:')

    def _parse(self, t):
        """Returns ('log', base) or ('ln', None)."""
        e = self._expr(t)
        if e == 'ln':
            return 'ln', None
        if e == 'log':
            return 'log', None
        if e.startswith('log:'):
            try:
                return 'log', int(e.split(':')[1])
            except Exception:
                return 'log', None
        return None, None

    def can_apply(self, a, b, ctx):
        if self._is_log_tool(a):
            return tile_state(b) in ('number', 'expr', 'frac_num', 'frac_expr')
        if self._is_log_tool(b):
            return tile_state(a) in ('number', 'expr', 'frac_num', 'frac_expr')
        return False

    def _to_sym(self, t):
        import sympy
        if getattr(t, 'kind', '') == 'fraction':
            m = getattr(t.data, 'meta', {}) or {}
            if m.get('is_expr'):
                return sympy.sympify(str(getattr(t, 'expr_str', '') or ''))
            try:
                n = int(float(m.get('numer_expr') or m.get('numer_disp', '0')))
                d = int(float(m.get('denom_expr') or m.get('denom_disp', '1')))
                return sympy.Rational(n, d)
            except Exception:
                return sympy.sympify(str(getattr(t, 'expr_str', '') or ''))
        return sympy.sympify(
            str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()
        )

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile
        log_tile = a if self._is_log_tool(a) else b
        arg_tile = b if self._is_log_tool(a) else a
        variant, base = self._parse(log_tile)

        if variant == 'log' and base is None and tile_state(arg_tile) == 'number':
            try:
                base_val = int(str(arg_tile.data.display or self._expr(arg_tile)).strip())
                if base_val < 2:
                    return None
            except Exception:
                return None
            sub_disp = str(base_val).translate(self.SUB)
            new_disp = f"log{sub_disp}"
            new_expr = f"log:{base_val}"
            try:
                log_tile.expr_str = new_expr
            except Exception:
                pass
            try:
                log_tile.set_label(new_disp)
            except Exception:
                log_tile.text = new_disp
            try:
                log_tile.data.display = new_disp
            except Exception:
                pass
            print(f"[LOG] armed with base {base_val}")
            return MergeResult(no_sticky=True, replace_tile=log_tile, delete_tile=arg_tile)

        arg_sym = self._to_sym(arg_tile)

        try:
            if variant == 'ln':
                result = sympy.simplify(sympy.log(arg_sym))
                log_disp = 'ln'
            elif variant == 'log' and base is not None:
                result = sympy.simplify(sympy.log(arg_sym, base))
                sub_disp = str(base).translate(self.SUB)
                log_disp = f"log{sub_disp}"
            else:
                return None

            arg_disp = _tile_disp(arg_tile)
            new_log_disp = f"{log_disp}({arg_disp})"
            try:
                log_tile.set_label(new_log_disp)
            except Exception:
                log_tile.text = new_log_disp
            try:
                log_tile.data.display = new_log_disp
            except Exception:
                pass

            if result.free_symbols:
                disp = _pretty(result)
                spawn_spec = {
                    'text': disp, 'kind': 'expr',
                    'color': _Tile.color_for_kind('expr'),
                    'expr_str': str(result), 'display': disp,
                }
            else:
                spawn_spec = _make_numeric_spec(result)

            return MergeResult(
                no_sticky=True,
                replace_tile=log_tile,
                delete_tile=arg_tile,
                spawn_spec=spawn_spec,
                spawn_direction=ctx.get('spawn_direction', 'right'),
            )

        except Exception as e:
            print(f"[LOG_ERROR] {e}")
            import traceback
            traceback.print_exc()
            return None


class SumRule(MergeRule):
    priority = 38

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _is_sum_tool(self, t):
        if getattr(t, 'kind', '') != 'tool':
            return False
        e = self._expr(t)
        return e in ('sum', 'sum_armed')

    def _is_armed(self, t):
        return getattr(t, 'kind', '') == 'tool' and self._expr(t) == 'sum_armed'

    def can_apply(self, a, b, ctx):
        if self._is_sum_tool(a):
            st = tile_state(b)
            if self._is_armed(a):
                return st in ('number',)
            return st in ('expr', 'frac_expr', 'irrational')
        if self._is_sum_tool(b):
            st = tile_state(a)
            if self._is_armed(b):
                return st in ('number',)
            return st in ('expr', 'frac_expr', 'irrational')
        return False

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile

        sum_tile = a if self._is_sum_tool(a) else b
        arg_tile = b if self._is_sum_tool(a) else a

        if not self._is_armed(sum_tile):
            expr_str = str(getattr(arg_tile, 'expr_str',
                           getattr(arg_tile, 'text', '')) or '').strip()
            arg_disp = _tile_disp(arg_tile)
            new_disp = f"Σ({arg_disp})"
            try:
                sum_tile.expr_str = 'sum_armed'
            except Exception:
                pass
            try:
                sum_tile.data.meta['sum_expr'] = expr_str
                sum_tile.data.meta['sum_disp'] = arg_disp
            except Exception:
                pass
            try:
                sum_tile.set_label(new_disp)
            except Exception:
                sum_tile.text = new_disp
            try:
                sum_tile.data.display = new_disp
            except Exception:
                pass
            print(f"[SUM] armed with expr: {expr_str}")
            return MergeResult(no_sticky=True, replace_tile=sum_tile, delete_tile=arg_tile)

        m = getattr(sum_tile.data, 'meta', {}) or {}
        sum_expr_str = m.get('sum_expr', '')
        sum_disp = m.get('sum_disp', '?')

        try:
            n_val = int(str(arg_tile.data.display or self._expr(arg_tile)).strip())
            if n_val < 1:
                print(f"[SUM] n must be >= 1")
                return None
        except Exception as e:
            print(f"[SUM_ERROR] bad n: {e}")
            return None

        try:
            f = sympy.sympify(sum_expr_str)
            free = sorted(f.free_symbols, key=str)

            new_disp = f"Σ({sum_disp},{n_val})"
            try:
                sum_tile.set_label(new_disp)
            except Exception:
                sum_tile.text = new_disp
            try:
                sum_tile.data.display = new_disp
            except Exception:
                pass

            if not free:
                result = sympy.simplify(f * n_val)
            else:
                sym = free[0]
                result = sympy.summation(f, (sym, 1, n_val))
                result = sympy.simplify(result)

            print(f"[SUM] Σ({sum_expr_str}, 1..{n_val}) = {result}")

            if result.free_symbols:
                disp = _pretty(result)
                spawn_spec = {
                    'text': disp, 'kind': 'expr',
                    'color': _Tile.color_for_kind('expr'),
                    'expr_str': str(result), 'display': disp,
                }
            else:
                spawn_spec = _make_numeric_spec(result)

            return MergeResult(
                no_sticky=True,
                replace_tile=sum_tile,
                delete_tile=arg_tile,
                spawn_spec=spawn_spec,
                spawn_direction=ctx.get('spawn_direction', 'right'),
            )

        except Exception as e:
            print(f"[SUM_ERROR] {e}")
            import traceback
            traceback.print_exc()
            return None

class ToolTrashDeleteRule(MergeRule):
    """
    🗑 tool dropped onto a tile deletes the target tile.
    The trash tool survives (acts like a reusable tool).
    """
    priority = 50

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def can_apply(self, a, b, ctx):
        if getattr(a, 'kind', '') != 'tool':
            return False
        if self._expr(a) != 'trash':
            return False
        # delete anything except tools (so you can't accidentally delete the trash)
        return getattr(b, 'kind', '') != 'tool'

    def apply(self, a, b, ctx):
        # Delete target tile 'b'; keep tool 'a' untouched
        return MergeResult(
            replace_tile=None,
            new_display=None,
            new_expr_str=None,
            delete_tile=b
        )
class FactorRule(MergeRule):
    """
    factor tool + number -> spawn prime factor tiles
    factor tool + expr   -> spawn algebraic factor tiles
    Handles placement collision-checking. Uses no_sticky=True.
    """
    priority = 45

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _is_factor_tool(self, t):
        return getattr(t, 'kind', '') == 'tool' and self._expr(t) == 'factor'

    def can_apply(self, a, b, ctx):
        if self._is_factor_tool(a):
            return tile_state(b) in ('number', 'expr', 'armed_expr')
        if self._is_factor_tool(b):
            return tile_state(a) in ('number', 'expr', 'armed_expr')
        return False

    def _find_free_cell(self, board, cx, cy, new_tile, occupied):
        """Find nearest free snapped cell using outward spiral search."""
        g = board.grid
        for radius in range(0, 12):
            for row in range(-radius, radius + 1):
                for col in range(-radius, radius + 1):
                    if abs(row) != radius and abs(col) != radius:
                        continue
                    tx = cx + col * g
                    ty = cy + row * g
                    snap_x, snap_y = board.snap_center(tx, ty, new_tile)
                    new_tile.center = (snap_x, snap_y)
                    rf = new_tile.frame
                    if rf.x < 0 or rf.y < 0:
                        continue
                    if rf.x + rf.width > board.width:
                        continue
                    if rf.y + rf.height > board.height:
                        continue
                    # Check exclusion zone
                    if board.exclusion_bottom_y and rf.y + rf.height > board.exclusion_bottom_y:
                        continue
                    # Check against already-placed tiles and occupied set
                    clear = True
                    for (ox, oy) in occupied:
                        if abs(snap_x - ox) < g * 0.9 and abs(snap_y - oy) < g * 0.9:
                            clear = False
                            break
                    if not clear:
                        continue
                    # Check against existing board tiles
                    for t in board.tiles:
                        try:
                            tf = t.frame
                            if (rf.x < tf.x + tf.width and rf.x + rf.width > tf.x and
                                    rf.y < tf.y + tf.height and rf.y + rf.height > tf.y):
                                clear = False
                                break
                        except Exception:
                            pass
                    if clear:
                        return snap_x, snap_y
        return board.snap_center(cx, cy, new_tile)

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile
        factor_tile = a if self._is_factor_tool(a) else b
        target = b if self._is_factor_tool(a) else a
        board = ctx.get('board')
        if board is None:
            return None

        st = tile_state(target)
        cx, cy = target.center
        specs = []

        if st == 'number':
            try:
                n = int(str(target.data.display or self._expr(target)).strip())
                fd = sympy.factorint(n)
                factors = []
                for prime in sorted(fd.keys()):
                    factors.extend([prime] * fd[prime])
                if len(factors) <= 1:
                    print(f"[FACTOR] {n} is prime, cannot factor")
                    return None
                for f in factors:
                    specs.append({
                        'text': str(f), 'kind': 'number',
                        'color': _Tile.color_for_kind('number'),
                        'expr_str': str(f), 'display': str(f),
                    })
            except Exception as e:
                print(f"[FACTOR_NUM_ERROR] {e}")
                return None

        elif st in ('expr', 'armed_expr'):
            try:
                expr = sympy.sympify(self._expr(target))
                factored = sympy.factor(expr)
                if factored.func == sympy.Mul:
                    args = [arg for arg in factored.args if arg != sympy.Integer(1)]
                else:
                    args = [factored]
                if len(args) <= 1:
                    print(f"[FACTOR] expression already irreducible")
                    return None
                for arg in args:
                    disp = _pretty(arg)
                    specs.append({
                        'text': disp, 'kind': 'expr',
                        'color': _Tile.color_for_kind('expr'),
                        'expr_str': str(arg), 'display': disp,
                    })
            except Exception as e:
                print(f"[FACTOR_EXPR_ERROR] {e}")
                return None

        if not specs:
            return None

        board._delete_tile(target)

        g = board.grid
        occupied = set()
        search_cx, search_cy = cx, cy

        for spec in specs:
            new_tile = board.create_tile_from_spec(spec)
            snap_x, snap_y = self._find_free_cell(board, search_cx, search_cy, new_tile, occupied)
            new_tile.center = (snap_x, snap_y)
            board.add_subview(new_tile)
            board.tiles.append(new_tile)
            board._enforce_exclusion(new_tile)
            occupied.add((snap_x, snap_y))
            search_cx = snap_x + g
            search_cy = snap_y
            print(f"[FACTOR] spawned {spec['text']} at ({snap_x:.0f},{snap_y:.0f})")

        if bool(getattr(factor_tile, 'sticky', False)):
            snap_x, snap_y = board.snap_center(cx, cy, factor_tile)
            factor_tile.center = (snap_x, snap_y)
            board._enforce_exclusion(factor_tile)
            print(f"[FACTOR] sticky snap-back to ({snap_x:.0f},{snap_y:.0f})")
            return MergeResult(no_sticky=True, keep_both=True)

        return MergeResult(no_sticky=True)
    
class TrigRule(MergeRule):
    """
    trig tool + number/expr/fraction -> evaluate or wrap symbolically.
    Updates trig tile display to show argument. Spawns result. Keeps trig tile.
    Reads board.trig_mode ('rad' or 'deg') from ctx.
    """
    priority = 42

    TRIG_FUNCS = {
        'sin':    'sin',
        'cos':    'cos',
        'tan':    'tan',
        'arcsin': 'asin',
        'arccos': 'acos',
        'arctan': 'atan',
    }
    DISP_NAMES = {
        'sin':    'sin',
        'cos':    'cos',
        'tan':    'tan',
        'arcsin': 'sin⁻¹',
        'arccos': 'cos⁻¹',
        'arctan': 'tan⁻¹',
    }
    INVERSE_OPS = {'arcsin', 'arccos', 'arctan'}

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _is_trig_tool(self, t):
        return getattr(t, 'kind', '') == 'tool' and self._expr(t) in self.TRIG_FUNCS

    def can_apply(self, a, b, ctx):
        if self._is_trig_tool(a):
            return tile_state(b) in ('number', 'expr', 'frac_num', 'frac_expr')
        if self._is_trig_tool(b):
            return tile_state(a) in ('number', 'expr', 'frac_num', 'frac_expr')
        return False

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile
        trig_tile = a if self._is_trig_tool(a) else b
        arg_tile  = b if self._is_trig_tool(a) else a
        board = ctx.get('board')
        trig_mode = getattr(board, 'trig_mode', 'deg') if board else 'deg'

        func_name = self._expr(trig_tile)
        sympy_name = self.TRIG_FUNCS.get(func_name)
        disp_name  = self.DISP_NAMES.get(func_name, func_name)
        sympy_func = getattr(sympy, sympy_name, None)
        if sympy_func is None:
            return None

        arg_kind = getattr(arg_tile, 'kind', '')
        if arg_kind == 'fraction':
            m = getattr(arg_tile.data, 'meta', {}) or {}
            if m.get('is_expr'):
                arg_sym = sympy.sympify(str(getattr(arg_tile, 'expr_str', '') or ''))
                is_numeric_arg = False
            else:
                try:
                    n = float(m.get('numer_expr') or m.get('numer_disp', '0'))
                    d = float(m.get('denom_expr') or m.get('denom_disp', '1'))
                    arg_sym = sympy.Rational(int(n), int(d))
                    is_numeric_arg = True
                except Exception:
                    arg_sym = sympy.sympify(str(getattr(arg_tile, 'expr_str', '') or ''))
                    is_numeric_arg = False
        else:
            arg_str = str(getattr(arg_tile, 'expr_str', getattr(arg_tile, 'text', '')) or '').strip()
            # Use Rational for simple numeric strings to keep sympy exact
            try:
                arg_sym = sympy.Rational(arg_str)
            except Exception:
                arg_sym = sympy.sympify(arg_str)
            is_numeric_arg = not bool(arg_sym.free_symbols)

        arg_disp = _tile_disp(arg_tile)
        new_trig_disp = f"{disp_name}({arg_disp})"
        try:
            trig_tile.set_label(new_trig_disp)
        except Exception:
            trig_tile.text = new_trig_disp
        try:
            trig_tile.data.display = new_trig_disp
        except Exception:
            pass

        spawn_spec = None
        try:
            if is_numeric_arg:
                eval_arg = arg_sym
                if trig_mode == 'deg' and func_name not in self.INVERSE_OPS:
                    eval_arg = arg_sym * sympy.pi / 180
                result = sympy.simplify(sympy_func(eval_arg))
                if trig_mode == 'deg' and func_name in self.INVERSE_OPS:
                    result = sympy.simplify(result * 180 / sympy.pi)
                    # Force clean numeric result - avoids irrational forms like 188.49.../pi
                    if not result.free_symbols:
                        try:
                            # Try to get a clean rational (e.g. 60, 45, 30)
                            r = sympy.nsimplify(result, rational=True, tolerance=1e-9)
                            if r.is_rational:
                                result = r
                            else:
                                result = sympy.N(result, 10)
                        except Exception:
                            result = sympy.N(result, 10)
                if result.free_symbols:
                    disp = _pretty(result)
                    spawn_spec = {
                        'text': disp, 'kind': 'expr',
                        'color': _Tile.color_for_kind('expr'),
                        'expr_str': str(result), 'display': disp,
                    }
                else:
                    spawn_spec = _make_numeric_spec(result)
            else:
                result = sympy.simplify(sympy_func(arg_sym))
                if result.free_symbols:
                    disp = _pretty(result)
                    spawn_spec = {
                        'text': disp, 'kind': 'expr',
                        'color': _Tile.color_for_kind('expr'),
                        'expr_str': str(result), 'display': disp,
                    }
                else:
                    spawn_spec = _make_numeric_spec(result)
        except Exception as e:
            print(f"[TRIG_EVAL_ERROR] {e}")
            disp = new_trig_disp
            spawn_spec = {
                'text': disp, 'kind': 'expr',
                'color': _Tile.color_for_kind('expr'),
                'expr_str': f"{func_name}({self._expr(arg_tile)})", 'display': disp,
            }

        return MergeResult(
            no_sticky=True,
            replace_tile=trig_tile,
            delete_tile=arg_tile,
            spawn_spec=spawn_spec,
            spawn_direction=ctx.get('spawn_direction', 'right'),
        )

class DiffRule(MergeRule):
    """
    d/dx tool + expr/number -> differentiate w.r.t first free symbol.
    Updates tool display, spawns result. Consumes expr tile.
    """
    priority = 43

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _is_diff_tool(self, t):
        return getattr(t, 'kind', '') == 'tool' and self._expr(t) == 'diff'

    def can_apply(self, a, b, ctx):
        if self._is_diff_tool(a):
            return tile_state(b) in ('number', 'expr', 'frac_num', 'frac_expr', 'irrational')
        if self._is_diff_tool(b):
            return tile_state(a) in ('number', 'expr', 'frac_num', 'frac_expr', 'irrational')
        return False

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile

        diff_tile = a if self._is_diff_tool(a) else b
        arg_tile  = b if self._is_diff_tool(a) else a

        arg_str = str(getattr(arg_tile, 'expr_str', getattr(arg_tile, 'text', '')) or '').strip()
        try:
            arg_sym = sympy.sympify(arg_str)
        except Exception as e:
            print(f"[DIFF_ERROR] parse: {e}")
            return None

        free = sorted(arg_sym.free_symbols, key=str)
        sym = free[0] if free else sympy.Symbol('x')

        arg_disp = _tile_disp(arg_tile)
        new_disp = f"d/dx({arg_disp})"
        try:
            diff_tile.set_label(new_disp)
        except Exception:
            diff_tile.text = new_disp
        try:
            diff_tile.data.display = new_disp
        except Exception:
            pass

        try:
            result = sympy.diff(arg_sym, sym)
            result = sympy.simplify(result)
            print(f"[DIFF] d/d{sym}({arg_sym}) = {result}")

            if result.free_symbols:
                disp = _pretty(result)
                spawn_spec = {
                    'text': disp, 'kind': 'expr',
                    'color': _Tile.color_for_kind('expr'),
                    'expr_str': str(result), 'display': disp,
                }
            else:
                spawn_spec = _make_numeric_spec(result)

        except Exception as e:
            print(f"[DIFF_ERROR] eval: {e}")
            return None

        return MergeResult(
            no_sticky=True,
            replace_tile=diff_tile,
            delete_tile=arg_tile,
            spawn_spec=spawn_spec,
            spawn_direction=ctx.get('spawn_direction', 'right'),
        )


class IntegrateRule(MergeRule):
    """
    ∫ tool + expr/number -> integrate w.r.t first free symbol (or x for constants).
    Updates tool display, spawns result. Consumes expr tile. No +C.
    """
    priority = 44

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _is_integrate_tool(self, t):
        return getattr(t, 'kind', '') == 'tool' and self._expr(t) == 'integrate'

    def can_apply(self, a, b, ctx):
        if self._is_integrate_tool(a):
            return tile_state(b) in ('number', 'expr', 'frac_num', 'frac_expr', 'irrational')
        if self._is_integrate_tool(b):
            return tile_state(a) in ('number', 'expr', 'frac_num', 'frac_expr', 'irrational')
        return False

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile

        int_tile = a if self._is_integrate_tool(a) else b
        arg_tile = b if self._is_integrate_tool(a) else a

        arg_str = str(getattr(arg_tile, 'expr_str', getattr(arg_tile, 'text', '')) or '').strip()
        try:
            arg_sym = sympy.sympify(arg_str)
        except Exception as e:
            print(f"[INTEGRATE_ERROR] parse: {e}")
            return None

        free = sorted(arg_sym.free_symbols, key=str)
        sym = free[0] if free else sympy.Symbol('x')

        arg_disp = _tile_disp(arg_tile)
        new_disp = f"∫({arg_disp})"
        try:
            int_tile.set_label(new_disp)
        except Exception:
            int_tile.text = new_disp
        try:
            int_tile.data.display = new_disp
        except Exception:
            pass

        try:
            result = sympy.integrate(arg_sym, sym)
            result = sympy.simplify(result)
            print(f"[INTEGRATE] ∫({arg_sym})d{sym} = {result}")

            if result.free_symbols:
                disp = _pretty(result)
                spawn_spec = {
                    'text': disp, 'kind': 'expr',
                    'color': _Tile.color_for_kind('expr'),
                    'expr_str': str(result), 'display': disp,
                }
            else:
                spawn_spec = _make_numeric_spec(result)

        except Exception as e:
            print(f"[INTEGRATE_ERROR] eval: {e}")
            return None

        return MergeResult(
            no_sticky=True,
            replace_tile=int_tile,
            delete_tile=arg_tile,
            spawn_spec=spawn_spec,
            spawn_direction=ctx.get('spawn_direction', 'right'),
        )


class NegateRule(MergeRule):
    priority = 46

    def can_apply(self, a, b, ctx):
        op_tile = a if getattr(a, 'kind', '') == 'op' else (b if getattr(b, 'kind', '') == 'op' else None)
        other   = b if op_tile is a else a
        if op_tile is None:
            return False
        if str(getattr(op_tile, 'text', '') or '').strip() != '-':
            return False
        if getattr(other, 'kind', '') in ('op', 'eq'):
            return False
        return True

    def preview_label(self, a, b, ctx):
        op_tile = a if getattr(a, 'kind', '') == 'op' else b
        other   = b if op_tile is a else a
        if other is b:
            other_disp = ctx.get('target_original') or str(getattr(other, 'text', '') or '').strip()
        else:
            d = getattr(other.data, 'display', None) if getattr(other, 'data', None) else None
            other_disp = str(d or getattr(other, 'text', '') or '').strip()
        return f"-{other_disp}"

    def apply(self, a, b, ctx):
        op_tile = a if getattr(a, 'kind', '') == 'op' else b
        other   = b if op_tile is a else a
        from merge_engine import _pretty
        import sympy
        expr_str = str(getattr(other, 'expr_str', getattr(other, 'text', '')) or '').strip()
        try:
            neg  = sympy.simplify(-sympy.sympify(expr_str))
            disp = _pretty(neg)
            neg_expr = str(neg)
        except Exception:
            disp = f"-{expr_str}"
            neg_expr = disp
        other.expr_str = neg_expr
        other.set_label(disp)
        try:
            other.data.display = disp
        except Exception:
            pass
        return MergeResult(replace_tile=other, delete_tile=op_tile)



class FactorialRule(MergeRule):
    priority = 47

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _is_factorial_tool(self, t):
        return getattr(t, 'kind', '') == 'tool' and self._expr(t) == 'factorial'

    def can_apply(self, a, b, ctx):
        if self._is_factorial_tool(a):
            return tile_state(b) == 'number'
        if self._is_factorial_tool(b):
            return tile_state(a) == 'number'
        return False

    def apply(self, a, b, ctx):
        import sympy
        from tile import Tile as _Tile

        fact_tile = a if self._is_factorial_tool(a) else b
        arg_tile  = b if self._is_factorial_tool(a) else a

        try:
            n_val = int(str(getattr(arg_tile.data, 'display', None) or
                           getattr(arg_tile, 'text', '')).strip())
            if n_val < 0:
                print(f"[FACTORIAL] negative input")
                return None
        except Exception as e:
            print(f"[FACTORIAL_ERROR] parse: {e}")
            return None

        try:
            result = sympy.factorial(n_val)
            print(f"[FACTORIAL] {n_val}! = {result}")

            new_label = f"{n_val}!"
            try:
                fact_tile.set_label(new_label)
            except Exception:
                fact_tile.text = new_label
            try:
                fact_tile.data.display = new_label
            except Exception:
                pass

            return MergeResult(
                no_sticky=True,
                replace_tile=fact_tile,
                delete_tile=arg_tile,
                spawn_spec=_make_numeric_spec(result),
                spawn_direction=ctx.get('spawn_direction', 'right'),
            )
        except Exception as e:
            print(f"[FACTORIAL_ERROR] eval: {e}")
            return None

class RandomRule(MergeRule):
        """
        random tool + number n -> spawn random int 1..n, label rand(n)
        random_range tool + number a -> arm with lower bound, label rand(a-?)
        random_range_armed + number b -> spawn random int a..b, label rand(a-b)
        """
        priority = 48

        def _expr(self, t):
            return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

        def _is_random_tool(self, t):
            if getattr(t, 'kind', '') != 'tool':
                return False
            return self._expr(t) in ('random', 'random_range', 'random_range_armed')

        def can_apply(self, a, b, ctx):
            if self._is_random_tool(a):
                return tile_state(b) == 'number'
            if self._is_random_tool(b):
                return tile_state(a) == 'number'
            return False

        def apply(self, a, b, ctx):
            import random as _random
            from tile import Tile as _Tile

            rand_tile = a if self._is_random_tool(a) else b
            arg_tile  = b if self._is_random_tool(a) else a
            expr = self._expr(rand_tile)
            m = getattr(rand_tile.data, 'meta', {}) or {}

            try:
                n_val = int(str(getattr(arg_tile.data, 'display', None) or
                               getattr(arg_tile, 'text', '')).strip())
            except Exception as e:
                print(f"[RANDOM_ERROR] parse: {e}")
                return None

            # Simple mode: rand + n -> 1..n
            if expr == 'random':
                if n_val < 1:
                    print(f"[RANDOM] n must be >= 1")
                    return None
                result = _random.randint(1, n_val)
                new_label = f"rand({n_val})"
                print(f"[RANDOM] rand(1..{n_val}) = {result}")
                try:
                    rand_tile.set_label(new_label)
                except Exception:
                    rand_tile.text = new_label
                try:
                    rand_tile.data.display = new_label
                except Exception:
                    pass
                result_str = str(result)
                return MergeResult(
                    no_sticky=True,
                    replace_tile=rand_tile,
                    delete_tile=arg_tile,
                    spawn_spec={
                        'text': result_str, 'kind': 'number',
                        'color': _Tile.color_for_kind('number'),
                        'expr_str': result_str, 'display': result_str,
                    },
                    spawn_direction=ctx.get('spawn_direction', 'right'),
                )

            # Range unarmed: random_range + first number -> arm with lower bound
            if expr == 'random_range':
                m['rand_a'] = n_val
                try:
                    rand_tile.expr_str = 'random_range_armed'
                except Exception:
                    pass
                new_label = f"rand({n_val}-?)"
                try:
                    rand_tile.set_label(new_label)
                except Exception:
                    rand_tile.text = new_label
                try:
                    rand_tile.data.display = new_label
                except Exception:
                    pass
                print(f"[RANDOM] armed lower bound a={n_val}")
                return MergeResult(
                    no_sticky=True,
                    replace_tile=rand_tile,
                    delete_tile=arg_tile,
                )

            # Range armed: random_range_armed + number b -> spawn a..b, reset b only
            if expr == 'random_range_armed':
                a_val = m.get('rand_a', 1)
                b_val = n_val
                if b_val <= a_val:
                    print(f"[RANDOM] b must be > a ({a_val})")
                    return None
                result = _random.randint(a_val, b_val)
                new_label = f"rand({a_val}-{b_val})"
                print(f"[RANDOM] rand({a_val}..{b_val}) = {result}")
                try:
                    rand_tile.set_label(new_label)
                except Exception:
                    rand_tile.text = new_label
                try:
                    rand_tile.data.display = new_label
                except Exception:
                    pass
                result_str = str(result)
                return MergeResult(
                    no_sticky=True,
                    replace_tile=rand_tile,
                    delete_tile=arg_tile,
                    spawn_spec={
                        'text': result_str, 'kind': 'number',
                        'color': _Tile.color_for_kind('number'),
                        'expr_str': result_str, 'display': result_str,
                    },
                    spawn_direction=ctx.get('spawn_direction', 'right'),
                )

            return None


class ArmNumberWithOpRule(MergeRule):
    """
    number/result + op  OR  op + number/result -> num_op tile
    Division excluded - handled by FractionFromDivisionRule.
    """
    priority = 20

    _OPS = ('+', '-', '*', '^', '/')

    _DISPLAY = {'*': '×', '^': '^', '+': '+', '-': '-', '/': '÷'}

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _is_numeric(self, t):
        return getattr(t, 'kind', '') == 'number' or getattr(t, 'is_result', False)

    def can_apply(self, a, b, ctx):
        sa, sb = tile_state(a), tile_state(b)
        if sa == 'number' and sb == 'op':
            return self._expr(b) in self._OPS
        if sb == 'number' and sa == 'op':
            return self._expr(a) in self._OPS
        return False
    def apply(self, a, b, ctx):
        ka = getattr(a, 'kind', '')
        is_op_a = ka == 'op'
        num = b if is_op_a else a
        op  = a if is_op_a else b

        num_expr = self._expr(num)
        op_expr  = self._expr(op)
        op_disp  = self._DISPLAY.get(op_expr, op_expr)

        disp = f"{op_disp}{num_expr}"
        expr = f"{num_expr}{op_expr}"

        try:
            num.kind = 'num_op'
            num.is_result = False
        except Exception:
            pass

        return MergeResult(
            replace_tile=num,
            new_display=disp,
            new_expr_str=expr,
            delete_tile=op
        )

class EvaluateArmedOpRule(MergeRule):
    """
    num_op + number/result/fraction  OR  armed numeric fraction + number/expr/fraction
    -> evaluate -> result tile.
    Priority 14.
    """
    priority = 14

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _is_armed(self, t):
        return tile_state(t) in ('armed_num', 'armed_frac')
    def _is_valid_other(self, t):
        if _is_numeric(t):
            return True
        if _is_expr(t):
            return True
        return False

    def _is_numeric(self, t):
        return tile_state(t) in ('number', 'frac_num')
    def _parse_num_op(self, expr):
        for op in ('+', '-', '*', '^', '/'):
            if expr.endswith(op):
                num = expr[:-1].strip()
                if num:
                    return num, op
        return None, None

    def can_apply(self, a, b, ctx):
        sa, sb = tile_state(a), tile_state(b)
        armed = {'armed_num', 'armed_frac'}
        valid_other = {'number', 'frac_num', 'expr', 'frac_expr'}
        if sa in armed and sb in valid_other:
            return True
        if sb in armed and sa in valid_other:
            return True
        return False
    def apply(self, a, b, ctx):
        from sympy import sympify, expand, together, fraction as sym_fraction, Rational
        from tile import Tile as _Tile

        armed  = a if self._is_armed(a) else b
        number = b if self._is_armed(a) else a

        print(f"[EVAL_DEBUG] armed={armed.kind} armed_expr={self._expr(armed)} number={number.kind} number_expr={self._expr(number)}")

        is_num_tool = getattr(armed, 'kind', '') == 'num_tool'
        armed_m = getattr(armed.data, 'meta', {}) or {}

        if is_num_tool:
            base_num = armed_m.get('base_num', '')
            op = armed_m.get('base_op', '')
            if not base_num or not op:
                return None
            try:
                armed_sym = sympify(base_num)
            except Exception:
                return None
        elif armed_m.get('armed_op'):
            op = armed_m.get('armed_op')
            numer = armed_m.get('numer_expr') or armed_m.get('numer_disp', '0')
            denom = armed_m.get('denom_expr') or armed_m.get('denom_disp', '1')
            try:
                armed_sym = Rational(int(float(numer)), int(float(denom)))
            except Exception:
                armed_sym = sympify(f"({numer})/({denom})")
        else:
            armed_expr = self._expr(armed)
            num_str, op = self._parse_num_op(armed_expr)
            if num_str is None:
                return None
            armed_sym = sympify(num_str)
            # Apply neg state to the armed operand (if stored as flag)
            try:
                if _is_neg(armed):
                    armed_sym = -armed_sym
            except Exception:
                pass

        other_kind = getattr(number, 'kind', '')
        if other_kind == 'fraction':
            other_m = getattr(number.data, 'meta', {}) or {}
            if other_m.get('is_expr'):
                other_sym = sympify(str(getattr(number, 'expr_str', '') or ''))
            else:
                try:
                    n = int(float(other_m.get('numer_expr') or other_m.get('numer_disp', '0')))
                    d = int(float(other_m.get('denom_expr') or other_m.get('denom_disp', '1')))
                    other_sym = Rational(n, d)
                except Exception:
                    other_sym = sympify(number.expr_str)
        else:
            other_sym = sympify(str(getattr(number, 'expr_str', getattr(number, 'text', '')) or ''))
            # Apply neg state to the "other" operand
            try:
                if _is_neg(number):
                    other_sym = -other_sym
            except Exception:
                pass

        try:
            op_py = '**' if op == '^' else op
            raw = eval(f"armed_sym {op_py} other_sym",
                       {'armed_sym': armed_sym, 'other_sym': other_sym})
            raw = eval(f"other_sym {op_py} armed_sym",
                       {'armed_sym': armed_sym, 'other_sym': other_sym})
            combined = together(raw)
            # If the combined result is numeric and negative, normalize to neg-meta + positive display later.
            # (We don't mutate 'combined' here; we just keep the information available.)
            try:
                _combined_is_numeric = (not bool(getattr(combined, 'free_symbols', set())))
            except Exception:
                _combined_is_numeric = False
            numer, denom = sym_fraction(combined)
            numer = expand(numer)

            if is_num_tool:
                op_disp = {'+': '+', '-': '-', '*': '×', '^': '^', '/': '÷'}.get(op, op)
                other_disp = str(getattr(number.data, 'display', None) or
                                 getattr(number, 'text', '') or str(other_sym)).strip()
                new_label = f"{other_disp} {op_disp} {armed_m['base_num']}"
                
                try:
                    armed.set_label(new_label)
                except Exception:
                    armed.text = new_label
            else:
                if armed_m.get('armed_op'):
                    armed_m['numer_disp'] = armed_m.get('numer_disp_orig', armed_m.get('numer_disp', ''))
                    armed_m.pop('armed_op', None)
                    armed_m.pop('armed_op_disp', None)
                    armed_m.pop('numer_disp_orig', None)
                    armed_m.pop('base_expr', None)

            has_symbols          = bool(combined.free_symbols)
            is_irrational_result = not has_symbols and not combined.is_rational

            if denom == 1:
                if has_symbols:
                    disp = _pretty(numer)
                    if is_num_tool:
                        return MergeResult(
                            no_sticky=True,
                            replace_tile=armed,
                            delete_tile=number,
                            spawn_spec={
                                'text': disp, 'kind': 'expr',
                                'color': _Tile.color_for_kind('expr'),
                                'expr_str': str(numer), 'display': disp,
                            },
                            spawn_direction=ctx.get('spawn_direction', 'right'),
                        )
                    else:
                        try:
                            b.kind = 'expr'
                            b.data.meta.pop('is_expr', None)
                        except Exception:
                            pass
                        return MergeResult(replace_tile=b, new_display=disp, new_expr_str=str(numer), delete_tile=a)

                elif is_irrational_result:
                    spec = _make_numeric_spec(numer)
                    if is_num_tool:
                        return MergeResult(
                            no_sticky=True,
                            replace_tile=armed,
                            delete_tile=number,
                            spawn_spec=spec,
                            spawn_direction=ctx.get('spawn_direction', 'right'),
                        )
                    else:
                        try:
                            b.set_cell_size(w_cells=1, h_cells=1, cell_size=b.cell_size, gutter=b.gutter)
                            b.kind = spec['kind']
                            if spec.get('_meta'):
                                b.data.meta.update(spec['_meta'])
                        except Exception:
                            pass
                        return MergeResult(replace_tile=b, new_display=spec['display'], new_expr_str=spec['expr_str'], delete_tile=a)

                else:
                    try:
                        result_str = str(int(numer))
                    except Exception:
                        result_str = str(numer)
                    if is_num_tool:
                        return MergeResult(
                            no_sticky=True,
                            replace_tile=armed,
                            delete_tile=number,
                            spawn_spec={
                                'text': result_str, 'kind': 'number',
                                'color': _Tile.color_for_kind('number'),
                                'expr_str': result_str, 'display': result_str,
                            },
                            spawn_direction=ctx.get('spawn_direction', 'right'),
                        )
                    else:
                        try:
                            b.set_cell_size(w_cells=1, h_cells=1, cell_size=b.cell_size, gutter=b.gutter)
                            b.kind = 'number'
                            b.is_result = True
                        except Exception:
                            pass
                        return MergeResult(replace_tile=b, new_display=result_str, new_expr_str=result_str, delete_tile=a)

            # Has denominator
            if is_num_tool:
                rn_s, rd_s = str(numer), str(denom)
                return MergeResult(
                    no_sticky=True,
                    replace_tile=armed,
                    delete_tile=number,
                    spawn_spec={
                        'text': f"{rn_s}/{rd_s}", 'kind': 'fraction',
                        'color': _Tile.color_for_kind('fraction'),
                        'spawn_kind': 'fraction',
                        '_meta': {
                            'numer_disp': rn_s, 'denom_disp': rd_s,
                            'numer_expr': rn_s, 'denom_expr': rd_s,
                        }
                    },
                    spawn_direction=ctx.get('spawn_direction', 'right'),
                )

            if has_symbols:
                _apply_expr_fraction(b, numer, denom, combined)
                return MergeResult(replace_tile=b, new_display=None, new_expr_str=str(combined), delete_tile=a)
            else:
                rn_s, rd_s = str(numer), str(denom)
                try:
                    b.data.meta['numer_disp'] = rn_s
                    b.data.meta['denom_disp'] = rd_s
                    b.data.meta['numer_expr'] = rn_s
                    b.data.meta['denom_expr'] = rd_s
                    b.data.meta.pop('is_expr', None)
                    b.expr_str = f"({rn_s})/({rd_s})"
                    b.set_cell_size(w_cells=1, h_cells=2, cell_size=b.cell_size, gutter=b.gutter)
                    b.kind = 'fraction'
                    b.is_result = True
                    b._ensure_fraction_views()
                    b._sync_fraction_from_meta()
                    b.layout()
                except Exception as e:
                    print(f"[EVALUATE_FRAC_APPLY_ERROR] {e}")
                return MergeResult(replace_tile=b, new_display=None, new_expr_str=b.expr_str, delete_tile=a)

        except Exception as e:
            print(f"[EVALUATE_ERROR] {e}")
            import traceback
            traceback.print_exc()
            return None
    
class EqArmRule(MergeRule):
    # Replaced by FxRule - stubbed to avoid import errors
    priority = 999
    def can_apply(self, a, b, ctx): return False
    def apply(self, a, b, ctx): return None

class EqTransposeRule(MergeRule):
    """
    Tiles dragged onto = -> flip sign, spawn on opposite side.

    - armed_num  +8   -> plain -8 number
    - armed_num  -8   -> plain +8 armed num_op  
    - plain neg  -8   -> armed +8 num_op
    - armed_expr +x2  -> plain -x2 expr
    - plain expr -x2  -> armed +x2 expr
    - plain expr +x2  -> plain -x2 expr

    Plain positive unarmed numbers do NOT merge with =.
    """
    priority = 35

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _parse_num_op(self, t):
        """Return (num_str, op) from num_op tile expr_str like '8+'."""
        expr = self._expr(t)
        for op in ('+', '-'):
            if expr.endswith(op):
                num = expr[:-1].strip()
                if num:
                    return num, op
        return None, None

    def can_apply(self, a, b, ctx):
        sa, sb = tile_state(a), tile_state(b)
        if sa == 'armed_num' and sb == 'eq':
            num, op = self._parse_num_op(a)
            return op in ('+', '-')
        if sb == 'armed_num' and sa == 'eq':
            num, op = self._parse_num_op(b)
            return op in ('+', '-')
        # plain negative number only
        if sa == 'number' and sb == 'eq':
            return self._expr(a).startswith('-')
        if sb == 'number' and sa == 'eq':
            return self._expr(b).startswith('-')
        # armed expr
        if sa == 'armed_expr' and sb == 'eq':
            return True
        if sb == 'armed_expr' and sa == 'eq':
            return True
        # any plain expr
        if sa == 'expr' and sb == 'eq':
            return True
        if sb == 'expr' and sa == 'eq':
            return True
        return False

    def _find_space(self, board, eq_tile, side, cy, exclude=None):
        g = board.grid
        eq_cx = eq_tile.center[0]
        step = g if side == 'right' else -g
        for dist in range(1, int(board.width / g) + 2):
            tx = eq_cx + step * dist
            if tx < 0 or tx > board.width:
                break
            half_g = g * 0.45
            occupied = False
            for t in board.tiles:
                if t is exclude or t is eq_tile:
                    continue
                try:
                    tcx, tcy = t.center
                    if abs(tcy - cy) > g * 0.6:
                        continue
                    if abs(tcx - tx) < half_g + t.width * 0.45:
                        occupied = True
                        break
                except Exception:
                    pass
            if not occupied:
                try:
                    from tile import Tile as _Tile
                    dummy = _Tile(text='0', kind='number', color='#FFD60A',
                                  w_cells=1, h_cells=1, cell_size=g, gutter=4)
                    sx, sy = board.snap_center(tx, cy, dummy)
                    return sx, sy
                except Exception:
                    return tx, cy
        return None, None

    def apply(self, a, b, ctx):
        import ui, sympy
        from tile import Tile as _Tile

        sb = tile_state(b)
        value_tile = a if sb == 'eq' else b
        eq         = b if sb == 'eq' else a

        board = ctx.get('board')
        if board is None:
            return None

        drag_dir   = ctx.get('spawn_direction', 'right')
        spawn_side = drag_dir

        def _pulse_eq():
            def _settle():
                ui.animate(
                    lambda: setattr(eq, 'transform', ui.Transform()),
                    duration=0.1
                )
            ui.animate(
                lambda: setattr(eq, 'transform', ui.Transform.scale(1.08, 1.08)),
                duration=0.08, completion=_settle
            )

        def _result(kind, disp, expr):
            """Return MergeResult using spawn_spec so board handles tile creation."""
            _pulse_eq()
            return MergeResult(
                delete_tile=value_tile,
                spawn_spec={
                    'text':     disp,
                    'kind':     kind,
                    'color':    _Tile.color_for_kind(kind),
                    'expr_str': expr,
                    'display':  disp,
                },
                spawn_direction=spawn_side,
            )

        vst = tile_state(value_tile)

        # --- armed_num ---
        if vst == 'armed_num':
            num_str, op = self._parse_num_op(value_tile)
            if num_str is None:
                return None
            if op == '+':
                # +8 armed -> plain -8
                disp = f"-{num_str}"
                print(f"[EQ_TRANSPOSE] armed +{num_str} -> plain {disp}")
                return _result('number', disp, disp)
            else:
                # -8 armed -> +8 armed num_op
                disp = f"+{num_str}"
                expr = f"{num_str}+"
                print(f"[EQ_TRANSPOSE] armed -{num_str} -> armed {disp}")
                return _result('num_op', disp, expr)

        # --- plain negative number: -8 -> armed +8 ---
        if vst == 'number':
            raw = self._expr(value_tile)
            num_str = raw[1:].strip()
            disp = f"+{num_str}"
            expr = f"{num_str}+"
            print(f"[EQ_TRANSPOSE] plain {raw} -> armed {disp}")
            return _result('num_op', disp, expr)

        # --- armed_expr ---
        if vst == 'armed_expr':
            m = getattr(value_tile.data, 'meta', {}) or {}
            op = m.get('armed_op', '+')
            base_expr = m.get('base_expr') or self._expr(value_tile)
            try:
                base_sym = sympy.sympify(base_expr)
                if op == '+':
                    result_sym  = sympy.expand(-base_sym)
                    result_expr = str(result_sym)
                    result_disp = _pretty(result_sym)
                    print(f"[EQ_TRANSPOSE] armed +({base_expr}) -> plain {result_disp}")
                else:
                    result_expr = str(base_sym)
                    result_disp = _pretty(base_sym)
                    print(f"[EQ_TRANSPOSE] armed -({base_expr}) -> plain {result_disp}")
                return _result('expr', result_disp, result_expr)
            except Exception as e:
                print(f"[EQ_TRANSPOSE_ARMED_EXPR_ERROR] {e}")
                return None

        # --- plain expr: negate via sympy ---
        if vst == 'expr':
            expr_str = self._expr(value_tile)
            try:
                expr_sym = sympy.sympify(expr_str)
                negated  = sympy.expand(-expr_sym)
                neg_expr = str(negated)
                neg_disp = _pretty(negated)
            except Exception as e:
                print(f"[EQ_TRANSPOSE_EXPR_ERROR] {e}")
                return None
            print(f"[EQ_TRANSPOSE] plain expr {expr_str} -> {neg_disp}")
            return _result('expr', neg_disp, neg_expr)

        return None


class EqSubstRule(MergeRule):
    # Replaced by FxRule - stubbed to avoid import errors
    priority = 999
    def can_apply(self, a, b, ctx): return False
    def apply(self, a, b, ctx): return None
class FxRule(MergeRule):
    """
    fx tile + number/expr/fraction -> substitute and evaluate.
    Number in  -> evaluates f(3) -> spawns result, fx tile persists.
    Expr in    -> substitutes symbolically, expands, spawns result, fx tile persists.
    fx tile always survives. Result spawns in drag direction.
    """
    priority = 11

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _is_fx(self, t):
        return getattr(t, 'kind', '') == 'expr_tool'

    def can_apply(self, a, b, ctx):
        if self._is_fx(a):
            return tile_state(b) in ('number', 'expr', 'frac_num', 'frac_expr')
        if self._is_fx(b):
            return tile_state(a) in ('number', 'expr', 'frac_num', 'frac_expr')
        return False

    def apply(self, a, b, ctx):
        import sympy
        fx_tile  = a if self._is_fx(a) else b
        arg_tile = b if self._is_fx(a) else a

        fx_expr = self._expr(fx_tile)
        try:
            f = sympy.sympify(fx_expr)
        except Exception as e:
            print(f"[FX_ERROR] can't parse fx expr: {e}")
            return None

        free = sorted(f.free_symbols, key=str)
        if not free:
            print(f"[FX_ERROR] no free symbols in {fx_expr}")
            return None
        sym = free[0]

        arg_kind = getattr(arg_tile, 'kind', '')
        if arg_kind == 'fraction':
            m = getattr(arg_tile.data, 'meta', {}) or {}
            if m.get('is_expr'):
                arg_sym = sympy.sympify(str(getattr(arg_tile, 'expr_str', '') or ''))
            else:
                try:
                    n = int(float(m.get('numer_expr') or m.get('numer_disp', '0')))
                    d = int(float(m.get('denom_expr') or m.get('denom_disp', '1')))
                    arg_sym = sympy.Rational(n, d)
                except Exception:
                    arg_sym = sympy.sympify(str(getattr(arg_tile, 'expr_str', '') or ''))
        else:
            arg_sym = sympy.sympify(
                str(getattr(arg_tile, 'expr_str', getattr(arg_tile, 'text', '')) or '').strip()
            )

        try:
            result = sympy.expand(f.subs(sym, arg_sym))
            print(f"[FX] {fx_expr} with {sym}={arg_sym} -> {result}")
        except Exception as e:
            print(f"[FX_EVAL_ERROR] {e}")
            return None

        # Build label by string-replacing sym in the pretty form
        # _pretty(f) gives x² so replacing x with (8) gives (8)²
        arg_disp = _tile_disp(arg_tile)
        pretty_f = _pretty(f)
        new_label = pretty_f.replace(str(sym), f"({arg_disp})")
        try:
            fx_tile.set_label(new_label)
        except Exception:
            fx_tile.text = new_label
        try:
            fx_tile.data.display = new_label
        except Exception:
            pass

        if result.free_symbols:
            from tile import Tile as _Tile
            disp = _pretty(result)
            spawn_spec = {
                'text': disp, 'kind': 'expr',
                'color': _Tile.color_for_kind('expr'),
                'expr_str': str(result), 'display': disp,
            }
        else:
            spawn_spec = _make_numeric_spec(result)

        return MergeResult(
            no_sticky=True,
            replace_tile=fx_tile,
            delete_tile=arg_tile,
            spawn_spec=spawn_spec,
            spawn_direction=ctx.get('spawn_direction', 'right'),
        )
    
def _frac_state(t):
    """Returns 'blank', 'half', 'complete', or None if not a fraction tile."""
    if getattr(t, 'kind', '') != 'fraction':
        return None
    m = getattr(t.data, 'meta', {}) or {}
    n = m.get('numer_disp')
    d = m.get('denom_disp')
    if n and d:
        return 'complete'
    if n:
        return 'half'
    return 'blank'


def _frac_state(t):
    if getattr(t, 'kind', '') != 'fraction':
        return None
    m = getattr(t.data, 'meta', {}) or {}
    n = m.get('numer_disp') or m.get('numer_expr')
    d = m.get('denom_disp') or m.get('denom_expr')
    if not n and not d:
        return 'blank'
    if n and not d:
        return 'half'
    return 'complete'


def tile_state(t):
    kind = getattr(t, 'kind', '')
    m = getattr(t.data, 'meta', {}) or {}

    if kind == 'op':
        return 'op'
    if kind == 'tool':
        return 'tool'
    if kind == 'eq':
        return 'eq'
    if kind == 'armed_eq':
        return 'armed_eq'
    if kind == 'num_op':
        return 'armed_num'
    if kind == 'num_tool':
        return 'armed_num'
    if kind in ('number', 'result'):
        return 'number'
    if getattr(t, 'is_result', False) and kind != 'fraction':
        return 'number'
    if kind == 'fraction':
        is_expr = bool(m.get('is_expr'))
        is_armed = bool(m.get('armed_op'))
        fs = _frac_state(t)
        if fs == 'blank':
            return 'frac_blank'
        if fs == 'half':
            return 'frac_half'
        if is_armed:
            return 'armed_frac_expr' if is_expr else 'armed_frac'
        return 'frac_expr' if is_expr else 'frac_num'
    if kind == 'armed_expr':
        return 'armed_expr'
    if kind == 'irrational':
        kind = 'expr'
    if kind == 'expr_tool':
        kind = 'expr'
    if kind in ('expr', 'symbol', 'fx'):
        if bool(m.get('armed_op')):
            return 'armed_expr'
        return 'expr'
    return 'unknown'

def _is_numeric(t):
    return tile_state(t) in ('number', 'frac_num')

def _is_expr(t):
    return tile_state(t) in ('expr', 'frac_expr')

def _frac_value(t):
    m = getattr(t.data, 'meta', {}) or {}
    try:
        n = float(m.get('numer_expr') or m.get('numer_disp', '0'))
        d = float(m.get('denom_expr') or m.get('denom_disp', '1'))
        return n / d if d != 0 else None
    except Exception:
        return None
def _is_expr(t):
    if getattr(t, 'kind', '') in ('expr', 'symbol'):
        return True
    # fraction tiles containing expressions count as expr
    if getattr(t, 'kind', '') == 'fraction':
        m = getattr(t.data, 'meta', {}) or {}
        return bool(m.get('is_expr'))
    return False
def _round_decimal(s, max_dp=8):
    """Round a decimal string to max_dp significant decimal places."""
    import re
    def _round_match(m):
        try:
            val = float(m.group(0))
            formatted = f"{val:.{max_dp}f}".rstrip('0').rstrip('.')
            return formatted
        except Exception:
            return m.group(0)
    return re.sub(r'-?\d+\.\d+', _round_match, s)


def _pretty(expr_or_str):
    import re
    s = str(expr_or_str)

    SUP = str.maketrans('0123456789+-', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻')

    def sup_replace(m):
        base = m.group(1)
        exp = m.group(2)
        exp_clean = exp.lstrip('(').rstrip(')')
        return base + exp_clean.translate(SUP)

    s = re.sub(r'([A-Za-z_]\w*)\*\*\((-\d+)\)', sup_replace, s)
    s = re.sub(r'([A-Za-z_]\w*)\*\*(\d+)', sup_replace, s)

    # Inverse trig
    s = re.sub(r'asin\(([^)]+)\)', r'sin⁻¹(\1)', s)
    s = re.sub(r'acos\(([^)]+)\)', r'cos⁻¹(\1)', s)
    s = re.sub(r'atan\(([^)]+)\)', r'tan⁻¹(\1)', s)

    # nth root
    ROOT_SYMS = {'2': '√', '3': '∛'}
    def root_replace(m):
        inner = m.group(1)
        n = m.group(2)
        sym = ROOT_SYMS.get(n)
        if sym:
            return f"{sym}{inner}"
        sup = n.translate(SUP)
        return f"{sup}√{inner}"
    s = re.sub(r'([A-Za-z_]\w*)\*\*\(1/(\d+)\)', root_replace, s)

    # Remove * between coefficient and variable
    s = re.sub(r'(\d)\*([A-Za-z])', r'\1\2', s)
    s = re.sub(r'([A-Za-z])\*([A-Za-z])', r'\1\2', s)

    # sqrt
    def sqrt_replace(m):
        inner = m.group(1)
        if len(inner) <= 3 and ' ' not in inner:
            return f'√{inner}'
        return f'√({inner})'
    s = re.sub(r'sqrt\(([^)]+)\)', sqrt_replace, s)

    s = s.replace('**', '^')
    s = s.replace('pi', 'π')
    s = s.replace('oo', '∞')

    # Round any decimals to 8 places
    s = _round_decimal(s)

    return s

def _tile_disp(t):
    """Build a clean human-readable display string from any tile type."""
    if getattr(t, 'kind', '') == 'fraction':
        m = getattr(t.data, 'meta', {}) or {}
        n = m.get('numer_disp', '')
        d = m.get('denom_disp', '')
        if n and d:
            return f"{n}/{d}"
        if n:
            return str(n)
    disp = str(getattr(t.data, 'display', None) or
               getattr(t, 'text', '') or '').strip()
    return disp or str(getattr(t, 'expr_str', '') or '').strip()

def _neg_meta(t):
    try:
        return getattr(t.data, 'meta', {}) or {}
    except Exception:
        return {}

def _is_neg(t):
    try:
        return bool(_neg_meta(t).get('neg'))
    except Exception:
        return False

def _set_neg(t, v):
    try:
        _neg_meta(t)['neg'] = bool(v)
    except Exception:
        pass

def _strip_leading_minus(s):
    s = str(s or '').strip()
    if s.startswith('−'):  # unicode minus
        s = '-' + s[1:]
    if s.startswith('-'):
        return s[1:].strip()
    return s

def _split_signed_str(s):
    """Return (is_neg, abs_str) for a string that may begin with '-' or '−'."""
    s = str(s or '').strip()
    if s.startswith('−'):
        s = '-' + s[1:]
    if s.startswith('-'):
        return True, s[1:].strip()
    return False, s

def _signed_expr_str(t):
    """
    Return a sympy-safe expression string that includes neg state,
    without mutating the tile's stored expr_str.
    """
    raw = str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()
    # If raw already has a minus, treat it as signed (but keep neg flag consistent).
    raw_neg, raw_abs = _split_signed_str(raw)
    neg = raw_neg or _is_neg(t)
    if not raw_abs:
        raw_abs = raw  # fallback
    if neg:
        # Parenthesize to protect compound expressions
        if any(ch in raw_abs for ch in ('+', '-', '*', '/', '^', ' ')) and not raw_abs.startswith('('):
            return f"-({raw_abs})"
        return f"-{raw_abs}"
    return raw_abs

def _apply_signed_result_meta(spec, sym_obj):
    """
    If sympy result is negative numeric, store as neg meta + positive display/expr.
    If not purely numeric, we leave sign inside expr string (sympy will handle it).
    """
    try:
        # Only normalize for numeric (no free symbols) results
        if getattr(sym_obj, 'free_symbols', None):
            if sym_obj.free_symbols:
                return spec
        # For numeric sympy objects, detect negativity
        if hasattr(sym_obj, 'is_number') and sym_obj.is_number:
            # sympy comparisons can be tricky; use float fallback
            is_neg = False
            try:
                is_neg = bool(sym_obj.is_negative)
            except Exception:
                try:
                    is_neg = float(sym_obj) < 0
                except Exception:
                    is_neg = False
            if is_neg:
                abs_obj = -sym_obj
                # build a normal numeric spec for abs_obj
                abs_spec = _make_numeric_spec(abs_obj)
                # carry kind/color from abs_spec
                abs_spec['_meta'] = dict(abs_spec.get('_meta') or {})
                abs_spec['_meta']['neg'] = True
                return abs_spec
    except Exception:
        pass
    return spec

def _make_numeric_spec(result):
    """
    Given a sympy expression with no free symbols, return the correct tile spec.
    Rational integers  -> number tile
    Rational non-integer -> number tile (decimal)
    Irrational (pi, sqrt(2), etc) -> irrational tile with exact_expr stored in meta
    """
    from tile import Tile as _Tile
    try:
        if result.is_integer:
            s = str(int(result))
            return {
                'text': s, 'kind': 'number',
                'color': _Tile.color_for_kind('number'),
                'expr_str': s, 'display': s,
            }
        elif result.is_rational:
            val = float(result)
            s = f"{val:.6g}"
            return {
                'text': s, 'kind': 'number',
                'color': _Tile.color_for_kind('number'),
                'expr_str': s, 'display': s,
            }
        else:
            disp = _pretty(result)
            exact = str(result)
            return {
                'text': disp, 'kind': 'irrational',
                'color': _Tile.color_for_kind('irrational'),
                'expr_str': exact, 'display': disp,
                '_meta': {'exact_expr': exact, 'showing_decimal': False},
            }
    except Exception:
        disp = _pretty(result)
        return {
            'text': disp, 'kind': 'expr',
            'color': _Tile.color_for_kind('expr'),
            'expr_str': str(result), 'display': disp,
        }

def _apply_expr_fraction(tile, numer_sym, denom_sym, result_sym):
    numer_disp = _pretty(numer_sym)
    denom_disp = _pretty(denom_sym)
    tile.data.meta['numer_disp'] = numer_disp
    tile.data.meta['denom_disp'] = denom_disp
    tile.data.meta['numer_expr'] = str(numer_sym)
    tile.data.meta['denom_expr'] = str(denom_sym)
    tile.data.meta['is_expr'] = True
    tile.expr_str = str(result_sym)
    tile.kind = 'fraction'
    expr_color = _Tile.color_for_kind('expr')
    tile.base_color = expr_color
    tile.drag_color = expr_color
    tile.background_color = expr_color
    if hasattr(tile, 'content_view') and tile.content_view is not None:
        tile.content_view.background_color = expr_color
    try:
        tile.set_cell_size(w_cells=1, h_cells=2, cell_size=tile.cell_size, gutter=tile.gutter)
        tile._ensure_fraction_views()
        tile._sync_fraction_from_meta()
        tile.layout()
    except Exception as e:
        print(f"[EXPR_FRAC_APPLY_ERROR] {e}")


class ImplicitMultiplyRule(MergeRule):
    """
    Non-adjacent drop of any expr/number/irrational onto another.
    Multiplies symbolically: a appended onto b = b * a.
    Only fires when drag was NOT adjacent (adjacent gestures use profiles).
    """
    priority = 5

    _KINDS = ('expr', 'number', 'irrational')

    def can_apply(self, a, b, ctx):
        if getattr(a, 'kind', '') not in self._KINDS:
            return False
        if getattr(b, 'kind', '') not in self._KINDS:
            return False
        # Must NOT be adjacent — adjacency is handled by profiles
        board      = ctx.get('board')
        drag_start = ctx.get('drag_start_center')
        if board and drag_start:
            if _started_adjacent(drag_start, b, board.grid):
                return False
        return True

    def apply(self, a, b, ctx):
        import sympy
        from merge_engine import _pretty, MergeResult
        try:
            a_expr = str(getattr(a, 'expr_str', None) or getattr(a, 'text', '') or '').strip()
            b_expr = str(getattr(b, 'expr_str', None) or getattr(b, 'text', '') or '').strip()
            result = sympy.expand(sympy.sympify(b_expr) * sympy.sympify(a_expr))
            disp   = _pretty(result)
            has_sym = bool(result.free_symbols)
            kind   = 'expr' if has_sym else 'number'
            from tile import Tile as _Tile
            color = _Tile.color_for_kind(kind)
            b.kind = kind
            b.set_label(disp)
            b.expr_str = str(result)
            b.base_color = b.background_color = b.drag_color = color
            try: b.data.display = disp
            except Exception: pass
            b.set_cell_size(w_cells=1, h_cells=1,
                            cell_size=b.cell_size, gutter=b.gutter)
            print(f"[IMPLICIT_MUL] {b_expr} * {a_expr} -> {result}")
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[IMPLICIT_MUL_ERROR] {e}")
            return None

    def preview_label(self, a, b, ctx):
        import sympy
        from merge_engine import _pretty
        try:
            a_expr = str(getattr(a, 'expr_str', None) or getattr(a, 'text', '') or '').strip()
            b_expr = str(getattr(b, 'expr_str', None) or getattr(b, 'text', '') or '').strip()
            result = sympy.expand(sympy.sympify(b_expr) * sympy.sympify(a_expr))
            return _pretty(result)
        except Exception:
            return None



class ExprMultiplyRule(MergeRule):
    """
    expr × expr  OR  number × expr  OR  expr × number -> sympy multiply -> result expr tile.
    Does not fire on armed tiles.
    """
    priority = 18

    def can_apply(self, a, b, ctx):
        sa, sb = tile_state(a), tile_state(b)
        expr_states = {'expr', 'frac_expr'}
        numeric_states = {'number', 'frac_num'}
        valid = expr_states | numeric_states

        if sa not in valid or sb not in valid:
            return False
        # At least one must be expr
        if sa not in expr_states and sb not in expr_states:
            return False
        return True
    def apply(self, a, b, ctx):
        from sympy import sympify, expand, together, fraction as sym_fraction, Rational

        def to_sym(t):
            if getattr(t, 'kind', '') == 'fraction':
                m = getattr(t.data, 'meta', {}) or {}
                if m.get('is_expr'):
                    base = sympify(str(getattr(t, 'expr_str', '') or ''))
                else:
                    try:
                        n = int(float(m.get('numer_expr') or m.get('numer_disp', '0')))
                        d = int(float(m.get('denom_expr') or m.get('denom_disp', '1')))
                        base = Rational(n, d)
                    except Exception:
                        base = sympify(str(getattr(t, 'expr_str', '') or ''))
            else:
                base = sympify(str(getattr(t, 'expr_str', getattr(t, 'text', '')) or ''))
            # Apply neg state on top (without mutating stored strings)
            try:
                if _is_neg(t):
                    base = -base
            except Exception:
                pass
            return base

        try:
            a_sym = to_sym(a)
            b_sym = to_sym(b)
            raw = a_sym * b_sym
            combined = together(raw)
            numer, denom = sym_fraction(combined)
            numer = expand(numer)

            print(f"[EXPR_MULTIPLY] {a_sym} * {b_sym} = {numer}/{denom}")

            has_symbols = bool(combined.free_symbols)
            is_irrational_result = not has_symbols and not combined.is_rational

            if denom != 1:
                try:
                    b.kind = 'expr'
                    b.data.meta.pop('is_expr', None)
                except Exception:
                    pass
                _apply_expr_fraction(b, numer, denom, combined)
                return MergeResult(replace_tile=b, new_display=None, new_expr_str=str(combined), delete_tile=a)

            try:
                b.set_cell_size(w_cells=1, h_cells=1, cell_size=b.cell_size, gutter=b.gutter)
                b.data.meta.pop('is_expr', None)
            except Exception:
                pass

            if has_symbols:
                try:
                    b.kind = 'expr'
                except Exception:
                    pass
                # if result starts negative, keep it inside expr_str; display uses _pretty
                disp = _pretty(numer)
                return MergeResult(
                    replace_tile=b,
                    new_display=disp,
                    new_expr_str=str(numer),
                    delete_tile=a
                )
            elif is_irrational_result:
                from tile import Tile as _Tile
                spec = _make_numeric_spec(numer)
                spec = _apply_signed_result_meta(spec, numer)
                try:
                    b.kind = spec['kind']
                    if spec.get('_meta'):
                        b.data.meta.update(spec['_meta'])
                except Exception:
                    pass
                return MergeResult(
                    replace_tile=b,
                    new_display=spec['display'],
                    new_expr_str=spec['expr_str'],
                    delete_tile=a
                )
            else:
                try:
                    result_str = str(int(numer))
                except Exception:
                    result_str = str(numer)
                # numeric sign normalization
                try:
                    is_neg = float(numer) < 0
                except Exception:
                    is_neg = False
                if is_neg:
                    try:
                        b.data.meta['neg'] = True
                    except Exception:
                        pass
                    result_str = _strip_leading_minus(result_str)
                try:
                    b.kind = 'number'
                    b.is_result = True
                except Exception:
                    pass
                return MergeResult(replace_tile=b, new_display=result_str, new_expr_str=result_str, delete_tile=a)

        except Exception as e:
            print(f"[EXPR_MULTIPLY_ERROR] {e}")
            return None

class ArmExprWithOpRule(MergeRule):
    """
    expr + op -> armed expr tile. Stores op in meta, updates display: "x² +"
    """
    priority = 21

    _OPS = ('+', '-', '*', '^')
    _DISPLAY = {'*': '×', '^': '^', '+': '+', '-': '-'}

    def _get_expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def can_apply(self, a, b, ctx):
        sa, sb = tile_state(a), tile_state(b)
        expr_states = {'expr', 'frac_expr'}
        if sa in expr_states and sb == 'op':
            return self._get_expr(b) in self._OPS
        if sb in expr_states and sa == 'op':
            return self._get_expr(a) in self._OPS
        return False
    def apply(self, a, b, ctx):
        ka = getattr(a, 'kind', '')
        is_op_a = ka == 'op'
        expr_tile = b if is_op_a else a
        op = a if is_op_a else b

        op_expr = self._get_expr(op)
        op_disp = self._DISPLAY.get(op_expr, op_expr)

        m = expr_tile.data.meta
        m['armed_op'] = op_expr
        m['armed_op_disp'] = op_disp
        m['base_expr'] = expr_tile.expr_str

        # Expr fraction tile - update numer label to show op
        if getattr(expr_tile, 'kind', '') == 'fraction':
            m['numer_disp_orig'] = m.get('numer_disp', '')
            m['numer_disp'] = f"{m.get('numer_disp_orig', '')} {op_disp}"
            try:
                expr_tile._sync_fraction_from_meta()
                expr_tile.layout()
            except Exception:
                pass
            return MergeResult(
                replace_tile=expr_tile,
                new_display=None,
                new_expr_str=expr_tile.expr_str,
                delete_tile=op
            )

        # Regular expr tile - update label
        m['disp_orig'] = _pretty(expr_tile.expr_str)
        new_disp = f"{m['disp_orig']} {op_disp}"

        return MergeResult(
            replace_tile=expr_tile,
            new_display=new_disp,
            new_expr_str=expr_tile.expr_str,
            delete_tile=op
        )
class EvaluateArmedExprRule(MergeRule):
    """
    armed_expr + number/expr/fraction -> sympy evaluate -> result expr tile.
    Priority 13: beats EvaluateArmedOpRule (14).
    """
    priority = 13

    def _is_armed_expr(self, t):
        return tile_state(t) in ('armed_expr', 'armed_frac_expr')
    def _is_valid_other(self, t):
        return tile_state(t) in ('number', 'frac_num', 'expr', 'frac_expr')
    def can_apply(self, a, b, ctx):
        sa, sb = tile_state(a), tile_state(b)
        armed = {'armed_expr', 'armed_frac_expr'}
        valid_other = {'number', 'frac_num', 'expr', 'frac_expr'}
        if sa in armed and sb in valid_other:
            return True
        if sb in armed and sa in valid_other:
            return True
        return False
    def apply(self, a, b, ctx):
        from sympy import sympify, expand, together, fraction as sym_fraction, Rational

        armed  = a if self._is_armed_expr(a) else b
        other  = b if self._is_armed_expr(a) else a

        m = armed.data.meta
        op = m.get('armed_op')

        armed_sym_str = m.get('base_expr') or armed.expr_str
        for op_char in ('+', '-', '*', '^'):
            if armed_sym_str.rstrip().endswith(op_char):
                armed_sym_str = armed_sym_str.rstrip()[:-1].strip()
                break

        other_kind = getattr(other, 'kind', '')
        if other_kind == 'fraction':
            other_m = getattr(other.data, 'meta', {}) or {}
            if other_m.get('is_expr'):
                b_sym = sympify(str(getattr(other, 'expr_str', '') or ''))
            else:
                try:
                    n = int(float(other_m.get('numer_expr') or other_m.get('numer_disp', '0')))
                    d = int(float(other_m.get('denom_expr') or other_m.get('denom_disp', '1')))
                    b_sym = Rational(n, d)
                except Exception:
                    b_sym = sympify(other.expr_str)
        else:
            b_sym = sympify(str(getattr(other, 'expr_str', getattr(other, 'text', '')) or ''))

        try:
            a_sym = sympify(armed_sym_str)
            op_py = '**' if op == '^' else op
            raw = eval(f"a_sym {op_py} b_sym", {'a_sym': a_sym, 'b_sym': b_sym})

            combined = together(raw)
            numer, denom = sym_fraction(combined)
            numer = expand(numer)

            print(f"[ARMED_EXPR_EVAL] ({a_sym}) {op} ({b_sym}) = {numer}/{denom}")

            m.pop('armed_op', None)
            m.pop('armed_op_disp', None)
            m.pop('disp_orig', None)
            m.pop('numer_disp_orig', None)
            m.pop('base_expr', None)

            has_symbols       = bool(combined.free_symbols)
            is_irrational_result = not has_symbols and not combined.is_rational

            if denom == 1:
                if has_symbols:
                    try:
                        b.set_cell_size(w_cells=1, h_cells=1, cell_size=b.cell_size, gutter=b.gutter)
                        b.kind = 'expr'
                        b.data.meta.pop('is_expr', None)
                    except Exception:
                        pass
                    return MergeResult(
                        replace_tile=b,
                        new_display=_pretty(numer),
                        new_expr_str=str(numer),
                        delete_tile=a
                    )
                elif is_irrational_result:
                    spec = _make_numeric_spec(numer)
                    try:
                        b.set_cell_size(w_cells=1, h_cells=1, cell_size=b.cell_size, gutter=b.gutter)
                        b.kind = spec['kind']
                        if spec.get('_meta'):
                            b.data.meta.update(spec['_meta'])
                    except Exception:
                        pass
                    return MergeResult(
                        replace_tile=b,
                        new_display=spec['display'],
                        new_expr_str=spec['expr_str'],
                        delete_tile=a
                    )
                else:
                    try:
                        result_str = str(int(numer))
                    except Exception:
                        result_str = str(numer)
                    try:
                        b.set_cell_size(w_cells=1, h_cells=1, cell_size=b.cell_size, gutter=b.gutter)
                        b.kind = 'number'
                        b.is_result = True
                    except Exception:
                        pass
                    return MergeResult(replace_tile=b, new_display=result_str, new_expr_str=result_str, delete_tile=a)

            # Has denominator
            if has_symbols:
                _apply_expr_fraction(b, numer, denom, combined)
                return MergeResult(replace_tile=b, new_display=None, new_expr_str=str(combined), delete_tile=a)
            else:
                rn_s, rd_s = str(numer), str(denom)
                try:
                    b.data.meta['numer_disp'] = rn_s
                    b.data.meta['denom_disp'] = rd_s
                    b.data.meta['numer_expr'] = rn_s
                    b.data.meta['denom_expr'] = rd_s
                    b.data.meta.pop('is_expr', None)
                    b.expr_str = f"({rn_s})/({rd_s})"
                    b.kind = 'fraction'
                    b.is_result = True
                    b._sync_fraction_from_meta()
                    b.layout()
                except Exception as e:
                    print(f"[ARMED_EXPR_EVAL_FRAC_ERROR] {e}")
                return MergeResult(replace_tile=b, new_display=None, new_expr_str=b.expr_str, delete_tile=a)

        except Exception as e:
            print(f"[ARMED_EXPR_EVAL_ERROR] {e}")
            return None

def _frac_value(t):
    """Return float value of a complete fraction, or None."""
    m = getattr(t.data, 'meta', {}) or {}
    try:
        n = float(m.get('numer_expr') or m.get('numer_disp'))
        d = float(m.get('denom_expr') or m.get('denom_disp'))
        if d == 0:
            return None
        return n / d
    except Exception:
        return None


class FillFractionRule(MergeRule):
    """
    number + blank fraction  -> fills numerator   (half fraction)
    number + half fraction   -> fills denominator (complete fraction)
    Symmetric - works either direction.
    """
    priority = 15

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _disp(self, t):
        return str(getattr(t, 'display', getattr(t, 'text', '')) or '').strip()

    def can_apply(self, a, b, ctx):
        sa, sb = tile_state(a), tile_state(b)
        fillable = {'number', 'expr', 'frac_num', 'frac_expr'}
        if sa in ('frac_blank', 'frac_half') and sb in fillable:
            return True
        if sb in ('frac_blank', 'frac_half') and sa in fillable:
            return True
        return False
    def apply(self, a, b, ctx):
        if _frac_state(a) in ('blank', 'half'):
            frac, other = a, b
        else:
            frac, other = b, a

        state = _frac_state(frac)
        m = frac.data.meta

        # Get display and expr from other tile
        if _is_expr(other):
            other_disp = _pretty(other.expr_str)
            other_expr = str(getattr(other, 'expr_str', '') or '')
            frac.data.meta['is_expr'] = True
        else:
            other_disp = str(getattr(other, 'display', getattr(other, 'text', '')) or '').strip()
            other_expr = str(getattr(other, 'expr_str', getattr(other, 'text', '')) or '').strip()

        if state == 'blank':
            m['numer_disp'] = other_disp
            m['numer_expr'] = other_expr
        else:
            m['denom_disp'] = other_disp
            m['denom_expr'] = other_expr
            n = m.get('numer_expr', '')
            frac.expr_str = f"({n})/({other_expr})"

        try:
            frac._sync_fraction_from_meta()
            frac.layout()
        except Exception:
            pass

        return MergeResult(
            replace_tile=frac,
            new_display=None,
            new_expr_str=frac.expr_str,
            delete_tile=other
        )
class MultiplyFractionsRule(MergeRule):
    """
    complete fraction + complete fraction -> multiply -> result fraction
    (a/b) * (c/d) = (a*c)/(b*d)
    """
    priority = 16

    def can_apply(self, a, b, ctx):
        return tile_state(a) == 'frac_num' and tile_state(b) == 'frac_num'
    def apply(self, a, b, ctx):
        ma = a.data.meta
        mb = b.data.meta

        try:
            an = float(ma.get('numer_expr') or ma.get('numer_disp'))
            ad = float(ma.get('denom_expr') or ma.get('denom_disp'))
            bn = float(mb.get('numer_expr') or mb.get('numer_disp'))
            bd = float(mb.get('denom_expr') or mb.get('denom_disp'))

            new_n = an * bn
            new_d = ad * bd

            # Clean display (int if possible)
            def fmt(v):
                return str(int(v)) if v == int(v) else f"{v:.10g}"

            # Simplify if denominator is 1
            if new_d == 1:
                result_str = fmt(new_n)
                try:
                    b.kind = 'number'
                    b.is_result = True
                except Exception:
                    pass
                return MergeResult(
                    replace_tile=b,
                    new_display=result_str,
                    new_expr_str=result_str,
                    delete_tile=a
                )

            # Keep as fraction
            b.data.meta['numer_disp'] = fmt(new_n)
            b.data.meta['denom_disp'] = fmt(new_d)
            b.data.meta['numer_expr'] = fmt(new_n)
            b.data.meta['denom_expr'] = fmt(new_d)
            b.expr_str = f"({fmt(new_n)})/({fmt(new_d)})"
            b.is_result = True

            try:
                b._sync_fraction_from_meta()
                b.layout()
            except Exception:
                pass

        except Exception as e:
            print(f"[MULTIPLY_FRACTIONS_ERROR] {e}")
            return None

        return MergeResult(
            replace_tile=b,
            new_display=None,
            new_expr_str=b.expr_str,
            delete_tile=a
        )


class MultiplyFractionByNumRule(MergeRule):
    """
    complete fraction + number -> multiply numerator
    Skips armed fractions (handled by EvaluateArmedOpRule).
    """
    priority = 17

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def can_apply(self, a, b, ctx):
        sa, sb = tile_state(a), tile_state(b)
        return (sa == 'frac_num' and sb == 'number') or \
               (sb == 'frac_num' and sa == 'number')
    def apply(self, a, b, ctx):
        if _frac_state(a) == 'complete':
            frac, num = a, b
        else:
            frac, num = b, a

        m = frac.data.meta

        try:
            n = float(m.get('numer_expr') or m.get('numer_disp'))
            d = float(m.get('denom_expr') or m.get('denom_disp'))
            multiplier = float(self._expr(num))
            new_n = n * multiplier

            def fmt(v):
                return str(int(v)) if v == int(v) else f"{v:.10g}"

            if new_n % d == 0:
                result_str = fmt(new_n / d)
                try:
                    frac.kind = 'number'
                    frac.is_result = True
                except Exception:
                    pass
                return MergeResult(
                    replace_tile=frac,
                    new_display=result_str,
                    new_expr_str=result_str,
                    delete_tile=num
                )

            m['numer_disp'] = fmt(new_n)
            m['numer_expr'] = fmt(new_n)
            frac.expr_str = f"({fmt(new_n)})/({fmt(d)})"
            frac.is_result = True

            try:
                frac._sync_fraction_from_meta()
                frac.layout()
            except Exception:
                pass

        except Exception as e:
            print(f"[MULTIPLY_FRAC_BY_NUM_ERROR] {e}")
            return None

        return MergeResult(
            replace_tile=frac,
            new_display=None,
            new_expr_str=frac.expr_str,
            delete_tile=num
        )
class ArmFractionWithOpRule(MergeRule):
    """
    complete fraction + op -> armed fraction tile
    Keeps fraction display, adds op to numerator label: "3 +/4"
    """
    priority = 22

    _OPS = ('+', '-', '*', '^')
    _DISPLAY = {'*': '×', '^': '^', '+': '+', '-': '-'}

    def _expr(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def can_apply(self, a, b, ctx):
        sa, sb = tile_state(a), tile_state(b)
        if sa == 'frac_num' and sb == 'op':
            return self._expr(b) in self._OPS
        if sb == 'frac_num' and sa == 'op':
            return self._expr(a) in self._OPS
        return False
    def apply(self, a, b, ctx):
        ka = getattr(a, 'kind', '')
        is_op_a = ka == 'op'
        frac = b if is_op_a else a
        op   = a if is_op_a else b

        op_expr = self._expr(op)
        op_disp = self._DISPLAY.get(op_expr, op_expr)

        m = frac.data.meta
        m['armed_op'] = op_expr
        m['armed_op_disp'] = op_disp
        m['numer_disp_orig'] = m.get('numer_disp', '')

        # Store the clean base expr separately - never append op to expr_str
        numer = m.get('numer_expr') or m.get('numer_disp', '')
        denom = m.get('denom_expr') or m.get('denom_disp', '')
        frac_expr = f"({numer})/({denom})"
        m['base_expr'] = frac_expr

        # Update numer display to show op: "x +"
        m['numer_disp'] = f"{m.get('numer_disp_orig', '')} {op_disp}"

        # expr_str stays clean for sympy - do NOT append op here
        frac.expr_str = frac_expr

        try:
            frac._sync_fraction_from_meta()
            frac.layout()
        except Exception:
            pass

        return MergeResult(
            replace_tile=frac,
            new_display=None,
            new_expr_str=frac_expr,
            delete_tile=op
        )
        

def _has_profile(kind):
    """True if this tile kind has a registered merge profile."""
    try:
        from merge_profile import REGISTRY
        return REGISTRY.get(kind) is not None
    except Exception:
        return False


def _try_profile_merge(a, b, ctx):
    try:
        from merge_profile import REGISTRY, detect_position
        b_kind = getattr(b, 'kind', '')

        if b_kind == 'tool':
            expr = str(getattr(b, 'expr_str', getattr(b, 'text', '')) or '').split(':')[0].strip().lower()
            if expr not in ('sin', 'cos', 'tan', 'sec', 'csc', 'cot'):
                return None

        # Expr fractions (is_expr=True in meta) use the expr profile
        lookup_kind = b_kind
        if b_kind == 'fraction':
            meta = getattr(getattr(b, 'data', None), 'meta', {}) or {}
            if meta.get('is_expr', False):
                lookup_kind = 'expr'

        profile = REGISTRY.get(lookup_kind)
        if profile is None:
            return None

        board      = ctx.get('board')
        grid       = board.grid if board else 60
        drag_start = ctx.get('drag_start_center')

        if drag_start is None:
            return None
        if not _started_adjacent(drag_start, b, grid):
            return None

        position = detect_position(drag_start, b, grid)
        if position is None:
            position = ctx.get('spawn_direction')
        if position is None:
            return None

        simple_mode = getattr(board, 'simple_merge_mode', False)
        op = profile.resolve(a, b, position, simple_mode=simple_mode)
        if op is None:
            return None

        print(f"[PROFILE] {b_kind}(lookup={lookup_kind}) {position} -> {op.__class__.__name__}")
        return op.build_result(a, b, ctx)
    except Exception as e:
        print(f"[PROFILE_MERGE_ERROR] {e}")
        return None

def _try_profile_preview(a, b, ctx):
    try:
        from merge_profile import REGISTRY, detect_position
        b_kind = getattr(b, 'kind', '')

        if b_kind == 'tool':
            expr = str(getattr(b, 'expr_str', getattr(b, 'text', '')) or '').split(':')[0].strip().lower()
            if expr not in ('sin', 'cos', 'tan', 'sec', 'csc', 'cot'):
                return None

        # Expr fractions use the expr profile, same as _try_profile_merge
        lookup_kind = b_kind
        if b_kind == 'fraction':
            meta = getattr(getattr(b, 'data', None), 'meta', {}) or {}
            if meta.get('is_expr', False):
                lookup_kind = 'expr'

        profile = REGISTRY.get(lookup_kind)
        if profile is None:
            return None

        board      = ctx.get('board')
        grid       = board.grid if board else 60
        drag_start = ctx.get('drag_start_center')

        if drag_start is None:
            return None
        if not _started_adjacent(drag_start, b, grid):
            return None

        position = detect_position(drag_start, b, grid)
        if position is None:
            position = ctx.get('spawn_direction')
        if position is None:
            return None

        simple_mode = getattr(board, 'simple_merge_mode', False)
        op = profile.resolve(a, b, position, simple_mode=simple_mode)
        if op is None:
            return None

        return op.preview(a, b, ctx)
    except Exception as e:
        print(f"[PROFILE_PREVIEW_ERROR] {e}")
        return None

class MergeEngine:

    def __init__(self):
        self.rules = sorted([
            DiagonalLogRule(),
            DiagonalPowerRule(),
            DiagonalDecimalConcatRule(),
            DirectionalAddRule(),
            DirectionalSubtractRule(),
            DirectionalMultiplyRule(),
            VerticalDivideRule(),
            ConcatNumbersRule(),
            AppendNumberToExprRule(),
            NegateRule(),
            NegateOpRule(),
            ArmNumberWithOpRule(),
            EvaluateArmedOpRule(),
            ArmExprWithOpRule(),
            EvaluateArmedExprRule(),
            ArmFractionWithOpRule(),
            FillFractionRule(),
            MultiplyFractionsRule(),
            MultiplyFractionByNumRule(),
            ToolWrapSqrtRule(),
            SqrtRule(),
            LogRule(),
            SumRule(),
            ToolTrashDeleteRule(),
            FactorRule(),
            TrigRule(),
            DiffRule(),
            IntegrateRule(),
            FactorialRule(),
            RandomRule(),
            EqArmRule(),
            EqTransposeRule(),
            EqSubstRule(),
            FxRule(),
            ImplicitMultiplyRule(),
            ExprMultiplyRule(),
        ], key=lambda r: -r.priority)
        self._init_profiles()

    def _init_profiles(self):
        try:
            from profiles.number_profile   import register as reg_number
            from profiles.trig_profile     import register as reg_trig
            from profiles.fraction_profile import register as reg_fraction
            from profiles.expr_profile     import register as reg_expr
            reg_number()
            reg_trig()
            reg_fraction()
            reg_expr()
        except Exception as e:
            print(f"[PROFILE_INIT_ERROR] {e}")

    def add_rule(self, rule):
        self.rules.append(rule)
        self.rules.sort(key=lambda r: -r.priority)

    def try_merge(self, a, b, ctx):
        # Profile system first
        result = _try_profile_merge(a, b, ctx)
        if result is not None:
            return result

        b_kind = getattr(b, 'kind', '')
        if _has_profile(b_kind):
            # If drag started adjacent to border zone, profile said "no op" — respect that
            board      = ctx.get('board')
            drag_start = ctx.get('drag_start_center')
            grid       = board.grid if board else 60
            if drag_start and _started_adjacent(drag_start, b, grid):
                return None
            # Non-adjacent drop or keyboard (no drag_start) — fall through to concat/implicit rules

        # Legacy rules
        for rule in self.rules:
            try:
                if rule.can_apply(a, b, ctx):
                    res = rule.apply(a, b, ctx)
                    if res is not None:
                        return res
            except Exception as e:
                print(f"[RULE_ERROR] {rule.__class__.__name__}: {e}")
        return None

    def find_rule(self, a, b, ctx):
        for rule in self.rules:
            try:
                if rule.can_apply(a, b, ctx):
                    return rule
            except Exception:
                pass
        return None

    def find_preview(self, a, b, ctx):
        result = _try_profile_preview(a, b, ctx)
        if result is not None:
            return result

        b_kind = getattr(b, 'kind', '')
        # Expr fractions count as profiled
        if b_kind == 'fraction':
            meta = getattr(getattr(b, 'data', None), 'meta', {}) or {}
            if meta.get('is_expr', False):
                b_kind = 'expr'

        if _has_profile(b_kind):
            board      = ctx.get('board')
            drag_start = ctx.get('drag_start_center')
            grid       = board.grid if board else 60
            if drag_start and _started_adjacent(drag_start, b, grid):
                return None
            # Non-adjacent — allow legacy preview

        for rule in self.rules:
            try:
                if rule.can_apply(a, b, ctx):
                    preview = rule.preview_label(a, b, ctx)
                    if preview is not None:
                        return (preview, getattr(b, 'kind', 'number'), None)
            except Exception:
                pass
        return None











