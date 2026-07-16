"""Tests for DJI RTK .MRK parsing and image matching."""

from __future__ import annotations

import numpy as np
from PIL import Image

from src.wildfire.gps import _dji_photo_seq, mrk_location, parse_mrk

MRK_LINES = (
    "3\t505369.172143\t[2364]\t  -339,N\t  -361,E\t   348,V\t"
    "51.10917679,Lat\t-115.38278248,Lon\t1368.634,Ellh\t0.012459, 0.010243, 0.020338\t50,Q\n"
    "4\t505370.496265\t[2364]\t  -359,N\t  -395,E\t   261,V\t"
    "51.10917663,Lat\t-115.38282037,Lon\t1368.367,Ellh\t0.012445, 0.010182, 0.020323\t50,Q\n"
    "garbage line that should be ignored\n"
)


def test_parse_mrk_rows(tmp_path):
    mrk = tmp_path / "DJI_202505021412_007_Timestamp.MRK"
    mrk.write_text(MRK_LINES, encoding="utf-8")
    rows = parse_mrk(mrk)
    assert set(rows) == {3, 4}
    lat, lon, alt = rows[3]
    assert lat == 51.10917679 and lon == -115.38278248 and alt == 1368.634


def test_dji_photo_seq_variants():
    assert _dji_photo_seq("DJI_20250502142325_0031_D.JPG") == 31
    assert _dji_photo_seq("DJI_0042.JPG") == 42
    assert _dji_photo_seq("IMG_1234.jpg") == 1234
    assert _dji_photo_seq("scene.jpg") is None


def test_mrk_location_prefers_sibling_file(tmp_path):
    mrk = tmp_path / "flight_Timestamp.MRK"
    mrk.write_text(MRK_LINES, encoding="utf-8")
    img = tmp_path / "DJI_20250502142325_0004_D.JPG"
    Image.fromarray(np.zeros((8, 8, 3), np.uint8)).save(img)
    loc = mrk_location(img)
    assert loc is not None
    assert loc[0] == 51.10917663 and loc[2] == 1368.367
    # no matching row -> None
    other = tmp_path / "DJI_20250502142325_0099_D.JPG"
    Image.fromarray(np.zeros((8, 8, 3), np.uint8)).save(other)
    assert mrk_location(other) is None
