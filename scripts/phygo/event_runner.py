"""Background worker that displays event labels on a timed schedule."""

from __future__ import annotations

from PyQt5 import QtCore


class EventWorker(QtCore.QObject):
    status_update = QtCore.pyqtSignal(str)
    sequence_finished = QtCore.pyqtSignal()

    def __init__(self, event_rows, event_labels, sample_rate=200):
        super().__init__()
        self.event_rows = event_rows
        self.event_labels = event_labels
        self.sample_rate = sample_rate
        self.force_stop = False
        self.event_index = 0
        self.epoch_length_ms = [0]

    def stop(self):
        self.force_stop = True

    def run(self):
        while self.event_index < len(self.event_rows):
            current_event = self.event_rows[self.event_index]
            wait_samples = int(current_event.latency)
            wait_in_ms = (wait_samples / self.sample_rate) * 1000
            wait_delta_ms = int(wait_in_ms - self.epoch_length_ms[-1])

            label = self.event_labels[current_event.label_index]
            if wait_delta_ms > 0:
                QtCore.QThread.msleep(wait_delta_ms)

            self.status_update.emit(label)
            self.epoch_length_ms.append(wait_in_ms)
            self.event_index += 1

            if self.force_stop:
                break
        else:
            self.status_update.emit("Done")
            self.sequence_finished.emit()
