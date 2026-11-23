"""Independent verification engine for decoded academic timetables."""

from typing import List, Dict, Tuple, Set
from core.models import SchedulingInstance, TimetableEntry, SessionToken


class TimetableValidator:
    """
    Decoupled Auditor: Independently verifies a generated timetable
    against all ground-truth institutional hard constraints.
    Does NOT rely on solver internal guarantees.
    """

    def __init__(self, instance: SchedulingInstance):
        self.instance = instance
        self.expected_tokens = instance.create_session_tokens()
        self.expected_token_ids = {t.session_id for t in self.expected_tokens}
        self.faculty_map = {f.faculty_id: f for f in instance.faculty}
        self.rooms_map = {r.room_id: r for r in instance.rooms}
        self.courses_map = {c.course_id: c for c in instance.courses}
        self.slots_map = {s.slot_id: s for s in instance.time_slots}

    def validate(self, entries: List[TimetableEntry]) -> Tuple[bool, List[str]]:
        """
        Runs exhaustive verification suite.
        Returns: (is_valid: bool, violations: List[str])
        """
        violations: List[str] = []

        # 1. Verify Every Session Scheduled Exactly Once
        scheduled_session_ids = [e.session_id for e in entries]
        session_counts: Dict[str, int] = {}
        for s_id in scheduled_session_ids:
            session_counts[s_id] = session_counts.get(s_id, 0) + 1

        missing_sessions = self.expected_token_ids - set(scheduled_session_ids)
        if missing_sessions:
            violations.append(f"Missing sessions not scheduled ({len(missing_sessions)}): {sorted(missing_sessions)}")

        duplicate_sessions = [s_id for s_id, count in session_counts.items() if count > 1]
        if duplicate_sessions:
            violations.append(f"Duplicate session schedules detected: {duplicate_sessions}")

        # 2. Verify Mutual Exclusion on Rooms (No Room Clashes)
        room_occupancy: Dict[Tuple[str, str], List[str]] = {}
        for e in entries:
            for s_id in e.slots_occupied:
                key = (e.room_id, s_id)
                room_occupancy.setdefault(key, []).append(e.session_id)

        for (room_id, s_id), sessions in room_occupancy.items():
            if len(sessions) > 1:
                violations.append(
                    f"Room Clash: Room '{room_id}' is double-booked at slot '{s_id}' by sessions: {sessions}"
                )

        # 3. Verify Mutual Exclusion on Faculty (No Faculty Clashes)
        faculty_occupancy: Dict[Tuple[str, str], List[str]] = {}
        for e in entries:
            for s_id in e.slots_occupied:
                key = (e.faculty_id, s_id)
                faculty_occupancy.setdefault(key, []).append(e.session_id)

        for (faculty_id, s_id), sessions in faculty_occupancy.items():
            if len(sessions) > 1:
                violations.append(
                    f"Faculty Clash: Faculty '{faculty_id}' is scheduled simultaneously at slot '{s_id}' with sessions: {sessions}"
                )

        # 4. Verify Mutual Exclusion on Student Batches (No Batch Clashes)
        batch_occupancy: Dict[Tuple[str, str], List[str]] = {}
        for e in entries:
            for s_id in e.slots_occupied:
                key = (e.batch_id, s_id)
                batch_occupancy.setdefault(key, []).append(e.session_id)

        for (batch_id, s_id), sessions in batch_occupancy.items():
            if len(sessions) > 1:
                violations.append(
                    f"Batch Clash: Student batch '{batch_id}' has overlapping sessions at slot '{s_id}': {sessions}"
                )

        # 5. Room Type and Capacity Conformance
        for e in entries:
            room = self.rooms_map.get(e.room_id)
            course = self.courses_map.get(e.course_id)
            if not room or not course:
                violations.append(f"Entry {e.session_id} references invalid room/course entity.")
                continue

            if room.room_type != course.course_type:
                violations.append(
                    f"Room Type Mismatch: Session '{e.session_id}' ({course.course_type}) placed in '{room.room_id}' ({room.room_type})"
                )
            if room.capacity < course.enrollment:
                violations.append(
                    f"Capacity Violation: Room '{room.room_id}' (cap {room.capacity}) cannot accommodate '{e.session_id}' (enrollment {course.enrollment})"
                )

        # 6. Contiguity of Multi-Period Sessions
        for e in entries:
            if e.duration == 2:
                if len(e.slots_occupied) != 2:
                    violations.append(f"Lab session '{e.session_id}' has duration 2 but occupies {len(e.slots_occupied)} slots.")
                else:
                    slot1 = self.slots_map.get(e.slots_occupied[0])
                    slot2 = self.slots_map.get(e.slots_occupied[1])
                    if not slot1 or not slot2:
                        violations.append(f"Invalid slots in session '{e.session_id}': {e.slots_occupied}")
                    elif slot1.day != slot2.day or slot2.period != slot1.period + 1:
                        violations.append(
                            f"Non-contiguous Lab: Session '{e.session_id}' occupies non-consecutive slots ({slot1.slot_id}, {slot2.slot_id})"
                        )

        # 7. Availability Restrictions
        for e in entries:
            faculty = self.faculty_map.get(e.faculty_id)
            if faculty and faculty.available_slots is not None:
                for s_id in e.slots_occupied:
                    if s_id not in faculty.available_slots:
                        violations.append(
                            f"Faculty Availability Violation: Faculty '{faculty.name}' scheduled at unavailable slot '{s_id}'"
                        )

            room = self.rooms_map.get(e.room_id)
            if room and room.available_slots is not None:
                for s_id in e.slots_occupied:
                    if s_id not in room.available_slots:
                        violations.append(
                            f"Room Availability Violation: Room '{room.name}' scheduled at unavailable slot '{s_id}'"
                        )

        # 8. Course Daily Spreading
        course_days: Dict[Tuple[str, str], List[str]] = {}
        for e in entries:
            course = self.courses_map.get(e.course_id)
            if course and course.course_type == "lecture" and course.sessions_per_week > 1:
                key = (e.course_id, e.day)
                course_days.setdefault(key, []).append(e.session_id)

        for (course_id, day), sessions in course_days.items():
            if len(sessions) > 1:
                violations.append(
                    f"Daily Spread Violation: Course '{course_id}' scheduled {len(sessions)} times on {day} ({sessions})"
                )

        is_valid = len(violations) == 0
        return is_valid, violations
