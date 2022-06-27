# Author : Nergo || Special thanks to Scott T Keene, Cambridge University

# IMPORT

import pyvisa
import matplotlib as mpl
import time
import glob
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation, rc, cm
import matplotlib.colors as colors
from scipy import ndimage
from scipy import signal
import scipy.signal
import scipy.misc
from scipy.interpolate import griddata
from scipy.optimize import fmin_powell
import scipy.ndimage as snd
from scipy.fft import fft, ifft, fftfreq
from tkinter import filedialog
import tkinter
import pickle
import pandas as pd

# MPL backend

mpl.use("TkAgg")
plt.style.use('dark_background')

# PARAMETERS TO MODIFY

I_comp = 0.7E-3 # current compliance S1
time_per_point = 3E-3  # Minimum value of 2e-5 #use time between measures from csv
time_before_meas = 2 #if SMU is not on, we give it time to initialize

# FUNCTION

def _read_csv(name):
    df = pd.read_csv(name, names=["Volt"], index_col=0, skiprows=1, low_memory=False)
    df.astype('float').dtypes
    #df_2 = df.truncate(after='1970-01-01 00:00:00.001300000')
    return df

def _settings_commands_SMU(inst, parameters, V_list, wait = True):
    print("SMU settings in progress : 0%")
    # parameters format (list of strings, units of seconds, amps, volts):
    # [(0) S1 compliance current,(1) time per point,(2) points per sweep,(3) acquisition time,
    #  (4) premeasurement voltage hold time]
    # Source settings before turn on - the second source is set as shown by carefulness, we wouldn't want to inject a current or voltage in the detector
    inst.write(":sour1:volt:lev:imm " + V_list.split(',')[0])
    inst.write(":sens1:curr:prot " + parameters[0])
    #inst.write(":sour2:func:mode curr")
    #inst.write(":sour2:func:lev:imm 0")

    print("SMU settings in progress : 20% \nTurning outputs on ...")
    # Turning outputs on
    inst.write(":outp1 on")
    inst.write(":outp2 on")
    print("Outputs on")

    # If wait is needed (if the SMU is not on yet)
    if wait:
        time.sleep(parameters[4])

    print("SMU settings in progress : 30%")
    # Sets the measurement list of voltages (channel 1)
    inst.write(":sour1:func:mode volt")
    inst.write(":sour1:volt:mode list")
    inst.write(":sour1:list:volt " + V_list)
    inst.write(":sour2:func:mode amps")
    inst.write(":sour2:curr:lev:imm 0")

    print("SMU settings in progress : 40%")
    # Sense settings
    inst.write(":sens1:func \"volt\"")
    inst.write(":sens2:func \"volt\"")
    inst.write(":sens2:volt:rang:auto on")
    inst.write(":sens1:volt:rang:auto on")
    inst.write(":sens2:curr:prot 2")

    print("SMU settings in progress : 50%")
    # Measurement wait time set to OFF
    inst.write(":sens1:wait off")
    inst.write(":sour1:wait off")
    inst.write(":sens2:wait off")
    # sour2 not touched because we don't really care

    print("SMU settings in progress : 55%")
    # Set trigger source to the same mode
    inst.write(":trig1:sour tim")
    inst.write("trig1:tim " + parameters[1])
    inst.write("trig1:acq:coun " + parameters[2])  # points per sweep
    inst.write(":trig1:acq:del def")
    inst.write("trig1:tran:coun " + parameters[2])
    inst.write(":trig1:tran:del def")
    inst.write(":trig2:sour tim")
    inst.write("trig2:tim " + parameters[1])
    inst.write("trig2:acq:coun " + parameters[2])
    inst.write(":trig2:acq:del def")
    inst.write("trig2:tran:coun " + parameters[2])
    inst.write(":trig2:tran:del def")

    print("SMU settings in progress : 80%")
    # Measurement interval is set to the same value
    inst.write(":sens1:curr:aper:auto on")
    inst.write(":sens2:volt:aper " + parameters[5])

    print("SMU settings in progress : 95%")
    # Output formatting
    inst.write(":form:elem:sens volt,curr,time")

    print("SMU settings in progress : 100% \nRunning measurements ...")
    # Running measurements
    inst.write(":init (@1,2)")

    print("Measurements in progress : Fetching data...")
    # Fetching data - there is a more elegant way to do that using read
    data_raw_0 = inst.query(":fetc:arr:time? (@1)")
    data_raw_1 = inst.query(":fetc:arr:curr? (@1)")
    data_raw_2 = inst.query(":fetc:arr:volt? (@1)")
    data_raw_3 = inst.query(":fetc:arr:time? (@2)")
    data_raw_4 = inst.query(":fetc:arr:volt? (@2)")

    print("Data export...")
    # Transforming data from list to array
    data_led_np_0 = np.asarray([float(i) for i in data_raw_0.split(',')])
    data_led_np_1 = np.asarray([float(i) for i in data_raw_1.split(',')])
    data_led_np_2 = np.asarray([float(i) for i in data_raw_2.split(',')])
    data_detect_np_0 = np.asarray([float(i) for i in data_raw_3.split(',')])
    data_detect_np_1 = np.asarray([float(i) for i in data_raw_4.split(',')])
    print("Done")
    return data_detect_np_0, data_detect_np_1, data_led_np_0, data_led_np_1, data_led_np_2


def _generate_sweep_from_pd(df):
    sweep = ""
    for i in range(0, len(df["Volt"]) - 1):
        sweep += "{:.3E}".format(df["Volt"][i], 3) + ","
    sweep += "{:.3E}".format(df["Volt"][len(df["Volt"]) - 1], 3)
    return sweep

# MAIN

if __name__ == '__main__':
    rm = pyvisa.ResourceManager()
    print(rm.list_resources())
    serial = 'USB0::0x0957::0xCE18::MY51143745::INSTR'
    print("trying 'USB0::0x0957::0xCE18::MY51143745::INSTR'")
    try:
        inst = rm.open_resource(serial)
    except:
        print("Incorrect serial, please modify code")
    assert (inst.query("*IDN?") == "Keysight Technologies,B2902A,MY51143745,3.4.2011.5100\n"), \
        print("Houston, we have a problem")
    print("connection successful")
    inst.timeout = 500 * 1e5  # to change, depends on longest measurement. Not in the readme but pretty obvious
    df = _read_csv("spinal_normalized_1_1.csv")
    print(len(df))
    for i in range(2500, int(len(df)/2), 2500):
        V_list = _generate_sweep_from_pd(df[i - 2500:i])

        # parameters format (list of strings, units of seconds, amps, volts):
        # [(0) S1 compliance current,(1) time per point,(2) points per sweep,(3) acquisition time,
        #  (4) premeasurement voltage hold time, (5) measurement delay]
        parameters = []
        parameters.append("{:.0E}".format(I_comp))
        parameters.append("{:.1E}".format((time_per_point)))
        parameters.append("{:.1f}".format(len(V_list.split(','))))
        parameters.append("{:.1E}".format(time_per_point / 2))
        parameters.append(time_before_meas)
        parameters.append("{:.1E}".format((time_per_point / 2)))

        # Create empty array to store output data
        transfer = np.empty((len(V_list.split(",")), 5), float)
        transfer[0,:] += 7.496999999999999886e+00 * int(i / 2500)
        transfer = _settings_commands_SMU(inst, parameters, V_list, False)

        # # Plotting
        # plt.plot(transfer[0], transfer[1], color='aquamarine', label = "Detector output")
        # plt.plot(transfer[2], transfer[4], color='salmon', label = "LED input")
        # plt.xlabel("$Time$ (s)")
        # plt.ylabel("$Voltage$ (V)")
        # plt.title("Spinal chord recording - wh Blood")
        # plt.show()

        # Saving CSV
        filename = "Spinalchordrecording-withblood" + str(int(i / 2500)) + ".csv" #change filename
        folder = "Data\\"
        np.savetxt(folder + filename, np.transpose(transfer), delimiter=",")
    # Plotting
    files = os.path.join(folder, "Spinalchordrecording-withblood*.csv")
    files = glob.glob(files)
    df_ex = pd.concat(map(pd.read_csv, files), names=[str(i) for i in range(5)], index_col=0, skiprows=1, low_memory=False)
    df_ex.astype('float').dtypes
    df_ex.plot(x = '0',y = '1', color='aquamarine', label = "Detector output")
    plt.plot(x= '2', y = '4', color='salmon', label = "LED input")
    plt.xlabel("$Time$ (s)")
    plt.ylabel("$Voltage$ (V)")
    plt.title("Spinal chord recording - wh Blood")
    plt.show()