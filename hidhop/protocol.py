"""Pure protocol parsing/building helpers."""

import struct

from hidhop import constants as c


def parse_frame(data):
    if len(data) < 2:
        return None, None, c.STATUS_ERR_INVALID_LEN
    cmd = data[0]
    payload_len = data[1]
    payload = data[2:]
    if len(payload) != payload_len:
        return cmd, None, c.STATUS_ERR_INVALID_LEN
    return cmd, payload, None


def build_frame(cmd, payload=b""):
    return bytes((cmd, len(payload))) + payload


def build_status(status_code, original_cmd):
    return build_frame(c.CMD_STATUS, bytes((status_code, original_cmd)))


def build_pong(timestamp, sequence):
    return build_frame(c.CMD_PONG, struct.pack("<II", timestamp, sequence))


def build_info_response(usb_connected, session_active, uptime_sec):
    payload = struct.pack(
        "<BBBBI",
        c.PROTOCOL_VERSION_MAJOR,
        c.PROTOCOL_VERSION_MINOR,
        1 if usb_connected else 0,
        1 if session_active else 0,
        uptime_sec,
    )
    return build_frame(c.CMD_INFO_RESPONSE, payload)


def build_name_response(name_bytes):
    payload = bytes((len(name_bytes),)) + name_bytes
    return build_frame(c.CMD_NAME_RESPONSE, payload)


def build_pin_result(success, attempts_left):
    return build_frame(c.CMD_PIN_RESULT, bytes((1 if success else 0, attempts_left)))


def build_gpio_state(led_state, relay_state=0, din_state=0, ain0_value=0, ain1_value=0):
    payload = struct.pack("<BBBHH", led_state, relay_state, din_state, ain0_value, ain1_value)
    return build_frame(c.CMD_GPIO_STATE, payload)


def parse_mouse_move(payload):
    if len(payload) != 4:
        raise ValueError("invalid mouse move length")
    return struct.unpack("<hh", payload)


def parse_mouse_click(payload):
    if len(payload) != 2:
        raise ValueError("invalid mouse click length")
    return payload[0], payload[1]


def parse_mouse_scroll(payload):
    if len(payload) != 2:
        raise ValueError("invalid mouse scroll length")
    return struct.unpack("<bb", payload)


def parse_keyboard_type(payload):
    if len(payload) < 2:
        raise ValueError("invalid keyboard type length")
    modifiers = payload[0]
    text_len = payload[1]
    text = payload[2:]
    if text_len != len(text):
        raise ValueError("invalid keyboard type text length")
    if text_len > c.MAX_KEYBOARD_PAYLOAD:
        raise ValueError("keyboard text too long")
    return modifiers, text


def parse_keyboard_key(payload):
    if len(payload) != 3:
        raise ValueError("invalid keyboard key length")
    return payload[0], payload[1], payload[2]


def parse_keyboard_combo(payload):
    if len(payload) < 2:
        raise ValueError("invalid keyboard combo length")
    modifiers = payload[0]
    key_count = payload[1]
    keys = payload[2:]
    if key_count != len(keys) or key_count > 6:
        raise ValueError("invalid keyboard combo key count")
    return modifiers, keys


def parse_media_key(payload):
    if len(payload) != 3:
        raise ValueError("invalid media key length")
    usage_id = payload[0] | (payload[1] << 8)
    return usage_id, payload[2]


def parse_length_prefixed_ascii(payload):
    if len(payload) < 1:
        raise ValueError("invalid payload")
    text_len = payload[0]
    text = payload[1:]
    if text_len != len(text):
        raise ValueError("length mismatch")
    return text


def consume_stream_frames(rx_buffer, chunk):
    data = rx_buffer + bytes(chunk)
    packets = []
    offset = 0
    total_len = len(data)

    while total_len - offset >= 2:
        payload_len = data[offset + 1]
        frame_len = 2 + payload_len
        if total_len - offset < frame_len:
            break
        packets.append(data[offset : offset + frame_len])
        offset += frame_len

    return data[offset:], packets
