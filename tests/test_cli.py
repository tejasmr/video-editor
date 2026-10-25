"""Tests for CLI scripts (split_video.py, merge_videos.py, probe_video.py)."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts import merge_videos, probe_video, split_video
from video_tools.ffmpeg_runner import VideoInfo


class TestCLI(unittest.TestCase):

    # -------------------------------------------------------------
    # Split Video CLI Tests
    # -------------------------------------------------------------
    def test_split_cli_dry_run_json(self):
        with patch("sys.argv", [
            "split_video.py",
            "-i", "sample.mp4",
            "-s", "0:00-7:29", "7:49-11:33",
            "--dry-run",
            "--json"
        ]), patch("sys.stdout", new=io.StringIO()) as fake_out:
            split_video.main()
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["status"], "success")
            self.assertEqual(len(data["output_segments"]), 2)

    def test_split_cli_dry_run_human_summary(self):
        with patch("sys.argv", [
            "split_video.py",
            "-i", "sample.mp4",
            "-s", "0:00-7:29", "7:49-11:33",
            "--dry-run"
        ]), patch("sys.stdout", new=io.StringIO()) as fake_out:
            split_video.main()
            output = fake_out.getvalue()
            self.assertIn("VIDEO SPLIT SUMMARY", output)
            self.assertIn("Part 01:", output)
            self.assertIn("Part 02:", output)

    def test_split_cli_custom_names_and_reencode(self):
        with patch("sys.argv", [
            "split_video.py",
            "-i", "sample.mp4",
            "-s", "0:00-1:00",
            "--output-names", "intro.mp4",
            "--output-dir", "out_dir",
            "--reencode",
            "--dry-run",
            "--json"
        ]), patch("sys.stdout", new=io.StringIO()) as fake_out:
            split_video.main()
            data = json.loads(fake_out.getvalue())
            self.assertIn("intro.mp4", data["output_segments"][0]["output_path"])

    def test_split_cli_file_not_found(self):
        with patch("sys.argv", [
            "split_video.py",
            "-i", "non_existent_video_123.mp4",
            "-s", "0:00-1:00"
        ]), patch("sys.stderr", new=io.StringIO()) as fake_err:
            with self.assertRaises(SystemExit) as ctx:
                split_video.main()
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("Input video not found", fake_err.getvalue())

    def test_split_cli_invalid_segment_format(self):
        with patch("sys.argv", [
            "split_video.py",
            "-i", "sample.mp4",
            "-s", "invalid_segment_token",
            "--dry-run"
        ]), patch("sys.stderr", new=io.StringIO()) as fake_err:
            with self.assertRaises(SystemExit) as ctx:
                split_video.main()
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("Could not parse segment range", fake_err.getvalue())

    def test_split_cli_exception_handling(self):
        # Overlapping segments triggers ValueError inside splitter
        with patch("sys.argv", [
            "split_video.py",
            "-i", "sample.mp4",
            "-s", "0:00-5:00", "4:00-7:00",
            "--dry-run"
        ]), patch("sys.stderr", new=io.StringIO()) as fake_err:
            with self.assertRaises(SystemExit) as ctx:
                split_video.main()
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("Error during video split:", fake_err.getvalue())

    # -------------------------------------------------------------
    # Merge Videos CLI Tests
    # -------------------------------------------------------------
    def test_merge_cli_dry_run_json(self):
        with patch("sys.argv", [
            "merge_videos.py",
            "-i", "clip1.mp4", "clip2.mp4",
            "--dry-run",
            "--json"
        ]), patch("sys.stdout", new=io.StringIO()) as fake_out:
            merge_videos.main()
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["status"], "success")
            self.assertEqual(len(data["ordered_inputs"]), 2)

    def test_merge_cli_dry_run_human_summary(self):
        with patch("sys.argv", [
            "merge_videos.py",
            "-i", "clip1.mp4", "clip2.mp4",
            "-o", "custom_merged.mp4",
            "--dry-run"
        ]), patch("sys.stdout", new=io.StringIO()) as fake_out:
            merge_videos.main()
            output = fake_out.getvalue()
            self.assertIn("VIDEO MERGE SUMMARY", output)
            self.assertIn("custom_merged.mp4", output)

    def test_merge_cli_with_segments_dry_run(self):
        with patch("sys.argv", [
            "merge_videos.py",
            "-i", "clip1.mp4", "clip2.mp4",
            "-s", "0:00-1:30", "full",
            "--dry-run"
        ]), patch("sys.stdout", new=io.StringIO()) as fake_out:
            merge_videos.main()
            output = fake_out.getvalue()
            self.assertIn("VIDEO MERGE SUMMARY", output)
            self.assertIn("00:00-01:30", output)

    def test_merge_cli_file_not_found(self):
        with patch("sys.argv", [
            "merge_videos.py",
            "-i", "non_existent_a.mp4", "non_existent_b.mp4"
        ]), patch("sys.stderr", new=io.StringIO()) as fake_err:
            with self.assertRaises(SystemExit) as ctx:
                merge_videos.main()
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("Input video not found", fake_err.getvalue())

    def test_merge_cli_exception_handling(self):
        with patch("sys.argv", [
            "merge_videos.py",
            "-i", "clip1.mp4",
            "--dry-run"
        ]), patch.object(merge_videos.VideoMerger, "merge", side_effect=RuntimeError("merge boom")), \
           patch("sys.stderr", new=io.StringIO()) as fake_err:
            with self.assertRaises(SystemExit) as ctx:
                merge_videos.main()
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("Error during video merge: merge boom", fake_err.getvalue())

    # -------------------------------------------------------------
    # Probe Video CLI Tests
    # -------------------------------------------------------------
    def test_probe_cli_json(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"video bytes")
            tmp_p = Path(tf.name)

        try:
            with patch("sys.argv", [
                "probe_video.py",
                str(tmp_p),
                "--json"
            ]), patch("sys.stdout", new=io.StringIO()) as fake_out:
                probe_video.main()
                data = json.loads(fake_out.getvalue())
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]["filename"], tmp_p.name)
        finally:
            tmp_p.unlink(missing_ok=True)

    def test_probe_cli_human_summary(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"video bytes")
            tmp_p = Path(tf.name)

        fake_info = VideoInfo(
            path=tmp_p,
            duration=120.0,
            width=1920,
            height=1080,
            fps=30.0,
            video_codec="h264",
            audio_codec="aac"
        )

        try:
            with patch("sys.argv", [
                "probe_video.py",
                str(tmp_p)
            ]), patch.object(probe_video.FFmpegRunner, "probe_video", return_value=fake_info), \
               patch("sys.stdout", new=io.StringIO()) as fake_out:
                probe_video.main()
                output = fake_out.getvalue()
                self.assertIn("VIDEO PROBE METADATA", output)
                self.assertIn("1920x1080 @ 30.00fps", output)
                self.assertIn("v=h264, a=aac", output)
        finally:
            tmp_p.unlink(missing_ok=True)

    def test_probe_cli_file_not_found_warning(self):
        with patch("sys.argv", [
            "probe_video.py",
            "completely_missing_file_xyz.mp4"
        ]), patch("sys.stderr", new=io.StringIO()) as fake_err:
            probe_video.main()
            self.assertIn("Warning: File not found", fake_err.getvalue())

    def test_package_exports(self):
        import video_tools
        self.assertEqual(video_tools.__version__, "1.0.0")
        self.assertTrue(hasattr(video_tools, "VideoSplitter"))
        self.assertTrue(hasattr(video_tools, "VideoMerger"))
        self.assertTrue(hasattr(video_tools, "FFmpegRunner"))
        self.assertTrue(hasattr(video_tools, "parse_timestamp"))


if __name__ == "__main__":
    unittest.main()
