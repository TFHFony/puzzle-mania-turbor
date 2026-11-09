"""builds the milestone 5 ROM: choice screen, memory game, menus + sliding puzzle (SCREEN 11), the reward clip (SCREEN 2, MSX2 palette, PCM) -> PM_turboR_M5.rom
env CLIPFRAMES = frames per clip (default 100; 0 = all)"""
import os, sys, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(PROJ, 'tools'))
import assets3 as A
SJ = r'F:\MSX Projects\Dev27\.claude\msx-video-tools\sjasmplus\sjasmplus-1.24.0.win\sjasmplus.exe'
STRIDE = 14336                                          # audio: every bank holds 16384 samples, the next bank starts 14336 samples later (2048 overlap)


def audio2():
    import music
    RATE = 3579545.0 / 14 / 16
    x = music.decode(os.path.join(PROJ, 'PM-Menu.mp3'), None, 0.0, int(round(RATE)))
    pcm = np.clip(np.round((x * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8)
    n = (len(pcm) + STRIDE - 1) // STRIDE
    ext = np.concatenate([pcm, pcm, pcm])[:n * STRIDE + 2048 + 2048]            # (the loop: the end continues with the beginning)
    return [ext[i * STRIDE:i * STRIDE + A.BANK].tobytes() for i in range(n)]


def chars(a):
    h, w = a.shape
    return a.reshape(h // 8, 8, w).transpose(0, 2, 1).reshape(-1).tobytes()


def clips(nf):
    import palette_opt as PO
    from encode_clips import USED
    pj = PO.load()
    banks, tab, pal = [], [], b''
    for p in range(12):
        c = USED[p]
        d = np.load(os.path.join(PROJ, 'work', os.environ.get('CLIP_PREFIX', '') + 'clip%02d_bytes.npz' % c))
        n = d['pat'].shape[0] if not nf else min(nf, d['pat'].shape[0])
        tab.append((len(banks), n))
        for f in range(n):
            banks.append(A.pad(chars(d['pat'][f]) + chars(d['col'][f]) + (d['pal'][f].tobytes() if 'pal' in d.files else b'')))
        pal += d['pal'][0].tobytes() if 'pal' in d.files else bytes(PO.to_v9938(np.array(pj['photo'][p], np.float32)))
    return banks, tab, pal


def rep(text, old, new):
    assert old in text, old[:60]
    return text.replace(old, new, 1)


def compose():
    m1 = open(os.path.join(HERE, 'm1.asm')).read(); g = open(os.path.join(HERE, 'm3_game.txt')).read()
    c = open(os.path.join(HERE, 'm4_clip.txt')).read()
    c = c[c.index(';;CLIP\n') + 7:c.index(';;ENDCLIP')]
    mm = open(os.path.join(HERE, 'm5_new.txt')).read()
    mm = mm[mm.index(';;MEM\n') + 6:mm.index(';;ENDMEM')]
    g = rep(g, ".solved: bit 0,d\n        jr z,.sizes\n        ld a,(g_n)\n        jp newgame\n", ".solved: bit 0,d\n        jr z,.sizes\n        ld a,(g_sel)\n        jp clip_start\n")
    g = rep(g, 'SOLVED!  SPACE = NEW GAME   ', 'SOLVED!  SPACE = REWARD     ')
    g = rep(g, "        dec a\n        jp z,size_keys\n        bit 2,e                         ; the puzzle: ESC back to the menu\n", "        dec a\n        jp z,size_keys\n        cp 2\n        jp z,choice_keys\n        cp 3\n        jp z,mem_keys\n        bit 2,e                         ; the puzzle: ESC back to the menu\n")
    g = rep(g, "menu_keys:\n        bit 0,d\n        jp nz,size_enter\n", "menu_keys:\n        bit 2,e\n        jp nz,choice_enter\n        bit 0,d\n        jp nz,size_enter\n")
    g = rep(g, "        call menu_enter\n        ld hl,(smp)\n", "        call choice_enter\n        ld hl,(smp)\n")
    g = rep(g, ".loop:  call tick\n", ".loop:  call tick\n        ld a,(g_mode)\n        cp 4\n        call z,mem_tick\n")
    head = m1[:m1.index("main:   ld sp,0xF300")].replace("milestone 1: SCREEN 11 photo, PCM music from a timer-paced scheduler, VDP job queue (HMMM tile swaps), late-sample counter.", "milestone 5: choice screen, memory game, menus, the sliding puzzle and the reward clip.")
    engine = m1[m1.index("; tick: BC, DE, HL are kept."):m1.index("; hmmm: a command entry")]
    engine = rep(engine, "        jp z,.cmd\n        ; 4: wait", "        jp z,.cmd\n        cp 5\n        jp z,.setreg\n        ; 4: wait")
    engine = rep(engine, "setbank: ld hl,(jbank)", ".setreg: ld a,(jt + 1)\n        out (0x99),a\n        ld a,(jt + 2)\n        or 0x80\n        out (0x99),a\n        xor a\n        ld (jt),a\n        ret\nsetbank: ld hl,(jbank)")
    engine = rep(engine, "        ld a,h\n        cp 0xC0\n        jr nz,.ok\n        call au_next\n", "        ld a,h\n        cp 0xB8\n        jr c,.ok\n        call au_next\n")
    a = engine.index("au_next:"); b = engine.index("; vstep: one unit")
    engine = engine[:a] + """au_next: ld de,0x3800                    ; HL - 3800h = the position in the next bank
        or a
        sbc hl,de
        push hl
        ld hl,(au_bank)
        inc hl
        ld de,AUD0 + AUDN
        or a
        sbc hl,de
        add hl,de
        jr c,.s
        ld hl,AUD0
.s:     ld (au_bank),hl
        ld a,l
        ld (0x7000),a
        ld a,h
        ld (0x7001),a
        pop hl
        ret

""" + engine[b:]
    tail = m1[m1.index("; prtstr: HL = string"):].replace('SAVEBIN "m1_bank0.bin"', 'SAVEBIN "m5_bank0.bin"')
    open(os.path.join(HERE, 'm5.asm'), 'w').write(head + g + "\n" + c + "\n" + mm + "\n" + engine + tail)


def main():
    nf = int(os.environ.get('CLIPFRAMES', '100'))
    ph = A.photos(); au = audio2(); cardb, choiceb = A.cards()
    cb, ctab, cpal = clips(nf)
    FULL0 = 1; THUMB0 = FULL0 + 48; LOGOB = THUMB0 + 6; FONTB = LOGOB + 1; CARD0 = FONTB + 1; CHOICEB = CARD0 + 3; AUD0 = CHOICEB + 1; AUDN = len(au); CLIP0 = AUD0 + AUDN
    banks = []
    for full, th in ph:
        b = A.pad(full, 4 * A.BANK)
        banks += [b[i * A.BANK:(i + 1) * A.BANK] for i in range(4)]
    for i in range(6):
        banks.append(A.pad(ph[2 * i][1] + ph[2 * i + 1][1]))
    banks.append(A.pad(A.logo())); banks.append(A.pad(A.font()))
    banks += cardb
    banks.append(choiceb)
    banks += au
    banks += cb
    assert AUD0 + AUDN < 256
    open(os.path.join(HERE, 'm1cfg.inc'), 'w').write('PHOTO0 equ %d\nFULL0 equ %d\nTHUMB0 equ %d\nLOGOB equ %d\nFONTB equ %d\nCARD0 equ %d\nCHOICEB equ %d\nAUD0 equ %d\nAUDN equ %d\n' % (FULL0, FULL0, THUMB0, LOGOB, FONTB, CARD0, CHOICEB, AUD0, AUDN))
    with open(os.path.join(HERE, 'clipdata.inc'), 'w') as f:
        f.write('clip_tab:\n' + ''.join('        dw %d, %d\n' % (CLIP0 + s, n) for s, n in ctab))
        f.write('clip_pal:\n' + ''.join('        db ' + ','.join(str(x) for x in cpal[i * 32:(i + 1) * 32]) + '\n' for i in range(12)))
    subprocess.run([sys.executable, os.path.join(HERE, 'gen_clip.py')], check=True)
    compose()
    r = subprocess.run([SJ, '--nologo', '--sym=m5.sym', 'm5.asm'], cwd=HERE, capture_output=True, text=True)
    print(r.stdout[-500:], r.stderr[-300:])
    if r.returncode != 0:
        sys.exit('assembly failed')
    code = open(os.path.join(HERE, 'm5_bank0.bin'), 'rb').read()
    assert len(code) == A.BANK
    rom = code + b''.join(banks)
    rom += bytes(-len(rom) % (1 << 20))
    out = os.path.join(PROJ, 'PM_turboR_M5.rom')
    open(out, 'wb').write(rom)
    print(out, len(rom) // 1048576, 'MB; banks', len(banks) + 1, 'clip frames', sum(n for _, n in ctab))


if __name__ == '__main__':
    main()
