"""A camera's rolling shutter: when each image row is read, as the texture RTX reads it.

RTX's `shutterTimeTexturePath` is a one-column, single-channel float32 OpenEXR, a row per
image row. A row's value is when it is read: 0 is the start of the previous camera frame,
1 the start of this one. A sensor reading out over `seconds` at `rate` frames a second reads
its top row at `1 - seconds * rate` and its bottom row at 1.
"""

from __future__ import annotations

import struct
from pathlib import Path

ATTRIBUTE = "shutterTimeTexturePath"


def rows(height: int, seconds: float, rate: float) -> list[float]:
    """When each of `height` rows is read, top first. Raises `ValueError` for a readout
    longer than a frame (RTX reads no earlier than the previous frame's start)."""
    first = 1.0 - seconds * rate
    if first < 0:
        raise ValueError(
            f"A readout of {seconds:g} s is longer than a frame at {rate:g} FPS ({1 / rate:.4g} s)."
        )
    if height < 2:
        return [1.0] * height
    return [first + (1.0 - first) * i / (height - 1) for i in range(height)]


def write(file: str | Path, values: list[float]) -> Path:
    """`values` as a one-column float32 OpenEXR (channel Y, uncompressed scanlines)."""

    def attribute(name: str, kind: str, data: bytes) -> bytes:
        return name.encode() + b"\0" + kind.encode() + b"\0" + struct.pack("<i", len(data)) + data

    height = len(values)
    box = struct.pack("<4i", 0, 0, 0, height - 1)
    channels = b"Y\0" + struct.pack("<iB3xii", 2, 0, 1, 1) + b"\0"  # 2: FLOAT
    header = (
        struct.pack("<ii", 20000630, 2)
        + attribute("channels", "chlist", channels)
        + attribute("compression", "compression", b"\0")
        + attribute("dataWindow", "box2i", box)
        + attribute("displayWindow", "box2i", box)
        + attribute("lineOrder", "lineOrder", b"\0")
        + attribute("pixelAspectRatio", "float", struct.pack("<f", 1.0))
        + attribute("screenWindowCenter", "v2f", struct.pack("<2f", 0.0, 0.0))
        + attribute("screenWindowWidth", "float", struct.pack("<f", 1.0))
        + b"\0"
    )
    line = 4 + 4 + 4  # y, the data's size, one float
    start = len(header) + 8 * height
    offsets = struct.pack(f"<{height}Q", *(start + i * line for i in range(height)))
    lines = b"".join(struct.pack("<iif", y, 4, v) for y, v in enumerate(values))
    file = Path(file)
    file.write_bytes(header + offsets + lines)
    return file
