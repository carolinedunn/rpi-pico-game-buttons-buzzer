# pico_button_toggle_lcd.py
# Raspberry Pi Pico + 16x2 I2C LCD (PCF8574+HD44780)
# 6 arcade buttons toggle their own LEDs; LCD shows last-pressed button for 5s

from machine import Pin, I2C
import time

# ========= USER CONFIG =========
TEAM_NAMES = ["Team 1", "Team 2", "Team 3", "Team 4", "Team 5", "Team 6"]

# Button GPIOs (pressed = LOW)
BTN_PINS = [16, 17, 19, 20, 21, 22]

# LED GPIOs (one per team, same order as BTN_PINS)
LED_PINS = [6, 7, 8, 9, 10, 11]

RESET_PIN         = 18      # kept for future use; not used here
DEBOUNCE_MS       = 80
MSG_HOLD_MS       = 5000    # show "last pressed" for 5 seconds

# LCD (PCF8574 backpack) — same pinout
I2C_ID       = 0           # I2C0: SDA=GP0, SCL=GP1
I2C_SDA_PIN  = 0
I2C_SCL_PIN  = 1
LCD_ADDR     = 0x27        # change to 0x3F if needed
LCD_COLS     = 16
LCD_ROWS     = 2

# LED polarity:
#  - Driving LED anode from GPIO (to resistor→LED→GND): keep True (GPIO HIGH = ON)
#  - Using low-side transistor/ULN2003 from VSYS: also True (GPIO HIGH = ON)
#  - Common-anode sink-direct and you want ON at LOW: set False
LED_ACTIVE_HIGH = True
# ===============================


# ---- Minimal I2C HD44780 driver (PCF8574 backpack) ----
class I2cLcd:
    MASK_RS = 0x01; MASK_RW = 0x02; MASK_E = 0x04; MASK_BL = 0x08
    def __init__(self, i2c, addr, cols, rows):
        self.i2c, self.addr, self.cols, self.rows = i2c, addr, cols, rows
        self.bl = self.MASK_BL
        self._w(0); time.sleep_ms(50)
        self._n(0x03); time.sleep_ms(5)
        self._n(0x03); time.sleep_us(150)
        self._n(0x03); self._n(0x02)       # 4-bit
        self.cmd(0x28)                     # 4-bit, 2-line
        self.cmd(0x08)                     # display off
        self.cmd(0x01); time.sleep_ms(2)   # clear
        self.cmd(0x06)                     # entry mode
        self.cmd(0x0C)                     # display on
    def _w(self, v): self.i2c.writeto(self.addr, bytes([v | self.bl]))
    def _p(self, d): self._w(d | self.MASK_E); time.sleep_us(1); self._w(d & ~self.MASK_E); time.sleep_us(50)
    def _n(self, n, rs=0):
        d = (n << 4) & 0xF0
        if rs: d |= self.MASK_RS
        self._p(d)
    def _b(self, val, rs): self._n(val >> 4, rs); self._n(val & 0x0F, rs)
    def cmd(self, c):
        self._b(c, 0)
        if c in (0x01, 0x02): time.sleep_ms(2)
    def putc(self, ch): self._b(ch, 1)
    def puts(self, s):
        for c in s: self.putc(ord(c))
    def clear(self): self.cmd(0x01)
    def set_cursor(self, col, row):
        offs = [0x00, 0x40, 0x00 + self.cols, 0x40 + self.cols]
        self.cmd(0x80 | (offs[row] + col))

# ---- LCD helpers ----
def center(text, width=LCD_COLS):
    if len(text) >= width: return text[:width]
    pad = (width - len(text)) // 2
    return " " * pad + text + " " * (width - len(text) - pad)

def lcd_show_ready(lcd):
    lcd.clear()
    lcd.set_cursor(0, 0); lcd.puts(center("READY"))
    lcd.set_cursor(0, 1); lcd.puts(center("Press a button"))

def lcd_show_last(lcd, label):
    lcd.clear()
    lcd.set_cursor(0, 0); lcd.puts(center("Last pressed"))
    lcd.set_cursor(0, 1); lcd.puts(center(label))

# ---- Main app ----
class ToggleGame:
    def __init__(self):
        # LCD
        self.i2c = I2C(I2C_ID, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=100000)
        self.lcd = I2cLcd(self.i2c, LCD_ADDR, LCD_COLS, LCD_ROWS)

        # Buttons (pull-ups; pressed == LOW)
        self.btns = [Pin(p, Pin.IN, Pin.PULL_UP) for p in BTN_PINS]

        # LEDs
        self.leds = [Pin(p, Pin.OUT) for p in LED_PINS]
        self.led_state = [False] * len(self.leds)
        self._apply_leds()

        # (optional) reset pin — not used, but set up if you want later
        self.btnR = Pin(RESET_PIN, Pin.IN, Pin.PULL_UP)

        # Debounce & event state
        self.last_edge = [0] * len(self.btns)
        self.pending_idx = None     # which button was pressed (to process in main loop)
        self.msg_deadline = 0       # when to return to READY
        self.showing_last = False

        # UI
        lcd_show_ready(self.lcd)

        # IRQs for buttons
        for i, b in enumerate(self.btns):
            b.irq(trigger=Pin.IRQ_FALLING, handler=lambda pin, idx=i: self._irq_btn(idx))

    # --- LED helpers ---
    def _led_on(self, pin_obj):  pin_obj.value(1 if LED_ACTIVE_HIGH else 0)
    def _led_off(self, pin_obj): pin_obj.value(0 if LED_ACTIVE_HIGH else 1)
    def _apply_leds(self):
        for i, led in enumerate(self.leds):
            (self._led_on if self.led_state[i] else self._led_off)(led)

    # --- IRQ handler: record the press, do work in loop() ---
    def _irq_btn(self, idx):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_edge[idx]) < DEBOUNCE_MS:
            return
        self.last_edge[idx] = now
        self.pending_idx = idx  # handle in main loop

    # --- Main loop ---
    def loop(self):
        while True:
            # Process a press (toggle LED, show message)
            if self.pending_idx is not None:
                idx = self.pending_idx
                self.pending_idx = None

                # toggle LED state & apply
                self.led_state[idx] = not self.led_state[idx]
                self._apply_leds()

                # update LCD with team name for 5 seconds
                name = TEAM_NAMES[idx] if idx < len(TEAM_NAMES) else f"Button {idx+1}"
                lcd_show_last(self.lcd, name)
                self.showing_last = True
                self.msg_deadline = time.ticks_add(time.ticks_ms(), MSG_HOLD_MS)

            # Return to READY after 5s (unless another press arrived and reset timer)
            if self.showing_last and time.ticks_diff(time.ticks_ms(), self.msg_deadline) >= 0:
                lcd_show_ready(self.lcd)
                self.showing_last = False

            time.sleep_ms(10)

def main():
    app = ToggleGame()
    try:
        app.loop()
    except KeyboardInterrupt:
        app.lcd.clear()
        app.set_cursor(0, 0); app.puts(center("Goodbye!"))
        time.sleep_ms(500)
        app.lcd.clear()

if __name__ == "__main__":
    main()
