#!/usr/bin/env python3
"""CLI tool to inspect and probe video file metadata (duration, codecs, resolution)."""

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from video_tools.ffmpeg_runner import FFmpegRunner
from video_tools.time_parser import format_duration_short, format_timestamp


def main():
    parser = argparse.ArgumentParser(
        description="Probe video file metadata (duration, format, resolution, codecs)."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Path(s) to video files to probe."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON format."
    )

    args = parser.parse_args()
    runner = FFmpegRunner()

    results = []
    for p_str in args.inputs:
        p = Path(p_str)
        if not p.exists():
            print(f"Warning: File not found: {p}", file=sys.stderr)
            continue

        info = runner.probe_video(p)
        results.append({
            "path": str(info.path),
            "filename": info.path.name,
            "duration_sec": info.duration,
            "duration_formatted": format_duration_short(info.duration),
            "width": info.width,
            "height": info.height,
            "fps": info.fps,
            "video_codec": info.video_codec,
            "audio_codec": info.audio_codec,
            "size_bytes": info.size_bytes
        })

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("=" * 60)
        print("VIDEO PROBE METADATA")
        print("=" * 60)
        for r in results:
            print(f"File:     {r['filename']}")
            print(f"  Path:     {r['path']}")
            print(f"  Duration: {r['duration_formatted']} ({r['duration_sec']:.2f}s)")
            if r['width'] and r['height']:
                print(f"  Size:     {r['width']}x{r['height']} @ {r.get('fps', 0):.2f}fps")
            if r['video_codec'] or r['audio_codec']:
                print(f"  Codecs:   v={r.get('video_codec')}, a={r.get('audio_codec')}")
            print("-" * 60)


if __name__ == "__main__":
    main()

