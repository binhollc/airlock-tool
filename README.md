# airlock-tool

Command-line tool for updating firmware on devices running the Airlock bootloader.

## Requirements

- Python 3.8 or later — [download here](https://www.python.org/downloads/)
  - When installing Python on Windows, check **"Add Python to PATH"**

## Install

Clone this repository and install:

```
git clone https://github.com/binhollc/airlock-tool.git
cd airlock-tool
pip install .
```

Verify it works:

```
airlock-tool --help
```

## How to flash firmware

### Step 1 — Connect the board

Connect the board to your computer using the USB port used for firmware updates (not the debug probe port).

For example, on the **FRDM-MCXN947**, use the **J11 (HS USB)** connector.

### Step 2 — Enter bootloader mode

If the application firmware supports it, the device enters bootloader mode automatically when `airlock-tool flash` is run. Otherwise, press the **RESET button twice quickly** (double-tap within half a second).

> If no application is installed, the board enters bootloader mode automatically when connected.

### Step 3 — Verify the board is detected

```
airlock-tool list --hid
```

Expected output:

```
         HID Devices
┌──────────────┬───────────┬───────────┬──────────────┐
│ Device       │ VID:PID   │ Unique ID │ Product      │
├──────────────┼───────────┼───────────┼──────────────┤
│ FRDM-MCXN947 │ cafe:4002 │ ...       │ frdm_mcxn947 │
└──────────────┴───────────┴───────────┴──────────────┘
```

If you see **"No HID devices found"**, check that:
- The USB cable is in the correct port (not the debug probe)
- You did the double-tap reset
- The bootloader is installed on the board

### Step 4 — Flash the firmware

```
airlock-tool flash firmware.afx
```

Expected output:

```
Found 514 blocks in firmware.afx
Connected to FRDM-MCXN947 (cafe:4002)
  Flash: 92 pages x 8192 bytes, family 0x2abc77ec
  Board: ...
Flashing ━━━━━━━━━━━━━━━━━━━━━ 100% (514/514)
Flash complete — reset into app
```

The board resets automatically and the new firmware starts running.

## Other commands

| Command | Description |
|---|---|
| `airlock-tool info` | Show detailed info about the connected device |
| `airlock-tool list` | List all connected devices (HID, WebUSB, drives) |
| `airlock-tool list --hid` | List HID devices only |
| `airlock-tool list --drives` | List USB Mass Storage boot drives only |
| `airlock-tool reset` | Reset device from bootloader into application |
| `airlock-tool flash file.afx --hid` | Force flashing via USB HID |
| `airlock-tool flash file.afx --msc` | Force flashing via USB Mass Storage |

All commands accept `-p <product>` to target a specific device when multiple are connected:

```
airlock-tool flash firmware.afx -p frdm_mcxn947
```

## Supported devices

| Device | VID:PID | Product name |
|---|---|---|
| Binho Supernova | 1fc9:82fc | binho_supernova |
| Binho Pulsar | 1fc9:82fd | binho_pulsar |
| FRDM-MCXN947 | cafe:4002 | frdm_mcxn947 |
| FRDM-MCXA153 | cafe:4012 | frdm_mcxa153 |
| FRDM-MCXA156 | cafe:4013 | frdm_mcxa156 |
| Nucleo-H503RB | cafe:4020 | nucleo_h503rb |

## Troubleshooting

| Problem | Solution |
|---|---|
| `airlock-tool` command not found | Make sure Python Scripts directory is in your PATH. Try `python -m airlock_tool.cli` as alternative |
| No HID devices found | Check USB cable is in the correct port and board is in bootloader mode (double-tap reset) |
| `hidapi` install fails | On Linux, install `libhidapi-dev` first: `sudo apt install libhidapi-dev` |
| Permission denied (Linux) | Add a udev rule for the device or run with `sudo` |

## License

See [LICENSE](LICENSE).
