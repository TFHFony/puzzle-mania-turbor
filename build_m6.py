"""builds the turbo R game (milestone 6: title, help pages, credits, joystick, SELECT + everything of M5) -> PM_turboR_M6.rom
env CLIPFRAMES = frames per clip (default 100; 0 = all)"""
import os, sys, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(PROJ, 'tools'))
import assets3 as A
import build_m5 as B5
rep = B5.rep
SJ = B5.SJ


def part(path, tag, endtag):
    t = open(os.path.join(HERE, path)).read()
    return t[t.index(';;' + tag + '\n') + len(tag) + 3:t.index(';;' + endtag)]


def compose(out_asm='m6.asm', bank0='m6_bank0.bin'):
    m1 = open(os.path.join(HERE, 'm1.asm')).read()
    g = open(os.path.join(HERE, 'm2_game.txt')).read()
    n = open(os.path.join(HERE, 'm3_new.txt')).read()
    # M3: the main loop, the keys and the menus replace the main and the keys of the puzzle
    a = g.index("main:   ld sp,0xF300"); b = g.index("; ---- the commands: HMMM")
    g = g[:a] + n[n.index(";;MAIN\n") + 7:n.index(";;ENDMAIN")] + "\n" + g[b:]
    a = g.index("; ---- the keyboard: the matrix")
    g = g[:a] + n[n.index(";;KEYS\n") + 7:n.index(";;ENDKEYS")] + n[n.index(";;MENU\n") + 7:n.index(";;ENDMENU")]
    c = part('m4_clip.txt', 'CLIP', 'ENDCLIP')
    mm = part('m5_new.txt', 'MEM', 'ENDMEM')
    pg = part('m6_new.txt', 'PAGES', 'ENDPAGES')
    g = rep(g, ".solved: bit 0,d\n        jr z,.sizes\n        ld a,(g_n)\n        jp newgame\n", ".solved: bit 0,d\n        jr z,.sizes\n        ld a,(g_sel)\n        jp clip_start\n")
    g = rep(g, 'SOLVED!  SPACE = NEW GAME   ', 'SOLVED!  SPACE = REWARD     ')
    g = rep(g, "        dec a\n        jp z,size_keys\n        bit 2,e                         ; the puzzle: ESC back to the menu\n",
            "        dec a\n        jp z,size_keys\n        cp 2\n        jp z,choice_keys\n        cp 3\n        jp z,mem_keys\n        cp 4\n        jp z,page_keys\n        cp 5\n        jp z,title_keys\n        bit 2,e                         ; the puzzle: ESC back to the menu\n")
    helpchk = "        ld a,(k_3o)\n        cpl\n        ld b,a\n        ld a,(k_3)\n        and b\n        bit 5,a                         ; H: the help\n        jp nz,help_enter\n"
    g = rep(g, "menu_keys:\n        bit 0,d\n        jp nz,size_enter\n", "menu_keys:\n" + helpchk + "        bit 2,e\n        jp nz,choice_enter\n        bit 0,d\n        jp nz,size_enter\n")
    mm = rep(mm, "choice_keys:                            ; D = new presses row 8\n        bit 0,d\n", "choice_keys:                            ; D = new presses row 8\n" + helpchk + "        bit 2,e\n        jp nz,credits_enter\n        bit 0,d\n")
    g = rep(g, "        call menu_enter\n        ld hl,(smp)\n", "        ld a,(0xFFE8)                   ; R#9: 212 lines, the 50 / 60 Hz bit of the BIOS\n        and 2\n        or 0x80\n        ld (g_r9),a\n        call title_enter\n        ld hl,(smp)\n")
    g = rep(g, ".loop:  call tick\n", ".loop:  call tick\n        ld a,(g_mode)\n        cp 4\n        call z,mem_tick\n")
    # the joystick and SELECT in the key routine
    g = rep(g, "        ld c,7\n        call rdrow\n        ld (k_7),a\n        call tick\n", "        ld c,7\n        call rdrow\n        ld (k_7),a\n        call joymerge\n        call tick\n")
    g = rep(g, "        ld a,(g_mode)\n        or a\n        jp z,menu_keys\n", "        bit 6,e                         ; SELECT: 50 / 60 Hz\n        jr z,.ns\n        push de\n        call toggle_hz\n        pop de\n.ns:    ld a,(g_mode)\n        or a\n        jp z,menu_keys\n")
    # the pages: four of them (3 help pages and the credits)
    pg = rep(pg, "        ld a,(g_pg)\n        or a\n        jr nz,.back\n        ld a,1                          ; help 1 -> help 2\n        jp page_enter\n", "        ld a,(g_pg)\n        cp 2\n        jr nc,.back\n        inc a                           ; the next help page\n        jp page_enter\n")
    pg = rep(pg, "        ld a,2\n        jp page_enter\n\n; ---- the title screen", "        ld a,3\n        jp page_enter\n\n; ---- the title screen")
    head = m1[:m1.index("main:   ld sp,0xF300")].replace("milestone 1: SCREEN 11 photo, PCM music from a timer-paced scheduler, VDP job queue (HMMM tile swaps), late-sample counter.", "the turbo R game.")
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
    tail = m1[m1.index("; prtstr: HL = string"):].replace('SAVEBIN "m1_bank0.bin"', 'SAVEBIN "%s"' % bank0)
    open(os.path.join(HERE, out_asm), 'w').write(head + g + "\n" + c + "\n" + mm + "\n" + pg + "\n" + engine + tail)


def main():
    nf = int(os.environ.get('CLIPFRAMES', '100'))
    ph = A.photos(); au = B5.audio2(); cardb, choiceb = A.cards(); pgs = A.pages()
    cb, ctab, cpal = B5.clips(nf)
    FULL0 = 1; THUMB0 = FULL0 + 48; LOGOB = THUMB0 + 6; FONTB = LOGOB + 1; CARD0 = FONTB + 1; CHOICEB = CARD0 + 3; PAGE0 = CHOICEB + 1; AUD0 = PAGE0 + len(pgs); AUDN = len(au); CLIP0 = AUD0 + AUDN
    banks = []
    for full, th in ph:
        b = A.pad(full, 4 * A.BANK)
        banks += [b[i * A.BANK:(i + 1) * A.BANK] for i in range(4)]
    for i in range(6):
        banks.append(A.pad(ph[2 * i][1] + ph[2 * i + 1][1]))
    banks.append(A.pad(A.logo())); banks.append(A.pad(A.font()))
    banks += cardb
    banks.append(choiceb)
    banks += pgs
    banks += au
    banks += cb
    assert AUD0 + AUDN < 256
    open(os.path.join(HERE, 'm1cfg.inc'), 'w').write('PHOTO0 equ %d\nFULL0 equ %d\nTHUMB0 equ %d\nLOGOB equ %d\nFONTB equ %d\nCARD0 equ %d\nCHOICEB equ %d\nPAGE0 equ %d\nAUD0 equ %d\nAUDN equ %d\n' % (FULL0, FULL0, THUMB0, LOGOB, FONTB, CARD0, CHOICEB, PAGE0, AUD0, AUDN))
    with open(os.path.join(HERE, 'clipdata.inc'), 'w') as f:
        f.write('clip_tab:\n' + ''.join('        dw %d, %d\n' % (CLIP0 + s, n) for s, n in ctab))
        f.write('clip_pal:\n' + ''.join('        db ' + ','.join(str(x) for x in cpal[i * 32:(i + 1) * 32]) + '\n' for i in range(12)))
    subprocess.run([sys.executable, os.path.join(HERE, 'gen_clip.py')], check=True)
    compose()
    r = subprocess.run([SJ, '--nologo', '--sym=m6.sym', 'm6.asm'], cwd=HERE, capture_output=True, text=True)
    print(r.stdout[-500:], r.stderr[-300:])
    if r.returncode != 0:
        sys.exit('assembly failed')
    code = open(os.path.join(HERE, 'm6_bank0.bin'), 'rb').read()
    assert len(code) == A.BANK
    rom = code + b''.join(banks)
    rom += bytes(-len(rom) % (1 << 20))
    out = os.path.join(PROJ, 'PM_turboR_M6.rom')
    open(out, 'wb').write(rom)
    print(out, len(rom) // 1048576, 'MB; banks', len(banks) + 1, 'clip frames', sum(n for _, n in ctab))


if __name__ == '__main__':
    main()
