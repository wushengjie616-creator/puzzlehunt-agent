from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath

from PIL import Image, UnidentifiedImageError


class UploadError(ValueError):
    """An uploaded image did not pass the local safety gate."""


@dataclass(frozen=True)
class ValidatedImage:
    data: bytes
    mime: str
    width: int
    height: int
    original_name: str


_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


def validate_image_upload(
    data: bytes,
    declared_mime: str,
    *,
    filename: str = "upload",
    max_bytes: int = 10 * 1024 * 1024,
    max_pixels: int = 24_000_000,
) -> ValidatedImage:
    if declared_mime not in set(_FORMATS.values()):
        raise UploadError("unsupported image MIME type")
    if not data or len(data) > max_bytes:
        raise UploadError(f"image size must be in 1..{max_bytes} bytes")
    safe_name = PurePath(filename).name[:120]
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > max_pixels:
                raise UploadError("image pixels exceed the safety limit")
            image.verify()
        with Image.open(BytesIO(data)) as image:
            actual_mime = _FORMATS.get(image.format or "")
            if actual_mime != declared_mime:
                raise UploadError("declared MIME does not match decoded image format")
            normalized = image.convert("RGB")
            output = BytesIO()
            target_format = "JPEG" if actual_mime == "image/jpeg" else image.format
            normalized.save(output, format=target_format, quality=92, optimize=True)
    except UploadError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise UploadError("image could not be decoded safely") from exc
    normalized_data = output.getvalue()
    if len(normalized_data) > max_bytes:
        raise UploadError("normalized image exceeds the size limit")
    return ValidatedImage(normalized_data, actual_mime, width, height, safe_name)
