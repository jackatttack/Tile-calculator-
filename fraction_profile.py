import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sympy
from merge_profile import Operation, MergeProfile, REGISTRY
from merge_engine import MergeResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_frac(tile):
    """Return (numer_expr, denom_expr, numer_disp, denom_disp, is_expr)."""
    meta = tile.data.meta if (hasattr(tile, 'data') and tile.data) else {}
    return (
        meta.get('numer_expr', '1'),
        meta.get('denom_expr', '1'),
        meta.get('numer_disp', '1'),
        meta.get('denom_disp', '1'),
        bool(meta.get('is_expr', False)),
    )


def _get_num(tile):
    """Get expression string from any tile, including fractions."""
    if getattr(tile, 'kind', '') == 'fraction':
        ne, de, _, _, _ = _get_frac(tile)
        return f"({ne})/({de})"
    return str(getattr(tile, 'expr_str', getattr(tile, 'text', '1')) or '1').strip()

def _is_frac(tile):
    return getattr(tile, 'kind', '') == 'fraction'


def _apply_frac(tile, n_sym, d_sym, is_expr):
    """Mutate tile into a fraction in-place."""
    from tile import Tile as _Tile
    n_str = str(int(n_sym)) if (n_sym.is_integer and not is_expr) else str(n_sym)
    d_str = str(int(d_sym)) if (d_sym.is_integer and not is_expr) else str(d_sym)
    frac_kind = 'expr' if is_expr else 'number'
    color = _Tile.color_for_kind(frac_kind)

    tile.kind = 'fraction'
    tile.set_cell_size(w_cells=1, h_cells=2,
                       cell_size=tile.cell_size, gutter=tile.gutter)
    tile.data.meta['numer_disp'] = n_str
    tile.data.meta['denom_disp'] = d_str
    tile.data.meta['numer_expr'] = n_str
    tile.data.meta['denom_expr'] = d_str
    tile.data.meta['is_expr']    = is_expr
    tile.base_color = tile.background_color = tile.drag_color = color
    if hasattr(tile, 'content_view') and tile.content_view:
        tile.content_view.background_color = color
    try:
        tile._ensure_fraction_views()
        tile._sync_fraction_from_meta()
        tile.layout()
    except Exception as e:
        print(f"[FRAC_APPLY_ERROR] {e}")


def _result_to_merge(result_sym, frac_tile, del_tile):
    """
    Resolve a sympy result onto frac_tile.
    Integer -> collapse to number tile.
    Rational -> stay as fraction.
    Irrational -> decimal number.
    Symbolic -> keep as expr fraction.
    """
    from tile import Tile as _Tile
    try:
        simplified = sympy.simplify(result_sym)

        if simplified.is_integer and not simplified.free_symbols:
            disp  = str(int(simplified))
            color = _Tile.color_for_kind('number')
            frac_tile.kind = 'number'
            frac_tile.set_label(disp)
            frac_tile.expr_str = disp
            frac_tile.set_cell_size(w_cells=1, h_cells=1,
                                    cell_size=frac_tile.cell_size,
                                    gutter=frac_tile.gutter)
            try: frac_tile.data.display = disp
            except Exception: pass
            frac_tile.base_color = frac_tile.background_color = frac_tile.drag_color = color
            return MergeResult(replace_tile=frac_tile, delete_tile=del_tile)

        if simplified.is_rational and not simplified.free_symbols:
            n, d = sympy.fraction(simplified)
            _apply_frac(frac_tile, n, d, is_expr=False)
            return MergeResult(replace_tile=frac_tile, delete_tile=del_tile)

        if simplified.free_symbols:
            n, d = sympy.fraction(simplified)
            _apply_frac(frac_tile, n, d, is_expr=True)
            return MergeResult(replace_tile=frac_tile, delete_tile=del_tile)

        # Irrational — evaluate to decimal
        try:
            fval = float(simplified.evalf())
            import math
            if not math.isnan(fval) and not math.isinf(fval):
                from merge_engine import _round_decimal
                if fval == int(fval) and abs(fval) < 1e15:
                    disp = str(int(fval))
                else:
                    disp = _round_decimal(f"{fval:.8f}")
                color = _Tile.color_for_kind('number')
                frac_tile.kind = 'number'
                frac_tile.set_label(disp)
                frac_tile.expr_str = disp
                frac_tile.set_cell_size(w_cells=1, h_cells=1,
                                        cell_size=frac_tile.cell_size,
                                        gutter=frac_tile.gutter)
                frac_tile.base_color = frac_tile.background_color = frac_tile.drag_color = color
                return MergeResult(replace_tile=frac_tile, delete_tile=del_tile)
        except Exception:
            pass

        # Last resort — symbolic fraction
        n, d = sympy.fraction(simplified)
        _apply_frac(frac_tile, n, d, is_expr=True)
        return MergeResult(replace_tile=frac_tile, delete_tile=del_tile)

    except Exception as e:
        print(f"[FRAC_RESULT_ERROR] {e}")
        return None


def _preview_result(result_sym):
    """Return (disp, kind, extra) preview tuple from a sympy result."""
    try:
        s = sympy.simplify(result_sym)
        if s.is_integer and not s.free_symbols:
            return (str(int(s)), 'number', None)
        if s.is_rational and not s.free_symbols:
            n, d = sympy.fraction(s)
            return (f"{n}/{d}", 'fraction', {
                'numer_disp': str(n), 'denom_disp': str(d),
                'numer_expr': str(n), 'denom_expr': str(d),
                'frac_kind': 'number',
            })
        if s.free_symbols:
            n, d = sympy.fraction(s)
            return (f"{n}/{d}", 'fraction', {
                'numer_disp': str(n), 'denom_disp': str(d),
                'numer_expr': str(n), 'denom_expr': str(d),
                'frac_kind': 'expr',
            })
        try:
            fval = float(s.evalf())
            import math
            if not math.isnan(fval) and not math.isinf(fval):
                from merge_engine import _round_decimal
                disp = str(int(fval)) if fval == int(fval) else _round_decimal(f"{fval:.8f}")
                return (disp, 'number', None)
        except Exception:
            pass
        return (str(s), 'expr', None)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class _FracOpBase(Operation):
    accepts = ('number', 'irrational', 'expr', 'fraction')
    simple  = True
    symbol  = '?'
    example = ''

    def _frac_sym(self, tile):
        ne, de, _, _, _ = _get_frac(tile)
        return sympy.sympify(ne), sympy.sympify(de)

    def _num_sym(self, tile):
        return sympy.sympify(_get_num(tile))


# ---------------------------------------------------------------------------
# Cardinal operations
# ---------------------------------------------------------------------------

class _FracAddOp(_FracOpBase):
    symbol  = '+'
    example = '1/2+1=3/2'
    simple  = True

    def build_result(self, a, b, ctx):
        try:
            bn, bd = self._frac_sym(b)
            av = (self._frac_sym(a)[0] / self._frac_sym(a)[1]
                  if _is_frac(a) else self._num_sym(a))
            return _result_to_merge(bn/bd + av, b, a)
        except Exception as e:
            print(f"[FRAC_ADD_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            bn, bd = self._frac_sym(b)
            av = (self._frac_sym(a)[0] / self._frac_sym(a)[1]
                  if _is_frac(a) else self._num_sym(a))
            return _preview_result(bn/bd + av)
        except Exception:
            return None


class _FracSubOp(_FracOpBase):
    symbol  = '-'
    example = '3/4-1=-1/4'
    simple  = True

    def build_result(self, a, b, ctx):
        try:
            bn, bd = self._frac_sym(b)
            av = (self._frac_sym(a)[0] / self._frac_sym(a)[1]
                  if _is_frac(a) else self._num_sym(a))
            return _result_to_merge(bn/bd - av, b, a)
        except Exception as e:
            print(f"[FRAC_SUB_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            bn, bd = self._frac_sym(b)
            av = (self._frac_sym(a)[0] / self._frac_sym(a)[1]
                  if _is_frac(a) else self._num_sym(a))
            return _preview_result(bn/bd - av)
        except Exception:
            return None


class _FracMulOp(_FracOpBase):
    symbol  = 'x'
    example = '2/3x3=2'
    simple  = True

    def build_result(self, a, b, ctx):
        try:
            bn, bd = self._frac_sym(b)
            if _is_frac(a):
                an, ad = self._frac_sym(a)
                result = (bn * an) / (bd * ad)
            else:
                av = self._num_sym(a)
                result = (bn * av) / bd
            return _result_to_merge(result, b, a)
        except Exception as e:
            print(f"[FRAC_MUL_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            bn, bd = self._frac_sym(b)
            if _is_frac(a):
                an, ad = self._frac_sym(a)
                result = (bn * an) / (bd * ad)
            else:
                result = (bn * self._num_sym(a)) / bd
            return _preview_result(result)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Diagonal operations
# ---------------------------------------------------------------------------

class _FracReplaceNumerOp(_FracOpBase):
    symbol  = 'n<'
    example = 'a/d replaces n'
    simple  = False

    def build_result(self, a, b, ctx):
        try:
            ne, de, nd, dd, _ = _get_frac(b)
            n_str = _get_num(a)
            n_sym = sympy.sympify(n_str)
            d_sym = sympy.sympify(de)
            is_expr = bool(n_sym.free_symbols or d_sym.free_symbols)
            _apply_frac(b, n_sym, d_sym, is_expr)
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[FRAC_REPL_N_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            ne, de, nd, dd, _ = _get_frac(b)
            n_str = _get_num(a)
            is_expr = bool(sympy.sympify(n_str).free_symbols)
            return (f"{n_str}/{dd}", 'fraction', {
                'numer_disp': n_str, 'denom_disp': dd,
                'numer_expr': n_str, 'denom_expr': de,
                'frac_kind': 'expr' if is_expr else 'number',
            })
        except Exception:
            return None


class _FracReplaceDenomOp(_FracOpBase):
    symbol  = 'd<'
    example = 'n/b replaces d'
    simple  = False

    def build_result(self, a, b, ctx):
        try:
            ne, de, nd, dd, _ = _get_frac(b)
            d_str = _get_num(a)
            d_sym = sympy.sympify(d_str)
            if d_sym == 0:
                return None
            n_sym = sympy.sympify(ne)
            is_expr = bool(n_sym.free_symbols or d_sym.free_symbols)
            _apply_frac(b, n_sym, d_sym, is_expr)
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[FRAC_REPL_D_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            ne, de, nd, dd, _ = _get_frac(b)
            d_str = _get_num(a)
            is_expr = bool(sympy.sympify(d_str).free_symbols)
            return (f"{nd}/{d_str}", 'fraction', {
                'numer_disp': nd, 'denom_disp': d_str,
                'numer_expr': ne, 'denom_expr': d_str,
                'frac_kind': 'expr' if is_expr else 'number',
            })
        except Exception:
            return None


class _FracConcatNumerOp(_FracOpBase):
    symbol  = 'n+'
    example = '(n+a)/d'
    simple  = False

    def build_result(self, a, b, ctx):
        try:
            ne, de, nd, dd, _ = _get_frac(b)
            a_str = _get_num(a)
            # Store display strings directly — do NOT pass through sympy
            # or it will evaluate e.g. (1)+(2) -> 3, losing display form
            new_ne = f"({ne})+({a_str})"
            new_nd = f"({nd})+{a_str}"
            if not hasattr(b.data, 'meta') or b.data.meta is None:
                b.data.meta = {}
            b.kind = 'fraction'
            b.set_cell_size(w_cells=1, h_cells=2, cell_size=b.cell_size, gutter=b.gutter)
            b.data.meta['numer_disp'] = new_nd
            b.data.meta['denom_disp'] = dd
            b.data.meta['numer_expr'] = new_ne
            b.data.meta['denom_expr'] = de
            b.data.meta['is_expr']    = True
            from tile import Tile as _Tile
            color = _Tile.color_for_kind('expr')
            b.base_color = b.background_color = b.drag_color = color
            if hasattr(b, 'content_view') and b.content_view:
                b.content_view.background_color = color
            try:
                b._ensure_fraction_views()
                b._sync_fraction_from_meta()
                b.layout()
            except Exception as e:
                print(f"[FRAC_CONCAT_N_LAYOUT_ERROR] {e}")
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[FRAC_CONCAT_N_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            ne, de, nd, dd, _ = _get_frac(b)
            a_str = _get_num(a)
            return (f"({nd}+{a_str})/{dd}", 'fraction', {
                'numer_disp': f"({nd})+{a_str}", 'denom_disp': dd,
                'numer_expr': f"({ne})+({a_str})", 'denom_expr': de,
                'frac_kind': 'expr',
            })
        except Exception:
            return None


class _FracConcatDenomOp(_FracOpBase):
    symbol  = 'd+'
    example = 'n/(d+a)'
    simple  = False

    def build_result(self, a, b, ctx):
        try:
            ne, de, nd, dd, _ = _get_frac(b)
            a_str = _get_num(a)
            new_de = f"({de})+({a_str})"
            new_dd = f"({dd})+{a_str}"
            if not hasattr(b.data, 'meta') or b.data.meta is None:
                b.data.meta = {}
            b.kind = 'fraction'
            b.set_cell_size(w_cells=1, h_cells=2, cell_size=b.cell_size, gutter=b.gutter)
            b.data.meta['numer_disp'] = nd
            b.data.meta['denom_disp'] = new_dd
            b.data.meta['numer_expr'] = ne
            b.data.meta['denom_expr'] = new_de
            b.data.meta['is_expr']    = True
            from tile import Tile as _Tile
            color = _Tile.color_for_kind('expr')
            b.base_color = b.background_color = b.drag_color = color
            if hasattr(b, 'content_view') and b.content_view:
                b.content_view.background_color = color
            try:
                b._ensure_fraction_views()
                b._sync_fraction_from_meta()
                b.layout()
            except Exception as e:
                print(f"[FRAC_CONCAT_D_LAYOUT_ERROR] {e}")
            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[FRAC_CONCAT_D_ERROR] {e}")
            return None

    def preview(self, a, b, ctx):
        try:
            ne, de, nd, dd, _ = _get_frac(b)
            a_str = _get_num(a)
            return (f"{nd}/({dd}+{a_str})", 'fraction', {
                'numer_disp': nd, 'denom_disp': f"({dd})+{a_str}",
                'numer_expr': ne, 'denom_expr': f"({de})+({a_str})",
                'frac_kind': 'expr',
            })
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Profile registration
# ---------------------------------------------------------------------------

FRACTION_PROFILE = MergeProfile(
    kind        = 'fraction',
    directional = {
        'right':        _FracSubOp(),
        'left':         _FracAddOp(),
        'below':        _FracMulOp(),
        'top_left':     _FracReplaceNumerOp(),
        'bottom_left':  _FracReplaceDenomOp(),
        'top_right':    _FracConcatNumerOp(),
        'bottom_right': _FracConcatDenomOp(),
    },
    accepts          = ('number', 'irrational', 'expr', 'fraction'),
    simple_positions = {'right', 'left', 'below'},
)

REGISTRY.register(FRACTION_PROFILE)

def register():
    pass  # registration happens at import time
