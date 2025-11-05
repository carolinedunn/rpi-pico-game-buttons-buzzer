# Player Raspberry Pi Pico Buzzer Game

A competitive buzzer game for up to 6 players using Raspberry Pi Pico with arcade-style buttons, LED feedback, distinct win tones, and an LCD display.

## Features

- **6 independent player buttons** with arcade-style feel
- **First-press-wins** logic with debouncing
- **Individual LED lighting** for each player's button (lights up on win)
- **Distinct win melodies** for each team
- **16x2 I2C LCD display** showing game status
- **Start chime** when the game is ready
- **Auto-reset** after 8 seconds or manual reset button
- **3D printable enclosure** (files included)

## Materials

- [Raspberry Pi Pico](https://amzn.to/3ZQxY9j)
- [Arcade style buttons](https://amzn.to/47JRmOd)
- [Breadboard](https://amzn.to/4nBJFiM)
- [Piezo buzzer](https://amzn.to/43QuStq)
- [Jumper wires](https://amzn.to/4hDTRpy)
- [Spade connectors](https://amzn.to/43UcBLQ)
- [16x2 I2C LCD display](https://amzn.to/3Llyiy8)

Material links provided are Amazon Affiliate links, which means I may earn a small commission at no extra cost to you.

## Wiring

| Component | Pin(s) | Notes |
|-----------|--------|-------|
| Team 1 Button | GP16 | INPUT_PULLUP to GND |
| Team 1 LED | GP6 | Through 220Ω to Anode, Cathode to GND |
| Team 2 Button | GP17 | INPUT_PULLUP to GND |
| Team 2 LED | GP7 | Through 220Ω to Anode, Cathode to GND |
| Team 3 Button | GP19 | INPUT_PULLUP to GND |
| Team 3 LED | GP8 | Through 220Ω to Anode, Cathode to GND |
| Team 4 Button | GP20 | INPUT_PULLUP to GND |
| Team 4 LED | GP9 | Through 220Ω to Anode, Cathode to GND |
| Team 5 Button | GP21 | INPUT_PULLUP to GND |
| Team 5 LED | GP10 | Through 220Ω to Anode, Cathode to GND |
| Team 6 Button | GP22 | INPUT_PULLUP to GND |
| Team 6 LED | GP11 | Through 220Ω to Anode, Cathode to GND |
| Reset Button | GP18 | INPUT_PULLUP to GND |
| Piezo Buzzer | GP15 | Through 100-220Ω resistor to piezo +, piezo - to GND |
| LCD SDA | GP0 | I2C Data |
| LCD SCL | GP1 | I2C Clock |
| LCD VCC | VBUS | Power |
| LCD GND | GND | Ground |

## 💾 Setup
1. **GitClone**
   ```bash
   sudo apt update && sudo apt upgrade
   git clone https://github.com/carolinedunn/rpi-pico-game-buttons-buzzer.git
2. Download MicroPython UF2 file for your Pico [from this page](https://projects.raspberrypi.org/en/projects/getting-started-with-the-pico/3)
3. Plug in your Pico while holding down the BOOTSEL button.
4. Copy the Python files from your Pi to your Pico.
5. Open [Thonny](https://thonny.org/) and select Pico and MicroPython for the environment.
6. Wire your Pico.
7. Test your Pico.
8. Save the file you want to run on boot as main.py

## 3D Printing

Download the enclosure files from [Thingiverse](https://www.thingiverse.com/thing:7183224)

## How to Play

1. Power on the Raspberry Pi Pico - you'll hear a start chime and see "READY" on the LCD
2. First player to press their button wins
3. The winning player's LED lights up and a unique melody plays
4. LCD displays which team won
5. Game auto-resets after 8 seconds, or press the reset button to play again

## Configuration

You can customize these settings in the code:

- `DEBOUNCE_MS` - Button debounce time (default: 30ms)
- `TIMEOUT_MS` - Auto-reset delay (default: 8000ms)
- `LED_ACTIVE_HIGH` - Set to `False` if using common-anode LED wiring
- `LCD_ADDR` - I2C address of your LCD (0x27 or 0x3F)
- `TEAM_NAMES` - Customize team names

---

## 📖 License
MIT License — free to use, remix, and share.  
Attribution appreciated: link back to [Caroline Dunn’s channel](https://www.youtube.com/caroline).  

---

## 📚 Author
Created by **Caroline Dunn**  
- 🌐 [winningintech.com](https://winningintech.com/)  
- 📺 [YouTube.com/Caroline](https://www.youtube.com/caroline)  
- 📘 [A Woman’s Guide to Winning in Tech](https://amzn.to/3YxHVO7)  
