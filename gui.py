from __future__ import annotations

from datetime import datetime
import customtkinter as ctk
import logging
import os
import queue
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

from runtime.config import APP_LABEL
from runtime.logger import app_logger
from runtime.utils import get_logs_dir, get_output_dir

from engine import HttpScraperEngine


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(APP_LABEL)
        self.geometry("800x680")
        self.minsize(600, 500)
        self.resizable(True, True)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.input_file_var = ctk.StringVar()
        self.semester_vars = {i: ctk.BooleanVar(value=False) for i in range(1, 9)}
        self.all_semesters_var = ctk.BooleanVar(value=False)

        self.status_var = ctk.StringVar(value="Ready to Start")
        self.progress_text_var = ctk.StringVar(value="0 / 0 Students Completed")
        self.current_output_file = None
        self.resume_run_meta = None
        self.is_paused = False

        self.log_queue = queue.Queue()
        app_logger.setup_gui_logging(self.log_queue)

        self.engine = HttpScraperEngine(
            {
                "set_status": self._set_status,
                "set_progress": self._set_progress,
                "on_finish": self._on_finish,
                "set_stats": self._set_stats,
            }
        )

        self._build_ui()
        self.poll_logs()

    def _build_ui(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=30, pady=(25, 10))

        title_label = ctk.CTkLabel(header_frame, text=APP_LABEL, font=("Helvetica", 32, "bold"))
        title_label.pack(side="left")


        input_group = ctk.CTkFrame(self)
        input_group.pack(fill="x", padx=30, pady=10)

        sem_container = ctk.CTkFrame(input_group, fg_color="transparent")
        sem_container.pack(fill="x", padx=15, pady=(15, 5))

        ctk.CTkLabel(sem_container, text="Target Semesters:", font=("Helvetica", 13, "bold")).pack(anchor="w", pady=(0, 5))

        sem_grid = ctk.CTkFrame(sem_container, fg_color="transparent")
        sem_grid.pack(fill="x")

        self.sem_checkboxes = []
        for i in range(1, 9):
            checkbox = ctk.CTkCheckBox(
                sem_grid,
                text=f"Semester {i}",
                variable=self.semester_vars[i],
                command=self._on_sem_toggle,
                width=100,
            )
            checkbox.grid(row=(i - 1) // 4, column=(i - 1) % 4, padx=10, pady=5, sticky="w")
            self.sem_checkboxes.append(checkbox)

        self.all_sem_cb = ctk.CTkCheckBox(
            sem_grid,
            text="All Semesters",
            variable=self.all_semesters_var,
            command=self._on_all_sem_toggle,
            text_color="#5bc0de",
        )
        self.all_sem_cb.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="w")

        self.selected_summary_label = ctk.CTkLabel(sem_grid, text="Selected: Semester 1", font=("Helvetica", 12), text_color="gray")
        self.selected_summary_label.grid(row=2, column=2, columnspan=2, padx=10, pady=10, sticky="w")

        self.semester_vars[1].set(True)
        self._update_summary_label()



        row3 = ctk.CTkFrame(input_group, fg_color="transparent")
        row3.pack(fill="x", padx=15, pady=(5, 15))

        ctk.CTkLabel(row3, text="Input Data:", font=("Helvetica", 13, "bold")).pack(side="left")
        self.file_display = ctk.CTkEntry(
            row3,
            textvariable=self.input_file_var,
            placeholder_text="Select your Excel file...",
            width=380,
            state="disabled",
        )
        self.file_display.pack(side="left", padx=10)

        ctk.CTkButton(row3, text="Browse File", width=100, command=self._browse_file).pack(side="left")

        control_frame = ctk.CTkFrame(self, fg_color="transparent")
        control_frame.pack(fill="x", padx=30, pady=15)

        self.start_btn = ctk.CTkButton(
            control_frame,
            text="START SCRAPER",
            font=("Helvetica", 15, "bold"),
            height=45,
            width=180,
            command=self._start,
        )
        self.start_btn.pack(side="left", padx=(0, 10))

        self.pause_btn = ctk.CTkButton(
            control_frame,
            text="PAUSE",
            font=("Helvetica", 15, "bold"),
            height=45,
            width=100,
            fg_color="#f0ad4e",
            hover_color="#eea236",
            text_color=("black", "black"),
            command=self._pause_resume,
            state="disabled",
        )
        self.pause_btn.pack(side="left", padx=10)

        self.stop_btn = ctk.CTkButton(
            control_frame,
            text="STOP",
            font=("Helvetica", 15, "bold"),
            height=45,
            width=100,
            fg_color="#d9534f",
            hover_color="#c9302c",
            command=self._stop,
            state="disabled",
        )
        self.stop_btn.pack(side="left", padx=10)

        self.open_dir_btn = ctk.CTkButton(
            control_frame,
            text="Open Output Folder",
            height=45,
            fg_color="#5bc0de",
            hover_color="#31b0d5",
            text_color="black",
            command=self._open_output_dir,
        )
        self.open_dir_btn.pack(side="right")

        status_group = ctk.CTkFrame(self)
        status_group.pack(fill="x", padx=30, pady=10)

        status_header = ctk.CTkFrame(status_group, fg_color="transparent")
        status_header.pack(fill="x", padx=15, pady=(10, 5))

        self.status_label = ctk.CTkLabel(status_header, textvariable=self.status_var, font=("Helvetica", 14, "bold"), text_color="#1f538d")
        self.status_label.pack(side="left")

        self.count_label = ctk.CTkLabel(status_header, textvariable=self.progress_text_var, font=("Helvetica", 12))
        self.count_label.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(status_group, width=640)
        self.progress_bar.pack(padx=15, pady=(0, 10))
        self.progress_bar.set(0)

        stats_frame = ctk.CTkFrame(status_group, fg_color="transparent")
        stats_frame.pack(fill="x", padx=15, pady=(0, 10))

        self.stat_vars = {
            "total": ctk.StringVar(value="Total: 0"),
            "processed": ctk.StringVar(value="Processed: 0"),
            "failed": ctk.StringVar(value="Failed: 0"),
            "success_rate": ctk.StringVar(value="Success %: 0.0%"),
            "est_time": ctk.StringVar(value="Est. Time: --"),
        }

        for i, variable in enumerate(self.stat_vars.values()):
            label = ctk.CTkLabel(stats_frame, textvariable=variable, font=("Helvetica", 12, "bold"))
            label.grid(row=0, column=i, padx=5, sticky="ew")
            stats_frame.columnconfigure(i, weight=1)

        log_label = ctk.CTkLabel(self, text="Activity Logs", font=("Helvetica", 12, "bold"), text_color="gray")
        log_label.pack(anchor="w", padx=35, pady=(10, 0))

        self.log_box = ctk.CTkTextbox(self, width=690, height=130, font=("Consolas", 11), state="disabled")
        self.log_box.pack(padx=30, pady=(5, 10))

        footer_label = ctk.CTkLabel(
            self,
            text="designed with ❤️ for educators | http automation simplified",
            font=("Helvetica", 11),
            text_color="gray",
        )
        footer_label.pack(pady=(5, 10))

    def _browse_file(self):
        filename = filedialog.askopenfilename(title="Select Input Excel", filetypes=[("Excel Files", "*.xlsx")])
        if filename:
            self.input_file_var.set(filename)
            app_logger.info(f"File Selected: {os.path.basename(filename)}")

            self.resume_run_meta = self.engine.find_resumable_run(filename)
            if self.resume_run_meta:
                self.current_output_file = self.resume_run_meta["output_file"]
                app_logger.info("Detected resumable checkpointed run for this file. Ready to resume!")
            else:
                self.current_output_file = None
                self._clear_old_logs()

    def _clear_old_logs(self):
        try:
            logs_dir = get_logs_dir()
            if os.path.exists(logs_dir):
                current_log = None
                if app_logger.logger.handlers:
                    for handler in app_logger.logger.handlers:
                        if isinstance(handler, logging.FileHandler) and hasattr(handler, "baseFilename"):
                            current_log = os.path.abspath(handler.baseFilename)
                            break
                for filename in os.listdir(logs_dir):
                    if not filename.endswith(".log"):
                        continue
                    filepath = os.path.join(logs_dir, filename)
                    if current_log and os.path.abspath(filepath) == os.path.abspath(current_log):
                        continue
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
                app_logger.info("Cleared old session logs.")
        except Exception as exc:
            app_logger.warning(f"Failed to clear old logs: {exc}")

    def _update_summary_label(self):
        selected = [str(i) for i in range(1, 9) if self.semester_vars[i].get()]
        if self.all_semesters_var.get() or len(selected) == 8:
            self.selected_summary_label.configure(text="Selected: All Semesters (8 total)")
        elif not selected:
            self.selected_summary_label.configure(text="Selected: None")
        else:
            self.selected_summary_label.configure(text=f"Selected: Sem {', '.join(selected)} ({len(selected)} total)")

    def _on_sem_toggle(self):
        if self.all_semesters_var.get():
            self.all_semesters_var.set(False)
        self._update_summary_label()

    def _on_all_sem_toggle(self):
        is_all = self.all_semesters_var.get()
        state = "disabled" if is_all else "normal"
        for i in range(1, 9):
            self.semester_vars[i].set(is_all)
            self.sem_checkboxes[i - 1].configure(state=state)
        self._update_summary_label()

    def _open_output_dir(self):
        output_dir = get_output_dir()
        try:
            if sys.platform == "darwin":
                os.system(f"open '{output_dir}'")
            elif sys.platform == "win32":
                os.startfile(output_dir)
            else:
                os.system(f"xdg-open '{output_dir}'")
        except Exception as exc:
            messagebox.showerror("Open Folder Error", f"Could not open output folder:\n{exc}")

    def _start(self):
        input_file = self.input_file_var.get()
        if not input_file or not os.path.exists(input_file):
            messagebox.showerror("Selection Error", "Please select a valid input Excel file first.")
            return

        selected_sems = [i for i in range(1, 9) if self.semester_vars[i].get()]
        if not selected_sems:
            messagebox.showerror("Selection Error", "Please select at least one semester.")
            return

        if self.resume_run_meta and sorted(selected_sems) != sorted(self.resume_run_meta["semesters"]):
            app_logger.info("Selected semesters differ from the resumable run. Starting a fresh run.")
            self.current_output_file = None
            self.resume_run_meta = None

        output_dir = get_output_dir()
        if not self.current_output_file:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.current_output_file = os.path.join(output_dir, f"AKTU_HTTP_Report_{timestamp}.xlsx")

        self.resume_run_meta = {
            "input_file": input_file,
            "output_file": self.current_output_file,
            "semesters": selected_sems,
        }

        self.start_btn.configure(state="disabled", text="RUNNING...")
        self.pause_btn.configure(state="normal", text="PAUSE")
        self.stop_btn.configure(state="normal")
        self.all_sem_cb.configure(state="disabled")
        for checkbox in self.sem_checkboxes:
            checkbox.configure(state="disabled")

        self.is_paused = False
        self.progress_bar.set(0)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        self.engine.start_scraping(
            input_file=input_file,
            output_file=self.current_output_file,
            semesters=selected_sems,
        )

    def _pause_resume(self):
        if not self.is_paused:
            self.is_paused = True
            self.pause_btn.configure(text="RESUME", fg_color="#5cb85c", hover_color="#4cae4c", text_color=("white", "white"))
            self._set_status("Paused (Will pause after current task)")
            self.engine.pause_scraping()
        else:
            self.is_paused = False
            self.pause_btn.configure(text="PAUSE", fg_color="#f0ad4e", hover_color="#eea236", text_color=("black", "black"))
            self._set_status("Resuming...")
            self.engine.resume_scraping()

    def _stop(self):
        if messagebox.askyesno("Confirm Stop", "Are you sure you want to stop? The current row will finish first."):
            self.pause_btn.configure(state="disabled")
            self.stop_btn.configure(state="disabled")
            self._set_status("Shutdown Signal Sent...")
            if self.is_paused:
                self.engine.resume_scraping()
            self.engine.stop_scraping()

    def _on_finish(self):
        # Called from the background worker thread — schedule real UI work on main thread.
        self.after(0, self._on_finish_ui)

    def _on_finish_ui(self):
        """All UI updates from run completion — must run on the main thread."""
        self.start_btn.configure(state="normal", text="START SCRAPER")
        self.pause_btn.configure(state="disabled", text="PAUSE", fg_color="#f0ad4e", text_color=("black", "black"))
        self.stop_btn.configure(state="disabled")

        self.all_sem_cb.configure(state="normal")
        state = "disabled" if self.all_semesters_var.get() else "normal"
        for checkbox in self.sem_checkboxes:
            checkbox.configure(state=state)

        self.is_paused = False
        summary = self.engine.get_last_run_summary()
        if self.engine.last_run_state == "finished":
            self.progress_text_var.set("Process Completed")
            self.resume_run_meta = None
        else:
            self.progress_text_var.set("Process Stopped")
        messagebox.showinfo("Task Complete", self._build_finish_message(summary))

    def _build_finish_message(self, summary):
        if not summary:
            return "Scraping process has finished or stopped gracefully."

        state_text = "Finished" if summary.get("state") == "finished" else "Stopped"
        lines = [
            f"{state_text} with {summary.get('processed', 0)} processed and {summary.get('failed', 0)} failed.",
            f"Average time per student: {summary.get('avg_seconds', 0.0):.2f}s",
        ]

        output_file = summary.get("output_file")
        if output_file:
            lines.append(f"Report: {output_file}")

        bootstraps = summary.get("bootstraps", 0)
        if bootstraps:
            lines.append(f"HTTP Session Bootstraps: {bootstraps}")

        return "\n".join(lines)

    def _set_status(self, text):
        self.after(0, lambda: self.status_var.set(text))

    def _set_progress(self, current, total):
        if total > 0:
            self.after(0, lambda: self.progress_bar.set(current / total))
            self.after(0, lambda: self.progress_text_var.set(f"{current} / {total} Students Completed"))

    def _set_stats(self, total, processed, failed, est_time):
        attempted = processed + failed
        pct = (processed / attempted) * 100.0 if attempted > 0 else 0.0
        self.after(0, lambda: self.stat_vars["total"].set(f"Total: {total}"))
        self.after(0, lambda: self.stat_vars["processed"].set(f"Processed: {processed}"))
        self.after(0, lambda: self.stat_vars["failed"].set(f"Failed: {failed}"))
        self.after(0, lambda: self.stat_vars["success_rate"].set(f"Success %: {pct:.1f}%"))
        self.after(0, lambda: self.stat_vars["est_time"].set(f"Est. Time: {est_time}"))

    def poll_logs(self):
        while not self.log_queue.empty():
            try:
                record = self.log_queue.get_nowait()
                self.log_box.configure(state="normal")
                self.log_box.insert("end", record + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
            except queue.Empty:
                break
        self.after(100, self.poll_logs)

    def destroy(self):
        if self.engine.thread and self.engine.thread.is_alive():
            if not messagebox.askyesno("Exit", "Scraping is in progress. Closing now will stop all tasks. Proceed?"):
                return
            self.engine.stop_scraping()
            self._set_status("Cleaning up resources...")
            self.update()
            # Wait for the worker thread to finish before tearing down Tk.
            # Without this, the thread may call self.after() on a destroyed root.
            self.engine.thread.join(timeout=5)

        super().destroy()
