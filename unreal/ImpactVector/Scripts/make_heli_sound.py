"""Procedural helicopter rotor loop (blade slap + turbine whine + rumble). 4 s, seamless, mono 44.1 kHz -> Content/Source/audio/env_heli_rotor_loop.wav"""
import numpy as np
import wave
from scipy.signal import butter, lfilter

SR = 44100
DUR = 4.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(7)

# blade slap: 9.5 Hz pulses (38 per loop), each a short low-passed noise burst + a thump
f_blade = 9.5
phase = (t * f_blade) % 1.0
env = np.exp(-phase * 14.0) * (phase < 0.6)
noise = rng.standard_normal(N)
b, a = butter(2, 900 / (SR / 2), "low")
slap = lfilter(b, a, noise) * env
thump = np.sin(2 * np.pi * 52 * t) * np.exp(-phase * 9.0)
# the two rotor blades are not identical: alternate pulse strength
alt = 0.8 + 0.2 * np.sign(np.sin(np.pi * f_blade * t))
body = (0.9 * slap + 0.8 * thump) * alt

# turbine whine + gearbox
whine = 0.07 * np.sin(2 * np.pi * 1180 * t + 2.0 * np.sin(2 * np.pi * 0.5 * t)) + 0.04 * np.sin(2 * np.pi * 2360 * t)
whine *= 0.8 + 0.2 * np.sin(2 * np.pi * 0.25 * t)
# low rumble
b2, a2 = butter(2, 160 / (SR / 2), "low")
rumble = lfilter(b2, a2, rng.standard_normal(N)) * 0.5

sig = body + whine + rumble
# seamless: crossfade the last 0.25 s into the first 0.25 s
X = int(SR * 0.25)
fade = np.linspace(0, 1, X)
head = sig[:X].copy()
tail = sig[-X:].copy()
sig[:X] = head * fade + tail * (1 - fade)
sig = sig[:-X]
sig = sig / np.max(np.abs(sig)) * 0.8
pcm = (sig * 32767).astype(np.int16)
out = r"F:\IVUnreal\Content\Source\audio\env_heli_rotor_loop.wav"
with wave.open(out, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("wrote", out, len(pcm) / SR, "s")
