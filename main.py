import RPi.GPIO as GPIO
from time import sleep
import pins
import settings
import pygame


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


def initialiseGPIO():
    global pwm,controller, sensors
    pygame.init()
    pygame.joystick.init()
    controller = pygame.joystick.Joystick(0)
    controller.init()
    print("Controller connected:",controller.get_name())
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pins.bl, GPIO.OUT)
    GPIO.setup(pins.br, GPIO.OUT)
    GPIO.setup(pins.fl, GPIO.OUT)
    GPIO.setup(pins.fr, GPIO.OUT)
    GPIO.setup(pins.clawpwm, GPIO.OUT)
    pwm=GPIO.PWM(pins.clawpwm, 50)
    pwm.start(0)
    i2c = board.I2C()  # uses board.SCL and board.SDA
    tca = adafruit_tca9548a.TCA9548A(i2c)
    sensors=[]
    for channel in range(4):
        sensors.append(tca[channel])

def moveClaw(position):
        turnTo = settings.clawOpen
        if position == 'closed': turnTo = settings.clawClosed
        duty = turnTo*(-2.5)+7.5
        GPIO.output(pins.clawpwm, True)
        pwm.ChangeDutyCycle(duty)
        sleep(0.03)

def move(direction):
    if direction == 'forwards':
        GPIO.output(pins.fl, True)
        GPIO.output(pins.bl, False)
        GPIO.output(pins.fr, True)
        GPIO.output(pins.br, False)
    elif direction == 'backwards':
        GPIO.output(pins.fl, False)
        GPIO.output(pins.bl, True)
        GPIO.output(pins.fr, False)
        GPIO.output(pins.br, True)
    elif direction == 'left':
        GPIO.output(pins.fl, False)
        GPIO.output(pins.bl, True)
        GPIO.output(pins.fr, True)
        GPIO.output(pins.br, False)
    elif direction == 'right':
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
        if readings[i] == 0:
            readings[i] == 1000
    print(readings)
    return readings

def manual(): 
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
        if abs(turn) + abs(forwards)<0.1: move('stop')
        elif abs(turn) > abs(forwards):
            if turn < 1: move('left')
            else: move('right')
        else:
            if forwards>1: move('forwards')
            else: move('backwards')

def lava():
    sleep(0.5)
    while True:
        if getController('B') == 1:
            move('stop')
            sleep(0.5)
            return
        bl,br,fl,fr = getTof()
        if bl+fr-br-fl>settings.lavatolerance: move('left')
        elif br+fl-bl-fr>settings.lavatolerance: move('right')
        else: move('forwards')

def escape():
    sleep(0.5)
    while True:
        move('forwards')
        if getController('B') == 1:
            move('stop')
            sleep(0.5)
            return
        bl,br,fl,fr = getTof()
        if bl-br>settings.escapeToTurn:
            sleep(0.5)
            move('left')
            sleep(0.5)
            bl,br,fl,fr = getTof()
            while br-fr>settings.escapeDoneTurn:
                sleep(0.03)
                bl,br,fl,fr = getTof()
            move('forwards')
            sleep(1)
        elif br-bl>settings.escapeToTurn:
            sleep(0.5)
            move('right')
            sleep(0.5)
            bl,br,fl,fr = getTof()
            while bl-fl>settings.escapeDoneTurn:
                sleep(0.03)
                bl,br,fl,fr = getTof()
            move('forwards')
            sleep(1)

def modeSelector():
    while True:
        if getController('A') == 1:
            manual()
        if getController('X') == 1:
            escape()
        if getController('Y') == 1:
            lava()


modeSelector()

# TO DO:
#  - escape route (when wall significantly greater than other wall move a tiny bit then turn until nearer wall parallel) - done I think
#  - modeselector (same as before kinda) - done but probably will change
#  - LEDs - could be simple, but could maybe thread them
#  - proofread because likely doesn't work 