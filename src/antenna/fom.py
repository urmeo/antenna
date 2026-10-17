"""Mathematical proxies for reported pattern values in dB.

Comparisons require the same known physical quantity and compatible settings.
These helpers do not verify gain.
"""
from __future__ import annotations

import math

from ._numeric import finite_real as _finite


def gain_linear(main_lobe_db: float) -> float:
    """Convert a reported dB value to a linear proxy without inferring its quantity."""
    if not _finite(main_lobe_db):
        raise ValueError("pattern magnitude must be finite")
    try:
        return 10.0 ** (main_lobe_db / 10.0)
    except OverflowError as exc:
        raise ValueError("pattern magnitude exceeds numeric range") from exc


def gain_per_area(main_lobe_db: float, area_mm2: float) -> float:
    """Linear pattern proxy per cm^2 of nominal patch area."""
    if not _finite(area_mm2) or area_mm2 <= 0:
        raise ValueError("area must be finite and positive")
    area_cm2 = area_mm2 / 100.0
    if area_cm2 == 0:
        raise ValueError("area is too small to represent in cm^2")
    return _proxy_result(gain_linear(main_lobe_db) / area_cm2)


def gain_bandwidth_product(main_lobe_db: float, bandwidth_pct: float) -> float:
    """Multiply the linear pattern proxy by a reported bandwidth fraction."""
    if not _finite(bandwidth_pct) or bandwidth_pct < 0:
        raise ValueError("bandwidth must be finite and nonnegative")
    return _proxy_result(gain_linear(main_lobe_db) * (bandwidth_pct / 100.0))


def _proxy_result(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("pattern proxy exceeds numeric range")
    return value
