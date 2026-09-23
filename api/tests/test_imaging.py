"""Photo handling: privacy first, then measurement."""

from __future__ import annotations

import io

from PIL import Image

from app.imaging import prepare
from tests.conftest import blurry_image, dark_image, sharp_image


def _image_with_metadata() -> bytes:
    """A 200x100 JPEG carrying a camera model, GPS coordinates and orientation 6."""
    image = Image.new("RGB", (200, 100), (90, 120, 80))
    exif = Image.Exif()
    exif[0x010F] = "StreamLensTest"  # Make
    exif[0x0110] = "SecretCamera9000"  # Model
    exif[0x0112] = 6  # Orientation: rotate to portrait

    gps = exif.get_ifd(0x8825)
    gps[1] = "N"
    gps[2] = ((40, 1), (12, 1), (30, 1))
    gps[3] = "W"
    gps[4] = ((8, 1), (25, 1), (15, 1))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif.tobytes(), quality=95)
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Privacy
# --------------------------------------------------------------------------

def test_exif_including_gps_is_stripped(tmp_path):
    raw = _image_with_metadata()
    assert Image.open(io.BytesIO(raw)).getexif(), "fixture should start with EXIF"

    prepared = prepare(raw, "upstream")

    result = Image.open(io.BytesIO(prepared.data))
    assert dict(result.getexif()) == {}
    assert result.getexif().get_ifd(0x8825) == {}
    assert b"SecretCamera9000" not in prepared.data
    assert prepared.exif_stripped is True


def test_orientation_is_applied_before_the_metadata_is_dropped():
    """Rotating first means stripping EXIF cannot leave the photo on its side."""
    prepared = prepare(_image_with_metadata(), "upstream")
    assert (prepared.width, prepared.height) == (100, 200)


# --------------------------------------------------------------------------
# Downscaling
# --------------------------------------------------------------------------

def test_large_photo_is_downscaled_to_the_limit():
    big = Image.new("RGB", (4000, 3000), (100, 110, 90))
    buffer = io.BytesIO()
    big.save(buffer, format="JPEG")

    prepared = prepare(buffer.getvalue(), "upstream", max_px=1600)
    assert max(prepared.width, prepared.height) == 1600
    assert (prepared.width, prepared.height) == (1600, 1200)  # aspect ratio kept


def test_small_photo_is_not_upscaled():
    prepared = prepare(sharp_image(240), "upstream", max_px=1600)
    assert (prepared.width, prepared.height) == (240, 240)


# --------------------------------------------------------------------------
# Quality measurement
# --------------------------------------------------------------------------

def test_sharp_photo_scores_far_above_a_blurry_one():
    sharp = prepare(sharp_image(), "upstream")
    blurry = prepare(blurry_image(), "upstream")
    assert sharp.blur_score > blurry.blur_score * 10


def test_blurry_photo_is_warned_about_not_blocked():
    prepared = prepare(blurry_image(), "upstream")
    codes = [i.code for i in prepared.issues]
    assert "blurry" in codes
    assert prepared.ok is False
    assert prepared.usable is True  # a warning never stops the citizen


def test_dark_photo_is_flagged():
    prepared = prepare(dark_image(), "upstream")
    assert "dark" in [i.code for i in prepared.issues]
    assert prepared.brightness < 45


def test_overexposed_photo_is_flagged():
    white = Image.new("RGB", (240, 240), (250, 250, 250))
    buffer = io.BytesIO()
    white.save(buffer, format="JPEG")

    prepared = prepare(buffer.getvalue(), "upstream")
    assert "overexposed" in [i.code for i in prepared.issues]


def test_a_good_photo_raises_no_issues():
    prepared = prepare(sharp_image(), "upstream")
    assert prepared.issues == []
    assert prepared.ok is True


def test_a_file_that_is_not_an_image_raises():
    try:
        prepare(b"this is not a photograph", "upstream")
    except ValueError as exc:
        assert "upstream" in str(exc)
    else:
        raise AssertionError("expected a ValueError")
