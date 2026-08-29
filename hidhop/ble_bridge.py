"""BLE GATT service + protocol dispatcher for HID-HOP."""

import struct
import time
try:
    import adafruit_logging as logging
except ImportError:  # host test fallback
    import logging

from _bleio import Attribute
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.characteristics import Characteristic
from adafruit_ble.characteristics.stream import StreamIn, StreamOut
from adafruit_ble.services import Service
from adafruit_ble.uuid import VendorUUID

from hidhop import constants as c
from hidhop import protocol

logger = logging.getLogger("hidhop.ble_bridge")

_CMD_NAMES = {
    c.CMD_MOUSE_MOVE: "MOUSE_MOVE",
    c.CMD_MOUSE_CLICK: "MOUSE_CLICK",
    c.CMD_MOUSE_SCROLL: "MOUSE_SCROLL",
    c.CMD_MOUSE_DRAG_START: "MOUSE_DRAG_START",
    c.CMD_MOUSE_DRAG_END: "MOUSE_DRAG_END",
    c.CMD_KEYBOARD_TYPE: "KEYBOARD_TYPE",
    c.CMD_KEYBOARD_KEY: "KEYBOARD_KEY",
    c.CMD_KEYBOARD_COMBO: "KEYBOARD_COMBO",
    c.CMD_MEDIA_KEY: "MEDIA_KEY",
    c.CMD_PING: "PING",
    c.CMD_GET_INFO: "GET_INFO",
    c.CMD_SET_NAME: "SET_NAME",
    c.CMD_SET_PIN: "SET_PIN",
    c.CMD_VERIFY_PIN: "VERIFY_PIN",
    c.CMD_GET_NAME: "GET_NAME",
    c.CMD_GPIO_SET_LED: "GPIO_SET_LED",
    c.CMD_GPIO_GET_LED: "GPIO_GET_LED",
    c.CMD_GPIO_SET_RELAY: "GPIO_SET_RELAY",
    c.CMD_GPIO_GET_RELAY: "GPIO_GET_RELAY",
    c.CMD_GPIO_READ_DIN: "GPIO_READ_DIN",
    c.CMD_GPIO_READ_AIN: "GPIO_READ_AIN",
    c.CMD_GPIO_GET_ALL: "GPIO_GET_ALL",
}


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
        logger.info("BLE bridge initialized with device_name=%s", self.config.device_name)

    @staticmethod
    def _cmd_name(cmd):
        return _CMD_NAMES.get(cmd, "UNKNOWN_0x%02X" % cmd)

    def _set_radio_name(self, name):
        self.ble.name = name

    def _start_advertising(self, name):
        self._set_radio_name(name)
        advertisement = ProvideServicesAdvertisement(self.service)
        advertisement.complete_name = name
        self.ble.stop_advertising()
        self.ble.start_advertising(advertisement)
        logger.info("BLE advertising started with name=%s", name)

    def _send(self, packet):
        self.service.response.write(packet)

    def _send_status(self, status_code, original_cmd):
        logger.debug(
            "Sending status=0x%02x for cmd=%s",
            status_code,
            self._cmd_name(original_cmd),
        )
        self._send(protocol.build_status(status_code, original_cmd))

    def _update_connection_state(self):
        is_connected = bool(self.ble.connected)
        if self._connected and not is_connected:
            self.pin_auth.reset_session()
            self._rx_buffer = bytearray()
            logger.info("BLE disconnected; auth session reset")
        elif (not self._connected) and is_connected:
            logger.info("BLE connected")
        if not is_connected and not self.ble.advertising:
            self._start_advertising(self.config.device_name)
        self._connected = is_connected

    def _require_auth(self, cmd):
        if cmd in c.PUBLIC_COMMANDS:
            return False
        return not self.pin_auth.authenticated

    def _dispatch(self, cmd, payload):
        logger.debug("Dispatching cmd=%s payload_len=%s", self._cmd_name(cmd), len(payload))
        if self._require_auth(cmd):
            logger.warning("Authentication required for cmd=%s", self._cmd_name(cmd))
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
            logger.info("Device name updated over BLE to %s", self.config.device_name)
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
            logger.info("PIN updated over BLE")
            self._send_status(c.STATUS_OK, cmd)
        elif cmd == c.CMD_VERIFY_PIN:
            raw = protocol.parse_length_prefixed_ascii(payload)
            pin = raw.decode("ascii")
            if pin and (not pin.isdigit()):
                raise ValueError("invalid pin")
            success, attempts_left = self.pin_auth.verify_pin(pin)
            logger.info("PIN verify result: success=%s attempts_left=%s", success, attempts_left)
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
            logger.warning("Relay set command received but relay control is not implemented")
            self._send_status(c.STATUS_OK, cmd)
        else:
            logger.warning("Unknown command received: 0x%02x", cmd)
            self._send_status(c.STATUS_ERR_UNKNOWN_CMD, cmd)

    def process_packet(self, packet):
        cmd, payload, parse_error = protocol.parse_frame(packet)
        if parse_error is not None:
            original = cmd if cmd is not None else 0
            logger.warning(
                "Frame parse error status=0x%02x original_cmd=0x%02x",
                parse_error,
                original,
            )
            self._send_status(parse_error, original)
            return
        try:
            self._dispatch(cmd, payload)
        except ValueError as exc:
            logger.warning("Invalid payload for cmd=%s: %s", self._cmd_name(cmd), exc)
            self._send_status(c.STATUS_ERR_INVALID_DATA, cmd)
        except Exception as exc:
            logger.error("Command execution failed for cmd=%s: %s", self._cmd_name(cmd), exc)
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
        logger.debug("Received BLE chunk len=%s rx_buffer_len=%s", len(chunk), len(self._rx_buffer))
        while len(self._rx_buffer) >= 2:
            payload_len = self._rx_buffer[1]
            frame_len = 2 + payload_len
            if len(self._rx_buffer) < frame_len:
                break
            packet = bytes(self._rx_buffer[:frame_len])
            del self._rx_buffer[:frame_len]
            self.process_packet(packet)
