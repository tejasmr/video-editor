"""Tests for VideoSplitter."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from video_tools.ffmpeg_runner import FFmpegRunner, VideoInfo
from video_tools.splitter import VideoSplitter, SegmentSpec, OutputVideoSegment, SplitResult


class DummyRunner(FFmpegRunner):
    """Mock runner that doesn't require real FFmpeg binaries."""
    def __init__(self, fail_first=False, fail_all=False):
        super().__init__(ffmpeg_bin="ffmpeg_mock", ffprobe_bin="ffprobe_mock")
        self.executed_commands = []
        self.fail_first = fail_first
        self.fail_all = fail_all
        self.call_count = 0

    def probe_video(self, video_path: Path) -> VideoInfo:
        return VideoInfo(
            path=video_path,
            duration=700.0,
            video_codec="h264",
            audio_codec="aac"
        )

    def run_ffmpeg(self, args, dry_run=False):
        self.executed_commands.append(args)
        self.call_count += 1
        if not dry_run:
            if self.fail_all:
                return 1, "", "mock ffmpeg fatal failure"
            if self.fail_first and self.call_count == 1:
                return 1, "", "mock stream copy error"
        return 0, "mock_stdout", ""


class TestVideoSplitter(unittest.TestCase):

    def test_segment_spec_validation(self):
        with self.assertRaises(ValueError):
            SegmentSpec(start=-1.0, end=10.0)
        with self.assertRaises(ValueError):
            SegmentSpec(start=10.0, end=5.0)

        spec = SegmentSpec(start=5.0, end=15.0)
        self.assertEqual(spec.duration, 10.0)

    def test_split_result_serialization(self):
        res = SplitResult(
            input_path="vid.mp4",
            total_duration_sec=100.0,
            output_segments=[],
            dry_run=True,
            status="success",
            message="msg"
        )
        d = res.to_dict()
        self.assertEqual(d["status"], "success")
        j = res.to_json()
        self.assertIn('"status": "success"', j)

    def test_splitter_dry_run_with_string_ranges(self):
        runner = DummyRunner()
        splitter = VideoSplitter(runner=runner)

        segments = [("0:00", "7:29"), ("7:49", "11:33")]

        result = splitter.split(
            video_path="sample_movie.mp4",
            segments=segments,
            dry_run=True
        )

        self.assertTrue(result.dry_run)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.output_segments), 2)

        seg1 = result.output_segments[0]
        self.assertEqual(seg1.output_index, 1)
        self.assertEqual(seg1.start_sec, 0.0)
        self.assertEqual(seg1.end_sec, 449.0)
        self.assertEqual(seg1.duration_sec, 449.0)
        self.assertIn("part01_00-00_to_07-29", seg1.output_path)
        self.assertIn("-ss 0.0", seg1.ffmpeg_command)
        self.assertIn("-to 449.0", seg1.ffmpeg_command)

        seg2 = result.output_segments[1]
        self.assertEqual(seg2.output_index, 2)
        self.assertEqual(seg2.start_sec, 469.0)
        self.assertEqual(seg2.end_sec, 693.0)
        self.assertEqual(seg2.duration_sec, 224.0)
        self.assertIn("part02_07-49_to_11-33", seg2.output_path)

    def test_splitter_custom_names_and_output_dir(self):
        runner = DummyRunner()
        splitter = VideoSplitter(runner=runner)

        segments = [
            SegmentSpec(start=0.0, end=10.0, output_name="intro"),
            ("10.0", "20.0")
        ]

        result = splitter.split(
            video_path="input.mp4",
            segments=segments,
            output_dir="custom_out",
            output_names=["custom_intro.mp4", "custom_outro.mp4"],
            dry_run=True
        )

        self.assertEqual(len(result.output_segments), 2)
        self.assertIn("custom_intro.mp4", result.output_segments[0].output_path)
        self.assertIn("custom_outro.mp4", result.output_segments[1].output_path)

    def test_splitter_probe_exception_handled(self):
        runner = DummyRunner()
        runner.probe_video = MagicMock(side_effect=Exception("probe error"))
        splitter = VideoSplitter(runner=runner)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"content")
            tmp_path = tf.name

        try:
            result = splitter.split(
                video_path=tmp_path,
                segments=[("0:00", "1:00")],
                dry_run=True
            )
            self.assertEqual(result.total_duration_sec, 0.0)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_splitter_reencode_fatal_raises(self):
        runner = DummyRunner(fail_all=True)
        splitter = VideoSplitter(runner=runner)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"content")
            tmp_path = tf.name

        try:
            with self.assertRaises(RuntimeError) as ctx:
                splitter.split(
                    video_path=tmp_path,
                    segments=[("0:00", "1:00")],
                    reencode=True,
                    dry_run=False
                )
            self.assertIn("FFmpeg split failed for segment", str(ctx.exception))
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_splitter_validation_errors(self):
        runner = DummyRunner()
        splitter = VideoSplitter(runner=runner)

        # Overlapping segments
        with self.assertRaises(ValueError):
            splitter.split(video_path="test.mp4", segments=[("0:00", "5:00"), ("4:00", "7:00")], dry_run=True)

        # Empty segments
        with self.assertRaises(ValueError):
            splitter.split(video_path="test.mp4", segments=[], dry_run=True)

        # Invalid segment structure
        with self.assertRaises(ValueError):
            splitter.split(video_path="test.mp4", segments=["bad_seg"], dry_run=True)

        # Non-existent input file when not dry-run
        with self.assertRaises(FileNotFoundError):
            splitter.split(video_path="non_existent_12345.mp4", segments=[("0:00", "1:00")], dry_run=False)

    def test_splitter_execution_stream_copy_fallback_to_reencode(self):
        # Runner fails first time (stream copy), succeeds second time (re-encode)
        runner = DummyRunner(fail_first=True)
        splitter = VideoSplitter(runner=runner)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"content")
            tmp_path = tf.name

        try:
            result = splitter.split(
                video_path=tmp_path,
                segments=[("0:00", "1:00")],
                dry_run=False
            )
            self.assertEqual(result.status, "success")
            self.assertEqual(len(runner.executed_commands), 2)  # 1 copy attempt + 1 fallback
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_splitter_execution_stream_copy_fallback_fatal_raises(self):
        # Stream copy fails, then fallback re-encode also fails -> raises RuntimeError
        runner = DummyRunner(fail_all=True)
        splitter = VideoSplitter(runner=runner)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"content")
            tmp_path = tf.name

        try:
            with self.assertRaises(RuntimeError) as ctx:
                splitter.split(
                    video_path=tmp_path,
                    segments=[("0:00", "1:00")],
                    reencode=False,
                    dry_run=False
                )
            self.assertIn("FFmpeg split failed for segment", str(ctx.exception))
        finally:
            Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
