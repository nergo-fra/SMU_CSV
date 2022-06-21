# Author : Nergo || Special thanks to Scott T Keene, Cambridge University

# IMPORT

import pyvisa
import matplotlib as mpl
import time
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

I_comp = 0.0007 # current compliance S1
time_per_point = 3.3333e-05  # Minimum value of 2e-5 #use time between measures from csv
time_before_meas = 2 #if SMU is not on, we give it time to initialize

# FUNCTION

def _read_csv(name):
    df = pd.read_csv(name, names=["Volt"], index_col=0, skiprows=1, low_memory=False)
    df.astype('float').dtypes
    return df

def _settings_commands_SMU(inst, parameters, V_list, wait = True):
    print("SMU settings in progress : 0% \n")
    # parameters format (list of strings, units of seconds, amps, volts):
    # [(0) S1 compliance current,(1) time per point,(2) points per sweep,(3) acquisition time,
    #  (4) premeasurement voltage hold time]
    # Source settings before turn on - the second source is set as shown by carefulness, we wouldn't want to inject a current or voltage in the detector
    inst.write(":sour1:func:mode volt")
    inst.write(":sour1:volt:lev:imm" + V_list.split(',')[0])
    inst.write(":sour1:volt:prot " + parameters[0])
    inst.write(":sour2:func:mode curr")
    inst.write(":sour2:func:lev:imm 0")
    inst.write(":sour1:volt:prot 2")

    print("SMU settings in progress : 20% \n Turning outputs on ... \n")
    # Turning outputs on
    inst.write(":outp1 on")
    inst.write(":outp2 on")
    print("Outputs on \n")

    # If wait is needed (if the SMU is not on yet)
    if wait:
        time.sleep(parameters[4])

    print("SMU settings in progress : 30% \n")
    # Sets the measurement list of voltages (channel 1)
    inst.write(":sour1:volt:mode list")
    inst.write(":sour1:list:volt " + V_list)

    print("SMU settings in progress : 40% \n")
    # Sense settings
    inst.write(":sens1:func \"volt\"")
    inst.write(":sens2:func \"volt\"")
    inst.write(":sens2:volt:rang:auto on")

    print("SMU settings in progress : 50% \n")
    # Measurement wait time set to OFF
    inst.write(":sens1:wait off")
    inst.write(":sour1:wait off")
    inst.write(":sens2:wait off")
    # sour2 not touched because we don't really care

    print("SMU settings in progress : 55% \n")
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

    print("SMU settings in progress : 80% \n")
    # Measurement interval is set to the same value
    inst.write(":sens1:curr:aper " + parameters[3])
    inst.write(":sens2:volt:aper " + parameters[3])

    print("SMU settings in progress : 95% \n")
    # Output formatting
    inst.write(":form:elem:sens volt,curr,time")

    print("SMU settings in progress : 100% \n Running measurements ...\n")
    # Running measurements
    inst.write(":init (@1,2)")

    print("Measurements done! \n Fetching data \n")
    data_raw = np.empty((len(V_list.split(",")), 5), float)
    # Fetching data - there is a more elegant way to do that using read
    data_raw[0] = inst.query(":fetc:arr:time? (@1)")
    data_raw[1] = inst.query(":fetc:arr:curr? (@1)")
    data_raw[2] = inst.query(":fetc:arr:volt? (@1)")
    data_raw[3] = inst.query(":fetc:arr:time? (@2)")
    data_raw[4] = inst.query(":fetc:arr:volt? (@2)")

    print("Data export... \n")
    # Transforming data from list to array
    data = np.empty((len(V_list.split(",")), 5), float)
    for i in range(5):
        data[i] = np.asarray([float(i) for i in data_raw[i].split(',')])
    print("Done\n")
    return data

def _generate_sweep_from_pd(df):
    sweep = ""
    for i in range(0, len(df["Volt"])):
        sweep += "{:.6E}".format(df["Volt"][i], 6) + ","
    sweep += "{:.5E}".format(df["Volt"][len(df["Volt"])], 5)
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
    inst.timeout = 500 * 1e5  # to change, depends on longest measurement. Not in the readme but pretty obvious
    df = _read_csv("spinal_normalized1.csv")
    V_list = _generate_sweep_from_pd(df)

    # parameters format (list of strings, units of seconds, amps, volts):
    # [(0) S1 compliance current,(1) time per point,(2) points per sweep,(3) acquisition time,
    #  (4) premeasurement voltage hold time]
    parameters = []
    parameters.append("{:.0E}".format(I_comp))
    parameters.append("{:.0f}".format(len(V_list.split(','))))
    parameters.append("{:.1E}".format(time_per_point / 2))
    parameters.append("{:.1E}".format((time_per_point / 2)))
    parameters.append(time_before_meas)

    # Create empty array to store output data
    transfer = np.empty((len(V_list.split(",")), 8), float)
    transfer = _settings_commands_SMU(inst, parameters, V_list, False)

    # Plotting
    plt.plot(transfer[0], transfer[1], color='aquamarine', label = "Detector output")
    plt.plot(transfer[2], transfer[4], color='salmon', label = "LED input")
    plt.xlabel("$Time$ (s)")
    plt.ylabel("$Voltage$ (V)")
    plt.title("Spinal chord recording - with Blood")
    plt.show()

    # Saving CSV
    filename = "Spinal chord recording - with blood " + str(1) #change filename
    folder = "Data\\"
    np.save(folder + filename, transfer)