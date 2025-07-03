from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
import pandas as pd
import numpy as np

class Ganglion:
    def __init__(self, serial_number=""):
        self.serial_number = serial_number
        params = BrainFlowInputParams()
        params.serial_port = serial_number
        self.board = BoardShim(BoardIds.GANGLION_BOARD.value, params)
        self.board.prepare_session()
        self.session_started = False

    def start_stream(self):
        self.board.start_stream()
        self.session_started = True
    
    def stop_stream(self):
        self.board.stop_stream()
        self.session_started = False
    
    def get_recent_ganglion_data(self):
        data = self.board.get_board_data()
        df = pd.DataFrame(np.transpose(data))
        return df