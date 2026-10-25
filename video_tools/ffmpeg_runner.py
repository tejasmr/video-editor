"""FFmpeg and FFprobe execution layer with auto-discovery and fallbacks."""

import json
import os
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class VideoInfo:
    """Metadata extracted from a video file."""
    path: Path
    duration: float
    width: Optional[int] = None
    height: Optional[int] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    fps: Optional[float] = None
    size_bytes: int = 0
    format_name: Optional[str] = None


class FFmpegRunner:
    """Manages discovery and execution of FFmpeg/FFprobe binaries."""

    def __init__(self, ffmpeg_bin: Optional[str] = None, ffprobe_bin: Optional[str] = None):
        self.ffmpeg_bin = ffmpeg_bin or self._find_binary("ffmpeg")
        self.ffprobe_bin = ffprobe_bin or self._find_binary("ffprobe")

    @staticmethod
    def _find_binary(name: str) -> Optional[str]:
        """Look for binary in env, PATH, or standard installation directories."""
        # Check env var
        env_var = f"{name.upper()}_PATH"
        if os.environ.get(env_var):
            p = os.environ[env_var]
            if os.path.isfile(p):
                return p

        # Check standard PATH
        which_path = shutil.which(name)
        if which_path:
            return which_path

        # Check imageio_ffmpeg if available
        if name == "ffmpeg":
            try:
                import imageio_ffmpeg
                exe = imageio_ffmpeg.get_ffmpeg_exe()
                if exe and os.path.isfile(exe):
                    return exe
            except Exception:
                pass

        # Check common platform directories
        candidates: List[str] = []
        if os.name == "nt":
            candidates.extend([
                rf"C:\ffmpeg\bin\{name}.exe",
                rf"C:\ProgramData\chocolatey\bin\{name}.exe",
                rf"C:\Program Files\ffmpeg\bin\{name}.exe",
                rf"C:\tools\ffmpeg\bin\{name}.exe",
                os.path.join(os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Packages"), f"{name}.exe"),
            ])
        else:
            candidates.extend([
                f"/usr/bin/{name}",
                f"/usr/local/bin/{name}",
                f"/opt/homebrew/bin/{name}",
            ])

        for c in candidates:
            if os.path.isfile(c):
                return c

        return None

    @property
    def is_ffmpeg_available(self) -> bool:
        return self.ffmpeg_bin is not None

    @property
    def is_ffprobe_available(self) -> bool:
        return self.ffprobe_bin is not None

    def require_ffmpeg(self):
        """Raise an informative error if ffmpeg is not available."""
        if not self.is_ffmpeg_available:
            raise RuntimeError(
                "FFmpeg executable not found. Please install FFmpeg and ensure it is in your PATH.\n"
                "Installation options on Windows:\n"
                "  - Chocolatey: choco install ffmpeg -y\n"
                "  - Winget:     winget install Gyan.FFmpeg\n"
                "  - Direct:     Download from https://www.gyan.dev/ffmpeg/builds/ and add to PATH or set FFMPEG_PATH."
            )

    def run_ffmpeg(
        self,
        args: List[str],
        dry_run: bool = False
    ) -> Tuple[int, str, str]:
        """Execute ffmpeg with given arguments."""
        cmd = [self.ffmpeg_bin or "ffmpeg"] + args
        if dry_run:
            cmd_str = subprocess.list2cmdline(cmd)
            return (0, f"[DRY-RUN] Would execute: {cmd_str}", "")

        self.require_ffmpeg()
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return proc.returncode, proc.stdout, proc.stderr

    def probe_video(self, video_path: Path) -> VideoInfo:
        """Inspect video file to retrieve duration and stream metadata."""
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        size_bytes = video_path.stat().st_size

        # Try ffprobe if available
        if self.is_ffprobe_available:
            try:
                cmd = [
                    self.ffprobe_bin,
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    str(video_path.resolve())
                ]
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )
                if proc.returncode == 0:
                    data = json.loads(proc.stdout)
                    fmt = data.get("format", {})
                    duration = float(fmt.get("duration", 0.0))
                    format_name = fmt.get("format_name", "")

                    v_codec = None
                    a_codec = None
                    width = None
                    height = None
                    fps = None

                    for s in data.get("streams", []):
                        codec_type = s.get("codec_type")
                        if codec_type == "video" and v_codec is None:
                            v_codec = s.get("codec_name")
                            width = s.get("width")
                            height = s.get("height")
                            r_fps = s.get("r_frame_rate", "")
                            if "/" in r_fps:
                                num, den = r_fps.split("/")
                                if float(den) > 0:
                                    fps = float(num) / float(den)
                        elif codec_type == "audio" and a_codec is None:
                            a_codec = s.get("codec_name")

                    return VideoInfo(
                        path=video_path,
                        duration=duration,
                        width=width,
                        height=height,
                        video_codec=v_codec,
                        audio_codec=a_codec,
                        fps=fps,
                        size_bytes=size_bytes,
                        format_name=format_name
                    )
            except Exception:
                pass

        # Fallback 1: Pure-Python MP4 box parser
        mp4_dur = self._read_mp4_duration(video_path)
        if mp4_dur is not None:
            return VideoInfo(
                path=video_path,
                duration=mp4_dur,
                size_bytes=size_bytes,
                format_name="mp4"
            )

        # Fallback 2: Check filename for duration hints (e.g. vid_1.41.mp4 or 2_03.mp4)
        from video_tools.time_parser import parse_timestamp
        stem = video_path.stem
        import re
        dur_m = re.search(r"(\d+[:._]\d{2})", stem)
        if dur_m:
            try:
                candidate = dur_m.group(1).replace("_", ":")
                dur_parsed = parse_timestamp(candidate)
                return VideoInfo(
                    path=video_path,
                    duration=dur_parsed,
                    size_bytes=size_bytes,
                    format_name="unknown"
                )
            except Exception:
                pass

        # Default fallback
        return VideoInfo(
            path=video_path,
            duration=0.0,
            size_bytes=size_bytes,
            format_name="unknown"
        )

    @staticmethod
    def _read_mp4_duration(file_path: Path) -> Optional[float]:
        """Pure-Python MP4 duration reader by parsing moov/mvhd atom."""
        try:
            with open(file_path, "rb") as f:
                while True:
                    header = f.read(8)
                    if len(header) < 8:
                        break
                    atom_size, atom_type = struct.unpack(">I4s", header)
                    atom_type_str = atom_type.decode("latin1", errors="ignore")

                    if atom_size == 1:
                        # 64-bit size
                        atom_size = struct.unpack(">Q", f.read(8))[0]
                        data_size = atom_size - 16
                    else:
                        data_size = atom_size - 8

                    if atom_type_str == "moov":
                        # Look inside moov
                        moov_bytes = f.read(data_size)
                        mvhd_idx = moov_bytes.find(b"mvhd")
                        if mvhd_idx != -1:
                            # mvhd atom starts 4 bytes before 'mvhd' (the 4-byte size)
                            mvhd_data = moov_bytes[mvhd_idx + 4:]
                            version = mvhd_data[0]
                            if version == 0:
                                # v0: creation(4), mod(4), timescale(4), duration(4)
                                timescale, duration = struct.unpack(">II", mvhd_data[12:20])
                            else:
                                # v1: creation(8), mod(8), timescale(4), duration(8)
                                timescale, duration = struct.unpack(">IQ", mvhd_data[20:32])
                            if timescale > 0:
                                return float(duration) / float(timescale)
                        break
                    else:
                        if data_size > 0:
                            f.seek(data_size, os.SEEK_CUR)
                        else:
                            break
        except Exception:
            pass
        return None

