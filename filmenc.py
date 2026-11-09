"""encodes the FONY film for turbor/gen_film.py: 256 x 144, 16 colours (tools/fony_palette.json), span updates.
  python turbor/filmenc.py [nframes]   -> work/film_enc.pkl: dict(stream=[16 KB banks], audio=[banks], pal=32 bytes V9938, n=frames)
A frame = GA groups for lines 0..127 and GB groups for lines 128..143, a group = 7 records of 7 data bytes and one of 6 (record = address lo, address hi | 40h, data)."""
import os, sys, pickle, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(PROJ, 'tools'))
import filmsim as S
import gen_film as GF
W, H = 256, 144
SLOTS = 8 * (GF.GA + GF.GB) + 6                  # samples per frame
RATE = 3579545.0 / 14 / 16
BANK = 16384
CACHE = os.path.join(PROJ, 'work', 'film_enc.pkl')
STARTS = [min(i * 7, 128 - 7) for i in range(19)]      # byte offsets of the spans in a line


def spans(D, q, gr, pal, y0, y1, groups):
    """one region (lines y0..y1-1): the records of its groups; D (indices of the display) is updated"""
    eD = ((pal[D[y0:y1]] - gr[y0:y1]) ** 2).sum(-1)
    eQ = ((pal[q[y0:y1]] - gr[y0:y1]) ** 2).sum(-1)
    d = eD - eQ                                                  # (h, W): the gain per pixel
    h = y1 - y0
    b7 = np.zeros((h, 19), np.float32); b6 = np.zeros((h, 19), np.float32)
    for k, xb in enumerate(STARTS):
        b7[:, k] = d[:, xb * 2:xb * 2 + 14].sum(1)
        b6[:, k] = d[:, xb * 2:xb * 2 + 12].sum(1)
    if y0 == 0:
        b7[127, 18] = -1e30                                       # (a 7 byte span ending at 4000h would carry into R#14: only as a 6 byte span)
    n7, n6 = 7 * groups, groups
    order = np.argsort(-b7.ravel())[:n7]
    take = np.zeros(h * 19, bool); take[order] = True
    b6f = np.where(take, -1e30, b6.ravel())
    order6 = np.argsort(-b6f)[:n6]
    recs = [(int(i), 7) for i in order] + [(int(i), 6) for i in order6]
    return recs


def pack(px):
    px = np.asarray(px)
    return (px[0::2] << 4 | px[1::2]).astype(np.uint8)


def encode(n):
    from palette_opt import to_v9938, snap
    import spanenc as SE
    pal = np.array(__import__('json').load(open(os.path.join(PROJ, 'tools', 'fony_palette.json'))), np.float32)
    import subprocess as sp
    fps = RATE / SLOTS                              # the source (24 fps) resampled to the frame rate of the stream
    cmd = ['ffmpeg', '-v', 'error', '-i', S.SRC, '-frames:v', str(n), '-vf', 'fps=%.5f,scale=%d:%d:flags=lanczos' % (fps, W, H), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    fr = np.frombuffer(sp.run(cmd, capture_output=True, check=True).stdout, np.uint8).reshape(-1, H, W, 3)
    n = min(n, len(fr))
    gr = S.grade(fr[:n])
    D = np.zeros((H, W), np.int64)
    frames = []
    for t in range(n):
        q = S.quant(gr[t], pal)
        frames.append(SE.frame_bytes(D, q, gr[t], pal, GF.GA, GF.GB, H))
    banks = SE.pack(frames)
    return banks, bytes(to_v9938(snap(pal))), len(frames[0]), 0


def audio(n):
    import build_m7 as B7
    src = r'F:\MSX Projects\Dev27\FONY.mp4'
    need = n * SLOTS
    dur_in = 10.0267
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-vn', '-ac', '1', '-af', 'atempo=%.6f' % (dur_in / (need / RATE)), '-ar', str(int(round(RATE))), '-f', 'f32le', '-'], capture_output=True, check=True)
    x = np.frombuffer(r.stdout, np.float32).astype(np.float64)
    x = np.concatenate([x[:need], np.zeros(max(0, need - len(x)))])
    x = x / max(1e-9, np.abs(x).max()) * 0.92
    idx = int(round(5.95 * need / dur_in))                      # the dreun (from 5.95 s of the FONY sound to the end) is also the sound of the XXXL screen: as loud as it was there (its own peak at 0.95)
    g = 0.95 / max(1e-9, np.abs(x[idx:]).max())
    gain = np.ones(len(x)); gain[idx:] = g; gain[idx - 200:idx] = np.linspace(1, g, 200)
    x = x * gain
    pcm = B7.pcm8(x)
    return B7.to_banks(pcm)


N_FRAMES = int(round(240 * 670 / SLOTS))          # the film lasts 10.06 s (240 frames of 670 slots, the first version): the frame count follows the slots per frame


def build(n=N_FRAMES):
    if os.path.exists(CACHE):
        d = pickle.load(open(CACHE, 'rb'))
        if d['n'] == n:
            return d
    banks, pal, fs, per = encode(n)
    d = dict(stream=banks, audio=audio(n), pal=pal, n=n, fs=fs, per=per)
    pickle.dump(d, open(CACHE, 'wb'))
    return d


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N_FRAMES
    if os.path.exists(CACHE):
        os.remove(CACHE)
    d = build(n)
    print('frames', d['n'], 'frame bytes', d['fs'], 'per bank', d['per'], 'stream banks', len(d['stream']), 'audio banks', len(d['audio']), 'slots', SLOTS)
