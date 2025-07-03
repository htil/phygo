from random import randint
import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets
import numpy as np
import collections
from ganglion import Ganglion
import random
import pandas as pd
import time

class EventWorker(QtCore.QObject):
    status_update = QtCore.pyqtSignal(str)
    
    def __init__(self, window, event_labels):
        super().__init__()
        self.window = window
        self.event_labels = event_labels
    
    def run(self):
        while self.window.event_index < len(self.window.events):
            current_event = self.window.events.iloc[self.window.event_index]
            wait = int(current_event[0])
            _wait = int(wait - self.window.epoch_lenght_array[-1])
           
            label = str(current_event[2])
            label = self.event_labels[current_event[2]]
            # print('label:', label)
            self.status_update.emit(label)
            QtCore.QThread.msleep(_wait) 
            # print('wait:', _wait)
            # print('elapsed:', (time.time() - self.window.start_time) * 1000)
            self.window.epoch_lenght_array.append(current_event[0])
            self.window.event_index += 1
        else:
            self.status_update.emit("Done")
            self.event_index = 0
            self.window.worker_thread.quit()
            self.window.worker_thread.wait()
            # self.window.worker_thread.stop()
            # return False
        
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, event_labels):
        super().__init__()

        self.configure_gui()

        # Set how often to update the plot (ms)
        self.update_freq = 100
        self.epoch_length = 3000
        self.sample_rate = 200
        self.events = ['Relax', 'Squeeze', 'Lift']
        self.is_paused = False
        self.event_labels = event_labels

        # Set size of data snapshot. How long to keep old data
        self.data_length_seconds = 10
        self.data_size = self.sample_rate * self.data_length_seconds

        self.channels = [0] # increase when more channels are added
        self.channelStreams = [collections.deque(
            maxlen=self.data_size) for channel in self.channels]  # set up channel data streams

        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.update_freq)
        self.timer.timeout.connect(self.update_plot)

        # self.timer2 = QtCore.QTimer()
        # self.timer2.setInterval(self.epoch_length)
        # self.timer2.timeout.connect(self.update_status)

        self.events = None
        self.event_index = 0

        self.events = pd.read_csv('events/study1.txt', header=None)
        self.epoch_lenght_array = [0]
        #self.read_events()

    def read_events(self):
        # Create worker thread
        self.worker_thread = QtCore.QThread()
        # Create worker object
        self.worker = EventWorker(self, self.event_labels)
        # Move worker to thread
        self.worker.moveToThread(self.worker_thread)
        # Connect signals
        self.worker_thread.started.connect(self.worker.run)
        self.worker.status_update.connect(self.status_label.setText)
        # Start thread
        self.worker_thread.start()



    def configure_gui(self):
        self.setWindowTitle("Windows Ganglion Tester")
        # Create large text label

        # Add label
        self.status_label = QtWidgets.QLabel("")
        font = self.status_label.font()
        font.setPointSize(24)
        self.status_label.setFont(font)
        self.status_label.setFixedHeight(500)
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)


        self.plot_graph = pg.PlotWidget()
        ymin = -10000
        ymax = 10000
        self.plot_graph.setYRange(ymin, ymax)

        # Create Start Button
        self.button = QtWidgets.QPushButton("Start")
        self.button.clicked.connect(self.start_ganglion)

        # Create Start Button
        self.start_events_button = QtWidgets.QPushButton("Start Events")
        self.start_events_button.clicked.connect(self.start_events)

        # Create Stop Button
        self.button2 = QtWidgets.QPushButton("Stop")
        self.button2.clicked.connect(self.stop_ganglion)

        # Create Connect Button
        self.connect_button = QtWidgets.QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_ganglion)

        # Create text input field
        self.text_input = QtWidgets.QLineEdit()
        self.text_input.setText("COM19")
        # self.text_input.setPlaceholderText("COM19")

        # Create layout to hold plot and button
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.plot_graph)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.button)
        layout.addWidget(self.button2)
        layout.addWidget(self.text_input)
        layout.addWidget(self.start_events_button)
        
        # Create a widget to hold the layout
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

                # Style Plot
        self.plot_graph.setBackground("w")
        pen = pg.mkPen(color=(255, 0, 0))

        # Get a line reference
        self.line = self.plot_graph.plot([], pen=pen)


    def connect_ganglion(self):
        try:
            # Attempt to connect to the Ganglion board
            self.sensor = Ganglion(serial_number=self.text_input.text())
            self.connect_button.setEnabled(False)  # Disable connect button on success
            self.status_label.setText("Connected")
        except Exception as e:
            # Show error message if connection fails
            QtWidgets.QMessageBox.critical(self, "Connection Error", 
                f"Failed to connect to Ganglion board: {str(e)}")
            return

    def update_status(self):
        self.status_label.setText("Starting")
        if self.is_paused:
            self.status_label.setText("Paused")
        else:
            random_event = random.choice(self.events)
            self.status_label.setText(random_event)
        self.is_paused = not self.is_paused

    def stop_ganglion(self):
        # Stop the stream
        self.sensor.stop_stream()
        # Stop the timer
        self.timer.stop()
        # self.timer2.stop()

    def start_events(self):
        self.start_time = time.time()
        self.read_events()

    def start_ganglion(self):
         # Setup Ganglion 
        self.sensor.start_stream()   
        # Add a timer to simulate new temperature measurements
        self.timer.start()
        # self.timer2.start()

    def update_plot(self):
        df = self.sensor.get_recent_ganglion_data()
        data = np.array(df.iloc[:,1]) # Get Sensor data
        
        # Append each value individually to the deque
        for value in data:
            self.channelStreams[0].append(value)
            
        array = np.array(self.channelStreams[0], dtype=np.float64)
        self.line.setData(array)

app = QtWidgets.QApplication([])
main = MainWindow(['Relax', 'Squeeze', 'Lift'])
main.show()
app.exec()