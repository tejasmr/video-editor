---
name: video-editor
description: Deterministically perform video editing operations including splitting, cutting out segments, and merging multiple videos based on timestamp instructions and human prompts.
---

# Unified Video Editor Skill

This skill guides the AI agent in interpreting human video editing prompts, extracting explicit deterministic parameters, asking for clarification if needed, and invoking the specialized Python tools.

## Architecture & Principles
- **AI Agent's Responsibility**:
  - Understand human prompts (informal time notations, deletions, rankings, descriptions).
  - Calculate exact keep segments $[A, B], [C, D]$ (with $B \le C$).
  - Probe candidate video files (`probe_video.py`) to discover durations when files are described by length.
  - Ask the user questions if requirements are incomplete or ambiguous.
- **Python Tools' Responsibility**:
  - Pure deterministic execution (FFmpeg stream copy, keyframe handling, container concat).
  - Receive strictly typed, validated parameters (`--segments`, `--inputs`).

## Tools Reference
- [split_video.py](../../../scripts/split_video.py): Accepts `--input <path>` and `--segments <start-end ...>`.
- [merge_videos.py](../../../scripts/merge_videos.py): Accepts `--inputs <ordered_paths ...>` and optional `--output`.
- [probe_video.py](../../../scripts/probe_video.py): Inspects duration and codecs of files.
