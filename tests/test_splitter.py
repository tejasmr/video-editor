"""Tests for VideoSplitter."""

import tempfile
import unittest
from pathlib import Path
from video_tools.ffmpeg_runner import FFmpegRunner, VideoInfo
from video_tools.splitter import VideoSplitter, SegmentSpec


class DummyRunner(FFmpegRunner):
    """Mock runner that doesn't require real FFmpeg binaries."""
    def __init__(self):
        super().__init__(ffmpeg_bin="ffmpeg_mock", ffprobe_bin="ffprobe_mock")
        self.executed_commands = []

    def probe_video(self, video_path: Path) -> VideoInfo:
        return VideoInfo(
            path=video_path,
            duration=700.0,
            video_codec="h264",
            audio_codec="aac"
        )

    def run_ffmpeg(self, args, dry_run=False):
        self.executed_commands.append(args)
        return 0, "mock_stdout", ""


class TestVideoSplitter(unittest.TestCase):

    def test_splitter_dry_run_with_string_ranges(self):
        runner = DummyRunner()
        splitter = VideoSplitter(runner=runner)

        # Agent resolved Prompt 1 to: 0:00-7:29 and 7:49-11:33
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

    def test_splitter_single_segment(self):
        runner = DummyRunner()
        splitter = VideoSplitter(runner=runner)

        # Agent resolved Prompt 2 (0:00-1:39 delete, 1:40 to 5:34 keep)
        segments = [("1:40", "5:34")]

        result = splitter.split(
            video_path="lecture.mp4",
            segments=segments,
            dry_run=True
        )

        self.assertEqual(len(result.output_segments), 1)
        seg = result.output_segments[0]
        self.assertEqual(seg.start_sec, 100.0)
        self.assertEqual(seg.end_sec, 334.0)
        self.assertEqual(seg.duration_sec, 234.0)

    def test_splitter_overlapping_segments_raises_error(self):
        runner = DummyRunner()
        splitter = VideoSplitter(runner=runner)

        overlapping = [("0:00", "5:00"), ("4:00", "7:00")]
        with self.assertRaises(ValueError):
            splitter.split(
                video_path="test.mp4",
                segments=overlapping,
                dry_run=True
            )

    def test_splitter_execution_calls_runner(self):
        runner = DummyRunner()
        splitter = VideoSplitter(runner=runner)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(b"fake video content")
            tmp_path = tf.name

        try:
            segments = [("0:00", "3:50"), ("4:04", "7:46")]
            result = splitter.split(
                video_path=tmp_path,
                segments=segments,
                dry_run=False
            )

            self.assertEqual(len(runner.executed_commands), 2)
            self.assertIn("-to", runner.executed_commands[0])
        finally:
            Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
