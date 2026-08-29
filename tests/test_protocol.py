import struct
import unittest

from hidhop import constants as c
from hidhop import protocol


class ProtocolTests(unittest.TestCase):
    def test_parse_frame_ok(self):
        cmd, payload, err = protocol.parse_frame(bytes([0x40, 0x02, 0xAA, 0xBB]))
        self.assertEqual(cmd, 0x40)
        self.assertEqual(payload, b"\xAA\xBB")
        self.assertIsNone(err)

    def test_parse_frame_invalid_length(self):
        cmd, payload, err = protocol.parse_frame(bytes([0x40, 0x03, 0xAA]))
        self.assertEqual(cmd, 0x40)
        self.assertIsNone(payload)
        self.assertEqual(err, c.STATUS_ERR_INVALID_LEN)

    def test_mouse_move_little_endian(self):
        dx, dy = protocol.parse_mouse_move(struct.pack("<hh", -1200, 42))
        self.assertEqual(dx, -1200)
        self.assertEqual(dy, 42)

    def test_keyboard_type_parse(self):
        modifiers, text = protocol.parse_keyboard_type(bytes([0x03, 0x03]) + b"abc")
        self.assertEqual(modifiers, 0x03)
        self.assertEqual(text, b"abc")

    def test_media_key_parse(self):
        usage_id, action = protocol.parse_media_key(bytes([0xE9, 0x00, 0x02]))
        self.assertEqual(usage_id, 0x00E9)
        self.assertEqual(action, 2)

    def test_build_pin_result(self):
        frame = protocol.build_pin_result(True, 2)
        self.assertEqual(frame, bytes([c.CMD_PIN_RESULT, 0x02, 0x01, 0x02]))

    def test_build_gpio_state(self):
        frame = protocol.build_gpio_state(0x05, 0, 0, 0x1234, 0x4567)
        self.assertEqual(frame[0], c.CMD_GPIO_STATE)
        self.assertEqual(frame[1], 7)
        self.assertEqual(frame[2], 0x05)
        self.assertEqual(frame[5:7], b"\x34\x12")
        self.assertEqual(frame[7:9], b"\x67\x45")


if __name__ == "__main__":
    unittest.main()
