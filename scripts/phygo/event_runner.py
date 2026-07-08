"""Background worker that displays event labels on a timed schedule."""

from __future__ import annotations

from PyQt5 import QtCore

from phygo.event_generator import PRE_RECORD_PADDING_MS, REST_LABEL


class EventWorker(QtCore.QObject):
    status_update = QtCore.pyqtSignal(str)
    sequence_finished = QtCore.pyqtSignal()

    def __init__(
        self,
        event_rows,
        event_labels,
        latency_ms: int,
        rest_ms: int,
        pre_record_padding_ms: int = PRE_RECORD_PADDING_MS,
        rest_label: str = REST_LABEL,
    ):
        super().__init__()
        self.event_rows = event_rows
        self.event_labels = event_labels
        self.latency_ms = latency_ms
        self.rest_ms = rest_ms
        self.pre_record_padding_ms = pre_record_padding_ms
        self.rest_label = rest_label
        self.force_stop = False
        self.event_index = 0

    def stop(self):
        self.force_stop = True

    def _wait_after_label(self, label: str) -> None:
        if label == self.rest_label:
            QtCore.QThread.msleep(self.rest_ms)
        else:
            QtCore.QThread.msleep(self.latency_ms)

    def run(self):
        if self.pre_record_padding_ms > 0 and not self.force_stop:
            QtCore.QThread.msleep(self.pre_record_padding_ms)

        while self.event_index < len(self.event_rows):
            current_event = self.event_rows[self.event_index]
            label = self.event_labels[current_event.label_index]

            self.status_update.emit(label)
            self.event_index += 1

            if self.force_stop:
                break

            self._wait_after_label(label)
        else:
            self.status_update.emit("Done")
            self.sequence_finished.emit()
