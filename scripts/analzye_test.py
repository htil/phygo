from physioanalyze import Study
from physiovisualize import plotBasic, plotMulti
from physioDSP import butter_lowpass, rectify, extractWindows, getMovingAverage, getRMSEnvelope
import numpy as np
import time

sFreq = 200
num_channels = 15

study = Study(num_channels, "emg", sFreq)
# Read raw csv file
study.readFile("../data/squeeze_data2.csv", 0, num_channels)

# Get 5 second epoch
data, times = study.getEpoch(0, 60)
rectified_signal = rectify(data[1])
movingAvg = getMovingAverage(rectified_signal, times, int(sFreq*0.5))
rmsEnvelope = getRMSEnvelope(rectified_signal, times, int(sFreq*0.5))
filteredData = butter_lowpass(rectified_signal, 5, sFreq, order=4)


plotMulti([rectified_signal, movingAvg, rmsEnvelope, filteredData], ['Rectified Signal', 'Moving Average', 'RMS Envelope', 'Filtered Data'], times, [8.3, 6])


print(data)