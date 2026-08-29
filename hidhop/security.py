"""Application-level PIN auth with lockout and constant-time comparison."""

import time
try:
    import adafruit_logging as logging
except ImportError:  # host test fallback
    import logging

from hidhop import constants as c

logger = logging.getLogger("hidhop.security")


def constant_time_equals(a, b):
    max_len = c.MAX_PIN_LENGTH
    diff = len(a) ^ len(b)
    for idx in range(max_len):
        byte_a = a[idx] if idx < len(a) else 0
        byte_b = b[idx] if idx < len(b) else 0
        diff |= byte_a ^ byte_b
    return diff == 0


class PinAuth:
    def __init__(self, config_store):
        self._config = config_store
        self._failed_attempts = 0
        self._lockout_until = 0
        self._authenticated = False

    @property
    def authenticated(self):
        return self._authenticated

    def reset_session(self):
        self._authenticated = False
        logger.debug("Session authentication reset")

    def _now(self):
        return int(time.monotonic())

    def verify_pin(self, candidate_pin):
        now = self._now()
        if now < self._lockout_until:
            logger.warning("PIN verification rejected during lockout")
            return False, 0

        expected = self._config.pin
        if expected == "":
            self._authenticated = True
            self._failed_attempts = 0
            logger.info("PIN verification bypassed because PIN is disabled")
            return True, c.MAX_PIN_ATTEMPTS

        if constant_time_equals(candidate_pin.encode("ascii"), expected.encode("ascii")):
            self._authenticated = True
            self._failed_attempts = 0
            logger.info("PIN verification succeeded")
            return True, c.MAX_PIN_ATTEMPTS

        self._authenticated = False
        self._failed_attempts += 1
        attempts_left = c.MAX_PIN_ATTEMPTS - self._failed_attempts
        logger.warning("PIN verification failed; attempts_left=%s", attempts_left)
        if attempts_left <= 0:
            self._lockout_until = now + c.PIN_LOCKOUT_SECONDS
            self._failed_attempts = 0
            attempts_left = 0
            logger.error("PIN lockout activated for %s seconds", c.PIN_LOCKOUT_SECONDS)
        return False, attempts_left
