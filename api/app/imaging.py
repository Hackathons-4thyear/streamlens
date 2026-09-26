"""Photo handling: privacy first, then quality measurement.

Every uploaded photo goes through `prepare()`, which

1. applies the EXIF orientation so the picture is the right way up,
2. drops ALL metadata, including any GPS coordinates the camera embedded,
3. downscales the long edge to MAX_IMAGE_PX,
4. re-encodes as JPEG.

Location is only ever stored from the explicit `lat`/`lon` fields the citizen
agreed to send - never harvested from a photo.

Quality is then measured on the prepared image:

- **blur** as the variance of the Laplacian. A sharp photo has lots of rapid
  intensity change at edges, so the second derivative varies a lot; a blurred
  one is smooth, so the variance collapses. Low variance means blurry.
- **brightness** as the mean of the luma channel, 0-255.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageOps

# 3x3 discrete Laplacian kernel.
_LAPLACIAN = np.array(
    [
        [0.0, 1.0, 0.0],
        [1.0, -4.0, 1.0],
        [0.0, 1.0, 0.0],
    ],
    dtype=np.float64,
)


@dataclass
class QualityIssue:
    code: str
    severity: str  # "warn" | "block"
    message: str


@dataclass
class PreparedPhoto:
    role: str
    data: bytes
    width: int
    height: int
    blur_score: float
    brightness: float
    # A smaller copy, and the ONLY version ever sent to an AI provider. Kept
    # separate from `data` so that changing what we store cannot silently
    # change what we transmit.
    ai_data: bytes = b""
    issues: list[QualityIssue] = field(default_factory=list)
    exif_stripped: bool = True
    original_bytes: int = 0

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def usable(self) -> bool:
        """Warnings still let the citizen carry on; only 'block' stops them."""
        return not any(i.severity == "block" for i in self.issues)


def _laplacian_variance(gray: np.ndarray) -> float:
    """Variance of the Laplacian, computed with an explicit 3x3 convolution.

    Done by hand with numpy slicing rather than pulling in OpenCV or SciPy for
    one kernel.
    """
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    out = np.zeros((gray.shape[0] - 2, gray.shape[1] - 2), dtype=np.float64)
    for dy in range(3):
        for dx in range(3):
            weight = _LAPLACIAN[dy, dx]
            if weight:
                out += weight * gray[dy : dy + out.shape[0], dx : dx + out.shape[1]]
    return float(out.var())


def prepare(
    raw: bytes,
    role: str,
    *,
    max_px: int = 1600,
    ai_max_px: int = 1024,
    blur_threshold: float = 100.0,
    dark_threshold: float = 45.0,
    bright_threshold: float = 225.0,
) -> PreparedPhoto:
    """Strip, downscale and measure one uploaded photo."""
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:  # noqa: BLE001 - any decode failure is the same to us
        raise ValueError(f"could not read the {role} photo as an image: {exc}") from exc

    # Rotate according to EXIF, THEN discard the metadata.
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")

    # Rebuilding from the pixel data guarantees nothing metadata-shaped survives.
    clean = Image.new("RGB", image.size)
    clean.putdata(list(image.getdata()))
    image = clean

    if max(image.size) > max_px:
        image.thumbnail((max_px, max_px), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    data = buffer.getvalue()

    # The copy for the AI: smaller again, from the same stripped pixels.
    ai_image = image.copy()
    if max(ai_image.size) > ai_max_px:
        ai_image.thumbnail((ai_max_px, ai_max_px), Image.LANCZOS)
    ai_buffer = io.BytesIO()
    ai_image.save(ai_buffer, format="JPEG", quality=82, optimize=True)
    ai_data = ai_buffer.getvalue()

    gray = np.asarray(image.convert("L"), dtype=np.float64)
    blur_score = _laplacian_variance(gray)
    brightness = float(gray.mean())

    issues: list[QualityIssue] = []
    if blur_score < blur_threshold:
        issues.append(
            QualityIssue(
                code="blurry",
                severity="warn",
                message=(
                    "This photo looks blurry. Hold still, tap the screen to focus, "
                    "and take it again if you can."
                ),
            )
        )
    if brightness < dark_threshold:
        issues.append(
            QualityIssue(
                code="dark",
                severity="warn",
                message=(
                    "This photo is very dark. Details in the shade will be hard to judge - "
                    "try again facing away from the sun."
                ),
            )
        )
    elif brightness > bright_threshold:
        issues.append(
            QualityIssue(
                code="overexposed",
                severity="warn",
                message=(
                    "This photo is very bright and washed out. Try shading the lens or "
                    "shooting from a different angle."
                ),
            )
        )

    return PreparedPhoto(
        role=role,
        data=data,
        width=image.width,
        height=image.height,
        blur_score=round(blur_score, 2),
        brightness=round(brightness, 2),
        ai_data=ai_data,
        issues=issues,
        original_bytes=len(raw),
    )
