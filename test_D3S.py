import time
import traceback
import numpy as np
import signal
import sys
import json
import csv
import os

sys.path.append("/home/pi/dosenet-raspberrypi-1/kromek_d3s_driver-main")
import capture

interval = int(sys.argv[1])

sys.stdout.flush()

running = True
#interval = 1

def run(interval):
    """
    Main method. Currently also stores and sum the spectra as well.
    Current way to stop is only using a keyboard interrupt.
    """
    cfg = capture.pre_run()
    try:
        while running:
            print("test run: getting data")
            data = capture.read_sensor(cfg)
            print(data)
            time.sleep(interval)
    except KeyboardInterrupt:
        print('\nKeyboardInterrupt: stopping Manager run')
        exit()

if __name__ == '__main__':
    '''
    Execute the main method with argument parsing enabled.
    '''
    print(interval)
    run(interval)
