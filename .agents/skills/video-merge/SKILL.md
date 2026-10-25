---
name: video-merge
description: Deterministically merge multiple video files into a single video according to prompt instructions, matching files by duration (e.g. 1:41, 2:03), filename, or explicit order.
---

# Video Merge Skill

Use this skill when the user requests merging multiple videos in a particular order or matching files by duration/description.

## Architectural Role of the Agent
The Python script [`merge_videos.py`](../../../scripts/merge_videos.py) is a **pure deterministic execution engine** that accepts an explicit, pre-ordered list of `--inputs` (`path1 path2 ...`).

**Your role as the AI Agent:**
1. **Probe Files When Needed**: If the user refers to files by duration (e.g. "1.41 file", "2:03 1st, 1:30 2nd"), run [`probe_video.py`](../../../scripts/probe_video.py) to inspect the duration of all candidate video paths.
2. **Reason & Match**: Map the user's descriptions to the probed video paths and order them into an exact sequence (`#1, #2, #3`).
3. **Clarify Ambiguities**: If multiple files match a duration, or if a described duration doesn't exist, **ask the user for clarification before executing**.
4. **Execute Deterministically**: Invoke `merge_videos.py` passing the ordered paths to `--inputs`.

---

## Agent Step-by-Step Procedure

### Step 1: Probe Candidate Videos
When files are referenced by duration or description, run:
```powershell
python scripts/probe_video.py "path/to/fileA.mp4" "path/to/fileB.mp4" "path/to/fileC.mp4" --json
```

This returns the exact duration and format of each file:
```json
[
  { "filename": "fileA.mp4", "duration_sec": 54.0, "duration_formatted": "0:54" },
  { "filename": "fileB.mp4", "duration_sec": 123.0, "duration_formatted": "2:03" },
  { "filename": "fileC.mp4", "duration_sec": 90.0, "duration_formatted": "1:30" }
]
```

### Step 2: Determine Ordered Input Paths

- **Prompt Example 1**:
  ```text
  merge the 1.41 file to 1.57
  ```
  1. Identify candidate matching ~1:41 (101s) -> `intro.mp4`
  2. Identify candidate matching ~1:57 (117s) -> `outro.mp4`
  3. Ordered sequence: `intro.mp4`, `outro.mp4`

- **Prompt Example 2**:
  ```text
  Please help merge 3 files into 1
  2:03 1st 
  1:30 to be added as 2nd 
  0:54 to be 3rd
  ```
  1. 1st: file with duration 2:03 (`fileB.mp4`)
  2. 2nd: file with duration 1:30 (`fileC.mp4`)
  3. 3rd: file with duration 0:54 (`fileA.mp4`)
  4. Ordered sequence: `fileB.mp4`, `fileC.mp4`, `fileA.mp4`

### Step 3: Run Deterministic Merge
Invoke `merge_videos.py` with the ordered file paths:

```powershell
python scripts/merge_videos.py --inputs "fileB.mp4" "fileC.mp4" "fileA.mp4" --output "merged.mp4"
```

### Step 4: Verification & Report
Confirm the merged file was created and report the sequence and total duration to the user.
