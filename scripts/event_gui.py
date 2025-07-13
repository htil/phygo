from random import randint
import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets
import numpy as np
import collections
from ganglion import Ganglion
import random
import pandas as pd
import time
from beeply.notes import *






class EventWorker(QtCore.QObject):
    status_update = QtCore.pyqtSignal(str)
    
    def __init__(self, window, event_labels, sample_rate=200):
        super().__init__()
        self.window = window
        self.event_labels = event_labels
        self.sample_rate = sample_rate
        self.force_stop = False

    def stop(self):
        self.force_stop = True
    
    def run(self):
        while self.window.event_index < len(self.window.events):
            current_event = self.window.events.iloc[self.window.event_index]
            # print('current_event:', current_event)
            wait = int(current_event[0])
            wait_in_ms = (wait / self.sample_rate) * 1000
            # print('wait_in_ms:', wait_in_ms)
            _wait = int(wait_in_ms - self.window.epoch_lenght_array[-1])
           
            label = str(current_event[2])
            label = self.event_labels[current_event[2]]
            # print('label:', label)
            QtCore.QThread.msleep(_wait) 
            self.status_update.emit(label)
            self.window.play_sound()
            # print('wait:', _wait)
            # print('elapsed:', (time.time() - self.window.start_time) * 1000)
            self.window.epoch_lenght_array.append(wait_in_ms)
            self.window.event_index += 1
            if self.force_stop:
                break
        else:
            self.status_update.emit("Done")
            # self.window.event_index = 0
            self.window.end_events(force=False)
            # self.window.worker_thread.quit()
            # self.window.worker_thread.wait()
            # self.window.worker_thread.stop()
            # return False
        
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.configure_gui()

        # Set how often to update the plot (ms)
        self.update_freq = 100
        self.epoch_length = 3000
        self.sample_rate = 200
        # self.events = ['Relax', 'Squeeze', 'Lift']
        self.is_paused = False

        # Set size of data snapshot. How long to keep old data
        self.data_length_seconds = 10
        self.data_size = self.sample_rate * self.data_length_seconds

        self.channels = [0] # increase when more channels are added
        self.channelStreams = [collections.deque(
            maxlen=self.data_size) for channel in self.channels]  # set up channel data streams

        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.update_freq)
        self.timer.timeout.connect(self.update_plot)
        self.save_data = False
        self.beeps = beeps()
        # Create worker thread
        self.worker_thread = QtCore.QThread()

        # self.timer2 = QtCore.QTimer()
        # self.timer2.setInterval(self.epoch_length)
        # self.timer2.timeout.connect(self.update_status)

        # self.events = None

    def play_sound(self):
        if self.save_toggle.isChecked():
            self.beeps.hear('A_')

    def read_events(self):
        self.event_index = 0
        event_file_name = self.event_file_name.text()
        self.event_labels = pd.read_csv(f'events/{event_file_name}_event_labels.txt', header=None)
        self.event_labels = self.event_labels.iloc[0].tolist()
        # print(self.event_labels)

        self.events = pd.read_csv(f'events/{event_file_name}.txt', header=None)
        self.epoch_lenght_array = [0]
        self.saved_df = pd.DataFrame()

        # If thread already running, stop it and reset variables
        if(self.worker_thread.isRunning()):
            print("Worker thread is running")
 
        # Create worker object
        self.worker = EventWorker(self, self.event_labels)
        # Move worker to thread
        self.worker.moveToThread(self.worker_thread)
        # Connect signals
        self.worker_thread.started.connect(self.worker.run)
        self.worker.status_update.connect(self.status_label.setText)
        # Start thread
        self.worker_thread.start()
        self.thread_running = True

    def configure_gui(self):
        # Set window position to center of screen
        screen = QtWidgets.QDesktopWidget().screenGeometry()
        self.setGeometry(0, 0, 800, 900)  # Set window size
        size = self.geometry()
        self.move(int((screen.width() - size.width()) / 2),
                 int((screen.height() - size.height()) / 2))
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
        # self.button = QtWidgets.QPushButton("Start")
        # self.button.clicked.connect(self.start_ganglion)

        # Create Start Button
        self.start_events_button = QtWidgets.QPushButton("Start Study")
        self.start_events_button.clicked.connect(self.start_events)

        # # Create Stop Button
        # self.button2 = QtWidgets.QPushButton("Stop")
        # self.button2.clicked.connect(self.stop_ganglion)

        # Create Connect Button
        self.connect_button = QtWidgets.QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_ganglion)

        # Create text input field
        self.text_input = QtWidgets.QLineEdit()
        self.text_input.setText("COM19")
        # Add label for COM port input
        self.text_input_label = QtWidgets.QLabel("COM Port:")

        # Save file name
        self.save_file_name_label = QtWidgets.QLabel("Save File Name:")

        self.save_file_name = QtWidgets.QLineEdit()
        self.save_file_name.setText("study1_data")

        # Create text input field
        self.event_file_name = QtWidgets.QLineEdit()
        self.event_file_name_label = QtWidgets.QLabel("Event File Name:")
        self.event_file_name.setText("study1")

        # Create Stop Study Button
        self.stop_events_button = QtWidgets.QPushButton("Stop Study") 
        self.stop_events_button.clicked.connect(self.end_events)
        

        # Create toggle for saving data
        self.save_toggle = QtWidgets.QCheckBox("Play Sound")
        self.save_toggle.setChecked(False)  # Default to saving data

        # self.text_input.setPlaceholderText("COM19")

        # Create layout to hold plot and button
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.plot_graph)
        
        # Text input fields
        layout.addWidget(self.text_input_label)
        layout.addWidget(self.text_input)

        layout.addWidget(self.save_file_name_label)
        layout.addWidget(self.save_file_name)
        
        layout.addWidget(self.event_file_name_label)
        layout.addWidget(self.event_file_name)

        layout.addWidget(self.save_toggle)

        
        # Buttons
        layout.addWidget(self.connect_button)
        # layout.addWidget(self.button)
        # layout.addWidget(self.button2)
        layout.addWidget(self.start_events_button)
        layout.addWidget(self.stop_events_button)

        # Create a widget to hold the layout
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        # Style Plot
        self.plot_graph.setBackground("w")
        pen = pg.mkPen(color=(255, 0, 0))

        # Get a line reference
        self.line = self.plot_graph.plot([], pen=pen)

    def end_events(self, force=True):
        self.save_data = False
        file_name = self.save_file_name.text()
        if force == False:
            self.saved_df.to_csv(f'data/{file_name}.csv', index=False)
        self.end_worker_thread()

    def end_worker_thread(self):
        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            self.worker.stop()
            self.worker_thread.quit()
            self.worker_thread.wait()
        

    def connect_ganglion(self):
        try:
            # Attempt to connect to the Ganglion board
            self.sensor = Ganglion(serial_number=self.text_input.text())
            self.connect_button.setEnabled(False)  # Disable connect button on success
            self.start_ganglion()
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
        self.save_data = True
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

        if (self.save_data == True):
            if (self.saved_df.empty):
                self.saved_df = df
            else:
                self.saved_df = pd.concat([self.saved_df, df], ignore_index=True)
                # print(self.saved_df) 
                #print(self.saved_df.shape)   
        
        # Append each value individually to the deque
        for value in data:
            self.channelStreams[0].append(value)
            
        array = np.array(self.channelStreams[0], dtype=np.float64)
        self.line.setData(array)

app = QtWidgets.QApplication([])
main = MainWindow()
main.show()
app.exec()