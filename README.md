# Puzzle Mania XXXL — turbo R version

The **turbo R** version of [Puzzle Mania XXXL](https://github.com/TFHFony/puzzle-mania-msx) (MSXdev26): the same two games, a sliding puzzle (twelve photos, 3×3 up to 6×6) and memory (twenty cards),
but built for the Panasonic FS-A1GT / FS-A1ST: photos, menus and puzzle in **SCREEN 11**, the title video and FONY film in **SCREEN 5**, the reward videos in SCREEN 2 with a palette per scene, and **PCM sound** (8 bit, 15980 Hz) in place of PSG/SCC.
Keyboard only. Freeware. Contains nudity (18+). The manual of the MSX1/2 version applies (same keys and menus).

## Release

The ROM is attached to the [release](../../releases), it is not in the repository: `PuzzleManiaXXXL-Turbo[NEO16].rom`, 128 MB, NEO16 mapper.
openMSX: `openmsx -machine Panasonic_FS-A1ST -cart "PuzzleManiaXXXL-Turbo[NEO16].rom" -romtype NEO-16`

## Build

This repository is meant to live in the folder `turbor/` of a working copy of
[puzzle-mania-msx](https://github.com/TFHFony/puzzle-mania-msx): the build uses its `tools/`, `assets/` and the source media (`Videos/`, `PM.wav`, `PM-Menu.mp3`, not published).

```
git clone https://github.com/TFHFony/puzzle-mania-msx.git
git clone https://github.com/TFHFony/puzzle-mania-turbor.git puzzle-mania-msx/turbor
cd puzzle-mania-msx
python tools/encode_clips.py --fast          # reward videos for the turbo R player (work/fast_clipNN_bytes.npz)
python turbor/clipenc.py                      # palette per scene, packed frames (work/mq_clipNN_bytes.npz)
FILM=1 TITLEVID=1 CLIPFRAMES=0 python turbor/build_m7.py      # -> PM_turboR_M7.rom (128 MB)
```
Needs Python 3 (numpy, scipy, pillow), ffmpeg and [sjasmplus](https://github.com/z00m128/sjasmplus). `clipenc.py` also uses `msx1_video.py` and `s4_lab.py` of
[msx1-video-player](https://github.com/TFHFony/msx1-video-player). The encoders cache their results in `work/` (the first complete build takes hours, a build with warm caches about a minute).
`CLIPFRAMES=60` builds a small development ROM.

## Layout
* `m1.asm` the engine (R800 scheduler: PCM sample every 16 timer ticks, VDP job queue) and `m2_game.txt` … `m7_new.txt`, `m4_clip.txt`, `m8_film.txt` the parts of the game that `build_m5/6/7.py` put together into one program (sjasmplus).
* `assets3.py` photos, thumbnails, cards, logo and font (as SCREEN 11 / YJK data), `yjk.py` the YJK encoder, `photoenc.py` the title photo.
* `gen_clip.py` generator of the cycle-exact reward video player, `clipenc.py` its encoder; `gen_film.py`, `filmenc.py`, `spanenc.py`, `titleenc.py`, `xxxlenc.py` the span-coded films (FONY intro, title video + jigsaw outro, XXXL screen) with `filmsim.py` / `titlesim.py`.

## Credits
Coding The File-Hunter & Claude · GFX The File-Hunter & Tittygram · Music The File-Hunter & Solmi AI
