from __future__ import annotations

import random
import threading
import time

from runtime.checkpoint_store import CheckpointStore
from runtime.excel_processor import ExcelProcessor
from runtime.logger import app_logger

from client import OneViewHttpClient
from models import StudentRecord, StudentScrapeError, normalize_dob


MAX_STUDENT_ATTEMPTS = 2


class HttpScraperEngine:
    def __init__(self, ui_callbacks):
        self.logger = app_logger
        self.callbacks = ui_callbacks
        self.excel = ExcelProcessor(self.logger)
        self.checkpoints = CheckpointStore(self.logger)

        self.thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()

        self.active_run_id = None
        self.last_run_state = "idle"
        self.last_run_summary = None

        self._progress_lock = threading.Lock()
        self._progress_state = {
            "total": 0,
            "completed": 0,
            "processed": 0,
            "failed": 0,
            "time_total": 0.0,
            "time_count": 0,
        }

    def find_resumable_run(self, input_file):
        return self.checkpoints.find_resumable_run(input_file)

    def get_last_run_summary(self):
        return dict(self.last_run_summary or {})

    def start_scraping(self, input_file, output_file, semesters):
        if self.thread and self.thread.is_alive():
            self.logger.warning("Scraping is already running.")
            return

        self.stop_event.clear()
        self.pause_event.clear()
        self.last_run_state = "running"
        self.last_run_summary = None
        self.thread = threading.Thread(
            target=self._run_loop,
            args=(input_file, output_file, semesters),
            daemon=True,
        )
        self.thread.start()

    def stop_scraping(self):
        self.logger.info("Stop requested. Scraper will stop after current student.")
        self.stop_event.set()

    def pause_scraping(self):
        self.logger.info("Pause requested. Scraper will pause before the next student.")
        self.pause_event.set()

    def resume_scraping(self):
        self.logger.info("Resuming scraping...")
        self.pause_event.clear()

    def _update_status(self, text):
        callback = self.callbacks.get("set_status")
        if callback:
            callback(text)

    def _update_progress(self, current, total):
        callback = self.callbacks.get("set_progress")
        if callback:
            callback(current, total)

    def _update_stats(self, total, processed, failed, est_time):
        callback = self.callbacks.get("set_stats")
        if callback:
            callback(total, processed, failed, est_time)

    def _initialize_progress(self, total, processed, failed):
        completed = processed + failed
        with self._progress_lock:
            self._progress_state = {
                "total": total,
                "completed": completed,
                "processed": processed,
                "failed": failed,
                "time_total": 0.0,
                "time_count": 0,
            }
        self._update_progress(completed, total)
        self._update_stats(total, processed, failed, "--")

    def _record_completion(self, success, elapsed):
        with self._progress_lock:
            self._progress_state["completed"] += 1
            if success:
                self._progress_state["processed"] += 1
            else:
                self._progress_state["failed"] += 1
            self._progress_state["time_total"] += elapsed
            self._progress_state["time_count"] += 1
            total = self._progress_state["total"]
            completed = self._progress_state["completed"]
            processed = self._progress_state["processed"]
            failed = self._progress_state["failed"]
            avg = self._progress_state["time_total"] / max(1, self._progress_state["time_count"])

        remaining = max(0, total - completed) * avg
        time_str = f"{int(remaining // 60)}m {int(remaining % 60)}s" if completed < total else "0m 0s"
        self._update_progress(completed, total)
        self._update_stats(total, processed, failed, time_str)

    def _run_loop(self, input_file, output_file, semesters):
        from runtime.config import APP_LABEL

        self._update_status(f"Starting {APP_LABEL}...")
        self.active_run_id = None

        try:
            df = self.excel.validate_input(input_file)
            if df is None:
                self.last_run_state = "stopped"
                return

            students = [
                StudentRecord(
                    row_index=int(row["row_index"]),
                    roll_no=str(row["Roll No"]).strip(),
                    dob=normalize_dob(row["DOB"]),
                )
                for row in df
            ]

            run_id = self.checkpoints.create_or_resume_run(
                input_file=input_file,
                output_file=output_file,
                semesters=semesters,
                students=[
                    {"row_index": student.row_index, "roll_no": student.roll_no, "dob": student.dob}
                    for student in students
                ],
            )
            self.active_run_id = run_id
            self.checkpoints.mark_run_status(run_id, "running")

            progress = self.checkpoints.get_run_progress(run_id)
            total_students = progress["total"]
            self._initialize_progress(total_students, progress["processed"], progress["failed"])

            pending_students = self.checkpoints.get_students_for_queue(run_id)
            if not pending_students:
                self._update_status("No pending students. Exporting latest checkpoint data...")
                self._export_checkpoint(run_id, output_file, semesters)
                self.checkpoints.mark_run_status(run_id, "finished")
                self.last_run_state = "finished"
                return

            # Sequential worker setup
            client = OneViewHttpClient(self.logger)
            student_list = list(pending_students)

            while student_list:
                while self.pause_event.is_set() and not self.stop_event.is_set():
                    time.sleep(0.2)

                if self.stop_event.is_set():
                    break

                student = student_list.pop(0)
                roll_no = student["roll_no"]
                dob = normalize_dob(student["dob"])
                attempt_no = self.checkpoints.mark_processing(run_id, roll_no)
                self._update_status(f"HTTP worker: {roll_no}")
                started_at = time.time()

                try:
                    result = client.scrape_student(roll_no, dob, semesters)
                    self.checkpoints.save_result(run_id, result)
                    self.logger.debug(f"Saved checkpoint for {roll_no}")
                    self._record_completion(success=True, elapsed=time.time() - started_at)
                except StudentScrapeError as exc:
                    retryable = (not exc.permanent) and attempt_no < MAX_STUDENT_ATTEMPTS and not self.stop_event.is_set()
                    if retryable:
                        self.logger.debug(f"Retrying {roll_no} after error: {exc.message}")
                        client.reset_session()
                        self.checkpoints.requeue_student(run_id, roll_no, exc.message)
                        student_list.append(student)
                    else:
                        self.logger.warning(f"Final failure for {roll_no}: {exc.message}")
                        self.checkpoints.save_failure(run_id, roll_no, exc.message)
                        self._record_completion(success=False, elapsed=time.time() - started_at)
                except Exception as exc:
                    message = f"Unhandled worker exception: {type(exc).__name__}"
                    retryable = attempt_no < MAX_STUDENT_ATTEMPTS and not self.stop_event.is_set()
                    if retryable:
                        self.logger.debug(f"Retrying {roll_no} after exception: {exc}")
                        client.reset_session()
                        self.checkpoints.requeue_student(run_id, roll_no, message)
                        student_list.append(student)
                    else:
                        self.logger.error(f"Final worker exception for {roll_no}: {exc}")
                        self.checkpoints.save_failure(run_id, roll_no, message)
                        self._record_completion(success=False, elapsed=time.time() - started_at)
                finally:
                    time.sleep(random.uniform(0.02, 0.1))

            final_state = "stopped" if self.stop_event.is_set() else "finished"
            self._update_status("Exporting checkpointed results to Excel...")
            self._export_checkpoint(run_id, output_file, semesters)
            self.checkpoints.mark_run_status(run_id, final_state)
            self.last_run_state = final_state
            self.last_run_summary = self._build_run_summary(output_file, client.session_bootstraps)
            self._update_status("Stopped" if final_state == "stopped" else "Finished")
        except Exception as exc:
            self.logger.error(f"Critical error in HTTP engine loop: {exc}")
            if self.active_run_id:
                try:
                    self.checkpoints.mark_run_status(self.active_run_id, "stopped")
                except Exception:
                    pass
            self.last_run_state = "stopped"
            self._update_status("Stopped due to error")
        finally:
            self.callbacks.get("on_finish", lambda: None)()

    def _export_checkpoint(self, run_id, output_file, semesters):
        self.excel.export_from_checkpoint(self.checkpoints, run_id, output_file, semesters)

    def _build_run_summary(self, output_file, bootstraps):
        with self._progress_lock:
            processed = self._progress_state["processed"]
            failed = self._progress_state["failed"]
            avg_seconds = self._progress_state["time_total"] / max(1, self._progress_state["time_count"])

        return {
            "state": self.last_run_state,
            "processed": processed,
            "failed": failed,
            "avg_seconds": avg_seconds,
            "bootstraps": bootstraps,
            "output_file": output_file,
        }
