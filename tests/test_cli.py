"""Tests for CLI scripts."""

import json
import subprocess
import sys
import unittest
from pathlib import Path


def run_cmd(cmd_list):
    res = subprocess.run(
        [sys.executable] + cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8"
    )
    return res


class TestCLI(unittest.TestCase):

    def test_split_cli_dry_run(self):
        script = str(Path("scripts/split_video.py").resolve())
        # Agent resolved prompt: 0:00 to 7:29 file 1, 7:49 to 11:33 file 2
        res = run_cmd([
            script,
            "-i", "fake_video.mp4",
            "-s", "0:00-7:29", "7:49-11:33",
            "--dry-run",
            "--json"
        ])
        self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["output_segments"]), 2)
        self.assertEqual(data["output_segments"][0]["duration_sec"], 449.0)
        self.assertEqual(data["output_segments"][1]["duration_sec"], 224.0)

    def test_merge_cli_dry_run(self):
        script = str(Path("scripts/merge_videos.py").resolve())
        # Agent resolved ordered inputs
        res = run_cmd([
            script,
            "-i", "vid_1.41.mp4", "vid_1.57.mp4",
            "--dry-run",
            "--json"
        ])
        self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["ordered_inputs"]), 2)


if __name__ == "__main__":
    unittest.main()
