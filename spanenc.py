"""the encoder side of the span player (turbor/gen_film.py): a frame = GA, GB + groups of 8 records (7 of 14 pixels, 1 of 12), each record = VRAM address lo, hi | 40h, pixel pairs.
Region A = lines 0..127 (R#14 = 0), region B = lines 128.. (R#14 = 1).  A display state D (palette indices) is kept: a record is only worth writing where the target differs.
  frame_bytes(D, q, gr, pal, GA, GB) -> bytes (D updated);  needed(D, q, y0, y1) -> number of 14 pixel spans that differ;  pack(frames) -> 16 KB banks"""
import numpy as np
STARTS = [min(i * 7, 128 - 7) for i in range(19)]      # byte offsets of the spans in a line
BANK = 16384


def pack_px(px):
    px = np.asarray(px)
    return (px[0::2] << 4 | px[1::2]).astype(np.uint8)


def span_gain(D, q, gr, pal, y0, y1):
    """(b7, b6): per line and span the gain (error of the display minus error of the target) of 14 / 12 pixels"""
    eD = ((pal[D[y0:y1]] - gr[y0:y1]) ** 2).sum(-1)
    eQ = ((pal[q[y0:y1]] - gr[y0:y1]) ** 2).sum(-1)
    d = eD - eQ
    h = y1 - y0
    b7 = np.zeros((h, 19), np.float32); b6 = np.zeros((h, 19), np.float32)
    for k, xb in enumerate(STARTS):
        b7[:, k] = d[:, xb * 2:xb * 2 + 14].sum(1)
        b6[:, k] = d[:, xb * 2:xb * 2 + 12].sum(1)
    return b7, b6


def needed(D, q, y0, y1):
    diff = (D[y0:y1] != q[y0:y1])
    n = 0
    for k, xb in enumerate(STARTS):
        n += int(diff[:, xb * 2:xb * 2 + 14].any(1).sum())
    return n


def region_records(D, q, gr, pal, y0, y1, groups):
    b7, b6 = span_gain(D, q, gr, pal, y0, y1)
    h = y1 - y0
    if y0 == 0 and h > 127:
        b7[127, 18] = -1e30            # (a 7 byte span ending at 4000h would carry into R#14: only as a 6 byte span)
    n7 = min(7 * groups, h * 19)
    order = np.argsort(-b7.ravel())[:n7]
    take = np.zeros(h * 19, bool); take[order] = True
    order6 = np.argsort(-np.where(take, -1e30, b6.ravel()))[:groups]
    seven = [(int(i), 7) for i in order]; six = [(int(i), 6) for i in order6]
    seven += [(0, 7)] * (7 * groups - len(seven))      # (a region with fewer spans than slots: rewrite the first span)
    six += [(0, 6)] * (groups - len(six))
    return seven, six


def frame_bytes(D, q, gr, pal, GA, GB, H):
    out = bytearray([GA, GB])
    for (y0, y1, groups) in ((0, min(128, H), GA), (128, H, GB)):
        if groups == 0:
            continue
        seven, six = region_records(D, q, gr, pal, y0, y1, groups)
        for g in range(groups):
            for i, ln in seven[g * 7:(g + 1) * 7] + [six[g]]:
                yl, k = divmod(i, 19)
                y = y0 + yl
                xb = STARTS[k]
                x0 = xb * 2
                sl = slice(x0, x0 + 2 * ln)
                gain = ((pal[D[y, sl]] - gr[y, sl]) ** 2).sum() - ((pal[q[y, sl]] - gr[y, sl]) ** 2).sum()
                if gain > 0:
                    D[y, sl] = q[y, sl]
                a = yl * 128 + xb
                out += bytes([a & 255, 0x40 | (a >> 8)]) + bytes(pack_px(D[y, sl]))
    return bytes(out)


def pack(frames):
    """frames -> banks: a bank holds whole frames, 0xFF marks 'next bank', 0xFE the end"""
    banks = []; cur = bytearray()
    for f in frames:
        assert len(f) < BANK - 1, len(f)
        if len(cur) + len(f) > BANK - 1:
            cur.append(0xFF); banks.append(bytes(cur) + bytes(BANK - len(cur))); cur = bytearray()
        cur += f
    cur.append(0xFE)
    banks.append(bytes(cur) + bytes(BANK - len(cur)))
    return banks
