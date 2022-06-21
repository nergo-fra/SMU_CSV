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
time_per_point = 1e-1  # Minimum value of 2e-5

# FUNCTION

def _read_csv(name):
    df = pd.read_csv(name, names=[str(x) for x in range(nb_channel + 1)], index_col=0, skiprows=1, low_memory=False)
    df.astype('float').dtypes
    return df

def _settings_commands_SMU(inst, parameters, V_list, wait = True):
    inst.write(":sour1:func:mode volt")
    inst.write(":sour1:curr:lev:imm" + V_list.split(',')[0])




def _run_measurements():
    print("done")

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
    V_list = _generate_sweep_from_csv()