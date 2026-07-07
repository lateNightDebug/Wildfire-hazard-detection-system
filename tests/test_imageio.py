"""Tests that load_rgb_uint8 always yields an (H, W, 3) uint8 RGB array."""

from __future__ import annotations

import numpy as np
from PIL import Image

from src.wildfire.imageio_utils import list_images, load_rgb_uint8


def _assert_rgb_uint8(arr, h, w):
    assert arr.dtype == np.uint8
    assert arr.ndim == 3 and arr.shape == (h, w, 3)
    assert arr.flags["C_CONTIGUOUS"]


def test_rgb_jpg(tmp_path):
    p = tmp_path / "rgb.jpg"
    Image.fromarray((np.random.rand(12, 10, 3) * 255).astype(np.uint8)).save(p)
    _assert_rgb_uint8(load_rgb_uint8(p), 12, 10)


def test_grayscale_png(tmp_path):
    p = tmp_path / "gray.png"
    Image.fromarray((np.random.rand(8, 9) * 255).astype(np.uint8), mode="L").save(p)
    _assert_rgb_uint8(load_rgb_uint8(p), 8, 9)


def test_rgba_drops_alpha(tmp_path):
    p = tmp_path / "rgba.png"
    Image.fromarray((np.random.rand(7, 6, 4) * 255).astype(np.uint8), mode="RGBA").save(p)
    _assert_rgb_uint8(load_rgb_uint8(p), 7, 6)


def test_16bit_tiff_scaled(tmp_path):
    p = tmp_path / "depth16.tiff"
    arr16 = (np.random.rand(10, 11) * 65535).astype(np.uint16)
    Image.fromarray(arr16).save(p)  # mode 'I;16'
    out = load_rgb_uint8(p)
    _assert_rgb_uint8(out, 10, 11)
    assert out.max() <= 255


def test_list_images_filters_and_sorts(tmp_path):
    (tmp_path / "b.jpg").write_bytes(b"x")
    (tmp_path / "a.png").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("ignore")
    names = [p.name for p in list_images(tmp_path)]
    assert names == ["a.png", "b.jpg"]
