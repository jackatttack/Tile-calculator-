"""
profiles/trig_profile.py
========================
MergeProfile for 'trig_tool' tile kind.

Directional map:
    right        → trig in radians          sin(x)
    left         → inverse trig in radians  sin−1(x)
    above        → trig in degrees          sin(x°)
    top_right    → inverse trig in degrees  sin−1(x°) → degrees output
    below        → hyperbolic               sinh(x)
    bottom_left  → inverse hyperbolic       sinh−1(x)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sympy
import math
from merge_profile import Operation, MergeProfile, REGISTRY


# ---------------------------------------------------------------------------
# Trig function tables
# ---------------------------------------------------------------------------

# Maps trig tool expression string → sympy function
_TRIG_MAP = {
    'sin':  sympy.sin,
    'cos':  sympy.cos,
    'tan':  sympy.tan,
    'sec':  lambda x: 1 / sympy.cos(x),
    'csc':  lambda x: 1 / sympy.sin(x),
    'cot':  lambda x: sympy.cos(x) / sympy.sin(x),
}

_INV_TRIG_MAP = {
    'sin':  sympy.asin,
    'cos':  sympy.acos,
    'tan':  sympy.atan,
    'sec':  lambda x: sympy.acos(1 / x),
    'csc':  lambda x: sympy.asin(1 / x),
    'cot':  lambda x: sympy.atan(1 / x),
}

_HYPER_MAP = {
    'sin':  sympy.sinh,
    'cos':  sympy.cosh,
    'tan':  sympy.tanh,
    'sec':  lambda x: 1 / sympy.cosh(x),
    'csc':  lambda x: 1 / sympy.sinh(x),
    'cot':  lambda x: sympy.cosh(x) / sympy.sinh(x),
}

_INV_HYPER_MAP = {
    'sin':  sympy.asinh,
    'cos':  sympy.acosh,
    'tan':  sympy.atanh,
    'sec':  lambda x: sympy.acosh(1 / x),
    'csc':  lambda x: sympy.asinh(1 / x),
    'cot':  lambda x: sympy.atanh(1 / x),
}

# Display names for inverse hyperbolic
_INV_HYPER_DISP = {
    'sin': 'sinh−1', 'cos': 'cosh−1', 'tan': 'tanh−1',
    'sec': 'sech−1', 'csc': 'csch−1', 'cot': 'coth−1',
}

_HYPER_DISP = {
    'sin': 'sinh', 'cos': 'cosh', 'tan': 'tanh',
    'sec': 'sech', 'csc': 'csch', 'cot': 'coth',
}


# ---------------------------------------------------------------------------
# Trig operation base
# ---------------------------------------------------------------------------

class _TrigOpBase(Operation):
    accepts  = ('number', 'irrational', 'expr')
    simple   = True
    symbol   = '?'
    example  = ''

    def _trig_name(self, tile):
        expr = str(getattr(tile, 'expr_str', getattr(tile, 'text', '')) or '')
        base = expr.split(':')[0].strip().lower()
        return base if base in _TRIG_MAP else 'sin'

    def _get_arg(self, t):
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _format_result(self, result):
        from merge_engine import _round_decimal
        if result.free_symbols:
            from merge_engine import _pretty
            return (_pretty(result), 'expr')
        try:
            fval = float(result.evalf())
            import math
            if math.isnan(fval) or math.isinf(fval):
                from merge_engine import _pretty
                return (_pretty(result), 'irrational')
            if fval == int(fval) and abs(fval) < 1e15:
                return (str(int(fval)), 'number')
            rounded = _round_decimal(f"{fval:.8f}")
            return (rounded, 'number')
        except Exception:
            from merge_engine import _pretty
            return (_pretty(result), 'irrational')

    def _trig_color(self):
        from tile import Tile as _Tile
        return _Tile.color_for_kind('trig_tool')

    def _apply(self, trig_tile, num_tile, sym_func, result_label, tool_label):
        from merge_engine import MergeResult
        from tile import Tile as _Tile
        try:
            arg    = sympy.sympify(self._get_arg(num_tile))
            result = sympy.simplify(sym_func(arg))
            disp, kind = self._format_result(result)
            print(f"[TRIG] {result_label}({self._get_arg(num_tile)}) -> {disp}")

            color      = _Tile.color_for_kind(kind)
            trig_color = self._trig_color()

            return MergeResult(
                replace_tile=None,
                delete_tile=None,
                spawn_spec={
                    'text':     disp,
                    'kind':     kind,
                    'color':    color,
                    'display':  disp,
                    'expr_str': str(result),
                    'w_cells': 1, 'h_cells': 1,
                },
                spawn_direction='right',
                mutate_target={
                    'set_label':        tool_label,
                    'base_color':       trig_color,
                    'background_color': trig_color,
                    'drag_color':       trig_color,
                }
            )
        except Exception as e:
            print(f"[TRIG_ERROR] {result_label}: {e}")
            return None

    def _preview_apply(self, trig_tile, num_tile, sym_func):
        try:
            arg    = sympy.sympify(self._get_arg(num_tile))
            result = sympy.simplify(sym_func(arg))
            disp, kind = self._format_result(result)
            return (disp, kind, None)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Radians (right →)
# ---------------------------------------------------------------------------

class _TrigRadOp(_TrigOpBase):
    symbol  = 'rad'
    example = 'sin(π/2)=1'
    simple  = True

    def build_result(self, a, b, ctx):
        name = self._trig_name(b)
        return self._apply(b, a, _TRIG_MAP.get(name, sympy.sin),
                           result_label=f"{name}(rad)", tool_label=f"{name}(rad)")

    def preview(self, a, b, ctx):
        return self._preview_apply(b, a, _TRIG_MAP.get(self._trig_name(b), sympy.sin))


# ---------------------------------------------------------------------------
# Inverse radians (left ←)
# ---------------------------------------------------------------------------

class _TrigInvRadOp(_TrigOpBase):
    symbol  = 'sin⁻¹r'
    example = 'sin⁻¹(1)=π/2'
    simple  = True

    def build_result(self, a, b, ctx):
        name = self._trig_name(b)
        return self._apply(b, a, _INV_TRIG_MAP.get(name, sympy.asin),
                           result_label=f"{name}⁻¹(rad)", tool_label=f"{name}⁻¹(rad)")

    def preview(self, a, b, ctx):
        return self._preview_apply(b, a, _INV_TRIG_MAP.get(self._trig_name(b), sympy.asin))


# ---------------------------------------------------------------------------
# Degrees (above ↑)
# Convert degrees to radians, apply, return numeric result
# ---------------------------------------------------------------------------

class _TrigDegOp(_TrigOpBase):
    symbol  = 'deg'
    example = 'sin(90°)=1'
    simple  = True

    def build_result(self, a, b, ctx):
        name = self._trig_name(b)
        func = _TRIG_MAP.get(name, sympy.sin)
        return self._apply(b, a, lambda x: func(x * sympy.pi / 180),
                           result_label=f"{name}(deg)", tool_label=f"{name}(deg)")

    def preview(self, a, b, ctx):
        name = self._trig_name(b)
        func = _TRIG_MAP.get(name, sympy.sin)
        return self._preview_apply(b, a, lambda x: func(x * sympy.pi / 180))


# ---------------------------------------------------------------------------
# Inverse degrees (top_right ↗)
# Apply inverse trig, convert result from radians to degrees
# ---------------------------------------------------------------------------

class _TrigInvDegOp(_TrigOpBase):
    symbol  = 'sin⁻¹°'
    example = 'sin⁻¹(1)=90°'
    simple  = False

    def build_result(self, a, b, ctx):
        name = self._trig_name(b)
        func = _INV_TRIG_MAP.get(name, sympy.asin)
        return self._apply(b, a, lambda x: func(x) * 180 / sympy.pi,
                           result_label=f"{name}⁻¹(deg)", tool_label=f"{name}⁻¹(deg)")

    def preview(self, a, b, ctx):
        name = self._trig_name(b)
        func = _INV_TRIG_MAP.get(name, sympy.asin)
        return self._preview_apply(b, a, lambda x: func(x) * 180 / sympy.pi)


# ---------------------------------------------------------------------------
# Hyperbolic (below ↓)
# ---------------------------------------------------------------------------

class _TrigHypOp(_TrigOpBase):
    symbol  = 'sinh'
    example = 'sinh(0)=0'
    simple  = False

    def build_result(self, a, b, ctx):
        name  = self._trig_name(b)
        label = _HYPER_DISP.get(name, f"{name}h")
        return self._apply(b, a, _HYPER_MAP.get(name, sympy.sinh),
                           result_label=label, tool_label=label)

    def preview(self, a, b, ctx):
        return self._preview_apply(b, a, _HYPER_MAP.get(self._trig_name(b), sympy.sinh))


# ---------------------------------------------------------------------------
# Inverse hyperbolic (bottom_left ↙)
# ---------------------------------------------------------------------------

class _TrigInvHypOp(_TrigOpBase):
    symbol  = 'sinh⁻¹'
    example = 'sinh⁻¹(0)=0'
    simple  = False

    def build_result(self, a, b, ctx):
        name  = self._trig_name(b)
        label = _INV_HYPER_DISP.get(name, f"{name}h⁻¹")
        return self._apply(b, a, _INV_HYPER_MAP.get(name, sympy.asinh),
                           result_label=label, tool_label=label)

    def preview(self, a, b, ctx):
        return self._preview_apply(b, a, _INV_HYPER_MAP.get(self._trig_name(b), sympy.asinh))


# ---------------------------------------------------------------------------
# Build and register trig profile
# ---------------------------------------------------------------------------

TRIG_PROFILE = MergeProfile(
    kind        = 'tool',
    directional = {
        'right':       _TrigRadOp(),
        'left':        _TrigInvRadOp(),
        'above':       _TrigDegOp(),
        'top_right':   _TrigInvDegOp(),
        'below':       _TrigHypOp(),
        'bottom_left': _TrigInvHypOp(),
    },
    accepts          = ('number', 'irrational', 'expr'),
    simple_positions = {'right', 'left', 'above'},
)


def register():
    REGISTRY.register(TRIG_PROFILE)
    print("[PROFILES] trig registered")
