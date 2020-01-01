# Driveway Gate Controller written in Python for the Raspberry Pi Zero W
# Written by Ron Ostafichuk (www.ostafichuk.com)
# https://github.com/rostafichuk/pi_py_bt_gate_control.git
# MIT License
# 
#

from picamera import PiCamera
import bluetooth, time, datetime
import RPi.GPIO as io # using RPi.GPIO
from gpiozero import CPUTemperature

bCameraExists = 1

cpu = CPUTemperature()

# You can hardcode the desired device ID here as a string to skip the discovery stage but you need to disable the load below
vAddr = ["A1:B1:C1:D1:E1:F1"] # list of approved Bluetooth MAC addresses

vMode = ["bootup","8","21"] # mode [night,open,closed,testio], open 24hr time, closed 24hr time
# Primary Gate Mode
sPrimaryGateMode = vMode[0] # can be "night" or "closed" or "open"
openHour_24 = int(vMode[1]) # open at 8 am = 8 for "night" mode
closeHour_24 = int(vMode[2]) # close at 9pm = 21 for "night" mode


# time values used to adjust the delays between states of the gate system
nSecondsToWaitBeforeOpen = 5
nSecondsToWaitBeforeClose = 20
nSecondsToRunOpening = 50
nSecondsToRunClosing = 50

# system states = waitBeforeOpen,opening,opened,waitBeforeClose,closing,closed
current_state = "unknown" # onstartup we need to be in a transition state to make sure gate gets moved
desired_state = "closed" # onstartup we want to close the gate
nStateChanged_ts = time.time()


# set raspi pin outputs
pin_HBridge_1 = 17
pin_HBridge_2 = 25 # was pin 27, may be burned out...
pin_led_green = 23
pin_led_red = 5 # was pin 24, may be burned out...

def SetRedLightOn():
    io.output(pin_led_red,0)
def SetRedLightOff():
    io.output(pin_led_red,1)

def SetGreenLightOn():
    io.output(pin_led_green,0)
def SetGreenLightOff():
    io.output(pin_led_green,1)

def SetHBridgeDirection(n):
    if n == 0:
        # turn off
        io.output(pin_HBridge_1,1)
        io.output(pin_HBridge_2,1)
        print("Stop Gate Motion")
    elif n > 0:
        io.output(pin_HBridge_1,0)
        io.output(pin_HBridge_2,1)
    elif n < 0:
        io.output(pin_HBridge_1,1)
        io.output(pin_HBridge_2,0)

def turnOffLightsAndHBridge():
    SetRedLightOff()
    SetGreenLightOff()
    SetHBridgeDirection(0)

def flashBothLights(n):
    print( "Flash both lights", n , "times" )
    for i in range(0,n):
        SetRedLightOn() 
        SetGreenLightOn()
        time.sleep(0.5)
        SetRedLightOff() 
        SetGreenLightOff()
        time.sleep(0.5)


# enclose program in a try catch to make sure the GPIO cleanup is run
camera = 0
try:
    if bCameraExists:
        try:
            print( "Initializing the Camera")
            camera = PiCamera()
        except:
            bCameraExists = 0
            print( "No camera found" )
        if bCameraExists:
            camera.resolution = (1024,768)
            camera.start_preview() # this must be running to take a picture?
            time.sleep(2) # 2 secs to warm up camera
            print( "Camera Ready")
        
    
    print( "Setting up the GPIO pins")
    io.setmode(io.BCM)

    # set pin modes
    io.setup(pin_led_green,io.OUT)
    io.setup(pin_led_red,io.OUT)

    io.setup(pin_HBridge_1,io.OUT)
    io.setup(pin_HBridge_2,io.OUT)

    # io.setup(pin_motion_detection,io.IN, pull_up_down=io.PUD_UP)

    print("Bluetooth Proximity Detection")
    print("=============================\n")
    turnOffLightsAndHBridge() # stop H Bridge in case gate was in motion!

    # for boot up, flash lights 5 times
    flashBothLights(5)
    
    # leave them on until we figure out a state
    SetRedLightOn() 
    SetGreenLightOn()


    # load the real MAC List from file
    try:
        with open('MACList.txt', 'r') as f:
            vAddr = f.read().splitlines()
    except:
        print( "ERROR: missing MACList.txt! default to no approved devices" )
        vAddr = ["A1:B1:C1:D1:E1:F1"] # need a list to prevent a crash
    finally:
        print( "Loaded Approved MAC List:")
        print( vAddr )
        print( "=========================")

    # system time
    localtime = time.localtime(time.time())

    print("Begin Scanning for approved devices...")

    #GPIO.setup(led_pin, GPIO.OUT)
    nLoop = 0
    btDeviceName = None
    while True:
        # always need the current time!
        nLoop += 1
        time_s = time.time()
        localtime = time.localtime(time_s) # keep localtime current
        sDateTime = datetime.datetime.now()

        # Once every 15 seconds load the primary gate mode and parameters from text file
        sPrevGateMode = sPrimaryGateMode
        try:
            with open('GateMode.txt', 'r') as f:
                vMode = f.read().splitlines()
                
            if len(vMode) > 0 and len(vMode[0]) > 2:
                sPrimaryGateMode = vMode[0].lower()
            if len(vMode) > 1 and len(vMode[1]) > 0:
                openHour_24 = int(vMode[1])
            if len(vMode) > 2 and len(vMode[2]) > 0:
                closeHour_24 = int(vMode[2])
        except:
            # prevent crash, use default mode of open
            print( "ERROR: missing GateMode.txt! default to Open Gate" )
            sPrimaryGateMode = "open"
        finally:
            if sPrevGateMode != sPrimaryGateMode:
                if sPrimaryGateMode == "night":
                    print(sDateTime , "Gate Mode Changed ->" , sPrimaryGateMode , " open=" , openHour_24 , " close=" , closeHour_24 )
                else:
                    print(sDateTime , "Gate Mode Changed ->" , sPrimaryGateMode )

        # set the desired_state based on the Primary Gate Mode
        if sPrimaryGateMode == "night":
            if localtime.tm_hour >= openHour_24:
                desired_state = "opened"
            else:
                desired_state = "closed"
        elif sPrimaryGateMode == "closed":
            desired_state = "closed"
        elif sPrimaryGateMode == "open":
            desired_state = "opened"
        elif sPrimaryGateMode == "testio":
            desired_state = "testio"
        else:
            # failed to have a valid gate mode, open it by default
            desired_state = "opened"

        # Try to gather information from the desired Bluetooth device.
        # ===================================================
        # We're using two different metrics (readable name and data services)
        # to reduce false negatives.
        if nLoop % 4 == 0:
            # only check the blue tooth once every 4 loops or 2 seconds
            btDeviceName = None
            for addr1 in vAddr:
                if ":" in addr1:
                    btDeviceName = bluetooth.lookup_name(addr1, timeout=10)
                    if btDeviceName != None:
                        break # found an approved device, ok to exit loop!
            
            # do normal operations
            # Flip the LED pin on or off depending on whether the device is nearby
            if btDeviceName == None:
                if nStateChanged_ts > time_s-1:
                    print(sDateTime , "No approved device in range!")
                    
                if desired_state == "opened" and current_state != "opened" and current_state != "opening":
                    if current_state != "waitBeforeOpen" and current_state != "opening" and current_state != "opened" and current_state != "waitBeforeOpen":
                        SetHBridgeDirection(0) # stop H Bridge in case gate was in motion!
                        flashBothLights(3)
                        current_state = "waitBeforeOpen";
                        nStateChanged_ts = time.time()
                        SetHBridgeDirection(0) # stop H Bridge!
                        print(sDateTime , "No approved device in range... Set Gate to " , desired_state, " in ", nSecondsToWaitBeforeClose , "seconds! ", nStateChanged_ts)
                if desired_state == "closed" and current_state != "closed" and current_state != "closing":
                    if current_state != "waitBeforeClose" and current_state != "closing" and current_state != "closed" and current_state != "waitBeforeClose":
                        SetHBridgeDirection(0) # stop H Bridge in case gate was in motion!
                        flashBothLights(3)
                        current_state = "waitBeforeClose";
                        nStateChanged_ts = time.time()
                        SetHBridgeDirection(0) # stop H Bridge!
                        print(sDateTime , "No approved device in range... Set Gate to " , desired_state, " in ", nSecondsToWaitBeforeClose , "seconds! ", nStateChanged_ts)
            else:
                if nStateChanged_ts > time_s-1:
                    print(sDateTime , "# detected an approved device" , addr1 )
                if current_state != "waitBeforeOpen" and current_state != "opening" and current_state != "opened":
                    SetHBridgeDirection(0) # stop H Bridge in case gate was in motion!
                    flashBothLights(3)
                    current_state = "waitBeforeOpen";
                    nStateChanged_ts = time.time()
                    SetHBridgeDirection(0) # stop H Bridge!
                    print(sDateTime , addr1, " ", btDeviceName, " detected! Open the Gate in " , nSecondsToWaitBeforeOpen, "s! ", nStateChanged_ts)
                
#        if bCameraExists and io.input(pin_motion_detection) == 0 and time_s > lastTimeForPic_s + 5:
            # take a picture and send it via wifi to server
#            sPictureFileName = "/tmp/pic"+time_s+".jpg";
#            camera.capture(sPictureFileName)
#            lastTimeForPic_s = time.time()
#            print(sDateTime , "Motion event, picture taken")

        if desired_state == "testio":
            # flash all IO pins
            nIO = nLoop % 2
            print( "Test Mode pin values " , nIO)
            io.output(pin_led_red,nIO)
            io.output(pin_led_green,nIO)
            io.output(pin_HBridge_1,nIO)
            io.output(pin_HBridge_2,nIO)
        else:
            # normal gate operation
            # handle state CHANGES!
            # ===================================================
            # : waitBeforeOpen,open,opened,waitBeforeClose,close,closed

            if current_state == "waitBeforeOpen":
                if nStateChanged_ts < time_s - nSecondsToWaitBeforeOpen:
                    # 30 seconds has expired, change state, new ts!
                    flashBothLights(3)
                    current_state = "opening"
                    nStateChanged_ts = time_s
            
            if current_state == "opening":
                if nStateChanged_ts < time_s-nSecondsToRunOpening:
                    # 30 seconds has expired, change state, new ts!
                    SetHBridgeDirection(0)
                    flashBothLights(2)
                    current_state = "opened"
                    nStateChanged_ts = time_s
                    
            if current_state == "waitBeforeClose":
                if nStateChanged_ts < time_s-nSecondsToWaitBeforeClose:
                    # 30 seconds has expired, change state, new ts!
                    flashBothLights(3)
                    current_state = "closing"
                    nStateChanged_ts = time_s
            
            if current_state == "closing":
                if nStateChanged_ts < time_s - nSecondsToRunClosing:
                    # 30 seconds has expired, change state, new ts!
                    SetHBridgeDirection(0)
                    flashBothLights(2)
                    current_state = "closed"
                    nStateChanged_ts = time_s
            
            
            # Handle behaviour during a specific state
            # ===================================================
            if current_state == "waitBeforeOpen":
                print(current_state,"[green]")
                SetRedLightOff()
                SetGreenLightOn()

            if current_state == "opening":
                print(current_state, "[green] set H bridge circuit to open gate")
                SetGreenLightOn()
                SetRedLightOff()
                SetHBridgeDirection(-1)
                
            if current_state == "opened":
                if nStateChanged_ts > time_s-1:
                    turnOffLightsAndHBridge()
                
            if current_state == "waitBeforeClose":
                print(current_state,"[red]")
                SetGreenLightOff()
                SetRedLightOn()

            if current_state == "closing":
                print(current_state,"[red] set H bridge circuit to close gate")
                SetRedLightOn()
                SetGreenLightOff()
                SetHBridgeDirection(1)

            if current_state == "closed":
                if nStateChanged_ts > time_s-1:
                    turnOffLightsAndHBridge()        

        # Arbitrary wait time to reduce cpu load
        # Pi4 uses 2% CPU typically for this program
        # if the CPU is super cold, then DO NOT SLEEP, try to use CPU cycles to heat the pi!
        if cpu.temperature > 20.0:
            time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    turnOffLightsAndHBridge() # make sure all is off if program crashes!
    io.cleanup()
    print("Exiting Program, cleaned up GPIO" )
    if bCameraExists:
        camera.close()
        print( "Closed Camera")
