"""Video Editing Tools Package for deterministic splitting and merging."""

from video_tools.ffmpeg_runner import FFmpegRunner, VideoInfo
from video_tools.merger import MergeResult, MergedFileInfo, VideoMerger
from video_tools.splitter import OutputVideoSegment, SegmentSpec, SplitResult, VideoSplitter
from video_tools.time_parser import (
    format_duration_short,
    format_filename_range,
    format_timestamp,
    parse_timestamp,
)

__version__ = "1.0.0"

__all__ = [
    "FFmpegRunner",
    "VideoInfo",
    "VideoMerger",
    "MergeResult",
    "MergedFileInfo",
    "VideoSplitter",
    "SegmentSpec",
    "OutputVideoSegment",
    "SplitResult",
    "parse_timestamp",
    "format_timestamp",
    "format_duration_short",
    "format_filename_range",
    "__version__",
]
