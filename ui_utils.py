"""Small UI helper utilities shared by views."""


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def get_point(touch, in_view=None):
    loc = touch.location
    if callable(loc):
        return loc(in_view) if in_view else loc()
    if in_view is not None:
        from_view = getattr(touch, 'view', None)
        if from_view is not None and from_view != in_view:
            try:
                window_pt = from_view.convert_point(loc, None)
                return in_view.convert_point(window_pt, None)
            except Exception:
                pass
    return loc


def pt_xy(pt):
    try:
        return pt.x, pt.y
    except Exception:
        return pt[0], pt[1]
