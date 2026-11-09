"""turbo R reward clips: full length, 11.62 fps, coded with a V9938 palette (16 of 512 colours) per SCENE.
  python turbor/clipenc.py [clip id ...]      -> work/mq_clipNN_bytes.npz: pat (n,192,32), col (n,192,32), pal (n,32) = the palette of every frame (V9938 bytes)
Every frame carries its palette; the player writes it after the frame, so a scene change changes the palette.
Scenes: cuts found from the difference of small pictures; short scenes are merged. Per scene: k-means + local search on the 3-bit grid (palette_opt) on a mosaic of frames."""
import os, sys, time
import numpy as np
import multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJ, 'tools')); sys.path.insert(0, r'F:\MSX Projects\Dev27\msx1-video-player\tools')
import subprocess
H, W = 192, 256
FPS = 3579545.0 / 14 / 16 / 1375
CUT = float(os.environ.get('CUT', '28'))        # mean abs difference (0..255) of 32x24 pictures that counts as a cut
MINSEG = 12                                      # frames: shorter scenes are merged with the previous one
LOOK = dict(sat=1.4, floor=0.0, contrast=1.15)


def extract(i):
    import encode_clips as E
    src = os.path.join(PROJ, 'Videos', E.CLIPS[i])
    crop = "crop=w='min(iw,ih*4/3)':h='min(ih,iw*3/4)':x='(iw-out_w)*%.3f':y='(ih-out_h)/2',scale=256:192:flags=area,hqdn3d=3:3:8:6" % E.CROPX.get(i, 0.5)
    if E.GRADE.get(i):
        crop += ',' + E.GRADE[i]
    out = os.path.join(PROJ, 'work', 'mq_clip%02d_frames.rgb' % i)
    if not os.path.exists(out):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-an', '-vf', crop + ',fps=%.6f' % FPS, '-pix_fmt', 'rgb24', '-f', 'rawvideo', out], check=True)
    return out, os.path.getsize(out) // (H * W * 3)


def look(a, gamma, lk):
    """gamma, saturation and contrast of the MSX2 photos (palette_opt.adjust) with a gamma fixed for the whole clip"""
    a = a / 255.0
    a = lk['floor'] + (1 - lk['floor']) * a ** gamma
    g = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])[..., None]
    a = np.clip(g + (a - g) * lk['sat'], 0, 1)
    a = np.clip((a - 0.5) * lk['contrast'] + 0.5, 0, 1)
    return a * 255.0


def clip_gamma(fr, n):
    idx = np.linspace(0, n - 1, min(n, 30)).astype(int)
    a = np.asarray(fr[idx], np.float32) / 255
    lum = float((0.3 * a[..., 0] + 0.55 * a[..., 1] + 0.15 * a[..., 2]).mean())
    return min(1.0, max(0.55, np.log(0.45) / np.log(max(lum, 0.05))))


def scenes(fr, n):
    small = np.asarray(fr[:, ::8, ::8].astype(np.float32).mean(-1))          # (n,24,32)
    d = np.abs(np.diff(small, axis=0)).mean((1, 2))
    cuts = [0] + [k + 1 for k in np.nonzero(d > CUT)[0]]
    segs = []
    for c in cuts:
        if segs and c - segs[-1] < MINSEG:
            continue
        segs.append(c)
    return segs


def fit_palette(task):
    """one scene: a palette from a mosaic of 4 half size frames"""
    path, n, i, lk, gamma, a, b = task
    import palette_opt as PO
    PO.FIXED = (0,); PO.BRIGHT = ()
    fr = np.memmap(path, np.uint8, 'r', shape=(n, H, W, 3))
    idx = np.linspace(a, b - 1, 4).astype(int)
    m = np.zeros((H, W, 3), np.float32)
    for k, f in enumerate(idx):
        m[(k // 2) * 96:(k // 2) * 96 + 96, (k % 2) * 128:(k % 2) * 128 + 128] = PO.half(look(np.asarray(fr[f], np.float32), gamma, lk))
    pal, best = PO.optimise(m, sweeps=3, log=lambda t: None)
    return i, np.asarray(PO.snap(pal)).astype(int)


def work(task):
    path, n, start, end, lk, gamma, pal = task
    import msx1_video as V, s4_lab as L
    from scipy.ndimage import gaussian_filter
    pal = np.asarray(pal, np.float32)
    fr = np.memmap(path, np.uint8, 'r', shape=(n, H, W, 3))
    pat_l, col_l = [], []
    prev = None
    for i in range(start, end):
        src = look(np.asarray(fr[i], np.float32), gamma, lk)
        A, B, bits = V.code_rows(src, pal, 0.06)
        ref_blur = L.to_gam(gaussian_filter(L.to_lin(src), (1, 1, 0)))
        if prev is not None:
            e_new = V.tile_err(ref_blur, V.to_img(A, B, bits, pal))
            e_old = V.tile_err(ref_blur, V.to_img(prev[0], prev[1], prev[2], pal))
            keep = e_old <= e_new * 1.4 + 800
            km = np.repeat(keep, 8, 0)
            A = np.where(km, prev[0], A); B = np.where(km, prev[1], B); bits = np.where(km[..., None], prev[2], bits)
        prev = (A, B, bits)
        pat_l.append((bits.astype(np.uint8) << (7 - np.arange(8, dtype=np.uint8))).sum(-1).astype(np.uint8))
        col_l.append(((B << 4) | A).astype(np.uint8))
    return start, np.array(pat_l), np.array(col_l)


def main():
    from palette_opt import to_v9938
    idx = [int(a) for a in sys.argv[1:]]
    import encode_clips as E
    for i in idx or E.USED:
        f = os.path.join(PROJ, 'work', 'mq_clip%02d_bytes.npz' % i)
        if os.path.exists(f):
            continue
        t0 = time.time()
        path, n = extract(i)
        fr = np.memmap(path, np.uint8, 'r', shape=(n, H, W, 3))
        import palette_opt as PO
        lk = PO.LOOK_CLIP.get(i, LOOK)
        gamma = clip_gamma(fr, n)
        segs = scenes(fr, n)
        bounds = segs + [n]
        print('clip', i, n, 'frames', len(segs), 'scenes', segs, 'gamma %.2f' % gamma, flush=True)
        with mp.Pool(8) as pool:
            pals = dict(pool.map(fit_palette, [(path, n, k, lk, gamma, bounds[k], bounds[k + 1]) for k in range(len(segs))]))
            print('  palettes %.0fs' % (time.time() - t0), flush=True)
            tasks = []
            for k in range(len(segs)):
                for s in range(bounds[k], bounds[k + 1], 38):
                    tasks.append((path, n, s, min(bounds[k + 1], s + 38), lk, gamma, pals[k]))
            res = sorted(pool.imap_unordered(work, tasks), key=lambda r: r[0])
        pal_bytes = np.zeros((n, 32), np.uint8)
        for k in range(len(segs)):
            pal_bytes[bounds[k]:bounds[k + 1]] = np.frombuffer(to_v9938(pals[k]), np.uint8)
        np.savez(f, pat=np.concatenate([r[1] for r in res]), col=np.concatenate([r[2] for r in res]), pal=pal_bytes)
        del fr
        os.remove(path)
        print('clip', i, n, 'frames', '%.0fs' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    mp.freeze_support()
    main()
