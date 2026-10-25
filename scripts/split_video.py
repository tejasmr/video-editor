#!/usr/bin/env python3
"""CLI tool for splitting video files deterministically by explicit time segments."""

import argparse
import json
import re
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from video_tools.splitter import VideoSplitter
from video_tools.time_parser import parse_timestamp


def main():
    parser = argparse.ArgumentParser(
        description="Deterministically split a video into one or multiple files based on explicit time segments."
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the input video file."
    )
    parser.add_argument(
        "--segments", "-s",
        nargs="+",
        required=True,
        help="Explicit time intervals to extract, e.g.: --segments 0:00-7:29 7:49-11:33 or 0:00,7:29 7:49,11:33"
    )
    parser.add_argument(
        "--output-dir", "-o",
        help="Output directory to save split files (defaults to '<video_dir>/<name>_splits')."
    )
    parser.add_argument(
        "--output-names",
        nargs="+",
        help="Optional explicit file names for each segment (e.g. --output-names part1.mp4 part2.mp4)."
    )
    parser.add_argument(
        "--reencode",
        action="store_true",
        help="Force re-encoding instead of fast stream copy."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the split plan and FFmpeg commands without executing."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON results."
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    if not args.dry_run and not input_path.exists():
        print(f"Error: Input video not found at: {input_path}", file=sys.stderr)
        sys.exit(1)

    parsed_segments = []
    for raw in args.segments:
        # Match tokens like "0:00-7:29", "0:00 to 7:29", "[0:00, 7:29]", or "0:00,7:29"
        clean = raw.strip("[]() ")
        parts = re.split(r"[-–—,]|(?:\s+to\s+)", clean)
        if len(parts) == 2:
            st = parse_timestamp(parts[0].strip())
            en = parse_timestamp(parts[1].strip())
            parsed_segments.append((st, en))
        else:
            print(f"Error: Could not parse segment range from '{raw}'. Expected format: START-END (e.g. 0:00-7:29)", file=sys.stderr)
            sys.exit(1)

    splitter = VideoSplitter()

    try:
        result = splitter.split(
            video_path=input_path,
            segments=parsed_segments,
            output_dir=args.output_dir,
            output_names=args.output_names,
            reencode=args.reencode,
            dry_run=args.dry_run
        )
    except Exception as e:
        print(f"Error during video split: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(result.to_json())
    else:
        print("=" * 60)
        print("VIDEO SPLIT SUMMARY")
        print("=" * 60)
        print(f"Input:        {result.input_path}")
        print(f"Status:       {result.status.upper()}")
        print(f"Message:      {result.message}")
        print(f"Segments ({len(result.output_segments)}):")
        for seg in result.output_segments:
            print(f"  Part {seg.output_index:02d}: [{seg.start_formatted} -> {seg.end_formatted}] "
                  f"({seg.duration_sec:.1f}s) -> {seg.output_path}")
            if args.dry_run:
                print(f"    Command: {seg.ffmpeg_command}")
        print("=" * 60)


if __name__ == "__main__":
    main()
