"""Deterministic Video Splitter.

Takes structured inputs: video path, explicit segments [A, B], [C, D], and optional output names.
All AI reasoning and prompt parsing is performed by the agent before calling this tool.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from video_tools.ffmpeg_runner import FFmpegRunner, VideoInfo
from video_tools.time_parser import format_filename_range, format_timestamp, parse_timestamp


@dataclass
class SegmentSpec:
    """Explicit segment boundaries."""
    start: float
    end: float
    output_name: Optional[str] = None

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def __post_init__(self):
        if self.start < 0:
            raise ValueError(f"Start time cannot be negative: {self.start}")
        if self.end < self.start:
            raise ValueError(f"End time ({self.end}) must be >= start time ({self.start})")


@dataclass
class OutputVideoSegment:
    """Information for an extracted video file."""
    output_index: int
    output_path: str
    start_sec: float
    end_sec: float
    duration_sec: float
    start_formatted: str
    end_formatted: str
    ffmpeg_command: str


@dataclass
class SplitResult:
    """Outcome of a video split operation."""
    input_path: str
    total_duration_sec: float
    output_segments: List[OutputVideoSegment]
    dry_run: bool
    status: str
    message: str

    def to_dict(self):
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class VideoSplitter:
    """Splits a video deterministically given explicit segments."""

    def __init__(self, runner: Optional[FFmpegRunner] = None):
        self.runner = runner or FFmpegRunner()

    def split(
        self,
        video_path: Union[str, Path],
        segments: List[Union[SegmentSpec, Tuple[Union[str, float], Union[str, float]]]],
        output_dir: Optional[Union[str, Path]] = None,
        output_names: Optional[List[str]] = None,
        reencode: bool = False,
        dry_run: bool = False
    ) -> SplitResult:
        """Split a video into segments based on explicit time ranges.

        Args:
            video_path: Path to the input video.
            segments: List of SegmentSpec or (start, end) tuples (e.g. [("0:00", "7:29"), ("7:49", "11:33")]).
            output_dir: Directory where split files will be stored.
            output_names: Optional explicit filenames for each output segment.
            reencode: If True, re-encodes with libx264/aac; if False, uses stream copy (-c copy).
            dry_run: If True, returns execution plan and commands without invoking FFmpeg.

        Returns:
            SplitResult with all created segments and execution metadata.
        """
        in_path = Path(video_path).resolve()
        if not dry_run and not in_path.exists():
            raise FileNotFoundError(f"Input video file not found: {in_path}")

        total_duration = 0.0
        if in_path.exists():
            try:
                info = self.runner.probe_video(in_path)
                total_duration = info.duration
            except Exception:
                pass

        # Normalize segments
        norm_segments: List[SegmentSpec] = []
        for idx, item in enumerate(segments):
            custom_name = output_names[idx] if (output_names and idx < len(output_names)) else None
            if isinstance(item, SegmentSpec):
                name = custom_name or item.output_name
                norm_segments.append(SegmentSpec(start=item.start, end=item.end, output_name=name))
            elif isinstance(item, (tuple, list)) and len(item) == 2:
                st = parse_timestamp(item[0])
                en = parse_timestamp(item[1])
                norm_segments.append(SegmentSpec(start=st, end=en, output_name=custom_name))
            else:
                raise ValueError(f"Invalid segment item: {item}. Expected SegmentSpec or (start, end) tuple.")

        if not norm_segments:
            raise ValueError("No segments provided for splitting.")

        # Validate that keep segments do not overlap
        norm_segments.sort(key=lambda s: s.start)
        for i in range(len(norm_segments) - 1):
            curr = norm_segments[i]
            nxt = norm_segments[i + 1]
            if curr.end > nxt.start:
                raise ValueError(
                    f"Overlapping segments: [{format_timestamp(curr.start)}, {format_timestamp(curr.end)}] "
                    f"overlaps with [{format_timestamp(nxt.start)}, {format_timestamp(nxt.end)}]"
                )

        # Determine output directory
        if output_dir:
            out_dir = Path(output_dir).resolve()
        else:
            out_dir = in_path.parent / f"{in_path.stem}_splits"

        if not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)

        ext = in_path.suffix if in_path.suffix else ".mp4"
        created_segments: List[OutputVideoSegment] = []

        for idx, seg in enumerate(norm_segments, start=1):
            if seg.output_name:
                out_filename = seg.output_name if seg.output_name.endswith(ext) else f"{seg.output_name}{ext}"
            else:
                range_tag = format_filename_range(seg.start, seg.end)
                out_filename = f"{in_path.stem}_part{idx:02d}_{range_tag}{ext}"

            out_file = out_dir / out_filename

            # Build deterministic FFmpeg command
            args = [
                "-y",
                "-ss", str(seg.start),
                "-to", str(seg.end),
                "-i", str(in_path),
            ]

            if reencode:
                args += ["-c:v", "libx264", "-c:a", "aac"]
            else:
                args += ["-c", "copy", "-avoid_negative_ts", "make_zero"]

            args.append(str(out_file))

            cmd_repr = "ffmpeg " + " ".join(f'"{a}"' if " " in a else a for a in args)

            retcode, stdout, stderr = self.runner.run_ffmpeg(args, dry_run=dry_run)
            if not dry_run and retcode != 0:
                # Try re-encoding fallback if stream copy failed
                if not reencode:
                    fallback_args = [
                        "-y",
                        "-ss", str(seg.start),
                        "-to", str(seg.end),
                        "-i", str(in_path),
                        "-c:v", "libx264",
                        "-c:a", "aac",
                        str(out_file)
                    ]
                    f_ret, f_out, f_err = self.runner.run_ffmpeg(fallback_args, dry_run=False)
                    if f_ret != 0:
                        raise RuntimeError(f"FFmpeg split failed for segment [{seg.start}, {seg.end}]: {f_err or stderr}")
                    cmd_repr = "ffmpeg " + " ".join(fallback_args)
                else:
                    raise RuntimeError(f"FFmpeg split failed for segment [{seg.start}, {seg.end}]: {stderr}")

            created_segments.append(
                OutputVideoSegment(
                    output_index=idx,
                    output_path=str(out_file),
                    start_sec=seg.start,
                    end_sec=seg.end,
                    duration_sec=seg.duration,
                    start_formatted=format_timestamp(seg.start),
                    end_formatted=format_timestamp(seg.end),
                    ffmpeg_command=cmd_repr
                )
            )

        status = "success" if (dry_run or created_segments) else "failed"
        action_word = "Planned" if dry_run else "Successfully created"
        msg = f"{action_word} {len(created_segments)} video file(s) from {in_path.name}"

        return SplitResult(
            input_path=str(in_path),
            total_duration_sec=total_duration,
            output_segments=created_segments,
            dry_run=dry_run,
            status=status,
            message=msg
        )
