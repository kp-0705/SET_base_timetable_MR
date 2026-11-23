"""Data loader module for CSV and JSON timetable specifications."""

import json
import csv
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.models import (
    Course, Faculty, Room, StudentBatch, TimeSlot, SchedulingInstance
)
from config import WORKING_DAYS, PERIODS_PER_DAY, PERIOD_LABELS


def generate_default_time_slots() -> List[TimeSlot]:
    """Generates standard weekly academic time slots (5 days x 6 periods)."""
    slots: List[TimeSlot] = []
    for day in WORKING_DAYS:
        for p in range(1, PERIODS_PER_DAY + 1):
            time_label = PERIOD_LABELS.get(p, f"P{p}")
            parts = time_label.split(" - ")
            start_t = parts[0].strip() if len(parts) == 2 else f"0{8+p}:00"
            end_t = parts[1].strip() if len(parts) == 2 else f"0{9+p}:00"
            slots.append(TimeSlot.create(day=day, period=p, start_time=start_t, end_time=end_t))
    return slots


def load_from_json(json_path: Path | str) -> SchedulingInstance:
    """Loads a complete scheduling instance from a single JSON file."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON configuration file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    courses = [Course(**c) for c in data.get("courses", [])]
    faculty = [Faculty(**f) for f in data.get("faculty", [])]
    rooms = [Room(**r) for r in data.get("rooms", [])]
    batches = [StudentBatch(**b) for b in data.get("batches", [])]

    if "time_slots" in data and data["time_slots"]:
        time_slots = [TimeSlot(**s) for s in data["time_slots"]]
    else:
        time_slots = generate_default_time_slots()

    return SchedulingInstance(
        courses=courses,
        faculty=faculty,
        rooms=rooms,
        batches=batches,
        time_slots=time_slots
    )


def save_to_json(instance: SchedulingInstance, json_path: Path | str) -> None:
    """Serializes a scheduling instance to JSON format."""
    path = Path(json_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(instance.model_dump_json(indent=2))


def _parse_list_field(field_val: Any) -> Optional[List[str]]:
    """Helper to parse comma-separated or bracketed string fields into list."""
    if not field_val or str(field_val).strip() in {"", "None", "nan", "[]"}:
        return None
    val_str = str(field_val).strip()
    if val_str.startswith("[") and val_str.endswith("]"):
        val_str = val_str[1:-1]
    items = [x.strip() for x in val_str.split(",") if x.strip()]
    return items if items else None


def load_from_csv(
    courses_csv: Path | str,
    faculty_csv: Path | str,
    rooms_csv: Path | str,
    batches_csv: Path | str,
    slots_csv: Optional[Path | str] = None
) -> SchedulingInstance:
    """Loads scheduling instance from individual CSV tables."""
    courses: List[Course] = []
    faculty: List[Faculty] = []
    rooms: List[Room] = []
    batches: List[StudentBatch] = []

    # 1. Load Courses
    with open(courses_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            courses.append(Course(
                course_id=row["course_id"].strip(),
                name=row["name"].strip(),
                course_type=row.get("course_type", "lecture").strip().lower(),
                faculty_id=row["faculty_id"].strip(),
                batch_id=row["batch_id"].strip(),
                enrollment=int(row["enrollment"]),
                sessions_per_week=int(row["sessions_per_week"]),
                duration_per_session=int(row.get("duration_per_session", 1))
            ))

    # 2. Load Faculty
    with open(faculty_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            faculty.append(Faculty(
                faculty_id=row["faculty_id"].strip(),
                name=row["name"].strip(),
                max_weekly_load=int(row.get("max_weekly_load", 15)),
                max_daily_load=int(row.get("max_daily_load", 3)),
                available_slots=_parse_list_field(row.get("available_slots")),
                preferred_slots=_parse_list_field(row.get("preferred_slots"))
            ))

    # 3. Load Rooms
    with open(rooms_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rooms.append(Room(
                room_id=row["room_id"].strip(),
                name=row["name"].strip(),
                capacity=int(row["capacity"]),
                room_type=row.get("room_type", "lecture").strip().lower(),
                available_slots=_parse_list_field(row.get("available_slots"))
            ))

    # 4. Load Batches
    with open(batches_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            batches.append(StudentBatch(
                batch_id=row["batch_id"].strip(),
                name=row["name"].strip(),
                semester=int(row.get("semester", 1)),
                size=int(row["size"]),
                enrolled_courses=_parse_list_field(row.get("enrolled_courses")) or []
            ))

    # 5. Load or Generate Time Slots
    if slots_csv and Path(slots_csv).exists():
        time_slots: List[TimeSlot] = []
        with open(slots_csv, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                time_slots.append(TimeSlot(
                    slot_id=row["slot_id"].strip(),
                    day=row["day"].strip(),
                    period=int(row["period"]),
                    start_time=row["start_time"].strip(),
                    end_time=row["end_time"].strip()
                ))
    else:
        time_slots = generate_default_time_slots()

    return SchedulingInstance(
        courses=courses,
        faculty=faculty,
        rooms=rooms,
        batches=batches,
        time_slots=time_slots
    )


def export_csv_templates(target_dir: Path | str) -> None:
    """Exports blank template CSVs with headers and example data for user download."""
    td = Path(target_dir)
    td.mkdir(parents=True, exist_ok=True)

    templates = {
        "courses_template.csv": (
            "course_id,name,course_type,faculty_id,batch_id,enrollment,sessions_per_week,duration_per_session\n"
            "CS501,Advanced Algorithms,lecture,FAC01,MTECH_CS,35,3,1\n"
            "CS502,Machine Learning,lecture,FAC02,MTECH_CS,35,3,1\n"
            "CS503,AI Systems Lab,lab,FAC03,MTECH_CS,35,1,2\n"
        ),
        "faculty_template.csv": (
            "faculty_id,name,max_weekly_load,max_daily_load,available_slots,preferred_slots\n"
            "FAC01,Dr. Alan Turing,15,3,,Mon_1;Mon_2;Wed_1\n"
            "FAC02,Dr. Barbara Liskov,15,3,,\n"
            "FAC03,Dr. Claude Shannon,15,3,,\n"
        ),
        "rooms_template.csv": (
            "room_id,name,capacity,room_type,available_slots\n"
            "CR101,Lecture Hall 1,60,lecture,\n"
            "CR102,Lecture Hall 2,40,lecture,\n"
            "LAB201,Computing Lab 1,40,lab,\n"
        ),
        "batches_template.csv": (
            "batch_id,name,semester,size,enrolled_courses\n"
            "MTECH_CS,M.Tech Computer Science Sem 1,1,35,CS501;CS502;CS503\n"
        ),
        "time_slots_template.csv": (
            "slot_id,day,period,start_time,end_time\n"
            "Mon_1,Monday,1,09:00,10:00\n"
            "Mon_2,Monday,2,10:00,11:00\n"
            "Mon_3,Monday,3,11:15,12:15\n"
            "Mon_4,Monday,4,12:15,13:15\n"
            "Mon_5,Monday,5,14:15,15:15\n"
            "Mon_6,Monday,6,15:15,16:15\n"
        )
    }

    for fname, content in templates.items():
        with open(td / fname, "w", encoding="utf-8") as f:
            f.write(content)
