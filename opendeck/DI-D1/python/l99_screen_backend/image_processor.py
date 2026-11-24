"""Image processing: PNG decode, validation, normalization, RGB565 conversion."""

from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass
from typing import Optional, Tuple

from PIL import Image


@dataclass(frozen=True)
class ImageValidationResult:
    """Result of image validation."""
    valid: bool
    error: Optional[str] = None
    width: int = 0
    height: int = 0
    mode: str = ""
    size_bytes: int = 0
    sha256: str = ""


@dataclass(frozen=True)
class ProcessedImage:
    """Processed image ready for screen output."""
    position: int
    rgb565_data: bytes
    sha256: str
    width: int
    height: int
    original_size: int
    timestamp: float


class ImageProcessor:
    """Handles PNG Data URL decoding, validation, and RGB565 conversion."""

    # L99 screen dimensions
    SCREEN_WIDTH = 320
    SCREEN_HEIGHT = 480

    # Logical 4x4 grid cell size
    CELL_WIDTH = 80
    CELL_HEIGHT = 120

    # Limits
    MAX_DECODED_SIZE = 2_000_000  # 2 MB
    MAX_POSITION = 15
    MIN_POSITION = 0

    # PNG magic bytes
    PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

    def __init__(self) -> None:
        self._rgba_composite_bg = (0, 0, 0, 255)  # Black background for alpha compositing

    def decode_data_url(self, data_url: str) -> Tuple[Optional[bytes], Optional[str]]:
        """Decode a PNG Data URL to raw bytes.
        
        Returns:
            (raw_bytes, error_message) - error_message is None on success.
        """
        try:
            if not data_url.startswith("data:image/png;base64,"):
                return None, "Data URL must start with 'data:image/png;base64,'"

            # Split header and base64 data
            parts = data_url.split(",", 1)
            if len(parts) != 2:
                return None, "Invalid data URL format: missing comma separator"

            b64_data = parts[1]
            raw = base64.b64decode(b64_data, validate=True)

            if len(raw) > self.MAX_DECODED_SIZE:
                return None, f"Decoded image {len(raw)} bytes exceeds {self.MAX_DECODED_SIZE} limit"

            if not raw.startswith(self.PNG_MAGIC):
                return None, "Decoded payload is not a valid PNG (magic bytes mismatch)"

            return raw, None

        except base64.binascii.Error as e:
            return None, f"Invalid Base64: {e}"
        except Exception as e:
            return None, f"Data URL decode failed: {e}"

    def validate_image(self, raw_png: bytes) -> ImageValidationResult:
        """Validate a raw PNG image.
        
        Performs full decode to verify PNG integrity.
        """
        if len(raw_png) > self.MAX_DECODED_SIZE:
            return ImageValidationResult(
                valid=False,
                error=f"Image {len(raw_png)} bytes exceeds {self.MAX_DECODED_SIZE} limit",
                size_bytes=len(raw_png)
            )

        if not raw_png.startswith(self.PNG_MAGIC):
            return ImageValidationResult(
                valid=False,
                error="Invalid PNG magic bytes",
                size_bytes=len(raw_png)
            )

        try:
            img = Image.open(io.BytesIO(raw_png))
            img.load()  # Force full decode
            width, height = img.size
            mode = img.mode

            # Calculate SHA-256
            sha256 = hashlib.sha256(raw_png).hexdigest()

            return ImageValidationResult(
                valid=True,
                width=width,
                height=height,
                mode=mode,
                size_bytes=len(raw_png),
                sha256=sha256
            )

        except Exception as e:
            return ImageValidationResult(
                valid=False,
                error=f"PNG decode failed: {e}",
                size_bytes=len(raw_png)
            )

    def validate_position(self, position: int) -> Tuple[bool, Optional[str]]:
        """Validate button position (0-15)."""
        if position < self.MIN_POSITION or position > self.MAX_POSITION:
            return False, f"Position {position} out of range [{self.MIN_POSITION}, {self.MAX_POSITION}]"
        return True, None

    def normalize_image(self, raw_png: bytes, target_width: int, target_height: int) -> Image.Image:
        """Decode PNG, convert to RGBA, composite alpha, resize to target dimensions.
        
        Alpha compositing policy: composite onto opaque black background.
        """
        img = Image.open(io.BytesIO(raw_png))

        # Convert to RGBA for consistent alpha handling
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Alpha composite onto black background
        background = Image.new("RGBA", img.size, self._rgba_composite_bg)
        img = Image.alpha_composite(background, img)

        # Resize to target cell dimensions using high-quality resampling
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        # Convert to RGB (drop alpha after compositing)
        img = img.convert("RGB")

        return img

    def rgb_to_rgb565(self, img: Image.Image) -> bytes:
        """Convert RGB PIL Image to RGB565 little-endian bytes.
        
        RGB565 format: 5 bits red, 6 bits green, 5 bits blue, little-endian.
        """
        if img.mode != "RGB":
            img = img.convert("RGB")

        width, height = img.size
        pixels = img.load()
        output = bytearray(width * height * 2)

        idx = 0
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                # RGB565: RRRRRGGGGGGBBBBB
                rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                # Little-endian
                output[idx] = rgb565 & 0xFF
                output[idx + 1] = (rgb565 >> 8) & 0xFF
                idx += 2

        return bytes(output)

    def calculate_sha256(self, data: bytes) -> str:
        """Calculate SHA-256 hash of data."""
        return hashlib.sha256(data).hexdigest()

    def process_image(
        self,
        position: int,
        data_url: str,
        timestamp: float
    ) -> Tuple[Optional[ProcessedImage], Optional[str]]:
        """Complete pipeline: decode, validate, normalize, convert to RGB565.
        
        Returns:
            (ProcessedImage, error_message) - error_message is None on success.
        """
        # Validate position
        valid, err = self.validate_position(position)
        if not valid:
            return None, err

        # Decode data URL
        raw_png, err = self.decode_data_url(data_url)
        if err:
            return None, err

        # Validate PNG
        validation = self.validate_image(raw_png)
        if not validation.valid:
            return None, validation.error

        # Normalize to cell size
        normalized = self.normalize_image(raw_png, self.CELL_WIDTH, self.CELL_HEIGHT)

        # Convert to RGB565
        rgb565_data = self.rgb_to_rgb565(normalized)

        # Calculate SHA-256 of the RGB565 output
        sha256 = self.calculate_sha256(rgb565_data)

        processed = ProcessedImage(
            position=position,
            rgb565_data=rgb565_data,
            sha256=sha256,
            width=self.CELL_WIDTH,
            height=self.CELL_HEIGHT,
            original_size=len(raw_png),
            timestamp=timestamp
        )

        return processed, None

    def process_clear(self, position: int, timestamp: float) -> ProcessedImage:
        """Create a clear (black) image for the given position."""
        # Create black RGB565 buffer
        black_rgb565 = bytes([0x00, 0x00] * (self.CELL_WIDTH * self.CELL_HEIGHT))
        sha256 = self.calculate_sha256(black_rgb565)

        return ProcessedImage(
            position=position,
            rgb565_data=black_rgb565,
            sha256=sha256,
            width=self.CELL_WIDTH,
            height=self.CELL_HEIGHT,
            original_size=0,
            timestamp=timestamp
        )