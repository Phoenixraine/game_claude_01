"""Sound registry: every synthesised sound is declared with its manifest metadata next to its code."""
from dataclasses import dataclass
from typing import Callable, Optional

BUSES = ("sfx_ext", "sfx_cockpit", "ambient", "ui", "music")


@dataclass
class Sound:
    id: str
    fn: Callable
    variant: int
    bus: str
    loop: bool
    vol_db: float          # recommended in-game gain (files are peak-normalised, this places them in the mix)
    radius: Optional[float]  # 3D attenuation radius in metres (None = 2D)
    group: str
    dur_range: tuple       # allowed duration in seconds (checked by tests)
    peak_db: float


REGISTRY = {}


def sound(id, bus, dur, loop=False, vol=0.0, radius=None, group=None, variants=1, peak=-1.5):
    """Decorator. `fn(rng, v)` returns a float array (mono or stereo). With variants=N it is registered as id_01..id_NN."""
    assert bus in BUSES, bus

    def deco(fn):
        for v in range(variants):
            sid = id if variants == 1 else "%s_%02d" % (id, v + 1)
            assert sid not in REGISTRY, sid
            REGISTRY[sid] = Sound(sid, fn, v, bus, loop, vol, radius, group or id, dur, peak)
        return fn

    return deco
