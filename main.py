# pico_buzzer6_lcd.py
# 6-button Game Night Buzzer on Raspberry Pi Pico
# - I2C 16x2 LCD (PCF8574 + HD44780)
# - Piezo buzzer (distinct tone per team) on GP15
# - Reset button on GP18
# - First press wins, LEDs indicate the winner
#
# Buttons: momentary to GND (INPUT_PULLUP)
# LEDs: drive via GPIO (3.3V) OR sink 5V through transistor/ULN2003 from VSYS
#
# Wiring (default pins - change lists below if needed):
#  • Buttons: GP16, GP17, GP19, GP20, GP21, GP22  (→ GND)
#  • LEDs:    GP6,  GP7,  GP8,  GP9,  GP10, GP11  (through 220–330Ω to LED +, LED − to GND)*
#  • Reset:   GP18  (→ GND)
#  • LCD: SDA→GP0, SCL→GP1 (addr 0x27 or 0x3F), power 3V3 recommended
#  • Piezo: GP15 → buzzer (+), buzzer (−) → GND (passive piezo preferred)
#
# *If LEDs need 5V: VSYS→LED(+), LED(−)→transistor→GND, GPIO→1k→base/gate, 10k pulldown.
#   Keep LED_ACTIVE_HIGH=True for low-side switching (GPIO HIGH = LED on).

from machine import Pin, I2C, PWM
import time

# ========= USER CONFIG =========
TEAM_NAMES = ["Team 1", "Team 2", "Team 3", "Team 4", "Team 5", "Team 6"]

# Button GPIOs (pressed = LOW)
BTN_PINS = [16, 17, 19, 20, 21, 22]

# LED GPIOs (one per team, same order as BTN_PINS)
LED_PINS = [6, 7, 8, 9, 10, 11]

RESET_PIN         = 18      # reset button → GND
DEBOUNCE_MS       = 80
TIMEOUT_S         = 8
RESET_COOLDOWN_MS = 400

# LCD (PCF8574 backpack)
I2C_ID       = 0          # I2C0: SDA=GP0, SCL=GP1
I2C_SDA_PIN  = 0
I2C_SCL_PIN  = 1
LCD_ADDR     = 0x27       # change to 0x3F if needed
LCD_COLS     = 16
LCD_ROWS     = 2

# Piezo buzzer
BUZZER_PIN   = 15
VOLUME_DUTY  = 32768      # 0..65535

# LED polarity:
#  - If driving LED anode from GPIO (to resistor→LED→GND), keep True (GPIO HIGH turns LED ON)
#  - If using low-side transistor/ULN2003 (VSYS→LED→res→transistor→GND), also True (GPIO HIGH = ON)
#  - If you wired common-anode with GPIO sinking directly and want ON at LOW, set False
LED_ACTIVE_HIGH = True
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
# Common pitches (Hz)
C5=523; D5=587; E5=659; F5=698; G5=784; A5=880; B5=988
C6=1047; D6=1175; E6=1319; F6=1397; G6=1568; A6=1760

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

START_CHIME = [ (C5,90,10), (E5,90,10), (G5,120,0) ]

# One quick, distinct melody per team (short so gameplay stays snappy)
MELODIES = [
    [(E5,120,15),(G5,120,15),(C6,160,0)],         # Team 1 asc
    [(C6,120,15),(G5,120,15),(E5,160,0)],         # Team 2 desc
    [(D5,100,10),(F5,100,10),(A5,140,0)],         # Team 3
    [(F5,100,10),(A5,100,10),(D6,140,0)],         # Team 4
    [(G5,100,10),(B5,100,10),(E6,140,0)],         # Team 5
    [(A5,100,10),(C6,100,10),(F6,140,0)],         # Team 6
]


# ---- Main app ----
class BuzzerGame:
    def __init__(self):
        # I2C LCD
        self.i2c = I2C(I2C_ID, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=100000)
        self.lcd = I2cLcd(self.i2c, LCD_ADDR, LCD_COLS, LCD_ROWS)

        # Buzzer
        self.buzzer = Buzzer(BUZZER_PIN, VOLUME_DUTY)

        # Buttons (pull-ups; pressed == LOW)
        self.btns = [Pin(p, Pin.IN, Pin.PULL_UP) for p in BTN_PINS]

        # LEDs
        self.leds = [Pin(p, Pin.OUT) for p in LED_PINS]
        self._leds_all_off()

        # Reset
        self.btnR = Pin(RESET_PIN, Pin.IN, Pin.PULL_UP)

        # State
        self.round_open = True
        self.winner_idx = None
        self.win_ts = 0
        self.last_edge = [0]*len(self.btns)
        self.last_r = 0
        self.reset_requested = False
        self.last_reset_handled = 0

        # UI + start chime
        lcd_ready(self.lcd)
        self._play_start_chime()

        # IRQs on falling edge (press)
        for i, b in enumerate(self.btns):
            # capture index as default arg to avoid late binding
            b.irq(trigger=Pin.IRQ_FALLING, handler=lambda pin, idx=i: self._irq_btn(idx))
        self.btnR.irq(trigger=Pin.IRQ_FALLING, handler=self._irq_r)

    # --- LED helpers ---
    def _led_on(self, pin_obj):
        pin_obj.value(1 if LED_ACTIVE_HIGH else 0)
    def _led_off(self, pin_obj):
        pin_obj.value(0 if LED_ACTIVE_HIGH else 1)
    def _leds_all_off(self):
        for led in self.leds:
            self._led_off(led)

    # --- IRQ handlers ---
    def _irq_btn(self, idx):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_edge[idx]) < DEBOUNCE_MS:
            return
        self.last_edge[idx] = now
        if self.round_open:
            self._declare_winner(idx)

    def _irq_r(self, pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_r) < DEBOUNCE_MS:
            return
        self.last_r = now
        self.reset_requested = True

    # --- Core actions ---
    def _declare_winner(self, idx):
        self.round_open = False
        self.winner_idx = idx
        self.win_ts = time.ticks_ms()

        # LEDs: only the winner ON
        for i, led in enumerate(self.leds):
            if i == idx:
                self._led_on(led)
            else:
                self._led_off(led)

        name = TEAM_NAMES[idx] if idx < len(TEAM_NAMES) else f"Team {idx+1}"
        lcd_winner(self.lcd, name)
        print("WIN:", name)

        # Play that team's melody
        try:
            melody = MELODIES[idx] if idx < len(MELODIES) else [(C6,150,0)]
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
        self.winner_idx = None
        self._leds_all_off()
        lcd_ready(self.lcd)
        print("RESET → READY")
        self._play_start_chime()

    def loop(self):
        while True:
            # one-shot reset handling (debounced + cooldown + wait for release)
            if self.reset_requested:
                now = time.ticks_ms()
                if time.ticks_diff(now, self.last_reset_handled) >= RESET_COOLDOWN_MS:
                    while self.btnR.value() == 0:
                        time.sleep_ms(5)
                    self.last_reset_handled = now
                    self.reset_requested = False
                    self.reset_round()

            # auto-reset after winner timeout
            if (not self.round_open) and (self.winner_idx is not None):
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
