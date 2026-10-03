"""Spectrogram sheets (one PNG per variation group): waveform envelope on top, log-frequency STFT below."""
import numpy as np
from scipy import signal

from . import render
from .dsp import SR


def _mono(x):
    return x if x.ndim == 1 else x.mean(axis=1)


def sheet(path, members, title):
    """members: list of (id, float array). Needs matplotlib; returns False when unavailable."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    k = len(members)
    fig, axes = plt.subplots(2 * k, 1, figsize=(10, 2.6 * k), gridspec_kw={"height_ratios": [1, 3] * k}, squeeze=False)
    axes = axes[:, 0]
    for i, (sid, x) in enumerate(members):
        m = _mono(x)
        t = np.arange(len(m)) / SR
        aw, asp = axes[2 * i], axes[2 * i + 1]
        # short-time RMS envelope in dBFS (what a level meter would show)
        w = max(1, int(0.01 * SR))
        env = np.sqrt(np.convolve(m * m, np.ones(w) / w, mode="same"))
        aw.fill_between(t, -np.abs(m), np.abs(m), color="#456", lw=0, alpha=0.5)
        aw.plot(t, env, color="#d33", lw=0.8)
        aw.set_xlim(0, t[-1])
        aw.set_ylim(-1.05, 1.05)
        aw.set_ylabel("amp")
        aw.set_title("%s   (%.2f s, %s, peak %.1f dBFS, rms %.1f dBFS)" % (
            sid, len(m) / SR, "stereo" if x.ndim == 2 else "mono", render.db(np.max(np.abs(x))), render.db(render.rms(x))), fontsize=9, loc="left")
        aw.tick_params(labelbottom=False)
        nper = 2048
        f, tt, S = signal.spectrogram(m, SR, window="hann", nperseg=nper, noverlap=nper * 3 // 4, mode="magnitude")
        D = 20 * np.log10(S + 1e-9)
        asp.pcolormesh(tt, f, D, vmin=D.max() - 90, vmax=D.max(), cmap="magma", shading="auto", rasterized=True)
        asp.set_yscale("symlog", linthresh=200, linscale=0.5)
        asp.set_ylim(20, SR / 2)
        asp.set_xlim(0, t[-1])
        asp.set_ylabel("Hz")
        if i == k - 1:
            asp.set_xlabel("s")
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=70)
    plt.close(fig)
    return True
