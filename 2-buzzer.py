#2-buzzer.py
from machine import Pin, PWM
from utime import sleep

# --- CONFIG ---
buzzer = PWM(Pin(15))        # PWM-capable
gled = Pin(13, Pin.OUT)
yled = Pin(12, Pin.OUT)
rled = Pin(11, Pin.OUT)
buzzer.duty_u16(0)

def beep(freq=1000, ms=1, vol=0.5):
    duty=int(65535*vol)
    buzzer.freq(freq)
    buzzer.duty_u16(duty)
    sleep(ms)
    buzzer.duty_u16(0)

while True:
	beep(1000, 1, 0.7)
	print("beep")
	sleep(1)
