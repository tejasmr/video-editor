# Deterministic Video Editor Agent & Skills

[![CI](https://github.com/tejasmr/video-editor/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tejasmr/video-editor/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/tejasmr/video-editor/graph/badge.svg?token=9bGCgel4jl)](https://codecov.io/gh/tejasmr/video-editor)

An agentic video editing toolkit designed for **Google Antigravity**.

---

## 🏛 Architecture & Philosophy

- **AI Agent (Reasoning Layer)**:
  - Understands human prompts with natural or informal phrasing (e.g. deletions, numbered cuts, duration references).
  - Translates deletions and splits into explicit keep intervals $[A, B], [C, D]$ where $B \le C$.
  - Probes candidate files using `scripts/probe_video.py` to match files by length (e.g. *"the 1.41 file"*, *"2:03 1st, 1:30 2nd"*).
  - Asks the user clarifying questions whenever instructions are incomplete, ambiguous, or invalid.
- **Python Scripts (Deterministic Execution Layer)**:
  - Pure executors that do not parse natural language prompts.
  - Accept strictly typed, validated inputs (`--segments`, `--inputs`).
  - Execute FFmpeg commands with lossless stream copy (`-c copy`) and automated fallback to re-encoding if keyframe boundaries or codec mismatches require it.

---

## 📁 Repository Structure

```text
video-editor/
├── .agents/
│   ├── skills/
│   │   ├── video-split/
│   │   │   └── SKILL.md       # Skill guiding the agent on splitting & deletions
│   │   ├── video-merge/
│   │   │   └── SKILL.md       # Skill guiding the agent on merging & duration matching
│   │   └── video-editor/
│   │       └── SKILL.md       # Unified video editing skill
│   ├── agents/
│   │   └── video-editor-agent.md # Agent specification
│   └── rules/
│       └── AGENTS.md          # Workspace rules
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI & Codecov workflow
├── video_tools/               # Core Python library
│   ├── __init__.py
│   ├── time_parser.py         # Timestamp parsing (MM:SS, HH:MM:SS, seconds, M.SS)
│   ├── ffmpeg_runner.py       # Cross-platform binary discovery & pure-Python MP4 duration fallback
│   ├── splitter.py            # Video splitting engine
│   └── merger.py              # Video concatenation & fallback engine
├── scripts/                   # CLI executable tools
│   ├── split_video.py         # Splits video by explicit segments
│   ├── merge_videos.py        # Merges videos by explicit ordered inputs
│   └── probe_video.py         # Inspects durations, resolution, and codecs
├── tests/                     # 100% test coverage suite
├── AGENTS.md                  # Project rules
├── pyproject.toml             # Package configuration & pytest settings
└── README.md
```

---

## 📦 Installation

Install as a package (includes static FFmpeg via `imageio-ffmpeg` automatically):

```bash
# Standard install
pip install .

# Editable install with development & testing dependencies
pip install -e ".[dev]"
```

After installation, the CLI tools are available directly as commands:
- `video-split`
- `video-merge`
- `video-probe`

---

## 🛠 Deterministic Tool Usage

### 1. Video Splitting (`scripts/split_video.py` or `video-split`)
Extracts explicit segments from a single video:

```powershell
python scripts/split_video.py --input "path/to/video.mp4" --segments 0:00-7:29 7:49-11:33
```

- Accepts timestamps in `MM:SS`, `HH:MM:SS`, or total seconds.
- Options:
  - `--output-dir` / `-o`: Directory to save generated files.
  - `--output-names`: Custom filenames for each output segment.
  - `--dry-run`: Preview planned files and exact FFmpeg commands without modifying disk.
  - `--reencode`: Force re-encoding instead of stream copy.

### 2. Video Merging (`scripts/merge_videos.py` or `video-merge`)
Concatenates multiple videos in the exact sequence specified. Supports optional segment slicing per input video (defaulting to full video if omitted):

```powershell
# Merge full videos
python scripts/merge_videos.py --inputs "take203.mp4" "take130.mp4" --output "merged.mp4"

# Merge specific segments from each video (use 'full' or omit to use whole video)
python scripts/merge_videos.py --inputs "part1.mp4" "part2.mp4" --segments "0:00-1:30" "full" --output "merged.mp4"
```

- Accepts optional `--segments` corresponding 1-to-1 with `--inputs` (use `full` or omit to keep entire input).
- Uses fast stream copy (`-c copy`) via FFmpeg concat demuxer.
- Automatically falls back to `filter_complex` re-encoding if video streams have different codecs or resolutions.
- Options:
  - `--segments`: Segment ranges per input file (e.g. `0:00-1:30`, `full`). Defaults to full videos if omitted.
  - `--dry-run`: Preview concat manifest, slicing steps, and FFmpeg commands without executing.
  - `--reencode`: Force re-encoding instead of stream copy.

### 3. Video Probing (`scripts/probe_video.py` or `video-probe`)
Inspects duration, resolution, framerate, and audio/video codecs:

```powershell
python scripts/probe_video.py file1.mp4 file2.mp4 --json
```

---

## 🤖 Antigravity Agent & Skills

When running inside **Google Antigravity**:
- **`/video-editor`**: Activate the unified skill to let the agent translate your prompt into tool inputs.
- The agent reads prompts such as:
  - *"Make 2 files: 0:00 to 7:29 file 1, 7:30 to 7:48 delete, 7:49 to 11:33 file 2"* -> calls `split_video.py --segments 0:00-7:29 7:49-11:33`.
  - *"Merge file 2:47 after 1:13"* -> probes both videos, orders them (`1:13` then `2:47`), and calls `merge_videos.py`.
- If requirements are ambiguous or contradictory, the agent will ask for clarification before running.

---

## 🧪 Testing & Coverage

Run the test suite:

```bash
# Run tests
pytest

# Run tests with 100% coverage report
pytest --cov=video_tools --cov=scripts --cov-report=term-missing
```

- **65 unit tests**
- **100% statement coverage**

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
