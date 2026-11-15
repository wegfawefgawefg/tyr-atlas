"""Tiny offline mixer for the meme soundtracks: game WAVs from extract/audio_wav and CC0 clips from tools/memes/sounds."""
import sys, os, glob, math, subprocess, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '../..'))
SR = 48000
mix = None

def init(dur):
    global mix; mix = np.zeros((int(dur * SR), 2), np.float32)
_cache = {}

def find(name):
    if os.path.exists(os.path.join(HERE, 'sounds', name + '.mp3')): return os.path.join(HERE, 'sounds', name + '.mp3')
    hits = glob.glob(os.path.join(REPO, 'extract/audio_wav', '**', name + '.wav'), recursive=True)
    assert hits, name; return hits[0]

def load(name):
    """Stereo float32 at 48 kHz, peak-normalised to 1.0 so gains below are relative to full scale."""
    if name not in _cache:
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', find(name), '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
        x = np.frombuffer(raw, np.float32).reshape(-1, 2).copy(); x /= max(1e-6, np.abs(x).max()); _cache[name] = x
    return _cache[name]

def db(g): return 10 ** (g / 20)

def pan_gains(p):  # equal power, p in [-1, 1]
    a = (p + 1) * math.pi / 4; return math.cos(a), math.sin(a)

def place(name, t, gain=0.0, trim=(0, None), fade_in=0.004, fade_out=0.02, rate=1.0, pan=0.0, length=None):
    x = load(name); a = int(trim[0] * SR); b = int(trim[1] * SR) if trim[1] else len(x); x = x[a:b]
    if rate != 1.0:
        n = int(len(x) / rate); src = np.arange(n) * rate
        x = np.stack([np.interp(src, np.arange(len(x)), x[:, c]) for c in (0, 1)], 1)
    if length: x = x[:int(length * SR)]
    x = x.copy(); n = len(x)
    fi = min(n, int(fade_in * SR)); fo = min(n, int(fade_out * SR))
    if fi: x[:fi] *= np.linspace(0, 1, fi)[:, None]
    if fo: x[-fo:] *= np.linspace(1, 0, fo)[:, None]
    l, r = pan_gains(pan); x[:, 0] *= l * db(gain) * 1.41; x[:, 1] *= r * db(gain) * 1.41
    s = int(t * SR)
    if s < 0: x = x[-s:]; s = 0
    e = min(len(mix), s + len(x)); mix[s:e] += x[:e - s]

def loop(name, t0, t1, gain_fn, rate_fn=lambda t: 1.0, pan_fn=lambda t: 0.0, trim=(0, None)):
    """Looping source with time-varying gain (dB), playback rate and pan."""
    x = load(name); a = int(trim[0] * SR); b = int(trim[1] * SR) if trim[1] else len(x); x = x[a:b]
    n = int((t1 - t0) * SR); ts = t0 + np.arange(n) / SR
    rate = np.array([rate_fn(t) for t in ts[::480]]).repeat(480)[:n]
    pos = np.cumsum(rate) % (len(x) - 1)
    y = np.stack([np.interp(pos, np.arange(len(x)), x[:, c]) for c in (0, 1)], 1)
    g = np.array([db(gain_fn(t)) for t in ts[::480]]).repeat(480)[:n]
    p = np.array([pan_fn(t) for t in ts[::480]]).repeat(480)[:n]
    ang = (p + 1) * np.pi / 4; y[:, 0] *= g * np.cos(ang) * 1.41; y[:, 1] *= g * np.sin(ang) * 1.41
    s = int(t0 * SR); mix[s:s + n] += y[:len(mix) - s]

def ramp(t, t0, t1):
    x = min(1, max(0, (t - t0) / (t1 - t0))); return x * x * (3 - 2 * x)

def write(out):
    """Soft limit, peak -1 dBFS, 16-bit WAV."""
    y = np.tanh(mix * 1.2) / np.tanh(1.2); y *= db(-1) / max(1e-6, np.abs(y).max())
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with wave.open(out, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((y * 32767).astype('<i2').tobytes())
