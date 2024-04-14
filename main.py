import RPi.GPIO as GPIO
from time import sleep
import pins
import settings
import pygame
import board
import adafruit_tca9548a
import threading
import os
import serial

map = {
    "LX": ["A",0],
    "LY": ["A",1],
    "RX": ["A",2],
    "RY": ["A",3],
    "RTRIG": ["A",4],
    "LTRIG": ["A",5],

    "A": ["B",0],
    "B": ["B",1],
    "X": ["B",3],
    "Y": ["B",4],

    "LBUMP": ["B",6],
    "RBUMP": ["B",7],

    "LMENU": ["B",10],
    "RMENU": ["B",11],
    "XLOGO": ["B",12],

    "HAT": ["H",0]  

}

def initializeGPIO():
    global pwm,controller, sensors, mode, lockall, ser
    mode = 'off'
    pygame.init()
    pygame.joystick.init()
    print(pygame.joystick.get_count==0)
    while pygame.joystick.get_count() <= 0:
        sleep(0.5)
    controller = pygame.joystick.Joystick(0)
    controller.init()
    print("Controller connected:",controller.get_name())
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pins.bl, GPIO.OUT)
    GPIO.setup(pins.br, GPIO.OUT)
    GPIO.setup(pins.fl, GPIO.OUT)
    GPIO.setup(pins.fr, GPIO.OUT)
    GPIO.setup(pins.led1, GPIO.OUT)
    GPIO.setup(pins.led2, GPIO.OUT)
    GPIO.setup(pins.clawpwm, GPIO.OUT)
    pwm=GPIO.PWM(pins.clawpwm, 50)
    pwm.start(0)
    i2c = board.I2C()  # uses board.SCL and board.SDA
    tca = adafruit_tca9548a.TCA9548A(i2c)
    sensors=[]
    for channel in range(4):
        sensors.append(tca[channel])
    ledThread = threading.Thread(target=leds)
    ledThread.start()
    stopThread = threading.Thread(target=stop)
    stopThread.start()
    modeSelector()

def stop():
    while True:
        #print(getController('LTRIG'))
        if getController('LTRIG') > 0:
            print('help')
            move('stop')
            os._exit(0)
        sleep(0.03)

def moveClaw(position):
        #print(position)
        turnTo = settings.clawOpen
        if position == 'closed': turnTo = settings.clawClosed
        duty = turnTo*(-2.5)+7.5
        GPIO.output(pins.clawpwm, True)
        pwm.ChangeDutyCycle(duty)
        sleep(0.03)

def move(direction):
    #print(direction)
    if direction == 'right':
        GPIO.output(pins.fl, True)
        GPIO.output(pins.bl, False)
        GPIO.output(pins.fr, True)
        GPIO.output(pins.br, False)
    elif direction == 'left':
        GPIO.output(pins.fl, False)
        GPIO.output(pins.bl, True)
        GPIO.output(pins.fr, False)
        GPIO.output(pins.br, True)
    elif direction == 'backwards':
        GPIO.output(pins.fl, False)
        GPIO.output(pins.bl, True)
        GPIO.output(pins.fr, True)
        GPIO.output(pins.br, False)
    elif direction == 'forwards':
        GPIO.output(pins.fl, True)
        GPIO.output(pins.bl, False)
        GPIO.output(pins.fr, False)
        GPIO.output(pins.br, True)
    else:
        GPIO.output(pins.fl, False)
        GPIO.output(pins.bl, False)
        GPIO.output(pins.fr, False)
        GPIO.output(pins.br, False)

def getController(toget):
    pygame.event.get()
    if map[toget][0] == "A": return controller.get_axis(map[toget][1])
    if map[toget][0] == "B": return controller.get_button(map[toget][1])
    return controller.get_hat(map[toget][1])

def getTof():
    readings=[]
    for luna in sensors:
        if luna.try_lock():
            distanceBytes = bytearray(2)
            luna.writeto_then_readfrom(0x10, bytes([0]), distanceBytes)
            readings.append(distanceBytes[0]+distanceBytes[1]*256)
            luna.unlock()
    for i in range(len(readings)):
        if readings[i] == 0: readings[i] == 1000
    #print(readings)
    return readings

def setleds(l1,l2):
    #print(l1,l2)
    GPIO.output(pins.led1,l1)
    GPIO.output(pins.led2,l2)

def manual(firer = False):
    if firer:
        ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
        ser.reset_input_buffer()
    clawpos = 'open'
    sleep(0.5)   
    while True:
        if getController('B') == 1:
            move('stop')
            sleep(0.5)
            return
        turn = getController("LX")
        forwards = getController("LY")
        claw = getController('RTRIG')
        if claw > 0.5 and clawpos == 'closed':
            clawpos = 'open'
            moveClaw(clawpos)
        elif claw < 0.5 and clawpos == 'open':
            clawpos = 'closed'
            moveClaw(clawpos)
        if firer:
            if getController('RY') > 0.5: 
                ser.write(b'D')
                sleep(0.1)
            if getController('RY') < -0.5: 
                ser.write(b'U')
                sleep(0.1)
            if getController('A') == 1: 
                ser.write(b'F')
                sleep(0.5)
            if ser.in_waiting > 0: print(ser.readline().decode('utf-8').rstrip())
        if abs(turn) + abs(forwards)<0.2: move('stop')
        elif abs(turn) > abs(forwards):
            if turn < 0: move('left')
            else: move('right')
        else:
            if forwards<0: move('forwards')
            else: move('backwards')

def lava():
    sleep(0.5)
    move('forwards')
    sleep(0.5)
    while True:
        move('forwards')
        sleep(0.05)
        if getController('B') == 1:
            move('stop')
            sleep(0.05)
            return
        bl,br,fl,fr = getTof()
        if abs(bl-fl) < abs(br-fr):
            toturn=br-fr
        else:
            toturn=fl-bl
        #print(toturn)
        if fl < 8: move('right')
        elif fr < 8: move('left')
        elif toturn > settings.lavatolerance: move('left')
        elif toturn < -settings.lavatolerance: move('right')
        else: move('forwards')
        sleep(0.1)


def escape():
    sleep(0.5)
    move('forwards')
    sleep(0.5)
    turnSequence=['right','right','left','left','right']
    nextTurnIdx=0
    while True:
        move('forwards')
        sleep(0.05)
        if getController('B') == 1:
            move('stop')
            sleep(0.05)
            return
        bl,br,fl,fr=getTof()
        if nextTurnIdx==5:
            while bl<50 and br<50:
                bl,br,fl,fr=getTof()
            sleep(0.5)
            move('stop')
            return
        elif turnSequence[nextTurnIdx] == 'right' and br>50:
            #sleep(0.1)
            move('right')
            sleep(0.5)
            move('forwards')
            bl,br,fl,fr=getTof()
            while br>50:
                 bl,br,fl,fr = getTof()
            sleep(0.2)
            nextTurnIdx+=1
        elif turnSequence[nextTurnIdx] == 'left' and bl>50:
            #sleep(0.1)
            move('left')
            sleep(0.5)
            move('forwards')
            bl,br,fl,fr=getTof()
            while bl>50:
                bl,br,fl,fr=getTof()
            sleep(0.2)
            nextTurnIdx+=1

def modeSelector():
    global mode
    move('stop')
    while True:
        mode = 'off'
        if getController('A') == 1:
            mode = 'manual'
            manual()
        if getController('Y') == 1:
            mode = 'lava'
            lava()
        if getController('X') == 1:
            mode = 'escape'
            escape()
        if getController('RBUMP') == 1:
            mode = 'pfm'
            manual(firer=True)

def leds():
    while True:
        if mode == 'manual':
            setleds(True, True)
            sleep(1)
        elif mode == 'escape':
            setleds(True, False)
            sleep(0.5)
            setleds(False, True)
            sleep(0.5)
        elif mode == 'lava':
            setleds(True, True)
            sleep(0.5)
            setleds(False,False)
            sleep(0.5)
        elif mode == 'pfm':
            setleds(True, True)
            sleep(0.5)
            setleds(True,False)
            sleep(0.5)
        else:
            setleds(False, False)
            sleep(1)

initializeGPIO()
