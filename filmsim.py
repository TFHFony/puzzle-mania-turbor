"""FONY film span-update simulation (SCREEN 5, 16 colours): per frame the K best spans of 14 pixels (7 bytes) are rewritten.
  python turbor/filmsim.py W H K [nframes]   -> prints PSNR of the display vs the source and of the ideal quantised frame, writes work/filmsim_W.png (montage)"""
import os, sys, json, subprocess
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
SRC = r'F:\MSX Projects\Dev27\FONY.mp4'
SPAN = 14
BAY = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) + 0.5) / 16 - 0.5


def frames(W, H, n):
    cmd = ['ffmpeg', '-v', 'error', '-i', SRC, '-frames:v', str(n), '-vf', 'scale=%d:%d:flags=lanczos' % (W, H), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.uint8).reshape(-1, H, W, 3)


def grade(fr, sat=1.25, gamma=0.85):
    a = fr.astype(np.float32) / 255
    lum = a.mean(-1)
    lo, hi = np.percentile(lum[::3], 1), np.percentile(lum[::3], 99.5)
    a = np.clip((a - lo) / (hi - lo), 0, 1)
    g = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])[..., None]
    a = np.clip(g + (a - g) * sat, 0, 1) ** gamma
    return a * 255


def quant(src, pal, amp=26.0):
    H, W, _ = src.shape
    d = BAY[np.arange(H)[:, None] % 4, np.arange(W)[None, :] % 4] * amp
    s = src + d[..., None]
    e = ((s[:, :, None, :] - pal[None, None]) ** 2).sum(-1)
    return e.argmin(-1)


def psnr(a, b):
    m = ((a - b) ** 2).mean()
    return 10 * np.log10(255 ** 2 / max(m, 1e-9))


def main():
    W, H, K = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 240
    pal = np.array(json.load(open(os.path.join(PROJ, 'tools', 'fony_palette.json'))), np.float32)
    gr = grade(frames(W, H, n))
    nsp = (W + SPAN - 1) // SPAN
    starts = [min(i * SPAN, W - SPAN) for i in range(nsp)]
    D = None
    ps_d, ps_q, used = [], [], []
    shots = []
    for t in range(n):
        q = quant(gr[t], pal)
        qi = pal[q]
        if D is None:
            D = np.zeros_like(q)
        di = pal[D]
        eD = ((di - gr[t]) ** 2).sum(-1)
        eQ = ((qi - gr[t]) ** 2).sum(-1)
        ben = np.zeros((H, nsp), np.float32)
        for k, x0 in enumerate(starts):
            ben[:, k] = (eD[:, x0:x0 + SPAN] - eQ[:, x0:x0 + SPAN]).sum(1)
        flat = ben.ravel()
        idx = np.argsort(-flat)[:K]
        idx = idx[flat[idx] > 0]
        for i in idx:
            y, k = divmod(int(i), nsp)
            x0 = starts[k]
            D[y, x0:x0 + SPAN] = q[y, x0:x0 + SPAN]
        used.append(len(idx))
        ps_d.append(psnr(pal[D], gr[t])); ps_q.append(psnr(qi, gr[t]))
        if t in (30, 90, 150, 210):
            shots.append(np.concatenate([gr[t], qi, pal[D]], 1))
    print('%dx%d K=%d: PSNR display %.2f  ideal %.2f  (min %.2f)  slots used avg %.0f' % (W, H, K, np.mean(ps_d), np.mean(ps_q), np.min(ps_d), np.mean(used)))
    Image.fromarray(np.concatenate(shots, 0).clip(0, 255).astype(np.uint8)).resize((W * 3 * 2, H * len(shots) * 2), Image.NEAREST).save(os.path.join(PROJ, 'work', 'filmsim_%d_%d.png' % (W, K)))


if __name__ == '__main__':
    main()
