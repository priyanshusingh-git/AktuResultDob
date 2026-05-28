import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from .utils import get_checkpoint_db_path


RUNNING_STATES = ("running", "stopped")


class CheckpointStore:
    def __init__(self, logger, db_path=None):
        self.logger = logger
        self.db_path = db_path or get_checkpoint_db_path()
        self._initialize()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            conn.close()

    def _initialize(self):
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    input_file TEXT NOT NULL,
                    output_file TEXT NOT NULL,
                    semesters_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS students (
                    run_id INTEGER NOT NULL,
                    row_index INTEGER NOT NULL,
                    roll_no TEXT NOT NULL,
                    dob TEXT NOT NULL,
                    state TEXT NOT NULL,
                    last_error TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, roll_no),
                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS results (
                    run_id INTEGER NOT NULL,
                    roll_no TEXT NOT NULL,
                    semester_no INTEGER NOT NULL,
                    student_name TEXT NOT NULL,
                    dob TEXT NOT NULL,
                    sgpa TEXT,
                    grand_total TEXT,
                    subjects_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, roll_no, semester_no),
                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS failures (
                    run_id INTEGER NOT NULL,
                    roll_no TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    PRIMARY KEY (run_id, roll_no),
                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS session_meta (
                    run_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, key),
                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
                );
                """
            )

    def _now(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _deserialize_run(self, row):
        if row is None:
            return None
        run = dict(row)
        run["semesters"] = json.loads(run.pop("semesters_json"))
        return run

    def find_resumable_run(self, input_file):
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM runs
                WHERE input_file = ?
                  AND status IN ('running', 'stopped')
                ORDER BY id DESC
                LIMIT 1
                """,
                (input_file,),
            ).fetchone()
        return self._deserialize_run(row)

    def create_or_resume_run(self, input_file, output_file, semesters, students):
        semesters_json = json.dumps(sorted(semesters))
        now = self._now()

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM runs
                WHERE input_file = ?
                  AND output_file = ?
                  AND semesters_json = ?
                  AND status IN ('running', 'stopped')
                ORDER BY id DESC
                LIMIT 1
                """,
                (input_file, output_file, semesters_json),
            ).fetchone()

            if row:
                run_id = row["id"]
                conn.execute(
                    """
                    UPDATE runs
                    SET status = 'running', updated_at = ?
                    WHERE id = ?
                    """,
                    (now, run_id),
                )
                conn.execute(
                    """
                    UPDATE students
                    SET state = 'pending',
                        last_error = NULL,
                        updated_at = ?
                    WHERE run_id = ?
                      AND state IN ('processing', 'failed')
                    """,
                    (now, run_id),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO runs (input_file, output_file, semesters_json, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'running', ?, ?)
                    """,
                    (input_file, output_file, semesters_json, now, now),
                )
                run_id = cursor.lastrowid

            for student in students:
                conn.execute(
                    """
                    INSERT INTO students (run_id, row_index, roll_no, dob, state, last_error, attempts, updated_at)
                    VALUES (?, ?, ?, ?, 'pending', NULL, 0, ?)
                    ON CONFLICT(run_id, roll_no) DO UPDATE SET
                        row_index = excluded.row_index,
                        dob = excluded.dob,
                        updated_at = excluded.updated_at
                    """,
                    (run_id, student["row_index"], student["roll_no"], student["dob"], now),
                )

        return run_id

    def mark_run_status(self, run_id, status):
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET status = ?, updated_at = ? WHERE id = ?",
                (status, self._now(), run_id),
            )

    def get_run_progress(self, run_id):
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM students WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
            processed = conn.execute(
                "SELECT COUNT(*) FROM students WHERE run_id = ? AND state = 'processed'",
                (run_id,),
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM students WHERE run_id = ? AND state = 'failed'",
                (run_id,),
            ).fetchone()[0]
        return {"total": total, "processed": processed, "failed": failed}

    def get_students_for_queue(self, run_id):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT row_index, roll_no, dob
                FROM students
                WHERE run_id = ?
                  AND state = 'pending'
                ORDER BY row_index
                """,
                (run_id,),
            ).fetchall()

        return [
            {"row_index": row["row_index"], "roll_no": row["roll_no"], "dob": row["dob"]}
            for row in rows
        ]

    def mark_processing(self, run_id, roll_no):
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE students
                SET state = 'processing',
                    attempts = attempts + 1,
                    updated_at = ?
                WHERE run_id = ?
                  AND roll_no = ?
                """,
                (now, run_id, str(roll_no).strip()),
            )
            attempts = conn.execute(
                "SELECT attempts FROM students WHERE run_id = ? AND roll_no = ?",
                (run_id, str(roll_no).strip()),
            ).fetchone()

        return attempts["attempts"] if attempts else 0

    def requeue_student(self, run_id, roll_no, error_type):
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE students
                SET state = 'pending',
                    last_error = ?,
                    updated_at = ?
                WHERE run_id = ?
                  AND roll_no = ?
                """,
                (error_type, self._now(), run_id, str(roll_no).strip()),
            )

    def save_result(self, run_id, result):
        now = self._now()
        roll_no = str(result["Roll No"]).strip()
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM results WHERE run_id = ? AND roll_no = ?",
                (run_id, roll_no),
            )

            for sem_num, sem_data in result.get("Semesters", {}).items():
                conn.execute(
                    """
                    INSERT INTO results (
                        run_id, roll_no, semester_no, student_name, dob, sgpa, grand_total, subjects_json, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        roll_no,
                        int(sem_num),
                        result["Name"],
                        result["DOB"],
                        sem_data.get("SGPA", ""),
                        sem_data.get("Grand Total", ""),
                        json.dumps(sem_data.get("Subjects", [])),
                        now,
                    ),
                )

            conn.execute(
                """
                UPDATE students
                SET state = 'processed',
                    last_error = NULL,
                    updated_at = ?
                WHERE run_id = ?
                  AND roll_no = ?
                """,
                (now, run_id, roll_no),
            )
            conn.execute(
                "DELETE FROM failures WHERE run_id = ? AND roll_no = ?",
                (run_id, roll_no),
            )

    def save_failure(self, run_id, roll_no, error_type):
        now = self._now()
        roll_no = str(roll_no).strip()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE students
                SET state = 'failed',
                    last_error = ?,
                    updated_at = ?
                WHERE run_id = ?
                  AND roll_no = ?
                """,
                (error_type, now, run_id, roll_no),
            )
            conn.execute(
                """
                INSERT INTO failures (run_id, roll_no, error_type, timestamp)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(run_id, roll_no) DO UPDATE SET
                    error_type = excluded.error_type,
                    timestamp = excluded.timestamp
                """,
                (run_id, roll_no, error_type, now),
            )

    def get_run_output_file(self, run_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT output_file FROM runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        return row["output_file"] if row else None

    def get_export_payload(self, run_id, semesters):
        semester_rows = {int(sem): [] for sem in semesters}
        with self._connect() as conn:
            result_rows = conn.execute(
                """
                SELECT roll_no, semester_no, student_name, dob, sgpa, grand_total, subjects_json
                FROM results
                WHERE run_id = ?
                ORDER BY semester_no, roll_no
                """,
                (run_id,),
            ).fetchall()
            failure_rows = conn.execute(
                """
                SELECT roll_no, error_type, timestamp
                FROM failures
                WHERE run_id = ?
                ORDER BY roll_no
                """,
                (run_id,),
            ).fetchall()

        for row in result_rows:
            sem_num = int(row["semester_no"])
            if sem_num not in semester_rows:
                continue
            semester_rows[sem_num].append(
                {
                    "Name": row["student_name"],
                    "Roll No": row["roll_no"],
                    "DOB": row["dob"],
                    "SGPA": row["sgpa"],
                    "Grand Total": row["grand_total"],
                    "Subjects": json.loads(row["subjects_json"] or "[]"),
                }
            )

        failures = [dict(row) for row in failure_rows]
        return {"semesters": semester_rows, "failures": failures}
