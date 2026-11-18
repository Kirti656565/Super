# ffmpeg recipes

All re-encoding examples assume these output flags unless shown otherwise; written as `$OUT` below:

```
-c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart
```

`FONT` = a font path from `fc-list` (e.g. `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`).

## Contents
1. Trim and cut
2. Speed, reverse, freeze
3. Audio: music, mixing, ducking, volume, extract
4. Text, titles, logos
5. Resize, crop, aspect ratio, rotate
6. Fades and transitions
7. Layouts: picture-in-picture, side-by-side
8. GIFs, thumbnails, slideshows, subtitles

---

## 1. Trim and cut

Keep 0:12 – 0:45 (frame accurate):
```
ffmpeg -i in.mp4 -ss 12 -to 45 $OUT out.mp4
```
Fast, no re-encode (start snaps to the previous keyframe):
```
ffmpeg -ss 12 -to 45 -i in.mp4 -c copy -avoid_negative_ts make_zero out.mp4
```
Remove a middle section (drop 10s–20s), keeping sync:
```
ffmpeg -i in.mp4 -filter_complex "\
[0:v]trim=0:10,setpts=PTS-STARTPTS[v1];[0:a]atrim=0:10,asetpts=PTS-STARTPTS[a1];\
[0:v]trim=start=20,setpts=PTS-STARTPTS[v2];[0:a]atrim=start=20,asetpts=PTS-STARTPTS[a2];\
[v1][a1][v2][a2]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" $OUT out.mp4
```
(Several cuts: add more trim pairs. A simpler alternative: `select`/`aselect` with `between(t,10,20)` negated, plus `setpts=N/FRAME_RATE/TB` and `asetpts=N/SR/TB`.)

Split into equal 60s parts:
```
ffmpeg -i in.mp4 -c copy -f segment -segment_time 60 -reset_timestamps 1 part_%03d.mp4
```

## 2. Speed, reverse, freeze

2x speed, audio pitch preserved (atempo range is 0.5–2.0 per instance; chain for more, e.g. 4x = `atempo=2,atempo=2`):
```
ffmpeg -i in.mp4 -filter_complex "[0:v]setpts=PTS/2[v];[0:a]atempo=2[a]" -map "[v]" -map "[a]" $OUT out.mp4
```
Slow motion 0.5x: `setpts=PTS*2` and `atempo=0.5`. For smooth slow-mo from low-fps footage add `minterpolate=fps=60` (slow).

Speed up only 30s–90s (3x), rest normal: trim into three parts, apply `setpts=(PTS-STARTPTS)/3` and `atempo=1.5,atempo=2` to the middle, concat as in "remove a middle section".

Reverse (loads the clip into memory — use for short clips only):
```
ffmpeg -i in.mp4 -vf reverse -af areverse $OUT out.mp4
```
Hold the last frame for 2s at the end:
```
ffmpeg -i in.mp4 -vf tpad=stop_mode=clone:stop_duration=2 -af apad=pad_dur=2 $OUT out.mp4
```
Mid-clip freeze: split at 5s, append `tpad=stop_mode=clone:stop_duration=2` to the first part's video and `apad=pad_dur=2` to its audio, then concat.

## 3. Audio

Replace audio with music, cut to video length, fade music out over the last 2s (D = video duration):
```
ffmpeg -i in.mp4 -stream_loop -1 -i song.mp3 -filter_complex \
"[1:a]atrim=0:D,afade=t=in:d=1,afade=t=out:st=D-2:d=2[a]" \
-map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -shortest out.mp4
```
(`-stream_loop -1` loops a song shorter than the video.)

Mix background music under the original audio at 20% volume:
```
ffmpeg -i in.mp4 -stream_loop -1 -i song.mp3 -filter_complex \
"[1:a]volume=0.2[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]" \
-map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k out.mp4
```
Ducking (music drops automatically while someone talks):
```
-filter_complex "[0:a]asplit[voice][key];[1:a]volume=0.5[m];\
[m][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck];\
[voice][duck]amix=inputs=2:duration=first:normalize=0[a]"
```
Normalize loudness (good default for social/YouTube, −14 LUFS):
```
ffmpeg -i in.mp4 -c:v copy -af loudnorm=I=-14:TP=-1.5:LRA=11 -c:a aac -b:a 192k out.mp4
```
Volume: `-af volume=1.5` (or `volume=6dB`). Mute: `-an`. Mute a range: `-af "volume=enable='between(t,5,8)':volume=0"`.

Extract audio: `ffmpeg -i in.mp4 -vn -c:a libmp3lame -q:a 2 out.mp3` (or `-c:a copy out.m4a` if source is AAC).

Add silent track (some platforms reject video with no audio):
```
ffmpeg -i in.mp4 -f lavfi -i anullsrc=r=48000:cl=stereo -c:v copy -c:a aac -shortest out.mp4
```

## 4. Text, titles, logos

Centered title for the first 3s with fade in/out:
```
ffmpeg -i in.mp4 -vf "drawtext=fontfile=FONT:text='My Trip':fontsize=h/10:fontcolor=white:\
borderw=4:bordercolor=black:x=(w-tw)/2:y=(h-th)/2:enable='between(t,0,3)':\
alpha='if(lt(t,0.5),t/0.5,if(gt(t,2.5),(3-t)/0.5,1))'" -c:a copy out.mp4
```
Bottom caption on a translucent box (lower third):
```
drawtext=fontfile=FONT:text='Jane Doe — Designer':fontsize=h/22:fontcolor=white:\
box=1:boxcolor=black@0.55:boxborderw=20:x=(w-tw)/2:y=h-th-h/12
```
Size text relative to `h` so it scales with the video. Keep it inside the safe area (≈10% from edges; for vertical video keep the bottom 20% clear of the platform UI).

Text escaping: inside `text='...'` escape `:` as `\:`, `'` as `'\''` (shell) and `%` as `\%`. For anything tricky, write the text to a file and use `textfile=title.txt`.

Logo/watermark, top-right, 15% of video width, 70% opacity:
```
ffmpeg -i in.mp4 -i logo.png -filter_complex \
"[1]format=rgba,colorchannelmixer=aa=0.7[lg];[lg][0:v]scale2ref=w=iw*0.15:h=ow/mdar[lg][v];\
[v][lg]overlay=W-w-W*0.03:H*0.03" -c:a copy out.mp4
```
Timestamp/clock overlay: `drawtext=fontfile=FONT:text='%{pts\:hms}':x=10:y=10:fontsize=h/25:fontcolor=white:box=1:boxcolor=black@0.5`.

## 5. Resize, crop, aspect ratio, rotate

Scale to 1280 wide keeping aspect: `-vf scale=1280:-2` (`-2` keeps the dimension even, required by H.264).

Horizontal → vertical 9:16, **crop to fill** (center; shift `x` to follow the subject):
```
-vf "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920,setsar=1"
```
Horizontal → vertical, **fit with blurred background**:
```
ffmpeg -i in.mp4 -filter_complex "[0:v]split[a][b];\
[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];\
[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];\
[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1" -c:a copy out.mp4
```
Letterbox with black bars to exactly 1920x1080:
```
-vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1"
```
Square 1:1 center crop: `-vf "crop='min(iw,ih)':'min(iw,ih)',scale=1080:1080"`.

Rotate 90° clockwise: `-vf transpose=1` (counter-clockwise `transpose=2`, 180° `transpose=1,transpose=1`). Flip: `hflip` / `vflip`.
Fix a wrong rotation flag without re-encoding: `ffmpeg -display_rotation 0 -i in.mp4 -c copy out.mp4` (ffmpeg ≥ 6).

Change fps: `-vf fps=30`. Stabilize (two passes, needs vidstab build): `vidstabdetect` then `vidstabtransform`; fallback `deshake`.

Color: `-vf eq=brightness=0.05:contrast=1.1:saturation=1.2`. Black & white: `hue=s=0`.

## 6. Fades and transitions

Fade in from black 1s and out over the last 1s (D = duration):
```
-vf "fade=t=in:d=1,fade=t=out:st=D-1:d=1" -af "afade=t=in:d=1,afade=t=out:st=D-1:d=1"
```
Transitions between clips: use `scripts/join.py --fade 0.5 --transition <name>`. xfade names include fade, dissolve, wipeleft, wiperight, slideleft, slideup, circleopen, radial, smoothleft, fadeblack, fadewhite, pixelize, zoomin.

## 7. Layouts

Picture-in-picture (webcam bottom-right at 25% width):
```
ffmpeg -i main.mp4 -i cam.mp4 -filter_complex \
"[1:v]scale=iw*0.25:-2[pip];[0:v][pip]overlay=W-w-20:H-h-20:shortest=1" -map 0:a? $OUT out.mp4
```
Side by side (same height): `[0:v]scale=-2:720[l];[1:v]scale=-2:720[r];[l][r]hstack=inputs=2`. Stacked: `vstack` with matched widths. 2x2 grid: `xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0`.

## 8. GIFs, thumbnails, slideshows, subtitles

High-quality GIF (5s from 0:10, 480 wide, 15 fps):
```
ffmpeg -ss 10 -t 5 -i in.mp4 -filter_complex \
"fps=15,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" out.gif
```
Thumbnail at 0:07: `ffmpeg -ss 7 -i in.mp4 -frames:v 1 -q:v 2 thumb.jpg`. Contact sheet: `-vf "fps=1/10,scale=320:-1,tile=4x3" -frames:v 1 sheet.jpg`.

Images → slideshow, 3s each, 1080p, with gentle zoom (Ken Burns):
```
ffmpeg -framerate 1/3 -pattern_type glob -i 'photos/*.jpg' -vf \
"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30" $OUT slideshow.mp4
```
For zoom per image: per-image input `-loop 1 -t 3 -i img.jpg` with `scale=3840:-2,zoompan=z='min(zoom+0.0015,1.3)':d=90:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30`, then join with `scripts/join.py --fade 0.5`.

Burn subtitles from an .srt (styled):
```
ffmpeg -i in.mp4 -vf "subtitles=subs.srt:force_style='FontName=DejaVu Sans,FontSize=22,Outline=2,MarginV=40'" -c:a copy out.mp4
```
Soft (toggleable) subtitles in MP4: `-i subs.srt -map 0 -map 1 -c copy -c:s mov_text`.
