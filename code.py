"""HID-HOP CircuitPython firmware entrypoint."""

import traceback
import adafruit_logging as logging

from hidhop.ble_bridge import HIDHopBridge
from hidhop.config_store import ConfigStore
from hidhop.gpio import GPIOController
from hidhop.hid_actions import HIDController
from hidhop.security import PinAuth

APP_LOG_LEVEL = logging.INFO
APP_LOGGERS = (
    "hidhop.app",
    "hidhop.ble_bridge",
    "hidhop.config_store",
    "hidhop.gpio",
    "hidhop.hid_actions",
    "hidhop.security",
)
logger = logging.getLogger("hidhop.app")


def configure_logging(level=APP_LOG_LEVEL):
    for name in APP_LOGGERS:
        logging.getLogger(name).setLevel(level)


def main():
    configure_logging()
    logger.info("Starting HID-HOP firmware")
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
    logger.error("Fatal error: %s", exc)
    traceback.print_exception(exc)
    raise
