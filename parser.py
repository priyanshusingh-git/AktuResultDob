from __future__ import annotations

from bs4 import BeautifulSoup, SoupStrainer
import re

from .models import SemesterResult, StudentResult, SubjectResult

PARSE_FILTER = SoupStrainer(["span", "table"])


def extract_identity_markers(soup: BeautifulSoup) -> list[tuple[str, str]]:
    markers: list[tuple[str, str]] = []
    for element in soup.find_all("span", id=True):
        element_id = element.get("id", "")
        lowered = element_id.lower()
        if "lblname" in lowered or "lblrollno" in lowered or "lblfathername" in lowered:
            text = element.get_text(" ", strip=True)
            if text:
                markers.append((element_id, text))
    return markers


def extract_name_from_soup(soup: BeautifulSoup) -> str:
    student_name = "Unknown"
    name_label = soup.find(id=lambda value: value and ("lblName" in value and "ContentPlaceHolder" in value))
    if not name_label:
        name_label = soup.find(id="lblName")
    if name_label and name_label.get_text(strip=True):
        student_name = name_label.get_text(" ", strip=True)

    if student_name == "Unknown":
        text = soup.get_text(" ", strip=True)
        match = re.search(r"Name\s*[:\-]\s*([A-Z][A-Z ]+)", text)
        if match:
            student_name = match.group(1).strip()

    student_name = re.sub(r"[^a-zA-Z\s.]", "", student_name)
    if student_name.endswith(" h") or student_name.endswith(" H"):
        student_name = student_name[:-2]
    return student_name.strip() or "Unknown"


def has_result_markers(soup: BeautifulSoup) -> bool:
    return bool(extract_identity_markers(soup) or parse_http_semester_data(soup))


def parse_http_semester_data(soup: BeautifulSoup) -> dict[int, list[SemesterResult]]:
    semester_data: dict[int, list[SemesterResult]] = {}
    sem_spans = soup.find_all("span", id=lambda value: value and "lblSemesterId" in value)
    for span in sem_spans:
        sem_text = span.get_text(strip=True)
        if not sem_text.isdigit():
            continue

        sem_num = int(sem_text)
        container = span.find_parent("table")
        if not container:
            continue

        sgpa = "N/A"
        sgpa_label = container.find("span", id=lambda value: value and isinstance(value, str) and "lblSGPA" in value)
        if sgpa_label:
            own_value = sgpa_label.get_text(strip=True)
            if own_value and re.fullmatch(r"\d+(?:\.\d+)?", own_value):
                sgpa = own_value
            parent_td = sgpa_label.find_parent("td")
            if parent_td and sgpa == "N/A":
                for item in parent_td.find_all("span"):
                    text_value = item.get_text(strip=True)
                    if text_value and text_value not in ("SGPA", "Result") and re.fullmatch(r"\d+(?:\.\d+)?", text_value):
                        sgpa = text_value
                        break

        grand_total = "N/A"
        total_label = container.find(
            "span",
            id=lambda value: value and isinstance(value, str) and "_lblSemesterTotalMarksObtained" in value,
        )
        if total_label:
            own_value = total_label.get_text(strip=True)
            if own_value and re.match(r"^\d+", own_value):
                grand_total = own_value
            parent_td = total_label.find_parent("td")
            if parent_td and grand_total == "N/A":
                for item in parent_td.find_all("span"):
                    text_value = item.get_text(strip=True)
                    if text_value and "Total Marks Obt" not in text_value and re.match(r"^\d+", text_value):
                        grand_total = text_value
                        break

        subjects: list[SubjectResult] = []
        subject_tables = container.find_all("table", id=lambda value: value and "grdViewSubjectMarksheet" in value)
        for table in subject_tables:
            for row in table.find_all("tr"):
                cols = row.find_all(["td", "th"])
                if len(cols) < 5:
                    continue
                code = cols[0].get_text(strip=True)
                if not code or code.lower() in ("code", "s.no", "sno", "#", "subject code", "subjectcode"):
                    continue

                internal = cols[3].get_text(strip=True)
                external = cols[4].get_text(strip=True)

                def clean_mark(mark: str) -> int:
                    if not mark or mark == "-":
                        return 0
                    cleaned = re.sub(r"[^\d]", "", mark)
                    return int(cleaned) if cleaned else 0

                int_val = clean_mark(internal)
                ext_val = clean_mark(external)
                subjects.append(
                    {
                        "Code": code,
                        "Name": cols[1].get_text(" ", strip=True),
                        "Internal": int_val,
                        "External": ext_val,
                        "Total": int_val + ext_val,
                    }
                )

        semester_data.setdefault(sem_num, []).append(
            {"SGPA": sgpa, "Grand Total": grand_total, "Subjects": subjects}
        )

    return semester_data


def select_requested_semesters(
    semester_data: dict[int, list[SemesterResult]],
    semesters: list[int],
) -> dict[int, SemesterResult]:
    final_data: dict[int, SemesterResult] = {}
    for sem_num in semesters:
        if sem_num in semester_data and semester_data[sem_num]:
            final_data[sem_num] = semester_data[sem_num][-1]
    return final_data


def parse_result_payload(html: str, roll_no: str, dob: str, semesters: list[int]) -> StudentResult:
    soup = BeautifulSoup(html, "html.parser", parse_only=PARSE_FILTER)
    student_name = extract_name_from_soup(soup)
    semester_data = parse_http_semester_data(soup)
    final_data = select_requested_semesters(semester_data, semesters)
    return {
        "Name": student_name,
        "Roll No": roll_no,
        "DOB": dob,
        "Semesters": final_data,
    }
