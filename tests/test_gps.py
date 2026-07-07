"""Tests for EXIF GPS conversion and graceful missing-GPS handling."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from src.wildfire.gps import _dms_to_decimal, _ratio_to_float, extract_gps


def test_ratio_to_float_variants():
    assert _ratio_to_float(5) == 5.0
    assert _ratio_to_float((3, 2)) == 1.5
    assert _ratio_to_float((1, 0)) == 0.0  # guard against div-by-zero


def test_dms_north_is_positive():
    # 53 deg 33' 0" N  ->  53.55
    assert _dms_to_decimal((53, 33, 0), "N") == pytest.approx(53.55, abs=1e-6)


def test_dms_west_is_negative():
    # 113 deg 29' 24" W  ->  -113.49
    assert _dms_to_decimal((113, 29, 24), "W") == pytest.approx(-113.49, abs=1e-6)


def test_dms_south_is_negative():
    assert _dms_to_decimal((10, 30, 0), "S") == pytest.approx(-10.5, abs=1e-6)


def test_dms_none_returns_none():
    assert _dms_to_decimal(None, "N") is None


def test_extract_gps_missing_returns_none(tmp_path):
    p = tmp_path / "plain.jpg"
    Image.fromarray(np.zeros((16, 16, 3), dtype=np.uint8)).save(p)
    assert extract_gps(p) is None
