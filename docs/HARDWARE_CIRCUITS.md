# VDA IR Control - Hardware Circuitry Design

Circuit designs for close-range IR transmitters (stuck directly on TV receivers), IR learning receivers, and serial bridge connections for ESP32 boards.

## Requirements

- **Boards**: Olimex ESP32-POE-ISO (Ethernet) or ESP32 DevKit (WiFi)
- **IR Outputs**: 5-8 TVs per board
- **IR LEDs**: Standard 940nm
- **IR Receiver**: TSOP38238 (38kHz demodulating)
- **Use Case**: Close-range IR (LED stuck directly on TV's IR receiver window)

---

## IR Transmitter Circuit (IRFZ44N MOSFET)

Using IRFZ44N power MOSFETs for reliable IR LED switching.

```
                        Vcc (5V from ESP32)
                            │
                        ┌───┴───┐
                        │  47Ω  │  (current limiting)
                        └───┬───┘
                            │
                        ┌───┴───┐
                        │  IR   │  940nm LED
                        │  LED  │
                        └───┬───┘
                            │
                       ┌────┴────┐
                       │    D    │
                       │         │  IRFZ44N
ESP32 GPIO ── 100Ω ────│    G    │  (TO-220 package)
                       │         │
                       │    S    │
                       └────┬────┘
                            │
                           GND
```

### IRFZ44N Pinout (looking at front, legs down)

```
┌─────────────┐
│             │
│   IRFZ44N   │
│             │
└──┬───┬───┬──┘
   │   │   │
   G   D   S
  Gate Drain Source
```

### Component Values

| Component | Value | Purpose |
|-----------|-------|---------|
| R_gate | 100Ω | Limits inrush current to gate capacitance |
| R_led | 47Ω | LED current limit (~75mA peak with 5V) |

### Notes

- IRFZ44N Vgs(th) is 2-4V; 3.3V GPIO will partially turn it on
- For IR LEDs this partial turn-on is fine (not switching high current)
- If LED seems dim, add a pull-up to 5V on gate (usually unnecessary)
- **Warning**: TO-220 metal tab is connected to DRAIN - don't let it short!

---

## GPIO Assignments

### Olimex ESP32-POE-ISO

```
Safe GPIOs for IR Output (no conflicts with Ethernet):
- GPIO 2, 4, 5, 13, 14, 15, 16, 32, 33

Reserved (Ethernet RMII):
- GPIO 17, 18, 19, 21, 22, 23
- GPIO 12 (Bootstrap - avoid)

Recommended Assignment:
┌──────────┬─────────┬─────────────┐
│ Port     │ GPIO    │ Function    │
├──────────┼─────────┼─────────────┤
│ IR_OUT1  │ GPIO 2  │ TV 1        │
│ IR_OUT2  │ GPIO 4  │ TV 2        │
│ IR_OUT3  │ GPIO 5  │ TV 3        │
│ IR_OUT4  │ GPIO 13 │ TV 4        │
│ IR_OUT5  │ GPIO 14 │ TV 5        │
│ IR_OUT6  │ GPIO 15 │ TV 6        │
│ IR_OUT7  │ GPIO 32 │ TV 7        │
│ IR_OUT8  │ GPIO 33 │ TV 8        │
│ IR_IN    │ GPIO 34 │ IR Learning │
│ UART RX  │ GPIO 9  │ Serial In   │
│ UART TX  │ GPIO 10 │ Serial Out  │
└──────────┴─────────┴─────────────┘
```

### ESP32 DevKit

```
Safe GPIOs for IR Output:
- GPIO 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33

Reserved:
- GPIO 2 (Built-in LED - can use if LED not needed)
- GPIO 34, 35, 36, 39 (Input only)

Recommended Assignment:
┌──────────┬─────────┬─────────────┐
│ Port     │ GPIO    │ Function    │
├──────────┼─────────┼─────────────┤
│ IR_OUT1  │ GPIO 4  │ TV 1        │
│ IR_OUT2  │ GPIO 5  │ TV 2        │
│ IR_OUT3  │ GPIO 12 │ TV 3        │
│ IR_OUT4  │ GPIO 13 │ TV 4        │
│ IR_OUT5  │ GPIO 14 │ TV 5        │
│ IR_OUT6  │ GPIO 15 │ TV 6        │
│ IR_OUT7  │ GPIO 18 │ TV 7        │
│ IR_OUT8  │ GPIO 19 │ TV 8        │
│ IR_IN    │ GPIO 34 │ IR Learning │
│ UART RX  │ GPIO 16 │ Serial In   │
│ UART TX  │ GPIO 17 │ Serial Out  │
└──────────┴─────────┴─────────────┘
```

---

## IR Receiver Circuit (Learning)

### TSOP38238 Connection

```
              TSOP38238
            ┌─────────────┐
            │   ┌─────┐   │
            │   │ ))) │   │  (IR receiver dome)
            │   └─────┘   │
            │             │
            │  1   2   3  │
            └──┬───┬───┬──┘
               │   │   │
               │   │   └── Pin 3: Vs (3.3V)
               │   │
               │   └────── Pin 2: GND
               │
               └────────── Pin 1: OUT → GPIO 34
```

### Simple Direct Connection (Recommended)

For close-range setups with short wiring:

```
3.3V ─────────────────── TSOP38238 Pin 3 (Vs)
GND ──────────────────── TSOP38238 Pin 2 (GND)
GPIO 34 ◄──────────────── TSOP38238 Pin 1 (OUT)
```

No filtering capacitors needed for close-range.

### Optional Filtering

If you experience inconsistent IR learning, add a 100nF ceramic cap:

```
3.3V ──┬─────────────── TSOP38238 Pin 3 (Vs)
       │
   ┌───┴───┐
   │ 100nF │  (ceramic, close to TSOP)
   └───┬───┘
       │
GND ───┴─────────────── TSOP38238 Pin 2 (GND)
```

---

## Serial Bridge (RS232/TTL)

### RS232 Level Conversion (MAX3232)

For HDMI matrices and AV equipment using RS232 levels (-12V to +12V):

```
                    ┌─────────────┐
ESP32 TX ──────────│ TX      T1O │──────── RS232 TX to device
(GPIO 10/17)       │             │
                   │   MAX3232   │
ESP32 RX ──────────│ RX      R1I │──────── RS232 RX from device
(GPIO 9/16)        │             │
                   │             │
            3.3V ──│ VCC     GND │──── GND
                   │             │
                   └──┬──┬──┬──┬─┘
                      │  │  │  │
                    C1+ C1- C2+ C2-
                      │  │  │  │
                   ┌──┴──┴──┴──┴──┐
                   │ 4x 100nF     │ (charge pump caps)
                   └──────────────┘
```

### TTL Level Connection (3.3V/5V)

Direct connection for TTL-level devices:

```
ESP32 TX (GPIO 10/17) ──────────── Device RX
ESP32 RX (GPIO 9/16)  ──────────── Device TX
GND ──────────────────────────────── GND
```

For 5V TTL devices, add a voltage divider on RX:

```
Device TX (5V) ──── 10kΩ ──┬── ESP32 RX
                           │
                         20kΩ
                           │
                          GND

Output = 5V × 20k/(10k+20k) = 3.3V
```

---

## Complete Wiring Diagram (Olimex POE-ISO)

```
                        OLIMEX ESP32-POE-ISO
                    ┌─────────────────────────────┐
                    │                             │
    RJ45 (PoE) ─────│ ETH                         │
                    │                             │
                    │ GPIO2  ○──── IR_OUT1 ───────│──→ TV1
                    │ GPIO4  ○──── IR_OUT2 ───────│──→ TV2
                    │ GPIO5  ○──── IR_OUT3 ───────│──→ TV3
                    │ GPIO13 ○──── IR_OUT4 ───────│──→ TV4
                    │ GPIO14 ○──── IR_OUT5 ───────│──→ TV5
                    │ GPIO15 ○──── IR_OUT6 ───────│──→ TV6
                    │ GPIO32 ○──── IR_OUT7 ───────│──→ TV7
                    │ GPIO33 ○──── IR_OUT8 ───────│──→ TV8
                    │                             │
                    │ GPIO34 ○──── IR_IN ◄────────│─── TSOP38238
                    │                             │
                    │ GPIO9  ○──── SERIAL RX ◄────│─── HDMI Matrix
                    │ GPIO10 ○──── SERIAL TX ─────│──→ HDMI Matrix
                    │                             │
                    │ 3.3V   ○──── VCC            │
                    │ 5V     ○──── IR LED VCC     │
                    │ GND    ○──── GND            │
                    │                             │
                    └─────────────────────────────┘
```

---

## Bill of Materials (per board)

| Qty | Component | Value | Notes |
|-----|-----------|-------|-------|
| 8 | IR LED | 940nm | TSAL6100, IR333, or similar |
| 8 | MOSFET | IRFZ44N | TO-220 package |
| 8 | Resistor | 100Ω | Gate resistors |
| 8 | Resistor | 47Ω | LED current limiting |
| 1 | IR Receiver | TSOP38238 | 38kHz demodulating |
| 1 | Capacitor | 100nF | Optional - IR receiver filtering |
| 1 | MAX3232 | - | Only if RS232 serial needed |
| 4 | Capacitor | 100nF | MAX3232 charge pump (if used) |

---

## Physical Installation

### IR LED Mounting (Close-Range)

```
TV Front Panel:
┌────────────────────────────────┐
│                                │
│    ┌────┐                      │
│    │ IR │ ← TV's IR receiver   │
│    │ RX │                      │
│    └────┘                      │
│      ▲                         │
│      │                         │
│   ┌──┴──┐                      │
│   │ LED │ ← Your IR LED        │
│   └─────┘   (taped over RX)    │
│                                │
└────────────────────────────────┘
```

**Mounting options:**
1. Black electrical tape (hides LED, blocks ambient IR)
2. 3M VHB tape (strong adhesive)
3. Small 3D printed housing
4. Heat shrink over LED leads for strain relief

### Cable Recommendations

- **Wire**: 2-conductor, 22-26 AWG
- **Length**: Keep runs under 10m
- **Shielding**: Use shielded cable if near power lines

**Connector options:**
- 3.5mm mono audio jack (simple, common)
- JST connectors (reliable, keyed)
- Screw terminals on board (easiest)

---

## Quick Reference

### Per IR Output Wiring

```
ESP32 GPIO ──── 100Ω ──── IRFZ44N Gate
                              │
5V ──── 47Ω ──── IR LED ──── Drain
                              │
GND ─────────────────────── Source
```

### IR Receiver Wiring

```
3.3V ──── TSOP Pin 3 (Vs)
GND ───── TSOP Pin 2 (GND)
GPIO 34 ← TSOP Pin 1 (OUT)
```
