#!/usr/bin/env bash
# Mix generated background music under a video's narration. The music sits about 20 dB under the voice and ducks
# further while someone speaks (sidechain compression); the result is loudness-normalised for YouTube (-14 LUFS).
#   video/audio/mix_bgm.sh INPUT.mp4 BGM.wav OUTPUT.mp4 [music_gain_db]
set -euo pipefail
IN="$1"; BGM="$2"; OUT="$3"; GAIN="${4:--19}"
ffmpeg -y -v error -i "$IN" -i "$BGM" -filter_complex \
  "[1:a]volume=${GAIN}dB[m];[0:a]asplit=2[voice][key];[m][key]sidechaincompress=threshold=0.02:ratio=6:attack=40:release=600[duck];\
   [voice][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$OUT"
echo "mixed -> $OUT"
