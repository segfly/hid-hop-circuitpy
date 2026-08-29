"""USB HID action handlers."""

import time

import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
from adafruit_hid.mouse import Mouse
from adafruit_hid.consumer_control import ConsumerControl


class HIDController:
    def __init__(self):
        self.keyboard = Keyboard(usb_hid.devices)
        self.layout = KeyboardLayoutUS(self.keyboard)
        self.mouse = Mouse(usb_hid.devices)
        self.consumer = ConsumerControl(usb_hid.devices)

    @staticmethod
    def usb_connected():
        return len(usb_hid.devices) > 0

    @staticmethod
    def _modifier_keycodes(modifiers):
        keys = []
        if modifiers & 0x01:
            keys.append(Keycode.LEFT_CONTROL)
        if modifiers & 0x02:
            keys.append(Keycode.LEFT_SHIFT)
        if modifiers & 0x04:
            keys.append(Keycode.LEFT_ALT)
        if modifiers & 0x08:
            keys.append(Keycode.LEFT_GUI)
        if modifiers & 0x10:
            keys.append(Keycode.RIGHT_CONTROL)
        if modifiers & 0x20:
            keys.append(Keycode.RIGHT_SHIFT)
        if modifiers & 0x40:
            keys.append(Keycode.RIGHT_ALT)
        if modifiers & 0x80:
            keys.append(Keycode.RIGHT_GUI)
        return keys

    def mouse_move(self, dx, dy):
        while dx != 0 or dy != 0:
            sx = max(-127, min(127, dx))
            sy = max(-127, min(127, dy))
            self.mouse.move(x=sx, y=sy)
            dx -= sx
            dy -= sy

    def mouse_click(self, buttons, action):
        button_map = {0x01: Mouse.LEFT_BUTTON, 0x02: Mouse.RIGHT_BUTTON, 0x04: Mouse.MIDDLE_BUTTON}
        mapped = 0
        for mask, value in button_map.items():
            if buttons & mask:
                mapped |= value
        if action == 0:
            self.mouse.release(mapped)
        elif action == 1:
            self.mouse.press(mapped)
        elif action == 2:
            self.mouse.click(mapped)
        else:
            raise ValueError("invalid mouse action")

    def mouse_scroll(self, vertical, horizontal):
        v = max(-127, min(127, vertical))
        h = max(-127, min(127, horizontal))
        try:
            self.mouse.move(wheel=v, pan=h)
        except TypeError:
            self.mouse.move(wheel=v)

    def keyboard_type(self, modifiers, text):
        mod_keys = self._modifier_keycodes(modifiers)
        if mod_keys:
            self.keyboard.press(*mod_keys)
        try:
            self.layout.write(text.decode("utf-8"))
        finally:
            if mod_keys:
                self.keyboard.release(*mod_keys)

    def keyboard_key(self, modifiers, keycode, action):
        keys = self._modifier_keycodes(modifiers)
        if action == 0:
            self.keyboard.release(*(keys + [keycode]))
        elif action == 1:
            self.keyboard.press(*(keys + [keycode]))
        elif action == 2:
            self.keyboard.press(*(keys + [keycode]))
            time.sleep(0.01)
            self.keyboard.release(*(keys + [keycode]))
        else:
            raise ValueError("invalid key action")

    def keyboard_combo(self, modifiers, keycodes):
        keys = self._modifier_keycodes(modifiers)
        self.keyboard.press(*(keys + list(keycodes)))
        time.sleep(0.01)
        self.keyboard.release(*(keys + list(keycodes)))

    def media_key(self, usage_id, action):
        if action == 2:
            self.consumer.send(usage_id)
        elif action == 1:
            self.consumer.press(usage_id)
        elif action == 0:
            self.consumer.release()
        else:
            raise ValueError("invalid media action")
