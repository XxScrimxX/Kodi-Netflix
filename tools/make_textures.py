"""Generate the small PNG textures the Unknown skin uses (gradients, focus underline, solid white).

Usage:  py tools/make_textures.py
Writes into skin.unknown/media/unknown/. Kodi stretches these, so they can stay tiny.
"""
import struct
import zlib
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "skin.unknown" / "media" / "unknown"


def write_png(path, width, height, pixel):
    """Write an RGBA PNG where pixel(x, y) returns an (r, g, b, a) tuple."""
    rows = (b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(width)) for y in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                     + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


def smoothstep(t):
    return t * t * (3 - 2 * t)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Opaque black on the left fading to clear on the right: blends the backdrop into the hero text.
    write_png(OUTPUT / "gradient-left.png", 256, 1, lambda x, y: (0, 0, 0, round(255 * smoothstep(1 - x / 255))))
    # Clear at the top fading to opaque black at the bottom: blends the backdrop into the poster rows.
    write_png(OUTPUT / "gradient-bottom.png", 1, 256, lambda x, y: (0, 0, 0, round(255 * smoothstep(y / 255))))
    # Focus underline for the top navigation buttons.
    write_png(OUTPUT / "underline.png", 8, 64, lambda x, y: (255, 255, 255, 255 if y >= 58 else 0))
    # Solid white, tinted with colordiffuse for focus frames and progress bars.
    write_png(OUTPUT / "white.png", 4, 4, lambda x, y: (255, 255, 255, 255))
    for texture in sorted(OUTPUT.glob("*.png")):
        print(texture.name, texture.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
