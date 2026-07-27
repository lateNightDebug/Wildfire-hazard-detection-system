"""The app icon must carry the brand mark at every size it is generated at.

This exists because of a real failure: `render_icon` used `Image.thumbnail()`,
which only ever SHRINKS. The mark cropped out of branding/logo.png is ~200 px,
so the 256 px Windows .ico came out right while the 1024 px macOS .icns kept the
mark at its native 200 px - 20% of the tile, the rest white plate. macOS 26
insets that into its own rounded tile and the app read as a blank white square
in Finder and the Dock.

Nothing else would have caught it: no test renders the icon, and the .ico size
that a developer eyeballs is exactly the size that still looked correct.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from scripts.install_desktop_app import ICNS_SIZES, ICON_SIZES, render_icon  # noqa: E402

# The mark sits at 70% of the canvas with a plate behind it. Measured across
# sizes it lands at 68-70%; 55% is loose enough to survive a logo swap with a
# different aspect ratio and still fail the 20% regression by a wide margin.
MIN_MARK_FRACTION = 0.55


def _mark_bbox(img):
    """Bounding box of the mark, ignoring the white plate and its brand rim.

    Cropping to the middle 80% drops the rim, so what is left is plate (white)
    plus mark (coloured ink). Anything not near-white is the mark.
    """
    size = img.width
    pad = int(size * 0.10)
    inner = img.crop((pad, pad, size - pad, size - pad)).convert("RGB")
    px = inner.load()
    xs, ys = [], []
    step = max(1, inner.width // 256)  # sampling: a 1024 px scan is pointless
    for x in range(0, inner.width, step):
        for y in range(0, inner.height, step):
            r, g, b = px[x, y]
            if r + g + b < 690:  # not the white plate
                xs.append(x)
                ys.append(y)
    assert xs and ys, "the icon has no mark at all - only the blank plate"
    return max(max(xs) - min(xs), max(ys) - min(ys))


@pytest.mark.parametrize("size", sorted({s for s, _ in ICNS_SIZES} | {w for w, _ in ICON_SIZES}))
def test_mark_fills_the_icon_at_every_generated_size(size):
    if size < 64:
        pytest.skip("below 64 px the mark is a few pixels and the measurement is noise")
    span = _mark_bbox(render_icon(size))
    assert span / size >= MIN_MARK_FRACTION, (
        f"at {size} px the mark spans only {span / size:.0%} of the icon - "
        "it is being scaled down but never up (see this module's docstring)"
    )


def test_icon_is_square_rgba_at_the_requested_size():
    img = render_icon(512)
    assert img.size == (512, 512)
    assert img.mode == "RGBA"
