# Deterministic Video Editor Agent & Skills

[![CI](https://github.com/tejasmr/video-editor/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tejasmr/video-editor/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/tejasmr/video-editor/branch/main/graph/badge.svg)](https://codecov.io/gh/tejasmr/video-editor)

An agentic video editing toolkit designed for **Google Antigravity**.

---

## 🏛 Architecture & Philosophy

- **AI Agent (Reasoning Layer)**:
  - Understands human prompts with natural or informal phrasing.
  - Translates deletions and splits into explicit keep intervals $[A, B], [C, D]$.
  - Probes video candidates (`probe_video.py`) to discover durations when files are described by length (e.g. "1.41 file", "2:03 1st").
  - Asks the user clarifying questions whenever instructions are incomplete, ambiguous, or invalid.
- **Python Scripts (Deterministic Execution Layer)**:
  - Do not parse natural language prompts.
  - Receive strictly typed, validated inputs (`--segments`, `--inputs`).
  - Execute FFmpeg commands with lossless stream copy (`-c copy`) and fallback re-encoding.

---

## 📁 Repository Structure

```text
video-editor/
├── .agents/
│   ├── skills/
│   │   ├── video-split/
│   │   │   └── SKILL.md       # Skill guiding the agent on splitting
│   │   ├── video-merge/
│   │   │   └── SKILL.md       # Skill guiding the agent on merging & probing
│   │   └── video-editor/
│   │       └── SKILL.md       # Unified video editor skill
│   ├── agents/
│   │   └── video-editor-agent.md # Agent specification
│   └── rules/
│       └── AGENTS.md          # Workspace rules
├── video_tools/               # Core Python library
│   ├── __init__.py
│   ├── time_parser.py         # Timestamp parser (MM:SS, HH:MM:SS, seconds)
│   ├── ffmpeg_runner.py       # FFmpeg/FFprobe runner with pure-Python duration fallback
│   ├── splitter.py            # Video splitting engine
│   └── merger.py              # Video merging engine
├── scripts/                   # Pure deterministic CLI tools
│   ├── split_video.py         # Takes --input and explicit --segments
│   ├── merge_videos.py        # Takes explicit ordered --inputs
│   └── probe_video.py         # Inspects durations and codecs
├── tests/                     # Test suite
└── AGENTS.md
```

---

## 🛠 Deterministic Script Usage

### 1. Split Tool: `scripts/split_video.py`
Takes explicit segment intervals:
```powershell
python scripts/split_video.py --input "path/to/video.mp4" --segments 0:00-7:29 7:49-11:33
```

### 2. Merge Tool: `scripts/merge_videos.py`
Takes explicit ordered input paths:
```powershell
python scripts/merge_videos.py --inputs "take203.mp4" "take130.mp4" "take054.mp4" --output "merged.mp4"
```

### 3. Probe Tool: `scripts/probe_video.py`
Inspects video metadata (durations, resolutions, codecs):
```powershell
python scripts/probe_video.py file1.mp4 file2.mp4 --json
```

---

## 🧪 Testing

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```
All unit tests pass.
