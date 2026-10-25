#!/usr/bin/env python3
"""CLI tool for merging multiple video files deterministically in specified order."""

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from video_tools.merger import VideoMerger


def main():
    parser = argparse.ArgumentParser(
        description="Deterministically merge multiple video files in exact specified sequence."
    )
    parser.add_argument(
        "--inputs", "-i",
        nargs="+",
        required=True,
        help="List of input video file paths in the exact concatenation order."
    )
    parser.add_argument(
        "--segments", "-s",
        nargs="+",
        help="Optional segment intervals for each input file (e.g. 0:00-1:30 2:00-3:15 or 'full'). Defaults to 'full'."
    )
    parser.add_argument(
        "--output", "-o",
        help="Path for the output merged video file (defaults to '<dir>/merged_<N>_files.mp4')."
    )
    parser.add_argument(
        "--reencode",
        action="store_true",
        help="Force re-encoding instead of fast stream copy."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the merge plan and FFmpeg commands without executing."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON results."
    )

    args = parser.parse_args()

    input_paths = [Path(p) for p in args.inputs]
    if not args.dry_run:
        for p in input_paths:
            if not p.exists():
                print(f"Error: Input video not found at: {p}", file=sys.stderr)
                sys.exit(1)

    merger = VideoMerger()

    try:
        result = merger.merge(
            video_paths=input_paths,
            segments=args.segments,
            output_path=args.output,
            reencode=args.reencode,
            dry_run=args.dry_run
        )
    except Exception as e:
        print(f"Error during video merge: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(result.to_json())
    else:
        print("=" * 60)
        print("VIDEO MERGE SUMMARY")
        print("=" * 60)
        print(f"Output File:    {result.output_path}")
        print(f"Status:         {result.status.upper()}")
        print(f"Total Duration: {result.total_duration_formatted} ({result.total_duration_sec:.1f}s)")
        print(f"Message:        {result.message}")
        print("Ordered Sequence:")
        for inp in result.ordered_inputs:
            seg_info = f" [segment: {inp.segment_formatted}]" if inp.segment_formatted != "full" else ""
            print(f"  #{inp.position}: {inp.path}{seg_info} [duration: {inp.duration_formatted}]")
        if args.dry_run:
            print(f"Command:        {result.ffmpeg_command}")
        print("=" * 60)


if __name__ == "__main__":
    main()
