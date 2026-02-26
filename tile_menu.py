import ui
import threading


def _always(tile):
    return True


def _is_fraction(tile):
    from merge_engine import tile_state
    return tile_state(tile) in ('frac_num', 'frac_expr')


def _is_numeric_fraction(tile):
    from merge_engine import tile_state
    return tile_state(tile) == 'frac_num'


def _is_decimal(tile):
    return tile.kind == 'number' and '.' in str(tile.data.display or '')


def _is_irrational(tile):
    return getattr(tile, 'kind', '') == 'irrational'

def _action_approx(tile, board):
    """Toggle between exact irrational form and decimal approximation."""
    import sympy
    from merge_engine import _pretty
    m = getattr(tile.data, 'meta', {}) or {}

    if m.get('showing_decimal'):
        exact = m.get('exact_expr', '')
        if not exact:
            return
        try:
            result = sympy.sympify(exact)
            disp = _pretty(result)
            tile.kind = 'irrational'
            tile.set_label(disp)
            tile.expr_str = exact
            m['showing_decimal'] = False
            print(f"[APPROX] restored exact: {disp}")
        except Exception as e:
            print(f"[APPROX_ERROR] restore: {e}")
    else:
        exact = m.get('exact_expr', '') or str(getattr(tile, 'expr_str', '') or '')
        if not exact:
            return
        try:
            result = sympy.N(sympy.sympify(exact), 10)
            val = float(result)
            s = f"{val:.8g}"
            m['exact_expr'] = exact
            m['showing_decimal'] = True
            tile.kind = 'number'
            tile.set_label(s)
            tile.expr_str = s
            print(f"[APPROX] decimal: {s}")
        except Exception as e:
            print(f"[APPROX_ERROR] evaluate: {e}")

    board._capture_undo_snapshot()

def _is_factorable(tile):
    from merge_engine import tile_state
    st = tile_state(tile)
    if st == 'number':
        try:
            int(str(tile.data.display or '').strip())
            return True
        except ValueError:
            return False
    return st in ('expr', 'armed_expr')
def _is_numeric_armable(tile):
    """Can this tile be converted to a persistent tool?"""
    from merge_engine import tile_state
    st = tile_state(tile)
    if st == 'armed_num':
        return True
    if st == 'expr' and bool(getattr(tile, 'expr_str', '')):
        try:
            import sympy
            f = sympy.sympify(str(tile.expr_str))
            return bool(f.free_symbols)
        except Exception:
            return False
    return False

def _is_expr_tile(tile):
    return getattr(tile, 'kind', '') in ('expr', 'fx')

def _action_fx(tile, board):
    from tile import Tile
    if getattr(tile, 'kind', '') == 'fx':
        tile.kind = 'expr'
    else:
        tile.kind = 'fx'
    print(f"[FX] tile kind -> {tile.kind}")

def _get_current_armed_op(tile):
    """Get currently armed operation symbol, or None."""
    from merge_engine import tile_state
    st = tile_state(tile)
    if st in ('armed_num', 'armed_expr'):
        expr = str(getattr(tile, 'expr_str', ''))
        for op in ('+', '-', '*', '^'):
            if expr.endswith(op):
                return op
    elif st == 'armed_frac':
        m = getattr(tile.data, 'meta', {}) or {}
        return m.get('armed_op')
    return None
def _action_arm_op(tile, board, op, op_display):
    from tile import Tile
    print(f"[ARM_DEBUG] tile kind={tile.kind} expr_str={getattr(tile, 'expr_str', '?')} display={tile.data.display}")
    print(f"[MENU] arm tile={tile.tile_id[:6]} with op={op}")
    try:
        from merge_engine import tile_state
        st = tile_state(tile)

        if st in ('number', 'armed_num'):
            num_str = str(getattr(tile, 'expr_str', tile.text) or '').strip()
            for old_op in ('+', '-', '*', '^'):
                if num_str.endswith(old_op):
                    num_str = num_str[:-1]
                    break
            if op == '/':
                tile.kind = 'fraction'
                tile.set_cell_size(w_cells=1, h_cells=2, cell_size=tile.cell_size, gutter=tile.gutter)
                tile.data.meta['numer_disp'] = num_str
                tile.data.meta['denom_disp'] = None
                tile.data.meta['numer_expr'] = num_str
                tile.data.meta['denom_expr'] = None
                try:
                    tile._ensure_fraction_views()
                    tile._sync_fraction_from_meta()
                    tile.layout()
                except Exception as e:
                    print(f"[ARM_FRAC_ERROR] {e}")
            else:
                tile.kind = 'num_op'
                disp = f"{num_str} {op_display}"
                expr = f"{num_str}{op}"
                tile.set_label(disp)
                tile.expr_str = expr

        elif st in ('expr', 'armed_expr', 'fx'):
            expr_str = str(getattr(tile, 'expr_str', '') or '').strip()
            for old_op in ('+', '-', '*', '^'):
                if expr_str.endswith(old_op):
                    expr_str = expr_str[:-1]
                    break
            if op == '/':
                tile.kind = 'fraction'
                tile.set_cell_size(w_cells=1, h_cells=2, cell_size=tile.cell_size, gutter=tile.gutter)
                tile.data.meta['numer_disp'] = tile.data.display or expr_str
                tile.data.meta['denom_disp'] = None
                tile.data.meta['numer_expr'] = expr_str
                tile.data.meta['denom_expr'] = None
                tile.data.meta['is_expr'] = True
                expr_color = Tile.color_for_kind('expr')
                tile.base_color = expr_color
                tile.drag_color = expr_color
                tile.background_color = expr_color
                if hasattr(tile, 'content_view') and tile.content_view is not None:
                    tile.content_view.background_color = expr_color
                try:
                    tile._ensure_fraction_views()
                    tile._sync_fraction_from_meta()
                    tile.layout()
                except Exception as e:
                    print(f"[ARM_FRAC_EXPR_ERROR] {e}")
            else:
                tile.kind = 'armed_expr'
                tile.data.meta['armed_op'] = op
                disp = f"{tile.data.display or expr_str} {op_display}"
                expr = f"{expr_str}{op}"
                tile.set_label(disp)
                tile.expr_str = expr

        elif st in ('frac_num', 'armed_frac'):
            if op != '/':
                m = tile.data.meta
                m['armed_op'] = op
                m['armed_op_disp'] = op_display
                if 'numer_disp_orig' not in m:
                    m['numer_disp_orig'] = m.get('numer_disp', '')
                try:
                    tile._sync_fraction_from_meta()
                    tile.layout()
                except Exception:
                    pass

        print(f"[MENU] armed {tile.kind} with {op}")
        board._capture_undo_snapshot()
    except Exception as e:
        print(f"[MENU_ARM_ERROR] {e}")
        import traceback
        traceback.print_exc()

def _is_poppable(tile):
    from merge_engine import tile_state
    st = tile_state(tile)

    if st in ('armed_num', 'armed_expr', 'armed_frac', 'armed_frac_expr'):
        return True

    if st == 'number':
        text = str(getattr(tile, 'expr_str', tile.text) or '').strip()
        # negative number: -8 -> poppable (splits off the minus)
        if text.startswith('-') and len(text) >= 2:
            return True
        # multi-digit: 345 -> poppable (splits first digit off left)
        return len(text) >= 2 and text.isdigit()

    if st == 'expr':
        try:
            import sympy
            expr_str = str(getattr(tile, 'expr_str', '') or '').strip()
            expr = sympy.sympify(expr_str)
            if expr.func == sympy.Add and len(expr.args) >= 2:
                return True
            if expr.func == sympy.Mul:
                args = expr.args
                has_num = any(a.is_number for a in args)
                has_sym = any(not a.is_number for a in args)
                return has_num and has_sym
        except Exception:
            pass
        return False

    if st in ('frac_num', 'frac_expr', 'frac_half'):
        return True

    return False

def _compute_pop_specs(tile):
    """
    Pure function — no side effects.
    Returns (left_spec, remain_spec) dicts describing what a pop would produce,
    or (None, None) if the tile isn't poppable.
    Each spec has: text, kind, color.
    """
    import sympy
    from tile import Tile
    from merge_engine import tile_state, _pretty

    st = tile_state(tile)

    def _kind_and_color(expr_str):
        try:
            sym = sympy.sympify(expr_str)
            if sym.free_symbols:
                k = 'expr'
            elif not sym.is_rational:
                k = 'irrational'
            else:
                k = 'number'
        except Exception:
            k = 'number'
        return k, Tile.color_for_kind(k)

    def _spec(text, kind):
        return {'text': str(text), 'kind': kind, 'color': Tile.color_for_kind(kind)}

    # --- armed: op pops left, value stays ---
    if st in ('armed_num', 'armed_expr'):
        expr_str = str(getattr(tile, 'expr_str', '') or '').strip()
        for op in ('+', '-', '*', '^'):
            if expr_str.endswith(op):
                val = expr_str[:-1]
                disp = str(getattr(tile.data, 'display', val) or val)
                # strip op from disp too
                for d_op in (' +', ' -', ' ×', ' ^', ' *'):
                    if disp.endswith(d_op):
                        disp = disp[:-len(d_op)]
                        break
                return (_spec(op, 'op'), _spec(disp, 'expr' if st == 'armed_expr' else 'number'))
        return (None, None)

    if st in ('armed_frac', 'armed_frac_expr'):
        m = getattr(tile.data, 'meta', {}) or {}
        op = m.get('armed_op', '?')
        n_disp = m.get('numer_disp_orig', m.get('numer_disp', '?'))
        return (_spec(op, 'op'), _spec(n_disp, 'fraction'))

    # --- negative number ---
    if st == 'number':
        text = str(getattr(tile, 'expr_str', tile.text) or '').strip()
        if text.startswith('-') and len(text) >= 2:
            num_str = text[1:].strip()
            return (_spec('-', 'op'), _spec(num_str, 'number'))
        if len(text) >= 2 and text.isdigit():
            return (_spec(text[0], 'number'), _spec(text[1:], 'number'))
        return (None, None)

    # --- expr ---
    if st == 'expr':
        expr_str = str(getattr(tile, 'expr_str', '') or '').strip()
        try:
            expr = sympy.sympify(expr_str)
            if expr.func == sympy.Mul:
                args = expr.args
                coeff     = sympy.Mul(*[a for a in args if a.is_number])
                remainder = sympy.Mul(*[a for a in args if not a.is_number])
                if coeff != 1 and remainder != 1:
                    return (_spec(_pretty(coeff), 'number'), _spec(_pretty(remainder), 'expr'))
            if expr.func == sympy.Add and len(expr.args) >= 2:
                terms = list(expr.args)
                terms_sorted = sorted(terms, key=lambda t: (t.free_symbols != set(), str(t)))
                last_term = terms_sorted[-1]
                remaining = sympy.Add(*[t for t in terms if t != last_term])
                return (_spec(_pretty(remaining), 'expr'), _spec(_pretty(last_term), 'expr'))
        except Exception:
            pass
        return (None, None)

    # --- fraction ---
    if st in ('frac_num', 'frac_expr', 'frac_half'):
        m = getattr(tile.data, 'meta', {}) or {}
        n_disp = m.get('numer_disp', '?')
        d_disp = m.get('denom_disp')
        n_expr = m.get('numer_expr') or n_disp
        d_expr = m.get('denom_expr') or d_disp
        if d_disp:
            n_kind, n_color = _kind_and_color(n_expr or '')
            d_kind, d_color = _kind_and_color(d_expr or '')
            return (
                {'text': n_disp, 'kind': n_kind, 'color': n_color},
                {'text': d_disp, 'kind': d_kind, 'color': d_color},
            )
        elif n_disp:
            n_kind, n_color = _kind_and_color(n_expr or '')
            return ({'text': n_disp, 'kind': n_kind, 'color': n_color}, None)

    return (None, None)

def _action_pop(tile, board):
    from tile import Tile
    print(f"[MENU] pop tile={tile.tile_id[:6]} kind={tile.kind}")
    try:
        board._capture_undo_snapshot()
        import sympy
        from tile_anim import pulse, spawn_from
        from merge_engine import tile_state, _pretty

        st = tile_state(tile)
        g = board.grid
        cx, cy = tile.center
        left_cx = cx - g

        def _kind_and_color(expr_str):
            try:
                sym = sympy.sympify(expr_str)
                if sym.free_symbols:
                    k = 'expr'
                elif not sym.is_rational:
                    k = 'irrational'
                else:
                    k = 'number'
            except Exception:
                k = 'number'
            return k, Tile.color_for_kind(k)

        def _place(spec, pos_cx, pos_cy=None):
            t = board.create_tile_from_spec(spec)
            sx, sy = board.snap_center(pos_cx, pos_cy if pos_cy is not None else cy, t)
            board.add_subview(t)
            board.tiles.append(t)
            board._enforce_exclusion(t)
            spawn_from(t, origin_center=(cx, cy), final_center=(sx, sy))
            return t

        def _do_pop():

            # --- armed tile: split off the op ---
            if st in ('armed_num', 'armed_expr', 'armed_frac', 'armed_frac_expr'):
                armed_op = None
                if st in ('armed_num', 'armed_expr'):
                    expr_str = str(getattr(tile, 'expr_str', '') or '').strip()
                    for op in ('+', '-', '*', '^'):
                        if expr_str.endswith(op):
                            armed_op = op
                            expr_str = expr_str[:-1]
                            break
                elif st in ('armed_frac', 'armed_frac_expr'):
                    m = getattr(tile.data, 'meta', {}) or {}
                    armed_op = m.get('armed_op')

                if not armed_op:
                    print("[POP] armed tile but no op found")
                    return

                board.remove_tile(tile)
                _place({
                    'text': armed_op, 'kind': 'op',
                    'color': Tile.color_for_kind('op'),
                    'expr_str': armed_op, 'display': armed_op,
                }, left_cx)

                if st == 'armed_num':
                    _place({
                        'text': expr_str, 'kind': 'number',
                        'color': Tile.color_for_kind('number'),
                        'expr_str': expr_str, 'display': expr_str,
                    }, cx)
                elif st == 'armed_expr':
                    disp = tile.data.display or expr_str
                    _place({
                        'text': disp, 'kind': 'expr',
                        'color': Tile.color_for_kind('expr'),
                        'expr_str': expr_str, 'display': disp,
                    }, cx)
                elif st in ('armed_frac', 'armed_frac_expr'):
                    m = tile.data.meta
                    is_expr = m.get('is_expr', False)
                    n_disp_orig = m.get('numer_disp_orig', m.get('numer_disp'))
                    frac_tile = board.create_tile_from_spec({'kind': 'fraction', 'spawn_kind': 'fraction'})
                    frac_tile.data.meta['numer_disp'] = n_disp_orig
                    frac_tile.data.meta['denom_disp'] = m.get('denom_disp')
                    frac_tile.data.meta['numer_expr'] = n_disp_orig
                    frac_tile.data.meta['denom_expr'] = m.get('denom_expr')
                    frac_tile.data.meta['is_expr'] = is_expr
                    if is_expr:
                        c = Tile.color_for_kind('expr')
                        frac_tile.base_color = c
                        frac_tile.drag_color = c
                        frac_tile.background_color = c
                        if hasattr(frac_tile, 'content_view') and frac_tile.content_view:
                            frac_tile.content_view.background_color = c
                    try:
                        frac_tile._ensure_fraction_views()
                        frac_tile._sync_fraction_from_meta()
                        frac_tile.layout()
                    except Exception as e:
                        print(f"[POP_FRAC_ERROR] {e}")
                    sx, sy = board.snap_center(cx, cy, frac_tile)
                    board.add_subview(frac_tile)
                    board.tiles.append(frac_tile)
                    board._enforce_exclusion(frac_tile)
                    spawn_from(frac_tile, origin_center=(cx, cy), final_center=(sx, sy))
                print(f"[POP] armed: op={armed_op} left, value right")
                return

            # --- negative number: -8 -> '-' op left, '8' at tile ---
            if st == 'number':
                text = str(getattr(tile, 'expr_str', tile.text) or '').strip()
                if text.startswith('-'):
                    num_str = text[1:].strip()
                    board.remove_tile(tile)
                    _place({
                        'text': '-', 'kind': 'op',
                        'color': Tile.color_for_kind('op'),
                        'expr_str': '-', 'display': '-',
                    }, left_cx)
                    _place({
                        'text': num_str, 'kind': 'number',
                        'color': Tile.color_for_kind('number'),
                        'expr_str': num_str, 'display': num_str,
                    }, cx)
                    print(f"[POP] negative: '-' left, '{num_str}' at tile")
                    return
                if len(text) < 2:
                    print("[POP] cannot pop single digit")
                    return
                first_digit = text[0]
                remaining   = text[1:]
                board.remove_tile(tile)
                _place({
                    'text': first_digit, 'kind': 'number',
                    'color': Tile.color_for_kind('number'),
                    'expr_str': first_digit, 'display': first_digit,
                }, left_cx)
                _place({
                    'text': remaining, 'kind': 'number',
                    'color': Tile.color_for_kind('number'),
                    'expr_str': remaining, 'display': remaining,
                }, cx)
                print(f"[POP] number: '{first_digit}' left, '{remaining}' at tile")
                return

            # --- expr ---
            elif st == 'expr':
                expr_str = str(getattr(tile, 'expr_str', '') or '').strip()
                try:
                    expr = sympy.sympify(expr_str)
                except Exception:
                    print("[POP] cannot parse expression")
                    return
                if expr.func == sympy.Mul:
                    args = expr.args
                    coeff     = sympy.Mul(*[a for a in args if a.is_number])
                    remainder = sympy.Mul(*[a for a in args if not a.is_number])
                    if coeff == 1 or remainder == 1:
                        print("[POP] no separable coefficient")
                        return
                    board.remove_tile(tile)
                    coeff_disp = _pretty(coeff)
                    rem_disp   = _pretty(remainder)
                    _place({
                        'text': coeff_disp, 'kind': 'number',
                        'color': Tile.color_for_kind('number'),
                        'expr_str': str(coeff), 'display': coeff_disp,
                    }, left_cx)
                    _place({
                        'text': rem_disp, 'kind': 'expr',
                        'color': Tile.color_for_kind('expr'),
                        'expr_str': str(remainder), 'display': rem_disp,
                    }, cx)
                    print(f"[POP] coeff: '{coeff_disp}' left, '{rem_disp}' at tile")
                    return
                if expr.func != sympy.Add or len(expr.args) < 2:
                    print("[POP] not splittable expr")
                    return
                terms = list(expr.args)
                terms_sorted = sorted(terms, key=lambda t: (t.free_symbols != set(), str(t)))
                last_term = terms_sorted[-1]
                remaining = sympy.Add(*[t for t in terms if t != last_term])
                board.remove_tile(tile)
                last_disp = _pretty(last_term)
                rem_disp  = _pretty(remaining)
                _place({
                    'text': rem_disp, 'kind': 'expr',
                    'color': Tile.color_for_kind('expr'),
                    'expr_str': str(remaining), 'display': rem_disp,
                }, left_cx)
                _place({
                    'text': last_disp, 'kind': 'expr',
                    'color': Tile.color_for_kind('expr'),
                    'expr_str': str(last_term), 'display': last_disp,
                }, cx)
                print(f"[POP] sum: '{rem_disp}' left, '{last_disp}' at tile")

            # --- fraction: numerator stays, denominator pops below ---
            elif st in ('frac_num', 'frac_expr', 'frac_half'):
                m = getattr(tile.data, 'meta', {}) or {}
                n_disp = m.get('numer_disp')
                d_disp = m.get('denom_disp')
                n_expr = m.get('numer_expr') or n_disp
                d_expr = m.get('denom_expr') or d_disp
                board.remove_tile(tile)
                if d_disp:
                    n_kind, n_color = _kind_and_color(n_expr or n_disp or '')
                    d_kind, d_color = _kind_and_color(d_expr or d_disp or '')
                    _place({
                        'text': n_disp, 'kind': n_kind, 'color': n_color,
                        'expr_str': n_expr, 'display': n_disp,
                    }, cx, cy - g * 0.5)
                    _place({
                        'text': d_disp, 'kind': d_kind, 'color': d_color,
                        'expr_str': d_expr, 'display': d_disp,
                    }, cx, cy + g * 0.5)
                    print(f"[POP] fraction: '{n_disp}' at tile, '{d_disp}' below")
                elif n_disp:
                    n_kind, n_color = _kind_and_color(n_expr or n_disp or '')
                    _place({
                        'text': n_disp, 'kind': n_kind, 'color': n_color,
                        'expr_str': n_expr, 'display': n_disp,
                    }, cx, cy)
                    print(f"[POP] half-fraction: '{n_disp}'")

        # Pulse first, pop on completion
        pulse(tile, completion=_do_pop)

    except Exception as e:
        print(f"[MENU_POP_ERROR] {e}")
        import traceback
        traceback.print_exc()

class MenuItem:
    def __init__(self, icon, label, applies_to, action):
        self.icon = icon
        self.label = label
        self.applies_to = applies_to
        self.action = action

#added this may be wrong
def _dispatch_menu_action(item, tile, board):
    """
    If a group selection exists and the tapped tile is in it,
    apply Delete/Copy to the whole group. Otherwise behave normally.
    """
    label = getattr(item, 'label', '')
    action_fn = getattr(item, 'action', None)

    group = list(getattr(board, 'group_selection', []) or [])
    in_group = (tile in group) if group else False

    # Only group-support for Delete + Copy
    if group and in_group and label in ('Delete', 'Copy'):
        if label == 'Delete':
            for t in list(group):
                try:
                    board.remove_tile(t)
                except Exception:
                    pass
            try:
                board.clear_group_selection()
            except Exception:
                pass
            try:
                board._capture_undo_snapshot()
            except Exception:
                pass
            return

        if label == 'Copy':
            # Duplicate all tiles with a diagonal offset
            g = float(getattr(board, 'grid', 60) or 60)
            spawned = []
            for t in list(group):
                try:
                    spec = board._clone_tile_spec(t)
                except Exception:
                    # Fallback minimal spec
                    spec = {
                        'text': getattr(t.data, 'display', '') if getattr(t, 'data', None) else getattr(t, 'text', ''),
                        'kind': getattr(t, 'kind', 'number'),
                        'color': getattr(t, 'base_color', '#FFD60A'),
                        'expr_str': getattr(t, 'expr_str', ''),
                        'display': getattr(t.data, 'display', '') if getattr(t, 'data', None) else getattr(t, 'text', ''),
                        'w_cells': getattr(t, 'w_cells', 1),
                        'h_cells': getattr(t, 'h_cells', 1),
                    }
                try:
                    new_t = board.create_tile_from_spec(spec)
                    cx, cy = t.center
                    new_t.center = (cx + g, cy + g)
                    board.add_subview(new_t)
                    board.tiles.append(new_t)
                    try:
                        board._enforce_exclusion(new_t)
                    except Exception:
                        pass
                    spawned.append(new_t)
                except Exception:
                    pass

            try:
                board._capture_undo_snapshot()
            except Exception:
                pass
            return

    # Default: single-tile behaviour
    if callable(action_fn):
        action_fn(tile, board)

def _action_delete(tile, board):
    try:
        group = getattr(board, 'lasso_selected_tiles', None) or []
        if group and (tile in group):
            print(f"[MENU] delete group n={len(group)}")
            # Remove all selected tiles
            for t in list(group):
                try:
                    board.remove_tile(t)
                except Exception:
                    pass
            # Clear selection
            try:
                board.lasso_selected_tiles = []
            except Exception:
                pass
            board._capture_undo_snapshot()
            return

        # Default: delete single tile
        print(f"[MENU] delete tile={tile.tile_id[:6]}")
        board.remove_tile(tile)
        board._capture_undo_snapshot()
    except Exception as e:
        print(f"[MENU_DELETE_ERROR] {e}")

def _action_duplicate(tile, board):
    try:
        group = getattr(board, 'lasso_selected_tiles', None) or []
        g = getattr(board, 'grid', 60)

        def _dup_one(src, dy):
            import copy
            new_tile = board.create_tile_from_spec({
                'text': src.data.display,
                'kind': src.kind,
                'color': getattr(src, 'base_color', None),
                'expr_str': getattr(src, 'expr_str', src.data.display),
                'display': src.data.display,
            })
            # Best-effort meta copy
            try:
                if hasattr(src, 'data') and hasattr(src.data, 'meta'):
                    new_tile.data.meta = copy.deepcopy(src.data.meta)
            except Exception:
                pass

            cx, cy = src.center
            new_tile.center = (cx, cy + dy)

            board.add_subview(new_tile)
            board.tiles.append(new_tile)

            # If it's a fraction, refresh its views/meta
            try:
                if getattr(new_tile, 'kind', '') == 'fraction':
                    new_tile._ensure_fraction_views()
                    new_tile._sync_fraction_from_meta()
                    new_tile.layout()
            except Exception:
                pass

            try:
                board._enforce_exclusion(new_tile)
            except Exception:
                pass
            return new_tile

        if group and (tile in group):
            print(f"[MENU] copy group n={len(group)}")
            new_tiles = []
            for t in list(group):
                try:
                    new_tiles.append(_dup_one(t, g))
                except Exception:
                    pass

            # New group becomes selected
            try:
                board.lasso_selected_tiles = list(new_tiles)
            except Exception:
                pass

            board._capture_undo_snapshot()
            return

        # Default: duplicate single tile
        print(f"[MENU] duplicate tile={tile.tile_id[:6]}")
        _dup_one(tile, g)
        board._capture_undo_snapshot()
    except Exception as e:
        print(f"[MENU_DUPLICATE_ERROR] {e}")

def _action_make_tool(tile, board):
    from tile import Tile
    from merge_engine import tile_state
    st = tile_state(tile)
    print(f"[MAKE_TOOL] tile={tile.tile_id[:6]} kind={tile.kind} state={st}")
    try:
        if st == 'armed_num':
            expr_str = str(getattr(tile, 'expr_str', '') or '').strip()
            base_op = None
            base_num = expr_str
            for op in ('+', '-', '*', '^', '/'):
                if expr_str.endswith(op):
                    base_op = op
                    base_num = expr_str[:-1].strip()
                    break
            if not base_op:
                print(f"[MAKE_TOOL] no op found")
                return
            tile.kind = 'num_tool'
            tile.data.meta['base_num'] = base_num
            tile.data.meta['base_op'] = base_op
            op_disp = {'+': '+', '-': '-', '*': '×', '^': '^', '/': '÷'}.get(base_op, base_op)
            tile.set_label(f"{base_num} {op_disp}")
            tile.expr_str = expr_str
            print(f"[MAKE_TOOL] num_tool: {base_num} {base_op}")

        elif st == 'expr':
            tile.kind = 'expr_tool'
            print(f"[MAKE_TOOL] expr_tool: {tile.expr_str}")

        else:
            print(f"[MAKE_TOOL] unsupported state: {st}")
            return

        board._capture_undo_snapshot()
    except Exception as e:
        print(f"[MAKE_TOOL_ERROR] {e}")
        import traceback
        traceback.print_exc()

def _action_swap_decimal(tile, board):
    print(f"[MENU] swap decimal tile={tile.tile_id[:6]}")
    try:
        from merge_engine import tile_state
        if tile_state(tile) != 'frac_num':
            return
        m = tile.data.meta
        n = float(m.get('numer_expr') or m.get('numer_disp', '0'))
        d = float(m.get('denom_expr') or m.get('denom_disp', '1'))
        if d == 0:
            return
        decimal_str = f"{n/d:.10g}"
        tile.set_cell_size(w_cells=1, h_cells=1, cell_size=tile.cell_size, gutter=tile.gutter)
        tile.kind = 'number'
        tile.set_label(decimal_str)
        tile.expr_str = decimal_str
        tile.data.meta['_was_fraction'] = {'n': n, 'd': d}
        board._capture_undo_snapshot()
        print(f"[MENU] converted {n}/{d} -> {decimal_str}")
    except Exception as e:
        print(f"[MENU_DECIMAL_ERROR] {e}")
def _action_to_fraction(tile, board):
    print(f"[MENU] to_fraction tile={tile.tile_id[:6]}")
    try:
        import sympy
        disp = str(tile.data.display or tile.text or '').strip()
        r = sympy.Rational(disp).limit_denominator(10000)
        n, d = int(r.p), int(r.q)
        print(f"[MENU] decimal {disp} -> {n}/{d}")

        cx, cy = tile.center
        board.remove_tile(tile)

        new_tile = board.create_tile_from_spec({'kind': 'fraction', 'spawn_kind': 'fraction'})
        new_tile.data.meta['numer_disp'] = str(n)
        new_tile.data.meta['denom_disp'] = str(d)
        new_tile.data.meta['numer_expr'] = str(n)
        new_tile.data.meta['denom_expr'] = str(d)
        try:
            new_tile._ensure_fraction_views()
            new_tile._sync_fraction_from_meta()
            new_tile.layout()
        except Exception as e:
            print(f"[MENU_TO_FRAC_SYNC_ERROR] {e}")

        new_cx, new_cy = board.snap_center(cx, cy, new_tile)
        new_tile.center = (new_cx, new_cy)
        board.add_subview(new_tile)
        board.tiles.append(new_tile)
        board._enforce_exclusion(new_tile)
        board._capture_undo_snapshot()
        print(f"[MENU] fraction tile created id={new_tile.tile_id[:6]}")
    except Exception as e:
        print(f"[MENU_TO_FRAC_ERROR] {e}")
        import traceback
        traceback.print_exc()
def _action_factor(tile, board):
    from tile import Tile
    print(f"[MENU] factor tile={tile.tile_id[:6]} kind={tile.kind}")
    try:
        import sympy
        from merge_engine import tile_state
        st = tile_state(tile)
        g = board.grid
        cx, cy = tile.center

        if st == 'number':
            n = int(str(tile.data.display or '').strip())
            fd = sympy.factorint(n)
            factors = []
            for prime in sorted(fd.keys()):
                factors.extend([prime] * fd[prime])
            if len(factors) <= 1:
                print(f"[MENU] {n} is prime, nothing to factor")
                return
            board.remove_tile(tile)
            cols = min(len(factors), 4)
            start_cx, start_cy = board.snap_center(
                cx - (cols - 1) * g / 2, cy,
                board.create_tile_from_spec({'text': '1', 'kind': 'number',
                    'color': Tile.color_for_kind('number')})
            )
            for i, f in enumerate(factors):
                t = board.create_tile_from_spec({
                    'text': str(f), 'kind': 'number',
                    'color': Tile.color_for_kind('number'),
                    'expr_str': str(f), 'display': str(f),
                })
                snap_x, snap_y = board.snap_center(
                    start_cx + (i % 4) * g, start_cy + (i // 4) * g, t)
                t.center = (snap_x, snap_y)
                board.add_subview(t)
                board.tiles.append(t)
                board._enforce_exclusion(t)

        elif st in ('expr', 'armed_expr'):
            expr_str = tile.expr_str or tile.data.display or ''
            expr = sympy.sympify(expr_str)
            factored = sympy.factor(expr)
            args = list(factored.args) if factored.func == sympy.Mul else [factored]
            args = [a for a in args if a != sympy.Integer(1)]
            if len(args) <= 1:
                print(f"[MENU] expression irreducible")
                return
            board.remove_tile(tile)
            tiles_to_place = []
            for arg in args:
                disp = str(arg)
                t = board.create_tile_from_spec({
                    'text': disp, 'kind': 'expr',
                    'color': Tile.color_for_kind('expr'),
                    'expr_str': disp, 'display': disp,
                })
                tiles_to_place.append(t)
            total_w = sum(t.width for t in tiles_to_place)
            current_cx = board.snap_center(
                cx - total_w / 2 + tiles_to_place[0].width / 2, cy, tiles_to_place[0])[0]
            for t in tiles_to_place:
                snap_x, snap_y = board.snap_center(current_cx, cy, t)
                t.center = (snap_x, snap_y)
                board.add_subview(t)
                board.tiles.append(t)
                board._enforce_exclusion(t)
                current_cx = snap_x + t.width / 2 + g / 2 + t.width / 2

        board._capture_undo_snapshot()
    except Exception as e:
        print(f"[MENU_FACTOR_ERROR] {e}")
        import traceback
        traceback.print_exc()


def _is_hint_eligible(tile):
    return getattr(tile, 'kind', '') in ('number', 'expr', 'fraction', 'irrational')

def _always(tile):
    return True

def _show_merge_hints(tile, board):
    existing = getattr(board, '_merge_hint_view', None)
    if existing is not None:
        try:
            existing.dismiss()
        except Exception:
            pass
        board._merge_hint_view = None

    if not _is_hint_eligible(tile):
        return

    hint_view = MergeHintView(tile, board)
    board.add_subview(hint_view)
    board._merge_hint_view = hint_view

MENU_ITEMS = [
    MenuItem('🗑️', 'Delete',    _always,              _action_delete),
    MenuItem('📋', 'Copy',      _always,               _action_duplicate),
    MenuItem('🔧', 'Make Tool', _is_numeric_armable,   _action_make_tool),
    MenuItem('⬅',  'Pop',       _is_poppable,          _action_pop),
    MenuItem('?',  'Hint',      _is_hint_eligible,     _show_merge_hints),
]




class MergeHintView(ui.View):
    """
    3×3 grid of hint cells around a tile showing available merge operations.
    For number/expr/fraction/irrational: hardcoded directional hints.
    For trig tools: reads from the registered MergeProfile.
    Dismissed on any board touch or drag.
    """
    CELL_SIZE  = 54
    CELL_ALPHA = 0.92
    DIM_ALPHA  = 0.25
    CELL_BG    = '#2C2C2E'
    DIM_BG     = '#1C1C1E'

    # Position string -> (grid_dx, grid_dy)
    POS_TO_OFFSET = {
        'right':        ( 1,  0),
        'left':         (-1,  0),
        'above':        ( 0, -1),
        'below':        ( 0,  1),
        'top_right':    ( 1, -1),
        'top_left':     (-1, -1),
        'bottom_right': ( 1,  1),
        'bottom_left':  (-1,  1),
    }

    # Static hints for number family tiles
    # (grid_dx, grid_dy): (symbol, example, applicable_kinds)
    NUMBER_HINTS = {
        (-1, -1): ('log', 'log28=3', ('number', 'irrational', 'expr')),
        ( 0, -1): ('×',   '3×4=12',  ('number', 'irrational', 'expr', 'fraction')),
        ( 1, -1): ('^',   '23=8',    ('number', 'irrational', 'expr')),
        (-1,  0): ('+',   '3+4=7',   ('number', 'irrational', 'expr', 'fraction')),
        ( 1,  0): ('−',   '8−3=5',   ('number', 'irrational', 'expr', 'fraction')),
        (-1,  1): ('mod', '7mod3=1', ()),
        ( 0,  1): ('÷',   '6÷2=3',   ('number', 'irrational', 'expr')),
        ( 1,  1): ('.',   '8.7',     ('number',)),
    }

    def __init__(self, tile, board):
        super().__init__(frame=(0, 0, board.width, board.height))
        self.touch_enabled = True
        self._tile  = tile
        self._board = board
        self._cells = []

        tile_kind = getattr(tile, 'kind', 'number')
        # Expr fractions behave like expr for profile lookup
        if tile_kind == 'fraction':
            meta = getattr(getattr(tile, 'data', None), 'meta', {}) or {}
            if meta.get('is_expr', False):
                tile_kind = 'expr'

        grid = board.grid

        # Get zone centers from border zone geometry (handles any tile size)
        try:
            from merge_engine import _tile_border_zones, _point_in_zone
            zones = _tile_border_zones(tile, grid)
            zone_centers = {name: (cx, cy) for name, (cx, cy, hw, hh) in zones.items()}
        except Exception:
            # Fallback: naive grid offsets from tile center
            tx, ty = tile.center
            zone_centers = {
                'left':         (tx - grid,      ty),
                'right':        (tx + grid,      ty),
                'above':        (tx,             ty - grid),
                'below':        (tx,             ty + grid),
                'top_left':     (tx - grid,      ty - grid),
                'top_right':    (tx + grid,      ty - grid),
                'bottom_left':  (tx - grid,      ty + grid),
                'bottom_right': (tx + grid,      ty + grid),
            }

        hints = self._build_hints(tile, tile_kind)

        for pos, (symbol, example, applicable) in hints.items():
            center = zone_centers.get(pos)
            if center is None:
                continue
            cx, cy = center
            fx = cx - self.CELL_SIZE / 2
            fy = cy - self.CELL_SIZE / 2

            cell = ui.View(frame=(fx, fy, self.CELL_SIZE, self.CELL_SIZE))
            cell.background_color = self.CELL_BG if applicable else self.DIM_BG
            cell.corner_radius    = 12
            cell.border_width     = 1
            cell.border_color     = '#3A3A3C' if applicable else '#2A2A2C'
            cell.alpha            = 0.0
            cell.touch_enabled    = False

            sym_lbl = ui.Label(frame=(0, 6, self.CELL_SIZE, 26))
            sym_lbl.text       = symbol
            sym_lbl.font       = ('<System-Bold>', 16)
            sym_lbl.text_color = '#FFFFFF' if applicable else '#555555'
            sym_lbl.alignment  = ui.ALIGN_CENTER
            cell.add_subview(sym_lbl)

            ex_lbl = ui.Label(frame=(2, 32, self.CELL_SIZE - 4, 16))
            ex_lbl.text            = example
            ex_lbl.font            = ('<System>', 10)
            ex_lbl.text_color      = '#8E8E93' if applicable else '#3A3A3C'
            ex_lbl.alignment       = ui.ALIGN_CENTER
            ex_lbl.number_of_lines = 1
            cell.add_subview(ex_lbl)

            board.add_subview(cell)
            target_alpha = self.CELL_ALPHA if applicable else self.DIM_ALPHA
            self._cells.append((cell, target_alpha))

        for cell, ta in self._cells:
            ui.animate(lambda c=cell, a=ta: setattr(c, 'alpha', a), duration=0.18)

    def _build_hints(self, tile, tile_kind):
        """
        Returns dict: position_name -> (symbol, example, applicable: bool)
        Reads from profile registry first, falls back to NUMBER_HINTS.
        """
        # Try profile registry
        try:
            from merge_profile import REGISTRY
            profile = REGISTRY.get(tile_kind)
            if profile is not None:
                result = {}
                for pos, op in profile.directional.items():
                    symbol  = getattr(op, 'symbol', '?')
                    example = getattr(op, 'example', '')
                    accepts = getattr(op, 'accepts', ())
                    # Dim ops that accept nothing (placeholders like _ModuloOp)
                    applicable = len(accepts) > 0
                    result[pos] = (symbol, example, applicable)
                return result
        except Exception as e:
            print(f"[HINT_PROFILE_ERROR] {e}")

        # Fallback: static NUMBER_HINTS mapped to position names
        POS_MAP = {
            (-1, -1): 'top_left',
            ( 0, -1): 'above',
            ( 1, -1): 'top_right',
            (-1,  0): 'left',
            ( 1,  0): 'right',
            (-1,  1): 'bottom_left',
            ( 0,  1): 'below',
            ( 1,  1): 'bottom_right',
        }
        result = {}
        tile_k = getattr(tile, 'kind', 'number')
        for (dx, dy), (symbol, example, kinds) in self.NUMBER_HINTS.items():
            pos = POS_MAP.get((dx, dy))
            if pos:
                result[pos] = (symbol, example, tile_k in kinds)
        return result

    def _build_trig_hints(self, tile):
        try:
            from merge_profile import REGISTRY
            profile = REGISTRY.get('tool')
            if profile is None:
                return {}
            result = {}
            for pos, op in profile.directional.items():
                offset = self.POS_TO_OFFSET.get(pos)
                if offset is None:
                    continue
                symbol  = getattr(op, 'symbol', '?')
                example = getattr(op, 'example', '')
                result[offset] = (symbol, example, True)
            return result
        except Exception as e:
            print(f"[TRIG_HINT_ERROR] {e}")
            return {}

    def dismiss(self):
        for cell, _ in self._cells:
            try:
                c = cell
                def _remove(v=c):
                    try:
                        if v.superview:
                            v.superview.remove_subview(v)
                    except Exception:
                        pass
                ui.animate(lambda v=c: setattr(v, 'alpha', 0.0),
                           duration=0.12, completion=lambda v=c: _remove(v))
            except Exception:
                pass
        self._cells = []
        try:
            if self.superview:
                self.superview.remove_subview(self)
        except Exception:
            pass

    def touch_began(self, touch):
        self.dismiss()
        try:
            if hasattr(self._board, '_merge_hint_view'):
                self._board._merge_hint_view = None
        except Exception:
            pass

class ActionsMenu(ui.View):
    """
    Actions menu - appears above tile.
    Shows: Delete, Copy, Sticky, Factor, Pop, etc.
    """
    
    ITEM_SIZE = 44
    PADDING = 6
    CORNER = 10
    BG = '#1C1C1E'
    ITEM_BG = '#2C2C2E'
    ITEM_ACTIVE = '#3A3A3C'
    
    def __init__(self, tile, board, **kwargs):
        super().__init__(**kwargs)
        self.tile = tile
        self.board = board
        self._buttons = []
        self._highlighted_button = None
        
        items = [i for i in MENU_ITEMS if i.applies_to(tile)]
        print(f"[ACTIONS_MENU] building menu for tile={tile.tile_id[:6]} kind={tile.kind} items={len(items)}")
        
        n_items = len(items)
        total_w = n_items * self.ITEM_SIZE + (n_items + 1) * self.PADDING
        total_h = self.ITEM_SIZE + self.PADDING * 2
        
        self.frame = (0, 0, total_w, total_h)
        self.background_color = self.BG
        self.corner_radius = self.CORNER
        self.border_width = 1
        self.border_color = '#3A3A3C'
        
        try:
            self.touch_enabled = True
        except Exception:
            pass
        
        for i, item in enumerate(items):
            x = self.PADDING + i * (self.ITEM_SIZE + self.PADDING)
            y = self.PADDING
            btn = ui.Button(frame=(x, y, self.ITEM_SIZE, self.ITEM_SIZE))
            btn.title = item.icon
            btn.font = ('<System>', 20)
            btn.background_color = self.ITEM_BG
            btn.tint_color = '#FFFFFF'
            btn.corner_radius = 8
            btn.border_width = 0
            
            def make_handler(it):
                def handler(sender):
                    print(f"[ACTIONS_MENU] tapped {it.label}")
                    self.dismiss()
                    try:
                        _dispatch_menu_action(it, self.tile, self.board)
                    except Exception as e:
                        print(f"[ACTIONS_MENU_ERROR] {e}")
                return handler
            
            btn.action = make_handler(item)
            btn._menu_action = btn.action
            self.add_subview(btn)
            self._buttons.append(btn)
        
        self._position_above_tile()
    
    def _position_above_tile(self):
        """Position menu above the tile."""
        tile = self.tile
        board = self.board
        tx, ty = tile.frame.x, tile.frame.y
        tw = tile.frame.width
        
        x = tx + tw / 2 - self.width / 2
        y = ty - self.height - 8
        
        x = max(4, min(x, board.width - self.width - 4))
        y = max(4, y)
        
        self.frame = (x, y, self.width, self.height)
        print(f"[ACTIONS_MENU] positioned at ({x:.0f}, {y:.0f})")
    
    def highlight_at_point(self, x, y):
        """Highlight button at menu-relative coords (x, y)."""
        new_highlight = None
        for btn in self._buttons:
            try:
                bx, by, bw, bh = btn.frame
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    new_highlight = btn
                    break
            except Exception:
                pass
        
        if new_highlight != self._highlighted_button:
            if self._highlighted_button:
                try:
                    self._highlighted_button.background_color = self.ITEM_BG
                except Exception:
                    pass
            
            self._highlighted_button = new_highlight
            if self._highlighted_button:
                try:
                    self._highlighted_button.background_color = '#5A5A5C'
                    print(f"[ACTIONS_MENU_HIGHLIGHT] {self._highlighted_button.title}")
                except Exception:
                    pass
    
    def get_highlighted_action(self):
        """Return the action callback for highlighted button, or None."""
        if self._highlighted_button:
            return getattr(self._highlighted_button, '_menu_action', None)
        return None
    
    def dismiss(self):
        print(f"[ACTIONS_MENU] dismissing")
        self._highlighted_button = None
        try:
            if self.superview:
                self.superview.remove_subview(self)
        except Exception as e:
            print(f"[ACTIONS_MENU_DISMISS_ERROR] {e}")
    
    def touch_began(self, touch):
        pass
    
    def touch_moved(self, touch):
        pass
    
    def touch_ended(self, touch):
        pass


class GroupActionsMenu(ui.View):
    """
    Minimal group menu: Delete + Copy only.
    """
    ITEM_SIZE = 44
    PADDING = 6
    CORNER = 10
    BG = '#1C1C1E'
    ITEM_BG = '#2C2C2E'

    def __init__(self, tiles, board, **kwargs):
        super().__init__(**kwargs)
        self.tiles = list(tiles or [])
        self.board = board

        items = [
            ('🗑️', 'Delete', self._action_delete_group),
            ('📋', 'Copy',   self._action_copy_group),
        ]

        n = len(items)
        total_w = n * self.ITEM_SIZE + (n + 1) * self.PADDING
        total_h = self.ITEM_SIZE + self.PADDING * 2

        self.frame = (0, 0, total_w, total_h)
        self.background_color = self.BG
        self.corner_radius = self.CORNER
        self.border_width = 1
        self.border_color = '#3A3A3C'
        self.alpha = 0.97
        try:
            self.touch_enabled = True
        except Exception:
            pass

        self._buttons = []
        for i, (icon, label, action) in enumerate(items):
            x = self.PADDING + i * (self.ITEM_SIZE + self.PADDING)
            y = self.PADDING
            btn = ui.Button(frame=(x, y, self.ITEM_SIZE, self.ITEM_SIZE))
            btn.title = icon
            btn.font = ('<System>', 20)
            btn.background_color = self.ITEM_BG
            btn.tint_color = '#FFFFFF'
            btn.corner_radius = 8

            def make_handler(fn):
                def handler(sender):
                    self.dismiss()
                    try:
                        fn()
                    except Exception as e:
                        print(f"[GROUP_MENU_ERROR] {e}")
                return handler

            btn.action = make_handler(action)
            self.add_subview(btn)
            self._buttons.append(btn)

        self._position_near_group()

    def _position_near_group(self):
        board = self.board
        tiles = self.tiles
        if not tiles:
            self.frame = (6, 6, self.width, self.height)
            return
        # position above the group bbox
        xs = []
        ys = []
        for t in tiles:
            try:
                f = t.frame
                xs.extend([f.x, f.x + f.width])
                ys.extend([f.y, f.y + f.height])
            except Exception:
                pass
        if not xs or not ys:
            self.frame = (6, 6, self.width, self.height)
            return
        min_x, max_x = min(xs), max(xs)
        min_y = min(ys)
        cx = (min_x + max_x) * 0.5
        x = cx - self.width * 0.5
        y = min_y - self.height - 10
        x = max(4, min(x, board.width - self.width - 4))
        y = max(4, y)
        self.frame = (x, y, self.width, self.height)

    def _action_delete_group(self):
        b = self.board
        tiles = list(self.tiles)
        for t in tiles:
            try:
                b.remove_tile(t)
            except Exception:
                pass
        try:
            b.clear_lasso_selection()
        except Exception:
            pass
        try:
            b._capture_undo_snapshot()
        except Exception:
            pass
        print(f"[GROUP] deleted {len(tiles)} tiles")

    def _action_copy_group(self):
        b = self.board
        tiles = list(self.tiles)
        if not tiles:
            return
        # Duplicate, offset down by one grid so they don’t overlap
        g = float(getattr(b, 'grid', 60) or 60)
        try:
            min_y = min(t.center[1] for t in tiles)
        except Exception:
            min_y = tiles[0].center[1]
        dy = g

        new_tiles = []
        for t in tiles:
            try:
                spec = b._clone_tile_spec(t)
                nt = b.create_tile_from_spec(spec)
                cx, cy = t.center
                nt.center = (cx, cy + dy)
                b.add_subview(nt)
                b.tiles.append(nt)
                try:
                    b._enforce_exclusion(nt)
                except Exception:
                    pass
                new_tiles.append(nt)
            except Exception:
                pass

        try:
            b.set_lasso_selection(new_tiles)
        except Exception:
            pass
        try:
            b._capture_undo_snapshot()
        except Exception:
            pass
        print(f"[GROUP] copied {len(new_tiles)} tiles")

    def dismiss(self):
        try:
            if self.superview:
                self.superview.remove_subview(self)
        except Exception:
            pass

class NumberScrubber(ui.View):
    ZONE_CELLS = 2
    BG = '#1C1C1E'
    HANDLE_COLOR = '#FFFFFF'
    TICK_COLOR = '#3A3A3C'
    ACTIVE_COLOR = '#0A84FF'

    def __init__(self, tile, board, touch_start_board_y):
            w = board.grid
            h = board.grid * (self.ZONE_CELLS * 2 + 1)
            super().__init__(frame=(0, 0, w, h))
            self.tile = tile
            self.board = board
            self.touch_start_y = touch_start_board_y
            self.last_increment = 0
            self.current_increment = 0
            self._auto_timer = None
            try:
                self.original_value = int(str(tile.expr_str or tile.text or '0').strip())
            except (ValueError, TypeError):
                self.original_value = 0
            self.background_color = self.BG
            self.corner_radius = 10
            self.border_width = 1
            self.border_color = '#3A3A3C'
            self.alpha = 0.92
            self._position()
    
    def _position(self):
            tile = self.tile
            board = self.board
            x = tile.frame.x + tile.frame.width + board.grid * 0.15
            y = tile.center[1] - self.height / 2
            x = min(x, board.width - self.width - 4)
            y = max(4, min(y, board.height - self.height - 4))
            self.frame = (x, y, self.width, self.height)
            # Anchor touch reference to scrubber center in board coords
            self.touch_start_y = self.y + self.height / 2
    
    def update_from_board_y(self, board_y):
            import threading
            half_grid = self.board.grid * 0.5
            dy = board_y - self.touch_start_y
            raw = -dy / half_grid
            limit = self.ZONE_CELLS * 2

            # Cancel existing auto-timer on any movement
            if self._auto_timer is not None:
                self._auto_timer.cancel()
                self._auto_timer = None

            clamped = max(-limit, min(limit, raw))
            increment = int(clamped) if clamped >= 0 else -int(-clamped)

            if increment != self.last_increment:
                self.last_increment = increment
                self.current_increment = increment
                self._apply_value(self.original_value + increment)
                self.set_needs_display()

            # At extremes - start auto-tick
            if raw >= limit:
                def tick_up():
                    self.original_value += 1
                    self.current_increment = 1
                    self._apply_value(self.original_value)
                    self.set_needs_display()
                    self._auto_timer = threading.Timer(0.12, tick_up)
                    self._auto_timer.start()
                self._auto_timer = threading.Timer(0.4, tick_up)
                self._auto_timer.start()
            elif raw <= -limit:
                def tick_down():
                    self.original_value -= 1
                    self.current_increment = -1
                    self._apply_value(self.original_value)
                    self.set_needs_display()
                    self._auto_timer = threading.Timer(0.12, tick_down)
                    self._auto_timer.start()
                self._auto_timer = threading.Timer(0.4, tick_down)
                self._auto_timer.start()
    
    def _apply_value(self, val):
        s = str(val)
        try:
            self.tile.set_label(s)
        except Exception:
            self.tile.text = s
        try:
            self.tile.expr_str = s
        except Exception:
            pass
        try:
            self.tile.data.display = s
        except Exception:
            pass
        print(f"[SCRUBBER] value -> {val}")

    def commit(self):
            if self._auto_timer is not None:
                self._auto_timer.cancel()
                self._auto_timer = None
            self.board._capture_undo_snapshot()
    
    def dismiss(self):
            if self._auto_timer is not None:
                self._auto_timer.cancel()
                self._auto_timer = None
            try:
                if self.superview:
                    self.superview.remove_subview(self)
            except Exception:
                pass
    
    def draw(self):
            w = self.width
            h = self.height
            cx = w / 2
            half_g = self.board.grid * 0.5
            center_y = h / 2

            # Tick marks only - no fills
            for i in range(-self.ZONE_CELLS * 2, self.ZONE_CELLS * 2 + 1):
                y = center_y + i * half_g
                is_center = (i == 0)
                is_major = (i % 2 == 0)
                tick_w = 16 if is_center else (10 if is_major else 6)
                color = '#FFFFFF' if is_center else ('#555558' if is_major else '#3A3A3C')
                ui.set_color(color)
                path = ui.Path()
                path.move_to(cx - tick_w / 2, y)
                path.line_to(cx + tick_w / 2, y)
                path.line_width = 2 if is_center else 1
                path.stroke()

            # Increment label at top
            if self.current_increment != 0:
                sign = '+' if self.current_increment > 0 else ''
                label = f"{sign}{self.current_increment}"
                ui.draw_string(label, rect=(0, 4, w, 18),
                    font=('<System-Bold>', 12), color=self.ACTIVE_COLOR,
                    alignment=ui.ALIGN_CENTER, line_break_mode=ui.LB_CLIP)
    
    
    
    

VARIANTS = {
    'sin':          [('sin', 'sin'),       ('arcsin', 'sin⁻¹')],
    'cos':          [('cos', 'cos'),       ('arccos', 'cos⁻¹')],
    'tan':          [('tan', 'tan'),       ('arctan', 'tan⁻¹')],
    'arcsin':       [('sin', 'sin'),       ('arcsin', 'sin⁻¹')],
    'arccos':       [('cos', 'cos'),       ('arccos', 'cos⁻¹')],
    'arctan':       [('tan', 'tan'),       ('arctan', 'tan⁻¹')],
    'sqrt':         [('sqrt', '√'),        ('cbrt', '∛'),       ('nthrt', 'n√')],
    'cbrt':         [('sqrt', '√'),        ('cbrt', '∛'),       ('nthrt', 'n√')],
    'nthrt':        [('sqrt', '√'),        ('cbrt', '∛'),       ('nthrt', 'n√')],
    'log':          [('log', 'log'),       ('ln', 'ln')],
    'ln':           [('log', 'log'),       ('ln', 'ln')],
    'deg_rad':      [('deg_rad', 'RAD'),   ('deg_rad', 'DEG')],
    'random':       [('random', 'rand'),   ('random_range', 'a-b')],
    'random_range': [('random', 'rand'),   ('random_range', 'a-b')],
    'random_range_armed': [('random', 'rand'), ('random_range', 'a-b')],
}

def _has_variants(tile):
    kind = getattr(tile, 'kind', '')
    # Tool variants (sin/cos/sqrt etc)
    if kind == 'tool':
        expr = str(getattr(tile, 'expr_str', '') or '').strip()
        base = expr.split(':')[0]
        return base in VARIANTS
    # Irrational tiles always have ≈ available
    if kind == 'irrational':
        return True
    # Decimals that came from an irrational can restore exact form
    if kind == 'number':
        m = getattr(tile.data, 'meta', {}) or {}
        return bool(m.get('exact_expr')) or bool(m.get('showing_decimal'))
    # Numeric fractions can convert to decimal
    if kind == 'fraction':
        m = getattr(tile.data, 'meta', {}) or {}
        # Numeric fraction -> decimal toggle
        if not m.get('is_expr'):
            return True
        # Expr fraction -> check if it evaluates to a numeric value (e.g. sqrt(2)/2)
        try:
            import sympy
            ne = m.get('numer_expr') or m.get('numer_disp', '')
            de = m.get('denom_expr') or m.get('denom_disp', '1')
            if ne and de:
                sym = sympy.sympify(f"({ne})/({de})")
                # Has no free symbols = purely numeric, offer decimal toggle
                return not bool(sym.free_symbols)
        except Exception:
            pass
        return False
    return False

class TileVariantPicker(ui.View):
    BG           = '#1C1C1E'
    ACTIVE_COLOR = '#0A84FF'

    def __init__(self, tile, board):
        self.tile = tile
        self.board = board
        kind = getattr(tile, 'kind', '')
        m = getattr(tile.data, 'meta', {}) or {}

        # Determine if this tile should offer decimal/exact toggle
        is_numeric_frac = (kind == 'fraction' and not m.get('is_expr'))
        is_expr_frac_numeric = False
        if kind == 'fraction' and m.get('is_expr'):
            try:
                import sympy
                ne = m.get('numer_expr') or m.get('numer_disp', '')
                de = m.get('denom_expr') or m.get('denom_disp', '1')
                if ne and de:
                    sym = sympy.sympify(f"({ne})/({de})")
                    is_expr_frac_numeric = not bool(sym.free_symbols)
            except Exception:
                pass

        self.approx_mode = (
            kind == 'irrational' or
            is_numeric_frac or
            is_expr_frac_numeric or
            kind == 'number' and bool(m.get('exact_expr'))
        )

        if self.approx_mode:
            showing_decimal = bool(m.get('showing_decimal'))
            if showing_decimal or kind == 'number':
                exact = m.get('exact_expr', '')
                try:
                    import sympy
                    from merge_engine import _pretty
                    result = sympy.sympify(exact)
                    preview_label = _pretty(result)
                except Exception:
                    preview_label = '↩'
                self.variants = [('exact', preview_label, 'irrational')]
            else:
                # Compute decimal preview
                try:
                    import sympy
                    if kind == 'fraction':
                        ne = m.get('numer_expr') or m.get('numer_disp', '0')
                        de = m.get('denom_expr') or m.get('denom_disp', '1')
                        sym = sympy.sympify(f"({ne})/({de})")
                        val = float(sympy.N(sym, 10))
                        preview_label = f"{val:.8g}"
                        # Store exact_expr so commit() can restore later
                        if not m.get('exact_expr'):
                            m['exact_expr'] = f"({ne})/({de})"
                    else:
                        exact = m.get('exact_expr', '') or str(getattr(tile, 'expr_str', '') or '')
                        result = sympy.N(sympy.sympify(exact), 10)
                        preview_label = f"{float(result):.8g}"
                except Exception:
                    preview_label = '≈'
                self.variants = [('decimal', preview_label, 'number')]
        else:
            expr = str(getattr(tile, 'expr_str', '') or '').strip()
            base = expr.split(':')[0]
            raw = VARIANTS.get(base, [])
            self.variants = [(e, d, 'tool') for e, d in raw]

        from tile import Tile as _Tile
        g = board.grid
        pad = 6
        tile_size = int(g * 0.85)
        w = tile_size + pad * 2
        h = (tile_size + pad) * max(len(self.variants), 1) + pad

        super().__init__(frame=(0, 0, w, h))
        self.current_index = None
        self.background_color = '#1C1C1E'
        self.corner_radius = 10
        self.border_width = 1
        self.border_color = '#3A3A3C'
        self.alpha = 0.97
        self._tile_size = tile_size
        self._pad = pad

        self._preview_tiles = []
        for i, (expr_str, label, tkind) in enumerate(self.variants):
            color = _Tile.color_for_kind(tkind)
            pt = _Tile(
                text=label, kind=tkind, color=color,
                w_cells=1, h_cells=1,
                cell_size=tile_size, gutter=2
            )
            pt.touch_enabled = False
            pt._fixed_size = True
            x = pad
            y = pad + i * (tile_size + pad)
            pt.frame = (x, y, tile_size, tile_size)
            self.add_subview(pt)
            self._preview_tiles.append(pt)

    def _position(self):
        tile = self.tile
        board = self.board
        x = tile.frame.x + tile.frame.width + int(board.grid * 0.15)
        y = tile.center[1] - self.height / 2
        x = min(x, board.width - self.width - 4)
        y = max(4, min(y, board.height - self.height - 4))
        self.frame = (x, y, self.width, self.height)

    def update_from_board_y(self, board_y):
        if not self.variants:
            return
        local_y = board_y - self.y
        pad = self._pad
        tile_size = self._tile_size
        zone_h = tile_size + pad
        idx = int((local_y - pad) / zone_h)
        idx = max(0, min(idx, len(self.variants) - 1))
        if idx != self.current_index:
            self.current_index = idx
            self.set_needs_display()

    def commit(self):
        if self.current_index is None or not self.variants:
            return

        variant = self.variants[self.current_index]
        action = variant[0]

        if self.approx_mode:
            import sympy
            from merge_engine import _pretty
            tile = self.tile
            m = getattr(tile.data, 'meta', {}) or {}
            kind = getattr(tile, 'kind', '')

            if action == 'exact':
                exact = m.get('exact_expr', '')
                if not exact:
                    return
                try:
                    result = sympy.sympify(exact)
                    from sympy import fraction as sym_fraction
                    numer, denom = sym_fraction(result)
                    if denom != 1 and result.is_rational:
                        tile.kind = 'fraction'
                        tile.set_cell_size(w_cells=1, h_cells=2,
                            cell_size=tile.cell_size, gutter=tile.gutter)
                        tile.data.meta['numer_disp'] = str(numer)
                        tile.data.meta['denom_disp'] = str(denom)
                        tile.data.meta['numer_expr'] = str(numer)
                        tile.data.meta['denom_expr'] = str(denom)
                        tile.data.meta['showing_decimal'] = False
                        tile.data.meta['is_expr'] = False
                        try:
                            tile._ensure_fraction_views()
                            tile._sync_fraction_from_meta()
                            tile.layout()
                        except Exception as e:
                            print(f"[APPROX_ERROR] frac_restore: {e}")
                    else:
                        disp = _pretty(result)
                        tile.kind = 'irrational'
                        tile.set_cell_size(w_cells=1, h_cells=1,
                            cell_size=tile.cell_size, gutter=tile.gutter)
                        tile.set_label(disp)
                        tile.expr_str = exact
                        m['showing_decimal'] = False
                    print(f"[APPROX] restored: {exact}")
                except Exception as e:
                    print(f"[APPROX_ERROR] restore: {e}")

            elif action == 'decimal':
                if kind == 'fraction':
                    try:
                        ne = m.get('numer_expr') or m.get('numer_disp', '0')
                        de = m.get('denom_expr') or m.get('denom_disp', '1')
                        sym = sympy.sympify(f"({ne})/({de})")
                        val = float(sympy.N(sym, 10))
                        s = f"{val:.8g}"
                        # Store exact form for restoration
                        m['exact_expr'] = f"({ne})/({de})"
                        m['showing_decimal'] = True
                        tile.set_cell_size(w_cells=1, h_cells=1,
                            cell_size=tile.cell_size, gutter=tile.gutter)
                        tile.kind = 'number'
                        tile.set_label(s)
                        tile.expr_str = s
                        print(f"[APPROX] fraction -> decimal: {s}")
                    except Exception as e:
                        print(f"[APPROX_ERROR] fraction: {e}")
                else:
                    exact = m.get('exact_expr', '') or str(getattr(tile, 'expr_str', '') or '')
                    if not exact:
                        return
                    try:
                        result = sympy.N(sympy.sympify(exact), 10)
                        val = float(result)
                        s = f"{val:.8g}"
                        m['exact_expr'] = exact
                        m['showing_decimal'] = True
                        tile.kind = 'number'
                        tile.set_cell_size(w_cells=1, h_cells=1,
                            cell_size=tile.cell_size, gutter=tile.gutter)
                        tile.set_label(s)
                        tile.expr_str = s
                        print(f"[APPROX] irrational -> decimal: {s}")
                    except Exception as e:
                        print(f"[APPROX_ERROR] decimal: {e}")

            self.board._capture_undo_snapshot()
            return

        # Normal tool variant swap
        display = variant[1]
        expr_str = variant[0]
        try:
            self.tile.expr_str = expr_str
        except Exception:
            pass
        try:
            if getattr(self.tile, 'kind', '') != 'fraction':
                self.tile.set_cell_size(
                    w_cells=1, h_cells=self.tile.h_cells,
                    cell_size=self.tile.cell_size, gutter=self.tile.gutter
                )
        except Exception:
            pass
        try:
            self.tile.set_label(display)
        except Exception:
            self.tile.text = display
        try:
            self.tile.data.display = display
        except Exception:
            pass
        if expr_str == 'deg_rad':
            mode = 'deg' if display == 'DEG' else 'rad'
            try:
                self.board.trig_mode = mode
                print(f"[VARIANT_PICKER] trig_mode -> {mode}")
            except Exception:
                pass
        else:
            print(f"[VARIANT_PICKER] transformed to {expr_str}")

    def dismiss(self):
        for pt in getattr(self, '_preview_tiles', []):
            try:
                self.remove_subview(pt)
            except Exception:
                pass
        self._preview_tiles = []
        try:
            if self.superview:
                self.superview.remove_subview(self)
        except Exception:
            pass

    def draw(self):
        if not self.variants or not self._preview_tiles:
            return
        if self.current_index is None:
            return
        pad = self._pad
        tile_size = self._tile_size
        i = self.current_index
        y = pad + i * (tile_size + pad)
        # White border around active tile
        path = ui.Path.rounded_rect(pad - 2, y - 2, tile_size + 4, tile_size + 4, 10)
        path.line_width = 2.5
        ui.set_color('#FFFFFF')
        path.stroke()

class NumberScrubber(ui.View):
    ZONE_CELLS = 2
    BG = '#1C1C1E'
    HANDLE_COLOR = '#FFFFFF'
    TICK_COLOR = '#3A3A3C'
    MAJOR_TICK_COLOR = '#555558'
    ACTIVE_COLOR = '#0A84FF'

    def __init__(self, tile, board):
        w = board.grid
        h = int(board.grid * (self.ZONE_CELLS * 2 + 1))
        super().__init__(frame=(0, 0, w, h))
        self.tile = tile
        self.board = board
        self.current_increment = 0
        self._auto_timer = None

        try:
            self.original_value = int(str(tile.expr_str or tile.text or '0').strip())
        except (ValueError, TypeError):
            self.original_value = 0

        self.background_color = self.BG
        self.corner_radius = 10
        self.border_width = 1
        self.border_color = '#3A3A3C'
        self._position()

    def _position(self):
        tile = self.tile
        board = self.board
        x = tile.frame.x + tile.frame.width + int(board.grid * 0.15)
        y = tile.center[1] - self.height / 2
        x = min(x, board.width - self.width - 4)
        y = max(4, min(y, board.height - self.height - 4))
        self.frame = (x, y, self.width, self.height)

    def scrubber_y_from_board_y(self, board_y):
        """Convert board y coordinate to scrubber-local y."""
        return board_y - self.y

    def update_from_board_y(self, board_y):
        import threading
        # Work in scrubber-local coordinates
        local_y = self.scrubber_y_from_board_y(board_y)
        center_y = self.height / 2
        half_g = self.board.grid * 0.5

        # dy negative = finger above center = positive increment
        dy = local_y - center_y
        raw = -dy / half_g
        limit = float(self.ZONE_CELLS * 2)

        # Cancel existing auto-timer whenever finger moves
        if self._auto_timer is not None:
            self._auto_timer.cancel()
            self._auto_timer = None

        if raw >= limit:
            # At top extreme - show max increment and auto-tick
            self.current_increment = int(limit)
            self._apply_value(self.original_value + self.current_increment)
            self.set_needs_display()

            def tick_up():
                self.original_value += 1
                self._apply_value(self.original_value)
                self.set_needs_display()
                self._auto_timer = threading.Timer(0.12, tick_up)
                self._auto_timer.start()

            self._auto_timer = threading.Timer(0.35, tick_up)
            self._auto_timer.start()

        elif raw <= -limit:
            # At bottom extreme - auto-tick down
            self.current_increment = -int(limit)
            self._apply_value(self.original_value + self.current_increment)
            self.set_needs_display()

            def tick_down():
                self.original_value -= 1
                self._apply_value(self.original_value)
                self.set_needs_display()
                self._auto_timer = threading.Timer(0.12, tick_down)
                self._auto_timer.start()

            self._auto_timer = threading.Timer(0.35, tick_down)
            self._auto_timer.start()

        else:
            # Normal zone
            increment = int(raw) if raw >= 0 else -int(-raw)
            if increment != self.current_increment:
                self.current_increment = increment
                self._apply_value(self.original_value + increment)
                self.set_needs_display()

    def _apply_value(self, val):
        s = str(int(val))
        try:
            self.tile.set_label(s)
        except Exception:
            self.tile.text = s
        try:
            self.tile.expr_str = s
        except Exception:
            pass
        try:
            self.tile.data.display = s
        except Exception:
            pass

    def commit(self):
        if self._auto_timer is not None:
            self._auto_timer.cancel()
            self._auto_timer = None
        self.board._capture_undo_snapshot()

    def dismiss(self):
        if self._auto_timer is not None:
            self._auto_timer.cancel()
            self._auto_timer = None
        try:
            if self.superview:
                self.superview.remove_subview(self)
        except Exception:
            pass

    def draw(self):
        w = self.width
        h = self.height
        cx = w / 2
        half_g = self.board.grid * 0.5
        center_y = h / 2

        # Tick marks only - no fills at all
        for i in range(-self.ZONE_CELLS * 2, self.ZONE_CELLS * 2 + 1):
            y = center_y + i * half_g
            if i == 0:
                tick_w = 16
                color = self.HANDLE_COLOR
                lw = 2.5
            elif i % 2 == 0:
                tick_w = 10
                color = self.MAJOR_TICK_COLOR
                lw = 1.5
            else:
                tick_w = 6
                color = self.TICK_COLOR
                lw = 1.0
            ui.set_color(color)
            path = ui.Path()
            path.move_to(cx - tick_w / 2, y)
            path.line_to(cx + tick_w / 2, y)
            path.line_width = lw
            path.stroke()

        # Increment label
        if self.current_increment != 0:
            sign = '+' if self.current_increment > 0 else ''
            label = f"{sign}{self.current_increment}"
            ui.draw_string(label, rect=(0, 4, w, 18),
                font=('<System-Bold>', 12), color=self.ACTIVE_COLOR,
                alignment=ui.ALIGN_CENTER, line_break_mode=ui.LB_CLIP)

# Backwards compatibility alias
TileMenu = ActionsMenu


















