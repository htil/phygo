import argparse
from brainflow import BoardIds
from brainflow.board_shim import BoardShim, BrainFlowInputParams
from brainflow.data_filter import DataFilter, FilterTypes, AggOperations
import time
import pandas as pd
import numpy as np
import mne
from mne.preprocessing import annotate_muscle_zscore
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path 
from mne.preprocessing import (create_eog_epochs, create_ecg_epochs, corrmap)

class HTIL_EEG:
    def __init__(self, board, real_time=True, z_score_threshold=3, serial_number=""):
        self.board = None
        self.Z_SCORE_THRESHOLD = z_score_threshold
        self.board_id = board
        self.session_started = False
        self.samplingRate = BoardShim.get_sampling_rate(self.board_id)

        if real_time:    
            self.create_board(board, serial_number)

    def create_board(self, board, serial_number=""):
        params = BrainFlowInputParams()
        # if serial_number != "":
        params.serial_port = serial_number
        self.board = BoardShim(board, params)
        self.board.prepare_session()
        # time.sleep(1)
        # self.board.start_stream()


    def get_recent_ganglion_data(self):
        data = self.board.get_board_data()
        df = pd.DataFrame(np.transpose(data))
        return df
    
    def start_stream(self):
        self.board.start_stream()
        self.session_started = True
    
    def stop_stream(self):
        self.board.stop_stream()
        self.session_started = False
    
    def epochs_to_dataframe(self, epochs, label, bads=[], freq_min=1.0, freq_max=30):
        epochs_power = epochs.compute_psd(fmin=freq_min, fmax=freq_max)
        power_data = epochs_power.get_data()
        print("shape", power_data.shape)
        power_data = self.scaleEEGPower(power_data)
        ch_names = BoardShim.get_eeg_names(self.board_id)
        
        # Remove bad channels
        for bad_ch in bads:
            ch_names.remove(bad_ch)

        # Find an operation that speeds the follown N^3 operation UP 
        df_formatted = pd.DataFrame( {'Channel': [], 'Frequency': [], 'Value': [], 'Label': []})
        for epoch_id, epoch in enumerate(power_data):
                for channel_id, channel_val in enumerate(epoch):
                    for freq_index, power in enumerate(channel_val):
                        #print(f'Epoch {epoch_id} channel: {channel_id} freq_index: {freq_index} power: {power}')
                        new_row = {'Channel': ch_names[channel_id], 'Frequency': freq_index, 'Value': power, 'Label': label}
                        df_formatted.loc[len(df_formatted)] = new_row  # len(df) gives the next index number

        return df_formatted


    def get_epochs(self, data, event_label, event_id, start=1, stop=5, duration=1.0, show_log=False, drop_bad=True, plot_epochs=False):
        # Only works for continuous file with only one event type
        events = mne.make_fixed_length_events(data, id=event_id, start=start, stop=stop, duration=duration)
        events_id = {event_label: event_id}
        epochs = mne.Epochs(data, events, tmin=0, tmax=1, event_id=events_id, baseline=(0, 0))
        if drop_bad:
            epochs.drop_bad()
        
        if show_log:
            epochs.plot_drop_log()

        # Drop noisy epochs
        #reject_criteria = dict(eeg=100e-6)  # 100 µV for EEG channels
        #epochs.drop_bad(reject=reject_criteria)

        if plot_epochs:
            print("pre ICA")
            epochs.plot(scalings=dict(eeg='1e-4', emg='1e-4'))
            k=input("Press enter to continue.") 

        self.run_ica(data, epochs)

        if plot_epochs:
            print("post ICA")
            epochs.plot(scalings=dict(eeg='1e-4', emg='1e-4'))
            k=input("Press enter to continue.") 

        epochs.save(Path('data/epochs') / f'{event_label}_epo.fif', overwrite=True)
        return epochs

    def df_to_process_raw(self, df, show_plot=True, show_muscle_artifacts=True):
        df = df.transpose()
        raw = self.df_to_raw(df)
        processed = self.preprocess_data(raw, show_muscle_artifacts=show_muscle_artifacts, show_plot=show_plot)
        return processed, raw

    def csv_to_epoch_dataframe(self, file, event_label, event_id, start=1, stop=5, duration=1.0, freq_max=30, show_muscle_artifacts=False, show_plot=False, show_log=False, drop_bad=True, plot_epochs=False):
        df = self.csv_to_dataframe(file)
        raw = self.df_to_raw(df)
        processed = self.preprocess_data(raw, show_muscle_artifacts=show_muscle_artifacts, show_plot=show_plot)
        epochs = self.get_epochs(processed, event_label, event_id, start=start, stop=stop, duration=duration, show_log=show_log, drop_bad=drop_bad, plot_epochs=plot_epochs)
        df = self.epochs_to_dataframe(epochs, event_label, freq_max=freq_max)
        return df

    def markMuscleArtifacts(self, raw, threshold, plotLog=True):
        threshold_muscle = threshold  # z-score
        annot_muscle, scores_muscle = annotate_muscle_zscore(
        raw, ch_type="eeg", threshold=threshold_muscle, min_length_good=0.2, filter_freq=[0, 60])
        raw.set_annotations(annot_muscle)

        if plotLog:
            fig, ax = plt.subplots()
            ax.plot(raw.times, scores_muscle)
            ax.axhline(y=threshold_muscle, color='r')
            ax.set(xlabel='time, (s)', ylabel='zscore', title='Muscle activity')
            plt.show()
            #k=input("Press enter to continue.") 
            #fig.savefig('muscle_annot.png')

    # Get ICs 
    def run_ica(self, raw, epochs):
        #print("Running ICA")
        orig_epochs = epochs.copy()
        n_components = 0.9999  # Should normally be higher, like 0.999!!
        method = 'picard'
        fit_params = dict(fastica_it=5)
        random_state = 42

        ica = mne.preprocessing.ICA(n_components=n_components, method=method, fit_params=fit_params, random_state=random_state)

        ica.fit(epochs)
        #eog_epochs = create_eog_epochs(raw, "F6")
        #eog_inds, eog_scores = ica.find_bads_eog(eog_epochs, "F6",  threshold=1.25)
        #ica.exclude = eog_inds
        #print(eog_inds)

        # Clean epochs
        ica.apply(epochs.load_data())
        orig_epochs.plot(scalings=dict(eeg='1e-4', emg='1e-4'))
        epochs.plot( scalings=dict(eeg='1e-4', emg='1e-4'))
    
    def df_to_raw(self, df, sfreq=256, ch_types='eeg'):
        eeg_channels_names = BoardShim.get_eeg_names(self.board_id)
        ch_types = ['eeg'] * len(eeg_channels_names)

        # Create MNE info object
        info = mne.create_info(ch_names = eeg_channels_names, sfreq = sfreq, ch_types=ch_types)

        # Create MNE raw object
        raw = mne.io.RawArray(df, info)

        return raw
    
    # def df_to_raw_ganglion(self, df, sfreq=256, ch_types='eeg'):
    #     eeg_channels_names = df.columns.tolist()
    #     eeg_channels_names = [str(name) for name in eeg_channels_names]
    #     print("eeg_channels_names", eeg_channels_names)
    #     ch_types = ['emg'] * len(eeg_channels_names) 

    #     # Create MNE info object
    #     info = mne.create_info(ch_names = eeg_channels_names, sfreq = sfreq, ch_types=ch_types)
    #     print(df)
    #     print(info)

        # # Create MNE raw object
        # raw = mne.io.RawArray(df, info)

        # return raw

    def preprocess_data(self, raw, l_freq=1, h_freq=30, show_muscle_artifacts=False, show_plot=False):
        
        '''
        eeg_channels_names = BoardShim.get_eeg_names(self.board_id)
        ch_types = ['eeg'] * len(eeg_channels_names)

        # Create MNE info object
        info = mne.create_info(ch_names = eeg_channels_names, sfreq = sfreq, ch_types=ch_types)

        # Create MNE raw object
        raw = mne.io.RawArray(data, info)
        '''

        raw.load_data()

        # Detect muscle artifacts
        self.markMuscleArtifacts(raw, self.Z_SCORE_THRESHOLD, plotLog=show_muscle_artifacts)

        
        raw_copy = raw.copy()
    
        # Band pass filter
        #raw_copy.load_data()
        raw_highpass = raw_copy.filter(l_freq=l_freq, h_freq=h_freq)
        # Convert from uV to V for MNE
        raw_highpass.apply_function(lambda x: x * 1e-6)

        # Format data date for annotations later
        raw_highpass.set_meas_date(0)
        raw_highpass.set_montage("standard_1020")

        # Re-reference the data to average
        eeg_reref_highpass, _ = mne.set_eeg_reference(raw_highpass)

        if show_plot:
            eeg_reref_highpass.plot(clipping=None, scalings=dict(eeg='1e-4', emg='1e-4'))
            k=input("Press enter to continue") 

        return eeg_reref_highpass

    def csv_to_dataframe(self, file):
        eeg_channels_names = BoardShim.get_eeg_names(self.board_id)
        df = pd.read_csv(file, usecols = eeg_channels_names).transpose()
        return df
    
    def scaleEEGPower(self, powerArray):
        powerArray = powerArray * 1e6**2 
        powerArray = (10 * np.log10(powerArray))
        return powerArray


    def get_recent_crown_data(self):
        data = self.board.get_board_data()
        eeg_channels_names = BoardShim.get_eeg_names(self.board_id)
        df = pd.DataFrame(np.transpose(data))
        selected = df.loc[:, 1:8]
        selected.columns = eeg_channels_names
        processed, raw = self.df_to_process_raw(selected)
        return df, processed, raw
    
    def get_crown_data(self, data_len=10):
        if self.session_started == False:
            self.start_stream()
            self.session_started = True
            
        # Get latest data to clear buffer
        self.board.get_board_data()

        time.sleep(data_len)
        df, processed, raw = self.get_recent_crown_data()
        return  df, processed, raw
    
    def raw_events_to_epochs(self, raw_file_path, events_path, event_dict, event_color, tmin=-0.5, tmax=1.0, baseline=(0, 0), l_freq=1, h_freq=30, show_muscle_artifacts=False, show_plot=False):
        #print("_________________________!!!!!!!______________")
        #print(tmin, tmax, l_freq, h_freq, baseline)
        raw = self.load_raw(raw_file_path)
        processed = self.preprocess_data(raw, show_muscle_artifacts=show_muscle_artifacts, show_plot=False, l_freq=l_freq, h_freq=h_freq)
        events = self.load_events(events_path)
        np_events = np.array(events)

        epochs = mne.Epochs(processed, np_events, tmin=tmin, tmax=tmax, event_id=event_dict, baseline=baseline)
        # Drop bad muscle artifacts
        epochs.drop_bad()
        epochs.plot_drop_log()

        # Reject noisy epochs
        #reject_criteria = dict(eeg=300e-6)  # 100 µV for EEG channels
        #epo#chs.drop_bad(reject=reject_criteria)
        #epochs.plot_drop_log()

        self.run_ica(raw, epochs)
        return epochs
        #epochs.plot(event_id=True, events=True, event_color=event_color, scalings=dict(eeg='1e-4', emg='1e-4'))


    def save_data(self, df, file_name):
        df.to_csv(file_name, index=False)

    def load_epochs(self, file_path):
        epochs = mne.read_epochs(Path(file_path))
        return epochs

    def load_raw(self, file_path):
        raw = mne.io.read_raw(Path(file_path))
        return raw
    
    def load_events(self, file_path):
        events = np.loadtxt(file_path, delimiter=',', dtype=int)
        return events
    
    def get_board(self):
        return self.board
