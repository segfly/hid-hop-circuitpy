"""BLE GATT service + protocol dispatcher for HID-HOP."""

import struct
import time

from _bleio import Attribute
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.characteristics import Characteristic
from adafruit_ble.characteristics.stream import StreamIn, StreamOut
from adafruit_ble.services import Service
from adafruit_ble.uuid import VendorUUID

from hidhop import constants as c
from hidhop import protocol


class HIDHopService(Service):
    uuid = VendorUUID(c.SERVICE_UUID)
    command = StreamIn(
        uuid=VendorUUID(c.COMMAND_UUID),
        buffer_size=128,
        properties=(Characteristic.WRITE | Characteristic.WRITE_NO_RESPONSE),
        write_perm=Attribute.ENCRYPT_NO_MITM,
    )
    response = StreamOut(
        uuid=VendorUUID(c.RESPONSE_UUID),
        buffer_size=128,
        properties=Characteristic.NOTIFY,
        read_perm=Attribute.ENCRYPT_NO_MITM,
        write_perm=Attribute.NO_ACCESS,
    )


class HIDHopBridge:
    def __init__(self, config_store, pin_auth, hid_controller, gpio_controller):
        self.config = config_store
        self.pin_auth = pin_auth
        self.hid = hid_controller
        self.gpio = gpio_controller
        self.ble = BLERadio()
        self.service = HIDHopService()
        self._connected = False
        self._start_time = time.monotonic()
        self._rx_buffer = bytearray()
        self._start_advertising(self.config.device_name)

    def _set_radio_name(self, name):
        self.ble.name = name

    def _start_advertising(self, name):
        self._set_radio_name(name)
        advertisement = ProvideServicesAdvertisement(self.service)
        advertisement.complete_name = name
        self.ble.stop_advertising()
        self.ble.start_advertising(advertisement)

    def _send(self, packet):
        self.service.response.write(packet)

    def _send_status(self, status_code, original_cmd):
        self._send(protocol.build_status(status_code, original_cmd))

    def _update_connection_state(self):
        is_connected = bool(self.ble.connected)
        if self._connected and not is_connected:
            self.pin_auth.reset_session()
            self._rx_buffer = bytearray()
        if not is_connected and not self.ble.advertising:
            self._start_advertising(self.config.device_name)
        self._connected = is_connected

    def _require_auth(self, cmd):
        if cmd in c.PUBLIC_COMMANDS:
            return False
        return not self.pin_auth.authenticated

    def _dispatch(self, cmd, payload):
        if self._require_auth(cmd):
            self._send_status(c.STATUS_ERR_AUTH_REQUIRED, cmd)
            return

        if cmd == c.CMD_MOUSE_MOVE:
            dx, dy = protocol.parse_mouse_move(payload)
            self.hid.mouse_move(dx, dy)
            self._send_status(c.STATUS_OK, cmd)
        elif cmd == c.CMD_MOUSE_CLICK:
            buttons, action = protocol.parse_mouse_click(payload)
            self.hid.mouse_click(buttons, action)
            self._send_status(c.STATUS_OK, cmd)
        elif cmd == c.CMD_MOUSE_SCROLL:
            vertical, horizontal = protocol.parse_mouse_scroll(payload)
            self.hid.mouse_scroll(vertical, horizontal)
            self._send_status(c.STATUS_OK, cmd)
        elif cmd == c.CMD_MOUSE_DRAG_START:
            if payload:
                raise ValueError("invalid mouse drag start")
            self.hid.mouse_click(0x01, 1)
            self._send_status(c.STATUS_OK, cmd)
        elif cmd == c.CMD_MOUSE_DRAG_END:
            if payload:
                raise ValueError("invalid mouse drag end")
            self.hid.mouse_click(0x01, 0)
            self._send_status(c.STATUS_OK, cmd)
        elif cmd == c.CMD_KEYBOARD_TYPE:
            modifiers, text = protocol.parse_keyboard_type(payload)
            self.hid.keyboard_type(modifiers, text)
            self._send_status(c.STATUS_OK, cmd)
        elif cmd == c.CMD_KEYBOARD_KEY:
            modifiers, keycode, action = protocol.parse_keyboard_key(payload)
            self.hid.keyboard_key(modifiers, keycode, action)
            self._send_status(c.STATUS_OK, cmd)
        elif cmd == c.CMD_KEYBOARD_COMBO:
            modifiers, keycodes = protocol.parse_keyboard_combo(payload)
            self.hid.keyboard_combo(modifiers, keycodes)
            self._send_status(c.STATUS_OK, cmd)
        elif cmd == c.CMD_MEDIA_KEY:
            usage_id, action = protocol.parse_media_key(payload)
            self.hid.media_key(usage_id, action)
            self._send_status(c.STATUS_OK, cmd)
        elif cmd == c.CMD_PING:
            if len(payload) != 8:
                raise ValueError("invalid ping")
            timestamp, sequence = struct.unpack("<II", payload)
            self._send(protocol.build_pong(timestamp, sequence))
        elif cmd == c.CMD_GET_INFO:
            if payload:
                raise ValueError("invalid get info")
            uptime = int(time.monotonic() - self._start_time)
            self._send(
                protocol.build_info_response(
                    self.hid.usb_connected(), self.pin_auth.authenticated, uptime
                )
            )
        elif cmd == c.CMD_SET_NAME:
            raw = protocol.parse_length_prefixed_ascii(payload)
            if len(raw) > c.MAX_DEVICE_NAME_LENGTH:
                raise ValueError("name too long")
            name = raw.decode("utf-8")
            if not self.config.set_name(name):
                raise ValueError("invalid name")
            self._set_radio_name(self.config.device_name)
            self._send_status(c.STATUS_OK, cmd)
        elif cmd == c.CMD_GET_NAME:
            if payload:
                raise ValueError("invalid get name")
            self._send(protocol.build_name_response(self.config.device_name.encode("utf-8")))
        elif cmd == c.CMD_SET_PIN:
            raw = protocol.parse_length_prefixed_ascii(payload)
            pin = raw.decode("ascii")
            if not self.config.set_pin(pin):
                raise ValueError("invalid pin")
            self._send_status(c.STATUS_OK, cmd)
        elif cmd == c.CMD_VERIFY_PIN:
            raw = protocol.parse_length_prefixed_ascii(payload)
            pin = raw.decode("ascii")
            if pin and (not pin.isdigit()):
                raise ValueError("invalid pin")
            success, attempts_left = self.pin_auth.verify_pin(pin)
            self._send(protocol.build_pin_result(success, attempts_left))
        elif cmd == c.CMD_GPIO_SET_LED:
            if len(payload) != 2:
                raise ValueError("invalid led set")
            ok = self.gpio.set_led(payload[0], payload[1])
            if not ok:
                raise ValueError("invalid led state")
            self._send_status(c.STATUS_OK, cmd)
        elif cmd in (c.CMD_GPIO_GET_LED, c.CMD_GPIO_GET_RELAY, c.CMD_GPIO_READ_DIN, c.CMD_GPIO_READ_AIN, c.CMD_GPIO_GET_ALL):
            if payload:
                raise ValueError("invalid gpio read")
            self._send(protocol.build_gpio_state(self.gpio.get_led_state(), 0, 0, 0, 0))
        elif cmd == c.CMD_GPIO_SET_RELAY:
            if len(payload) != 2:
                raise ValueError("invalid relay set")
            self._send_status(c.STATUS_OK, cmd)
        else:
            self._send_status(c.STATUS_ERR_UNKNOWN_CMD, cmd)

    def process_packet(self, packet):
        cmd, payload, parse_error = protocol.parse_frame(packet)
        if parse_error is not None:
            original = cmd if cmd is not None else 0
            self._send_status(parse_error, original)
            return
        try:
            self._dispatch(cmd, payload)
        except ValueError:
            self._send_status(c.STATUS_ERR_INVALID_DATA, cmd)
        except Exception:
            self._send_status(c.STATUS_ERR_USB_FAILED, cmd)

    def run_forever(self):
        while True:
            self._update_connection_state()
            incoming = self.service.command
            if self.ble.connected and incoming.in_waiting:
                chunk = incoming.read(incoming.in_waiting)
                if chunk:
                    self._feed(bytes(chunk))
            time.sleep(0.01)

    def _feed(self, chunk):
        self._rx_buffer.extend(chunk)
        while len(self._rx_buffer) >= 2:
            payload_len = self._rx_buffer[1]
            frame_len = 2 + payload_len
            if len(self._rx_buffer) < frame_len:
                break
            packet = bytes(self._rx_buffer[:frame_len])
            del self._rx_buffer[:frame_len]
            self.process_packet(packet)
