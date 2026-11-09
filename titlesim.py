"""title video in the letters, SCREEN 5 span update simulation: PSNR (inside the letters) against the number of span slots per frame.
  python turbor/titlesim.py K [nframes]"""
import os, sys, json, subprocess
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(PROJ, 'tools')); sys.path.insert(0, r'F:\MSX Projects\Dev27\msx1-video-player\tools')
import filmsim as S
import title_video as TV
H, W = 192, 256
SRC = os.path.join(PROJ, 'Videos', 'STEF-1.mp4')
STARTS = [min(i * 7, 128 - 7) for i in range(19)]


def frames(n, fps=30.0, start=TV.TITLE_START):
    vf = "crop=w='min(iw,ih*4/3)':h='min(ih,iw*3/4)':x='(iw-out_w)*0.5':y='(ih-out_h)/2',scale=256:192:flags=area,hqdn3d=3:3:8:6,fps=%.5f" % fps
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(start), '-i', SRC, '-frames:v', str(n), '-an', '-vf', vf, '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, H, W, 3)


def grade(fr, sat=1.4, gamma=0.85):
    a = fr.astype(np.float32) / 255
    lum = a.mean(-1)
    lo, hi = np.percentile(lum[::3], 1), np.percentile(lum[::3], 99.5)
    a = np.clip((a - lo) / (hi - lo), 0, 1)
    g = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])[..., None]
    a = np.clip(g + (a - g) * sat, 0, 1) ** gamma
    return a * 255


def global_palette(gr, m):
    import palette_opt as PO
    PO.FIXED = (0,); PO.BRIGHT = ()
    idx = np.linspace(0, len(gr) - 1, 4).astype(int)
    mos = np.zeros((H, W, 3), np.float32)
    for k, f in enumerate(idx):
        mos[(k // 2) * 96:(k // 2) * 96 + 96, (k % 2) * 128:(k % 2) * 128 + 128] = PO.half(gr[f])
    pal, _ = PO.optimise(mos, sweeps=3, log=lambda t: None)
    return np.asarray(PO.snap(pal)).astype(np.float32)


def main():
    K = int(sys.argv[1]); n = int(sys.argv[2]) if len(sys.argv) > 2 else 240
    m = TV.letter_mask()
    gr = grade(frames(n))
    gr = gr * m[None, ..., None]
    pal = global_palette(gr, m)
    nsp = 19
    D = np.zeros((H, W), np.int64)
    ps = []
    shots = []
    for t in range(n):
        q = S.quant(gr[t], pal)
        q[~m] = 0
        eD = ((pal[D] - gr[t]) ** 2).sum(-1); eQ = ((pal[q] - gr[t]) ** 2).sum(-1)
        d = eD - eQ
        ben = np.zeros((H, nsp), np.float32)
        for k, xb in enumerate(STARTS):
            ben[:, k] = d[:, xb * 2:xb * 2 + 14].sum(1)
        flat = ben.ravel(); idx = np.argsort(-flat)[:K]; idx = idx[flat[idx] > 0]
        for i in idx:
            y, k = divmod(int(i), nsp); x0 = STARTS[k] * 2
            D[y, x0:x0 + 14] = q[y, x0:x0 + 14]
        mse = (((pal[D] - gr[t]) ** 2).sum(-1) * m).sum() / (m.sum() * 3)
        ps.append(10 * np.log10(255 ** 2 / max(mse, 1e-9)))
        if t in (n // 4, n // 2, 3 * n // 4, n - 1):
            shots.append(np.concatenate([gr[t], pal[D]], 1))
    print('K=%d: letters %d px (%.0f spans), PSNR %.2f min %.2f' % (K, m.sum(), m.sum() / 14, np.mean(ps), np.min(ps)))
    Image.fromarray(np.concatenate(shots, 0).clip(0, 255).astype(np.uint8)).save(os.path.join(PROJ, 'work', 'titlesim_%d.png' % K))


if __name__ == '__main__':
    main()
