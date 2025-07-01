
from htil_eeg import HTIL_EEG 
from brainflow.board_shim import BoardIds
import time
import seaborn as sns
import matplotlib.pyplot as plt


def plot_data(df, channel):
    plt.figure(figsize=(10,6))
    sns.lineplot(data=df.iloc[:,channel])
    plt.title(f'Channel {channel}')
    plt.xlabel('Sample Number') 
    plt.ylabel('Value')
    plt.show()

def main():
    h_eeg = HTIL_EEG(BoardIds.GANGLION_BOARD.value, serial_number="COM19")
    print("Starting stream")
    time.sleep(60)
    df  = h_eeg.get_recent_ganglion_data()
    plot_data(df, 1)
    h_eeg.stop_stream()
    # Save DataFrame to CSV
    df.to_csv('../data/squeeze_data3.csv', index=False)


if __name__ == "__main__":
    main()