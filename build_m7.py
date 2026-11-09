"""builds the turbo R game (milestone 7: + attract mode, win jingle, better PCM coding) -> PM_turboR_M7.rom
env CLIPFRAMES = frames per clip (default 100; 0 = all)"""
import os, sys, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(PROJ, 'tools'))
import assets3 as A
import build_m5 as B5
import build_m6 as B6
rep = B5.rep
SJ = B5.SJ
RATE = 3579545.0 / 14 / 16
STRIDE = 14336


def pcm8(x):
    """float -1..1 -> 8 bit unsigned: TPDF dither and first order noise shaping (the quantisation noise goes to the high frequencies)"""
    rng = np.random.default_rng(1)
    d = rng.random(len(x)) - rng.random(len(x))
    s = np.clip(x, -1, 1) * 127.0 + 128.0
    out = np.empty(len(x), np.uint8)
    e = 0.0
    for i in range(len(x)):
        v = s[i] - e
        q = int(round(v + d[i]))
        q = 0 if q < 0 else 255 if q > 255 else q
        e = q - v
        out[i] = q
    return out


def to_banks(pcm):
    n = (len(pcm) + STRIDE - 1) // STRIDE
    ext = np.concatenate([pcm, pcm, pcm])[:n * STRIDE + 4096]
    return [ext[i * STRIDE:i * STRIDE + A.BANK].tobytes() for i in range(n)]


def audio_music():
    import music
    x = music.decode(os.path.join(PROJ, 'PM-Menu.mp3'), None, 0.0, int(round(RATE)))
    return to_banks(pcm8(x * 0.92))


def audio_jingle():
    """the FONY jingle of the disk version (assets/fony_jingle_win.wav) without the silence in front -> banks, number of samples"""
    import subprocess as sp
    r = sp.run(['ffmpeg', '-v', 'error', '-i', os.path.join(PROJ, 'assets', 'fony_jingle_win.wav'), '-ac', '1', '-ar', str(int(round(RATE))), '-f', 'f32le', '-'], capture_output=True, check=True)
    x = np.frombuffer(r.stdout, np.float32).astype(np.float64)
    nz = np.nonzero(np.abs(x) > 0.02 * np.abs(x).max())[0]
    x = x[nz[0]:]
    x = x / np.abs(x).max() * 0.95
    x[-400:] *= np.linspace(1, 0, 400)
    pcm = pcm8(x)
    pcm = np.concatenate([pcm, np.full(300, 128, np.uint8)])
    n = (len(pcm) + STRIDE - 1) // STRIDE
    ext = np.concatenate([pcm, np.full(n * STRIDE + 4096 - len(pcm), 128, np.uint8)])
    return [ext[i * STRIDE:i * STRIDE + A.BANK].tobytes() for i in range(n)], len(pcm)


def audio_puzzle():
    """the puzzle music of the original: PM.wav (173 s, loops), the whole track, 8 bit (cached)"""
    import music
    f = os.path.join(PROJ, 'work', 'turbor', 'pm_pcm8_v1.npy')
    if os.path.exists(f):
        pcm = np.load(f)
    else:
        x = music.decode(os.path.join(PROJ, 'PM.wav'), None, 0.0, int(round(RATE)))
        pcm = pcm8(x * 0.92)
        np.save(f, pcm)
    return to_banks(pcm)


def compose(out_asm='m7.asm', bank0='m7_bank0.bin'):
    B6.compose(out_asm, bank0)
    t = open(os.path.join(HERE, out_asm)).read()
    att = B6.part('m7_new.txt', 'ATT', 'ENDATT')
    # the shuffle: a count of its own and a log of its moves; the attract mode, the keys, the clock
    t = rep(t, "shufmove:\n        ld b,a\n", "shufmove:\n        ld (g_dir),a\n        ld b,a\n")
    t = rep(t, "        ld a,d\n        ld (g_gx),a\n        ld a,e\n        ld (g_gy),a\n        ret\n\ncellidx:", "        ld a,d\n        ld (g_gx),a\n        ld a,e\n        ld (g_gy),a\n        ld a,(g_att)                    ; the move is logged (the attract mode undoes it)\n        or a\n        ret z\n        ld hl,(g_lp)\n        ld a,(g_dir)\n        ld (hl),a\n        inc hl\n        ld (g_lp),hl\n        ret\n\ncellidx:")
    t = rep(t, "        ld hl,s_solved\n        ld e,8\n        ld d,203\n        jp prtstr\n", "        jp win_seq\n")
    t = rep(t, "        ld hl,s_msolved\n        ld e,8\n        ld d,200\n        jp prtstr\n", "        jp win_mem\n")
    t = rep(t, "        ld (hl),1\n        ld a,(m_cur)\n        ld b,1\n        call drawcard\n", "        ld (hl),1\n        ld a,(m_cur)\n        ld e,a\n        ld d,0\n        ld hl,m_seen\n        add hl,de\n        ld (hl),1\n        ld a,(m_cur)\n        ld b,1\n        call drawcard\n")
    t = rep(t, "        call mem_deal\n        ld hl,0\n        ld (m_moves),hl\n", "        call mem_deal\n        ld hl,m_seen\n        ld b,20\n.zs:    ld (hl),0\n        inc hl\n        djnz .zs\n        ld hl,0\n        ld (m_moves),hl\n")
    t = rep(t, "clip_wrap:                              ; the end of the clip: the first frame again\n", "clip_wrap:                              ; the end of the clip: the first frame again (the attract mode: back)\n        ld a,(g_att)\n        or a\n        jr z,.cn\n        ld a,2\n        ld (g_att),a\n        jp clip_exit\n.cn:\n")
    t = rep(t, "        ld a,(g_after)\n        or a\n        jp z,menu_enter\n        jp choice_enter\n", "        ld a,(g_att)\n        or a\n        jr z,.na\n        cp 2\n        jp z,att_after\n        xor a\n        ld (g_att),a\n        ld (g_aph),a\n        ld a,200\n        ld (g_shn),a\n        call att_unmute\n        jp choice_enter\n.na:    ld a,(g_after)\n        or a\n        jp z,menu_enter\n        jp choice_enter\n")
    t = rep(t, "au_next: ld de,0x3800", "au_next: ld de,0x3800")
    t = rep(t, "        ld hl,(au_bank)\n        inc hl\n        ld de,AUD0 + AUDN\n        or a\n        sbc hl,de\n        add hl,de\n        jr c,.s\n        ld hl,AUD0\n", "        ld hl,(au_bank)\n        inc hl\n        ld de,(au_end)\n        or a\n        sbc hl,de\n        add hl,de\n        jr c,.s\n        ld hl,(au_start)\n")
    t = rep(t, "        ld (g_r9),a\n        call title_enter\n", "        ld (g_r9),a\n        ld hl,AUD0\n        ld (au_start),hl\n        ld hl,AUD0 + AUDN\n        ld (au_end),hl\n        ld a,200\n        ld (g_shn),a\n        call title_enter\n")
    t = rep(t, "        call z,mem_tick\n", "        call z,mem_tick\n        ld a,(g_att)\n        or a\n        call nz,att_tick\n")
    t = rep(t, "        ld (g_snext),hl\n        ld a,(g_mode)\n        cp 2\n        jr nz,.loop\n", "        ld (g_snext),hl\n        ld a,(g_mode)\n        cp 2\n        jr nz,.loop\n")
    t = rep(t, "        bit 6,e                         ; SELECT: 50 / 60 Hz\n", "        ld a,d                          ; any key at all (the cursor keys, SPACE, ESC, the joystick, or one of the keyboard rows): in the attract mode it stops it, else it counts for the song\n        or e\n        jr nz,.xk\n        call anykey\n        jr z,.xb\n.xk:    ld a,(g_att)\n        or a\n        jp nz,att_stop\n        ld a,1\n        ld (g_act),a\n.xb:    push de\n        call att_check\n        pop de\n    bit 6,e                         ; SELECT: 50 / 60 Hz\n")
    t = t.replace("\nclip_wrap:", "\n" + att + "\nclip_wrap:", 1) if False else t.replace("; ---- the title screen", att + "\n; ---- the title screen", 1)
    for dead in ('s_hud:', 's_solved:', 's_msolved:'):
        k = t.index(dead)
        t = t[:k] + t[t.index(chr(10), k) + 1:]
    if os.environ.get('FILM') or os.environ.get('TITLEVID'):
        film = B6.part('m8_film.txt', 'FILM', 'ENDFILM')
        call = ('        call film_play\n' if os.environ.get('FILM') else '') + ('        call tv_play\n' if os.environ.get('TITLEVID') else '')
        t = rep(t, "        ld (g_shn),a\n        call title_enter\n", "        ld (g_shn),a\n" + call + ("" if os.environ.get('TITLEVID') else "        call title_enter\n"))
        t = t.replace("\nclip_wrap:", "\n" + film + "\nclip_wrap:", 1)
    if os.environ.get('CLIP_DBUF', '1') == '0':
        t = t.replace('s2regs: db 0x02, 0x00,', 's2regs: db 0x02, 0x40,', 1)
    if os.environ.get('TITLEVID'):                       # (the title screen with the photo is not used any more)
        a = t.index('title_enter:' + chr(10) + '        ld a,6')
        e = t.index('title_keys:', a)
        t = t[:a] + t[e:]
    open(os.path.join(HERE, out_asm), 'w').write(t)


def clips_packed(nf):
    """the clips: 4 frames in 3 banks (chunks of 4096 bytes: pattern 0..4095 | colour 0..4095 | pattern 4096.. + colour 4096..) and a palette stream (32 bytes per frame)"""
    import palette_opt as PO
    from encode_clips import USED
    pre = os.environ.get('CLIP_PREFIX', 'mq_')
    banks, tab, ptab, pal = [], [], [], b''
    for p in range(12):
        fn = os.path.join(PROJ, 'work', pre + 'clip%02d_bytes.npz' % USED[p])
        if not os.path.exists(fn) and os.environ.get('CLIP_FALLBACK'):
            fn = os.path.join(PROJ, 'work', pre + 'clip00_bytes.npz')       # (test builds: a clip that is not encoded yet)
        d = np.load(fn)
        n = d['pat'].shape[0] if not nf else min(nf, d['pat'].shape[0])
        n -= n % 4
        tab.append((len(banks), n))
        chunks = []
        for f in range(n):
            fr = B5.chars(d['pat'][f]) + B5.chars(d['col'][f])
            chunks += [fr[0:4096], fr[6144:10240], fr[4096:6144] + fr[10240:12288]]
        for g in range(0, len(chunks), 12):
            blob = b''.join(chunks[g:g + 12])
            banks += [blob[i * A.BANK:(i + 1) * A.BANK] for i in range(3)]
        ptab.append(len(banks))
        ps = d['pal'][:n].tobytes()
        for i in range(0, len(ps), A.BANK):
            banks.append(A.pad(ps[i:i + A.BANK]))
        pal += d['pal'][0].tobytes()
    return banks, tab, ptab, pal


def main():
    nf = int(os.environ.get('CLIPFRAMES', '100'))
    ph = A.photos(); jb, jn = audio_jingle(); cardb, choiceb = A.cards(); pgs = A.pages()
    cb, ctab, cptab, cpal = clips_packed(nf)
    FULL0 = 1; THUMB0 = FULL0 + 36; MTHUMB0 = THUMB0 + 6; LOGOB = MTHUMB0 + 12; FONTB = LOGOB + 1; CARD0 = FONTB + 1; CHOICEB = CARD0 + 3; PAGE0 = CHOICEB + 1; JING0 = PAGE0 + len(pgs); CLIP0 = JING0 + len(jb)
    banks = []
    for full in A.fulls192():
        banks += [A.pad(full, 3 * A.BANK)[k * A.BANK:(k + 1) * A.BANK] for k in range(3)]
    for i in range(6):
        banks.append(A.pad(ph[2 * i][1] + ph[2 * i + 1][1]))
    for mt in A.mthumbs():
        banks.append(A.pad(mt))
    banks.append(A.pad(A.logo() + A.arrows())); banks.append(A.pad(A.font()))
    banks += cardb
    banks.append(choiceb)
    banks += pgs
    banks += jb
    banks += cb
    FILM = bool(os.environ.get('FILM')); TVID = bool(os.environ.get('TITLEVID'))
    extra = ''
    inc = 'film_pal:\n        db 0' + ',0' * 31 + '\ntv_pal:\n        db 0' + ',0' * 31 + '\n'
    nxt = CLIP0 + len(cb)
    if FILM or TVID:
        sys.path.insert(0, HERE)
    if FILM:
        import filmenc as FE
        fd = FE.build()
        FILM0 = nxt; banks += fd['stream']
        FILMA0 = FILM0 + len(fd['stream']); banks += fd['audio']
        nxt = FILMA0 + len(fd['audio'])
        extra += 'FILM0 equ %d\nFILMA0 equ %d\n' % (FILM0, FILMA0)
        inc = inc.replace('film_pal:\n        db 0' + ',0' * 31, 'film_pal:\n        db ' + ','.join(str(x) for x in fd['pal']))
    if TVID:
        import titleenc as TE
        td = TE.build()
        TV0 = nxt; banks += td['stream']
        tv_audio = list(td['audio'])
        TVA0 = TV0 + len(td['stream']); banks += tv_audio
        nxt = TVA0 + len(tv_audio)
        import xxxlenc as XE
        assert FILM, 'the dreun of XXXL is the end of the film audio'
        XXXL0 = TVA0 + len(tv_audio); banks += XE.picture()
        nxt = XXXL0 + 4
        need = fd['n'] * FE.SLOTS                                                   # the samples of the film audio
        idx = int(round(XE.BOOM_T0 * need / 10.0267))                               # the dreun = the film audio from 5.95 s of the FONY sound to its end (no banks of its own)
        extra += 'TV0 equ %d\nTVA0 equ %d\nXXXL0 equ %d\nBOOMB equ %d\nBOOMO equ %d\nBOOMLEN equ %d\nFILMAN equ %d\n' % (TV0, TVA0, XXXL0, FILMA0 + idx // 14336, idx % 14336, need - idx, len(fd['audio']))
        inc = inc.replace('tv_pal:\n        db 0' + ',0' * 31, 'tv_pal:\n        db ' + ','.join(str(x) for x in td['pal']))
    if TVID:
        AUDN = -(-td['nvideo'] * (8 * TE.G_VIDEO + TE.OVER) // STRIDE)
        SILB = TVA0 + AUDN                                               # (the first bank behind the music is silence: no bank of its own; the LAST bank holds a copy of the start of the music)
        assert SILB < TVA0 + len(tv_audio) - 1
    else:
        SILB = nxt; banks.append(bytes([128]) * A.BANK); nxt += 1
    PUZ0 = nxt; pz = audio_puzzle(); banks += pz
    extra += 'PUZ0 equ %d\nPUZN equ %d\n' % (PUZ0, len(pz))
    if not FILM:
        extra += 'FILM0 equ 0\nFILMA0 equ 0\n'
    if not TVID:
        extra += 'TV0 equ 0\nTVA0 equ 0\nBOOMB equ 0\nBOOMO equ 0\nBOOMLEN equ 0\nFILMAN equ 0\nXXXL0 equ 0\n'
    if FILM or TVID:
        open(os.path.join(HERE, 'filmdata.inc'), 'w').write(inc)
        subprocess.run([sys.executable, os.path.join(HERE, 'gen_film.py')], check=True)
    assert TVID, 'the menu song lives in the title audio banks'
    AUD0 = TVA0                                                                   # the menu song = the first banks of the title audio (the music, then its silent tail)
    AUDN = -(-td['nvideo'] * (8 * TE.G_VIDEO + TE.OVER) // STRIDE)
    open(os.path.join(HERE, 'm1cfg.inc'), 'w').write('PHOTO0 equ %d\nFULL0 equ %d\nTHUMB0 equ %d\nMTHUMB0 equ %d\nLOGOB equ %d\nFONTB equ %d\nCARD0 equ %d\nCHOICEB equ %d\nPAGE0 equ %d\nJING0 equ %d\nJINGN equ %d\nJINGLEN equ %d\nSILB equ %d\nAUD0 equ %d\nAUDN equ %d\n' % (FULL0, FULL0, THUMB0, MTHUMB0, LOGOB, FONTB, CARD0, CHOICEB, PAGE0, JING0, len(jb), jn, SILB, AUD0, AUDN) + extra)
    with open(os.path.join(HERE, 'clipdata.inc'), 'w') as f:
        f.write('clip_tab:\n' + ''.join('        dw %d, %d\n' % (CLIP0 + s, n) for s, n in ctab))
        f.write('clip_ptab:\n' + ''.join('        dw %d\n' % (CLIP0 + s) for s in cptab))
    subprocess.run([sys.executable, os.path.join(HERE, 'gen_clip.py')], check=True)
    compose()
    r = subprocess.run([SJ, '--nologo', '--sym=m7.sym', 'm7.asm'], cwd=HERE, capture_output=True, text=True)
    print(r.stdout[-500:], r.stderr[-300:])
    if r.returncode != 0:
        sys.exit('assembly failed')
    code = open(os.path.join(HERE, 'm7_bank0.bin'), 'rb').read()
    assert len(code) == A.BANK
    rom = code + b''.join(banks)
    rom += bytes(-len(rom) % (1 << 20))
    out = os.path.join(PROJ, 'PM_turboR_M7.rom')
    open(out, 'wb').write(rom)
    print(out, len(rom) // 1048576, 'MB; banks', len(banks) + 1, 'clip frames', sum(n for _, n in ctab), 'jingle samples', jn)


if __name__ == '__main__':
    main()
