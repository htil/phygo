import mne
from pathlib import Path
import pandas as pd
from brainflow.board_shim import BoardShim, BoardIds
import numpy as np


def load_events(file_path):
        events = np.loadtxt(file_path, delimiter=',', dtype=int)
        return events

def csv_to_dataframe(file):
        # print(BoardIds.GANGLION_BOARD.value)
        # eeg_channels_names = BoardShim.get_eeg_names(BoardIds.GANGLION_BOARD)
        # print(eeg_channels_names)
        eeg_channels_names = [str(i) for i in range(15)]
        df = pd.read_csv(file, usecols = eeg_channels_names).transpose()

        return df

def df_to_raw( df, sfreq=200, ch_types='emg'):
    # eeg_channels_names = BoardShim.get_eeg_names(self.board_id)
    print(df.shape)
    eeg_channels_names = [str(i) for i in range(df.shape[0])]
    ch_types = ['eeg'] * len(eeg_channels_names)

    # Create MNE info object
    info = mne.create_info(ch_names = eeg_channels_names, sfreq = sfreq, ch_types=ch_types)

    # Create MNE raw object
    raw = mne.io.RawArray(df, info)

    return raw

def csv_to_raw(file, start_channel=0, end_channel=15):
    df = csv_to_dataframe(file)
    df = df.iloc[start_channel:end_channel, :]
    raw = df_to_raw(df)
    return raw

raw = csv_to_raw("data/study5_data.csv", 1, 2)
# raw.plot(clipping=None, scalings=dict(eeg='1e5', emg='1e5'))

# Load events and check if we have enough
events = np.array(load_events("events/study1.txt"))  
print(f"Loaded {len(events)} events")

if len(events) < 2:
    print("Warning: Not enough events to create epochs. Need at least 2 events.")
else:
    event_dict = {"relax": 0, "squeeze": 1}
    
    # Create epochs with more lenient rejection criteria
    try:
        # Try with default settings first
        epochs = mne.Epochs(raw, events, tmin=-0.1, tmax=0.5, event_id=event_dict, baseline=(0, 0))
        
        # If all epochs are dropped, try with more lenient criteria
        if len(epochs) == 0:
            print("All epochs dropped with default criteria. Trying with more lenient settings...")
            epochs = mne.Epochs(raw, events, tmin=-0.1, tmax=0.5, event_id=event_dict, 
                              baseline=(0, 0), reject=None, flat=None)
        else:
            # Show default rejection criteria
            print("\nDefault rejection criteria used:")
            print("- reject: None (uses MNE defaults)")
            print("- flat: None (uses MNE defaults)")
            print("- Typical defaults: reject={'eeg': 100e-6} (100 µV), flat={'eeg': 1e-6} (1 µV)")
        
        # Check if any epochs survived
        if len(epochs) == 0:
            print("Warning: All epochs were dropped. This might indicate data quality issues.")
            print("Try adjusting rejection criteria or check your data.")
            # Show drop log to understand why epochs were dropped
            epochs.plot_drop_log()
        else:
            print(f"Successfully created {len(epochs)} epochs")
            print(f"Original events: {len(events)}")
            print(f"Epochs dropped: {len(events) - len(epochs)}")
            
            # Show drop log to see why epochs were dropped
            print("\nDrop log (showing why epochs were rejected):")
            epochs.plot_drop_log()
            
            print(epochs['relax'])
            # Only plot if we have epochs
            if len(epochs['relax']) > 0:
                epochs['relax'].plot()
            else:
                print("No 'relax' epochs available for plotting")
    except Exception as e:
        print(f"Error creating epochs: {e}")
        print("This might be due to insufficient data or event timing issues.")


# df = csv_to_dataframe("data/study5_data.csv")
# df = df.iloc[1:2, :]  # Select only row 1 (which was channel 1 after transpose)
# print(df) 
# raw = df_to_raw(df)
# Increase y-axis scaling by making the scaling value larger
raw.plot(clipping=None, scalings=dict(eeg='1e5', emg='1e5')) 