"""Persistent settings in microcontroller.nvm with checksum and fallback."""

from hidhop import constants as c

try:
    import microcontroller
except ImportError:  # host test fallback
    microcontroller = None

_MAGIC = b"HHP1"
_VERSION = 1
_LAYOUT_SIZE = 37
_NAME_OFFSET = 8
_PIN_OFFSET = 28


class ConfigStore:
    def __init__(self):
        if microcontroller is not None:
            self._nvm = microcontroller.nvm
        else:
            self._nvm = bytearray(64)
        self.device_name = "HID-HOP"
        self.pin = "123456"
        self._load_or_defaults()

    def _checksum(self, buf):
        return sum(buf) & 0xFF

    def _load_or_defaults(self):
        raw = bytes(self._nvm[:_LAYOUT_SIZE])
        if len(raw) < _LAYOUT_SIZE:
            self.save()
            return
        body = raw[:-1]
        if (
            raw[0:4] != _MAGIC
            or raw[4] != _VERSION
            or raw[-1] != self._checksum(body)
        ):
            self.save()
            return
        name_len = raw[5]
        pin_len = raw[6]
        if name_len > c.MAX_DEVICE_NAME_LENGTH or pin_len > c.MAX_PIN_LENGTH:
            self.save()
            return
        try:
            name = raw[_NAME_OFFSET : _NAME_OFFSET + name_len].decode("utf-8")
            pin = raw[_PIN_OFFSET : _PIN_OFFSET + pin_len].decode("ascii")
        except UnicodeError:
            self.save()
            return
        if not pin.isdigit() or len(pin) < c.MIN_PIN_LENGTH:
            self.save()
            return
        self.device_name = name if name else "HID-HOP"
        self.pin = pin

    def save(self):
        buf = bytearray(_LAYOUT_SIZE)
        buf[0:4] = _MAGIC
        buf[4] = _VERSION
        name_bytes = self.device_name.encode("utf-8")[: c.MAX_DEVICE_NAME_LENGTH]
        pin_bytes = self.pin.encode("ascii")[: c.MAX_PIN_LENGTH]
        buf[5] = len(name_bytes)
        buf[6] = len(pin_bytes)
        buf[_NAME_OFFSET : _NAME_OFFSET + len(name_bytes)] = name_bytes
        buf[_PIN_OFFSET : _PIN_OFFSET + len(pin_bytes)] = pin_bytes
        buf[-1] = self._checksum(buf[:-1])
        self._nvm[:_LAYOUT_SIZE] = buf

    def set_name(self, name):
        encoded = name.encode("utf-8")
        if not encoded or len(encoded) > c.MAX_DEVICE_NAME_LENGTH:
            return False
        self.device_name = encoded.decode("utf-8")
        self.save()
        return True

    def set_pin(self, pin):
        if len(pin) < c.MIN_PIN_LENGTH or len(pin) > c.MAX_PIN_LENGTH:
            return False
        if not pin.isdigit():
            return False
        self.pin = pin
        self.save()
        return True
