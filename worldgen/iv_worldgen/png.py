"""Minimal PNG encoder (RGB, 8 bit) on zlib: previews without PIL."""
import struct
import zlib


def _chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def encode_png(width, height, rgb):
    """rgb: bytes/bytearray of width*height*3."""
    assert len(rgb) == width * height * 3
    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + _chunk(b"IEND", b"")


def write_png(path, width, height, rgb):
    with open(path, "wb") as f:
        f.write(encode_png(width, height, rgb))


def encode_png_gray(width, height, gray):
    """8-bit greyscale PNG (colour type 0); gray: bytes/bytearray of width*height."""
    assert len(gray) == width * height
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += gray[y * width:(y + 1) * width]
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + _chunk(b"IEND", b"")
