#!/usr/bin/env bash
# Generate three short speech clips for Audio Live Link testing.
# Output: 48 kHz, 16-bit, mono PCM WAV (matches BlackHole's default 48 kHz).
set -euo pipefail
OUT="$(cd "$(dirname "$0")/.." && pwd)/test_audio"
mkdir -p "$OUT"
VOICE="${VOICE:-Samantha}"

say_wav () {
  local name="$1" text="$2"
  say -v "$VOICE" -o "$OUT/$name.aiff" "$text"
  afconvert -f WAVE -d LEI16@48000 -c 1 "$OUT/$name.aiff" "$OUT/$name.wav"
  rm "$OUT/$name.aiff"
  echo "wrote $OUT/$name.wav ($(afinfo "$OUT/$name.wav" | awk '/estimated duration/ {print $3}')s)"
}

say_wav clip1 "Hello, I am a MetaHuman. This is the first test clip for the audio live link."
say_wav clip2 "Peter Piper picked a peck of pickled peppers. Big bold vowels: ah, ee, oo, oh."
say_wav clip3 "Now the third and final clip. If my mouth is moving, the pipeline is working."
