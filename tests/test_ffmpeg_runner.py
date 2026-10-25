"""Comprehensive tests for FFmpegRunner."""

import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from video_tools.ffmpeg_runner import FFmpegRunner, VideoInfo


class TestFFmpegRunner(unittest.TestCase):

    def test_find_binary_with_env(self):
        with patch.dict(os.environ, {"FFMPEG_PATH": __file__}):
            found = FFmpegRunner._find_binary("ffmpeg")
            self.assertEqual(found, __file__)

    def test_find_binary_with_which(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch("shutil.which", return_value="/mock/bin/ffmpeg"):
            found = FFmpegRunner._find_binary("ffmpeg")
            self.assertEqual(found, "/mock/bin/ffmpeg")

    def test_find_binary_not_found(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch("shutil.which", return_value=None), \
             patch("builtins.open", side_effect=FileNotFoundError), \
             patch("os.path.isfile", return_value=False):
            with patch("video_tools.ffmpeg_runner.FFmpegRunner._find_binary", return_value=None):
                runner = FFmpegRunner(ffmpeg_bin=None, ffprobe_bin=None)
                self.assertFalse(runner.is_ffmpeg_available)
                self.assertFalse(runner.is_ffprobe_available)

    def test_require_ffmpeg_raises_when_missing(self):
        runner = FFmpegRunner(ffmpeg_bin=None)
        runner.ffmpeg_bin = None
        with self.assertRaises(RuntimeError) as ctx:
            runner.require_ffmpeg()
        self.assertIn("FFmpeg executable not found", str(ctx.exception))

    def test_require_ffmpeg_succeeds_when_present(self):
        runner = FFmpegRunner(ffmpeg_bin="/bin/ffmpeg")
        # Should not raise
        runner.require_ffmpeg()

    def test_run_ffmpeg_dry_run(self):
        runner = FFmpegRunner(ffmpeg_bin="/bin/ffmpeg")
        code, stdout, stderr = runner.run_ffmpeg(["-i", "test.mp4", "out.mp4"], dry_run=True)
        self.assertEqual(code, 0)
        self.assertIn("[DRY-RUN] Would execute:", stdout)
        self.assertEqual(stderr, "")

    @patch("subprocess.run")
    def test_run_ffmpeg_real_execution(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "done"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        runner = FFmpegRunner(ffmpeg_bin="/bin/ffmpeg")
        code, stdout, stderr = runner.run_ffmpeg(["-i", "test.mp4", "out.mp4"], dry_run=False)
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "done")

    def test_probe_video_file_not_found(self):
        runner = FFmpegRunner()
        with self.assertRaises(FileNotFoundError):
            runner.probe_video(Path("non_existent_file_xyz.mp4"))

    @patch("subprocess.run")
    def test_probe_video_with_ffprobe_success(self, mock_run):
        probe_data = {
            "format": {"duration": "123.45", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1"
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac"
                }
            ]
        }
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(probe_data)
        mock_run.return_value = mock_proc

        runner = FFmpegRunner(ffprobe_bin="/bin/ffprobe")
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"content")
            tmp_path = Path(tf.name)

        try:
            info = runner.probe_video(tmp_path)
            self.assertEqual(info.duration, 123.45)
            self.assertEqual(info.video_codec, "h264")
            self.assertEqual(info.audio_codec, "aac")
            self.assertEqual(info.width, 1920)
            self.assertEqual(info.height, 1080)
            self.assertEqual(info.fps, 30.0)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_probe_video_pure_python_mp4_fallback(self):
        # Build synthetic MP4 with moov/mvhd atom
        mvhd_body = struct.pack(">B3sIIII", 0, b"\x00\x00\x00", 0, 0, 1000, 7500)
        mvhd_atom = struct.pack(">I4s", len(mvhd_body) + 8, b"mvhd") + mvhd_body
        moov_atom = struct.pack(">I4s", len(mvhd_atom) + 8, b"moov") + mvhd_atom

        runner = FFmpegRunner(ffprobe_bin=None)  # No ffprobe

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(moov_atom)
            tmp_path = Path(tf.name)

        try:
            info = runner.probe_video(tmp_path)
            self.assertEqual(info.duration, 7.5)
            self.assertEqual(info.format_name, "mp4")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_probe_video_filename_duration_hint_fallback(self):
        runner = FFmpegRunner(ffprobe_bin=None)

        with tempfile.NamedTemporaryFile(prefix="clip_2.03_", suffix=".mp4", delete=False) as tf:
            tf.write(b"raw data without atom")
            tmp_path = Path(tf.name)

        try:
            info = runner.probe_video(tmp_path)
            self.assertEqual(info.duration, 123.0)  # 2:03 = 123s
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_probe_video_default_unknown_fallback(self):
        runner = FFmpegRunner(ffprobe_bin=None)

        with tempfile.NamedTemporaryFile(prefix="video_", suffix=".dat", delete=False) as tf:
            tf.write(b"random bytes")
            tmp_path = Path(tf.name)

        try:
            info = runner.probe_video(tmp_path)
            self.assertEqual(info.duration, 0.0)
            self.assertEqual(info.format_name, "unknown")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_read_mp4_duration_v1_and_ftyp_and_64bit(self):
        # 1. Test v1 mvhd atom
        mvhd_body_v1 = struct.pack(">B3sQQIQ", 1, b"\x00\x00\x00", 0, 0, 1000, 15000)
        mvhd_atom_v1 = struct.pack(">I4s", len(mvhd_body_v1) + 8, b"mvhd") + mvhd_body_v1
        moov_atom_v1 = struct.pack(">I4s", len(mvhd_atom_v1) + 8, b"moov") + mvhd_atom_v1

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(moov_atom_v1)
            p1 = Path(tf.name)

        try:
            dur = FFmpegRunner._read_mp4_duration(p1)
            self.assertEqual(dur, 15.0)
        finally:
            p1.unlink(missing_ok=True)

        # 2. Test 64-bit atom size (atom_size == 1)
        # ftyp atom with 64-bit size: header has size 1, then type, then 64-bit length
        ftyp_payload = b"isom" + b"\x00\x00\x02\x00"
        total_ftyp_len = 16 + len(ftyp_payload)
        ftyp_64 = struct.pack(">I4sQ", 1, b"ftyp", total_ftyp_len) + ftyp_payload

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(ftyp_64 + moov_atom_v1)
            p2 = Path(tf.name)

        try:
            dur2 = FFmpegRunner._read_mp4_duration(p2)
            self.assertEqual(dur2, 15.0)
        finally:
            p2.unlink(missing_ok=True)


    def test_probe_video_ffprobe_json_error_falls_back(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "not valid json {{"
        runner = FFmpegRunner(ffprobe_bin="/bin/ffprobe")

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"content")
            tmp_path = Path(tf.name)

        try:
            with patch("subprocess.run", return_value=mock_proc):
                info = runner.probe_video(tmp_path)
                self.assertEqual(info.duration, 0.0)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_probe_video_duration_hint_invalid_parse(self):
        runner = FFmpegRunner(ffprobe_bin=None)
        with tempfile.NamedTemporaryFile(prefix="clip_99.99_", suffix=".mp4", delete=False) as tf:
            tf.write(b"content")
            tmp_path = Path(tf.name)

        try:
            with patch("video_tools.time_parser.parse_timestamp", side_effect=ValueError("bad time")):
                info = runner.probe_video(tmp_path)
                self.assertEqual(info.duration, 0.0)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_find_binary_windows_candidate(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch("shutil.which", return_value=None), \
             patch("os.name", "nt"), \
             patch("os.path.isfile", side_effect=lambda p: str(p) == r"C:\ffmpeg\bin\ffmpeg.exe"):
            found = FFmpegRunner._find_binary("ffmpeg")
            self.assertEqual(found, r"C:\ffmpeg\bin\ffmpeg.exe")

    def test_find_binary_posix_candidate(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch("shutil.which", return_value=None), \
             patch("os.name", "posix"), \
             patch("os.path.isfile", side_effect=lambda p: str(p) == "/usr/bin/ffmpeg"):
            found = FFmpegRunner._find_binary("ffmpeg")
            self.assertEqual(found, "/usr/bin/ffmpeg")

    def test_read_mp4_duration_atom_zero_data_size(self):
        # Create an atom with size 8 (so data_size is 0)
        zero_atom = struct.pack(">I4s", 8, b"free")
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(zero_atom)
            p = Path(tf.name)

        try:
            dur = FFmpegRunner._read_mp4_duration(p)
            self.assertIsNone(dur)
        finally:
            p.unlink(missing_ok=True)


    def test_read_mp4_duration_moov_without_mvhd(self):
        # moov atom containing no mvhd atom
        moov_atom = struct.pack(">I4s", 16, b"moov") + b"emptycontent1234"
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(moov_atom)
            p = Path(tf.name)
        try:
            dur = FFmpegRunner._read_mp4_duration(p)
            self.assertIsNone(dur)
        finally:
            p.unlink(missing_ok=True)

    def test_read_mp4_duration_open_exception_handled(self):
        with patch("builtins.open", side_effect=OSError("disk read error")):
            dur = FFmpegRunner._read_mp4_duration(Path("some_file.mp4"))
            self.assertIsNone(dur)

    def test_find_binary_imageio_exception_handled(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch("shutil.which", return_value=None), \
             patch.dict("sys.modules", {"imageio_ffmpeg": None}):
            found = FFmpegRunner._find_binary("ffmpeg")
            # Should gracefully handle import error
            self.assertIsNone(found)


if __name__ == "__main__":
    unittest.main()
