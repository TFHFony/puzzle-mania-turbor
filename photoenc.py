"""the photo variant of the title: the letters PUZZLE MANIA filled with a still (the photo of clip WELCOME_PHOTO), SCREEN 5, for the length of the music, then the jigsaw outro.
  python turbor/photoenc.py   -> work/photo_enc.pkl: dict(stream=banks, pal=32 bytes V9938, total_slots, seconds)
The picture is drawn in two or three frames of up to 200 groups; then idle frames (one byte 0FDh in the stream = a frame of 4 sample slots: only the key / audio housekeeping) until the music
is over; the outro is the one of the video variant (titleenc.py), on this photo.  The sound is the audio of the title video (music, then silence)."""
import os, sys, pickle, math
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(PROJ, 'tools')); sys.path.insert(0, r'F:\MSX Projects\Dev27\msx1-video-player\tools')
import titlesim as TS
import filmsim as S
import spanenc as SE
import titleenc as TE
import title_video as TV
import assets3 as A
H, W = TE.H, TE.W
RATE = TE.RATE
OVER, GMIN, GMAX = TE.OVER, TE.GMIN, TE.GMAX
WELCOME_PHOTO = 7                                # the clip whose still fills the letters (the original: tools/build_game.py WELCOME_PHOTO)
IDLE = 4                                         # slots of an idle frame
CACHE = os.path.join(PROJ, 'work', 'photo_enc.pkl')


def still():
    CL, USED, choices = A.clips()
    png = os.path.join(PROJ, 'work', 'stills', 'clip%02d_%d_src.png' % (WELCOME_PHOTO, choices[WELCOME_PHOTO]))
    im = Image.open(png).convert('RGB').resize((W, H), Image.LANCZOS)
    return np.asarray(im)


def encode():
    import build_m7 as B7
    from palette_opt import to_v9938
    import jigsaw as J
    m = TV.letter_mask()
    x = TE.music_pcm()
    gr = TS.grade(still()[None])[0]
    grm = gr * m[..., None]
    import palette_opt as PO                    # the palette of the photo of the MSX2 version (palette_opt.json): the picture is nothing but that photo
    CL, USED, _ = A.clips()
    pal = np.asarray(PO.snap(np.array(PO.load()['photo'][USED.index(WELCOME_PHOTO)], np.float32))).astype(np.float32)
    D = np.zeros((H, W), np.int64)
    frames = []
    slots = 0
    q = S.quant(grm, pal); q[~m] = 0
    while True:                                  # the picture
        nA = SE.needed(D, q, 0, 128); nB = SE.needed(D, q, 128, H)
        if nA + nB == 0:
            break
        ga = min(GMAX // 2, max(1, math.ceil(nA / 8))); gb = min(GMAX // 2, max(1, math.ceil(nB / 8)))
        frames.append(SE.frame_bytes(D, q, grm, pal, ga, gb, H))
        slots += 8 * (ga + gb) + OVER
    print('picture: %d frames, %d slots' % (len(frames), slots), flush=True)
    n_idle = (len(x) - slots) // IDLE            # until the music is over
    frames += [bytes([0xFD])] * n_idle
    slots += n_idle * IDLE
    print('idle frames %d, music %.2f s' % (n_idle, len(x) / RATE), flush=True)
    sc = J.Scene(np.clip(gr, 0, 255).astype(np.uint8), m)
    tfall = J.fall_length(sc.pcs)
    t_cut = TE.T_HOLD0 + TE.T_REVEAL + TE.T_HOLD1
    t_end = t_cut + TE.T_CUT + tfall + TE.T_END

    def target(t):
        if t < TE.T_HOLD0:
            img, vis = sc.reveal(0.0)
        elif t < TE.T_HOLD0 + TE.T_REVEAL:
            img, vis = sc.reveal((t - TE.T_HOLD0) / TE.T_REVEAL)
        elif t < t_cut:
            img, vis = sc.reveal(1.0)
        elif t < t_cut + TE.T_CUT:
            img, vis = sc.cut()
        elif t < t_cut + TE.T_CUT + tfall:
            img, vis = sc.fall(t - t_cut - TE.T_CUT)
        else:
            img, vis = np.zeros((H, W, 3), np.uint8), np.zeros((H, W), bool)
        return np.asarray(img, np.float32), vis

    t = 0.0
    slots_out = 0
    while t < t_end:
        g = GMIN
        for it in range(4):
            tn = t + (8 * g + OVER) / RATE
            img, vis = target(tn)
            q2 = S.quant(img, pal); q2[~vis] = 0
            nA = SE.needed(D, q2, 0, 128); nB = SE.needed(D, q2, 128, H)
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
        frames.append(SE.frame_bytes(D, q2, img, pal, ga, gb, H))
        slots_out += 8 * (ga + gb) + OVER
        t = tn
        if len(frames) % 40 == 0:
            print('  outro t=%.2f g=%d' % (t, ga + gb), flush=True)
    banks = SE.pack(frames)
    return dict(stream=banks, pal=bytes(to_v9938(pal)), total_slots=slots + slots_out + 4000, seconds=(slots + slots_out) / RATE)


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
    print('stream banks', len(d['stream']), 'seconds %.1f' % d['seconds'], 'slots', d['total_slots'])
