"""title video in the letters (SCREEN 5, 16 colours of the MSX2 palette) + the jigsaw outro, as one span stream for turbor/gen_film.py.
  python turbor/titleenc.py   -> work/title_enc.pkl: dict(stream=banks, audio=banks, pal=32 bytes V9938, nvideo, nframes, seconds)
The video frames come at the rate of the player (RATE / SLOTS) and last exactly as long as the music (PM-Menu.mp3); then the picture grows out of the letters, is cut into jigsaw
pieces that fall (tools/jigsaw.py Scene) -- those frames have the time step they need (the groups per frame are chosen so that the changes fit)."""
import os, sys, pickle, math, time
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(PROJ, 'tools')); sys.path.insert(0, r'F:\MSX Projects\Dev27\msx1-video-player\tools')
import titlesim as TS
import filmsim as S
import spanenc as SE
import title_video as TV
H, W = 192, 256
RATE = 3579545.0 / 14 / 16
G_VIDEO = 56                                     # groups per video frame: 56 * 8 + 6 = 454 slots = 35.2 fps: four frames fill a bank (16136 of 16383 bytes)
OVER = 6                                         # samples of a frame outside the groups
GMIN, GMAX = 40, 200
CACHE = os.path.join(PROJ, 'work', 'title_enc.pkl')
T_HOLD0, T_REVEAL, T_HOLD1, T_CUT, T_END = 0.4, 0.7, 0.5, 0.3, 0.4


def music_pcm():
    import music
    return music.decode(os.path.join(PROJ, 'PM-Menu.mp3'), None, 0.0, int(round(RATE)))


def region_groups(m):
    """GA / GB of a video frame: the groups follow the number of spans of the letters in the lines 0..127 and 128..191"""
    cnt = []
    for y0, y1 in ((0, 128), (128, H)):
        n = 0
        for xb in SE.STARTS:
            n += int(m[y0:y1, xb * 2:xb * 2 + 14].any(1).sum())
        cnt.append(n)
    ga = int(round(G_VIDEO * cnt[0] / (cnt[0] + cnt[1])))
    return ga, G_VIDEO - ga


def palette(gr, last, m):
    import palette_opt as PO
    PO.FIXED = (0,); PO.BRIGHT = ()
    idx = np.linspace(0, len(gr) - 1, 12).astype(int)
    mos = np.zeros((H, W, 3), np.float32)
    tiles = [PO.half(gr[i]) for i in idx] + [PO.half(last)] * 4
    for k, t in enumerate(tiles):
        mos[(k // 4) * 48:(k // 4) * 48 + 48, (k % 4) * 64:(k % 4) * 64 + 64] = t[::2, ::2] if t.shape[0] > 48 else t
    pal, _ = PO.optimise(mos, sweeps=3, log=lambda t: None)
    return np.asarray(PO.snap(pal)).astype(np.float32)


def encode():
    import build_m7 as B7
    from palette_opt import to_v9938
    import jigsaw as J
    m = TV.letter_mask()
    x = music_pcm()
    S_slots = 8 * G_VIDEO + OVER
    n_video = int(round(len(x) / S_slots))
    fps = RATE / S_slots
    print('music %.2f s, %d samples; frame %d slots = %.3f fps; %d video frames' % (len(x) / RATE, len(x), S_slots, fps, n_video), flush=True)
    raw = TS.frames(n_video, fps)
    assert len(raw) >= n_video, len(raw)
    raw = raw[:n_video]
    gr = TS.grade(raw)                              # graded, full picture
    grm = gr * m[None, ..., None]
    pal = palette(grm, gr[-1], m)
    GA, GB = region_groups(m)
    print('palette done; GA/GB', GA, GB, flush=True)
    D = np.zeros((H, W), np.int64)
    frames = []
    t0 = time.time()
    for t in range(n_video):
        q = S.quant(grm[t], pal); q[~m] = 0
        frames.append(SE.frame_bytes(D, q, grm[t], pal, GA, GB, H))
    print('video frames coded %.0fs' % (time.time() - t0), flush=True)
    # the outro
    photo = np.clip(gr[-1], 0, 255).astype(np.uint8)
    sc = J.Scene(photo, m)
    tfall = J.fall_length(sc.pcs)
    t_cut = T_HOLD0 + T_REVEAL + T_HOLD1
    t_end = t_cut + T_CUT + tfall + T_END

    def target(t):
        if t < T_HOLD0:
            img, vis = sc.reveal(0.0)
        elif t < T_HOLD0 + T_REVEAL:
            img, vis = sc.reveal((t - T_HOLD0) / T_REVEAL)
        elif t < t_cut:
            img, vis = sc.reveal(1.0)
        elif t < t_cut + T_CUT:
            img, vis = sc.cut()
        elif t < t_cut + T_CUT + tfall:
            img, vis = sc.fall(t - t_cut - T_CUT)
        else:
            img, vis = np.zeros((H, W, 3), np.uint8), np.zeros((H, W), bool)
        return np.asarray(img, np.float32), vis

    t = 0.0
    slots_out = 0
    first = True
    while t < t_end:
        g = GMIN
        for it in range(4):
            tn = t + (8 * g + OVER) / RATE
            img, vis = target(tn)
            q = S.quant(img, pal); q[~vis] = 0
            nA = SE.needed(D, q, 0, 128); nB = SE.needed(D, q, 128, H)
            ga = max(1, math.ceil(nA / 8)); gb = max(1, math.ceil(nB / 8))
            g2 = min(GMAX, max(GMIN, ga + gb))
            if g2 == g:
                break
            g = g2
        if ga + gb > GMAX:
            ga = max(1, int(GMAX * ga / (ga + gb))); gb = GMAX - ga
        elif ga + gb < g:
            ga += g - ga - gb
        tn = t + (8 * (ga + gb) + OVER) / RATE
        frames.append(SE.frame_bytes(D, q, img, pal, ga, gb, H))
        slots_out += 8 * (ga + gb) + OVER
        t = tn
        if len(frames) % 20 == 0:
            print('  outro t=%.2f g=%d' % (t, ga + gb), flush=True)
    banks = SE.pack(frames)
    total_slots = n_video * S_slots + slots_out + 4000
    n = (total_slots + B7.STRIDE - 1) // B7.STRIDE + 1
    pcm_x = np.concatenate([x[:n_video * S_slots], np.zeros(max(0, n_video * S_slots - len(x))), np.zeros(slots_out + 4000)])
    abanks = B7.to_banks(B7.pcm8(np.clip(pcm_x * 0.92, -1, 1)))
    return dict(stream=banks, audio=abanks, pal=bytes(to_v9938(pal)), nvideo=n_video, nframes=len(frames), seconds=(n_video * S_slots + slots_out) / RATE)


def build():
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, 'rb'))
    d = encode()
    pickle.dump(d, open(CACHE, 'wb'))
    return d


if __name__ == '__main__':
    if os.path.exists(CACHE):
        os.remove(CACHE)
    d = build()
    print('frames', d['nframes'], 'video', d['nvideo'], 'stream banks', len(d['stream']), 'audio banks', len(d['audio']), 'seconds %.1f' % d['seconds'])
