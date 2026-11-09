"""assets for the turbo R game (milestone 3): the 12 photos as SCREEN 11 (YJK) full pictures (256 x 212) and thumbnails (100 x 72), the logo, the font, the menu music.
Everything is cached in work/turbor/ (the YJK coding takes a while: 8 processes)."""
import os, sys, json, subprocess, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(PROJ, 'tools'))
CACHE = os.path.join(PROJ, 'work', 'turbor'); os.makedirs(CACHE, exist_ok=True)
FW, FH = 256, 212                      # a full picture
TW, TH = 100, 72                       # a thumbnail
BANK = 16384


def clips():
    from encode_clips import CLIPS, USED
    choices = json.load(open(os.path.join(PROJ, 'tools', 'choices.json')))
    return CLIPS, USED, choices


def grab(video, t, w, h):
    vf = "crop=w='min(iw,ih*4/3)':h='min(ih,iw*3/4)':x='(iw-out_w)*0.5':y='(ih-out_h)/2',scale=%d:%d:flags=area" % (w, h)
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.2f' % t, '-i', video, '-frames:v', '1', '-vf', vf, '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(h, w, 3)


def duration(video):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video], capture_output=True, text=True)
    return float(r.stdout)


def still_time(p):
    """the time in the video of the still that the MSX versions use for photo p: the frame that looks most like work/stills/clipNN_k_src.png (cached).
    Candidates: the time the stills were cut at (duration * (k + 0.5) / 8) and the best matches of a search over the whole video; the best match of all wins."""
    f = os.path.join(CACHE, 'times_v3.json')
    T = json.load(open(f)) if os.path.exists(f) else {}
    if str(p) in T:
        return T[str(p)]
    CL, USED, choices = clips()
    c = USED[p]
    video = os.path.join(PROJ, 'Videos', CL[c])
    png = os.path.join(PROJ, 'work', 'stills', 'clip%02d_%d_src.png' % (c, choices[c]))
    ref = np.asarray(Image.open(png).convert('RGB').resize((64, 48), Image.BOX), np.float32)

    def frames(ss, t, fps):
        vf = "crop=w='min(iw,ih*4/3)':h='min(ih,iw*3/4)':x='(iw-out_w)*0.5':y='(ih-out_h)/2',scale=64:48:flags=area,fps=%g" % fps
        r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % ss, '-t', '%.3f' % t, '-i', video, '-vf', vf, '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'], capture_output=True, check=True)
        return np.frombuffer(r.stdout, np.uint8).reshape(-1, 48, 64, 3).astype(np.float32)
    dur = duration(video)
    cands = [dur * (choices[c] + 0.5) / 8]
    fr = frames(0, dur, 8)
    d = np.abs(fr - ref).mean((1, 2, 3))
    for k in np.argsort(d)[:4]:
        cands.append(k / 8.0)
    best = (1e9, 0.0)
    for t in cands:
        t0 = max(0.0, t - 0.2)
        fr2 = frames(t0, 0.5, 30)
        d2 = np.abs(fr2 - ref).mean((1, 2, 3))
        k2 = int(d2.argmin())
        if d2[k2] < best[0]:
            best = (float(d2[k2]), t0 + k2 / 30.0)
    T[str(p)] = [round(best[1], 3), round(best[0], 1)]
    json.dump(T, open(f, 'w'))
    print('still', p, CL[c], 'time %.3f' % best[1], 'diff %.1f' % best[0], flush=True)
    return T[str(p)]


def still_png(p):
    CL, USED, choices = clips()
    c = USED[p]
    return os.path.join(PROJ, 'work', 'stills', 'clip%02d_%d_src.png' % (c, choices[c]))


def photo_job(p):
    """-> (full bytes 54272, thumbnail bytes 7200) of photo p"""
    import yjk
    f = os.path.join(CACHE, 'photo%02d_v4.npz' % p)
    if os.path.exists(f):
        d = np.load(f)
        return d['full'].tobytes(), d['thumb'].tobytes()
    CL, USED, choices = clips()
    c = USED[p]
    video = os.path.join(PROJ, 'Videos', CL[c])
    t, diff = still_time(p)
    if diff > 10:                         # (the video does not hold this still any more: the still of the MSX versions itself)
        im = Image.open(still_png(p)).convert('RGB')
        full = yjk.encode(np.asarray(im.resize((FW, FH), Image.LANCZOS)), 4)
        thumb = yjk.encode(np.asarray(im.resize((TW, TH), Image.LANCZOS)), 4)
    else:
        full = yjk.encode(grab(video, t, FW, FH), 4)
        thumb = yjk.encode(grab(video, t, TW, TH), 4)
    np.savez(f, full=full, thumb=thumb)
    return full.tobytes(), thumb.tobytes()


def full192_job(p):
    """the picture of photo p for the puzzle: 256 x 192 SCREEN 11 bytes (49152 = exactly 3 banks), placed at y = 10 of the 212 lines like the 192 lines of the original"""
    import yjk
    f = os.path.join(CACHE, 'full192_%02d_v1.npy' % p)
    if os.path.exists(f):
        return np.load(f).tobytes()
    CL, USED, choices = clips()
    c = USED[p]
    video = os.path.join(PROJ, 'Videos', CL[c])
    t, diff = still_time(p)
    if diff > 10:
        im = Image.open(still_png(p)).convert('RGB')
        d = yjk.encode(np.asarray(im.resize((256, 192), Image.LANCZOS)), 4)
    else:
        d = yjk.encode(grab(video, t, 256, 192), 4)
    np.save(f, d)
    return d.tobytes()


def fulls192():
    with ProcessPoolExecutor(max_workers=8) as ex:
        return list(ex.map(full192_job, range(12)))


def card_job(p):
    """the card of photo p: 40 x 40 (a centred square), SCREEN 11 bytes (1600)"""
    import yjk
    f = os.path.join(CACHE, 'card%02d_v4.npy' % p)
    if os.path.exists(f):
        return np.load(f).tobytes()
    CL, USED, choices = clips()
    c = USED[p]
    video = os.path.join(PROJ, 'Videos', CL[c])
    t, diff = still_time(p)
    vf = "crop=w='min(iw,ih)':h='min(ih,iw)':x='(iw-out_w)*0.5':y='(ih-out_h)/2',scale=40:40:flags=area"
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.2f' % t, '-i', video, '-frames:v', '1', '-vf', vf, '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'], capture_output=True, check=True)
    img = np.frombuffer(r.stdout, np.uint8).reshape(40, 40, 3)
    if diff > 10:
        im = Image.open(still_png(p)).convert('RGB')
        w, h = im.size
        s = min(w, h)
        img = np.asarray(im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize((40, 40), Image.LANCZOS))
    d = yjk.encode(img, 4)
    np.save(f, d)
    return d.tobytes()


def cards():
    """-> 3 banks: the 12 photo cards (10 + 2), the card back; and the picture of the card back for the choice screen (100 x 72)"""
    with ProcessPoolExecutor(max_workers=8) as ex:
        cs = list(ex.map(card_job, range(12)))
    f = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 30)
    def back(w, h, fs, fw):
        im = Image.new('P', (w, h), 1)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, w - 1, h - 1], fill=15)
        d.rectangle([fw, fw, w - 1 - fw, h - 1 - fw], fill=4)
        ff = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', fs)
        x0, y0, x1, y1 = d.textbbox((0, 0), '?', font=ff)
        d.text(((w - (x1 - x0)) // 2 - x0, (h - (y1 - y0)) // 2 - y0), '?', font=ff, fill=15)
        return pal_bytes(np.asarray(im)).tobytes()
    b0 = pad(b''.join(cs[:10])); b1 = pad(b''.join(cs[10:]))
    b2 = pad(back(40, 40, 36, 4))
    big = pad(back(104, 80, 66, 3))
    return [b0, b1, b2], big


def photos():
    with ProcessPoolExecutor(max_workers=8) as ex:
        return list(ex.map(photo_job, range(12)))


def pal_bytes(idx):
    """palette-pixel bytes (SCREEN 11: A = 1, the palette colour in the high nibble) of an array of colour numbers"""
    return ((np.asarray(idx, np.uint8) << 4) | 0x08).astype(np.uint8)


def logo():
    """256 x 16 (like the original: tile rows 0..1): PUZZLE MANIA in light yellow (11) and XXXL white on red (8) in a box, the same letter size and height; the whole header centred -> bytes"""
    im = Image.new('P', (256, 16), 1)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype('C:/Windows/Fonts/ariblk.ttf', 16)
    t1 = d.textbbox((0, 0), 'PUZZLE MANIA', font=f)
    t2 = d.textbbox((0, 0), 'XXXL', font=f)
    w1, w2 = t1[2] - t1[0], t2[2] - t2[0]
    bw, gap = w2 + 14, 8
    x0 = (256 - (w1 + gap + bw)) // 2
    ytxt = 8 - (t1[1] + t1[3]) // 2                   # the letters of both words vertically centred on the same line (the cap height is the same)
    d.text((x0 - t1[0], ytxt), 'PUZZLE MANIA', font=f, fill=11)
    bx = x0 + w1 + gap
    d.rectangle([bx, 0, bx + bw - 1, 15], fill=8)
    d.text((bx + (bw - w2) // 2 - t2[0], ytxt), 'XXXL', font=f, fill=15)
    a = np.asarray(im)
    a = np.where(a > 15, 1, a)
    return pal_bytes(a).tobytes()


GLYPHS = 63                                         # chars 32..93 and 94 = the copyright sign (the glyphs are indexed by char - 32)
COPY = [0x3C, 0x42, 0x99, 0xA1, 0xA1, 0x99, 0x42, 0x3C]       # (the glyph of the original)


def font():
    """the font of the original: the 8 x 8 font of the MSX BIOS (turbor/biosfont.bin = chars 32..95 of the FS-A1ST firmware) made bold (b | b >> 1) like core.asm boldtext;
    4 sets of 63 glyphs of 8 x 8 palette pixels: set 0 = two-tone (upper four rows grey 14, lower four white 15, like boldtext), 1 = red (8), 2 = yellow (10), 3 = white (15) -> 16128 bytes"""
    raw = open(os.path.join(HERE, 'biosfont.bin'), 'rb').read()
    gl = []
    for c in range(32, 95):
        rows = list(COPY) if c == 94 else list(raw[(c - 32) * 8:(c - 32) * 8 + 8])
        a = np.array([[(b >> (7 - x)) & 1 for x in range(8)] for b in rows], bool)
        a = a | np.concatenate([np.zeros((8, 1), bool), a[:, :-1]], axis=1)
        gl.append(a)
    out = b''
    for mode in ('two', 8, 10, 15):
        for a in gl:
            im = np.full((8, 8), 0x18, np.uint8)
            for r in range(8):
                col = (14 if r < 4 else 15) if mode == 'two' else mode
                im[r, a[r]] = (col << 4) | 8
            out += im.tobytes()
    return out


def arrows():
    """the two arrows (16 x 32): left at 0, right at 512"""
    out = b''
    for left in (True, False):
        im = np.full((32, 16), 0x18, np.uint8)
        for r in range(32):
            t = min(r, 31 - r)
            if left:
                im[r, 15 - t:] = 0xB8
            else:
                im[r, :t + 1] = 0xB8
        out += im.tobytes()
    return out


def mthumb_job(p):
    """the thumbnail of photo p for the photo menu: 104 x 80 SCREEN 11 bytes (8320)"""
    import yjk
    f = os.path.join(CACHE, 'mthumb%02d_v1.npy' % p)
    if os.path.exists(f):
        return np.load(f).tobytes()
    CL, USED, choices = clips()
    c = USED[p]
    video = os.path.join(PROJ, 'Videos', CL[c])
    t, diff = still_time(p)
    if diff > 10:
        im = Image.open(still_png(p)).convert('RGB')
        d = yjk.encode(np.asarray(im.resize((104, 80), Image.LANCZOS)), 4)
    else:
        d = yjk.encode(grab(video, t, 104, 80), 4)
    np.save(f, d)
    return d.tobytes()


def mthumbs():
    with ProcessPoolExecutor(max_workers=8) as ex:
        return list(ex.map(mthumb_job, range(12)))


def audio():
    import music
    RATE = 3579545.0 / 14 / 16
    x = music.decode(os.path.join(PROJ, 'PM-Menu.mp3'), None, 0.0, int(round(RATE)))
    pcm = np.clip(np.round((x * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8)
    n = (len(pcm) + BANK - 1) // BANK
    pcm = np.concatenate([pcm, np.full(n * BANK - len(pcm), 128, np.uint8)])
    return [pcm[i * BANK:(i + 1) * BANK].tobytes() for i in range(n)]


PAGES = {
    'howto1': [
        ('HOW TO PLAY  1/3', 'title'), ('', None),
        ('CHOOSE YOUR PUZZLE', YELLOW := 11),
        ('Cursor left / right and SPACE.', 15), ('SLIDING PUZZLE or MEMORY.', 15), ('', None),
        ('CHOOSE A PHOTO', 11),
        ('Cursor keys + SPACE.  12 photos.', 15),
        ('H = this help,  ESC = credits.', 14), ('', None),
        ('CHOOSE A SIZE', 11),
        ('3x3 (easy) to 6x6 (hard).', 15), ('Cursor keys + SPACE.  ESC = back.', 15), ('', None),
        ('SELECT  = 50 / 60 Hz', 14), ('Joystick port 1 works as well.', 14), ('', None),
        ('SPACE = next page,  ESC = skip', 14)],
    'howto2': [
        ('HOW TO PLAY  2/3', 'title'), ('', None),
        ('SLIDING PUZZLE', 11),
        ('Rebuild the photo.  Only a tile next', 15), ('to the empty square can move.', 15), ('', None),
        ('Cursor keys: the tile next to the gap', 7), ('slides in that direction.', 7), ('', None),
        ('H  hold: look at the solution', 15),
        ('3 4 5 6  new game in that size', 15),
        ('ESC  back to the menu', 15), ('', None),
        ('SPACE after the win = your reward!', 9), ('', None),
        ('SPACE = next page,  ESC = skip', 14)],
    'howto3': [
        ('HOW TO PLAY  3/3', 'title'), ('', None),
        ('MEMORY', 11),
        ('Twenty cards, ten pairs of photos.', 15), ('Move the yellow frame with the', 15), ('cursor keys, SPACE turns a card.', 15), ('', None),
        ('Two the same: they stay face up.', 7), ('Not the same: they turn back, so try', 7), ('to remember where they were.', 7), ('', None),
        ('ESC  back to the choice screen', 15), ('', None),
        ('SPACE after the last pair = your', 9), ('reward: the film of that photo!', 9), ('', None),
        ('SPACE = menu', 14)],
    'credits': [
        ('PUZZLE MANIA XXXL', 'title'), ('', None),
        ('MSXDEV26 ENTRY  -  MSX TURBO R', 7), ('', None),
        ('FREEWARE', 11),
        ('Free to play, copy and share.', 15), ('The full game must stay free of charge.', 15), ('', None),
        ('CODING', 11), ('The File-Hunter  &  Claude', 15), ('', None),
        ('GFX', 11), ('The File-Hunter  &  Tittygram', 15), ('', None),
        ('MUSIC', 11), ('The File-Hunter  &  Solmi AI', 15), ('', None),
        ('THANKS FOR PLAYING!', 9), ('SPACE = back', 14)],
}


def pages():
    """the help pages and the credits as 256 x 212 pictures of palette pixels (4 banks each); the page renderer of the MSX versions (tools/screens.py) with the texts of the turbo R version"""
    import screens as S
    pal = np.asarray(S.PAL, np.float32)
    S.PALETTE_IDX = {}
    out = []
    for name in ('howto1', 'howto2', 'howto3', 'credits'):
        lines = [(t, (S.PAL if False else c)) for t, c in PAGES[name]]
        # (screens.render takes the colour numbers of the TMS palette)
        img = S.render(lines)
        flat = img.reshape(-1, 3).astype(np.float32)
        idx = ((flat[:, None, :] - pal[None]) ** 2).sum(-1).argmin(1).reshape(192, 256).astype(np.uint8)
        canvas = np.ones((212, 256), np.uint8)
        canvas[10:202] = idx
        b = pal_bytes(canvas).tobytes() + bytes(4 * BANK - 212 * 256)
        out += [b[i * BANK:(i + 1) * BANK] for i in range(4)]
    return out


def pad(b, n=BANK):
    assert len(b) <= n, len(b)
    return b + bytes(n - len(b))


if __name__ == '__main__':
    ph = photos()
    print('photos done', len(ph), len(ph[0][0]), len(ph[0][1]))
