"""Decodes SAT satisfying assignments into domain TimetableEntry objects."""

from typing import List, Dict, Tuple, Set, Optional
from core.models import SchedulingInstance, TimetableEntry, SessionToken
from config import WORKING_DAYS


def decode_timetable(
    model: List[int],
    primary_vars: Dict[Tuple[str, str, str], int],
    instance: SchedulingInstance
) -> List[TimetableEntry]:
    """
    Filters positive literals from the SAT model, identifies active x[s, t, r] variables,
    and constructs human-readable, fully populated TimetableEntry records.
    """
    model_set: Set[int] = set(model)
    entries: List[TimetableEntry] = []

    # Pre-build lookup dictionaries for fast decoding
    session_tokens_map: Dict[str, SessionToken] = {
        token.session_id: token for token in instance.create_session_tokens()
    }
    slots_map = {s.slot_id: s for s in instance.time_slots}
    rooms_map = {r.room_id: r for r in instance.rooms}
    faculty_map = {f.faculty_id: f for f in instance.faculty}
    batches_map = {b.batch_id: b for b in instance.batches}
    courses_map = {c.course_id: c for c in instance.courses}
    slots_by_day_period = {(s.day, s.period): s for s in instance.time_slots}

    for (session_id, slot_id, room_id), var_id in primary_vars.items():
        if var_id in model_set:
            session = session_tokens_map.get(session_id)
            slot = slots_map.get(slot_id)
            room = rooms_map.get(room_id)
            if not session or not slot or not room:
                continue

            course = courses_map.get(session.course_id)
            faculty = faculty_map.get(session.faculty_id)
            batch = batches_map.get(session.batch_id)

            # Determine all occupied slots (handling duration 2)
            occupied_slots = [slot_id]
            end_period = slot.period
            end_time = slot.end_time

            if session.duration == 2:
                next_tuple = (slot.day, slot.period + 1)
                next_slot = slots_by_day_period.get(next_tuple)
                if next_slot:
                    occupied_slots.append(next_slot.slot_id)
                    end_period = next_slot.period
                    end_time = next_slot.end_time

            entry = TimetableEntry(
                session_id=session.session_id,
                course_id=session.course_id,
                course_name=course.name if course else session.course_id,
                course_type=session.course_type,
                faculty_id=session.faculty_id,
                faculty_name=faculty.name if faculty else session.faculty_id,
                batch_id=session.batch_id,
                batch_name=batch.name if batch else session.batch_id,
                room_id=room.room_id,
                room_name=room.name,
                day=slot.day,
                start_period=slot.period,
                duration=session.duration,
                slots_occupied=occupied_slots,
                start_time=slot.start_time,
                end_time=end_time
            )
            entries.append(entry)

    # Sort entries by day of the week, then start period, then room
    day_order = {day: idx for idx, day in enumerate(WORKING_DAYS)}
    entries.sort(key=lambda e: (day_order.get(e.day, 99), e.start_period, e.room_id))

    return entries
