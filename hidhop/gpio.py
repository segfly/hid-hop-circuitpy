"""LED control for up to 3 outputs; relay/DIN/AIN are reported as zeros."""

import digitalio
import board

from hidhop import constants as c


class GPIOController:
    def __init__(self):
        self._led_ios = self._init_led_ios()
        self._led_state = 0

    def _init_led_ios(self):
        led_pin_names = [
            ("LED_RED", "LED_GREEN", "LED_BLUE"),
            ("LEDR", "LEDG", "LEDB"),
            ("D0", "D1", "D2"),
        ]
        resolved = []
        for group in led_pin_names:
            if all(hasattr(board, name) for name in group):
                for name in group:
                    resolved.append(getattr(board, name))
                break
        if not resolved and hasattr(board, "LED"):
            resolved.append(getattr(board, "LED"))

        led_ios = []
        for pin in resolved[: c.GPIO_LED_COUNT]:
            try:
                io = digitalio.DigitalInOut(pin)
                io.direction = digitalio.Direction.OUTPUT
                io.value = False
                led_ios.append(io)
            except Exception:
                pass
        return led_ios

    def _apply(self):
        for index, io in enumerate(self._led_ios):
            io.value = bool(self._led_state & (1 << index))

    def set_led(self, led_index, state):
        if led_index == 0xFF:
            self._led_state = state & 0x07
            self._apply()
            return True
        if led_index >= c.GPIO_LED_COUNT or state not in (0, 1):
            return False
        if state:
            self._led_state |= 1 << led_index
        else:
            self._led_state &= ~(1 << led_index)
        self._apply()
        return True

    def get_led_state(self):
        return self._led_state & 0x07
