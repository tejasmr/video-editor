# Video Editor Workspace Rules

These guidelines apply to all video processing and editing operations in this repository.

## 1. Role Division
- **The Agent**: Interprets natural user prompts, reasons about time ranges, probes files to match durations, and handles clarifications if anything is unclear.
- **The Python Scripts**: Pure deterministic executors. They accept strictly explicit inputs (`--segments`, `--inputs`).

## 2. Deterministic Execution Standards
- Always use the tested scripts in `scripts/` (`split_video.py`, `merge_videos.py`, `probe_video.py`).
- Keep segments must never overlap ($A \le B \le C \le D$).
- All timestamp calculations must be validated before calling the script.

## 3. Encoding Standards
- Prefer lossless stream copy (`-c copy`) with `-avoid_negative_ts make_zero`.
- Automated fallback to `filter_complex` (`-c:v libx264 -c:a aac`) if container codecs or keyframe boundaries require it.
