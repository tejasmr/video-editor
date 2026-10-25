"""Deterministic time parsing and formatting utilities for video timestamps.

Handles:
- MM:SS format (e.g., "7:29", "0:00", "11:33")
- HH:MM:SS format (e.g., "01:15:30")
- Total seconds (e.g., 94, "94.5", "449s")
- Dotted minute.second format (e.g., "1.41" -> 1m 41s = 101.0s, "2.03" -> 2m 3s = 123.0s)
"""

import re
from typing import Union


def parse_timestamp(val: Union[str, int, float], allow_dotted_min_sec: bool = True) -> float:
    """Convert timestamp representation to seconds (float).

    Args:
        val: Input timestamp string, int, or float.
        allow_dotted_min_sec: If True, interprets patterns like "1.41" as 1 min 41 sec
                              when the decimal part is <= 59.

    Returns:
        Total seconds as a float.

    Raises:
        ValueError: If the timestamp cannot be parsed or is negative.
    """
    if val is None:
        raise ValueError("Timestamp cannot be None")

    if isinstance(val, (int, float)):
        if val < 0:
            raise ValueError(f"Negative timestamp not allowed: {val}")
        return float(val)

    s = str(val).strip().lower()
    if not s:
        raise ValueError("Empty timestamp string")

    # Remove trailing units like 's' or 'sec'
    s = re.sub(r"(s|sec|secs|seconds)$", "", s).strip()

    # Match HH:MM:SS or H:MM:SS (.fraction optional)
    m_hms = re.match(r"^(\d+):([0-5]?\d):([0-5]?\d(?:\.\d+)?)$", s)
    if m_hms:
        hours = int(m_hms.group(1))
        minutes = int(m_hms.group(2))
        seconds = float(m_hms.group(3))
        return hours * 3600.0 + minutes * 60.0 + seconds

    # Match MM:SS or M:SS (.fraction optional)
    m_ms = re.match(r"^(\d+):([0-5]?\d(?:\.\d+)?)$", s)
    if m_ms:
        minutes = int(m_ms.group(1))
        seconds = float(m_ms.group(2))
        return minutes * 60.0 + seconds

    # Check for dotted notation like "1.41" (often spoken or typed as 1 min 41 sec)
    if allow_dotted_min_sec:
        m_dot = re.match(r"^(\d+)\.([0-5]\d)$", s)
        if m_dot:
            # e.g., 1.41 -> 1 min 41 sec = 101.0 sec
            # 2.03 -> 2 min 03 sec = 123.0 sec
            minutes = int(m_dot.group(1))
            seconds = float(m_dot.group(2))
            return minutes * 60.0 + seconds

    # Pure number (seconds)
    try:
        val_float = float(s)
        if val_float < 0:
            raise ValueError(f"Negative timestamp not allowed: {val_float}")
        return val_float
    except ValueError:
        pass

    raise ValueError(f"Invalid timestamp format: '{val}'")


def format_timestamp(seconds: float, include_hours: bool = False, use_colons: bool = True) -> str:
    """Format seconds into MM:SS or HH:MM:SS string.

    Args:
        seconds: Time in seconds.
        include_hours: If True, always outputs HH:MM:SS. If False, only outputs
                       hours if seconds >= 3600.
        use_colons: If True uses ':', if False uses '-' (safe for file paths).

    Returns:
        Formatted timestamp string.
    """
    if seconds < 0:
        seconds = 0.0

    total_sec = round(seconds)
    hours = total_sec // 3600
    rem = total_sec % 3600
    minutes = rem // 60
    sec = rem % 60

    sep = ":" if use_colons else "-"

    if hours > 0 or include_hours:
        return f"{hours:02d}{sep}{minutes:02d}{sep}{sec:02d}"
    return f"{minutes:02d}{sep}{sec:02d}"


def format_duration_short(seconds: float) -> str:
    """Format duration as M:SS or H:MM:SS without leading zero on minutes."""
    total_sec = round(seconds)
    hours = total_sec // 3600
    rem = total_sec % 3600
    minutes = rem // 60
    sec = rem % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes}:{sec:02d}"


def format_filename_range(start: float, end: float) -> str:
    """Format range for filenames, e.g., '00m00s_to_07m29s' or '00-00_to_07-29'."""
    start_str = format_timestamp(start, use_colons=False)
    end_str = format_timestamp(end, use_colons=False)
    return f"{start_str}_to_{end_str}"

