# pico_button_message.py
# Raspberry Pi Pico + 16x2 I2C LCD (PCF8574+HD44780) + reset button on GP18
# Init screen: "Press the button"
# On press: show "button pressed" for 5 seconds, then return to init message

from machine import Pin, I2C
import time

# ---- Pins / LCD config (same pinout as your project) ----
I2C_ID       = 0          # I2C0
I2C_SDA_PIN  = 0          # GP0
I2C_SCL_PIN  = 1          # GP1
LCD_ADDR     = 0x27       # change to 0x3F if needed
LCD_COLS     = 16
LCD_ROWS     = 2

RESET_PIN    = 18         # reset button → GND

DEBOUNCE_MS  = 80
DISPLAY_MS   = 5000       # show "button pressed" for 5 seconds

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

# ---- Helpers ----
def center(text, width=LCD_COLS):
    if len(text) >= width: return text[:width]
    pad = (width - len(text)) // 2
    return " " * pad + text + " " * (width - len(text) - pad)

def show_init(lcd):
    lcd.clear()
    lcd.set_cursor(0, 0); lcd.puts(center("Press the button"))

def show_pressed(lcd):
    lcd.clear()
    lcd.set_cursor(0, 0); lcd.puts(center("Button Pressed"))

# ---- App ----
class ButtonDisplay:
    def __init__(self):
        # LCD
        self.i2c = I2C(I2C_ID, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=100000)
        self.lcd = I2cLcd(self.i2c, LCD_ADDR, LCD_COLS, LCD_ROWS)

        # Reset button (INPUT_PULLUP, pressed == LOW)
        self.btnR = Pin(RESET_PIN, Pin.IN, Pin.PULL_UP)

        # State
        self.last_r = 0
        self.showing_pressed = False
        self.pressed_at = 0
        self.reset_requested = False
        self.last_reset_handled = 0

        # UI
        show_init(self.lcd)

        # IRQ
        self.btnR.irq(trigger=Pin.IRQ_FALLING, handler=self._irq_r)

    def _irq_r(self, pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_r) < DEBOUNCE_MS:
            return
        self.last_r = now
        self.reset_requested = True

    def loop(self):
        while True:
            # handle one-shot press in main loop (debounced + wait-for-release)
            if self.reset_requested:
                now = time.ticks_ms()
                self.reset_requested = False
                # wait for release to avoid repeats while held
                while self.btnR.value() == 0:
                    time.sleep_ms(5)
                # show pressed message and start timer
                show_pressed(self.lcd)
                self.showing_pressed = True
                self.pressed_at = time.ticks_ms()

            # after 5 seconds, return to init message
            if self.showing_pressed:
                if time.ticks_diff(time.ticks_ms(), self.pressed_at) >= DISPLAY_MS:
                    show_init(self.lcd)
                    self.showing_pressed = False

            time.sleep_ms(10)

def main():
    app = ButtonDisplay()
    try:
        app.loop()
    except KeyboardInterrupt:
        app.lcd.clear()
        app.lcd.set_cursor(0, 0); app.lcd.puts(center("Goodbye!"))
        time.sleep(500)
        app.lcd.clear()

if __name__ == "__main__":
    main()
