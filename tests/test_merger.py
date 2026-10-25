"""Tests for VideoMerger."""

import unittest
from pathlib import Path
from video_tools.ffmpeg_runner import FFmpegRunner, VideoInfo
from video_tools.merger import VideoMerger


class DummyMergerRunner(FFmpegRunner):
    """Mock runner that returns mock metadata for different files."""
    def __init__(self, duration_map=None):
        super().__init__(ffmpeg_bin="ffmpeg_mock", ffprobe_bin="ffprobe_mock")
        self.duration_map = duration_map or {}
        self.executed_commands = []

    def probe_video(self, video_path: Path) -> VideoInfo:
        dur = self.duration_map.get(video_path.name, 100.0)
        return VideoInfo(
            path=video_path,
            duration=dur,
            video_codec="h264",
            audio_codec="aac"
        )

    def run_ffmpeg(self, args, dry_run=False):
        self.executed_commands.append(args)
        return 0, "mock_stdout", ""


class TestVideoMerger(unittest.TestCase):

    def test_merger_ordered_inputs(self):
        """Test merger receives exact ordered list determined by the agent."""
        dur_map = {
            "clip_alpha_0.54.mp4": 54.0,
            "clip_beta_2.03.mp4": 123.0,
            "clip_gamma_1.30.mp4": 90.0,
        }
        runner = DummyMergerRunner(dur_map)
        merger = VideoMerger(runner=runner)

        # The agent determined the order: 2:03 1st, 1:30 2nd, 0:54 3rd
        ordered_files = [
            "clip_beta_2.03.mp4",
            "clip_gamma_1.30.mp4",
            "clip_alpha_0.54.mp4"
        ]

        result = merger.merge(
            video_paths=ordered_files,
            output_path="final_merged.mp4",
            dry_run=True
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.ordered_inputs), 3)

        self.assertEqual(result.ordered_inputs[0].position, 1)
        self.assertIn("clip_beta_2.03.mp4", result.ordered_inputs[0].path)
        self.assertEqual(result.ordered_inputs[0].duration_sec, 123.0)

        self.assertEqual(result.ordered_inputs[1].position, 2)
        self.assertIn("clip_gamma_1.30.mp4", result.ordered_inputs[1].path)
        self.assertEqual(result.ordered_inputs[1].duration_sec, 90.0)

        self.assertEqual(result.ordered_inputs[2].position, 3)
        self.assertIn("clip_alpha_0.54.mp4", result.ordered_inputs[2].path)
        self.assertEqual(result.ordered_inputs[2].duration_sec, 54.0)

        self.assertEqual(result.total_duration_sec, 267.0)


if __name__ == "__main__":
    unittest.main()
