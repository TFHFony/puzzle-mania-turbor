; PUZZLE MANIA turbo R - milestone 1: SCREEN 11 photo, PCM music from a timer-paced scheduler, VDP job queue (HMMM tile swaps), late-sample counter.
; The cartridge (NEO16): bank 0 = this code (page 1), photo banks, audio banks, font bank (generated: m1cfg.inc). The engine runs from the RAM of page 3 in R800 DRAM mode.
        DEVICE NOSLOT64K
        ORG 0x4000
        db "AB"
        dw init
        dw 0,0,0,0,0,0
        db "ROM_NE16"
        ORG 0x4020
        INCLUDE "m1cfg.inc"             ; PHOTO0, AUD0, AUDN, FONTB

; ---- variables (RAM page 3)
tgt     equ 0xC000                      ; the time (timer, low byte) of the next sample
au_ptr  equ 0xC001                      ; the audio read pointer (window of page 2)
au_bank equ 0xC003                      ; the audio bank in that window
maxl    equ 0xC005                      ; the largest lateness of a sample (timer ticks)
latec   equ 0xC006                      ; the number of late samples (lateness >= 2 ticks)
smp     equ 0xC008                      ; the number of samples played (wraps)
q_head  equ 0xC00A
q_tail  equ 0xC00B
jt      equ 0xC00C                      ; the running job: 16 bytes, +0 type (0 none, 1 stream, 2 rect, 3 command, 4 wait for the command)
jbank   equ jt + 1                      ; +1 bank (page 1 window), +3 source, +5 length (rect: width, height), +7 R#14, +8 address low, +9 address high | 40h
jsrc    equ jt + 3
jlen    equ jt + 5
jr14    equ jt + 7
jal     equ jt + 8
jah     equ jt + 9
jphase  equ 0xC01C
j_h     equ 0xC01D
j_rw    equ 0xC01E
j_ptr   equ 0xC01F
j_cnt   equ 0xC021
q_buf   equ 0xC030                      ; 8 entries of 16 bytes
t_next  equ 0xC0B0                      ; the sample count of the next tile swap / HUD refresh
h_next  equ 0xC0B2
t_step  equ 0xC0B4
t_pair  equ 0xC0B5
e_buf   equ 0xC0C0                      ; a queue entry under construction (16 bytes)
d_buf   equ 0xC0D0                      ; decimal digits
RAMBASE equ 0xC100

init:   di
        ld sp,0xF380
        xor a
        ld (0x6000),a                   ; page 1 window = bank 0
        ld (0x6001),a
        call 0x0138                     ; RSLREG: page 2 = our slot as well (as in the game)
        rrca
        rrca
        and 3
        ld c,a
        ld b,0
        ld hl,0xFCC1
        add hl,bc
        ld a,(hl)
        and 0x80
        jr z,.ne
        or c
        ld c,a
        inc hl
        inc hl
        inc hl
        inc hl
        ld a,(hl)
        and 0x0C
        or c
        ld c,a
.ne:    ld a,c
        ld h,0x80
        call 0x0024                     ; ENASLT
        di
        ld a,(0x002D)                   ; MSX version byte of the main ROM: 3 = turbo R
        cp 3
        jp c,not_tr
        ld a,0x82                       ; R800 DRAM mode
        call 0x0180                     ; CHGCPU
        di
        ld a,8
        call 0x005F                     ; CHGMOD: SCREEN 8, then the YJK bits
        di
        ld hl,vdpregs                   ; the VDP registers of SCREEN 11, written here instead of trusting what the BIOS left (it leaves the display blanked)
        ld b,vdpregs_end - vdpregs
        ld c,0x80
.vr:    ld a,(hl)
        out (0x99),a
        ld a,c
        out (0x99),a
        inc hl
        inc c
        djnz .vr
        ld a,(0xFFE8)                   ; R#9: 212 lines, the 50 / 60 Hz bit as the BIOS has it
        and 0x02
        or 0x80
        out (0x99),a
        ld a,0x89
        out (0x99),a
        ld hl,vdpregs2
        ld b,5
.v2:    ld a,(hl)
        out (0x99),a
        inc hl
        ld a,(hl)
        out (0x99),a
        inc hl
        djnz .v2
        xor a                           ; the palette (colours 0..15 for the palette pixels of SCREEN 11)
        out (0x99),a
        ld a,0x90
        out (0x99),a
        ld hl,pal16
        ld bc,0x209A
        otir
        ld hl,ram_image
        ld de,RAMBASE
        ld bc,ram_end - ram_start
        ldir
        jp RAMBASE

vdpregs: db 0x0E                        ; R#0: M5 M4 M3 = 1 1 1 (SCREEN 8 / 10 / 11 / 12)
        db 0x40                         ; R#1: display on, no interrupt, 8x8 sprites
        db 0x1F                         ; R#2: page 0
        db 0, 0, 0, 0                   ; R#3..R#6 (not used in a bitmap mode)
        db 0x01                         ; R#7: the border: black
        db 0x0A                         ; R#8: 64K chips (VR), sprites off
vdpregs_end:
pal16:  db 0x00, 0x00                   ; 0 black (transparent)
        db 0x00, 0x00                   ; 1 black
        db 0x11, 0x05                   ; 2 medium green
        db 0x33, 0x06                   ; 3 light green
        db 0x27, 0x02                   ; 4 dark blue
        db 0x37, 0x03                   ; 5 light blue
        db 0x25, 0x02                   ; 6 dark red
        db 0x27, 0x06                   ; 7 cyan
        db 0x72, 0x02                   ; 8 medium red
        db 0x73, 0x03                   ; 9 light red
        db 0x62, 0x06                   ; 10 dark yellow
        db 0x63, 0x06                   ; 11 light yellow
        db 0x14, 0x01                   ; 12 dark green
        db 0x65, 0x02                   ; 13 magenta
        db 0x55, 0x05                   ; 14 grey
        db 0x77, 0x07                   ; 15 white
vdpregs2: db 0x00, 0x92                  ; R#18 = 0: no display adjust
        db 0x00, 0x97                   ; R#23 = 0: no vertical scroll
        db 0x18, 0x99                   ; R#25 = 18h: YJK + YAE = SCREEN 11
        db 0x00, 0x9A                   ; R#26 = 0
        db 0x00, 0x9B                   ; R#27 = 0

not_tr: ld a,0
        call 0x005F
        ld hl,m_nt
.p:     ld a,(hl)
        or a
        jr z,.h
        call 0x00A2
        inc hl
        jr .p
.h:     jr .h
m_nt:   db "Wanna see HQ XXXL b(.)(.)bies?",13,10,"Get an MSX Turbo-R",0

ram_image:
        PHASE RAMBASE
ram_start:
main:   ld sp,0xF300
        ld hl,0xC000                    ; variables and queue start at 0
        ld de,0xC001
        ld bc,0x00FF
        ld (hl),0
        ldir
        ld hl,AUD0                      ; the audio: bank AUD0 in the window of page 2
        ld (au_bank),hl
        ld a,l
        ld (0x7000),a
        ld a,h
        ld (0x7001),a
        ld hl,0x8000
        ld (au_ptr),hl
        in a,(0xE6)
        ld (tgt),a
        ; the photo: 4 stream jobs
        ld b,4
        ld hl,PHOTO0
        ld (e_buf + 1),hl
        ld hl,0                         ; VRAM address of the part
        ld (v_a),hl
        xor a
        ld (v_r),a
.ph:    push bc
        ld a,1
        ld (e_buf),a
        ld hl,0x4000
        ld (e_buf + 3),hl
        ld hl,16384
        ld (e_buf + 5),hl
        ld a,(v_r)                      ; the address: part * 16384
        ld (e_buf + 7),a
        xor a
        ld (e_buf + 8),a
        ld a,0x40
        ld (e_buf + 9),a
        ld hl,e_buf
        call q_put
        ld hl,(e_buf + 1)
        inc hl
        ld (e_buf + 1),hl
        ld a,(v_r)
        inc a
        ld (v_r),a
        pop bc
        djnz .ph
        call wait_idle
        ld hl,2000
        ld (t_next),hl
        ld hl,8000
        ld (h_next),hl
.loop:  call tick
        ld hl,(smp)
        ld de,(h_next)
        or a
        sbc hl,de
        bit 7,h
        jr nz,.nh
        call hud
        ld hl,(h_next)
        ld de,8000
        add hl,de
        ld (h_next),hl
.nh:    ld hl,(smp)
        ld de,(t_next)
        or a
        sbc hl,de
        bit 7,h
        jr nz,.loop
        call tileswap
        ld hl,(t_next)
        ld de,3000
        add hl,de
        ld (t_next),hl
        jr .loop

v_a:    dw 0
v_r:    db 0

; ================================================================================================ the scheduler
; tick: BC, DE, HL are kept.  Loops until the foreground may run: the sample (at the exact time: 16 timer ticks = 62.58 us = 15980 Hz), then units of the job queue (each at most two VDP
; accesses) while there are 8 ticks or more to spare; the foreground only gets control when at least 5 ticks (19 us) are left: it must not stay away longer than that.
tick:   exx
.t:     in a,(0xE6)
        ld hl,tgt
        sub (hl)
        cp 128
        jr c,.due
        neg                             ; A = ticks until the next sample
        cp 5
        jr c,.t                         ; (too little time for the foreground: wait for the sample)
        cp 8
        jr c,.ret
        ld c,a
        ld a,(jt)                       ; a job unit?
        or a
        jr nz,.u
        ld a,(q_head)
        ld hl,q_tail
        cp (hl)
        jr z,.ret                       ; nothing to do: the foreground
.u:     call vstep
        jr .t
.ret:   exx
        ret
.due:   ld c,a                          ; lateness in ticks
        cp 64
        jr c,.ok0
        in a,(0xE6)                     ; (far too late: no catching up in a burst: start again from now)
        ld (tgt),a
.ok0:   ld hl,(au_ptr)
        ld a,(hl)
        out (0xA4),a
        inc hl
        ld a,h
        cp 0xC0
        jr nz,.ok
        call au_next
.ok:    ld (au_ptr),hl
        ld hl,tgt
        ld a,(hl)
        add a,16
        ld (hl),a
        ld hl,(smp)
        inc hl
        ld (smp),hl
        ld a,(maxl)
        cp c
        jr nc,.m
        ld a,c
        ld (maxl),a
.m:     ld a,c
        cp 3
        jr c,.t
        ld hl,(latec)
        inc hl
        ld (latec),hl
        jr .t

au_next: ld hl,(au_bank)
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
        ld hl,0x8000
        ret

; vstep: one unit of the job queue: at most two accesses to the VDP (the setup of an address or a command is split in two units)
vstep:  ld a,(jt)
        or a
        jr nz,.go
        ld a,(q_head)                   ; load the next job
        ld hl,q_tail
        cp (hl)
        ret z
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,q_buf
        add hl,de
        ld de,jt
        ld bc,16
        ldir
        ld a,(q_head)
        inc a
        and 7
        ld (q_head),a
        xor a
        ld (jphase),a
        ld (j_rw),a
        ld hl,(jsrc)
        ld (j_ptr),hl
        ld hl,(jlen)
        ld (j_cnt),hl
        ld a,(jt)
        cp 2
        jr nz,.n2
        ld a,(jlen + 1)
        ld (j_h),a
.n2:    ld a,(jt)
        cp 3
        ret nz
        ld hl,jt + 1                    ; command: the 15 registers are in the entry (the 16th byte goes to R#47, which is not used)
        ld (j_ptr),hl
        ld hl,16
        ld (j_cnt),hl
        ret
.go:    cp 1
        jp z,.stream
        cp 2
        jp z,.rect
        cp 3
        jp z,.cmd
        ; 4: wait until the command is done: select status register 2, read it until bit 0 is clear, select status register 0 again
        ld a,(jphase)
        or a
        jr nz,.w1
        ld a,2
        out (0x99),a
        ld a,0x8F
        out (0x99),a
        ld a,1
        ld (jphase),a
        ret
.w1:    dec a
        jr nz,.w2
        in a,(0x99)
        rra
        ret c
        ld a,2
        ld (jphase),a
        ret
.w2:    xor a
        out (0x99),a
        ld a,0x8F
        out (0x99),a
        xor a
        ld (jt),a
        ret
.stream: ld a,(jphase)
        or a
        jr z,.s0
        dec a
        jr z,.s1
        ld hl,(j_ptr)
        ld c,0x98
        outi
        outi
        ld (j_ptr),hl
        ld hl,(j_cnt)
        dec hl
        dec hl
        ld (j_cnt),hl
        ld a,h
        or l
        ret nz
        xor a
        ld (jt),a
        ret
.s0:    call setbank
        ld a,(jr14)
        out (0x99),a
        ld a,0x8E
        out (0x99),a
        ld a,1
        ld (jphase),a
        ret
.s1:    ld a,(jal)
        out (0x99),a
        ld a,(jah)
        out (0x99),a
        ld a,2
        ld (jphase),a
        ret
.rect:  ld a,(jphase)
        or a
        jr z,.r0
        dec a
        jr z,.r1
        ld hl,(j_ptr)
        ld c,0x98
        outi
        outi
        ld (j_ptr),hl
        ld a,(j_rw)
        sub 2
        ld (j_rw),a
        ret nz
        ld a,(j_h)                      ; a row is done: the next one, or the end
        or a
        jr nz,.rn
        xor a
        ld (jt),a
        ret
.rn:    xor a
        ld (jphase),a
        ret
.r0:    call setbank
        ld a,(jr14)
        out (0x99),a
        ld a,0x8E
        out (0x99),a
        ld a,1
        ld (jphase),a
        ret
.r1:    ld a,(jal)
        out (0x99),a
        ld a,(jah)
        out (0x99),a
        ld a,(jlen)
        ld (j_rw),a
        ld a,(jah)                      ; the next row: + 256
        inc a
        cp 0x80
        jr nz,.ra
        ld a,0x40
        ld hl,jr14
        inc (hl)
.ra:    ld (jah),a
        ld hl,j_h
        dec (hl)
        ld a,2
        ld (jphase),a
        ret
.cmd:   ld a,(jphase)
        or a
        jr nz,.cd
        ld a,32                         ; R#17 = 32: auto increment from R#32
        out (0x99),a
        ld a,0x91
        out (0x99),a
        ld a,1
        ld (jphase),a
        ret
.cd:    ld hl,(j_ptr)
        ld c,0x9B
        outi
        outi
        ld (j_ptr),hl
        ld hl,(j_cnt)
        dec hl
        dec hl
        ld (j_cnt),hl
        ld a,h
        or l
        ret nz
        xor a
        ld (jt),a
        ret
setbank: ld hl,(jbank)
        ld a,l
        ld (0x6000),a
        ld a,h
        ld (0x6001),a
        ret

; ================================================================================================ foreground helpers
q_put:  ld a,(q_head)                   ; HL = a 16 byte entry -> the queue (ticks until there is room)
        ld b,a
        ld a,(q_tail)
        inc a
        and 7
        cp b
        jr nz,.ok
        call tick
        jr q_put

.ok:    call tick                       ; (the copy below must not make the sample late)
        ld a,(q_tail)
        ex de,hl
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,q_buf
        add hl,bc
        ex de,hl
        ld bc,16
        ldir
        ld a,(q_tail)
        inc a
        and 7
        ld (q_tail),a
        ret

wait_idle:
.w:     call tick
        ld a,(jt)
        or a
        jr nz,.w
        ld a,(q_head)
        ld hl,q_tail
        cp (hl)
        jr nz,.w
        ret

; address of pixel (x = E, y = D): -> e_buf + 7..9
setpix: ld a,d                          ; address = y * 256 + x: R#14 = y >> 6, high = (y & 63) | 40h, low = x
        rlca
        rlca
        and 3
        ld (e_buf + 7),a
        ld a,d
        and 63
        or 0x40
        ld (e_buf + 9),a
        ld a,e
        ld (e_buf + 8),a
        ret

; hmmm: a command entry: SX, SY, DX, DY (words in hm_sx ...), 80 x 60
hmmm:   call tick
        ld a,3
        ld (e_buf),a
        ld hl,(hm_sx)
        ld (e_buf + 1),hl
        ld hl,(hm_sy)
        ld (e_buf + 3),hl
        call tick
        ld hl,(hm_dx)
        ld (e_buf + 5),hl
        ld hl,(hm_dy)
        ld (e_buf + 7),hl
        ld hl,80
        ld (e_buf + 9),hl
        ld hl,60
        ld (e_buf + 11),hl
        xor a
        ld (e_buf + 13),a
        ld (e_buf + 14),a
        ld (e_buf + 15),a
        ld a,0xD0                       ; HMMM
        ld (e_buf + 15),a
        ld hl,e_buf                     ; (byte 15 = the command register; bytes 13, 14 = CLR, ARG)
        call q_put
        ld a,4                          ; and wait for it
        ld (e_buf),a
        ld hl,e_buf
        jp q_put
hm_sx:  dw 0
hm_sy:  dw 0
hm_dx:  dw 0
hm_dy:  dw 0

; ================================================================================================ the demo: three commands per swap of two tiles (through a scratch area in page 1 of the VRAM)
tileswap:
        ld a,(t_pair)                   ; the pair: tile a (0..7) with tile a + 1, in the order of the grid
        ld c,a
        inc a
        cp 8
        jr c,.p
        xor a
.p:     ld (t_pair),a
        ld a,c
        call tick
        call tilexy                     ; HL = x, DE = y of tile a -> (ta_x, ta_y)
        ld (ta_x),hl
        ld (ta_y),de
        ld a,c
        inc a
        call tick
        call tilexy
        ld (tb_x),hl
        ld (tb_y),de
        ld hl,(ta_x)                    ; A -> scratch
        ld (hm_sx),hl
        ld hl,(ta_y)
        ld (hm_sy),hl
        ld hl,0
        ld (hm_dx),hl
        ld hl,256
        ld (hm_dy),hl
        call tick
        call hmmm
        ld hl,(tb_x)                    ; B -> A
        ld (hm_sx),hl
        ld hl,(tb_y)
        ld (hm_sy),hl
        ld hl,(ta_x)
        ld (hm_dx),hl
        ld hl,(ta_y)
        ld (hm_dy),hl
        call tick
        call hmmm
        ld hl,0                         ; scratch -> B
        ld (hm_sx),hl
        ld hl,256
        ld (hm_sy),hl
        ld hl,(tb_x)
        ld (hm_dx),hl
        ld hl,(tb_y)
        ld (hm_dy),hl
        call tick
        jp hmmm
ta_x:   dw 0
ta_y:   dw 0
tb_x:   dw 0
tb_y:   dw 0
; tile number A (0..8) -> HL = x, DE = y: the grid of 3 x 3 tiles of 80 x 60 pixels at (8, 16)
tilexy: ld b,0
.r:     cp 3
        jr c,.c
        sub 3
        inc b
        jr .r
.c:     add a,a
        ld e,a
        ld d,0
        ld hl,x_tab
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        push de
        ld a,b
        add a,a
        ld e,a
        ld d,0
        ld hl,y_tab
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        pop hl
        ret
x_tab:  dw 8, 88, 168
y_tab:  dw 16, 76, 136

; ================================================================================================ the HUD: LATE n MAX m (text drawn glyph by glyph by rect jobs)
hud:    ld hl,s_late
        ld e,8                          ; x = 8
        ld d,200                        ; y = 200
        call prtstr
        push de
        ld hl,(latec)
        call dec5
        pop de
        ld hl,d_buf
        call prtstr
        ld hl,s_max
        call prtstr
        push de
        ld a,(maxl)
        ld l,a
        ld h,0
        call dec5
        pop de
        ld hl,d_buf + 2
        jp prtstr
s_late: db "LATE ",0
s_max:  db " MAX ",0

; prtstr: HL = string, (E, D) = x, y of the first glyph; E, D advance by 8 pixels per character
prtstr: call tick
        ld a,(hl)
        or a
        ret z
        push hl
        sub 32
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl                       ; * 64
        ld bc,0x4000
        add hl,bc
        ld bc,(pf_off)
        add hl,bc
        ld (e_buf + 3),hl
        call tick
        ld a,2
        ld (e_buf),a
        ld hl,FONTB
        ld (e_buf + 1),hl
        ld hl,0x0808                    ; w = 8, h = 8
        ld (e_buf + 5),hl
        push de
        call setpix
        call tick
        ld hl,e_buf
        call q_put
        pop de
        ld a,e
        add a,8
        ld e,a
        pop hl
        inc hl
        jr prtstr

; dec5: HL -> d_buf: five decimal digits (ASCII) and a zero
dec5:   ld de,d_buf
        ld bc,10000
        call .d
        ld bc,1000
        call .d
        ld bc,100
        call .d
        ld bc,10
        call .d
        ld a,l
        add a,'0'
        ld (de),a
        inc de
        xor a
        ld (de),a
        ret

.d:     call tick                       ; (a long loop: the sample clock goes on)
        ld a,'0' - 1
.s:     inc a
        or a
        sbc hl,bc
        jr nc,.s
        add hl,bc
        ld (de),a
        inc de
        ret
ram_end:
        DEPHASE
ram_image_end:
        ds 0x8000 - $, 0xFF
        SAVEBIN "m1_bank0.bin", 0x4000, 0x4000
