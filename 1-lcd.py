# welcome_lcd.py
# Raspberry Pi Pico + I2C 16x2 LCD (PCF8574 + HD44780)
# Pins: I2C0 -> SDA=GP0, SCL=GP1, LCD addr 0x27 (change to 0x3F if needed)

from machine import Pin, I2C
import time

I2C_ID      = 0      # I2C0
I2C_SDA_PIN = 0
I2C_SCL_PIN = 1
LCD_ADDR    = 0x27   # try 0x3F if your module differs
LCD_COLS    = 16
LCD_ROWS    = 2

class I2cLcd:
    MASK_RS = 0x01; MASK_RW = 0x02; MASK_E = 0x04; MASK_BL = 0x08
    def __init__(self, i2c, addr, cols, rows):
        self.i2c, self.addr, self.cols, self.rows = i2c, addr, cols, rows
        self.bl = self.MASK_BL
        self._w(0); time.sleep_ms(50)
        self._n(0x03); time.sleep_ms(5)
        self._n(0x03); time.sleep_us(150)
        self._n(0x03); self._n(0x02)         # 4-bit
        self.cmd(0x28)                        # function set: 4-bit, 2-line
        self.cmd(0x08)                        # display off
        self.cmd(0x01); time.sleep_ms(2)      # clear
        self.cmd(0x06)                        # entry mode
        self.cmd(0x0C)                        # display on (no cursor)
    def _w(self, v): self.i2c.writeto(self.addr, bytes([v | self.bl]))
    def _p(self, d): self._w(d | self.MASK_E); time.sleep_us(1); self._w(d & ~self.MASK_E); time.sleep_us(50)
    def _n(self, n, rs=0):
        d = (n << 4) & 0xF0
        if rs: d |= self.MASK_RS
        self._p(d)
    def _b(self, val, rs):
        self._n(val >> 4, rs); self._n(val & 0x0F, rs)
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

# Init I2C + LCD
i2c = I2C(I2C_ID, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=100000)
lcd = I2cLcd(i2c, LCD_ADDR, LCD_COLS, LCD_ROWS)

# Print exactly as requested
lcd.clear()
lcd.set_cursor(0, 0); lcd.puts("Welcome to")
lcd.set_cursor(0, 1); lcd.puts("Game Night")
