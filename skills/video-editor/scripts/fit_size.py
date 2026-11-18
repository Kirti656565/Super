#!/usr/bin/env python3
"""Re-encode a video so it lands just under a target file size (two-pass H.264).

Usage: fit_size.py IN OUT --mb 10 [--audio-kbps 96] [--max-height 1080]

Lowers the resolution automatically when the bitrate would be too low for it to look decent.
"""
import argparse
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
from probe import probe  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--mb", type=float, required=True, help="target size in megabytes (10^6 bytes)")
    ap.add_argument("--audio-kbps", type=int, default=96)
    ap.add_argument("--max-height", type=int, default=None)
    a = ap.parse_args()

    info = probe(a.inp)
    dur = info["duration_s"]
    if not dur:
        sys.exit("could not read duration")
    has_audio = info["audio"] is not None
    audio_kbps = a.audio_kbps if has_audio else 0
    # 4% headroom for container overhead
    total_kbps = a.mb * 8_000 * 0.96 / dur
    video_kbps = int(total_kbps - audio_kbps)
    if video_kbps < 100:
        audio_kbps = 48 if has_audio else 0
        video_kbps = int(total_kbps - audio_kbps)
    if video_kbps < 50:
        sys.exit(f"target {a.mb} MB is too small for {dur:.1f}s of video (would be {video_kbps} kbps)")

    # pick a height that suits the bitrate
    src_h = info["video"]["height"] if info["video"] else 1080
    h = a.max_height or src_h
    if video_kbps < 2500:
        h = min(h, 720)
    if video_kbps < 1200:
        h = min(h, 480)
    if video_kbps < 500:
        h = min(h, 360)
    vf = f"scale=-2:'min({h},ih)'"

    passlog = os.path.join(tempfile.mkdtemp(), "pass")
    common = ["-c:v", "libx264", "-preset", "medium", "-b:v", f"{video_kbps}k",
              "-pix_fmt", "yuv420p", "-vf", vf, "-passlogfile", passlog]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a.inp, *common, "-pass", "1", "-an", "-f", "mp4", os.devnull], check=True)
    audio = ["-c:a", "aac", "-b:a", f"{audio_kbps}k"] if has_audio else ["-an"]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a.inp, *common, "-pass", "2", *audio,
                    "-movflags", "+faststart", a.out], check=True)
    size = os.path.getsize(a.out) / 1_000_000
    print(f"{a.out}: {size:.2f} MB (target {a.mb} MB), video {video_kbps} kbps, audio {audio_kbps} kbps, max height {h}")
    if size > a.mb:
        print("WARNING: over target; re-run with a smaller --mb", file=sys.stderr)


if __name__ == "__main__":
    main()
