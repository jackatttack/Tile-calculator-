"""
tile_anim.py — Centralised animation primitives for tile interactions.
"""

import ui

# ── Shared timing constants ───────────────────────────────────────────────────

PULSE_SCALE       = 1.10
PULSE_UP          = 0.08
PULSE_DOWN        = 0.09
SPAWN_SCALE_START = 0.1
SPAWN_DURATION    = 0.22
FLY_DURATION      = 0.15
POP_DURATION      = 0.20


# ── Core primitives ───────────────────────────────────────────────────────────

import math
import random

class _Particle(ui.View):
    """Tiny dot that flies outward during a merge burst."""
    def __init__(self, color, size):
        super().__init__()
        self.width = self.height = size
        self.corner_radius = size / 2.0
        self.background_color = color
        self.touch_enabled = False


def emit_particles(parent, center, color='#FFD60A', count=10):
    """Burst particles outward from center, auto-clean via completion."""
    cx, cy = center
    for i in range(count):
        size = random.uniform(4, 9)
        p = _Particle(color, size)
        p.center = (cx, cy)
        p.alpha  = 1.0
        parent.add_subview(p)

        angle = (2.0 * math.pi / count) * i + random.uniform(-0.3, 0.3)
        dist  = random.uniform(35, 80)
        tx    = cx + math.cos(angle) * dist
        ty    = cy + math.sin(angle) * dist

        def _fly(pp=p, tx=tx, ty=ty):
            pp.center    = (tx, ty)
            pp.alpha     = 0.0
            pp.transform = ui.Transform.scale(0.2, 0.2)

        def _done(pp=p, par=parent):
            try:
                if pp.superview is par:
                    par.remove_subview(pp)
            except Exception:
                pass

        ui.animate(_fly, duration=0.4, completion=_done)


def flash_view(tile):
    """White flash overlay that fades out on the tile."""
    try:
        flash = ui.View(frame=tile.bounds)
        flash.background_color = 'white'
        flash.corner_radius    = getattr(tile, 'corner_radius', 14)
        flash.alpha            = 0.75
        flash.touch_enabled    = False
        tile.add_subview(flash)

        def _fade():
            flash.alpha = 0.0

        def _done(*args):
            try:
                if flash.superview is tile:
                    tile.remove_subview(flash)
            except Exception:
                pass

        ui.animate(_fade, duration=0.22, completion=_done)
    except Exception as e:
        print(f"[FLASH_ERROR] {e}")


def merge_burst(tile, color=None):
    """
    Full merge celebration on the result tile:
      grow → flash + particles → settle.
    Call this after the tile label/color have already been updated.
    """
    if tile is None:
        return

    burst_color = color or getattr(tile, 'base_color', '#FFD60A') or '#FFD60A'

    def _grow():
        tile.transform = ui.Transform.scale(1.28, 1.28)
        tile.alpha     = 1.0

    def _after_grow(*args):
        flash_view(tile)
        try:
            parent = tile.superview
            if parent is not None:
                emit_particles(parent, tile.center, color=burst_color, count=12)
        except Exception as e:
            print(f"[BURST_PARTICLES_ERROR] {e}")

        def _settle():
            tile.transform = ui.Transform()

        def _done(*args):
            pass

        ui.animate(_settle, duration=0.22, completion=_done)

    ui.animate(_grow, duration=0.10, completion=_after_grow)

def pulse(tile, scale=None, up=None, down=None, completion=None):
    if tile is None:
        if completion:
            completion()
        return
    s = scale or PULSE_SCALE
    u = up    or PULSE_UP
    d = down  or PULSE_DOWN
    def _settle(*args):
        def _done(*args):
            if completion:
                completion()
        ui.animate(
            lambda: setattr(tile, 'transform', ui.Transform()),
            duration=d, completion=_done
        )
    try:
        ui.animate(
            lambda: setattr(tile, 'transform', ui.Transform.scale(s, s)),
            duration=u, completion=_settle
        )
    except Exception as e:
        print(f"[ANIM_PULSE_ERROR] {e}")
        if completion:
            completion()

def fly_to(tile, target_center, completion=None):
    """Slide, shrink and fade the dragged tile into the target."""
    tx, ty = target_center

    def _anim():
        tile.center    = (tx, ty)
        tile.transform = ui.Transform.scale(0.1, 0.1)
        tile.alpha     = 0.0

    def _done(*args):
        tile.alpha     = 1.0
        tile.transform = ui.Transform()
        if completion:
            completion()

    ui.animate(_anim, duration=0.22, completion=_done)

def spawn_from(tile, origin_center, final_center, duration=None):
    if tile is None:
        return
    d = duration or SPAWN_DURATION
    ox, oy = origin_center
    fx, fy = final_center
    try:
        tile.center    = (ox, oy)
        tile.transform = ui.Transform.scale(SPAWN_SCALE_START, SPAWN_SCALE_START)
        tile.alpha     = 0.0
        def _go():
            tile.center    = (fx, fy)
            tile.transform = ui.Transform.scale(1.0, 1.0)
            tile.alpha     = 1.0
        ui.animate(_go, duration=d)
    except Exception as e:
        print(f"[ANIM_SPAWN_FROM_ERROR] {e}")


def pop_in(tile, duration=None):
    if tile is None:
        return
    d = duration or SPAWN_DURATION
    try:
        tile.transform = ui.Transform.scale(SPAWN_SCALE_START, SPAWN_SCALE_START)
        tile.alpha     = 0.0
        def _go():
            tile.transform = ui.Transform.scale(1.0, 1.0)
            tile.alpha     = 1.0
        ui.animate(_go, duration=d)
    except Exception as e:
        print(f"[ANIM_POP_IN_ERROR] {e}")


def shrink_out(tile, duration=None, completion=None):
    if tile is None:
        if completion:
            completion()
        return
    d = duration or FLY_DURATION
    def _go():
        tile.transform = ui.Transform.scale(0.1, 0.1)
        tile.alpha     = 0.0
    def _done(*args):
        if completion:
            completion()
    try:
        ui.animate(_go, duration=d, completion=_done if completion else None)
    except Exception as e:
        print(f"[ANIM_SHRINK_OUT_ERROR] {e}")
        if completion:
            completion()

def undo_pulse(tile, completion=None):
    pulse(tile, scale=1.12, up=0.08, down=0.08, completion=completion)


def undo_spawn(tile, from_center, to_center, duration=None):
    spawn_from(tile, origin_center=from_center, final_center=to_center,
               duration=duration or POP_DURATION)


def undo_absorb(tile, target_center, completion=None, duration=None):
    fly_to(tile, target_center=target_center,
           duration=duration or FLY_DURATION, completion=completion)


# ── Compound sequences ────────────────────────────────────────────────────────

def flash_expression(text, center, board, duration=0.5):
    """
    Briefly show an expression like '7+8' at center before
    the merge result appears. Fades in fast, holds, fades out.
    """
    import ui
    w, h = 140, 30
    lbl = ui.Label(frame=(0, 0, w, h))
    lbl.text            = text
    lbl.font            = ('<System>', 13)
    lbl.text_color      = '#FFFFFF'
    lbl.alignment       = ui.ALIGN_CENTER
    lbl.background_color = (0, 0, 0, 0)
    lbl.alpha           = 0.0
    cx, cy = center
    lbl.center = (cx, cy)
    try:
        board.add_subview(lbl)
        def _hold():
            def _out():
                try:
                    if lbl.superview:
                        lbl.superview.remove_subview(lbl)
                except Exception:
                    pass
            ui.animate(lambda: setattr(lbl, 'alpha', 0.0),
                       duration=0.15, completion=_out)
        ui.animate(lambda: setattr(lbl, 'alpha', 0.9),
                   duration=0.1,
                   completion=lambda: ui.animate(lambda: None,
                       duration=duration, completion=_hold))
    except Exception as e:
        print(f"[FLASH_EXPR_ERROR] {e}")

def merge_sequence(dragged, target, spawned=None, spawn_origin=None, spawn_final=None):
    if target is None:
        return
    tc = target.center
    def _after_fly():
        pulse(target)
        if spawned is not None:
            origin = spawn_origin or tc
            final  = spawn_final  or spawned.center
            spawn_from(spawned, origin_center=origin, final_center=final)
    fly_to(dragged, target_center=tc, completion=_after_fly)


def undo_merge_sequence(result_tile, target_center, dragged_center, completion=None):
    undo_pulse(result_tile, completion=completion)


def undo_tool_merge_sequence(result_tile, tool_tile, target_center, completion=None):
    def _after_absorb():
        undo_pulse(tool_tile, completion=completion)
    undo_absorb(result_tile,
                target_center=tool_tile.center if tool_tile else target_center,
                completion=_after_absorb)

