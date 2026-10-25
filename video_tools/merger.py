"""Deterministic Video Merger.

Merges multiple video files (or specific segments of them) in the exact sequence provided.
All AI reasoning (duration matching, ordering decisions) is performed by the agent before calling this tool.
"""

import json
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from video_tools.ffmpeg_runner import FFmpegRunner, VideoInfo
from video_tools.time_parser import format_duration_short, format_timestamp, parse_timestamp


@dataclass
class MergedFileInfo:
    """Information about an input file merged into the sequence."""
    position: int
    path: str
    duration_sec: float
    duration_formatted: str
    segment_formatted: str = "full"
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None


@dataclass
class MergeResult:
    """Outcome of a video merge operation."""
    output_path: str
    ordered_inputs: List[MergedFileInfo]
    total_duration_sec: float
    total_duration_formatted: str
    dry_run: bool
    status: str
    message: str
    ffmpeg_command: str

    def to_dict(self):
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class VideoMerger:
    """Merges multiple videos in exact ordered sequence, supporting optional segments."""

    def __init__(self, runner: Optional[FFmpegRunner] = None):
        self.runner = runner or FFmpegRunner()

    def merge(
        self,
        video_paths: List[Union[str, Path]],
        segments: Optional[List[Union[str, Tuple[Union[str, float], Union[str, float]], None]]] = None,
        output_path: Optional[Union[str, Path]] = None,
        reencode: bool = False,
        dry_run: bool = False
    ) -> MergeResult:
        """Merge videos in the exact order of the video_paths list.

        Args:
            video_paths: List of video paths in the desired concatenation order.
            segments: Optional list of segment ranges for each video (e.g. ['0:00-1:30', 'full', (10, 50)]).
                      Defaults to 'full' for any video without an explicit segment.
            output_path: Destination path for merged video file.
            reencode: If True, uses re-encoding filter_complex; if False, uses stream copy (-c copy).
            dry_run: If True, returns execution plan and command without invoking FFmpeg.

        Returns:
            MergeResult containing ordering details, output path, and execution metadata.
        """
        if not video_paths:
            raise ValueError("No input video paths provided")

        resolved_paths = [Path(p).resolve() for p in video_paths]
        if not dry_run:
            for p in resolved_paths:
                if not p.exists():
                    raise FileNotFoundError(f"Input video file not found: {p}")

        # Normalize segments per input file
        ordered_inputs: List[MergedFileInfo] = []
        for idx, p in enumerate(resolved_paths):
            dur = 0.0
            try:
                info = self.runner.probe_video(p)
                dur = info.duration
            except Exception:
                pass

            seg_spec = segments[idx] if (segments and idx < len(segments)) else None
            start_sec = None
            end_sec = None
            seg_formatted = "full"

            if seg_spec is not None and str(seg_spec).strip().lower() not in ("full", "all", "-", ""):
                if isinstance(seg_spec, (tuple, list)) and len(seg_spec) == 2:
                    start_sec = parse_timestamp(seg_spec[0])
                    end_sec = parse_timestamp(seg_spec[1])
                else:
                    parts = re.split(r"[-–—,]|(?:\s+to\s+)", str(seg_spec).strip("[]() "))
                    if len(parts) == 2:
                        start_sec = parse_timestamp(parts[0].strip())
                        end_sec = parse_timestamp(parts[1].strip())
                    else:
                        raise ValueError(f"Invalid segment format for input {idx + 1}: '{seg_spec}'. Expected START-END or 'full'")

                if end_sec < start_sec:
                    raise ValueError(f"End time ({end_sec}) must be >= start time ({start_sec}) for input {idx + 1}")

                seg_formatted = f"{format_timestamp(start_sec)}-{format_timestamp(end_sec)}"
                effective_dur = max(0.0, end_sec - start_sec)
            else:
                effective_dur = dur

            ordered_inputs.append(
                MergedFileInfo(
                    position=idx + 1,
                    path=str(p),
                    duration_sec=effective_dur,
                    duration_formatted=format_duration_short(effective_dur),
                    segment_formatted=seg_formatted,
                    start_sec=start_sec,
                    end_sec=end_sec
                )
            )

        # Output path
        first_path = resolved_paths[0]
        ext = first_path.suffix if first_path.suffix else ".mp4"
        if output_path:
            out_file = Path(output_path).resolve()
        else:
            out_file = first_path.parent / f"merged_{len(ordered_inputs)}_files{ext}"

        if not dry_run:
            out_file.parent.mkdir(parents=True, exist_ok=True)

        total_dur = sum(item.duration_sec for item in ordered_inputs)
        temp_files_to_clean: List[Path] = []

        try:
            # Prepare files for concatenation (slice segments if requested)
            paths_to_concat: List[str] = []
            for idx, item in enumerate(ordered_inputs):
                if item.start_sec is not None and item.end_sec is not None:
                    # Input requires slicing
                    if dry_run:
                        paths_to_concat.append(f"{item.path} [segment: {item.segment_formatted}]")
                    else:
                        temp_slice = out_file.parent / f"{out_file.stem}_slice_{idx + 1}_{item.segment_formatted.replace(':', '-')}{ext}"
                        temp_files_to_clean.append(temp_slice)
                        slice_args = [
                            "-y",
                            "-ss", str(item.start_sec),
                            "-to", str(item.end_sec),
                            "-i", item.path,
                        ]
                        if reencode:
                            slice_args += ["-c:v", "libx264", "-c:a", "aac"]
                        else:
                            slice_args += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
                        slice_args.append(str(temp_slice))

                        s_ret, s_out, s_err = self.runner.run_ffmpeg(slice_args, dry_run=False)
                        if s_ret != 0 and not reencode:
                            # Re-encode fallback for slice
                            slice_fb = [
                                "-y",
                                "-ss", str(item.start_sec),
                                "-to", str(item.end_sec),
                                "-i", item.path,
                                "-c:v", "libx264",
                                "-c:a", "aac",
                                str(temp_slice)
                            ]
                            fb_ret, fb_out, fb_err = self.runner.run_ffmpeg(slice_fb, dry_run=False)
                            if fb_ret != 0:
                                raise RuntimeError(f"FFmpeg slicing failed for {item.path} [{item.segment_formatted}]: {fb_err or s_err}")
                        elif s_ret != 0:
                            raise RuntimeError(f"FFmpeg slicing failed for {item.path}: {s_err}")
                        paths_to_concat.append(str(temp_slice))
                else:
                    paths_to_concat.append(item.path)

            # Build concat list manifest
            concat_content = []
            for p_str in paths_to_concat:
                escaped_path = p_str.replace("'", "'\\''")
                concat_content.append(f"file '{escaped_path}'")
            concat_text = "\n".join(concat_content) + "\n"

            concat_list_file = out_file.parent / f"{out_file.stem}_concat_list.txt"
            temp_files_to_clean.append(concat_list_file)
            if not dry_run:
                with open(concat_list_file, "w", encoding="utf-8") as f:
                    f.write(concat_text)

            # Prepare primary FFmpeg concat command
            args = [
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list_file),
            ]

            if reencode:
                args += ["-c:v", "libx264", "-c:a", "aac"]
            else:
                args += ["-c", "copy"]

            args.append(str(out_file))

            cmd_repr = "ffmpeg " + " ".join(f'"{a}"' if " " in a else a for a in args)
            retcode, stdout, stderr = self.runner.run_ffmpeg(args, dry_run=dry_run)

            # Fallback to filter_complex re-encode if stream copy fails
            if not dry_run and retcode != 0:
                if not reencode:
                    fc_args = ["-y"]
                    filter_inputs = []
                    for i, p_str in enumerate(paths_to_concat):
                        fc_args += ["-i", p_str]
                        filter_inputs.append(f"[{i}:v][{i}:a]")

                    n = len(paths_to_concat)
                    concat_filter = f"{''.join(filter_inputs)}concat=n={n}:v=1:a=1[outv][outa]"
                    fc_args += [
                        "-filter_complex", concat_filter,
                        "-map", "[outv]",
                        "-map", "[outa]",
                        "-c:v", "libx264",
                        "-c:a", "aac",
                        str(out_file)
                    ]
                    f_ret, f_out, f_err = self.runner.run_ffmpeg(fc_args, dry_run=False)
                    if f_ret != 0:
                        raise RuntimeError(f"FFmpeg merge failed: {f_err or stderr}")
                    cmd_repr = "ffmpeg " + " ".join(fc_args)
                    retcode = f_ret
                else:
                    raise RuntimeError(f"FFmpeg merge failed: {stderr}")

        finally:
            if not dry_run:
                for tmp in temp_files_to_clean:
                    if tmp.exists():
                        try:
                            tmp.unlink()
                        except Exception:
                            pass

        status = "success" if (dry_run or retcode == 0 or out_file.exists()) else "failed"
        action_word = "Planned merge of" if dry_run else "Successfully merged"
        msg = f"{action_word} {len(ordered_inputs)} video file(s) into {out_file.name}"

        return MergeResult(
            output_path=str(out_file),
            ordered_inputs=ordered_inputs,
            total_duration_sec=total_dur,
            total_duration_formatted=format_duration_short(total_dur),
            dry_run=dry_run,
            status=status,
            message=msg,
            ffmpeg_command=cmd_repr
        )
