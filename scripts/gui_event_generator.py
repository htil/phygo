from random import randint
import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets
import os


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.configure_gui()

    def configure_gui(self):
        # Set window position to center of screen

        screen = QtWidgets.QDesktopWidget().screenGeometry()
        self.setGeometry(0, 0, 600, 400)  # Set window size
        size = self.geometry()
        self.move(int((screen.width() - size.width()) / 2),
                 int((screen.height() - size.height()) / 2))
        self.setWindowTitle("Event Generator")
    

        # GUI Components
        self.button = QtWidgets.QPushButton("Generate")
        self.button.clicked.connect(self.run)
        self.event_label = QtWidgets.QLabel("Number of Events")
        
        # Create text input field
        self.event_count_input = QtWidgets.QLineEdit()
        self.event_count_input.setText("20")

         # Create text input field
        self.sfreq_input = QtWidgets.QLineEdit()
        self.sfreq_input.setText("200")
        self.sfreq_label = QtWidgets.QLabel("Sampling Frequency")

        
         # Create text input field
        self.epoch_length_input = QtWidgets.QLineEdit()
        self.epoch_length_input.setText("2")
        self.epoch_length_label = QtWidgets.QLabel("Epoch Length")

         # Create text input field
        self.labels_input = QtWidgets.QLineEdit()
        self.labels_input.setText("Relax,Thumb,Index")
        self.labels_label = QtWidgets.QLabel("Labels")


         # Create text input field
        self.event_file_path_input = QtWidgets.QLineEdit()
        self.event_file_path_input.setText("study5")
        self.event_file_path_label = QtWidgets.QLabel("Event File Path")

        # Add components to layouts
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.event_label)
        layout.addWidget(self.event_count_input)
        layout.addWidget(self.sfreq_label)
        layout.addWidget(self.sfreq_input)
        layout.addWidget(self.epoch_length_label)
        layout.addWidget(self.epoch_length_input)
        layout.addWidget(self.labels_label)
        layout.addWidget(self.labels_input)
        layout.addWidget(self.event_file_path_label)
        layout.addWidget(self.event_file_path_input)
        layout.addWidget(self.button)


        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)


    def append_line_to_file(self, file_path, line):
        with open(file_path, 'a') as f:
            f.write(line + '\n')

    def generate_events(self, file_path):
        for i in range(self.num_of_events ):
            latency = i *  int(self.epoch_length) * int(self.sfreq) 
            label = i % len(self.labels)
            if (i > 0):
                self.append_line_to_file(file_path, f"{latency}, 0, {label}")
            elif (i == 0):
                self.append_line_to_file(file_path, f"{self.sfreq}, 0, {label}")

    def check_file_exists(self,file_path):
        if os.path.exists(file_path):
            os.remove(file_path) 

    def write_labels_to_file(self, file_path):
        # labels_path = file_path.replace('.txt', '_event_labels.txt')
        self.check_file_exists(file_path)
        self.append_line_to_file(file_path, ','.join(self.labels))


    def run(self):
        self.event_count = self.event_count_input.text()
        self.sfreq = self.sfreq_input.text()
        self.epoch_length = self.epoch_length_input.text()
        self.labels = self.labels_input.text().split(',')
        self.event_file_path = self.event_file_path_input.text()
        self.num_of_events =  int(self.event_count)  * len(self.labels)
        event_file_path = f'events/{self.event_file_path}.txt'
        event_labels_file_path = f'events/{self.event_file_path}_event_labels.txt'

        self.check_file_exists(event_file_path)
        self.generate_events(event_file_path)
        self.write_labels_to_file(event_labels_file_path)

        # Show success message when events are generated
        estimated_time = (int(self.num_of_events) * int(self.epoch_length) / 60)
        estimated_time = round(estimated_time, 2)
        QtWidgets.QMessageBox.information(self, "Success", 
            f"Events generated successfully!\nEvent file: {self.event_file_path}.txt\nLabels file: {self.event_file_path}_event_labels.txt\nEstimated study time: {estimated_time} minutes")


app = QtWidgets.QApplication([])
main = MainWindow()
main.show()
app.exec()