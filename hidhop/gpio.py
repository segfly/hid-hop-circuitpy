"""LED control for up to 3 outputs; relay/DIN/AIN are reported as zeros."""

import digitalio
import board

from hidhop import constants as c


class GPIOController:
    def __init__(self):
        self._active_low = False
        self._led_ios = self._init_led_ios()
        self._led_state = 0

    def _init_led_ios(self):
        led_pin_groups = [
            (("LED_RED", "LED_GREEN", "LED_BLUE"), True),
            (("LEDR", "LEDG", "LEDB"), False),
            (("D0", "D1", "D2"), False),
        ]
        resolved = []
        active_low = False
        for group, group_active_low in led_pin_groups:
            if all(hasattr(board, name) for name in group):
                for name in group:
                    resolved.append(getattr(board, name))
                active_low = group_active_low
                break
        if not resolved and hasattr(board, "LED"):
            resolved.append(getattr(board, "LED"))
            active_low = False

        self._active_low = active_low
        led_ios = []
        for pin in resolved[: c.GPIO_LED_COUNT]:
            try:
                io = digitalio.DigitalInOut(pin)
                io.direction = digitalio.Direction.OUTPUT
                io.value = active_low
                led_ios.append(io)
            except Exception:
                pass
        return led_ios

    def _apply(self):
        for index, io in enumerate(self._led_ios):
            on = bool(self._led_state & (1 << index))
            io.value = (not on) if self._active_low else on

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
