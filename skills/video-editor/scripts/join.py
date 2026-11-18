#!/usr/bin/env python3
"""Join clips into one video, normalizing size/fps/audio, with optional crossfades.

Usage: join.py OUT IN1 IN2 [IN3 ...] [--fade SECONDS] [--size WxH] [--fps N] [--fit crop|pad]

- --size defaults to the first clip's display size; --fps to the first clip's fps (rounded).
- --fit pad (default) letterboxes clips with a different aspect ratio; crop fills the frame.
- Clips without audio get silence, so the audio track stays continuous.
- With --fade, consecutive clips overlap by SECONDS (video xfade + audio acrossfade),
  so the output is shorter than the sum of the clips by (n-1)*SECONDS.
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from probe import probe  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--fade", type=float, default=0.0)
    ap.add_argument("--size")
    ap.add_argument("--fps", type=float)
    ap.add_argument("--fit", choices=["pad", "crop"], default="pad")
    ap.add_argument("--transition", default="fade", help="xfade transition name (fade, wipeleft, slideup, dissolve, ...)")
    a = ap.parse_args()
    if len(a.inputs) < 2:
        sys.exit("need at least two inputs")

    infos = [probe(p) for p in a.inputs]
    for i in infos:
        if "error" in i or not i["video"]:
            sys.exit(f"cannot use {i['file']}: {i.get('error', 'no video stream')}")
    w, h = map(int, (a.size or infos[0]["video"]["display"]).split("x"))
    w, h = w - w % 2, h - h % 2
    fps = a.fps or round(infos[0]["video"]["fps"]) or 30
    durs = [i["duration_s"] for i in infos]
    if a.fade and a.fade >= min(durs):
        sys.exit(f"--fade {a.fade} must be shorter than the shortest clip ({min(durs)}s)")

    if a.fit == "pad":
        fit = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
    else:
        fit = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"

    args, parts = [], []
    for idx, (p, info) in enumerate(zip(a.inputs, infos)):
        args += ["-i", p]
    n = len(a.inputs)
    for idx, info in enumerate(infos):
        parts.append(f"[{idx}:v:0]{fit},setsar=1,fps={fps},format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[v{idx}]")
        if info["audio"]:
            parts.append(f"[{idx}:a:0]aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS,"
                         f"apad=whole_dur={durs[idx]},atrim=0:{durs[idx]}[a{idx}]")
        else:
            parts.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{durs[idx]}[a{idx}]")

    if a.fade:
        prev_v, prev_a, offset = "v0", "a0", 0.0
        for idx in range(1, n):
            offset += durs[idx - 1] - a.fade
            vo, ao = f"vx{idx}", f"ax{idx}"
            parts.append(f"[{prev_v}][v{idx}]xfade=transition={a.transition}:duration={a.fade}:offset={offset:.3f}[{vo}]")
            parts.append(f"[{prev_a}][a{idx}]acrossfade=d={a.fade}[{ao}]")
            prev_v, prev_a = vo, ao
        vout, aout = prev_v, prev_a
    else:
        parts.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vout][aout]")
        vout, aout = "vout", "aout"

    cmd = ["ffmpeg", "-y", "-v", "error", *args, "-filter_complex", ";".join(parts),
           "-map", f"[{vout}]", "-map", f"[{aout}]",
           "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out]
    r = subprocess.run(cmd)
    if r.returncode:
        print("filter_complex was:\n" + ";\n".join(parts), file=sys.stderr)
        sys.exit(r.returncode)
    o = probe(a.out)
    print(f"{a.out}: {o['duration_s']}s, {o['video']['display']} @ {o['video']['fps']}fps, {o['size_mb']} MB")


if __name__ == "__main__":
    main()
