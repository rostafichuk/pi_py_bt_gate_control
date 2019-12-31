# Driveway Gate Controller written in Python for the Raspberry Pi Zero W
# Written by Ron Ostafichuk (www.ostafichuk.com)
# https://github.com/rostafichuk/pi_py_bt_gate_control.git
# MIT License
# 
#

from picamera import PiCamera
import bluetooth, time
import RPi.GPIO as io # using RPi.GPIO

bCameraExists = 1

# You can hardcode the desired device ID here as a string to skip the discovery stage but you need to disable the load below
vAddr = ["A1:B1:C1:D1:E1:F1"] # list of approved Bluetooth MAC addresses

vMode = ["open","8","21"] # mode [night,open,closed], open 24hr time, closed 24hr time
# Primary Gate Mode
sPrimaryGateMode = vMode[0] # can be "night" or "closed" or "open"
openHour_24 = int(vMode[1]) # open at 8 am for "night" mode
closeHour_24 = int(vMode[2]) # close at 9pm for "night" mode

if sPrimaryGateMode == "night":
    print( "Gate Mode ->" , sPrimaryGateMode , " open=" , openHour_24 , " close=" , closeHour_24 )
else:
    print( "Gate Mode ->" , sPrimaryGateMode )


# time values used to adjust the delays between states of the gate system
nSecondsToWaitBeforeOpen = 5
nSecondsToWaitBeforeClose = 10
nSecondsToRunOpening = 40
nSecondsToRunClosing = 40
# system states = waitBeforeOpen,opening,opened,waitBeforeClose,closing,closed
current_state = "waitBeforeOpen" # onstartup we need to be in a transition state to make sure gate gets moved
desired_state = "opened" # onstartup assume gate should be opened and is in an unknown state, th
nStateChanged_ts = time.time()


# set raspi pin outputs
pin_HBridge_1 = 17
pin_HBridge_2 = 27
pin_led_green = 23
pin_led_red = 24
pin_emergency_stop = 25
pin_motion_detection = 21 # used to take a picture at the gate

def SetRedLightOn():
    io.output(pin_led_red,1)
def SetRedLightOff():
    io.output(pin_led_red,0)

def SetGreenLightOn():
    io.output(pin_led_red,1)
def SetGreenLightOff():
    io.output(pin_led_red,0)

def SetHBridgeDirection(n):
    if n == 0:
        # turn off
        io.output(pin_HBridge_1,1)
        io.output(pin_HBridge_2,1)
    elif n > 0:
        io.output(pin_HBridge_1,0)
        io.output(pin_HBridge_2,1)
    elif n < 0:
        io.output(pin_HBridge_1,1)
        io.output(pin_HBridge_2,0)


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

    #io.setup(pin_emergency_stop,io.IN, pull_up_down=io.PUD_DOWN) # make pin an input (down means emergency stop when no connection, use that as the default for safety!)
    io.setup(pin_emergency_stop,io.IN, pull_up_down=io.PUD_UP)  # for testing (connection means stop, bad!)

    io.setup(pin_motion_detection,io.IN, pull_up_down=io.PUD_UP)
    
    # load the real MAC List from file
    try:
        with open('MACList.txt', 'r') as f:
            vAddr = f.read().splitlines()
    finally:
        print( "Loaded Approved MAC List:")
        print( vAddr )
        print( "=========================")

    # system time
    localtime = time.localtime(time.time())


    print("Bluetooth Proximity Detection\n")
    print("Startup desired state = ", current_state)

    print("Scanning for approved devices %s." % (vAddr))

    #GPIO.setup(led_pin, GPIO.OUT)
    while True:
        # always need the current time!
        time_s = time.time()
        localtime = time.localtime(time_s) # keep localtime current

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
        finally:
            if sPrevGateMode != sPrimaryGateMode:
                if sPrimaryGateMode == "night":
                    print( "Gate Mode ->" , sPrimaryGateMode , " open=" , openHour_24 , " close=" , closeHour_24 )
                else:
                    print( "Gate Mode ->" , sPrimaryGateMode )

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
        else:
            # failed to have a valid gate mode, open it by default
            desired_state = "opened"

        # Try to gather information from the desired Bluetooth device.
        # ===================================================
        # We're using two different metrics (readable name and data services)
        # to reduce false negatives.
        btDeviceName = None
        for addr1 in vAddr:
            if ":" in addr1:
                btDeviceName = bluetooth.lookup_name(addr1, timeout=10)
                if btDeviceName != None:
                    break # found an approved device, ok to exit loop!
            
        if bCameraExists and io.input(pin_motion_detection) == 0 and time_s > lastTimeForPic_s + 5:
            # take a picture and send it via wifi to server
            sPictureFileName = "/tmp/pic"+time_s+".jpg";
            camera.capture(sPictureFileName)
            lastTimeForPic_s = time.time()
            print("Motion event, picture taken")

        if io.input(pin_emergency_stop) == 0:
            print("# emergency shutdown!")
            #Turn off H Bridge and flash lights and do not check Bluetooth or system states
            SetHBridgeDirection(0) # stop H Bridge!
            SetRedLightOff()
            SetGreenLightOff()
            time.sleep(2)
            SetRedLightOn()
            SetGreenLightOn()            
            time.sleep(2) # extra sleep time in emergency stop mode, only check button once every 2 seconds
        else:
            # do normal operations
            # Flip the LED pin on or off depending on whether the device is nearby
            if btDeviceName == None:
                if nStateChanged_ts > time_s-1:
                    print("# no approved device in range! Set Gate to ", desired_state , ". Gate Mode is " , sPrimaryGateMode)
                if desired_state == "opened" and current_state != "opened":
                    if current_state != "waitBeforeOpen" and current_state != "opening" and current_state != "opened":
                        current_state = "waitBeforeOpen";
                        nStateChanged_ts = time.time()
                        SetHBridgeDirection(0) # stop H Bridge!
                        print("No approved device in range... Set Gate to " , desired_state, " in ", nSecondsToWaitBeforeClose , "seconds! ", nStateChanged_ts)
                if desired_state == "closed" and current_state != "closed":
                    if current_state != "waitBeforeClose" and current_state != "closing" and current_state != "closed":
                        current_state = "waitBeforeClose";
                        nStateChanged_ts = time.time()
                        SetHBridgeDirection(0) # stop H Bridge!
                        print("No approved device in range... Set Gate to " , desired_state, " in ", nSecondsToWaitBeforeClose , "seconds! ", nStateChanged_ts)
            else:
                if nStateChanged_ts > time_s-1:
                    print("# detected an approved device")
                if current_state != "waitBeforeOpen" and current_state != "opening" and current_state != "opened":            
                    current_state = "waitBeforeOpen";
                    nStateChanged_ts = time.time()
                    SetHBridgeDirection(0) # stop H Bridge!
                    print(addr1, " ", btDeviceName, " detected! Open the Gate in " , nSecondsToWaitBeforeOpen, "s! ", nStateChanged_ts)
                    

            # handle state CHANGES!
            # ===================================================
            # : waitBeforeOpen,open,opened,waitBeforeClose,close,closed

            if current_state == "waitBeforeOpen":
                if nStateChanged_ts < time_s - nSecondsToWaitBeforeOpen:
                    # 30 seconds has expired, change state, new ts!
                    current_state = "opening"
                    nStateChanged_ts = time_s
            
            if current_state == "opening":
                if nStateChanged_ts < time_s-nSecondsToRunOpening:
                    # 30 seconds has expired, change state, new ts!
                    SetHBridgeDirection(0)
                    current_state = "opened"
                    nStateChanged_ts = time_s
                    
            if current_state == "waitBeforeClose":
                if nStateChanged_ts < time_s-nSecondsToWaitBeforeClose:
                    # 30 seconds has expired, change state, new ts!
                    current_state = "closing"
                    nStateChanged_ts = time_s
            
            if current_state == "closing":
                if nStateChanged_ts < time_s - nSecondsToRunClosing:
                    # 30 seconds has expired, change state, new ts!
                    SetHBridgeDirection(0)
                    current_state = "closed"
                    nStateChanged_ts = time_s
            
            
            # Handle behaviour during a specific state
            # ===================================================
            if current_state == "waitBeforeOpen":
                print(current_state,"#flash green light")
                if (time_s * 2.0) % 2 == 0:
                    SetGreenLightOn()
                else:
                    SetGreenLightOff()


            if current_state == "opening":
                print(current_state, "#Solid green light","#set H bridge circuit to open gate")
                SetGreenLightOn()
                SetHBridgeDirection(-1)
                
            if current_state == "opened":
                if nStateChanged_ts > time_s-1:
                    print(current_state,"#turn off lights and H Bridge")
                    SetHBridgeDirection(0)
                    SetGreenLightOff()
                    SetRedLightOff()

                
            if current_state == "waitBeforeClose":
                print(current_state,"# flash red light")
                if (time_s * 2.0) % 2 == 0:
                    SetRedLightOn()
                else:
                    SetRedLightOff()            

            if current_state == "closing":
                print(current_state,"# Solid red light","# set H bridge circuit to close gate")
                SetRedLightOn()
                SetHBridgeDirection(1)

            if current_state == "closed":
                if nStateChanged_ts > time_s-1:
                    print(current_state,"#turn off lights and H Bridge")
                    SetHBridgeDirection(0)
                    SetRedLightOff()
                    SetGreenLightOff()
        # end of else condition on emergency button!  Damn python needs brackets like a real language!
        

        # Arbitrary wait time to reduce cpu load
        # Pi4 uses 2% CPU typically for this program
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    io.cleanup()
    print( "Exiting Program, cleaned up GPIO" )
    if bCameraExists:
        camera.close()
        print( "Closed Camera")
