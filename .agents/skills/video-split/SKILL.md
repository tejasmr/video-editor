---
name: video-split
description: Deterministically split a video file into single or multiple videos based on timestamp ranges [A, B], [C, D] (where B <= C), handling deletions, time formats (MM:SS, HH:MM:SS, seconds), and custom prompts.
---

# Video Split Skill

Use this skill when the user requests splitting a video or cutting out/deleting specific parts.

## Architectural Role of the Agent
The Python script [`split_video.py`](../../../scripts/split_video.py) is a **pure deterministic execution engine** that accepts only explicit `--input` and `--segments` (e.g. `0:00-7:29`, `7:49-11:33`).

**Your role as the AI Agent:**
1. **Interpret the Prompt**: Extract the time intervals, handle deletion/skip requests, and convert everything into standard keep segments `[A, B], [C, D]` where $B \le C$.
2. **Handle Ambiguity**: If any timestamp is ambiguous, missing, overlapping, or contradicts video boundaries, **ask the user for clarification before executing**.
3. **Execute Deterministically**: Invoke `split_video.py` passing explicit segments.

---

## Agent Step-by-Step Procedure

### Step 1: Analyze User Prompt & Calculate Keep Segments
Transform natural instructions into clean keep segments:

- **Prompt Example 1**:
  ```text
  Make 2 files 
  0:00 to 7:29 file 1
  7:30 to 7:48 delete 
  7:49 to 11:33 file 2
  ```
  - Keep 1: `0:00-7:29`
  - Deleted: `7:30-7:48` (discarded)
  - Keep 2: `7:49-11:33`
  - Segments to pass: `--segments 0:00-7:29 7:49-11:33`

- **Prompt Example 2**:
  ```text
  0:00 to 1:39 delete 
  1:40 to 5:34 1 file
  ```
  - Deleted: `0:00-1:39`
  - Keep 1: `1:40-5:34`
  - Segments to pass: `--segments 1:40-5:34`

- **Prompt Example 3**:
  ```text
  1. 0:00 to 3:50
  2. 4:04 to 7:46
  3. 8:02 to 11:43
  ```
  - Segments to pass: `--segments 0:00-3:50 4:04-7:46 8:02-11:43`

### Step 2: Validate Boundaries & Resolve Ambiguity
- Verify that start time $\le$ end time for each segment.
- Verify that keep segments do not overlap ($B \le C$).
- If something is unclear (e.g. user says "cut out the middle" without times, or end time is beyond file duration), stop and ask the user.

### Step 3: Run the Deterministic Tool
Run `split_video.py` with explicit arguments:

```powershell
python scripts/split_video.py --input "<video_path>" --segments 0:00-7:29 7:49-11:33 [--output-dir "<dir>"] [--dry-run]
```

### Step 4: Report Results
Summarize the output files, durations, and paths with markdown links.
