#!/usr/bin/env python3
"""Print a compact summary of media files: duration, size, fps, rotation, codecs, audio.

Usage: probe.py FILE [FILE ...] [--json]
"""
import json
import subprocess
import sys


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return {"file": path, "error": out.stderr.strip()}
    data = json.loads(out.stdout)
    fmt = data.get("format", {})
    info = {
        "file": path,
        "duration_s": round(float(fmt.get("duration", 0) or 0), 3),
        "size_mb": round(int(fmt.get("size", 0) or 0) / 1_000_000, 2),
        "bitrate_kbps": round(int(fmt.get("bit_rate", 0) or 0) / 1000),
        "video": None,
        "audio": None,
    }
    for s in data.get("streams", []):
        if s["codec_type"] == "video" and info["video"] is None and s.get("disposition", {}).get("attached_pic") != 1:
            num, _, den = (s.get("avg_frame_rate") or s.get("r_frame_rate") or "0/1").partition("/")
            fps = round(float(num) / float(den), 3) if den and float(den) else 0
            rotation = 0
            for sd in s.get("side_data_list", []) or []:
                if "rotation" in sd:
                    rotation = int(sd["rotation"])
            rotation = rotation or int(s.get("tags", {}).get("rotate", 0) or 0)
            w, h = s.get("width"), s.get("height")
            info["video"] = {
                "codec": s.get("codec_name"),
                "width": w,
                "height": h,
                "display": f"{h}x{w}" if abs(rotation) in (90, 270) else f"{w}x{h}",
                "fps": fps,
                "rotation": rotation,
                "pix_fmt": s.get("pix_fmt"),
            }
        elif s["codec_type"] == "audio" and info["audio"] is None:
            info["audio"] = {
                "codec": s.get("codec_name"),
                "sample_rate": int(s.get("sample_rate", 0) or 0),
                "channels": s.get("channels"),
            }
    return info


def main():
    args = [a for a in sys.argv[1:] if a != "--json"]
    if not args:
        print(__doc__)
        sys.exit(1)
    results = [probe(p) for p in args]
    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
        return
    for r in results:
        if "error" in r:
            print(f"{r['file']}: ERROR {r['error']}")
            continue
        line = f"{r['file']}: {r['duration_s']}s, {r['size_mb']} MB"
        v, a = r["video"], r["audio"]
        if v:
            line += f" | video {v['codec']} {v['display']} @ {v['fps']}fps"
            if v["rotation"]:
                line += f" (stored {v['width']}x{v['height']}, rotation {v['rotation']})"
        else:
            line += " | no video"
        line += f" | audio {a['codec']} {a['sample_rate']}Hz {a['channels']}ch" if a else " | NO AUDIO"
        print(line)


if __name__ == "__main__":
    main()
