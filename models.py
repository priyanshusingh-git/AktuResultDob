from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import TypedDict


SubjectResult = TypedDict(
    "SubjectResult",
    {
        "Code": str,
        "Name": str,
        "Internal": int,
        "External": int,
        "Total": int,
    },
)


SemesterResult = TypedDict(
    "SemesterResult",
    {
        "SGPA": str,
        "Grand Total": str,
        "Subjects": list[SubjectResult],
    },
)


StudentResult = TypedDict(
    "StudentResult",
    {
        "Name": str,
        "Roll No": str,
        "DOB": str,
        "Semesters": dict[int, SemesterResult],
    },
)


@dataclass(frozen=True)
class StudentRecord:
    row_index: int
    roll_no: str
    dob: str


@dataclass
class SlotMetrics:
    slot_id: int
    success_count: int = 0
    failure_count: int = 0
    session_bootstraps: int = 0


class StudentScrapeError(Exception):
    def __init__(self, message: str, permanent: bool = False):
        super().__init__(message)
        self.message = message
        self.permanent = permanent


class SessionBootstrapError(StudentScrapeError):
    pass


def normalize_dob(raw_value: object) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return value

    patterns = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%m-%y",
    )
    for pattern in patterns:
        try:
            return datetime.strptime(value, pattern).strftime("%d-%m-%Y")
        except ValueError:
            continue

    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:\s.*)?", value)
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"

    match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", value)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    return value
