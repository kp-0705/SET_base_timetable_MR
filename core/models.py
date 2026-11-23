"""Domain data models and schemas using Pydantic for validation."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class TimeSlot(BaseModel):
    """Represents an academic period in a week."""
    slot_id: str = Field(..., description="Unique slot identifier, e.g., Mon_1")
    day: str = Field(..., description="Day of week, e.g., Monday")
    period: int = Field(..., ge=1, le=10, description="Period number (1-based)")
    start_time: str = Field(..., description="Start time string, e.g., 09:00")
    end_time: str = Field(..., description="End time string, e.g., 10:00")

    @classmethod
    def create(cls, day: str, period: int, start_time: str, end_time: str) -> "TimeSlot":
        return cls(
            slot_id=f"{day[:3]}_{period}",
            day=day,
            period=period,
            start_time=start_time,
            end_time=end_time
        )


class Room(BaseModel):
    """Represents a lecture hall or laboratory."""
    room_id: str = Field(..., description="Unique room ID, e.g., CR101, LAB201")
    name: str = Field(..., description="Descriptive room name")
    capacity: int = Field(..., gt=0, description="Seating capacity")
    room_type: str = Field(..., description="'lecture' or 'lab'")
    available_slots: Optional[List[str]] = Field(
        default=None, 
        description="List of slot_ids when room is available. None means always available."
    )

    @field_validator("room_type")
    @classmethod
    def validate_room_type(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if v_clean not in {"lecture", "lab"}:
            raise ValueError(f"room_type must be 'lecture' or 'lab', got '{v}'")
        return v_clean


class Faculty(BaseModel):
    """Represents an academic instructor."""
    faculty_id: str = Field(..., description="Unique faculty identifier, e.g., FAC01")
    name: str = Field(..., description="Faculty full name")
    max_weekly_load: int = Field(default=15, gt=0, description="Max teaching periods per week")
    max_daily_load: int = Field(default=3, gt=0, description="Max teaching periods per day")
    available_slots: Optional[List[str]] = Field(
        default=None,
        description="Allowed slot_ids for teaching. None means all slots available."
    )
    preferred_slots: Optional[List[str]] = Field(
        default=None,
        description="Preferred slot_ids (soft constraint)."
    )


class Course(BaseModel):
    """Represents a curriculum course offering."""
    course_id: str = Field(..., description="Unique course code, e.g., CS501")
    name: str = Field(..., description="Full course name")
    course_type: str = Field(default="lecture", description="'lecture' or 'lab'")
    faculty_id: str = Field(..., description="Assigned faculty member ID")
    batch_id: str = Field(..., description="Target student batch ID")
    enrollment: int = Field(..., gt=0, description="Number of enrolled students")
    sessions_per_week: int = Field(..., gt=0, le=10, description="Number of weekly sessions")
    duration_per_session: int = Field(
        default=1, 
        ge=1, 
        le=3, 
        description="Duration in consecutive periods (1 for lecture, 2 for lab)"
    )

    @field_validator("course_type")
    @classmethod
    def validate_course_type(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if v_clean not in {"lecture", "lab"}:
            raise ValueError(f"course_type must be 'lecture' or 'lab', got '{v}'")
        return v_clean


class StudentBatch(BaseModel):
    """Represents a cohort of students attending courses together."""
    batch_id: str = Field(..., description="Unique batch identifier, e.g., MTECH_CS_SEM1")
    name: str = Field(..., description="Batch display name")
    semester: int = Field(default=1, ge=1, le=8)
    size: int = Field(..., gt=0, description="Student count in batch")
    enrolled_courses: List[str] = Field(
        default_factory=list, 
        description="List of course_ids this batch takes"
    )


class SessionToken(BaseModel):
    """Represents one discrete instance of a course session to be scheduled in the week."""
    session_id: str = Field(..., description="Unique session token ID, e.g., CS501_S1")
    course_id: str
    session_index: int = Field(..., ge=1, description="1-based index of this weekly session")
    duration: int = Field(..., ge=1, description="Duration in periods (1 or 2)")
    course_type: str = Field(..., description="'lecture' or 'lab'")
    faculty_id: str
    batch_id: str
    enrollment: int


class TimetableEntry(BaseModel):
    """A fully decoded, concrete scheduled assignment."""
    session_id: str
    course_id: str
    course_name: str
    course_type: str
    faculty_id: str
    faculty_name: str
    batch_id: str
    batch_name: str
    room_id: str
    room_name: str
    day: str
    start_period: int
    duration: int
    slots_occupied: List[str]
    start_time: str = ""
    end_time: str = ""


class SchedulingInstance(BaseModel):
    """Encapsulates the complete input specification for timetabling."""
    courses: List[Course]
    faculty: List[Faculty]
    rooms: List[Room]
    batches: List[StudentBatch]
    time_slots: List[TimeSlot]

    def get_course(self, course_id: str) -> Optional[Course]:
        for c in self.courses:
            if c.course_id == course_id:
                return c
        return None

    def get_faculty(self, faculty_id: str) -> Optional[Faculty]:
        for f in self.faculty:
            if f.faculty_id == faculty_id:
                return f
        return None

    def get_room(self, room_id: str) -> Optional[Room]:
        for r in self.rooms:
            if r.room_id == room_id:
                return r
        return None

    def get_batch(self, batch_id: str) -> Optional[StudentBatch]:
        for b in self.batches:
            if b.batch_id == batch_id:
                return b
        return None

    def get_slot(self, slot_id: str) -> Optional[TimeSlot]:
        for s in self.time_slots:
            if s.slot_id == slot_id:
                return s
        return None

    def create_session_tokens(self) -> List[SessionToken]:
        """Decomposes all courses into individual weekly session tokens."""
        tokens: List[SessionToken] = []
        for course in self.courses:
            for s_idx in range(1, course.sessions_per_week + 1):
                token = SessionToken(
                    session_id=f"{course.course_id}_S{s_idx}",
                    course_id=course.course_id,
                    session_index=s_idx,
                    duration=course.duration_per_session,
                    course_type=course.course_type,
                    faculty_id=course.faculty_id,
                    batch_id=course.batch_id,
                    enrollment=course.enrollment,
                )
                tokens.append(token)
        return tokens


class TimetableResult(BaseModel):
    """Output summary of SAT or MaxSAT execution."""
    status: str = Field(..., description="'SAT', 'UNSAT', 'OPTIMIZED', or 'ERROR'")
    is_valid: bool = False
    solver_name: str = ""
    cardinality_encoding: str = ""
    variables_count: int = 0
    clauses_count: int = 0
    aux_variables_count: int = 0
    cnf_generation_time_sec: float = 0.0
    solving_time_sec: float = 0.0
    total_time_sec: float = 0.0
    entries: List[TimetableEntry] = Field(default_factory=list)
    unsat_core: Optional[List[str]] = None
    unsat_explanations: Optional[List[str]] = None
    soft_constraints_satisfied: Optional[int] = None
    soft_constraints_total: Optional[int] = None
    optimization_cost: Optional[int] = None
    error_message: Optional[str] = None
