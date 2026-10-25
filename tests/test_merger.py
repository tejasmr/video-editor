"""Tests for VideoMerger."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from video_tools.ffmpeg_runner import FFmpegRunner, VideoInfo
from video_tools.merger import VideoMerger, MergeResult, MergedFileInfo


class DummyMergerRunner(FFmpegRunner):
    """Mock runner that returns mock metadata for different files."""
    def __init__(self, duration_map=None, fail_first=False, fail_all=False):
        super().__init__(ffmpeg_bin="ffmpeg_mock", ffprobe_bin="ffprobe_mock")
        self.duration_map = duration_map or {}
        self.executed_commands = []
        self.fail_first = fail_first
        self.fail_all = fail_all
        self.call_count = 0

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
        self.call_count += 1
        if not dry_run:
            if self.fail_all:
                return 1, "", "mock fatal error"
            if self.fail_first and self.call_count == 1:
                return 1, "", "concat stream copy failed"
        return 0, "mock_stdout", ""


class TestVideoMerger(unittest.TestCase):

    def test_merge_result_serialization(self):
        res = MergeResult(
            output_path="out.mp4",
            ordered_inputs=[],
            total_duration_sec=10.0,
            total_duration_formatted="0:10",
            dry_run=True,
            status="success",
            message="done",
            ffmpeg_command="ffmpeg cmd"
        )
        self.assertEqual(res.to_dict()["status"], "success")
        self.assertIn('"status": "success"', res.to_json())

    def test_merger_ordered_inputs(self):
        """Test merger receives exact ordered list determined by the agent."""
        dur_map = {
            "clip_alpha_0.54.mp4": 54.0,
            "clip_beta_2.03.mp4": 123.0,
            "clip_gamma_1.30.mp4": 90.0,
        }
        runner = DummyMergerRunner(dur_map)
        merger = VideoMerger(runner=runner)

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
        self.assertEqual(result.ordered_inputs[0].duration_sec, 123.0)
        self.assertEqual(result.ordered_inputs[1].position, 2)
        self.assertEqual(result.ordered_inputs[1].duration_sec, 90.0)
        self.assertEqual(result.ordered_inputs[2].position, 3)
        self.assertEqual(result.ordered_inputs[2].duration_sec, 54.0)
        self.assertEqual(result.total_duration_sec, 267.0)

    def test_merger_empty_paths_raises_error(self):
        merger = VideoMerger()
        with self.assertRaises(ValueError):
            merger.merge(video_paths=[])

    def test_merger_missing_file_raises_error(self):
        merger = VideoMerger()
        with self.assertRaises(FileNotFoundError):
            merger.merge(video_paths=["missing_1.mp4", "missing_2.mp4"], dry_run=False)

    def test_merger_execution_stream_copy_fallback(self):
        runner = DummyMergerRunner(fail_first=True)
        merger = VideoMerger(runner=runner)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f1, \
             tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f2:
            f1.write(b"video 1")
            f2.write(b"video 2")
            p1, p2 = Path(f1.name), Path(f2.name)

        out_path = p1.parent / "test_merged_output.mp4"
        try:
            result = merger.merge(
                video_paths=[p1, p2],
                output_path=out_path,
                dry_run=False
            )
            self.assertEqual(result.status, "success")
            self.assertEqual(len(runner.executed_commands), 2)  # 1 copy + 1 filter_complex fallback
            self.assertIn("-filter_complex", runner.executed_commands[1])
        finally:
            p1.unlink(missing_ok=True)
            p2.unlink(missing_ok=True)
            out_path.unlink(missing_ok=True)

    def test_merger_execution_stream_copy_fallback_fatal_raises(self):
        # Stream copy fails, then fallback re-encode also fails -> raises RuntimeError
        runner = DummyMergerRunner(fail_all=True)
        merger = VideoMerger(runner=runner)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f1:
            f1.write(b"video 1")
            p1 = Path(f1.name)

        try:
            with self.assertRaises(RuntimeError) as ctx:
                merger.merge(video_paths=[p1], reencode=False, dry_run=False)
            self.assertIn("FFmpeg merge failed:", str(ctx.exception))
        finally:
            p1.unlink(missing_ok=True)

    def test_merger_cleanup_exception_handled(self):
        runner = DummyMergerRunner()
        merger = VideoMerger(runner=runner)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f1:
            f1.write(b"video")
            p1 = Path(f1.name)
        try:
            with patch("pathlib.Path.unlink", side_effect=OSError("unlink error")):
                res = merger.merge(video_paths=[p1], dry_run=False)
                self.assertEqual(res.status, "success")
        finally:
            import os
            try:
                os.remove(p1)
            except Exception:
                pass

    def test_merger_execution_fatal_failure_raises(self):
        runner = DummyMergerRunner(fail_all=True)
        merger = VideoMerger(runner=runner)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f1:
            f1.write(b"video 1")
            p1 = Path(f1.name)

        try:
            with self.assertRaises(RuntimeError):
                merger.merge(video_paths=[p1], reencode=True, dry_run=False)
        finally:
            p1.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
