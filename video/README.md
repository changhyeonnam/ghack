# Demo video toolkit

Everything that turns the screen recording into the submission video is code, so it can be edited and rebuilt.

| Folder | What it makes | Command |
|---|---|---|
| `motion/` | Motion-graphics scenes (intro, how it works, benchmark, outro) as HTML animated by time, rendered frame by frame | `node motion/render.mjs <scene> --d <seconds>` (see `motion/README.md`) |
| `captions/` | English captions from the narration timeline: an `.srt` for YouTube and PNG overlays for burned-in subtitles (no libass needed) | `python3 captions/make_captions.py TIMELINE.json` then `python3 captions/burn_in.py IN.mp4 OUT.mp4` |
| `audio/` | Royalty-free background music synthesised with numpy, mixed under the narration with ducking and normalised to -14 LUFS | `python3 audio/make_bgm.py SECONDS` then `audio/mix_bgm.sh IN.mp4 bgm.wav OUT.mp4` |

Order used for the submission cut: splice the motion scenes into the recording (matching each scene's length to its
narration clip), mix the music, then burn in the captions. Edit on-screen text in `motion/scenes/*.html` and caption
text in `captions/captions.json`.
