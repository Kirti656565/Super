---
name: video-editor
description: General-purpose video editing with ffmpeg — trim and cut, join clips, crossfade transitions, add or replace music, text and title overlays, logos and watermarks, speed up or slow down, resize/crop for TikTok, Reels, Shorts, YouTube or Instagram, compress for email/Discord/WhatsApp size limits, extract audio, make GIFs and thumbnails, fix volume, rotate, and export. Use this skill whenever the user wants anything done to a video or audio file (mp4, mov, mkv, webm, avi, mp3, wav), even if they don't say "edit" — e.g. "make this clip shorter", "put these videos together", "add a song to my video", "make it vertical", "it's too big to send", "add my name at the bottom", "speed up the boring part". For removing silences/filler words from a talking-head recording, a dedicated talking-head skill is better if one is available.
---

# Video Editor

Edit video and audio files with `ffmpeg`/`ffprobe`. The goal is a finished file the user can play and share, made without silently losing quality, sync or audio.

## Workflow

1. **Inspect first.** Run `python3 <skill>/scripts/probe.py <file>...` on every input. It prints duration, resolution, fps, rotation, codecs and whether there is audio. Most broken edits come from skipping this: joining clips with different sizes/fps, assuming audio exists, or ignoring phone rotation metadata.
2. **Restate the plan briefly** when the request is ambiguous (e.g. "cut the boring part" — which seconds?). If the user gave enough detail, just do it; don't ask about things with an obvious default.
3. **Build the command(s).** Look up the matching recipe in `references/recipes.md`. Prefer one ffmpeg pass with a `-filter_complex` over many re-encodes, because every re-encode loses quality.
4. **Never overwrite the input.** Write to a new file, e.g. `clip_trimmed.mp4`. Use `-y` only for your own output paths.
5. **Verify the output.** Run `probe.py` on the result and check duration, resolution, and that audio is present when it should be. For visual changes (text, crop, logo), grab a frame with `ffmpeg -ss <t> -i out.mp4 -frames:v 1 check.png` and look at it — text off-screen or a bad crop is easy to miss otherwise.
6. **Report**: output path, duration, resolution, file size, and anything you had to assume.

## Defaults (and why)

- **Output**: MP4, H.264 (`-c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p`), AAC audio (`-c:a aac -b:a 192k`), `-movflags +faststart`. This plays everywhere — phones, browsers, WhatsApp, every social platform. `yuv420p` matters: without it some players show a black screen.
- **Stream copy (`-c copy`)** only for plain trims/joins where speed matters and the user accepts cuts snapping to keyframes. When cut accuracy matters, re-encode.
- **Accurate seeking**: put `-ss`/`-to` *after* `-i` for frame-accurate cuts when re-encoding; put `-ss` before `-i` only for fast keyframe cuts with `-c copy`.
- **Keep the source fps and resolution** unless asked to change them.
- **Fonts for text**: pass an explicit `fontfile=` (find one with `fc-list | grep -i -E "dejavu|inter|liberation|arial"`). Escape `:` and `'` in drawtext text, or write the text to a file and use `textfile=`.

## Platform presets

| Target | Size | Notes |
|---|---|---|
| TikTok / Reels / Shorts | 1080x1920 (9:16) | Shorts must be ≤ 60 s, Reels ≤ 90 s for best reach |
| YouTube | 1920x1080 (16:9) | |
| Instagram feed | 1080x1350 (4:5) or 1080x1080 | |
| Twitter/X | 1280x720 | ≤ 140 s, ≤ 512 MB |

To change aspect ratio, ask (or pick sensibly) between **crop to fill** (loses edges, looks native) and **fit with blurred background** (keeps everything). For a speaker or single subject, crop; for screen recordings or wide shots, blurred background. Recipes for both are in the reference.

## Size targets

To hit a file-size limit (Discord 10 MB, email 25 MB, WhatsApp 16 MB…), use `python3 <skill>/scripts/fit_size.py in.mp4 out.mp4 --mb 10`. It computes the bitrate from the duration and runs a two-pass encode, landing just under the limit. Guessing a CRF usually misses by a lot.

## Joining clips

Use `python3 <skill>/scripts/join.py out.mp4 a.mp4 b.mp4 ... [--fade 0.5] [--size 1920x1080] [--fps 30]`. It normalizes every clip to the same size/fps/audio format (adding silent audio to clips with none), then joins them — with crossfades if `--fade` is given. Hand-written concat or xfade chains are the most common source of errors (offset math, mismatched timebases, missing audio streams), which is why this is a script.

## Reference

`references/recipes.md` — tested commands for: trim, cut out a middle section, speed change (with pitch-correct audio), reverse, music (replace, mix with ducking, loop/fade to fit), volume/normalize, text/title/lower-third, logo/watermark, crop/resize/pad/blur-fill, rotate/flip, fades, freeze frame, picture-in-picture, side-by-side, GIF, thumbnails, extract/strip audio, images-to-slideshow, burn subtitles. Read the section you need rather than the whole file.

## When things go wrong

- `Invalid argument` / filter errors: print the full `-filter_complex` string and check stream labels; each label can be consumed only once (use `split`/`asplit` to reuse one).
- Audio drifts out of sync after joining: clips had different sample rates or fps — use `join.py`, which normalizes them.
- Output is sideways: the phone stored rotation as metadata; ffmpeg auto-rotates when re-encoding, but `-c copy` keeps the flag. Re-encode.
- No audio in output: an input had no audio stream and a `[0:a]` reference was dropped or failed. Check `probe.py` and add `anullsrc` silence if needed.
