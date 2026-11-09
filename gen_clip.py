"""generates turbor/clipplay.inc: the cycle exact reward clip player (Z80 mode, 3.58 MHz), frames packed 4 in 3 banks.
One PCM sample every 224 Z80 cycles (= 16 timer ticks = 62.58 us = 15980.1 Hz); during the video part 9 bytes to the VDP between two samples.
A frame = 3 chunks of 4096 bytes: chunk 0 = pattern[0:4096], chunk 1 = colour[0:4096], chunk 2 = pattern[4096:6144] + colour[4096:6144].
4 frames = 12 chunks = 3 banks of 16 KB (4 chunks each), so a frame has its own code per position in the group (t = 0..3: the banks and offsets are constants).
The video part of a chunk is a subroutine (vA: 4096 bytes, vB: 2048 bytes): the call / ret are accounted in the set-up samples.
Then 32 bytes of palette (from a palette stream of its own, 32 bytes per frame) and the housekeeping samples.
Cycle counts on the MSX in Z80 mode: every opcode byte fetched in an M1 cycle gets one wait state, an I/O instruction one more (measured: OUTI = 19, OUT (n),A = 13)."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
PERIOD = 224
lines = []
CORR = int(os.environ.get('CLIP_CORR', '1'))        # a correction of the period (to tune against the emulator)
BPS = 9                                              # video bytes per sample
RET = 11                                             # ret
RETX = 0                                             # (what the sample after a ret has to count of it)
CALL = 18
LDIXL = 13
LOOPS = {'clip_vA': 56, 'clip_vB': 28}


DBUF = os.environ.get('CLIP_DBUF', '1') != '0'          # double buffering of the tables (R#14 / R#4 / R#10)
PADS = [('nop', 5, 1), ('ld a,(hl)', 8, 1), ('inc sp|dec sp', 14, 2), ('ex (sp),hl|ex (sp),hl', 40, 2)]   # (what, cycles, bytes): ex (sp),hl twice = HL back, 2 bytes for 40 cycles
_PADC = {}


def _padbest(n):
    """the fewest bytes that take exactly n cycles"""
    if n in _PADC:
        return _PADC[n]
    best = None
    if n == 0:
        best = (0, ())
    elif n > 0:
        for i, (w, c, nb) in enumerate(PADS):
            if n >= c:
                r = _padbest(n - c)
                if r is not None and (best is None or r[0] + nb < best[0]):
                    best = (r[0] + nb, (i,) + r[1])
    _PADC[n] = best
    return best


def pad_instrs(n):
    """nops (5), 'ld a,(hl)' (8), inc sp / dec sp pairs (14) and ex (sp),hl pairs (40) that take exactly n cycles with as few bytes as possible"""
    assert n >= 0, n
    r = _padbest(n)
    if r is None:
        raise ValueError('cannot pad %d cycles' % n)
    out = []
    for i in sorted(set(r[1]), reverse=True):
        k = r[1].count(i)
        w = PADS[i][0]
        for _ in range(k):
            for part in w.split('|'):
                out.append('        ' + part)
    return out


def can_pad(n):
    try:
        pad_instrs(n)
        return True
    except (ValueError, AssertionError):
        return False


class Sample:
    """one sample slot: the instructions with their cycle counts, then the padding to PERIOD"""
    def __init__(self, label=None):
        self.ins = []
        self.tail = []
        self.cyc = 0
        self.label = label

    def add(self, text, cycles):
        self.ins.append(text if text.endswith(':') else '        ' + text)
        self.cyc += cycles

    def tailadd(self, text, cycles):
        self.tail.append('        ' + text)
        self.cyc += cycles

    def audio(self):
        self.add('ld a,(de)', 8)
        self.add('inc de', 7)
        self.add('out (0xA4),a', 13)

    def video(self, n=BPS):
        for _ in range(n):
            self.add('outi', 19)

    def emit(self, extra=0, adj=None):
        t = PERIOD + (CORR if adj is None else adj) - self.cyc - extra
        out = []
        if self.label:
            out.append(self.label + ':')
        out += self.ins + pad_instrs(t) + self.tail
        lines.extend(out)


def video_sub(name, nbytes, loops_label):
    """a subroutine: ixl = the number of loops of 8 samples is set by the caller; then whole samples, one with the rest, ret"""
    nfull, rest = divmod(nbytes, BPS)
    loops, inl = divmod(nfull, 8)
    assert loops == LOOPS[name], (loops, name)
    lines.append(name + ':')
    lines.append(loops_label + ':')
    for i in range(7):
        s = Sample(); s.audio(); s.video(); s.emit()
    s = Sample(); s.audio(); s.video()
    s.tailadd('dec ixl', 10)
    s.tailadd('jp nz,%s' % loops_label, 11)
    s.emit()
    for i in range(inl):
        s = Sample(); s.audio(); s.video(); s.emit()
    if rest:
        s = Sample(); s.audio(); s.video(rest)
        s.tailadd('ret', RET)                          # (the ret belongs to the last sample: then the next sample starts clean)
        s.emit()


def setup_sample(label, bank_delta, store, extra, sub, vram_hi, hl_off):
    """a set-up sample: bank (page 1 window), the VRAM address, HL, C = 98h and the call of the video subroutine"""
    s = Sample(label); s.audio()
    s.add('ld hl,(cl_bank)', 17)
    if bank_delta:
        s.add('inc hl', 7)
    s.add('ld a,l', 5)
    s.add('ld (0x6000),a', 14)
    s.add('ld a,h', 5)
    s.add('ld (0x6001),a', 14)
    if store == 'now':
        s.add('ld (cl_bank),hl', 17)
    elif store == 'inc':
        s.add('inc hl', 7)
        s.add('ld (cl_bank),hl', 17)
    s.add('ld hl,0x%04X' % hl_off, 11)
    s.add('xor a', 5)
    s.add('out (0x99),a', 13)
    s.add('ld a,0x%02X' % (0x40 | vram_hi), 8)
    s.add('out (0x99),a', 13)
    s.add('ld c,0x98', 8)
    s.add('ld ixl,%d' % LOOPS[sub], LDIXL)
    s.tailadd('call %s' % sub, CALL)
    s.emit(extra=extra)


def housekeeping(t):
    # H1: the key (SPACE = bit 0 of row 8)
    s = Sample(); s.audio()
    s.add('in a,(0xAA)', 13)
    s.add('and 0xF0', 8)
    s.add('or 8', 8)
    s.add('out (0xAA),a', 13)
    s.add('in a,(0xA9)', 13)
    s.add('and 1', 8)
    s.add('jp z,clip_exit', 11)
    s.emit(adj=4)
    # H2: the audio pointer: D >= B8h: the next bank and DE - 3800h (without a branch)
    s = Sample(); s.audio()
    s.add('ld a,d', 5)
    s.add('cp 0xB8', 8)
    s.add('sbc a,a', 5)
    s.add('cpl', 5)
    s.add('and 0x38', 8)
    s.add('ld b,a', 5)
    s.add('ld a,d', 5)
    s.add('sub b', 5)
    s.add('ld d,a', 5)
    s.add('ld a,b', 5)
    s.add('rlca', 5)
    s.add('rlca', 5)
    s.add('rlca', 5)
    s.add('and 1', 8)
    s.add('ld hl,(au_bank)', 17)
    s.add('ld c,a', 5)
    s.add('ld b,0', 8)
    s.add('add hl,bc', 12)                            # (16 bit bank numbers)
    s.add('ld (au_bank),hl', 17)
    s.add('ld a,(au_end)', 14)                        # the end of the music that plays (the menu song, the puzzle music, ...): HL = the new bank
    s.add('xor l', 5)
    s.add('ld c,a', 5)
    s.add('ld a,(au_end + 1)', 14)
    s.add('xor h', 5)
    s.add('or c', 5)
    s.add('jp nz,clip_aok%d' % t, 11)
    s.add('ld hl,(au_start)', 17)
    s.add('ld (au_bank),hl', 17)
    s.cyc -= 34
    s.add('clip_aok%d:' % t, 0)
    s.emit()
    # H3: the audio bank register and the frame counter
    s = Sample(); s.audio()
    s.add('ld hl,(au_bank)', 17)
    s.add('ld a,l', 5)
    s.add('ld (0x7000),a', 14)
    s.add('ld a,h', 5)
    s.add('ld (0x7001),a', 14)
    s.add('ld hl,(cl_cnt)', 17)
    s.add('dec hl', 7)
    s.add('ld (cl_cnt),hl', 17)
    s.add('ld a,h', 5)
    s.add('or l', 5)
    s.add('jp z,clip_wrap', 11)                      # (the end of the clip: only after a frame of position 3, the count is a multiple of 4)
    if t == 3:
        s.add('clip_after:', 0)
    s.emit(adj=1)


def palette_samples(t, extra):
    """32 bytes of the palette of the frame (palette stream: bank cl_pb, address cl_pp) to port 9Ah from colour 0"""
    s = Sample(); s.audio()
    s.add('ld hl,(cl_pb)', 17)
    s.add('ld a,l', 5)
    s.add('ld (0x6000),a', 14)
    s.add('ld a,h', 5)
    s.add('ld (0x6001),a', 14)
    s.add('ld hl,(cl_pp)', 17)
    s.add('ld c,0x9A', 8)
    s.add('xor a', 5)
    s.add('out (0x99),a', 13)
    s.add('ld a,0x90', 8)
    s.add('out (0x99),a', 13)
    k0 = 0
    for k in (3, 2, 1, 0):
        if can_pad(PERIOD + CORR - (s.cyc + 19 * k) - extra):
            k0 = k
            break
    s.video(k0)
    s.emit(extra=extra)
    left = 32 - k0
    while left:
        k = min(BPS, left)
        s = Sample(); s.audio(); s.video(k); s.emit()
        left -= k
    # the palette pointer on: HL points behind the 32 bytes; on to the next bank at the end of a bank (both paths take the same time)
    s = Sample(); s.audio()
    s.add('ld (cl_pp),hl', 17)
    s.add('ld a,h', 5)
    s.add('cp 0x80', 8)
    s.add('jp z,clip_pw%d' % t, 11)
    wrap = 17 + 7 + 17 + 11 + 17
    x = wrap - 11
    s.ins += pad_instrs(x)
    s.cyc += x
    s.add('jp clip_pj%d' % t, 11)
    s.ins += ['clip_pw%d:' % t, '        ld hl,(cl_pb)', '        inc hl', '        ld (cl_pb),hl', '        ld hl,0x4000', '        ld (cl_pp),hl', 'clip_pj%d:' % t]
    s.emit()


def r14_sample(label, buf):
    s = Sample(label); s.audio()
    s.add('ld a,%d' % buf, 8)
    s.add('out (0x99),a', 13)
    s.add('ld a,0x8E', 8)
    s.add('out (0x99),a', 13)
    s.emit()


def flip_sample(buf):
    """the finished set of tables on the display: R#4 (pattern), R#10 (colour: A16..A14), R#1 (display on)"""
    s = Sample(); s.audio()
    for val, reg in ((0x0B if buf else 0x03, 0x84), (1 if buf else 0, 0x8A), (0x40, 0x81)):
        s.add('ld a,0x%02X' % val, 8)
        s.add('out (0x99),a', 13)
        s.add('ld a,0x%02X' % reg, 8)
        s.add('out (0x99),a', 13)
    s.emit()


def frame(t):
    lab = 'clip_frame' if t == 0 else 'clip_f%d' % t
    buf = 1 if t in (0, 2) else 0                     # the set that this frame is written to
    if DBUF:
        r14_sample(lab, buf)
        lab = None
    n0 = (3 * t) % 4                                  # the offset (in chunks of 4096 bytes) of the first chunk of the frame in its bank
    offs = [0x4000 + 0x1000 * ((n0 + c) % 4) for c in range(3)]
    bank_delta = {0: [0, 0, 0], 1: [0, 1, 1], 2: [0, 0, 1], 3: [0, 0, 0]}[t]
    store = {0: [None, None, None], 1: [None, None, 'now'], 2: [None, None, 'now'], 3: [None, None, 'inc']}[t]
    setup_sample(lab, bank_delta[0], store[0], 0, 'clip_vA', 0x00, offs[0])
    setup_sample(None, bank_delta[1], store[1], RETX, 'clip_vA', 0x20, offs[1])
    setup_sample(None, bank_delta[2], store[2], RETX, 'clip_vB', 0x10, offs[2])
    # the second half of chunk 2: the colour table (HL goes on)
    s = Sample(); s.audio()
    s.add('xor a', 5)
    s.add('out (0x99),a', 13)
    s.add('ld a,0x70', 8)
    s.add('out (0x99),a', 13)
    s.add('ld ixl,%d' % LOOPS['clip_vB'], LDIXL)
    s.tailadd('call clip_vB', CALL)
    s.emit(extra=RETX)
    palette_samples(t, RETX)
    housekeeping(t)
    if DBUF:
        flip_sample(buf)
    if t == 3:
        s = Sample(); s.audio()
        s.add('ld b,11', 8)
        s.add('djnz $', 0)
        s.cyc += 14 * 10 + 9
        s.tailadd('jp clip_frame', 11)
        s.emit()


def gen():
    lines.append('; generated by gen_clip.py: the cycle exact player of the reward clip (Z80 mode), 4 frames in 3 banks')
    for t in range(4):
        frame(t)
    video_sub('clip_vA', 4096, 'clip_va_l')
    video_sub('clip_vB', 2048, 'clip_vb_l')


if __name__ == '__main__':
    gen()
    open(os.path.join(HERE, 'clipplay.inc'), 'w').write('\n'.join(lines) + '\n')
    print('clipplay.inc written:', len(lines), 'lines')
