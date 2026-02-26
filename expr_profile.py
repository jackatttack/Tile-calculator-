import os
import sys

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sympy

from merge_profile import Operation, MergeProfile, REGISTRY
from merge_engine import MergeResult


# ---------------------------------------------------------------------------
# Path setup (optional)
# ---------------------------------------------------------------------------

# NOTE:
# Your pasted version had markdown-bold **file** which breaks Python.
# This keeps the same intent: add the project root (two levels up) to sys.path.



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_expr(tile):
    """Get a sympy-parseable expression string from any tile."""
    if getattr(tile, 'kind', '') == 'fraction':
        meta = getattr(getattr(tile, 'data', None), 'meta', {}) or {}
        ne = meta.get('numer_expr', '1')
        de = meta.get('denom_expr', '1')
        return f"({ne})/({de})"
    return str(getattr(tile, 'expr_str', getattr(tile, 'text', '0')) or '0').strip()


def _get_disp(tile):
    if getattr(tile, 'kind', '') == 'fraction':
        meta = getattr(getattr(tile, 'data', None), 'meta', {}) or {}
        return f"{meta.get('numer_disp', '?')}/{meta.get('denom_disp', '?')}"
    return str(getattr(tile, 'text', getattr(tile, 'expr_str', '0')) or '0').strip()


def _is_variable(tile):
    """True if tile is a single symbolic variable (x, t, n, etc.)."""
    try:
        s = sympy.sympify(_get_expr(tile))
        return bool(getattr(s, 'is_Symbol', False))
    except Exception:
        return False


def _is_numeric(tile):
    """True if tile evaluates to a pure number (no free symbols)."""
    try:
        s = sympy.sympify(_get_expr(tile))
        return not bool(getattr(s, 'free_symbols', set()))
    except Exception:
        return False


def _is_expression(tile):
    """True if tile has free symbols (symbolic expression)."""
    try:
        s = sympy.sympify(_get_expr(tile))
        return bool(getattr(s, 'free_symbols', set()))
    except Exception:
        return False


def _pretty_expr(sym):
    """Convert sympy expr to readable string: 2*x**2 -> 2x^2"""
    s = str(sym)
    import re
    # x**n -> x^n
    s = re.sub(r'\*\*(\w+)', r'^\1', s)
    # 2*x -> 2x, x*2 -> 2x (simple cases)
    s = re.sub(r'(\d)\*([a-zA-Z])', r'\1\2', s)
    s = re.sub(r'([a-zA-Z])\*(\d)', r'\2\1', s)
    # x*y -> xy for single letter vars
    s = re.sub(r'([a-zA-Z])\*([a-zA-Z])', r'\1\2', s)
    return s


def _pretty_expr(sym):
    """Convert sympy expr to readable string: 2*x**2 -> 2x^2"""
    import re
    s = str(sym)
    s = re.sub(r'\*\*(\w+)', r'^\1', s)
    s = re.sub(r'(\d)\*([a-zA-Z])', r'\1\2', s)
    s = re.sub(r'([a-zA-Z])\*(\d)', r'\2\1', s)
    s = re.sub(r'([a-zA-Z])\*([a-zA-Z])', r'\1\2', s)
    return s


def _pretty_expr(sym):
    import re
    s = str(sym)
    s = re.sub(r'\*\*(\w+)', r'^\1', s)
    s = re.sub(r'(\d)\*([a-zA-Z])', r'\1\2', s)
    s = re.sub(r'([a-zA-Z])\*(\d)', r'\2\1', s)
    s = re.sub(r'([a-zA-Z])\*([a-zA-Z])', r'\1\2', s)
    return s


def _format_result(sym):
    """Turn a sympy result into (disp, kind, expr_str)."""
    try:
        from merge_engine import _pretty
        simplified = sympy.simplify(sym)
        expr_str = str(simplified)

        if not simplified.free_symbols:
            try:
                fval = float(simplified.evalf())
                import math
                if math.isnan(fval) or math.isinf(fval):
                    raise ValueError
                if fval == int(fval) and abs(fval) < 1e15:
                    disp = str(int(fval))
                    return (disp, 'number', disp)
                try:
                    from merge_engine import _round_decimal
                    disp = _round_decimal(f"{fval:.8f}")
                except Exception:
                    disp = f"{fval:.8f}".rstrip('0').rstrip('.')
                return (disp, 'number', disp)
            except Exception:
                pass
            return (_pretty(simplified), 'irrational', expr_str)

        # Symbolic fraction - store raw sympy in expr_str, pretty in disp
        n, d = sympy.fraction(simplified)
        if d != 1:
            return (_pretty(n) + '/' + _pretty(d), 'fraction', expr_str)

        return (_pretty(simplified), 'expr', expr_str)

    except Exception as e:
        print(f"[EXPR_FORMAT_ERROR] {e}")
        s = str(sym)
        return (s, 'expr', s)

def _apply_to_tile(tile, disp, kind, expr_str):
    """Mutate tile to show a result. Handles fraction results."""
    from tile import Tile as _Tile
    from merge_engine import _pretty

    if kind == 'fraction':
        try:
            import sympy as _sympy
            sym = _sympy.sympify(expr_str)
            n, d = _sympy.fraction(sym)
            # Store raw sympy strings - _sync_fraction_from_meta will pretty-print
            n_raw = str(n)
            d_raw = str(d)
            is_expr = bool(sym.free_symbols)
            frac_kind = 'expr' if is_expr else 'number'
            color = _Tile.color_for_kind(frac_kind)
            tile.kind = 'fraction'
            tile.set_cell_size(w_cells=1, h_cells=2,
                               cell_size=tile.cell_size, gutter=tile.gutter)
            if not hasattr(tile.data, 'meta') or tile.data.meta is None:
                tile.data.meta = {}
            tile.data.meta['numer_disp'] = n_raw   # raw - pretty applied in _sync
            tile.data.meta['denom_disp'] = d_raw
            tile.data.meta['numer_expr'] = n_raw
            tile.data.meta['denom_expr'] = d_raw
            tile.data.meta['is_expr']    = is_expr
            tile.base_color = tile.background_color = tile.drag_color = color
            if hasattr(tile, 'content_view') and tile.content_view:
                tile.content_view.background_color = color
            try:
                tile._ensure_fraction_views()
                tile._sync_fraction_from_meta()
                tile.layout()
            except Exception as e:
                print(f"[APPLY_FRAC_ERROR] {e}")
            return
        except Exception as e:
            print(f"[APPLY_TO_TILE_FRAC_ERROR] {e}")

    color = _Tile.color_for_kind(kind)
    tile.kind = kind
    tile.set_label(disp)
    tile.expr_str = expr_str
    try:
        tile.data.display = disp
    except Exception:
        pass
    tile.base_color = tile.background_color = tile.drag_color = color
    if hasattr(tile, 'content_view') and tile.content_view:
        tile.content_view.background_color = color
    if getattr(tile, 'h_cells', 1) != 1 or getattr(tile, 'w_cells', 1) != 1:
        tile.set_cell_size(w_cells=1, h_cells=1,
                           cell_size=tile.cell_size, gutter=tile.gutter)

class _ExprOpBase(Operation):
    accepts = ('number', 'irrational', 'expr', 'fraction')
    simple = True
    symbol = '?'
    example = ''


# ---------------------------------------------------------------------------
# Cardinal operations
# ---------------------------------------------------------------------------

class _ExprAddOp(_ExprOpBase):
    symbol = '+'
    example = 'x+2'
    simple = True

    def build_result(self, a, b, ctx):
        try:
            bs = sympy.sympify(_get_expr(b))
            as_ = sympy.sympify(_get_expr(a))
            disp, kind, expr_str = _format_result(bs + as_)
            _apply_to_tile(b, disp, kind, expr_str)
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[EXPR_ADD_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            bs = sympy.sympify(_get_expr(b))
            as_ = sympy.sympify(_get_expr(a))
            disp, kind, _ = _format_result(bs + as_)
            return (disp, kind, None)
        except Exception:
            return None


class _ExprSubOp(_ExprOpBase):
    symbol = '-'
    example = 'x-2'
    simple = True

    def build_result(self, a, b, ctx):
        try:
            bs = sympy.sympify(_get_expr(b))
            as_ = sympy.sympify(_get_expr(a))
            disp, kind, expr_str = _format_result(bs - as_)
            _apply_to_tile(b, disp, kind, expr_str)
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[EXPR_SUB_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            bs = sympy.sympify(_get_expr(b))
            as_ = sympy.sympify(_get_expr(a))
            disp, kind, _ = _format_result(bs - as_)
            return (disp, kind, None)
        except Exception:
            return None


class _ExprMulOp(_ExprOpBase):
    symbol = 'x'
    example = '2*(x+1)'
    simple = True

    def build_result(self, a, b, ctx):
        try:
            bs = sympy.sympify(_get_expr(b))
            as_ = sympy.sympify(_get_expr(a))
            disp, kind, expr_str = _format_result(bs * as_)
            _apply_to_tile(b, disp, kind, expr_str)
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[EXPR_MUL_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            bs = sympy.sympify(_get_expr(b))
            as_ = sympy.sympify(_get_expr(a))
            disp, kind, _ = _format_result(bs * as_)
            return (disp, kind, None)
        except Exception:
            return None


class _ExprDivOp(_ExprOpBase):
    """Make a fraction: dragged becomes denominator."""
    symbol = '/'
    example = '(x+1)/2'
    simple = True

    def build_result(self, a, b, ctx):
        try:
            from tile import Tile as _Tile

            bs = sympy.sympify(_get_expr(b))
            as_ = sympy.sympify(_get_expr(a))
            if as_ == 0:
                return None

            result = sympy.simplify(bs / as_)

            # Integer numeric result - collapse
            if result.is_integer and not result.free_symbols:
                disp = str(int(result))
                _apply_to_tile(b, disp, 'number', disp)
                return MergeResult(replace_tile=b, delete_tile=a)

            # Build fraction tile
            n_sym, d_sym = sympy.fraction(result)
            n_str = str(n_sym)
            d_str = str(d_sym)

            is_expr = bool(result.free_symbols)
            frac_kind = 'expr' if is_expr else 'number'
            color = _Tile.color_for_kind(frac_kind)

            b.kind = 'fraction'
            b.set_cell_size(
                w_cells=1,
                h_cells=2,
                cell_size=b.cell_size,
                gutter=b.gutter
            )

            if not hasattr(b.data, 'meta') or b.data.meta is None:
                b.data.meta = {}

            b.data.meta['numer_disp'] = n_str
            b.data.meta['denom_disp'] = d_str
            b.data.meta['numer_expr'] = n_str
            b.data.meta['denom_expr'] = d_str
            b.data.meta['is_expr'] = is_expr

            b.base_color = color
            b.background_color = color
            b.drag_color = color

            if hasattr(b, 'content_view') and b.content_view:
                b.content_view.background_color = color

            try:
                b._ensure_fraction_views()
                b._sync_fraction_from_meta()
                b.layout()
            except Exception as e:
                print(f"[EXPR_DIV_LAYOUT_ERROR] {e}")

            return MergeResult(replace_tile=b, delete_tile=a)

        except Exception as e:
            print(f"[EXPR_DIV_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            bs = sympy.sympify(_get_expr(b))
            as_ = sympy.sympify(_get_expr(a))
            if as_ == 0:
                return None

            result = sympy.simplify(bs / as_)

            if result.is_integer and not result.free_symbols:
                return (str(int(result)), 'number', None)

            n, d = sympy.fraction(result)
            is_expr = bool(result.free_symbols)

            return (f"{n}/{d}", 'fraction', {
                'numer_disp': str(n),
                'denom_disp': str(d),
                'numer_expr': str(n),
                'denom_expr': str(d),
                'frac_kind': 'expr' if is_expr else 'number',
            })
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Diagonal operations
# ---------------------------------------------------------------------------

class _ExprPowerOp(_ExprOpBase):
    """top_right: raise expression to power of dragged."""
    symbol = '^'
    example = 'x^2'
    simple = False

    def build_result(self, a, b, ctx):
        try:
            bs = sympy.sympify(_get_expr(b))
            as_ = sympy.sympify(_get_expr(a))
            disp, kind, expr_str = _format_result(bs ** as_)
            _apply_to_tile(b, disp, kind, expr_str)
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[EXPR_POW_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            bs = sympy.sympify(_get_expr(b))
            as_ = sympy.sympify(_get_expr(a))
            disp, kind, _ = _format_result(bs ** as_)
            return (disp, kind, None)
        except Exception:
            return None


class _ExprSubstituteOp(_ExprOpBase):
    """
    top_left: smart substitute.
    - Dragged is numeric: subs into expr, spawns result, expr survives.
    - Dragged is expression: composes f(g(x)), mutates target, consumes dragged.
    """
    symbol = 'f(a)'
    example = 'f(x) sub a'
    simple = False

    def build_result(self, a, b, ctx):
        try:
            b_sym = sympy.sympify(_get_expr(b))
            a_sym = sympy.sympify(_get_expr(a))
            x = sympy.Symbol('x')

            result = b_sym.subs(x, a_sym)
            disp, kind, expr_str = _format_result(result)

            if _is_numeric(a):
                # Spawn result, delete number tile, keep expression tile unchanged
                spawn_spec = {
                    'text':     disp,
                    'kind':     kind,
                    'expr_str': expr_str,
                    'display':  disp,
                }
                return MergeResult(
                    replace_tile=b,
                    delete_tile=a,
                    spawn_spec=spawn_spec,
                    spawn_direction=ctx.get('spawn_direction', 'right'),
                    no_sticky=True,
                )

            # Compose: f(g(x)) — mutate target, consume dragged
            _apply_to_tile(b, disp, kind, expr_str)
            return MergeResult(replace_tile=b, delete_tile=a)

        except Exception as e:
            print(f"[EXPR_SUBS_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            b_sym = sympy.sympify(_get_expr(b))
            a_sym = sympy.sympify(_get_expr(a))
            x = sympy.Symbol('x')
            result = b_sym.subs(x, a_sym)
            disp, kind, _ = _format_result(result)
            return (disp, kind, None)
        except Exception:
            return None


class _ExprIntegrateOp(_ExprOpBase):
    """
    bottom_left: integrate with respect to dragged variable.
    Only fires if dragged is a single symbol.
    """
    symbol = 'integral'
    example = 'integralx dx'
    simple = False

    def can_apply(self, a, b, ctx):
        return _is_variable(a)

    def build_result(self, a, b, ctx):
        try:
            b_sym = sympy.sympify(_get_expr(b))
            var = sympy.sympify(_get_expr(a))
            result = sympy.integrate(b_sym, var)
            disp, kind, expr_str = _format_result(result)
            _apply_to_tile(b, disp, kind, expr_str)
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[EXPR_INT_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        if not _is_variable(a):
            return None
        try:
            b_sym = sympy.sympify(_get_expr(b))
            var = sympy.sympify(_get_expr(a))
            result = sympy.integrate(b_sym, var)
            disp, kind, _ = _format_result(result)
            return (disp, kind, None)
        except Exception:
            return None


class _ExprDifferentiateOp(_ExprOpBase):
    """
    bottom_right: differentiate with respect to dragged variable.
    Only fires if dragged is a single symbol.
    """
    symbol = 'd/dx'
    example = 'd/dx x^2'
    simple = False

    def can_apply(self, a, b, ctx):
        return _is_variable(a)

    def build_result(self, a, b, ctx):
        try:
            b_sym = sympy.sympify(_get_expr(b))
            var = sympy.sympify(_get_expr(a))
            result = sympy.diff(b_sym, var)
            disp, kind, expr_str = _format_result(result)
            _apply_to_tile(b, disp, kind, expr_str)
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[EXPR_DIFF_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        if not _is_variable(a):
            return None
        try:
            b_sym = sympy.sympify(_get_expr(b))
            var = sympy.sympify(_get_expr(a))
            result = sympy.diff(b_sym, var)
            disp, kind, _ = _format_result(result)
            return (disp, kind, None)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Profile registration
# ---------------------------------------------------------------------------

EXPR_PROFILE = MergeProfile(
    kind='expr',
    directional={
        'left': _ExprAddOp(),
        'right': _ExprSubOp(),
        'above': _ExprMulOp(),
        'below': _ExprDivOp(),
        'top_right': _ExprPowerOp(),
        'top_left': _ExprSubstituteOp(),
        'bottom_left': _ExprIntegrateOp(),
        'bottom_right': _ExprDifferentiateOp(),
    },
    accepts=('number', 'irrational', 'expr', 'fraction'),
    simple_positions={'left', 'right', 'above', 'below'},
)

REGISTRY.register(EXPR_PROFILE)


def register():
    # Registration happens at import time.
    pass
