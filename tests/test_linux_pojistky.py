import importlib.machinery
import importlib.util
import os
import sys
import unittest
from unittest import mock

if sys.platform != "linux":
    raise unittest.SkipTest("linuxová část")

ROOT = os.path.join(os.path.dirname(__file__), "..")
_loader = importlib.machinery.SourceFileLoader("kocici_hlidac", os.path.join(ROOT, "kocici-hlidac"))
_spec = importlib.util.spec_from_loader("kocici_hlidac", _loader)
hl = importlib.util.module_from_spec(_spec)
_loader.exec_module(hl)


def zamceny(now=1000.0):
    h = hl.Hlidac()
    h.telemetry = mock.Mock()
    h.stop_saver = mock.Mock()
    h.locked = True
    h.locked_at = h.last_key = now
    return h


class TichoTest(unittest.TestCase):
    def test_ticho_odemkne(self):
        h = zamceny()
        h.check_quiet(1000.0 + hl.QUIET_UNLOCK - 1)
        self.assertTrue(h.locked)
        h.check_quiet(1000.0 + hl.QUIET_UNLOCK)
        self.assertFalse(h.locked)

    def test_lezici_kocka_zamek_drzi(self):
        h = zamceny()
        h.devs = {99: ("/dev/input/event99", "test")}
        with mock.patch.object(hl, "held_keys", return_value=[30, 31]):
            h.check_quiet(1000.0 + hl.QUIET_UNLOCK + 1)
        self.assertTrue(h.locked)

    def test_klavesa_posune_ticho(self):
        h = zamceny()
        h.on_key(30, 1, 1100.0)
        h.check_quiet(1000.0 + hl.QUIET_UNLOCK + 1)
        self.assertTrue(h.locked)


class UspaniTest(unittest.TestCase):
    def test_po_uspani_odemkne(self):
        h = zamceny()
        h.clock_gap = 10.0
        with mock.patch.object(hl.Hlidac, "suspend_gap", return_value=10.0 + 600):
            h.check_suspend()
        self.assertFalse(h.locked)

    def test_bez_uspani_drzi(self):
        h = zamceny()
        h.clock_gap = 10.0
        with mock.patch.object(hl.Hlidac, "suspend_gap", return_value=10.5):
            h.check_suspend()
        self.assertTrue(h.locked)


class DisplejTest(unittest.TestCase):
    def test_zhasne_a_touchpad_rozsviti(self):
        h = zamceny()
        with mock.patch.object(hl, "dpms", return_value=True) as dpms:
            h.check_screen(1000.0 + hl.SCREEN_OFF_AFTER - 1)
            self.assertFalse(h.screen_off)
            h.check_screen(1000.0 + hl.SCREEN_OFF_AFTER)
            self.assertTrue(h.screen_off)
            dpms.assert_called_with("off")
            h.on_pointer(1100.0)
            self.assertFalse(h.screen_off)
            h.check_screen(1100.0 + hl.SCREEN_OFF_AFTER - 1)
            self.assertFalse(h.screen_off)

    def test_odemceni_rozsviti(self):
        h = zamceny()
        h.screen_off = True
        with mock.patch.object(hl, "dpms", return_value=True) as dpms:
            h.unlock()
        dpms.assert_called_with("on")


class ZamykaciObrazovkaTest(unittest.TestCase):
    def test_pri_zamcene_obrazovce_negrabuje(self):
        h = hl.Hlidac()
        h.start_saver = mock.Mock()
        with mock.patch.object(hl, "screen_locked", return_value=True):
            h.lock("test")
        self.assertFalse(h.locked)
        h.start_saver.assert_not_called()


if __name__ == "__main__":
    unittest.main()
