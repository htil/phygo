"""Combined PhyGo GUI for event design and Ganglion recording."""

from __future__ import annotations

import collections
import os
import sys
import time

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets

from ganglion import Ganglion

from phygo.event_generator import (
    DEFAULT_REST_MS,
    PRE_RECORD_PADDING_MS,
    REST_LABEL,
    EventRow,
    generate_events,
    estimate_duration_minutes,
    interleaved_presentation_time_samples,
    labels_with_rest,
    parse_labels,
    save_event_files,
    validate_event_rows,
    validate_labels,
    validate_positive_int,
)
from phygo.event_runner import EventWorker
from phygo.recording import (
    resolve_storage_paths,
    save_recording_dataframe,
    validate_output_directory,
)

try:
    from beeply.notes import beeps
except ImportError:
    beeps = None

BEEP_AFTER_LABEL_MS = 100


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, scripts_dir: str | None = None):
        super().__init__()
        default_dir = scripts_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.scripts_dir, self.events_dir, self.data_dir = resolve_storage_paths(default_dir)

        self.sample_rate = 200
        self.latency_ms = 2000
        self.rest_ms = DEFAULT_REST_MS
        self.update_freq = 100
        self.data_length_seconds = 10
        self.data_size = self.sample_rate * self.data_length_seconds
        self.channels = [0]
        self.channel_streams = [
            collections.deque(maxlen=self.data_size) for _ in self.channels
        ]

        self.event_rows: list[EventRow] = []
        self.presented_event_rows: list[EventRow] = []
        self.event_labels: list[str] = []
        self.events_confirmed = False
        self.sensor = None
        self.save_data = False
        self.saved_df = pd.DataFrame()
        self.worker = None
        self.worker_thread = None
        self.beeps = beeps() if beeps else None

        self._build_ui()
        self._center_on_screen()

        self.plot_timer = QtCore.QTimer()
        self.plot_timer.setInterval(self.update_freq)
        self.plot_timer.timeout.connect(self._update_plot)

    def _center_on_screen(self):
        screen = QtWidgets.QDesktopWidget().screenGeometry()
        self.setGeometry(0, 0, 960, 820)
        size = self.geometry()
        self.move(
            int((screen.width() - size.width()) / 2),
            int((screen.height() - size.height()) / 2),
        )

    def _build_ui(self):
        self.setWindowTitle("PhyGo")
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        root_layout = QtWidgets.QVBoxLayout(central)
        self.tabs = QtWidgets.QTabWidget()
        root_layout.addWidget(self.tabs)

        self.tabs.addTab(self._build_design_tab(), "1. Design Events")
        self.tabs.addTab(self._build_recording_tab(), "2. Record")

        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Define event labels and generate the event sequence.")

    def _build_design_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        form = QtWidgets.QFormLayout()
        self.labels_input = QtWidgets.QLineEdit("Relax,Thumb,Index")
        self.events_per_label_input = QtWidgets.QLineEdit("20")
        self.sfreq_input = QtWidgets.QLineEdit(str(self.sample_rate))
        self.latency_input = QtWidgets.QLineEdit(str(self.latency_ms))
        self.rest_input = QtWidgets.QLineEdit(str(self.rest_ms))
        self.session_name_input = QtWidgets.QLineEdit("study1")

        form.addRow("Event Labels (comma-separated):", self.labels_input)
        form.addRow("Events per Label:", self.events_per_label_input)
        form.addRow("Sampling Frequency (Hz):", self.sfreq_input)
        form.addRow("Latency (ms):", self.latency_input)
        form.addRow("Rest (ms):", self.rest_input)
        form.addRow("Session Name:", self.session_name_input)
        layout.addLayout(form)

        path_row = QtWidgets.QHBoxLayout()
        self.output_dir_input = QtWidgets.QLineEdit(self.scripts_dir)
        browse_button = QtWidgets.QPushButton("Browse…")
        browse_button.clicked.connect(self._browse_output_dir)
        path_row.addWidget(QtWidgets.QLabel("Project Directory:"))
        path_row.addWidget(self.output_dir_input)
        path_row.addWidget(browse_button)
        layout.addLayout(path_row)

        button_row = QtWidgets.QHBoxLayout()
        generate_button = QtWidgets.QPushButton("Generate Event")
        generate_button.clicked.connect(self._generate_events)
        remove_button = QtWidgets.QPushButton("Remove Selected")
        remove_button.clicked.connect(self._remove_selected_rows)
        confirm_button = QtWidgets.QPushButton("Confirm Events for Recording")
        confirm_button.clicked.connect(self._confirm_events)
        button_row.addWidget(generate_button)
        button_row.addWidget(remove_button)
        button_row.addStretch()
        button_row.addWidget(confirm_button)
        layout.addLayout(button_row)

        self.preview_table = QtWidgets.QTableWidget(0, 4)
        self.preview_table.setHorizontalHeaderLabels(
            ["Latency (samples)", "Placeholder", "Label Index", "Label"]
        )
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.preview_table)

        self.design_summary_label = QtWidgets.QLabel(
            "No events generated yet. Click Generate Event to build the sequence."
        )
        layout.addWidget(self.design_summary_label)

        return widget

    def _build_recording_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        self.status_label = QtWidgets.QLabel("Waiting for event confirmation…")
        font = self.status_label.font()
        font.setPointSize(28)
        self.status_label.setFont(font)
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setMinimumHeight(120)
        layout.addWidget(self.status_label)

        self.plot_graph = pg.PlotWidget()
        self.plot_graph.setBackground("w")
        self.plot_graph.setYRange(-10000, 10000)
        self.line = self.plot_graph.plot([], pen=pg.mkPen(color=(255, 0, 0)))
        layout.addWidget(self.plot_graph)

        connection_form = QtWidgets.QFormLayout()
        self.com_port_input = QtWidgets.QLineEdit("COM19")
        connection_form.addRow("COM Port:", self.com_port_input)
        layout.addLayout(connection_form)

        self.connection_status_label = QtWidgets.QLabel("Connection: Not connected")
        self.recording_status_label = QtWidgets.QLabel("Recording: Idle")
        layout.addWidget(self.connection_status_label)
        layout.addWidget(self.recording_status_label)

        self.play_sound_checkbox = QtWidgets.QCheckBox("Play sound on each event")
        self.play_sound_checkbox.setChecked(False)
        layout.addWidget(self.play_sound_checkbox)

        button_row = QtWidgets.QHBoxLayout()
        self.connect_button = QtWidgets.QPushButton("Connect Ganglion")
        self.connect_button.clicked.connect(self._connect_ganglion)
        self.start_button = QtWidgets.QPushButton("Start Study")
        self.start_button.clicked.connect(self._start_study)
        self.start_button.setEnabled(False)
        self.stop_button = QtWidgets.QPushButton("Stop Study")
        self.stop_button.clicked.connect(lambda: self._end_study(force=True))
        self.stop_button.setEnabled(False)
        button_row.addWidget(self.connect_button)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        layout.addLayout(button_row)

        return widget

    def _set_storage_paths(self, project_dir: str) -> None:
        self.scripts_dir, self.events_dir, self.data_dir = resolve_storage_paths(project_dir)

    def _browse_output_dir(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Project Directory", self.scripts_dir
        )
        if directory:
            self._set_storage_paths(directory)
            self.output_dir_input.setText(self.scripts_dir)

    def _read_labels_from_input(self) -> tuple[list[str] | None, str]:
        labels = parse_labels(self.labels_input.text())
        valid, message = validate_labels(labels)
        if not valid:
            return None, message
        return labels, ""

    def _read_generation_params(self) -> tuple[dict | None, str]:
        labels, label_error = self._read_labels_from_input()
        if label_error:
            return None, label_error

        events_per_label, events_error = validate_positive_int(
            self.events_per_label_input.text(), "Events per label"
        )
        if events_error:
            return None, events_error

        latency_ms, latency_error = validate_positive_int(
            self.latency_input.text(), "Latency"
        )
        if latency_error:
            return None, latency_error
        rest_ms, rest_error = validate_positive_int(self.rest_input.text(), "Rest")
        if rest_error:
            return None, rest_error
        sfreq, sfreq_error = validate_positive_int(
            self.sfreq_input.text(), "Sampling frequency"
        )
        if sfreq_error:
            return None, sfreq_error

        session_name = self.session_name_input.text().strip()
        if not session_name:
            return None, "Session name is required."

        return {
            "labels": labels,
            "events_per_label": events_per_label,
            "sfreq": sfreq,
            "latency_ms": latency_ms,
            "rest_ms": rest_ms,
            "session_name": session_name,
        }, ""

    def _populate_preview_table(self):
        self.preview_table.setRowCount(len(self.event_rows))
        for row_index, event_row in enumerate(self.event_rows):
            latency_item = QtWidgets.QTableWidgetItem(str(event_row.latency))
            placeholder_item = QtWidgets.QTableWidgetItem(str(event_row.placeholder))
            label_index_item = QtWidgets.QTableWidgetItem(str(event_row.label_index))
            label_name = (
                self.event_labels[event_row.label_index]
                if 0 <= event_row.label_index < len(self.event_labels)
                else "?"
            )
            label_item = QtWidgets.QTableWidgetItem(label_name)
            label_item.setFlags(label_item.flags() & ~QtCore.Qt.ItemIsEditable)

            self.preview_table.setItem(row_index, 0, latency_item)
            self.preview_table.setItem(row_index, 1, placeholder_item)
            self.preview_table.setItem(row_index, 2, label_index_item)
            self.preview_table.setItem(row_index, 3, label_item)

    def _read_rows_from_table(self) -> tuple[list[EventRow] | None, str]:
        rows: list[EventRow] = []
        for row_index in range(self.preview_table.rowCount()):
            latency_item = self.preview_table.item(row_index, 0)
            placeholder_item = self.preview_table.item(row_index, 1)
            label_index_item = self.preview_table.item(row_index, 2)

            if not latency_item or not placeholder_item or not label_index_item:
                return None, f"Row {row_index + 1} is incomplete."

            try:
                latency = int(latency_item.text().strip())
                placeholder = int(placeholder_item.text().strip())
                label_index = int(label_index_item.text().strip())
            except ValueError:
                return None, f"Row {row_index + 1} contains invalid numeric values."

            rows.append(
                EventRow(
                    latency=latency,
                    placeholder=placeholder,
                    label_index=label_index,
                )
            )
        return rows, ""

    def _update_design_summary(self):
        if not self.event_rows:
            self.design_summary_label.setText(
                "No events generated yet. Click Generate Event to build the sequence."
            )
            return

        duration = estimate_duration_minutes(
            int(self.events_per_label_input.text()),
            len(parse_labels(self.labels_input.text())),
            self.latency_ms,
            self.rest_ms,
        )
        self.design_summary_label.setText(
            f"{len(self.event_rows)} events defined (including Rest). "
            f"Estimated duration: {duration} minutes."
        )

    def _generate_events(self):
        params, error = self._read_generation_params()
        if error:
            QtWidgets.QMessageBox.warning(self, "Invalid Input", error)
            return

        self.event_labels = labels_with_rest(params["labels"])
        self.latency_ms = params["latency_ms"]
        self.rest_ms = params["rest_ms"]
        self.sample_rate = params["sfreq"]
        self.event_rows = generate_events(
            events_per_label=params["events_per_label"],
            latency_ms=params["latency_ms"],
            rest_ms=params["rest_ms"],
            stimulus_labels=params["labels"],
            sfreq=params["sfreq"],
        )
        self.events_confirmed = False
        self._populate_preview_table()
        self._update_design_summary()
        self.status_bar.showMessage("Event sequence generated. Review and confirm before recording.")

    def _remove_selected_rows(self):
        selected_rows = sorted(
            {index.row() for index in self.preview_table.selectedIndexes()},
            reverse=True,
        )
        for row_index in selected_rows:
            self.preview_table.removeRow(row_index)
        self.events_confirmed = False

    def _confirm_events(self):
        stimulus_labels, label_error = self._read_labels_from_input()
        if label_error:
            QtWidgets.QMessageBox.warning(self, "Missing Labels", label_error)
            return

        all_labels = labels_with_rest(stimulus_labels)

        rows, row_error = self._read_rows_from_table()
        if row_error:
            QtWidgets.QMessageBox.warning(self, "Invalid Events", row_error)
            return

        valid, validation_error = validate_event_rows(rows, all_labels)
        if not valid:
            QtWidgets.QMessageBox.warning(self, "Invalid Events", validation_error)
            return

        output_dir = self.output_dir_input.text().strip()
        valid_dir, dir_error = validate_output_directory(output_dir)
        if not valid_dir:
            QtWidgets.QMessageBox.warning(self, "Invalid Save Location", dir_error)
            return

        self.event_labels = all_labels
        self.event_rows = rows
        self.events_confirmed = True

        latency_ms, latency_error = self._read_latency_ms()
        rest_ms, rest_error = self._read_rest_ms()
        sfreq, sfreq_error = self._read_sampling_frequency()
        if not latency_error and not rest_error and not sfreq_error:
            self.latency_ms = latency_ms
            self.rest_ms = rest_ms
            self.sample_rate = sfreq
            self.event_rows = self._sync_event_sample_times(
                rows, latency_ms, rest_ms, sfreq
            )

        self._set_storage_paths(output_dir)
        self.output_dir_input.setText(self.scripts_dir)
        self._update_design_summary()

        if self.sensor is not None:
            self.start_button.setEnabled(True)

        self.status_label.setText("Ready to record")
        self.status_bar.showMessage(
            f"Events confirmed ({len(rows)} events). Connect the Ganglion and start the study."
        )
        self.tabs.setCurrentIndex(1)

        QtWidgets.QMessageBox.information(
            self,
            "Events Confirmed",
            (
                f"{len(rows)} events are ready for recording.\n"
                f"Session name: {self.session_name_input.text().strip()}\n"
                f"Estimated duration: {estimate_duration_minutes(int(self.events_per_label_input.text()), len(stimulus_labels), self.latency_ms, self.rest_ms)} minutes"
            ),
        )

    def _connect_ganglion(self):
        if self.sensor is not None:
            return

        try:
            self.sensor = Ganglion(serial_number=self.com_port_input.text().strip())
            self.sensor.start_stream()
            self.plot_timer.start()
            self.connect_button.setEnabled(False)
            self.connection_status_label.setText(
                f"Connection: Connected ({self.com_port_input.text().strip()})"
            )
            if self.events_confirmed:
                self.start_button.setEnabled(True)
            self.status_bar.showMessage("Ganglion connected.")
        except Exception as exc:
            self.sensor = None
            QtWidgets.QMessageBox.critical(
                self,
                "Connection Error",
                f"Failed to connect to Ganglion board:\n{exc}",
            )
            self.connection_status_label.setText("Connection: Failed")

    def _play_sound(self):
        if not self.save_data:
            return
        if self.play_sound_checkbox.isChecked() and self.beeps is not None:
            self.beeps.hear("A_")

    def _schedule_beep_after_label(self) -> None:
        QtCore.QTimer.singleShot(BEEP_AFTER_LABEL_MS, self._play_sound)

    def _read_latency_ms(self) -> tuple[int | None, str]:
        latency_ms, error = validate_positive_int(self.latency_input.text(), "Latency")
        return latency_ms, error

    def _read_sampling_frequency(self) -> tuple[int | None, str]:
        sfreq, error = validate_positive_int(self.sfreq_input.text(), "Sampling frequency")
        return sfreq, error

    def _read_rest_ms(self) -> tuple[int | None, str]:
        rest_ms, error = validate_positive_int(self.rest_input.text(), "Rest")
        return rest_ms, error

    def _sync_event_sample_times(
        self, rows: list[EventRow], latency_ms: int, rest_ms: int, sfreq: int
    ) -> list[EventRow]:
        return [
            EventRow(
                latency=interleaved_presentation_time_samples(
                    index, latency_ms, rest_ms, sfreq
                ),
                placeholder=0,
                label_index=row.label_index,
            )
            for index, row in enumerate(rows)
        ]

    def _start_study(self):
        if not self.events_confirmed:
            QtWidgets.QMessageBox.warning(
                self,
                "Events Not Confirmed",
                "Confirm the event sequence on the Design Events tab before starting.",
            )
            return

        if self.sensor is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Not Connected",
                "Connect to the Ganglion device before starting the study.",
            )
            return

        if self.worker_thread is not None and self.worker_thread.isRunning():
            QtWidgets.QMessageBox.information(self, "Study Running", "A study is already in progress.")
            return

        latency_ms, latency_error = self._read_latency_ms()
        if latency_error:
            QtWidgets.QMessageBox.warning(self, "Invalid Latency", latency_error)
            return
        rest_ms, rest_error = self._read_rest_ms()
        if rest_error:
            QtWidgets.QMessageBox.warning(self, "Invalid Rest", rest_error)
            return
        sfreq, sfreq_error = self._read_sampling_frequency()
        if sfreq_error:
            QtWidgets.QMessageBox.warning(self, "Invalid Sampling Frequency", sfreq_error)
            return
        self.latency_ms = latency_ms
        self.rest_ms = rest_ms
        self.sample_rate = sfreq
        self.event_rows = self._sync_event_sample_times(
            self.event_rows, latency_ms, rest_ms, sfreq
        )

        self.start_time = time.time()
        self.save_data = True
        self.saved_df = pd.DataFrame()
        self.presented_event_rows = []
        self.presentation_event_index = 0
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.recording_status_label.setText("Recording: In progress")
        self.status_bar.showMessage("Study started. Recording physiological data…")

        self.worker_thread = QtCore.QThread()
        self.worker = EventWorker(
            event_rows=self.event_rows,
            event_labels=self.event_labels,
            latency_ms=self.latency_ms,
            rest_ms=self.rest_ms,
            pre_record_padding_ms=PRE_RECORD_PADDING_MS,
        )
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.status_update.connect(self._on_event_status)
        self.worker.sequence_finished.connect(lambda: self._end_study(force=False))
        self.worker_thread.start()

    def _on_event_status(self, label: str):
        self.status_label.setText(label)
        if label == "Done" or not self.save_data:
            return

        sample = round((time.time() - self.start_time) * self.sample_rate)
        if self.presentation_event_index < len(self.event_rows):
            label_index = self.event_rows[self.presentation_event_index].label_index
        else:
            label_index = self.event_labels.index(label)

        self.presented_event_rows.append(
            EventRow(latency=sample, placeholder=0, label_index=label_index)
        )
        self.presentation_event_index += 1
        if label != REST_LABEL:
            self._schedule_beep_after_label()

    def _end_worker_thread(self):
        if self.worker is not None:
            self.worker.stop()
        if self.worker_thread is not None and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait()
        self.worker = None
        self.worker_thread = None

    def _end_study(self, force: bool = True):
        self.save_data = False
        self._end_worker_thread()
        self.start_button.setEnabled(self.sensor is not None and self.events_confirmed)
        self.stop_button.setEnabled(False)
        self.recording_status_label.setText("Recording: Stopped")

        session_name = self.session_name_input.text().strip()
        if not session_name:
            QtWidgets.QMessageBox.warning(self, "Missing Session Name", "Session name is required.")
            return

        saved_paths: list[str] = []
        try:
            event_rows_to_save = (
                self.presented_event_rows if self.presented_event_rows else self.event_rows
            )
            event_file, labels_file = save_event_files(
                base_name=session_name,
                rows=event_rows_to_save,
                labels=self.event_labels,
                events_dir=self.events_dir,
            )
            saved_paths.extend([event_file, labels_file])

            if not self.saved_df.empty:
                data_file = save_recording_dataframe(
                    self.saved_df,
                    self.data_dir,
                    session_name,
                )
                saved_paths.append(data_file)
            elif not force:
                QtWidgets.QMessageBox.warning(
                    self,
                    "No Data Recorded",
                    "The study finished but no physiological data was captured.",
                )
        except OSError as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save study files:\n{exc}",
            )
            self.status_bar.showMessage("Error saving study files.")
            return

        if saved_paths:
            message = "Study files saved:\n" + "\n".join(saved_paths)
            QtWidgets.QMessageBox.information(self, "Files Saved", message)
            self.status_bar.showMessage("Study complete. Files saved successfully.")

        if force:
            self.status_label.setText("Study stopped")

    def _update_plot(self):
        if self.sensor is None:
            return

        try:
            df = self.sensor.get_recent_ganglion_data()
        except Exception as exc:
            self.recording_status_label.setText(f"Recording: Error ({exc})")
            return

        if df.empty:
            return

        if self.save_data:
            if self.saved_df.empty:
                self.saved_df = df.copy()
            else:
                self.saved_df = pd.concat([self.saved_df, df], ignore_index=True)

        if df.shape[1] < 2:
            return

        data = np.array(df.iloc[:, 1])
        for value in data:
            self.channel_streams[0].append(value)

        array = np.array(self.channel_streams[0], dtype=np.float64)
        self.line.setData(array)

    def closeEvent(self, event):
        self.save_data = False
        self._end_worker_thread()
        if self.sensor is not None:
            try:
                self.sensor.stop_stream()
            except Exception:
                pass
        self.plot_timer.stop()
        event.accept()


def run_app():
    scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(scripts_dir=scripts_dir)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
