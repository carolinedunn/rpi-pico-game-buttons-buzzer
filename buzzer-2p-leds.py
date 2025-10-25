# pico_buzzer_lcd.py
# Two-button buzzer on Raspberry Pi Pico with I2C 16x2 LCD (PCF8574 + HD44780) + piezo (GP15).
# Adds per-button LEDs: winner's LED lights; both LEDs off on reset.
#
# Wiring:
#  • Team A button: GP16 ↔ GND     • Team B button: GP17 ↔ GND     • Reset: GP18 ↔ GND
#  • Team A LED: GP12 → 220Ω → LED(+) ; LED(−) → GND  (set LED_ACTIVE_HIGH=True)
#  • Team B LED: GP13 → 220Ω → LED(+) ; LED(−) → GND
#    (For common-anode LEDs, tie LED(+) to 3V3, LED(−) via 220Ω to GPIO, and set LED_ACTIVE_HIGH=False)
#  • LCD: VBUS(5V), GND, SDA→GP0, SCL→GP1 (addr 0x27 or 0x3F)
#  • Piezo: GP15 → (+), (–) → GND   (for passive piezo, consider 100–220 Ω series resistor)

from machine import Pin, I2C, PWM
import time

# ========= USER CONFIG =========
TEAM_A_NAME      = "Team 1"
TEAM_B_NAME      = "Team 2"

BTN_A_PIN        = 16      # GP16 ↔ GND
BTN_B_PIN        = 17      # GP17 ↔ GND
RESET_PIN        = 18      # GP18 ↔ GND
DEBOUNCE_MS      = 100
TIMEOUT_S        = 8

I2C_ID           = 0       # I2C0 → GP0=SDA, GP1=SCL
I2C_SDA_PIN      = 0
I2C_SCL_PIN      = 1
LCD_ADDR         = 0x27    # try 0x27 first; if not, change to 0x3F
LCD_COLS         = 16
LCD_ROWS         = 2

BUZZER_PIN       = 15
VOLUME_DUTY      = 32768   # 0..65535
RESET_COOLDOWN_MS = 400    # ignore additional resets for this long

# --- NEW: LED pins ---
LED_A_PIN        = 12      # Team A LED GPIO
LED_B_PIN        = 13      # Team B LED GPIO
LED_ACTIVE_HIGH  = True    # False if using common-anode (active-low) wiring
# ===============================

# ---- Minimal I2C HD44780 driver (PCF8574 backpack) ----
class I2cLcd:
    MASK_RS = 0x01; MASK_RW = 0x02; MASK_E = 0x04; MASK_BL = 0x08
    def __init__(self, i2c, addr, cols, rows):
        self.i2c, self.addr, self.cols, self.rows = i2c, addr, cols, rows
        self.bl = self.MASK_BL
        self._write_byte(0); time.sleep_ms(50)
        self._send_nibble(0x03); time.sleep_ms(5)
        self._send_nibble(0x03); time.sleep_us(150)
        self._send_nibble(0x03); self._send_nibble(0x02)      # 4-bit
        self.command(0x28)  # function set: 4-bit, 2-line
        self.command(0x08)  # display off
        self.command(0x01)  # clear
        time.sleep_ms(2)
        self.command(0x06)  # entry mode
        self.command(0x0C)  # display on (no cursor)

    def _write_byte(self, val): self.i2c.writeto(self.addr, bytes([val | self.bl]))
    def _pulse_e(self, data):   self._write_byte(data | self.MASK_E); time.sleep_us(1); self._write_byte(data & ~self.MASK_E); time.sleep_us(50)
    def _send_nibble(self, nibble, rs=0):
        data = (nibble << 4) & 0xF0
        if rs: data |= self.MASK_RS
        self._pulse_e(data)
    def _send_byte(self, val, rs): self._send_nibble(val >> 4, rs); self._send_nibble(val & 0x0F, rs)
    def command(self, cmd):
        self._send_byte(cmd, rs=0)
        if cmd in (0x01, 0x02): time.sleep_ms(2)
    def write_char(self, ch): self._send_byte(ch, rs=1)
    def write(self, s):       [self.write_char(ord(c)) for c in s]
    def clear(self):          self.command(0x01)
    def home(self):           self.command(0x02)
    def set_cursor(self, col, row):
        row_offsets = [0x00, 0x40, 0x00 + self.cols, 0x40 + self.cols]
        self.command(0x80 | (row_offsets[row] + col))

# ---- Helper UI ----
def center(text, width):
    if len(text) >= width: return text[:width]
    pad = (width - len(text)) // 2
    return " " * pad + text + " " * (width - len(text) - pad)

def lcd_ready(lcd):
    lcd.clear()
    lcd.set_cursor(0, 0); lcd.write(center("READY", LCD_COLS))
    lcd.set_cursor(0, 1); lcd.write(center("Press a button", LCD_COLS))

def lcd_winner(lcd, name):
    lcd.clear()
    lcd.set_cursor(0, 0); lcd.write(center(f"{name} WINS!", LCD_COLS))
    lcd.set_cursor(0, 1); lcd.write(center("Wait/Reset to play", LCD_COLS))

# ---- Buzzer helpers ----
C5=523; D5=587; E5=659; F5=698; G5=784; A5=880; B5=988
C6=1047; D6=1175; E6=1319; G6=1568

class Buzzer:
    def __init__(self, pin_num, volume=32768):
        self.pwm = PWM(Pin(pin_num))
        self.pwm.duty_u16(0)
        self.volume = max(0, min(65535, volume))
    def tone(self, freq, ms):
        if freq <= 0:
            self.silence(ms); return
        self.pwm.freq(int(freq))
        self.pwm.duty_u16(self.volume)
        time.sleep_ms(ms)
        self.pwm.duty_u16(0)
    def silence(self, ms):
        self.pwm.duty_u16(0)
        time.sleep_ms(ms)
    def play(self, seq):
        for f, d, g in seq:
            self.tone(f, d)
            if g: self.silence(g)
    def deinit(self):
        self.pwm.duty_u16(0); self.pwm.deinit()

MELODY_A = [ (E5,120,20), (G5,120,20), (C6,180,0) ]    # ascending (Team 1)
MELODY_B = [ (C6,120,20), (G5,120,20), (E5,180,0) ]    # descending (Team 2)
START_CHIME = [ (C5,90,10), (E5,90,10), (G5,120,0) ]   # short arming chime

# ---- Main app ----
class BuzzerGame:
    def __init__(self):
        # I2C LCD
        self.i2c = I2C(I2C_ID, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=100000)
        self.lcd = I2cLcd(self.i2c, LCD_ADDR, LCD_COLS, LCD_ROWS)

        # Buzzer
        self.buzzer = Buzzer(BUZZER_PIN, VOLUME_DUTY)

        # Buttons (pull-ups; pressed == LOW)
        self.btnA = Pin(BTN_A_PIN, Pin.IN, Pin.PULL_UP)
        self.btnB = Pin(BTN_B_PIN, Pin.IN, Pin.PULL_UP)
        self.btnR = Pin(RESET_PIN,  Pin.IN, Pin.PULL_UP)

        # --- NEW: LED outputs ---
        self.ledA = Pin(LED_A_PIN, Pin.OUT)
        self.ledB = Pin(LED_B_PIN, Pin.OUT)
        self._leds_all_off()  # ensure off at boot

        self.round_open = True
        self.winner = None
        self.win_ts = 0
        self.last_a = self.last_b = self.last_r = 0

        self.reset_requested = False
        self.last_reset_handled = 0

        # UI + start chime
        lcd_ready(self.lcd)
        self._play_start_chime()

        # IRQs on falling edge (press)
        self.btnA.irq(trigger=Pin.IRQ_FALLING, handler=self._irq_a)
        self.btnB.irq(trigger=Pin.IRQ_FALLING, handler=self._irq_b)
        self.btnR.irq(trigger=Pin.IRQ_FALLING, handler=self._irq_r)

    # --- LED helpers ---
    def _led_on(self, pin_obj):
        pin_obj.value(1 if LED_ACTIVE_HIGH else 0)
    def _led_off(self, pin_obj):
        pin_obj.value(0 if LED_ACTIVE_HIGH else 1)
    def _leds_all_off(self):
        self._led_off(self.ledA)
        self._led_off(self.ledB)

    # --- IRQ handlers ---
    def _irq_a(self, pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_a) < DEBOUNCE_MS: return
        self.last_a = now
        if self.round_open:
            self._declare_winner(TEAM_A_NAME, MELODY_A, 'A')

    def _irq_b(self, pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_b) < DEBOUNCE_MS: return
        self.last_b = now
        if self.round_open:
            self._declare_winner(TEAM_B_NAME, MELODY_B, 'B')

    def _irq_r(self, pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_r) < DEBOUNCE_MS: return
        self.last_r = now
        self.reset_requested = True

    # --- Core game actions ---
    def _declare_winner(self, name, melody, which):
        self.round_open = False
        self.winner = name
        self.win_ts = time.ticks_ms()

        # LED: light ONLY the winner, turn the other off
        if which == 'A':
            self._led_on(self.ledA)
            self._led_off(self.ledB)
        else:
            self._led_on(self.ledB)
            self._led_off(self.ledA)

        lcd_winner(self.lcd, name)
        print("WIN:", name)
        try:
            self.buzzer.play(melody)
        except Exception as e:
            print("Buzzer error:", e)

    def _play_start_chime(self):
        try:
            self.buzzer.play(START_CHIME)
        except Exception as e:
            print("Start chime error:", e)

    def reset_round(self):
        self.round_open = True
        self.winner = None
        self._leds_all_off()           # LEDs off on reset
        lcd_ready(self.lcd)
        print("RESET → READY")
        self._play_start_chime()

    def loop(self):
        while True:
            # handle a requested reset once
            if self.reset_requested:
                now = time.ticks_ms()
                if time.ticks_diff(now, self.last_reset_handled) >= RESET_COOLDOWN_MS:
                    while self.btnR.value() == 0:
                        time.sleep_ms(5)
                    self.last_reset_handled = now
                    self.reset_requested = False
                    self.reset_round()

            # auto-reset after winner timeout
            if (not self.round_open) and self.winner is not None:
                if time.ticks_diff(time.ticks_ms(), self.win_ts) >= TIMEOUT_S * 1000:
                    self.reset_round()

            time.sleep_ms(10)

def main():
    game = BuzzerGame()
    try:
        game.loop()
    except KeyboardInterrupt:
        game.lcd.clear()
        game.lcd.set_cursor(0,0); game.lcd.write(center("Goodbye!", LCD_COLS))
        time.sleep(0.3)
        game.lcd.clear()
        game.buzzer.deinit()

if __name__ == "__main__":
    main()
 