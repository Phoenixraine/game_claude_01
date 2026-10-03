"""Battle / menu music for IMPACT VECTOR, synthesised from nothing (numpy + scipy), in the spirit of anime mecha-battle themes:
driving breakbeat, distorted saw bass, supersaw stabs and a heroic minor-key lead.

python audio/make_battle_music.py [out_dir]

Writes stems of identical length (16 bars at 144 BPM) so the game can layer them by intensity, plus a menu loop and two stingers:
  mus_battle_drums_loop  mus_battle_bass_loop  mus_battle_synth_loop  mus_battle_lead_loop  mus_menu_loop  mus_victory  mus_defeat
Loops are seamless: the reverb / release tails wrap around to the start.
"""
import os, sys
import numpy as np
from scipy import signal
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen import dsp

SR = dsp.SR
BPM = 144.0
BEAT = 60.0 / BPM
BAR = BEAT * 4
BARS = 16
LEN = int(round(BAR * BARS * SR))
rng = np.random.default_rng(20261003)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def zeros():
    return np.zeros((LEN + SR * 6, 2))


def put(buf, sig, t, gain=1.0, pan=0.0):
    """add a mono signal at time t seconds, panned (-1..1), wrapping the tail around the loop"""
    i = int(round(t * SR))
    if sig.ndim == 1:
        l = sig * gain * np.sqrt(0.5 * (1 - pan))
        r = sig * gain * np.sqrt(0.5 * (1 + pan))
        sig = np.stack([l, r], 1)
    else:
        sig = sig * gain
    n = min(len(sig), buf.shape[0] - i)
    if n > 0:
        buf[i:i + n] += sig[:n]


def fold(buf):
    out = buf[:LEN].copy()
    tail = buf[LEN:]
    k = len(tail)
    j = 0
    while j < k:
        n = min(LEN, k - j)
        out[:n] += tail[j:j + n]
        j += n
    return out


def env(N, a, d, s, r):
    return dsp.adsr(N, a, d, s, r)


# ---------------------------------------------------------------- instruments
def kick(vol=1.0):
    N = int(0.42 * SR)
    t = np.arange(N) / SR
    f = 46 + 130 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.20)
    click = dsp.hp(dsp.white(rng, N), 3000) * np.exp(-t / 0.004) * 0.35
    return (body + click) * vol


def snare(vol=1.0):
    N = int(0.32 * SR)
    t = np.arange(N) / SR
    noise = dsp.bp(dsp.white(rng, N), 1800, 9000) * np.exp(-t / 0.07)
    tone = np.sin(2 * np.pi * 190 * t * (1 + 0.15 * np.exp(-t / 0.02))) * np.exp(-t / 0.05) * 0.8
    return (noise * 1.2 + tone) * vol


def clap(vol=1.0):
    N = int(0.3 * SR)
    t = np.arange(N) / SR
    out = np.zeros(N)
    for k in range(3):
        d = int(k * 0.011 * SR)
        out[d:] += dsp.bp(dsp.white(rng, N - d), 1200, 6000) * np.exp(-t[:N - d] / (0.012 if k < 2 else 0.09))
    return out * vol * 0.8


def hat(open_=False, vol=1.0):
    N = int((0.25 if open_ else 0.06) * SR)
    t = np.arange(N) / SR
    return dsp.hp(dsp.white(rng, N), 7500) * np.exp(-t / (0.09 if open_ else 0.014)) * vol * 0.55


def taiko(vol=1.0):
    N = int(1.1 * SR)
    t = np.arange(N) / SR
    f = 62 + 40 * np.exp(-t / 0.08)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.35)
    skin = dsp.bp(dsp.white(rng, N), 200, 900) * np.exp(-t / 0.06) * 0.6
    return (body + skin) * vol


def crash(vol=1.0):
    N = int(3.2 * SR)
    t = np.arange(N) / SR
    n = dsp.hp(dsp.white(rng, N), 4500) * np.exp(-t / 0.9)
    return n * vol * 0.5


def supersaw(f, sec, vol=1.0, detune=0.012, voices=7, cutoff=(6000.0, 1800.0), att=0.01, rel=0.2):
    N = int(sec * SR)
    out = np.zeros(N)
    for k in range(voices):
        d = (k - (voices - 1) / 2) / ((voices - 1) / 2 + 1e-9)
        out += dsp.saw(f * (1 + detune * d), N, rng.uniform(0, 1))
    out /= voices
    e = dsp.adsr(N, att, 0.08, 0.75, rel)
    fc = np.linspace(cutoff[0], cutoff[1], N)
    out = dsp.tv_filter(out, fc, "lp")
    return out * e * vol


def bass_note(f, sec, vol=1.0):
    N = int(sec * SR)
    o = dsp.saw(f, N) * 0.8 + dsp.square(f, N, 0.35) * 0.35
    o = dsp.tv_filter(o, np.full(N, 420.0) + 900.0 * np.exp(-np.arange(N) / (0.05 * SR)), "lp", q=1.6)
    o = np.tanh(o * 3.2) * 0.6
    sub = np.sin(2 * np.pi * f * np.arange(N) / SR) * 0.8
    e = dsp.adsr(N, 0.004, 0.06, 0.8, 0.05)
    return (o + sub) * e * vol


def lead_note(f, sec, vol=1.0, vib=5.5):
    N = int(sec * SR)
    t = np.arange(N) / SR
    vf = f * (1 + 0.006 * np.sin(2 * np.pi * vib * t) * np.minimum(1.0, t / 0.18))
    ph = 2 * np.pi * np.cumsum(vf) / SR
    s = np.zeros(N)
    for h, amp in ((1, 1.0), (2, 0.5), (3, 0.36), (4, 0.22), (5, 0.15), (6, 0.1)):
        s += np.sin(h * ph + 0.3 * h) * amp
    s = np.tanh(s * 0.9) * 0.7
    e = dsp.adsr(N, 0.01, 0.1, 0.8, 0.12)
    return s * e * vol


def pad_note(f, sec, vol=1.0):
    N = int(sec * SR)
    out = np.zeros(N)
    for k in range(5):
        out += dsp.saw(f * (1 + 0.004 * (k - 2)), N, rng.uniform(0, 1))
    out = dsp.lp(out / 5, 1500, 2)
    return out * dsp.adsr(N, min(1.5, sec * 0.35), 0.2, 0.9, min(2.0, sec * 0.4)) * vol


# ---------------------------------------------------------------- the song
# Am | F | C | G  x2 (bars 1-8), then Dm | Bb | F | E  x2 (bars 9-16): tension and a lift back to the top
CHORDS = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [48, 52, 55]), (55, [55, 59, 62]),
          (57, [57, 60, 64]), (53, [53, 57, 60]), (48, [48, 52, 55]), (55, [55, 59, 62]),
          (50, [50, 53, 57]), (46, [46, 50, 53]), (53, [53, 57, 60]), (52, [52, 56, 59]),
          (50, [50, 53, 57]), (46, [46, 50, 53]), (53, [53, 57, 60]), (52, [52, 56, 59])]

# heroic lead: (bar, beat offset, midi, beats)
L = []
def motif(bar0, notes):
    t = 0.0
    for m, b in notes:
        if m is not None:
            L.append((bar0 * 4 + t, m, b))
        t += b
motif(0, [(69, 1.5), (72, 0.5), (76, 2.0), (74, 1.5), (72, 0.5), (71, 2.0)])
motif(1, [(69, 1.5), (65, 0.5), (69, 1.0), (72, 1.0), (71, 1.0), (69, 1.0)])
motif(2, [(72, 1.5), (76, 0.5), (79, 2.0), (77, 1.5), (76, 0.5), (74, 2.0)])
motif(3, [(74, 1.0), (71, 1.0), (67, 1.0), (71, 1.0), (74, 4.0)])
motif(4, [(81, 1.5), (79, 0.5), (76, 2.0), (77, 1.5), (76, 0.5), (74, 2.0)])
motif(5, [(72, 1.0), (74, 1.0), (72, 1.0), (69, 1.0), (65, 1.0), (69, 3.0)])
motif(6, [(76, 1.5), (79, 0.5), (84, 2.0), (83, 1.5), (81, 0.5), (79, 2.0)])
motif(7, [(79, 1.0), (76, 1.0), (74, 1.0), (71, 1.0), (79, 4.0)])
motif(8, [(74, 1.0), (77, 1.0), (81, 2.0), (80, 1.0), (77, 1.0), (74, 2.0)])
motif(9, [(70, 1.0), (74, 1.0), (77, 2.0), (76, 1.0), (74, 1.0), (70, 2.0)])
motif(10, [(72, 1.0), (77, 1.0), (81, 2.0), (79, 1.0), (77, 1.0), (72, 2.0)])
motif(11, [(76, 1.0), (80, 1.0), (83, 2.0), (80, 4.0)])
motif(12, [(86, 1.5), (84, 0.5), (81, 2.0), (82, 1.5), (81, 0.5), (77, 2.0)])
motif(13, [(79, 1.5), (77, 0.5), (74, 2.0), (77, 1.5), (74, 0.5), (70, 2.0)])
motif(14, [(81, 1.0), (84, 1.0), (88, 2.0), (86, 1.0), (84, 1.0), (81, 2.0)])
motif(15, [(83, 1.0), (80, 1.0), (76, 1.0), (80, 1.0), (83, 4.0)])


def render_drums():
    b = zeros()
    k, s, c, h, ho, tk, cr = kick(), snare(), clap(), hat(), hat(True), taiko(), crash()
    for bar in range(BARS):
        t0 = bar * BAR
        heavy = 8 <= bar < 12            # the break: half-time with taiko
        for step in range(16):
            ts = t0 + step * BEAT / 4
            if heavy:
                if step in (0, 10):
                    put(b, k, ts, 1.0)
                if step in (0, 6, 8, 14):
                    put(b, tk, ts, 0.8, pan=0.2 * (1 if step % 4 else -1))
                if step == 8:
                    put(b, s, ts, 1.1)
                    put(b, c, ts, 0.7)
                if step % 2 == 0:
                    put(b, h, ts, 0.55 if step % 4 else 0.8)
            else:
                if step in (0, 6, 10) or (bar % 4 == 3 and step == 14):
                    put(b, k, ts, 1.0)
                if step in (4, 12):
                    put(b, s, ts, 1.0)
                    put(b, c, ts, 0.55)
                if step == 15 and bar % 2 == 1:
                    put(b, s, ts, 0.6)
                put(b, h, ts, 0.8 if step % 4 == 2 else 0.45, pan=0.25 if step % 2 else -0.25)
                if step == 14:
                    put(b, ho, ts, 0.6)
        if bar % 8 == 0:
            put(b, cr, t0, 0.9)
        if bar in (7, 15):          # fills
            for q in range(8):
                put(b, snare(0.9 - 0.05 * q), t0 + BAR - BEAT + q * BEAT / 8, 0.6 + 0.05 * q)
            put(b, tk, t0 + BAR - BEAT / 2, 1.0)
    out = fold(b)
    return out


def render_bass():
    b = zeros()
    for bar in range(BARS):
        root = CHORDS[bar][0] - 12
        t0 = bar * BAR
        heavy = 8 <= bar < 12
        pat = [0, 0, 12, 0, 0, 7, 0, 10] if not heavy else [0, None, None, None, 0, None, 3, None]
        for i, off in enumerate(pat):
            if off is None:
                continue
            ts = t0 + i * BEAT / 2
            put(b, bass_note(hz(root + off), BEAT / 2 * 0.92 * (2 if heavy else 1)), ts, 0.9, pan=0.0)
    return fold(b)


def render_synth():
    b = zeros()
    for bar in range(BARS):
        root, tri = CHORDS[bar]
        t0 = bar * BAR
        heavy = 8 <= bar < 12
        # supersaw stabs on the off-beats, long pad chord underneath
        for note in tri:
            put(b, pad_note(hz(note + 12), BAR * 1.05), t0, 0.18, pan=(note % 5 - 2) * 0.2)
        for i in (0, 3, 6, 10, 14) if not heavy else (0, 8):
            ts = t0 + i * BEAT / 2 / 1.0 * 0.5
            for note in tri:
                put(b, supersaw(hz(note + 12), BEAT * 0.4, 1.0, cutoff=(5000.0, 1500.0)), ts, 0.16, pan=(note % 7 - 3) * 0.12)
        # 16th arpeggio in the lifted sections
        if bar >= 4 and not heavy:
            for i in range(16):
                m = tri[i % 3] + 12 * (1 + (i // 3) % 2)
                N = int(BEAT / 4 * 1.1 * SR)
                note = dsp.saw(hz(m), N) * dsp.decay(N, N * 0.35 / SR / 4) * 0.5
                note = dsp.lp(note, 3500, 2)
                put(b, note, t0 + i * BEAT / 4, 0.2, pan=-0.35 if i % 2 else 0.35)
    out = fold(b)
    out = dsp.stereo_reverb(rng, out.T[0], 1.6, 0.0).T if False else out
    return out


def render_lead():
    b = zeros()
    for (beat, m, dur) in L:
        put(b, lead_note(hz(m), dur * BEAT * 0.96), beat * BEAT, 0.8, pan=0.05)
        # a ghost echo on the other side
        put(b, lead_note(hz(m), dur * BEAT * 0.96), beat * BEAT + BEAT * 0.75, 0.28, pan=-0.5)
    out = fold(b)
    return out


def with_reverb(x, rt60, mix):
    l = dsp.reverb(rng, x[:, 0], rt60, mix, tail=False)[:len(x)]
    r = dsp.reverb(rng, x[:, 1], rt60, mix, tail=False)[:len(x)]
    return np.stack([l, r], 1)


def finish(x, name, rms_db=-20.0, peak_db=-1.5):
    x = x - x.mean(0, keepdims=True)
    rms = np.sqrt(np.mean(x ** 2))
    x = x * (10 ** (rms_db / 20) / max(rms, 1e-9))
    pk = np.abs(x).max()
    lim = 10 ** (peak_db / 20)
    if pk > lim:
        x = np.tanh(x / lim * 0.9) * lim / 0.9 * 0.999 if False else x * (lim / pk)
    return x


def write(out_dir, name, x):
    path = os.path.join(out_dir, name + ".wav")
    wavfile.write(path, SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))
    print("wrote", path, "%.1f s" % (len(x) / SR))


def menu_loop():
    L2 = int(round(BAR * 2 * 8 * SR))     # 8 slow bars (16 beats of 'half time') -> same tempo grid, 2x length per bar
    buf = np.zeros((L2 + SR * 8, 2))
    chords = [(45, [57, 60, 64]), (41, [53, 57, 60]), (48, [55, 60, 64]), (43, [55, 59, 62])] * 2
    for i, (root, tri) in enumerate(chords):
        t0 = i * BAR * 2
        for n in tri:
            sig = pad_note(hz(n), BAR * 2.3, 1.0)
            s = np.stack([sig * 0.5, sig * 0.5], 1)
            j = int(t0 * SR)
            buf[j:j + len(s)] += s * 0.22
        sub = np.sin(2 * np.pi * hz(root) * np.arange(int(BAR * 2.2 * SR)) / SR) * dsp.adsr(int(BAR * 2.2 * SR), 0.5, 0.3, 0.8, 1.5)
        j = int(t0 * SR)
        buf[j:j + len(sub), 0] += sub * 0.4
        buf[j:j + len(sub), 1] += sub * 0.4
        # distant taiko every other bar and a glassy ping
        if i % 2 == 0:
            tk = taiko(0.9)
            j2 = int((t0 + BAR) * SR)
            buf[j2:j2 + len(tk), 0] += tk * 0.5
            buf[j2:j2 + len(tk), 1] += tk * 0.5
        pn = dsp.sine(hz(tri[2] + 24), int(3.0 * SR)) * dsp.decay(int(3.0 * SR), 0.9)
        j3 = int((t0 + BEAT * 3) * SR)
        buf[j3:j3 + len(pn), 0] += pn * 0.07
        buf[j3:j3 + len(pn), 1] += pn * 0.05
    out = buf[:L2].copy()
    tail = buf[L2:]
    out[:len(tail)] += tail
    out = with_reverb(out, 3.4, 0.35)
    return out


def stinger(win):
    sec = 6.0
    N = int(sec * SR)
    buf = np.zeros((N, 2))
    chord = [57, 60, 64, 69] if win else [57, 60, 63, 66]
    for i, n in enumerate(chord):
        sig = supersaw(hz(n + (12 if win else 0)), 4.5, 1.0, cutoff=(4000.0, 900.0), att=0.05, rel=1.5)
        buf[:len(sig), i % 2] += sig * 0.3
    tk = taiko(1.0)
    buf[:len(tk), 0] += tk * 0.6
    buf[:len(tk), 1] += tk * 0.6
    if win:
        for q, n in enumerate([69, 72, 76, 81]):
            sig = lead_note(hz(n), 1.2)
            i0 = int(q * 0.22 * SR)
            buf[i0:i0 + len(sig)] += np.stack([sig, sig], 1) * 0.4
    buf = with_reverb(buf, 2.8, 0.4)
    return buf


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out_dir, exist_ok=True)
    d = render_drums()
    write(out_dir, "mus_battle_drums_loop", finish(d, "d", -19))
    bs = render_bass()
    write(out_dir, "mus_battle_bass_loop", finish(bs, "b", -20))
    sy = with_reverb(render_synth(), 1.8, 0.25)
    write(out_dir, "mus_battle_synth_loop", finish(sy, "s", -21))
    ld = with_reverb(render_lead(), 2.2, 0.3)
    write(out_dir, "mus_battle_lead_loop", finish(ld, "l", -21))
    write(out_dir, "mus_menu_loop", finish(menu_loop(), "m", -20))
    write(out_dir, "mus_victory", finish(stinger(True), "v", -17))
    write(out_dir, "mus_defeat", finish(stinger(False), "f", -17))
