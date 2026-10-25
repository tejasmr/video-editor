"""Deterministic Video Merger.

Merges multiple video files in the exact sequence provided by the caller.
All AI reasoning (duration matching, ordering decisions) is performed by the agent before calling this tool.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Union

from video_tools.ffmpeg_runner import FFmpegRunner, VideoInfo
from video_tools.time_parser import format_duration_short


@dataclass
class MergedFileInfo:
    """Information about an input file merged into the sequence."""
    position: int
    path: str
    duration_sec: float
    duration_formatted: str


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
    """Merges multiple videos in exact ordered sequence."""

    def __init__(self, runner: Optional[FFmpegRunner] = None):
        self.runner = runner or FFmpegRunner()

    def merge(
        self,
        video_paths: List[Union[str, Path]],
        output_path: Optional[Union[str, Path]] = None,
        reencode: bool = False,
        dry_run: bool = False
    ) -> MergeResult:
        """Merge videos in the exact order of the video_paths list.

        Args:
            video_paths: List of video paths in the desired concatenation order.
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

        # Collect info for each input file
        ordered_inputs: List[MergedFileInfo] = []
        for idx, p in enumerate(resolved_paths, start=1):
            dur = 0.0
            try:
                info = self.runner.probe_video(p)
                dur = info.duration
            except Exception:
                pass
            ordered_inputs.append(
                MergedFileInfo(
                    position=idx,
                    path=str(p),
                    duration_sec=dur,
                    duration_formatted=format_duration_short(dur)
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

        # Build concat list manifest
        concat_content = []
        for item in ordered_inputs:
            escaped_path = item.path.replace("'", "'\\''")
            concat_content.append(f"file '{escaped_path}'")
        concat_text = "\n".join(concat_content) + "\n"

        concat_list_file = out_file.parent / f"{out_file.stem}_concat_list.txt"
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
                for i, item in enumerate(ordered_inputs):
                    fc_args += ["-i", item.path]
                    filter_inputs.append(f"[{i}:v][{i}:a]")

                n = len(ordered_inputs)
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
            else:
                raise RuntimeError(f"FFmpeg merge failed: {stderr}")

        if not dry_run and concat_list_file.exists():
            try:
                concat_list_file.unlink()
            except Exception:
                pass

        status = "success" if (dry_run or out_file.exists()) else "failed"
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
