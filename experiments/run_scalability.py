"""Experiment 3: Scalability Analysis across Increasing Course Sizes (10 to 60+ Courses)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import random
import time
import pandas as pd
from typing import List

from core.models import Course, Faculty, Room, StudentBatch, TimeSlot, SchedulingInstance
from core.constraint_encoder import ConstraintEncoder
from core.sat_solver import SATSolverService
from core.data_loader import generate_default_time_slots
import config


def generate_synthetic_instance(num_courses: int, seed: int = 42) -> SchedulingInstance:
    """
    Generates a realistic, scaling academic instance.
    Maintains balanced ratios: ~3 courses per faculty, ~4 courses per room.
    """
    random.seed(seed)
    time_slots = generate_default_time_slots()

    num_faculty = max(4, num_courses // 3)
    num_rooms = max(4, num_courses // 4)
    num_batches = max(2, num_courses // 4)

    # 1. Create Batches
    batches: List[StudentBatch] = []
    for b_idx in range(1, num_batches + 1):
        batches.append(StudentBatch(
            batch_id=f"BATCH_{b_idx}",
            name=f"Cohort Batch {b_idx}",
            semester=(b_idx % 4) + 1,
            size=30 + (b_idx % 20),
            enrolled_courses=[]
        ))

    # 2. Create Faculty
    faculty: List[Faculty] = []
    for f_idx in range(1, num_faculty + 1):
        faculty.append(Faculty(
            faculty_id=f"FAC_{f_idx}",
            name=f"Prof. Faculty {f_idx}",
            max_weekly_load=15,
            max_daily_load=4,
            available_slots=None
        ))

    # 3. Create Rooms (80% lecture, 20% lab)
    rooms: List[Room] = []
    for r_idx in range(1, num_rooms + 1):
        r_type = "lab" if r_idx % 5 == 0 else "lecture"
        rooms.append(Room(
            room_id=f"ROOM_{r_idx}",
            name=f"Room {r_idx} ({r_type.capitalize()})",
            capacity=60,
            room_type=r_type,
            available_slots=None
        ))

    # 4. Create Courses
    courses: List[Course] = []
    for c_idx in range(1, num_courses + 1):
        is_lab = (c_idx % 5 == 0)
        c_type = "lab" if is_lab else "lecture"
        dur = 2 if is_lab else 1
        sessions = 1 if is_lab else 2

        assigned_fac = faculty[(c_idx - 1) % len(faculty)].faculty_id
        assigned_batch = batches[(c_idx - 1) % len(batches)].batch_id

        course_id = f"CRS_{c_idx:03d}"
        courses.append(Course(
            course_id=course_id,
            name=f"Course Offering {c_idx}",
            course_type=c_type,
            faculty_id=assigned_fac,
            batch_id=assigned_batch,
            enrollment=35,
            sessions_per_week=sessions,
            duration_per_session=dur
        ))

    return SchedulingInstance(
        courses=courses,
        faculty=faculty,
        rooms=rooms,
        batches=batches,
        time_slots=time_slots
    )


def run_experiment() -> pd.DataFrame:
    course_counts = [10, 20, 30, 40, 50, 60]
    results = []

    print("Running Scalability Benchmark...")
    for count in course_counts:
        inst = generate_synthetic_instance(count)
        start_t = time.perf_counter()

        encoder = ConstraintEncoder(inst, cardinality_strategy="sequential")
        enc_res = encoder.encode()

        solver = SATSolverService("glucose4")
        sol_res = solver.solve(enc_res.clauses)
        total_time = time.perf_counter() - start_t

        results.append({
            "Courses Count": count,
            "Total Sessions": len(inst.create_session_tokens()),
            "Faculty Count": len(inst.faculty),
            "Rooms Count": len(inst.rooms),
            "Batches Count": len(inst.batches),
            "Total Variables": enc_res.stats["total_vars"],
            "Total Clauses": enc_res.stats["total_clauses"],
            "CNF Gen Time (s)": enc_res.stats["generation_time_sec"],
            "Solve Time (s)": sol_res.solving_time_sec,
            "Total Pipeline Time (s)": round(total_time, 4),
            "Status": sol_res.status
        })
        print(f"Courses: {count:2d} | Vars: {enc_res.stats['total_vars']:6d} | Clauses: {enc_res.stats['total_clauses']:7d} | Solve: {sol_res.solving_time_sec:.4f}s | Status: {sol_res.status}")

    df = pd.DataFrame(results)
    out_file = config.RESULTS_DIR / "scalability_benchmark.csv"
    df.to_csv(out_file, index=False)
    print(f"\nSaved scalability benchmark to: {out_file}")
    return df


if __name__ == "__main__":
    run_experiment()
