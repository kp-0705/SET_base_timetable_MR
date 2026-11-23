"""Timetable Grid Views and Formatted Schedules for Streamlit."""

from typing import List, Dict, Optional
import pandas as pd
from core.models import TimetableEntry
from config import WORKING_DAYS, PERIODS_PER_DAY, PERIOD_LABELS


def build_grid_dataframe(
    entries: List[TimetableEntry],
    filter_by: str = "batch",  # "batch", "faculty", "room", or "all"
    filter_value: Optional[str] = None
) -> pd.DataFrame:
    """
    Constructs a 2D matrix (Periods as rows, Days as columns) for grid display.
    """
    # Filter entries
    filtered_entries = entries
    if filter_by == "batch" and filter_value:
        filtered_entries = [e for e in entries if e.batch_id == filter_value]
    elif filter_by == "faculty" and filter_value:
        filtered_entries = [e for e in entries if e.faculty_id == filter_value]
    elif filter_by == "room" and filter_value:
        filtered_entries = [e for e in entries if e.room_id == filter_value]

    # Initialize empty grid
    grid: Dict[str, Dict[str, str]] = {
        day: {f"P{p} ({PERIOD_LABELS.get(p, '')})": "" for p in range(1, PERIODS_PER_DAY + 1)}
        for day in WORKING_DAYS
    }

    for e in filtered_entries:
        day = e.day
        if day not in grid:
            continue

        for p_offset in range(e.duration):
            p_num = e.start_period + p_offset
            row_key = f"P{p_num} ({PERIOD_LABELS.get(p_num, '')})"
            if row_key not in grid[day]:
                continue

            type_badge = "🧪 LAB" if e.course_type == "lab" else "📖 LEC"
            dur_str = f" [Double {e.duration}hr]" if e.duration > 1 and p_offset == 0 else ""

            cell_text = (
                f"{type_badge} {e.course_id}: {e.course_name}{dur_str}\n"
                f"👤 {e.faculty_name} | 🏛️ {e.room_id}\n"
                f"👥 {e.batch_id}"
            )

            # If multiple sessions are shown (e.g. "all" filter)
            if grid[day][row_key]:
                grid[day][row_key] += "\n---\n" + cell_text
            else:
                grid[day][row_key] = cell_text

    df = pd.DataFrame(grid)
    df.index.name = "Period / Time"
    return df


def build_exportable_dataframe(entries: List[TimetableEntry]) -> pd.DataFrame:
    """Converts timetable entries into a tabular format for CSV/Excel export."""
    records = []
    for e in entries:
        records.append({
            "Session ID": e.session_id,
            "Course ID": e.course_id,
            "Course Name": e.course_name,
            "Type": e.course_type.capitalize(),
            "Duration (hrs)": e.duration,
            "Day": e.day,
            "Start Period": e.start_period,
            "Time": f"{e.start_time} - {e.end_time}",
            "Room ID": e.room_id,
            "Room Name": e.room_name,
            "Faculty ID": e.faculty_id,
            "Faculty Name": e.faculty_name,
            "Student Batch ID": e.batch_id,
            "Batch Name": e.batch_name,
            "Occupied Slots": "; ".join(e.slots_occupied)
        })
    return pd.DataFrame(records)
