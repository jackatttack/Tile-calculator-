"""
profiles/number_profile.py
==========================
MergeProfile for 'number', 'irrational', and 'expr' tile kinds.

Directional map:
    top_left     → log_a(b)
    above        → b ÷ a  (fraction or integer)
    top_right    → b ^ a  (power)
    left         → b − a
    right        → b + a
    bottom_left  → b mod a  (future — registered but returns None)
    below        → b × a
    bottom_right → decimal concat  (b.a)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sympy
from merge_profile import Operation, MergeProfile, REGISTRY


# ---------------------------------------------------------------------------
# Shared accepted kinds for number-family rules
# ---------------------------------------------------------------------------

_ACCEPTS = ('number', 'expr', 'irrational', 'fraction')
_NUMERIC  = ('number', 'irrational')            # no free symbols expected


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

class _AddOp(Operation):
    symbol  = '+'
    example = '3+4=7'
    accepts = _ACCEPTS
    simple  = True

    def compute(self, a_expr, b_expr):
        try:
            result = sympy.simplify(
                sympy.sympify(a_expr) + sympy.sympify(b_expr))
            return self._sympy_result_to_tuple(result)
        except Exception:
            return None

    def build_result(self, a, b, ctx):
        try:
            a_expr = self._get_expr(a)
            b_expr = self._get_expr(b)
            result = sympy.simplify(
                sympy.sympify(a_expr) + sympy.sympify(b_expr))
            print(f"[ADD] {b_expr} + {a_expr} -> {result}")
            return self._apply_sympy_result(a, b, result)
        except Exception as e:
            print(f"[ADD_ERROR] {e}")
            return None

    def _apply_sympy_result(self, a, b, result):
        if result.is_rational and not result.is_integer:
            n, d = sympy.fraction(result)
            return self._build_fraction_result(a, b, n, d)
        disp, kind = self._sympy_result_to_tuple(result)
        return self._standard_update(a, b, disp, kind)

    def _standard_update(self, a, b, disp, kind):
        from merge_engine import MergeResult
        from tile import Tile as _Tile
        color = _Tile.color_for_kind(kind)
        b.kind = kind
        b.set_label(disp)
        b.expr_str = disp
        b.set_cell_size(w_cells=1, h_cells=1,
                        cell_size=b.cell_size, gutter=b.gutter)
        try: b.data.display = disp
        except Exception: pass
        b.base_color = b.background_color = b.drag_color = color
        return MergeResult(replace_tile=b, delete_tile=a)

    def preview(self, a, b, ctx):
        try:
            result = sympy.simplify(
                sympy.sympify(self._get_expr(a)) +
                sympy.sympify(self._get_expr(b)))
            if result.is_rational and not result.is_integer:
                n, d = sympy.fraction(result)
                return (f"{n}/{d}", 'fraction', {
                    'numer_disp': str(n), 'denom_disp': str(d),
                    'numer_expr': str(n), 'denom_expr': str(d),
                    'frac_kind': 'number',
                })
            disp, kind = self._sympy_result_to_tuple(result)
            return (disp, kind, None)
        except Exception:
            return None


class _SubtractOp(_AddOp):
    symbol  = '−'
    example = '8−3=5'
    simple  = True

    def compute(self, a_expr, b_expr):
        try:
            result = sympy.simplify(
                sympy.sympify(b_expr) - sympy.sympify(a_expr))
            return self._sympy_result_to_tuple(result)
        except Exception:
            return None

    def build_result(self, a, b, ctx):
        try:
            a_expr = self._get_expr(a)
            b_expr = self._get_expr(b)
            result = sympy.simplify(
                sympy.sympify(b_expr) - sympy.sympify(a_expr))
            print(f"[SUB] {b_expr} - {a_expr} -> {result}")
            return self._apply_sympy_result(a, b, result)
        except Exception as e:
            print(f"[SUB_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            result = sympy.simplify(
                sympy.sympify(self._get_expr(b)) -
                sympy.sympify(self._get_expr(a)))
            if result.is_rational and not result.is_integer:
                n, d = sympy.fraction(result)
                return (f"{n}/{d}", 'fraction', {
                    'numer_disp': str(n), 'denom_disp': str(d),
                    'numer_expr': str(n), 'denom_expr': str(d),
                    'frac_kind': 'number',
                })
            disp, kind = self._sympy_result_to_tuple(result)
            return (disp, kind, None)
        except Exception:
            return None


class _MultiplyOp(_AddOp):
    symbol  = '×'
    example = '3×4=12'
    simple  = True

    def compute(self, a_expr, b_expr):
        try:
            result = sympy.simplify(
                sympy.sympify(a_expr) * sympy.sympify(b_expr))
            return self._sympy_result_to_tuple(result)
        except Exception:
            return None

    def build_result(self, a, b, ctx):
        try:
            a_expr = self._get_expr(a)
            b_expr = self._get_expr(b)
            result = sympy.simplify(
                sympy.sympify(a_expr) * sympy.sympify(b_expr))
            print(f"[MUL] {b_expr} × {a_expr} -> {result}")
            return self._apply_sympy_result(a, b, result)
        except Exception as e:
            print(f"[MUL_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            result = sympy.simplify(
                sympy.sympify(self._get_expr(a)) *
                sympy.sympify(self._get_expr(b)))
            if result.is_rational and not result.is_integer:
                n, d = sympy.fraction(result)
                return (f"{n}/{d}", 'fraction', {
                    'numer_disp': str(n), 'denom_disp': str(d),
                    'numer_expr': str(n), 'denom_expr': str(d),
                    'frac_kind': 'number',
                })
            disp, kind = self._sympy_result_to_tuple(result)
            return (disp, kind, None)
        except Exception:
            return None


class _DivideOp(_AddOp):
    symbol  = '÷'
    example = '6÷2=3'
    simple  = True

    def compute(self, a_expr, b_expr):
        try:
            n = sympy.sympify(b_expr)
            d = sympy.sympify(a_expr)
            if d == 0:
                return None
            result = sympy.simplify(n / d)
            return self._sympy_result_to_tuple(result)
        except Exception:
            return None

    def build_result(self, a, b, ctx):
        from merge_engine import MergeResult
        from tile import Tile as _Tile
        try:
            a_expr = self._get_expr(a)
            b_expr = self._get_expr(b)
            n_sym  = sympy.sympify(b_expr)
            d_sym  = sympy.sympify(a_expr)
            if d_sym == 0:
                return None
            print(f"[DIV] {b_expr} ÷ {a_expr}")

            result = sympy.simplify(n_sym / d_sym)

            # Integer result — simple update
            if result.is_integer:
                disp  = str(int(result))
                color = _Tile.color_for_kind('number')
                b.kind = 'number'
                b.set_label(disp)
                b.expr_str = disp
                b.set_cell_size(w_cells=1, h_cells=1,
                                cell_size=b.cell_size, gutter=b.gutter)
                try: b.data.display = disp
                except Exception: pass
                b.base_color = b.background_color = b.drag_color = color
                return MergeResult(replace_tile=b, delete_tile=a)

            # Rational → fraction tile — compute all values FIRST
            if result.is_rational:
                fn, fd = sympy.fraction(result)
                fn_str = str(int(fn)) if fn.is_integer else str(fn)
                fd_str = str(int(fd)) if fd.is_integer else str(fd)
                is_expr = False
            elif n_sym.free_symbols or d_sym.free_symbols:
                fn_str = str(n_sym)
                fd_str = str(d_sym)
                is_expr = True
            else:
                # Irrational decimal
                disp, kind = self._sympy_result_to_tuple(result)
                return self._standard_update(a, b, disp, kind)

            # Now apply fraction mutation atomically
            frac_kind = 'expr' if is_expr else 'number'
            color = _Tile.color_for_kind(frac_kind)

            # Ensure meta dict exists
            if not hasattr(b, 'data') or b.data is None:
                return None
            if not hasattr(b.data, 'meta') or b.data.meta is None:
                b.data.meta = {}

            b.kind = 'fraction'
            b.set_cell_size(w_cells=1, h_cells=2,
                            cell_size=b.cell_size, gutter=b.gutter)
            b.data.meta['numer_disp'] = fn_str
            b.data.meta['denom_disp'] = fd_str
            b.data.meta['numer_expr'] = fn_str
            b.data.meta['denom_expr'] = fd_str
            b.data.meta['is_expr']    = is_expr
            b.base_color = b.background_color = b.drag_color = color
            if hasattr(b, 'content_view') and b.content_view:
                b.content_view.background_color = color
            try:
                b._ensure_fraction_views()
                b._sync_fraction_from_meta()
                b.layout()
            except Exception as e:
                print(f"[DIV_FRAC_LAYOUT_ERROR] {e}")

            return MergeResult(replace_tile=b, delete_tile=a)

        except Exception as e:
            print(f"[DIV_ERROR] {e}")
            import traceback; traceback.print_exc()
            return None

    def preview(self, a, b, ctx):
        try:
            n = sympy.sympify(self._get_expr(b))
            d = sympy.sympify(self._get_expr(a))
            if d == 0:
                return None
            result = sympy.simplify(n / d)
            if result.is_integer:
                return (str(int(result)), 'number', None)
            if result.is_rational:
                fn, fd = sympy.fraction(result)
                return (f"{fn}/{fd}", 'fraction', {
                    'numer_disp': str(fn), 'denom_disp': str(fd),
                    'numer_expr': str(fn), 'denom_expr': str(fd),
                    'frac_kind': 'number',
                })
            nd = self._get_disp(b)
            dd = self._get_disp(a)
            return (f"{nd}/{dd}", 'fraction', {
                'numer_disp': nd, 'denom_disp': dd,
                'numer_expr': str(n), 'denom_expr': str(d),
                'frac_kind': 'expr' if (n.free_symbols or d.free_symbols) else 'number',
            })
        except Exception:
            return None


class _PowerOp(Operation):
    symbol  = '^'
    example = '23=8'
    accepts = _ACCEPTS
    simple  = False

    def compute(self, a_expr, b_expr):
        try:
            result = sympy.simplify(
                sympy.sympify(b_expr) ** sympy.sympify(a_expr))
            return self._sympy_result_to_tuple(result)
        except Exception:
            return None

    def build_result(self, a, b, ctx):
        from merge_engine import MergeResult
        from tile import Tile as _Tile
        try:
            a_expr = self._get_expr(a)
            b_expr = self._get_expr(b)
            result = sympy.simplify(
                sympy.sympify(b_expr) ** sympy.sympify(a_expr))
            print(f"[POW] {b_expr}^{a_expr} -> {result}")
            disp, kind = self._sympy_result_to_tuple(result)
            color = _Tile.color_for_kind(kind)
            b.kind = kind
            b.set_label(disp)
            b.expr_str = str(result)
            b.set_cell_size(w_cells=1, h_cells=1,
                            cell_size=b.cell_size, gutter=b.gutter)
            try: b.data.display = disp
            except Exception: pass
            b.base_color = b.background_color = b.drag_color = color
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[POW_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            result = sympy.simplify(
                sympy.sympify(self._get_expr(b)) **
                sympy.sympify(self._get_expr(a)))
            disp, kind = self._sympy_result_to_tuple(result)
            return (disp, kind, None)
        except Exception:
            return None


class _LogOp(Operation):
    symbol  = 'log'
    example = 'log28=3'
    accepts = _ACCEPTS
    simple  = False

    def compute(self, a_expr, b_expr):
        # a is base, b is argument
        try:
            base   = sympy.sympify(a_expr)
            arg    = sympy.sympify(b_expr)
            result = sympy.simplify(sympy.log(arg, base))
            return self._sympy_result_to_tuple(result)
        except Exception:
            return None

    def build_result(self, a, b, ctx):
        from merge_engine import MergeResult
        from tile import Tile as _Tile
        try:
            a_expr = self._get_expr(a)
            b_expr = self._get_expr(b)
            base   = sympy.sympify(a_expr)
            arg    = sympy.sympify(b_expr)
            result = sympy.simplify(sympy.log(arg, base))
            print(f"[LOG] log_{a_expr}({b_expr}) -> {result}")
            disp, kind = self._sympy_result_to_tuple(result)
            color = _Tile.color_for_kind(kind)
            b.kind = kind
            b.set_label(disp)
            b.expr_str = str(result)
            b.set_cell_size(w_cells=1, h_cells=1,
                            cell_size=b.cell_size, gutter=b.gutter)
            try: b.data.display = disp
            except Exception: pass
            b.base_color = b.background_color = b.drag_color = color
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[LOG_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            result = sympy.simplify(sympy.log(
                sympy.sympify(self._get_expr(b)),
                sympy.sympify(self._get_expr(a))))
            disp, kind = self._sympy_result_to_tuple(result)
            return (disp, kind, None)
        except Exception:
            return None


class _DecimalConcatOp(Operation):
    symbol  = '.'
    example = '8.7'
    accepts = ('number',)
    simple  = False

    def _is_plain(self, t):
        if getattr(t, 'kind', '') not in ('number', 'irrational'):
            return False
        try:
            float(str(getattr(t, 'expr_str', getattr(t, 'text', '')) or ''))
            return True
        except ValueError:
            return False

    def _concat(self, a_disp, b_disp):
        a_str = a_disp.lstrip('-')
        return f"{b_disp}.{a_str}" if '.' not in b_disp else f"{b_disp}{a_str}"

    def compute(self, a_expr, b_expr):
        try:
            result_str = self._concat(a_expr, b_expr)
            float(result_str)
            return (result_str, 'number')
        except Exception:
            return None

    def build_result(self, a, b, ctx):
        from merge_engine import MergeResult
        from tile import Tile as _Tile
        if not self._is_plain(a) or not self._is_plain(b):
            return None
        try:
            a_disp = self._get_disp(a)
            b_disp = self._get_disp(b)
            result_str = self._concat(a_disp, b_disp)
            float(result_str)
            print(f"[DEC_CONCAT] {b_disp} . {a_disp} -> {result_str}")
            color = _Tile.color_for_kind('number')
            b.kind = 'number'
            b.set_label(result_str)
            b.expr_str = result_str
            b.set_cell_size(w_cells=1, h_cells=1,
                            cell_size=b.cell_size, gutter=b.gutter)
            try: b.data.display = result_str
            except Exception: pass
            b.base_color = b.background_color = b.drag_color = color
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[DEC_CONCAT_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        if not self._is_plain(a) or not self._is_plain(b):
            return None
        try:
            result_str = self._concat(self._get_disp(a), self._get_disp(b))
            float(result_str)
            return (result_str, 'number', None)
        except Exception:
            return None


class _ModuloOp(Operation):
    """Placeholder — bottom_left diagonal, not yet implemented."""
    symbol  = 'mod'
    example = '7mod3=1'
    accepts = ()   # empty = never fires
    simple  = False

    def compute(self, a_expr, b_expr):
        return None


# ---------------------------------------------------------------------------
# Build and register number profile
# ---------------------------------------------------------------------------

NUMBER_PROFILE = MergeProfile(
    kind        = 'number',
    directional = {
        'left':         _AddOp(),
        'right':        _SubtractOp(),
        'above':        _MultiplyOp(),
        'below':        _DivideOp(),
        'top_right':    _PowerOp(),
        'top_left':     _LogOp(),
        'bottom_right': _DecimalConcatOp(),
        'bottom_left':  _ModuloOp(),
    },
    accepts          = _ACCEPTS,
    simple_positions = {'left', 'right', 'above', 'below'},
)

IRRATIONAL_PROFILE = MergeProfile(
    kind        = 'irrational',
    directional = {
        'left':         _AddOp(),
        'right':        _SubtractOp(),
        'above':        _MultiplyOp(),
        'below':        _DivideOp(),
        'top_right':    _PowerOp(),
        'top_left':     _LogOp(),
        'bottom_right': _DecimalConcatOp(),
        'bottom_left':  _ModuloOp(),
    },
    accepts          = _ACCEPTS,
    simple_positions = {'left', 'right', 'above', 'below'},
)

# Same operations apply to expr and irrational tiles as the target
EXPR_PROFILE = MergeProfile(
    kind        = 'expr',
    directional = NUMBER_PROFILE.directional,   # shared op instances
    accepts     = _ACCEPTS,
    simple_positions = NUMBER_PROFILE.simple_positions,
)

IRRATIONAL_PROFILE = MergeProfile(
    kind        = 'irrational',
    directional = NUMBER_PROFILE.directional,
    accepts     = _ACCEPTS,
    simple_positions = NUMBER_PROFILE.simple_positions,
)

FRACTION_PROFILE = MergeProfile(
    kind        = 'fraction',
    directional = {
        'right':  _AddOp(),
        'left':   _SubtractOp(),
        'below':  _MultiplyOp(),
    },
    accepts         = _ACCEPTS,
    simple_positions = {'right', 'left', 'below'},
)


def register():
    REGISTRY.register(NUMBER_PROFILE)
    REGISTRY.register(IRRATIONAL_PROFILE)
    print("[PROFILES] number/irrational registered")
