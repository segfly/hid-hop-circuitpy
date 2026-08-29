import unittest

from hidhop.config_store import ConfigStore


class ConfigStoreTests(unittest.TestCase):
    def test_set_pin_allows_clear(self):
        store = ConfigStore()
        self.assertTrue(store.set_pin(""))
        self.assertEqual(store.pin, "")

    def test_empty_pin_persists_across_reload(self):
        store = ConfigStore()
        self.assertTrue(store.set_pin(""))

        reloaded = ConfigStore()
        reloaded._nvm = store._nvm
        reloaded._load_or_defaults()
        self.assertEqual(reloaded.pin, "")


if __name__ == "__main__":
    unittest.main()
