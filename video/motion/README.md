# LedgerLens motion graphics

Code-driven motion graphics for the demo video. Each scene is one self-contained HTML page
(no network, system fonts). It exposes `window.renderAt(t)`, which is a pure function of time,
and `window.SCENE.duration`. `render.mjs` steps through every frame at 30 fps, takes a screenshot
of each one and encodes them with ffmpeg. The same inputs always give the same video.

## Scenes

| Scene | Default | What it shows |
|---|---|---|
| `intro` | 18 s | "Southeast Asia's small businesses run the economy." Then counters for 8.8% (Vietnam SMEs with a bank loan, FiinGroup) and 75.5% (firms that cannot borrow without collateral, VCCI), then "What they have:" with three chips: bank PDFs, marketplace screenshots, paper receipts. |
| `how` | 14 s | Three steps joined by arrows that draw in: Read with evidence, Challenge (turns amber), Human signs. Caption: Gemini 3.8 Flash · Agent Development Kit · Python checks. |
| `benchmark` | 16 s | "Live Gemini run · 3 demo businesses · 20 planted traps". Bars for traps caught (18/20 vs 3/20), counters for unsourced numbers (0 vs 62), the cost line and a footnote on strict scoring. |
| `outro` | 8 s | "Humans decide. AI shows its work.", the LedgerLens wordmark (the lens draws itself), the tech stack row and the repo URL. |

## Render

```bash
cd video/motion
export PATH=/opt/homebrew/opt/node@24/bin:$PATH   # Node 24
npm install                                       # once; installs playwright 1.60.0 (uses installed Google Chrome)
node render.mjs                                   # all scenes -> out/<scene>.mp4
node render.mjs benchmark                         # one scene
node render.mjs benchmark --d 12.4                # one scene, 12.4 s long
node render.mjs intro --d 20 --out /tmp/intro_20s.mp4
```

Output: H.264 (libx264, CRF 16), `yuv420p`, 1920x1080, exactly 30 fps, no audio. The frame count
is `round(d * 30)`. Rendering takes about 1.7x real time (an 18 s scene takes about 30 s).
Set `FFMPEG=/path/to/ffmpeg` or `PW_CHANNEL=chromium` to override the defaults.

To preview, open a scene in a browser. It loops in real time. Add `?t=7.5` to freeze one instant
and `?d=12` to preview another duration, for example `scenes/benchmark.html?d=12&t=11`.

## Edit text and numbers

Every scene has a block marked `EDIT TEXT ... HERE` near the top of the file, with
`DEFAULT_DURATION` and a `TEXT` / `DATA` object. Change the values there and re-render.
- `intro`: in `headline`, the `|` marks the line break and the start of the teal highlight. Stat values animate from 0 to `value`.
- `how`: `steps[]` holds the titles, body text and tags. `highlight` is the index of the amber step.
- `benchmark`: `total`, `ours.caught`, `baseline.caught` and `unsourced.ours` / `unsourced.baseline`. Bar widths come from `caught / total`. The `cost` strings may contain `<b>`.
- `outro`: `line1`, `line2`, `stack[]`, `url`.

Colours are CSS variables in `:root` at the top of each file: ink `#0F3D4C`, teal `#2A7F8E`,
tint `#E6F2F4`, amber `#E0A100`, red `#B3261E`, grey `#5F6368` and blue `#1f4fd8` on `#f7f7f5`.

## Match durations to the narration

All cues are fractions of the scene duration. Every element is in place by about 75% of the
duration, and the final frame holds for the rest. Any duration from 0.7x to 1.4x of the default
looks right. To fit a scene to a voice clip, measure the clip and render with that length:

```bash
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 narration/benchmark.wav)
node render.mjs benchmark --d "$D"
```

To make the change permanent, edit `DEFAULT_DURATION` in the scene file instead.
To change when something appears, edit the `cue(t, start, end)` fractions in that scene's `renderAt`.

## Splice into the main video

Each clip has the same format as a typical 1080p30 edit, so ffmpeg can concatenate them without
re-encoding if the main video segments are also H.264 / yuv420p / 1920x1080 / 30 fps.
Otherwise, re-encode everything once.

Replace a segment of the main video with a scene and keep the main audio, re-encoding once:

```bash
# main.mp4: put out/benchmark.mp4 at 01:05.0-01:21.0 (16 s), keep main.mp4's audio throughout
ffmpeg -i main.mp4 -i out/benchmark.mp4 -filter_complex \
  "[1:v]setpts=PTS-STARTPTS+65/TB[mg]; \
   [0:v][mg]overlay=enable='between(t,65,81)':eof_action=pass[v]" \
  -map "[v]" -map 0:a -c:v libx264 -crf 18 -pix_fmt yuv420p -r 30 -c:a copy final.mp4
```

Lay narration over a scene, or join scenes back to back:

```bash
ffmpeg -i out/intro.mp4 -i narration/intro.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest intro_vo.mp4

printf "file '%s'\n" out/intro.mp4 out/how.mp4 out/benchmark.mp4 out/outro.mp4 > list.txt
ffmpeg -f concat -safe 0 -i list.txt -c copy motion_all.mp4
```

Add a 0.3 s cross-fade between two clips with `xfade`:
`-filter_complex "[0:v][1:v]xfade=transition=fade:duration=0.3:offset=<len0-0.3>"`.

Rendered files in `out/` and `node_modules/` are ignored by git.
