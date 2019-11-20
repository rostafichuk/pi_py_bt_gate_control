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

search_time = 10

# set raspi pin outputs
pin_HBridge_1 = 17
pin_HBridge_2 = 27
pin_led_green = 23
pin_led_red = 24
pin_emergency_stop = 25
pin_motion_detection = 5 # used to take a picture at the gate

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

    io.setup(pin_emergency_stop,io.IN, pull_up_down=io.PUD_DOWN) # make pin an input (down means emergency stop when no connection, use that as the default for safety!)
    #io.setup(pin_emergency_stop,io.IN, pull_up_down=io.PUD_UP)  # for testing

    io.setup(pin_motion_detection,io.IN, pull_up_down=io.PUD_UP)
    
    # load the real MAC List from file
    try:
        with open('MACList.txt', 'r') as f:
            vAddr = f.read().splitlines()
    finally:
        print( "Loaded Approved MAC List")
        print( vAddr )

    # system time
    localtime = time.localtime(time.time())

    # Primary Gate Mode
    sPrimaryGateMode = "Closed at Night" # can be "Closed at Night" or "Always Closed" or "Always Open"
    openHour_24 = 8 # open at 8 am
    closeHour_24 = 21 # close at 9pm


    # time values used to adjust the delays between states of the gate system
    nSecondsToWaitBeforeOpen = 5
    nSecondsToWaitBeforeClose = 10
    nSecondsToRunOpening = 40
    nSecondsToRunClosing = 40
    # system states = WaitBeforeOpen,Opening,Opened,WaitBeforeClose,Closing,Closed

    nStateChanged_ts = time.time()
    current_state = "WaitBeforeOpen" # onstartup we need to be in a transition state to make sure gate gets moved
    desired_state = "Opened" # onstartup assume gate should be opened and is in an unknown state, th


    print("Bluetooth Proximity Detection\n")
    print("Startup desired state = ", current_state)

    print("Scanning for approved devices %s." % (vAddr))

    #GPIO.setup(led_pin, GPIO.OUT)
    while True:
        # always need the current time!
        time_s = time.time()
        localtime = time.localtime(time_s) # keep localtime current

        # set the desired_state based on the Primary Gate Mode
        if sPrimaryGateMode == "Closed at Night":
            if localtime.tm_hour >= openHour_24:
                desired_state = "Opened"
            else:
                desired_state = "Closed"
        if sPrimaryGateMode == "Always Closed":
            desired_state = "Closed"
        if sPrimaryGateMode == "Always Open":
            desired_state = "Opened"

        # Try to gather information from the desired Bluetooth device.
        # ===================================================
        # We're using two different metrics (readable name and data services)
        # to reduce false negatives.
        btDeviceName = None
        for addr1 in vAddr:
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
            #Turn off H Bridge and lights and do not check Bluetooth or system states
            SetHBridgeDirection(0) # stop H Bridge!
            SetRedLightOff()
            SetGreenLightOff()        
            time.sleep(4) # extra sleep time in emergency stop mode, only check button once every 5 seconds
        else:
            # do normal operations
            # Flip the LED pin on or off depending on whether the device is nearby
            if btDeviceName == None:
                if nStateChanged_ts > time_s-1:
                    print("# no approved device in range! Set Gate to ", desired_state , ". Primary Gate Mode is " , sPrimaryGateMode)
                if desired_state == "Opened" and current_state != "Opened":
                    if current_state != "WaitBeforeOpen" and current_state != "Opening" and current_state != "Opened":
                        current_state = "WaitBeforeOpen";
                        nStateChanged_ts = time.time()
                        SetHBridgeDirection(0) # stop H Bridge!
                        print("No approved device in range... Set Gate to " , desired_state, " in ", nSecondsToWaitBeforeClose , "seconds! ", nStateChanged_ts)
                if desired_state == "Closed" and current_state != "Closed":
                    if current_state != "WaitBeforeClose" and current_state != "Closing" and current_state != "Closed":
                        current_state = "WaitBeforeClose";
                        nStateChanged_ts = time.time()
                        SetHBridgeDirection(0) # stop H Bridge!
                        print("No approved device in range... Set Gate to " , desired_state, " in ", nSecondsToWaitBeforeClose , "seconds! ", nStateChanged_ts)
            else:
                if nStateChanged_ts > time_s-1:
                    print("# detected an approved device")
                if current_state != "WaitBeforeOpen" and current_state != "Opening" and current_state != "Opened":            
                    current_state = "WaitBeforeOpen";
                    nStateChanged_ts = time.time()
                    SetHBridgeDirection(0) # stop H Bridge!
                    print(addr, " ", btDeviceName, " detected! Open the Gate in " , nSecondsToWaitBeforeOpen, "s! ", nStateChanged_ts)
                    

            # handle state CHANGES!
            # ===================================================
            # : WaitBeforeOpen,Open,Opened,WaitBeforeClose,Close,Closed

            if current_state == "WaitBeforeOpen":
                if nStateChanged_ts < time_s - nSecondsToWaitBeforeOpen:
                    # 30 seconds has expired, change state, new ts!
                    current_state = "Opening"
                    nStateChanged_ts = time_s
            
            if current_state == "Opening":
                if nStateChanged_ts < time_s-nSecondsToRunOpening:
                    # 30 seconds has expired, change state, new ts!
                    SetHBridgeDirection(0)
                    current_state = "Opened"
                    nStateChanged_ts = time_s
                    
            if current_state == "WaitBeforeClose":
                if nStateChanged_ts < time_s-nSecondsToWaitBeforeClose:
                    # 30 seconds has expired, change state, new ts!
                    current_state = "Closing"
                    nStateChanged_ts = time_s
            
            if current_state == "Closing":
                if nStateChanged_ts < time_s - nSecondsToRunClosing:
                    # 30 seconds has expired, change state, new ts!
                    SetHBridgeDirection(0)
                    current_state = "Closed"
                    nStateChanged_ts = time_s
            
            
            # Handle behaviour during a specific state
            # ===================================================
            if current_state == "WaitBeforeOpen":
                print(current_state,"#flash green light")
                if (time_s * 2.0) % 2 == 0:
                    SetGreenLightOn()
                else:
                    SetGreenLightOff()


            if current_state == "Opening":
                print(current_state, "#Solid green light","#set H bridge circuit to open gate")
                SetGreenLightOn()
                SetHBridgeDirection(-1)
                
            if current_state == "Opened":
                if nStateChanged_ts > time_s-1:
                    print(current_state,"#turn off lights and H Bridge")
                    SetHBridgeDirection(0)
                    SetGreenLightOff()
                    SetRedLightOff()

                
            if current_state == "WaitBeforeClose":
                print(current_state,"# flash red light")
                if (time_s * 2.0) % 2 == 0:
                    SetRedLightOn()
                else:
                    SetRedLightOff()            

            if current_state == "Closing":
                print(current_state,"# Solid red light","# set H bridge circuit to close gate")
                SetRedLightOn()
                SetHBridgeDirection(1)

            if current_state == "Closed":
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
