# pi_py_bt_gate_control
Raspberry Pi and Python Driveway Gate Control using Bluetooth Proximity for access control.
Note: This is not meant to be secure, it is not, it is meant to be convenient.  Anyone can circumvent any gate security system with a 50 dollar set of lock cutters or even a big rock, no need for bank level security here (these aren't the droids your looking for).

This is written to run on a Raspberry Pi Zero W

Instead of using a remote control to operate this gate controller, the Bluetooth Mac of your vehicle or phone can be used to trigger the opening of the gate when in range.

This code is in progress and does not support a strain sensor for safety shutoff yet, only an emergency stop button so far.

Use it at your own risk!

How to use this:
You will need to create a file in the same directory as the code.  
  Name the file MACList.txt and put in the MAC addresses of all the devices you want to open the gate (one on each line).  You can use any line as a comment as long as it does not contain a colon.  The devices do not need to be discoverable or even paired to the PI for this code to work.
 
To Set the default Gate mode create a text file in the same folder named GateMode.txt
This file contains three possible things:
open
closed
night

Meaning:
open = open always (effectively not in use)
closed = closed unless valid MAC detected
note: night means closed from 10pm to 8am, but will open for valid MAC

I will be posting the code and instructions on building the hardware on my personal website www.ostafichuk.com when I get a chance...


Run these commands to get bluetooth and gpio working:

sudo apt-get install python3 python3-dev python3-pip python3-rpi.gpio bluetooth libbluetooth-dev

sudo pip3 install RPi.GPIO

sudo pip3 install pybluez

git clone 'this repo clone string'

For auto start of app on boot:
sudo nano /etc/rc.local

put the line:

sudo python3 /home/pi/pi_py_bt_gate_control.py &

before the line with 'exit 0' near the bottom.
