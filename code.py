"""HID-HOP CircuitPython firmware entrypoint."""

import traceback

from hidhop.ble_bridge import HIDHopBridge
from hidhop.config_store import ConfigStore
from hidhop.gpio import GPIOController
from hidhop.hid_actions import HIDController
from hidhop.security import PinAuth


def main():
    config = ConfigStore()
    bridge = HIDHopBridge(
        config_store=config,
        pin_auth=PinAuth(config),
        hid_controller=HIDController(),
        gpio_controller=GPIOController(),
    )
    bridge.run_forever()


try:
    main()
except Exception as exc:  # pragma: no cover
    print("Fatal error:", exc)
    traceback.print_exception(exc)
    raise
