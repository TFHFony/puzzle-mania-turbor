"""YJK encoder for the V9958 (turbo R): SCREEN 12 (5-bit Y) and SCREEN 11 (4-bit Y + attribute bit).
A group of four horizontal pixels shares J and K (6 bit signed); every pixel has its own Y.
 R = Y + J, G = Y + K, B = (5 Y - 2 J - K) / 4   (all in 0..31 units, clamped)
Byte layout: SCREEN 12: Y(5) << 3 | c(3);  SCREEN 11: Y(4) << 4 | A << 3 | c(3);
 c of the four bytes of a group: K low 3 bits, K high 3 bits, J low 3 bits, J high 3 bits.
usage: encode(img (h, w, 3) uint8, ybits=4) -> bytes (h * w), decode(bytes, w, h, ybits) -> img"""
import numpy as np

W_ERR = np.array([2.0, 4.0, 1.0], np.float32)         # R, G, B weights of the error (the eye is most sensitive to green)


def _to_units(img):
    return np.asarray(img, np.float32) / 255.0 * 31.0


def _render(Y, J, K):
    R = np.clip(Y + J, 0, 31)
    G = np.clip(Y + K, 0, 31)
    B = np.clip((5 * Y - 2 * J - K) / 4.0, 0, 31)
    return R, G, B


def encode(img, ybits=4, search=3):
    h, w, _ = img.shape
    assert w % 4 == 0
    s = _to_units(img)
    R, G, B = (s[..., i].reshape(h, w // 4, 4) for i in range(3))
    step = 2 ** (5 - ybits)
    cand = np.arange(0, 32, step, dtype=np.float32)               # the Y values that exist
    Y0 = np.clip(B / 2 + R / 4 + G / 8, 0, 31)
    J0 = np.round((R - Y0).mean(-1)); K0 = np.round((G - Y0).mean(-1))
    bestJ = np.zeros((h, w // 4), np.int16); bestK = np.zeros((h, w // 4), np.int16)
    bestY = np.zeros((h, w // 4, 4), np.float32); bestE = np.full((h, w // 4), 1e30, np.float32)
    for dj in range(-search, search + 1):
        for dk in range(-search, search + 1):
            J = np.clip(J0 + dj, -32, 31); K = np.clip(K0 + dk, -32, 31)
            Jb, Kb = J[..., None, None], K[..., None, None]
            Rr, Gr, Br = _render(cand, Jb, Kb)                      # (h, g, 1, n)
            e = W_ERR[0] * (Rr - R[..., None]) ** 2 + W_ERR[1] * (Gr - G[..., None]) ** 2 + W_ERR[2] * (Br - B[..., None]) ** 2
            yi = e.argmin(-1)
            ee = np.take_along_axis(e, yi[..., None], -1)[..., 0].sum(-1)
            m = ee < bestE
            bestE = np.where(m, ee, bestE); bestJ = np.where(m, J, bestJ).astype(np.int16); bestK = np.where(m, K, bestK).astype(np.int16)
            bestY = np.where(m[..., None], cand[yi], bestY)
    return pack(bestY, bestJ, bestK, ybits, h, w)


def pack(Y, J, K, ybits, h, w):
    Ji = (J.astype(np.int16) & 63).astype(np.uint8); Ki = (K.astype(np.int16) & 63).astype(np.uint8)
    low = np.stack([Ki & 7, Ki >> 3, Ji & 7, Ji >> 3], -1)         # (h, g, 4)
    yv = (Y / (2 ** (5 - ybits))).astype(np.uint8)
    if ybits == 5:
        out = (yv << 3) | low
    else:
        out = (yv << 4) | low                                       # the attribute bit (3) stays 0: a YJK pixel
    return out.reshape(h, w).astype(np.uint8)


def decode(data, ybits=4):
    h, w = data.shape
    g = data.reshape(h, w // 4, 4)
    low = g & 7
    Kv = (low[..., 0] | (low[..., 1] << 3)).astype(np.int16); Jv = (low[..., 2] | (low[..., 3] << 3)).astype(np.int16)
    Kv = np.where(Kv > 31, Kv - 64, Kv); Jv = np.where(Jv > 31, Jv - 64, Jv)
    Y = (g >> (8 - ybits)).astype(np.float32) * (2 ** (5 - ybits)) if ybits == 5 else (g >> 4).astype(np.float32) * 2
    if ybits == 5:
        Y = (g >> 3).astype(np.float32)
    R, G, B = _render(Y, Jv[..., None].astype(np.float32), Kv[..., None].astype(np.float32))
    return (np.stack([R, G, B], -1).reshape(h, w, 3) / 31 * 255).astype(np.uint8)


if __name__ == '__main__':
    import sys, subprocess
    from PIL import Image
    video, sec = sys.argv[1], sys.argv[2]
    W, H = 256, 212
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', sec, '-i', video, '-frames:v', '1', '-vf', 'crop=w=ih*%d/%d:h=ih,scale=%d:%d:flags=area' % (W, H, W, H), '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'], capture_output=True, check=True)
    src = np.frombuffer(r.stdout, np.uint8).reshape(H, W, 3)
    for yb in (5, 4):
        d = encode(src, yb)
        out = decode(d, yb)
        mse = ((out.astype(float) - src) ** 2).mean()
        print('ybits', yb, 'PSNR %.2f dB' % (10 * np.log10(255 * 255 / mse)))
        Image.fromarray(np.concatenate([src, out], 1)).resize((W * 4, H * 2), Image.NEAREST).save(sys.argv[3] % yb)
