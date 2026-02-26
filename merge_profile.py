'''merge_profile.py
================
Merge Engine 2.0 — profile-based directional merge system.

Each tile kind declares a MergeProfile that owns its full interaction map.
The engine queries profiles before falling back to legacy rules, allowing
incremental migration without breaking anything.

Positions:
    Cardinal:  'right', 'left', 'above', 'below'
    Diagonal:  'top_right', 'top_left', 'bottom_right', 'bottom_left'

Simple mode: only cardinal directions are active.'''


import ui


# ---------------------------------------------------------------------------
# Operation base class
# ---------------------------------------------------------------------------

class Operation:
    """
    A single merge operation owned by a MergeProfile.

    Subclasses implement compute(), and optionally override preview() and
    build_result(). All methods are pure — no tile mutation except inside
    build_result().
    """

    # Displayed in MergeHintView
    symbol  = '?'
    example = ''

    # Which tile kinds this operation accepts as the dragged tile (a)
    accepts = ('number', 'expr', 'fraction', 'irrational')

    # If True, appears in simple mode (cardinal only implied by position,
    # but this flag lets diagonals opt in to simple mode too if desired)
    simple = True

    def compute(self, a_expr, b_expr):
        """
        Pure calculation. Returns (result_str, kind) or None on failure.
        kind is one of: 'number', 'expr', 'irrational', 'fraction'
        """
        return None

    def preview(self, a, b, ctx):
        """
        Returns (disp_str, kind, extra) for ghost tile preview, or None.
        extra is a dict for fraction tiles, None otherwise.
        Default implementation calls compute() on the raw expressions.
        """
        try:
            a_expr = self._get_expr(a)
            b_expr = self._get_expr(b)
            if not a_expr or not b_expr:
                return None
            result = self.compute(a_expr, b_expr)
            if result is None:
                return None
            disp, kind = result
            return (disp, kind, None)
        except Exception:
            return None

    def build_result(self, a, b, ctx):
        """
        Apply the operation: mutate b in place, return MergeResult or None.
        Default implementation calls compute() and applies standard tile update.
        """
        from merge_engine import MergeResult
        from tile import Tile as _Tile

        try:
            a_expr = self._get_expr(a)
            b_expr = self._get_expr(b)
            if not a_expr or not b_expr:
                return None

            result = self.compute(a_expr, b_expr)
            if result is None:
                return None

            disp, kind = result
            color = _Tile.color_for_kind(kind)

            b.kind = kind
            b.set_label(disp)
            b.expr_str = disp
            b.set_cell_size(w_cells=1, h_cells=1,
                            cell_size=b.cell_size, gutter=b.gutter)
            try:
                b.data.display = disp
            except Exception:
                pass
            b.base_color       = color
            b.background_color = color
            b.drag_color       = color

            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[OP_BUILD_ERROR] {self.__class__.__name__}: {e}")
            return None

    # ------------------------------------------------------------------
    # Helpers available to all subclasses
    # ------------------------------------------------------------------

    def _get_expr(self, t):
        if getattr(t, 'kind', '') == 'fraction':
            m = getattr(t.data, 'meta', {}) or {}
            n = m.get('numer_expr') or m.get('numer_disp', '0')
            d = m.get('denom_expr') or m.get('denom_disp', '1')
            return f"({n})/({d})"
        return str(getattr(t, 'expr_str', getattr(t, 'text', '')) or '').strip()

    def _get_disp(self, t):
        if getattr(t, 'kind', '') == 'fraction':
            m = getattr(t.data, 'meta', {}) or {}
            return f"{m.get('numer_disp','?')}/{m.get('denom_disp','?')}"
        d = getattr(t.data, 'display', None) if getattr(t, 'data', None) else None
        return str(d or self._get_expr(t)).strip()

    def _sympy_result_to_tuple(self, result):
        """Convert a sympy result to (disp_str, kind)."""
        import sympy
        from merge_engine import _pretty, _round_decimal
        if result.free_symbols:
            return (_pretty(result), 'expr')
        elif result.is_integer:
            return (str(int(result)), 'number')
        elif result.is_rational:
            return (_round_decimal(str(float(result))), 'number')
        else:
            return (_pretty(result), 'irrational')

    def _build_fraction_result(self, a, b, n_sym, d_sym):
        """
        Mutate b into a fraction tile with numerator n_sym, denominator d_sym.
        Returns MergeResult or None.
        """
        import sympy
        from merge_engine import MergeResult
        from tile import Tile as _Tile

        try:
            n_str = str(int(n_sym)) if n_sym.is_integer else str(n_sym)
            d_str = str(int(d_sym)) if d_sym.is_integer else str(d_sym)
            is_expr = bool(n_sym.free_symbols or d_sym.free_symbols)
            frac_kind = 'expr' if is_expr else 'number'
            color = _Tile.color_for_kind(frac_kind)

            b.kind = 'fraction'
            b.set_cell_size(w_cells=1, h_cells=2,
                            cell_size=b.cell_size, gutter=b.gutter)
            b.data.meta['numer_disp'] = n_str
            b.data.meta['denom_disp'] = d_str
            b.data.meta['numer_expr'] = n_str
            b.data.meta['denom_expr'] = d_str
            b.data.meta['is_expr']    = is_expr
            b.base_color       = color
            b.background_color = color
            b.drag_color       = color
            if hasattr(b, 'content_view') and b.content_view:
                b.content_view.background_color = color
            try:
                b._ensure_fraction_views()
                b._sync_fraction_from_meta()
                b.layout()
            except Exception as e:
                print(f"[FRAC_RESULT_ERROR] {e}")

            return MergeResult(replace_tile=b, delete_tile=a)
        except Exception as e:
            print(f"[BUILD_FRAC_ERROR] {e}")
            return None


# ---------------------------------------------------------------------------
# MergeProfile
# ---------------------------------------------------------------------------

class MergeProfile:
    """
    Declares the full interaction map for one tile kind.

    Parameters
    ----------
    kind : str
        The tile kind this profile belongs to ('number', 'trig_tool', etc.)
    directional : dict
        Maps position string → Operation instance.
        Positions: 'right', 'left', 'above', 'below',
                   'top_right', 'top_left', 'bottom_right', 'bottom_left'
    accepts : tuple of str
        Which tile kinds are valid as the dragged tile (a).
        The profile's tile is always the target (b).
    fallback : Operation or None
        Non-directional operation used when no position matches.
    simple_positions : set
        Which positions are active in simple mode.
        Defaults to the four cardinals.
    """

    SIMPLE_POSITIONS = {'right', 'left', 'above', 'below'}

    def __init__(self, kind, directional=None, accepts=None,
                 fallback=None, simple_positions=None):
        self.kind             = kind
        self.directional      = directional or {}
        self.accepts          = accepts or ('number', 'expr',
                                            'fraction', 'irrational')
        self.fallback         = fallback
        self.simple_positions = simple_positions or self.SIMPLE_POSITIONS

    def resolve(self, a, b, position, simple_mode=False):
        """
        Return the Operation for this (a, b, position) combination, or None.
        """
        if getattr(a, 'kind', '') not in self.accepts:
            return None

        op = self.directional.get(position)
        if op is None:
            return self.fallback

        if simple_mode and position not in self.simple_positions:
            return None

        # Let operation veto itself (e.g. integrate/diff require variable tile)
        if hasattr(op, 'can_apply') and not op.can_apply(a, b, {}):
            return None

        return op

    def hint_grid(self, tile_kind=None):
        """
        Return a dict mapping position → (symbol, example, active)
        for the MergeHintView. active=False dims the cell.
        """
        grid = {}
        for pos, op in self.directional.items():
            active = (tile_kind is None or tile_kind in self.accepts)
            grid[pos] = (op.symbol, op.example, active)
        return grid


# ---------------------------------------------------------------------------
# ProfileRegistry — singleton
# ---------------------------------------------------------------------------

class ProfileRegistry:
    """Global registry mapping tile kind → MergeProfile."""

    def __init__(self):
        self._profiles = {}

    def register(self, profile):
        self._profiles[profile.kind] = profile
        print(f"[PROFILE] registered '{profile.kind}'")

    def get(self, kind):
        return self._profiles.get(kind)

    def has(self, kind):
        return kind in self._profiles

    def all_kinds(self):
        return list(self._profiles.keys())


# Module-level singleton
REGISTRY = ProfileRegistry()


# ---------------------------------------------------------------------------
# Position detection — shared logic for all profiles
# ---------------------------------------------------------------------------

def detect_position(drag_start, target, grid, approach_direction=None):
    """
    Classify drag_start into a merge position relative to target.
    Uses border zone geometry — works correctly for any tile size.
    """
    if target is None or drag_start is None:
        return None
    from merge_engine import _classify_drag_start
    return _classify_drag_start(drag_start, target, grid)
