"""the XXXL screen (after the jigsaw outro): the letters XXXL as high as the screen, filled with the photo of the Oops clip (clip 6), black around them, SCREEN 11 (YJK);
the sound is the end of the FONY film (the 'dreun', from 5.95 s).
  build() -> dict(pic=[4 banks], boom=[banks], boomlen=samples)"""
import os, sys, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(PROJ, 'tools')); sys.path.insert(0, r'F:\MSX Projects\Dev27\msx1-video-player\tools')
import assets3 as A
PHOTO_CLIP = 6
BOOM_T0 = 5.95
RATE = 3579545.0 / 14 / 16


def letters_mask(word='XXXL', box=(6, 6, 250, 206), gap=45):
    font = ImageFont.truetype(r'C:\Windows\Fonts\impact.ttf', 400)
    full = []
    for ch in word:
        g = Image.new('L', (800, 700), 0)
        ImageDraw.Draw(g).text((50, 20), ch, font=font, fill=255)
        full.append(g)
    ytop = min(g.getbbox()[1] for g in full); ybot = max(g.getbbox()[3] for g in full)
    glyphs = [g.crop((g.getbbox()[0], ytop, g.getbbox()[2], ybot)) for g in full]
    big = Image.new('L', (sum(g.width for g in glyphs) + gap * (len(glyphs) - 1), ybot - ytop), 0)
    x = 0
    for g in glyphs:
        big.paste(g, (x, 0)); x += g.width + gap
    mask = Image.new('L', (256, 212), 0)
    mask.paste(big.resize((box[2] - box[0], box[3] - box[1]), Image.LANCZOS), (box[0], box[1]))
    return np.asarray(mask) >= 128


def picture():
    import yjk
    CL, USED, choices = A.clips()
    p = USED.index(PHOTO_CLIP)
    im = Image.open(A.still_png(p)).convert('RGB').resize((256, 212), Image.LANCZOS)
    img = np.zeros((212, 256, 3), np.uint8)
    m = letters_mask()
    img[m] = np.asarray(im)[m]
    full = yjk.encode(img, 4).tobytes()
    b = A.pad(full, 4 * A.BANK)
    return [b[i * A.BANK:(i + 1) * A.BANK] for i in range(4)]


def boom():
    import build_m7 as B7
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(BOOM_T0), '-i', r'F:\MSX Projects\Dev27\FONY.mp4', '-vn', '-ac', '1', '-ar', str(int(round(RATE))), '-f', 'f32le', '-'], capture_output=True, check=True)
    x = np.frombuffer(r.stdout, np.float32).astype(np.float64)
    x = x / np.abs(x).max() * 0.95
    x[-300:] *= np.linspace(1, 0, 300)
    pcm = np.concatenate([B7.pcm8(x), np.full(300, 128, np.uint8)])
    n = (len(pcm) + B7.STRIDE - 1) // B7.STRIDE
    ext = np.concatenate([pcm, np.full(n * B7.STRIDE + 4096 - len(pcm), 128, np.uint8)])
    return [ext[i * B7.STRIDE:i * B7.STRIDE + A.BANK].tobytes() for i in range(n)], len(pcm)


def build():
    b, n = boom()
    return dict(pic=picture(), boom=b, boomlen=n)


if __name__ == '__main__':
    d = build()
    print('pic banks', len(d['pic']), 'boom banks', len(d['boom']), 'samples', d['boomlen'])
