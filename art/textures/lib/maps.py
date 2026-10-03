"""Map utilities: normal/AO from height, ORM packing, PNG writing (8/16 bit), preview helpers, colour space tags."""
import json
import os

import numpy as np
from PIL import Image
from scipy.fft import irfft2, rfft2

from . import noise

F32 = np.float32


def normal_from_height(h, strength=4.0):
    """OpenGL (Y+) tangent-space normal from a periodic height map in 0..1. The slope per pixel is rescaled by n/2048 so a
    recipe looks the same at every resolution; `strength` ~ 1 (subtle) .. 6 (deep grooves)."""
    n = h.shape[0]
    dhdx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5     # per pixel
    dhdy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5     # per row (downwards)
    s = strength * 10.0 * n / 2048.0
    nx, ny, nz_ = -dhdx * s, dhdy * s, np.ones_like(h)
    ln = np.sqrt(nx * nx + ny * ny + nz_ * nz_)
    return np.stack([nx / ln, ny / ln, nz_ / ln], -1).astype(F32)


def ao_from_height(h, radius=6.0, strength=1.5):
    """Cavity AO: where the height is below its blurred surroundings the surface is occluded (1 = open)."""
    cav = noise.blur(h, radius) - h
    return np.clip(1.0 - np.clip(cav * strength * 8.0, 0, 1), 0, 1).astype(F32)


def encode_normal(nrm):
    return np.clip((nrm * 0.5 + 0.5), 0, 1).astype(F32)


def to_u8(a):
    return (np.clip(a, 0, 1) * 255.0 + 0.5).astype(np.uint8)


def to_u16(a):
    return (np.clip(a, 0, 1) * 65535.0 + 0.5).astype(np.uint16)


def save_png(path, arr, bits=8):
    """arr: float 0..1, (h, w), (h, w, 3) or (h, w, 4)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if bits == 16:
        a = to_u16(arr)
        if a.ndim == 2:
            Image.fromarray(a, mode="I;16").save(path, optimize=False, compress_level=6)
        else:
            raise ValueError("16-bit RGB not supported by PIL; use single channel")
    else:
        a = to_u8(arr)
        Image.fromarray(a).save(path, optimize=False, compress_level=9 if a.size > 3 * 2048 * 2048 else 6)


def load_png(path):
    im = Image.open(path)
    a = np.asarray(im)
    if a.dtype == np.uint16:
        return a.astype(F32) / 65535.0
    return a.astype(F32) / 255.0


SRGB = "sRGB"
LINEAR = "Linear"
CHANNEL_SPACE = {"BaseColor": SRGB, "Normal": LINEAR, "ORM": LINEAR, "Height": LINEAR}


class Material:
    """A finished PBR set at one resolution."""

    def __init__(self, name, base, height, rough, metal, ao=None, normal_strength=4.0, height_bits=8, tile=True, note=""):
        self.name = name
        self.base = np.clip(base, 0, 1).astype(F32)
        self.height = np.clip(height, 0, 1).astype(F32)
        self.rough = np.clip(rough, 0.03, 1).astype(F32)
        self.metal = np.clip(metal, 0, 1).astype(F32)
        self.ao_extra = ao
        self.normal_strength = normal_strength
        self.height_bits = height_bits
        self.tile = tile
        self.note = note

    def finish(self):
        self.normal = normal_from_height(self.height, self.normal_strength)
        ao = ao_from_height(self.height)
        if self.ao_extra is not None:
            ao = ao * self.ao_extra
        self.ao = np.clip(ao, 0, 1).astype(F32)
        self.orm = np.stack([self.ao, self.rough, self.metal], -1).astype(F32)
        return self

    def write(self, out_dir):
        d = os.path.join(out_dir, self.name)
        files = {}
        save_png(os.path.join(d, self.name + "_BaseColor.png"), self.base)
        save_png(os.path.join(d, self.name + "_Normal.png"), encode_normal(self.normal))
        save_png(os.path.join(d, self.name + "_ORM.png"), self.orm)
        save_png(os.path.join(d, self.name + "_Height.png"), self.height, bits=16 if self.height_bits == 16 else 8)
        for k in ("BaseColor", "Normal", "ORM", "Height"):
            files[k] = {"file": "out/%s/%s_%s.png" % (self.name, self.name, k), "colorspace": CHANNEL_SPACE[k]}
        return files


def thumb(arr, size):
    a = to_u8(arr)
    im = Image.fromarray(a)
    return im.resize((size, size), Image.LANCZOS)
