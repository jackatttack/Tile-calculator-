import ui
from tile import Tile


class Board(ui.View):

    def __init__(self, grid=60, padding=12, **kwargs):
        super().__init__(**kwargs)
        self.background_color = '#2C2C2E'
        self.grid = int(grid)
        self.padding = int(padding)

        self.tiles = []
        self.selected_tile = None

        self._drag_tile = None
        self._drag_offset = (0, 0)
        self._drag_start_center = None
        self._drag_last_center = None
        self._drag_prev_center = None
        self._last_tap_time = 0.0
        self._last_tap_pos = (0, 0)

        # Keyboard typing state
        self._keyboard_active_tile = None
        # If True, the next spawned/typed tile becomes negative (meta['neg']=True).
        # This enables typing: '-' then 'x' => -x
        self._keyboard_pending_neg = False
        self._keyboard_frac_mode = False
        self._keyboard_frac_tile = None
        # Pending unary minus (keyboard): tap '-' then next tile becomes negative.
        if not hasattr(self, '_keyboard_pending_neg'):
            self._keyboard_pending_neg = False
        self._keyboard_denom_tile = None

        from merge_engine import MergeEngine
        self.merge_engine = MergeEngine()

        self.exclusion_bottom_y = None
        self.trig_mode = 'deg'

        self._init_undo()

        from board_touch import TouchHandler
        self._touch_handler = TouchHandler(self)
        from lasso_tool import LassoTool
        self.lasso = LassoTool(self)

        self._active_settings_menu = None
        self._setup_gear_button()
        self.group_selection = []

    def set_lasso_selection(self, tiles):
        # tiles: list[Tile]
        try:
            self.lasso_selected_tiles = list(tiles or [])
        except Exception:
            self.lasso_selected_tiles = []
        self._apply_lasso_highlight()

    def clear_lasso_selection(self):
        try:
            self.lasso_selected_tiles = []
        except Exception:
            pass
        self._apply_lasso_highlight()

    def _apply_lasso_highlight(self):
        # Simple highlight: white border for grouped tiles (blue still used for single selected_tile)
        group = set(getattr(self, 'lasso_selected_tiles', []) or [])
        for t in getattr(self, 'tiles', []):
            try:
                if t is None:
                    continue
                if t in group and t is not getattr(self, 'selected_tile', None):
                    t.border_color = '#ff0808'
                    t.border_width = 3
                else:
                    # restore “normal” visuals via existing API
                    if t is getattr(self, 'selected_tile', None):
                        # selected_tile handles its own style
                        pass
                    else:
                        t.set_selected(False)
            except Exception:
                pass
        try:
            self.set_needs_display()
        except Exception:
            pass

    def _setup_gear_button(self):
        from settings_menu import GearButton
        btn = GearButton(self, self._on_gear_tapped)
        self.add_subview(btn)
        self._gear_button = btn

    def _on_gear_tapped(self):
        from settings_colors import ColorPickerPanel
        for v in list(self.subviews):
            if isinstance(v, ColorPickerPanel):
                v.dismiss()
                return
        panel = ColorPickerPanel(self)
        self.add_subview(panel)
        panel.bring_to_front()

    def _on_settings_select(self, action):
        self._active_settings_menu = None
        if action == 'colors':
            from settings_colors import ColorPickerModal
            try:
                v = ColorPickerModal(self)
                v.present('sheet')
            except Exception as e:
                print(f"[COLOR_MODAL_ERROR] {e}")

    def _init_undo(self):
        self._undo_stack = []
        self._undo_limit = 20
        self._capture_undo_snapshot()

    def _capture_undo_snapshot(self, action=None):
        try:
            state = {'tiles': [], 'action': action}
            for t in self.tiles:
                m = getattr(t.data, 'meta', {}) or {}
                tile_data = {
                    'kind':     getattr(t, 'kind', 'number'),
                    'text':     getattr(t, 'text', ''),
                    'center':   list(t.center),
                    'expr_str': getattr(t, 'expr_str', ''),
                    'display':  getattr(t.data, 'display', ''),
                    'color':    getattr(t, 'base_color', '#FFD60A'),
                    'w_cells':  getattr(t, 'w_cells', 1),
                    'h_cells':  getattr(t, 'h_cells', 1),
                    'sticky':   getattr(t, 'sticky', False),
                    'meta':     dict(m) if m else {},
                }
                state['tiles'].append(tile_data)
            self._undo_stack.append(state)
            if len(self._undo_stack) > self._undo_limit:
                self._undo_stack.pop(0)
            print(f"[UNDO] captured snapshot ({len(self.tiles)} tiles, stack={len(self._undo_stack)})")
        except Exception as e:
            print(f"[UNDO_CAPTURE_ERROR] {e}")

    def undo(self):
        if len(self._undo_stack) < 2:
            print("[UNDO] nothing to undo")
            return False
        try:
            current_state = self._undo_stack[-1]
            self._undo_stack.pop()
            prev_state = self._undo_stack[-1]
            action = current_state.get('action')

            def _restore():
                for t in list(self.tiles):
                    try:
                        if t.superview:
                            t.superview.remove_subview(t)
                    except Exception:
                        pass
                self.tiles.clear()
                self.selected_tile = None
                self._keyboard_active_tile = None
                for td in prev_state['tiles']:
                    spec = {
                        'text':     td['text'],
                        'kind':     td['kind'],
                        'color':    td['color'],
                        'expr_str': td['expr_str'],
                        'display':  td['display'],
                        'w_cells':  td.get('w_cells', 1),
                        'h_cells':  td.get('h_cells', 1),
                        '_meta':    td.get('meta', {}),
                    }
                    new_tile = self.create_tile_from_spec(spec)
                    # normalize() called inside create_tile_from_spec,
                    # but run again after center/sticky are set
                    new_tile.center = tuple(td['center'])
                    try:
                        new_tile.sticky = bool(td.get('sticky', False))
                    except Exception:
                        try:
                            new_tile._sticky = bool(td.get('sticky', False))
                        except Exception:
                            pass
                    new_tile.normalize()
                    self.add_subview(new_tile)
                    self.tiles.append(new_tile)
                print(f"[UNDO] restored state ({len(self.tiles)} tiles)")

            if action and action.get('type') in ('merge', 'tool_merge'):
                from tile_anim import undo_pulse, undo_spawn, undo_absorb

                target_center  = action.get('target_center')
                dragged_center = action.get('dragged_center')
                replace_center = action.get('replace_center')
                result_center  = action.get('result_center')
                is_tool        = action.get('type') == 'tool_merge'

                result_tile = None
                search_center = result_center or replace_center
                if search_center:
                    for t in self.tiles:
                        tx, ty = t.center
                        rx, ry = search_center
                        if abs(tx - rx) < 12 and abs(ty - ry) < 12:
                            result_tile = t
                            break

                target_tile = None
                if is_tool and target_center:
                    for t in self.tiles:
                        tx, ty = t.center
                        tcx, tcy = target_center
                        if abs(tx - tcx) < 12 and abs(ty - tcy) < 12:
                            target_tile = t
                            break
                elif not is_tool:
                    target_tile = result_tile

                if result_tile:
                    pulse_tile = target_tile if (is_tool and target_tile) else result_tile

                    def _after_restore():
                        if dragged_center:
                            for t in self.tiles:
                                tx, ty = t.center
                                dx, dy = dragged_center
                                if abs(tx - dx) < 12 and abs(ty - dy) < 12:
                                    undo_spawn(t,
                                               from_center=target_center or (tx, ty),
                                               to_center=dragged_center)
                                    break

                    def _phase2():
                        _restore()
                        _after_restore()

                    if is_tool and target_tile and result_tile is not target_tile:
                        def _after_absorb():
                            undo_pulse(pulse_tile, completion=_phase2)
                        undo_absorb(result_tile,
                                    target_center=target_tile.center,
                                    completion=_after_absorb)
                    else:
                        undo_pulse(pulse_tile, completion=_phase2)
                    return True

            _restore()
            return True

        except Exception as e:
            print(f"[UNDO_RESTORE_ERROR] {e}")
            import traceback
            traceback.print_exc()
            return False

    def set_exclusion_bottom_y(self, y):
        try:
            self.exclusion_bottom_y = float(y)
        except Exception:
            self.exclusion_bottom_y = None

    def _clamp_center(self, cx, cy, tile):
        half_w = tile.width * 0.5
        half_h = tile.height * 0.5
        min_x = half_w
        max_x = self.width - half_w
        min_y = half_h
        max_y = self.height - half_h
        if max_x < min_x:
            max_x = min_x
        if max_y < min_y:
            max_y = min_y
        cx = max(min_x, min(max_x, cx))
        cy = max(min_y, min(max_y, cy))
        return cx, cy

    def snap_center(self, cx, cy, tile):
        g = float(self.grid)
        w_cells = int(getattr(tile, 'w_cells', 1) or 1)
        h_cells = int(getattr(tile, 'h_cells', 1) or 1)
        block_w = w_cells * g
        block_h = h_cells * g
        ax = cx - block_w * 0.5
        ay = cy - block_h * 0.5
        ax = round(ax / g) * g
        ay = round(ay / g) * g
        cx = ax + block_w * 0.5
        cy = ay + block_h * 0.5
        return self._clamp_center(cx, cy, tile)

    def _animate_to_snapped(self, tile, duration=0.12):
        if tile is None:
            return
        try:
            cx, cy = tile.center
            sx, sy = self.snap_center(cx, cy, tile)
            dx = sx - cx
            dy = sy - cy
            if (dx * dx + dy * dy) < 1.0:
                tile.center = (sx, sy)
                return
            def _go():
                tile.center = (sx, sy)
            ui.animate(_go, duration=duration)
        except Exception:
            try:
                tile.center = self.snap_center(*tile.center, tile)
            except Exception:
                pass

    def _enforce_exclusion(self, tile):
        if self.exclusion_bottom_y is None:
            return
        try:
            boundary = float(self.exclusion_bottom_y)
        except Exception:
            return
        boundary = max(0.0, min(boundary, float(self.height)))
        half_h = tile.height * 0.5
        if tile.y + tile.height > boundary:
            max_center_y = boundary - half_h
            min_center_y = self.padding + half_h
            max_center_y = max(min_center_y, min(max_center_y, self.height - self.padding - half_h))
            cx, cy = tile.center
            cy = max_center_y
            cx, cy = self.snap_center(cx, cy, tile)
            tile.center = (cx, cy)

    def _opposite_dir(self, d):
        return {'left': 'right', 'right': 'left', 'above': 'below', 'below': 'above'}.get(d, 'right')

    def _row_center_y(self, tile):
        if getattr(tile, 'kind', '') == 'fraction':
            return tile.y + self.grid / 2
        return tile.center[1]

    def _is_integer_tile(self, tile):
        try:
            int(str(tile.expr_str or tile.text or '').strip())
            return True
        except (ValueError, TypeError):
            return False

    # ------------------------------------------------------------------
    # Tile management
    # ------------------------------------------------------------------

    def _handle_toggle_tile(self, tile):
        """
        Toggle a tile between positive/negative using a meta flag, NOT armed-op state.

        Meta:
          - meta['neg'] (bool): current neg state
          - meta['pos_expr'] (str): cached positive/base expression (no leading - wrapper)

        This is used by keyboard '-' to produce -x, -root(2), etc.
        """
        if tile is None:
            return

        # Lazy imports to avoid module cycles
        try:
            import sympy
        except Exception:
            sympy = None

        try:
            from merge_engine import _pretty
        except Exception:
            def _pretty(x):
                return str(x)

        def _strip_outer_neg(s):
            s = str(s or '').strip()
            if not s:
                return s
            # Common forms we produce: -(...)  or  -(...)
            if s.startswith('-(') and s.endswith(')'):
                return s[2:-1].strip()
            if s.startswith('-') and len(s) > 1:
                # If it's a simple "-x" or "-3", strip only the first '-' (best-effort)
                return s[1:].strip()
            return s

        m = getattr(getattr(tile, 'data', None), 'meta', None)
        if m is None:
            return

        kind = str(getattr(tile, 'kind', '') or '')

        # --- FRACTION special-case: meta holds numer/denom, we rebuild expr_str from that ---
        if kind == 'fraction':
            try:
                numer_expr = m.get('numer_expr') or m.get('numer_disp') or '0'
                denom_expr = m.get('denom_expr') or m.get('denom_disp') or '1'
                base = f"({numer_expr})/({denom_expr})"
            except Exception:
                base = str(getattr(tile, 'expr_str', '') or '').strip() or '0'

            # Cache base positive expr
            if not m.get('pos_expr'):
                m['pos_expr'] = _strip_outer_neg(base)

            neg = not bool(m.get('neg', False))
            m['neg'] = neg

            pos_expr = str(m.get('pos_expr') or '').strip() or _strip_outer_neg(base) or '0'
            new_expr = f"-({pos_expr})" if neg else pos_expr

            # Apply
            try:
                tile.expr_str = new_expr
            except Exception:
                pass

            # Display: try pretty(sympy), else just prefix '-' visually
            disp = None
            if sympy is not None:
                try:
                    disp = _pretty(sympy.sympify(new_expr))
                except Exception:
                    disp = None
            if disp is None:
                disp = f"-{pos_expr}" if neg else pos_expr

            try:
                tile.set_label(disp)
            except Exception:
                try:
                    tile.display = disp
                except Exception:
                    try:
                        tile.text = disp
                    except Exception:
                        pass

            # Keep fraction visuals in sync if you rely on them
            try:
                tile._ensure_fraction_views()
                tile._sync_fraction_from_meta()
                tile.layout()
            except Exception:
                pass

            return

        # --- Default: any non-fraction tile ---
        cur = str(getattr(tile, 'expr_str', None) or getattr(tile, 'text', '') or '').strip()

        # Cache base positive expr once
        if not m.get('pos_expr'):
            # If we already had neg in meta, strip it to recover base
            if bool(m.get('neg', False)):
                m['pos_expr'] = _strip_outer_neg(cur)
            else:
                m['pos_expr'] = _strip_outer_neg(cur)

        pos_expr = str(m.get('pos_expr') or '').strip()
        if not pos_expr:
            pos_expr = _strip_outer_neg(cur) or '0'
            m['pos_expr'] = pos_expr

        neg = not bool(m.get('neg', False))
        m['neg'] = neg

        new_expr = f"-({pos_expr})" if neg else pos_expr

        # Apply expr_str
        try:
            tile.expr_str = new_expr
        except Exception:
            pass

        # Apply display
        disp = None
        if sympy is not None:
            try:
                disp = _pretty(sympy.sympify(new_expr))
            except Exception:
                disp = None
        if disp is None:
            # Visual fallback
            disp = f"-{pos_expr}" if neg else pos_expr

        try:
            tile.set_label(disp)
        except Exception:
            try:
                tile.display = disp
            except Exception:
                try:
                    tile.text = disp
                except Exception:
                    pass

        # Ensure the tile resizes/legibility updates
        try:
            tile.ensure_legible()
        except Exception:
            pass

    def refresh_tile_colors(self):
        """Repaint all live tiles with current KIND_COLORS after a color change."""
        for t in self.tiles:
            try:
                kind = getattr(t, 'kind', '')
                color = Tile.color_for_kind(kind)
                t.background_color = color
                t.base_color = color
            except Exception as e:
                print(f"[REFRESH_COLORS_ERROR] {e}")

    def _enter_frac_mode(self, numer_tile):
        try:
            numer_disp = str(getattr(numer_tile.data, 'display', None) or
                             getattr(numer_tile, 'text', '') or '').strip()
            numer_expr = str(getattr(numer_tile, 'expr_str', None) or
                             getattr(numer_tile, 'text', '') or '').strip()
        except Exception:
            numer_disp = ''
            numer_expr = ''
        cx, cy = numer_tile.center
        self._delete_tile(numer_tile)
        frac = self.create_tile_from_spec({
            'text': '', 'kind': 'fraction', 'color': '#FF9F0A',
            'expr_str': '', 'display': '',
        })
        frac.data.meta['numer_disp'] = numer_disp
        frac.data.meta['numer_expr'] = numer_expr
        frac.data.meta['denom_disp'] = None
        frac.data.meta['denom_expr'] = None
        try:
            frac._ensure_fraction_views()
            frac._sync_fraction_from_meta()
        except Exception:
            pass
        snap_x, snap_y = self.snap_center(cx, cy, frac)
        frac.center = (snap_x, snap_y)
        self.add_subview(frac)
        self.tiles.append(frac)
        self._enforce_exclusion(frac)
        self.select_tile(frac)
        self._keyboard_frac_mode = True
        self._keyboard_frac_tile = frac
        self._keyboard_denom_tile = None
        self._keyboard_active_tile = None
        print(f"[FRAC_MODE] entered, numer={numer_expr}")

    def _sync_denom_to_frac(self):
        frac = self._keyboard_frac_tile
        denom = self._keyboard_denom_tile
        if frac is None or denom is None:
            return
        try:
            disp = str(getattr(denom.data, 'display', None) or
                       getattr(denom, 'text', '') or '').strip()
            expr = str(getattr(denom, 'expr_str', None) or
                       getattr(denom, 'text', '') or '').strip()
            frac.data.meta['denom_disp'] = disp
            frac.data.meta['denom_expr'] = expr
            numer_expr = frac.data.meta.get('numer_expr', '')
            frac.expr_str = f"({numer_expr})/({expr})"
            frac._sync_fraction_from_meta()
            frac.layout()
        except Exception as e:
            print(f"[SYNC_DENOM_ERROR] {e}")

    def _close_frac_mode(self):
        frac = self._keyboard_frac_tile
        self._keyboard_frac_mode = False
        self._keyboard_frac_tile = None
        self._keyboard_denom_tile = None
        self._keyboard_active_tile = frac
        if frac is not None:
            self.select_tile(frac)
        print(f"[FRAC_MODE] closed")
    
    def add_tile(self, tile, center=None, snap=True):
        self.tiles.append(tile)
        self.add_subview(tile)
        if center is None:
            center = (self.width * 0.5, self.height * 0.5)
        cx, cy = center
        if snap:
            cx, cy = self.snap_center(cx, cy, tile)
        tile.center = (cx, cy)

    def create_tile_from_spec(self, spec):
        text = spec.get('text', '1')
        color = spec.get('color', '#FFD60A')
        kind = spec.get('kind', 'generic')
        spawn_kind = spec.get('spawn_kind', kind)

        if spawn_kind == 'fraction':
            t = Tile(
                text='', kind='fraction', color='#FF9F0A',
                w_cells=1, h_cells=2, cell_size=self.grid, gutter=4
            )
            meta = spec.get('_meta', {})
            if not meta:
                t.data.meta['numer_disp'] = None
                t.data.meta['denom_disp'] = None
                t.data.meta['numer_expr'] = None
                t.data.meta['denom_expr'] = None
            else:
                t.data.meta.update(meta)
            try:
                t._ensure_fraction_views()
                t._sync_fraction_from_meta()
            except Exception:
                pass
            try:
                t.magnetic = bool(spec.get('magnetic', False))
            except Exception:
                pass
            t.normalize()
            return t

        w_cells = int(spec.get('w_cells', 1) or 1)
        h_cells = int(spec.get('h_cells', 1) or 1)
        t = Tile(
            text=text, kind=kind, color=color,
            w_cells=w_cells, h_cells=h_cells,
            cell_size=self.grid, gutter=4
        )
        if 'expr_str' in spec:
            try:
                t.expr_str = spec['expr_str']
            except Exception:
                pass
        if 'display' in spec:
            try:
                t.data.display = spec['display']
                t.label.text = spec['display']
            except Exception:
                pass
        if spec.get('_meta'):
            t.data.meta.update(spec['_meta'])
        try:
            t.magnetic = bool(spec.get('magnetic', False))
        except Exception:
            pass
        t.normalize()
        return t

    def remove_tile(self, tile):
        try:
            if self.selected_tile is tile:
                self.select_tile(None)
            if self._drag_tile is tile:
                self._drag_tile = None
                self._drag_start_center = None
            if tile in self.tiles:
                self.tiles.remove(tile)
            if tile.superview is not None:
                tile.superview.remove_subview(tile)
            print(f"[BOARD] removed tile={tile.tile_id[:6]}")
        except Exception as e:
            print(f"[BOARD_REMOVE_ERROR] {e}")

    def _delete_tile(self, tile):
        if tile is None:
            return
        try:
            if self.selected_tile is tile:
                self.select_tile(None)
            if self._drag_tile is tile:
                self._drag_tile = None
                self._drag_start_center = None
            if tile in self.tiles:
                self.tiles.remove(tile)
            if tile.superview is not None:
                tile.superview.remove_subview(tile)
            print(f"[MERGE_DELETE] removed id={getattr(tile,'tile_id','?')[:6]}")
        except Exception as e:
            print(f"[MERGE_DELETE_ERROR] {e}")

    def select_tile(self, tile):
        if self.selected_tile is tile:
            return
        if self.selected_tile is not None:
            self.selected_tile.set_selected(False)
        self.selected_tile = tile
        if tile is not None:
            tile.bring_to_front()
            tile.set_selected(True)

    # ------------------------------------------------------------------
    # Drag API (used by keyboard)
    # ------------------------------------------------------------------

    def begin_drag_tile(self, tile, point=None):
        if tile is None:
            return
        if point is None:
            point = tile.center
        self.select_tile(tile)
        self._drag_tile = tile
        self._drag_tile.set_dragging(True)
        self._drag_start_center = tile.center
        self._drag_offset = (0, 0)
        try:
            c = tile.center
        except Exception:
            c = (0.0, 0.0)
        self._drag_last_center = c
        self._drag_prev_center = c

    def drag_tile_to_point(self, tile, point):
        if tile is None:
            return
        cx, cy = point
        cx, cy = self._clamp_center(cx, cy, tile)
        try:
            last = getattr(self, '_drag_last_center', None)
            if last is None:
                last = tile.center
            self._drag_prev_center = last
            self._drag_last_center = (cx, cy)
        except Exception:
            pass
        tile.center = (cx, cy)

    def end_drag_tile(self, tile):
        if tile is None:
            return
        self._dbg_tile("kb_drop_start", tile)
        try:
            raw_cx, raw_cy = tile.center
        except Exception:
            raw_cx, raw_cy = (0.0, 0.0)
        self._enforce_exclusion(tile)
        drop_p = (raw_cx, raw_cy)
        target = self.tile_at_point_excluding(drop_p, tile)
        if target is not None:
            try:
                dx = raw_cx - target.center[0]
                dy = raw_cy - target.center[1]
            except Exception:
                dx, dy = (-1.0, 0.0)
            if abs(dx) >= abs(dy):
                entered_from = 'left' if dx < 0 else 'right'
            else:
                entered_from = 'above' if dy < 0 else 'below'
            opposite = self._opposite_dir(entered_from)
            ctx = {
                'board': self,
                'spawn_direction': opposite,
                'return_direction': entered_from,
            }
            res = self.merge_engine.try_merge(tile, target, ctx)
            merged = self._apply_merge_result(res, dragged=tile, target=target)
            if merged:
                self._capture_undo_snapshot()
                tile.set_dragging(False)
                if self._drag_tile is tile:
                    self._drag_tile = None
                    self._drag_start_center = None
                return
        self._animate_to_snapped(tile, duration=0.12)
        self._capture_undo_snapshot()
        tile.set_dragging(False)
        if self._drag_tile is tile:
            self._drag_tile = None
            self._drag_start_center = None

    # ------------------------------------------------------------------
    # Merge helpers
    # ------------------------------------------------------------------

    def _apply_tile_updates(self, tile, res):
        if res.new_display is not None:
            # Reset to 1×1 before relabelling so ensure_legible
            # can shrink as well as grow
            try:
                if getattr(tile, 'kind', '') != 'fraction':
                    tile.set_cell_size(
                        w_cells=1,
                        h_cells=tile.h_cells,
                        cell_size=tile.cell_size,
                        gutter=tile.gutter
                    )
            except Exception:
                pass
            try:
                tile.set_label(res.new_display)
            except Exception:
                try:
                    tile.display = res.new_display
                except Exception:
                    tile.text = res.new_display
        if res.new_expr_str is not None:
            try:
                tile.expr_str = res.new_expr_str
            except Exception:
                pass

    def _clone_tile_spec(self, tile):
        import copy
        spec = {
            'text':    tile.data.display or '',
            'kind':    tile.kind,
            'color':   tile.base_color,
            'expr_str':tile.expr_str or '',
            'display': tile.data.display or '',
            'w_cells': getattr(tile, 'w_cells', 1),
            'h_cells': getattr(tile, 'h_cells', 1),
        }
        try:
            spec['_meta'] = copy.deepcopy(tile.data.meta)
        except Exception as e:
            spec['_meta'] = {}
            print(f"[CLONE_ERROR] {e}")
        return spec

    def _spawn_adjacent(self, anchor, spec, direction):
        g = self.grid
        cx, cy = anchor.center
        h = getattr(anchor, 'h_cells', 1)

        try:
            new_tile = self.create_tile_from_spec(spec)
        except Exception as e:
            print(f"[SPAWN_ERROR] create_tile_from_spec failed: {e}")
            return None

        # Use actual pixel widths for correct offset regardless of tile sizes
        anchor_hw = anchor.width / 2
        anchor_hh = anchor.height / 2
        new_hw = new_tile.width / 2
        new_hh = new_tile.height / 2

        def is_free(center_xy):
            try:
                tx, ty = self.snap_center(center_xy[0], center_xy[1], new_tile)
                new_tile.center = (tx, ty)
                rf = new_tile.frame
            except Exception:
                return False
            if rf.x < 0 or rf.y < 0 or (rf.x + rf.width) > self.width or (rf.y + rf.height) > self.height:
                return False
            for t in self.tiles:
                if t is anchor:
                    continue
                try:
                    tf = t.frame
                    if rf.x < tf.x + tf.width and rf.x + rf.width > tf.x and \
                       rf.y < tf.y + tf.height and rf.y + rf.height > tf.y:
                        return False
                except Exception:
                    pass
            return True

        def candidates():
            if direction == 'right':
                base = (cx + anchor_hw + new_hw, cy)
                step, lateral = (g, 0), (0, g)
            elif direction == 'left':
                base = (cx - anchor_hw - new_hw, cy)
                step, lateral = (-g, 0), (0, g)
            elif direction == 'above':
                base = (cx, cy - anchor_hh - new_hh)
                step, lateral = (0, -g), (g, 0)
            elif direction == 'below':
                base = (cx, cy + anchor_hh + new_hh)
                step, lateral = (0, g), (g, 0)
            else:
                base = (cx + anchor_hw + new_hw, cy)
                step, lateral = (g, 0), (0, g)

            max_steps = max(6, int(self.width / g) + 2)
            for k in range(max_steps):
                yield (base[0] + step[0] * k, base[1] + step[1] * k)
            for lane in range(1, 7):
                for sign in (1, -1):
                    off = lane * sign
                    lb = (base[0] + lateral[0] * off, base[1] + lateral[1] * off)
                    for k in range(max_steps):
                        yield (lb[0] + step[0] * k, lb[1] + step[1] * k)

        chosen = None
        for c in candidates():
            if is_free(c):
                chosen = c
                break

        if chosen is None:
            if direction == 'right':   chosen = (cx + anchor_hw + new_hw, cy)
            elif direction == 'left':  chosen = (cx - anchor_hw - new_hw, cy)
            elif direction == 'above': chosen = (cx, cy - anchor_hh - new_hh)
            elif direction == 'below': chosen = (cx, cy + anchor_hh + new_hh)
            else:                      chosen = (cx + anchor_hw + new_hw, cy)

        try:
            meta = spec.get('_meta')
            if meta:
                new_tile.data.meta.update(meta)
                if new_tile.kind == 'fraction':
                    try:
                        new_tile._ensure_fraction_views()
                        new_tile._sync_fraction_from_meta()
                        new_tile.layout()
                    except Exception as e:
                        print(f"[SPAWN_META_ERROR] {e}")
        except Exception:
            pass

        try:
            new_cx, new_cy = self.snap_center(chosen[0], chosen[1], new_tile)
            new_tile.center = (new_cx, new_cy)
            self.add_subview(new_tile)
            self.tiles.append(new_tile)
            self._enforce_exclusion(new_tile)
            print(f"[SPAWN_DONE] tile={new_tile.tile_id[:6]} at ({new_cx:.0f},{new_cy:.0f}) dir={direction}")
            return new_tile
        except Exception as e:
            print(f"[SPAWN_ERROR] {e}")
            return None

    def _drag_direction(self, tile):
        if self._drag_start_center is None:
            return 'right'
        sx, sy = self._drag_start_center
        ex, ey = tile.center
        dx, dy = ex - sx, ey - sy
        if abs(dx) >= abs(dy):
            return 'right' if dx > 0 else 'left'
        else:
            return 'below' if dy > 0 else 'above'

    def _entered_from_velocity(self, target, raw_cx=None, raw_cy=None):
        if target is None:
            return 'left'
        g = float(getattr(self, 'grid', 60) or 60)
        dead = g * 0.18
        try:
            p = getattr(self, '_drag_prev_center', None)
            if p is not None:
                dxp = float(p[0]) - float(target.center[0])
                dyp = float(p[1]) - float(target.center[1])
                if abs(dxp) > dead or abs(dyp) > dead:
                    if abs(dxp) >= abs(dyp):
                        return 'left' if dxp < 0 else 'right'
                    else:
                        return 'above' if dyp < 0 else 'below'
        except Exception:
            pass
        try:
            p = getattr(self, '_drag_prev_center', None)
            c = getattr(self, '_drag_last_center', None)
            if p is not None and c is not None:
                vx = float(c[0]) - float(p[0])
                vy = float(c[1]) - float(p[1])
                if (vx * vx + vy * vy) > 1.0:
                    if abs(vx) >= abs(vy):
                        return 'left' if vx > 0 else 'right'
                    else:
                        return 'above' if vy > 0 else 'below'
        except Exception:
            pass
        try:
            if raw_cx is None or raw_cy is None:
                raw_cx, raw_cy = (0.0, 0.0)
            dx = float(raw_cx) - float(target.center[0])
            dy = float(raw_cy) - float(target.center[1])
            if abs(dx) >= abs(dy):
                return 'left' if dx < 0 else 'right'
            else:
                return 'above' if dy < 0 else 'below'
        except Exception:
            return 'left'

    # ------------------------------------------------------------------
    # Equation chain
    # ------------------------------------------------------------------

    def _tiles_to_expr(self, tiles):
        parts = []
        for t in tiles:
            kind = getattr(t, 'kind', '')
            m = getattr(t.data, 'meta', {}) or {}

            if kind == 'fraction':
                n = m.get('numer_expr') or m.get('numer_disp', '0')
                d = m.get('denom_expr') or m.get('denom_disp', '1')
                s = f"({n})/({d})"
                if m.get('neg'):
                    s = f"-({s})"
                parts.append(s)
            else:
                s = str(getattr(t, 'expr_str', None) or getattr(t, 'text', '') or '').strip()
                if m.get('neg'):
                    s = f"-({s})" if s else '-0'
                parts.append(s)

        return ''.join(parts)

    def _spawn_eq_result(self, eq_tile, result, direction):
        import sympy
        from merge_engine import _pretty
        disp = _pretty(result)
        estr = str(result)
        has_sym = bool(sympy.sympify(estr).free_symbols)
        kind  = 'number' if not has_sym else 'expr'
        color = '#FFD60A' if kind == 'number' else '#BF5AF2'
        spec = {'text': disp, 'kind': kind, 'color': color, 'expr_str': estr, 'display': disp}
        self._spawn_adjacent(eq_tile, spec, direction)

    def _spawn_eq_solutions(self, eq_tile, sym, solutions):
        import sympy
        from merge_engine import _pretty
        if not solutions:
            return
        positions = ['above'] if len(solutions) == 1 else ['above', 'below']
        for sol, pos in zip(solutions, positions):
            try:
                is_numeric = not bool(sympy.sympify(sol).free_symbols)
            except Exception:
                is_numeric = False
            disp = f"{sym} = {_pretty(sol)}"
            estr = f"{sym} = {sol}" if not is_numeric else str(sol)
            spec = {
                'text':    disp,
                'kind':    'number' if is_numeric else 'expr',
                'color':   '#FFD60A' if is_numeric else '#BF5AF2',
                'expr_str':estr,
                'display': disp,
            }
            self._spawn_adjacent(eq_tile, spec, pos)

    def _eq_chain_scan(self, eq_tile):
        import sympy
        g = self.grid
        eq_cx, eq_cy = eq_tile.center
        row_tiles = [t for t in self.tiles
                     if t is not eq_tile and abs(self._row_center_y(t) - eq_cy) < g * 0.6]
        left_tiles  = sorted([t for t in row_tiles if t.center[0] < eq_cx], key=lambda t: t.center[0])
        right_tiles = sorted([t for t in row_tiles if t.center[0] > eq_cx], key=lambda t: t.center[0])
        left_expr  = self._tiles_to_expr(left_tiles)
        right_expr = self._tiles_to_expr(right_tiles)
        print(f"[EQ_CHAIN] left='{left_expr}' right='{right_expr}'")
        if not left_expr and not right_expr:
            return
        try:
            if left_expr and right_expr:
                L = sympy.sympify(left_expr)
                R = sympy.sympify(right_expr)
                free = (L - R).free_symbols
                if free:
                    sym = sorted(free, key=str)[0]
                    solutions = sympy.solve(L - R, sym)
                    self._spawn_eq_solutions(eq_tile, sym, solutions)
                else:
                    self._spawn_eq_result(eq_tile, sympy.simplify(L), 'right')
            elif left_expr:
                self._spawn_eq_result(eq_tile, sympy.simplify(sympy.sympify(left_expr)), 'right')
            else:
                self._spawn_eq_result(eq_tile, sympy.simplify(sympy.sympify(right_expr)), 'left')
        except Exception as e:
            print(f"[EQ_CHAIN_ERROR] {e}")
            import traceback
            traceback.print_exc()

    # ------------------------------------------------------------------
    # Merge result application
    # ------------------------------------------------------------------

    def _log_merge_decision(self, res, dragged, target):
        def tid(t):
            return getattr(t, 'tile_id', '?')[:6] if t else 'None'
        print(f"[MERGE_DECISION] dragged={tid(dragged)} target={tid(target)} "
              f"replace={tid(getattr(res,'replace_tile',None))} "
              f"delete={tid(getattr(res,'delete_tile',None))} "
              f"keep_both={getattr(res,'keep_both',False)} "
              f"spawn_dir={getattr(res,'spawn_direction',None)}")

    def _micro_pop(self, tile, strength=1.0):
        if tile is None:
            return
        try:
            amp = max(1.03, min(1.09, 1.045 + 0.02 * max(0.0, float(strength) - 1.0)))
            tile.transform = ui.Transform()
            def settle():
                try:
                    ui.animate(lambda: setattr(tile, 'transform', ui.Transform()), duration=0.09)
                except Exception:
                    tile.transform = ui.Transform()
            ui.animate(
                lambda: setattr(tile, 'transform', ui.Transform.scale(amp, amp)),
                duration=0.07, completion=settle
            )
        except Exception as e:
            print(f"[MICRO_POP_ERROR] {e}")

    def _apply_merge_result(self, res, dragged=None, target=None):
        if res is None:
            return False, None
        try:
            self._log_merge_decision(res, dragged, target)
        except Exception:
            pass

        replace_tile     = getattr(res, 'replace_tile', None)
        delete_tile      = getattr(res, 'delete_tile', None)
        keep_both        = bool(getattr(res, 'keep_both', False))
        spawn_direction  = getattr(res, 'spawn_direction', None)
        spawn_spec       = getattr(res, 'spawn_spec', None)
        return_tile      = getattr(res, 'return_tile', None)
        return_direction = getattr(res, 'return_direction', None)
        no_sticky        = bool(getattr(res, 'no_sticky', False))
        mutate_a         = getattr(res, 'mutate_a', None)
        mutate_target    = getattr(res, 'mutate_target', None)

        def _apply_mutations(tile, mutations):
            if tile is None or mutations is None:
                return
            try:
                lbl = mutations.get('set_label')
                if lbl is not None:
                    tile.set_label(lbl)
                for attr in ('base_color', 'background_color', 'drag_color',
                             'kind', 'expr_str'):
                    if attr in mutations:
                        setattr(tile, attr, mutations[attr])
            except Exception as e:
                print(f"[MUTATE_ERROR] {e}")

        _apply_mutations(dragged, mutate_a)
        _apply_mutations(target, mutate_target)

        def _entered_from(dragged_tile, target_tile):
            if dragged_tile is None or target_tile is None:
                return 'left'
            try:
                dx = dragged_tile.center[0] - target_tile.center[0]
                dy = dragged_tile.center[1] - target_tile.center[1]
            except Exception:
                return 'left'
            if abs(dx) >= abs(dy):
                return 'left' if dx < 0 else 'right'
            else:
                return 'above' if dy < 0 else 'below'

        def _opposite(d):
            return {'left': 'right', 'right': 'left', 'above': 'below', 'below': 'above'}.get(d, 'right')

        def _restore_tile_from_spec(tile, spec):
            if tile is None or spec is None:
                return
            try:
                k = spec.get('kind')
                if k is not None:
                    tile.kind = k
            except Exception:
                pass
            try:
                w = int(spec.get('w_cells', getattr(tile, 'w_cells', 1) or 1) or 1)
                h = int(spec.get('h_cells', getattr(tile, 'h_cells', 1) or 1) or 1)
                tile.set_cell_size(w_cells=w, h_cells=h, cell_size=tile.cell_size, gutter=tile.gutter)
            except Exception:
                pass
            try:
                meta = spec.get('_meta')
                if meta is not None:
                    tile.data.meta.clear()
                    tile.data.meta.update(meta)
            except Exception:
                pass
            try:
                if 'expr_str' in spec:
                    tile.expr_str = spec.get('expr_str') or ''
            except Exception:
                pass
            disp = spec.get('display', spec.get('text', ''))
            try:
                tile.set_label(disp)
            except Exception:
                try:
                    tile.display = disp
                except Exception:
                    try:
                        tile.text = disp
                    except Exception:
                        pass
            try:
                if getattr(tile, 'kind', '') == 'fraction':
                    tile._ensure_fraction_views()
                    tile._sync_fraction_from_meta()
                    tile.layout()
            except Exception:
                pass

        dragged_is_sticky = bool(getattr(dragged, 'sticky', False)) and not no_sticky

        if delete_tile is not None and getattr(delete_tile, 'sticky', False):
            delete_tile = None

        if dragged_is_sticky and target is not None:
            entered  = return_direction or _entered_from(dragged, target)
            opposite = spawn_direction or _opposite(entered)
            return_tile      = dragged
            return_direction = entered
            spawn_direction  = opposite
            if delete_tile is dragged:
                delete_tile = None
            host = replace_tile
            if host is None or host is dragged:
                host = target
            spawned_tile = None
            if spawn_spec is not None:
                if replace_tile is not None:
                    self._apply_tile_updates(replace_tile, res)
                anchor = host or target or dragged
                if anchor is not None:
                    spawned_tile = self._spawn_adjacent(anchor, spawn_spec, spawn_direction)
            else:
                restore_spec = None
                try:
                    restore_spec = self._clone_tile_spec(host)
                except Exception:
                    pass
                if host is not None:
                    self._apply_tile_updates(host, res)
                try:
                    result_spec = self._clone_tile_spec(host)
                except Exception:
                    result_spec = None
                if restore_spec is not None:
                    _restore_tile_from_spec(host, restore_spec)
                if result_spec is not None:
                    anchor = host or target or dragged
                    if anchor is not None:
                        spawned_tile = self._spawn_adjacent(anchor, result_spec, spawn_direction)
            if return_tile is not None and return_direction is not None:
                anchor = host or target or dragged
                if anchor is not None:
                    g = self.grid
                    ax, ay = anchor.center
                    w = getattr(anchor, 'w_cells', 1)
                    h = getattr(anchor, 'h_cells', 1)
                    dirs = {'right': (ax + g*w, ay), 'left': (ax - g*w, ay),
                            'above': (ax, ay - g*h), 'below': (ax, ay + g*h)}
                    rcx, rcy = dirs.get(return_direction, (ax + g, ay))
                    try:
                        rcx, rcy = self.snap_center(rcx, rcy, return_tile)
                        return_tile.center = (rcx, rcy)
                        self._enforce_exclusion(return_tile)
                    except Exception:
                        pass
            if delete_tile is not None and delete_tile is not return_tile:
                self._delete_tile(delete_tile)
            try:
                self._micro_pop(spawned_tile or host, strength=1.0)
            except Exception:
                pass
            return True, spawned_tile

        if delete_tile is None:
            if keep_both or (return_tile is not None):
                delete_tile = None
            else:
                delete_tile = dragged

        if replace_tile is not None:
            self._apply_tile_updates(replace_tile, res)

        spawned_tile = None
        if spawn_spec is not None and spawn_direction is not None:
            anchor = replace_tile or target or dragged
            if anchor:
                spawned_tile = self._spawn_adjacent(anchor, spawn_spec, spawn_direction)

        if return_tile is not None and return_direction is not None:
            anchor = replace_tile or target or dragged
            if anchor is not None:
                g = self.grid
                ax, ay = anchor.center
                w = getattr(anchor, 'w_cells', 1)
                h = getattr(anchor, 'h_cells', 1)
                dirs = {'right': (ax + g*w, ay), 'left': (ax - g*w, ay),
                        'above': (ax, ay - g*h), 'below': (ax, ay + g*h)}
                rcx, rcy = dirs.get(return_direction, (ax + g, ay))
                try:
                    rcx, rcy = self.snap_center(rcx, rcy, return_tile)
                    return_tile.center = (rcx, rcy)
                    self._enforce_exclusion(return_tile)
                except Exception:
                    pass

        if keep_both:
            try:
                self._micro_pop(spawned_tile or replace_tile, strength=1.0)
            except Exception:
                pass
            return True, spawned_tile

        if delete_tile is not None and delete_tile is not replace_tile:
            if delete_tile is return_tile:
                try:
                    self._micro_pop(spawned_tile or replace_tile, strength=1.0)
                except Exception:
                    pass
                return True, spawned_tile
            self._delete_tile(delete_tile)

        try:
            self._micro_pop(spawned_tile or replace_tile, strength=1.0)
        except Exception:
            pass
        return True, spawned_tile

    def tile_at_point(self, p):
        try:
            x, y = (p.x, p.y)
        except Exception:
            x, y = (p[0], p[1])
        for t in reversed(self.subviews):
            if not isinstance(t, Tile):
                continue
            if getattr(t, '_is_ghost', False):
                continue
            try:
                if t.frame.contains_point((x, y)):
                    return t
            except Exception:
                if (t.x <= x <= t.x + t.width) and (t.y <= y <= t.y + t.height):
                    return t
        return None

    def tile_at_point_excluding(self, p, exclude_tile):
        dragged_frame = getattr(exclude_tile, 'frame', None)
        for t in reversed(self.subviews):
            if t is exclude_tile or not isinstance(t, Tile):
                continue
            if getattr(t, '_is_ghost', False):
                continue
            try:
                if t.frame.contains_point(p):
                    return t
            except Exception:
                pass
            if dragged_frame is not None:
                try:
                    df = dragged_frame
                    tf = t.frame
                    overlap_w = min(df.x + df.width,  tf.x + tf.width)  - max(df.x, tf.x)
                    overlap_h = min(df.y + df.height, tf.y + tf.height) - max(df.y, tf.y)
                    if overlap_w > 0 and overlap_h > 0:
                        overlap_area = overlap_w * overlap_h
                        dragged_area = df.width * df.height
                        if dragged_area > 0 and overlap_area / dragged_area >= 0.25:
                            return t
                except Exception:
                    pass
        return None

    def layout(self):
        try:
            btn = getattr(self, '_gear_button', None)
            if btn is not None:
                size = 36
                margin = 8
                btn.frame = (self.width - size - margin, margin, size, size)
        except Exception:
            pass

    def draw(self):
        g = self.grid
        ui.set_color('#3A3A3C')
        path = ui.Path()
        x = 0
        while x <= self.width:
            path.move_to(x, 0)
            path.line_to(x, self.height)
            x += g
        y = 0
        while y <= self.height:
            path.move_to(0, y)
            path.line_to(self.width, y)
            y += g
        path.line_width = 1
        path.stroke()

    def _dbg_tile(self, tag, tile):
        if tile is None:
            print(f"[DBG {tag}] tile=None")
            return
        tid  = getattr(tile, 'tile_id', '?')
        kind = getattr(tile, 'kind', '?')
        text = getattr(tile, 'text', '?')
        sup  = 'YES' if tile.superview else 'NO'
        cx, cy = tile.center
        x, y, w, h = tile.frame
        print(f"[DBG {tag}] id={tid[:6]} kind={kind} text={text} "
              f"superview={sup} center=({cx:.1f},{cy:.1f}) "
              f"frame=({x:.1f},{y:.1f},{w:.1f},{h:.1f})")

    def _touch_point(self, touch, in_view=None):
        loc = getattr(touch, 'location', None)
        if callable(loc):
            p = loc(in_view) if in_view is not None else loc()
            try:
                return (p.x, p.y)
            except Exception:
                return (p[0], p[1])
        p = loc
        try:
            x, y = (p.x, p.y)
        except Exception:
            x, y = (p[0], p[1])
        if in_view is not None:
            from_view = getattr(touch, 'view', None)
            if from_view is not None and from_view != in_view:
                try:
                    x = x + from_view.x - in_view.x
                    y = y + from_view.y - in_view.y
                except Exception:
                    pass
        return (x, y)

    # ------------------------------------------------------------------
    # Touch delegation
    # ------------------------------------------------------------------

    def touch_began(self, touch):
        p = self._touch_point(touch, in_view=self)
        overlay = self._overlay_at(p)
        if overlay is not None:
            try:
                overlay.touch_began(touch)
            except Exception:
                pass
            return
        self._touch_handler.touch_began(touch)

    def touch_moved(self, touch):
        p = self._touch_point(touch, in_view=self)
        overlay = self._overlay_at(p)
        if overlay is not None:
            try:
                overlay.touch_moved(touch)
            except Exception:
                pass
            return
        self._touch_handler.touch_moved(touch)

    def touch_ended(self, touch):
        p = self._touch_point(touch, in_view=self)
        overlay = self._overlay_at(p)
        if overlay is not None:
            try:
                overlay.touch_ended(touch)
            except Exception:
                pass
            return
        self._touch_handler.touch_ended(touch)

    def _overlay_at(self, p):
        """Return the frontmost overlay panel at point p, or None."""
        x, y = p
        from settings_colors import ColorPickerPanel
        candidates = []
        for v in self.subviews:
            if isinstance(v, ColorPickerPanel):
                candidates.append(v)
            elif v is getattr(self, '_active_settings_menu', None) and v.superview:
                candidates.append(v)
        for v in reversed(candidates):
            try:
                f = v.frame
                if f.x <= x <= f.x + f.width and f.y <= y <= f.y + f.height:
                    return v
            except Exception:
                pass
        return None



    def _touch_in_overlay(self, p):
        """Legacy helper (kept for compatibility) - True if any overlay consumes this point."""
        return self._overlay_at(p) is not None

    def is_group_selected(self, tile):
        try:
            return tile in (self.group_selection or [])
        except Exception:
            return False

    def clear_group_selection(self):
        tiles = list(self.group_selection or [])
        self.group_selection = []
        for t in tiles:
            try:
                t.set_group_selected(False)
            except Exception:
                pass

    def set_group_selection(self, tiles):
        # Normalize + dedupe
        out = []
        seen = set()
        for t in (tiles or []):
            if t is None:
                continue
            try:
                tid = getattr(t, 'tile_id', None) or id(t)
            except Exception:
                tid = id(t)
            if tid in seen:
                continue
            seen.add(tid)
            # Only keep live tiles
            try:
                if t.superview is None:
                    continue
            except Exception:
                pass
            out.append(t)

        # Clear old visuals
        try:
            self.clear_group_selection()
        except Exception:
            pass

        self.group_selection = out

        # Apply new visuals
        for t in out:
            try:
                t.set_group_selected(True)
            except Exception:
                pass


