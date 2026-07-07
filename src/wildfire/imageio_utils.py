"""Reliable image loading: JPG/TIFF -> 8-bit, 3-channel RGB numpy array.

Pillow is preferred over OpenCV here because cv2 returns BGR and mishandles
16-bit / multi-page / multi-band TIFFs. Ultralytics (and SAHI) expect 8-bit RGB.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

# Allow large drone images without the decompression-bomb warning aborting load.
Image.MAX_IMAGE_PIXELS = None

# Extensions SAHI/Ultralytics can read directly from a path without preprocessing.
PASSTHROUGH_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
SUPPORTED_EXTS = PASSTHROUGH_EXTS | {".tif", ".tiff"}


def load_rgb_uint8(path: str | Path) -> np.ndarray:
    """Load any supported image as an (H, W, 3) uint8 RGB array.

    Handles 16-bit (and float) TIFFs, grayscale, palette, RGBA, and multi-band
    images. Always returns a C-contiguous uint8 RGB array.
    """
    with Image.open(path) as im:
        im.load()
        # Palette / 'P' and 'L' modes: let Pillow expand them sensibly first.
        if im.mode in ("P", "LA", "PA"):
            im = im.convert("RGBA") if "A" in im.mode else im.convert("RGB")
        arr = np.asarray(im)

    # --- bit depth -> 8-bit ---
    if arr.dtype == np.uint16:
        arr = (arr / 256).astype(np.uint8)
    elif arr.dtype != np.uint8:
        a = arr.astype(np.float32)
        rng = float(a.max() - a.min())
        arr = (((a - a.min()) / rng) * 255).astype(np.uint8) if rng > 0 else np.zeros_like(a, np.uint8)

    # --- channels -> exactly 3 (RGB) ---
    if arr.ndim == 2:  # grayscale
        arr = np.stack([arr] * 3, axis=-1)
    elif arr.ndim == 3:
        c = arr.shape[2]
        if c == 1:
            arr = np.repeat(arr, 3, axis=2)
        elif c == 4:  # RGBA -> drop alpha
            arr = arr[:, :, :3]
        elif c > 4:  # multi-band TIFF -> first 3 bands
            arr = arr[:, :, :3]
    else:
        raise ValueError(f"Unsupported image shape {arr.shape} for {path!r}")

    return np.ascontiguousarray(arr, dtype=np.uint8)


def list_images(folder: str | Path) -> list[Path]:
    """Return supported image files in `folder`, sorted, non-recursive."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(
        p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    )
