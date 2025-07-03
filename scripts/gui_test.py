from random import randint
import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Temperature Monitor")

        # Temperature vs time dynamic plot
        self.plot_graph = pg.PlotWidget()
        self.update_freq = 200
        # self.setCentralWidget(self.plot_graph)
        # Create a button and add it to a layout
        self.button = QtWidgets.QPushButton("Start/Stop")
        self.button.clicked.connect(self.toggle_timer)
        
        # Create layout to hold plot and button
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.plot_graph)
        layout.addWidget(self.button)
        
        # Create a widget to hold the layout
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.plot_graph.setBackground("w")
        pen = pg.mkPen(color=(255, 0, 0))
        # self.plot_graph.setTitle("Temperature vs Time", color="b", size="20pt")
        # styles = {"color": "red", "font-size": "18px"}
        # self.plot_graph.setLabel("left", "Temperature (°C)", **styles)
        # self.plot_graph.setLabel("bottom", "Time (min)", **styles)
        # self.plot_graph.addLegend()
        # self.plot_graph.showGrid(x=False, y=True)
        # self.plot_graph.setYRange(20, 40)
        self.time = list(range(10))
        self.temperature = [randint(20, 40) for _ in range(10)]
        # Get a line reference
        self.line = self.plot_graph.plot(
            self.time,
            self.temperature,
            name="Temperature Sensor",
            pen=pen,
        )
        # Add a timer to simulate new temperature measurements
        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.update_freq)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

    def toggle_timer(self):
        print("toggle_timer")

    def update_plot(self):
        self.time = self.time[1:]
        self.time.append(self.time[-1] + 1)
        self.temperature = self.temperature[1:]
        self.temperature.append(randint(20, 40))
        self.line.setData(self.time, self.temperature)

app = QtWidgets.QApplication([])
main = MainWindow()
main.show()
app.exec()