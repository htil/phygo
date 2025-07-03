from random import randint
from htil_eeg import HTIL_EEG 
from brainflow.board_shim import BoardIds, BoardShim
import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets
import numpy as np
import collections

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.configure_gui()

        # Set how often to update the plot (ms)
        self.update_freq = 100
        self.sample_rate = 200

        # Set size of data snapshot. How long to keep old data
        self.data_length_seconds = 10
        self.data_size = self.sample_rate * self.data_length_seconds

        self.channels = [0] # increase when more channels are added
        self.channelStreams = [collections.deque(
            maxlen=self.data_size) for channel in self.channels]  # set up channel data streams

        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.update_freq)
        self.timer.timeout.connect(self.update_plot)

    def configure_gui(self):
        self.setWindowTitle("Windows Ganglion Tester")

        self.plot_graph = pg.PlotWidget()
        ymin = -10000
        ymax = 10000
        self.plot_graph.setYRange(ymin, ymax)


        # Create Start Button
        self.button = QtWidgets.QPushButton("Start")
        self.button.clicked.connect(self.start_ganglion)

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
        layout.addWidget(self.plot_graph)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.button)
        layout.addWidget(self.button2)
        layout.addWidget(self.text_input)
        
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
            self.h_eeg = HTIL_EEG(BoardIds.GANGLION_BOARD.value, serial_number=self.text_input.text())
            self.connect_button.setEnabled(False)  # Disable connect button on success
        except Exception as e:
            # Show error message if connection fails
            QtWidgets.QMessageBox.critical(self, "Connection Error", 
                f"Failed to connect to Ganglion board: {str(e)}")
            return

    def stop_ganglion(self):
        # Stop the stream
        self.h_eeg.stop_stream()
        # Stop the timer
        self.timer.stop()

    def start_ganglion(self):
         # Setup Ganglion 
        self.h_eeg.start_stream()   
        # Add a timer to simulate new temperature measurements
        self.timer.start()

    def update_plot(self):
        df = self.h_eeg.get_recent_ganglion_data()
        data = np.array(df.iloc[:,1]) # Get Sensor data
        
        # Append each value individually to the deque
        for value in data:
            self.channelStreams[0].append(value)
            
        array = np.array(self.channelStreams[0], dtype=np.float64)
        self.line.setData(array)

app = QtWidgets.QApplication([])
main = MainWindow()
main.show()
app.exec()