"""Data validation and domain pruning for timetabling instances."""

from typing import List, Tuple, Dict, Set
from core.models import SchedulingInstance, SessionToken, TimeSlot, Room, Faculty, Course


class DataValidationError(Exception):
    """Raised when the scheduling dataset fails semantic sanity checks."""
    pass


def validate_scheduling_instance(instance: SchedulingInstance) -> List[str]:
    """
    Performs comprehensive pre-solve semantic validation on the scheduling instance.
    Returns a list of warning messages (if any). Raises DataValidationError on critical flaws.
    """
    warnings: List[str] = []
    
    # 1. Check entity presence
    if not instance.courses:
        raise DataValidationError("Scheduling instance contains zero courses.")
    if not instance.faculty:
        raise DataValidationError("Scheduling instance contains zero faculty members.")
    if not instance.rooms:
        raise DataValidationError("Scheduling instance contains zero rooms.")
    if not instance.batches:
        raise DataValidationError("Scheduling instance contains zero student batches.")
    if not instance.time_slots:
        raise DataValidationError("Scheduling instance contains zero time slots.")

    faculty_ids: Set[str] = {f.faculty_id for f in instance.faculty}
    batch_ids: Set[str] = {b.batch_id for b in instance.batches}
    slot_ids: Set[str] = {s.slot_id for s in instance.time_slots}
    room_ids: Set[str] = {r.room_id for r in instance.rooms}

    # 2. Validate course references and room compatibility
    for course in instance.courses:
        if course.faculty_id not in faculty_ids:
            raise DataValidationError(
                f"Course '{course.course_id}' references unknown faculty ID '{course.faculty_id}'."
            )
        if course.batch_id not in batch_ids:
            raise DataValidationError(
                f"Course '{course.course_id}' references unknown batch ID '{course.batch_id}'."
            )
        
        # Check if any room can theoretically host this course
        compatible_rooms = [
            r for r in instance.rooms
            if r.room_type == course.course_type and r.capacity >= course.enrollment
        ]
        if not compatible_rooms:
            raise DataValidationError(
                f"Course '{course.course_id}' ({course.course_type}, enrollment {course.enrollment}) "
                f"has no compatible room with sufficient capacity!"
            )

    # 3. Validate time slots and period continuity
    slots_by_day: Dict[str, List[TimeSlot]] = {}
    for slot in instance.time_slots:
        slots_by_day.setdefault(slot.day, []).append(slot)
    
    for day, slots in slots_by_day.items():
        periods = sorted([s.period for s in slots])
        expected = list(range(min(periods), max(periods) + 1))
        if periods != expected:
            warnings.append(f"Time slots for {day} have discontinuous period gaps: {periods}")

    # 4. Check faculty workload ceilings
    faculty_demand: Dict[str, int] = {}
    for course in instance.courses:
        hours = course.sessions_per_week * course.duration_per_session
        faculty_demand[course.faculty_id] = faculty_demand.get(course.faculty_id, 0) + hours

    for fac in instance.faculty:
        demanded = faculty_demand.get(fac.faculty_id, 0)
        if demanded > fac.max_weekly_load:
            raise DataValidationError(
                f"Faculty '{fac.name}' ({fac.faculty_id}) is assigned {demanded} hours, "
                f"exceeding max weekly load of {fac.max_weekly_load} hours!"
            )
        if fac.available_slots is not None:
            invalid_slots = set(fac.available_slots) - slot_ids
            if invalid_slots:
                raise DataValidationError(
                    f"Faculty '{fac.faculty_id}' references non-existent available slot(s): {invalid_slots}"
                )
            if len(fac.available_slots) < demanded:
                warnings.append(
                    f"Faculty '{fac.faculty_id}' has only {len(fac.available_slots)} available slots "
                    f"but is assigned {demanded} hours. Feasibility may be compromised."
                )

    # 5. Check room availability slot validity
    for room in instance.rooms:
        if room.available_slots is not None:
            invalid_slots = set(room.available_slots) - slot_ids
            if invalid_slots:
                raise DataValidationError(
                    f"Room '{room.room_id}' references non-existent available slot(s): {invalid_slots}"
                )

    # 6. Check student batch total demand vs week capacity
    total_slots_count = len(instance.time_slots)
    batch_demand: Dict[str, int] = {}
    for course in instance.courses:
        hours = course.sessions_per_week * course.duration_per_session
        batch_demand[course.batch_id] = batch_demand.get(course.batch_id, 0) + hours

    for b_id, hours in batch_demand.items():
        if hours > total_slots_count:
            raise DataValidationError(
                f"Batch '{b_id}' requires {hours} hours, but the total schedule only has {total_slots_count} slots!"
            )

    return warnings


def compute_consecutive_slot(
    slot_id: str, 
    slots_map: Dict[str, TimeSlot],
    slots_by_day_period: Dict[Tuple[str, int], TimeSlot]
) -> str | None:
    """Finds the next consecutive period on the same day, if it exists."""
    curr_slot = slots_map.get(slot_id)
    if not curr_slot:
        return None
    next_tuple = (curr_slot.day, curr_slot.period + 1)
    next_slot = slots_by_day_period.get(next_tuple)
    return next_slot.slot_id if next_slot else None


def get_valid_slot_room_pairs(
    session: SessionToken,
    instance: SchedulingInstance,
    slots_map: Dict[str, TimeSlot],
    slots_by_day_period: Dict[Tuple[str, int], TimeSlot]
) -> List[Tuple[str, str]]:
    """
    Domain Pruning Engine: Returns only viable (slot_id, room_id) pairs for a session token.
    Filters out incompatible rooms, insufficient capacity, unavailable slots, and period boundaries.
    """
    faculty = instance.get_faculty(session.faculty_id)
    valid_pairs: List[Tuple[str, str]] = []

    # 1. Candidate rooms matching type and capacity
    candidate_rooms = [
        r for r in instance.rooms
        if r.room_type == session.course_type and r.capacity >= session.enrollment
    ]

    for slot in instance.time_slots:
        # Check consecutive periods if duration > 1
        occupied_slots: List[str] = [slot.slot_id]
        if session.duration == 2:
            next_slot_id = compute_consecutive_slot(slot.slot_id, slots_map, slots_by_day_period)
            if not next_slot_id:
                # Cannot start a double period in the final period of the day
                continue
            occupied_slots.append(next_slot_id)

        # Check faculty availability across all occupied slots
        if faculty and faculty.available_slots is not None:
            if not all(s_id in faculty.available_slots for s_id in occupied_slots):
                continue

        # Check room compatibility and availability
        for room in candidate_rooms:
            if room.available_slots is not None:
                if not all(s_id in room.available_slots for s_id in occupied_slots):
                    continue
            valid_pairs.append((slot.slot_id, room.room_id))

    return valid_pairs
