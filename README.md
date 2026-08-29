# HID-HOP CircuitPython Firmware

CircuitPython rewrite of the HID-HOP MCU firmware for nRF52840 boards (e.g. Seeed XIAO nRF52840 / Raytac MDBT50Q-CX-40 with compatible bootloader), compatible with the published iOS app protocol.

This project replaces only MCU firmware behavior used by the iOS companion app:
- iOS app: https://github.com/nathanabrewer/hid-hop-ios
- Original Zephyr firmware: https://github.com/nathanabrewer/hid-hop-firmware

## Scope Implemented

- BLE GATT service and UUIDs exactly matching the iOS app.
- Binary protocol subset the iOS app sends (mouse, keyboard/media, ping/info, name, PIN, LED GPIO, gpio-state reads).
- USB HID actions for mouse/keyboard/consumer control.
- Device name + PIN persistence in `microcontroller.nvm` with magic/version/checksum validation and safe default fallback.
- Application PIN auth with constant-time comparison and lockout policy.
- BLE characteristic permissions requiring encrypted link access.

## Intentionally Out of Scope

Not implemented by design in this CircuitPython rewrite:
- BLE Mesh features (provisioning/vendor models/discovery/relay).
- RC PWM/servo/ESC control.
- Custom mesh AES-128-CCM E2E encryption and mesh challenge-response.

If you need those, use the original firmware project: https://github.com/nathanabrewer/hid-hop-firmware

## Required Libraries

Copy the following from `adafruit-circuitpython-bundle-10.x-mpy-20260827.zip` (from https://circuitpython.org/libraries) into `/lib` on CIRCUITPY:

- `adafruit_ble/`
- `adafruit_hid/`

No other community libraries are required by this code.

## Pairing / Security Behavior

- Command/response characteristics require an encrypted BLE link; iOS should present a one-time native pairing prompt on first connect.
- PIN auth is an additional app-layer gate on top of BLE encryption.
- Default PIN on first boot is `123456`.
- PIN verify uses constant-time comparison.
- Lockout policy: after 3 failed PIN attempts, verification is locked for 5 minutes.

## GPIO Behavior

- LED commands are implemented (`CMD_GPIO_SET_LED`, `CMD_GPIO_GET_LED`, `CMD_GPIO_GET_ALL` with LED bits).
- Relay/DIN/AIN commands are accepted for app compatibility but currently return/reflect zero state (no hardware backend).

## File Layout

- `code.py` — entrypoint
- `hidhop/ble_bridge.py` — BLE service + command dispatch
- `hidhop/protocol.py` — protocol frame/parser/encoders
- `hidhop/hid_actions.py` — USB HID adapters
- `hidhop/gpio.py` — LED control
- `hidhop/config_store.py` — `microcontroller.nvm` config persistence
- `hidhop/security.py` — PIN authentication/lockout
- `tests/test_protocol.py` — host-side protocol byte-layout tests

## Setup

1. Install CircuitPython 10.2.1 on supported nRF52840 board.
2. Copy required libraries into `/lib`.
3. Copy `code.py` and `hidhop/` folder to CIRCUITPY root.
4. Reboot (or save `code.py` while connected).
5. In iOS app, scan/connect, accept OS pairing prompt, then verify/set PIN.
