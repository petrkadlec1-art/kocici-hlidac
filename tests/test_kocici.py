import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import kocici  # noqa: E402


class DetektorTest(unittest.TestCase):
    def test_ctyri_klavesy_naraz(self):
        d = kocici.Detektor()
        self.assertIsNone(d.press(1, 0.0))
        self.assertIsNone(d.press(2, 0.01))
        self.assertIsNone(d.press(3, 0.02))
        self.assertIn("naráz", d.press(4, 0.03))

    def test_rychle_psani_projde(self):
        d = kocici.Detektor()
        now = 0.0
        for code in [1, 2, 1, 3, 2, 4, 3, 5, 4, 6] * 5:  # stisky se překrývají nanejvýš po dvou
            if code in d.down:
                d.release(code)
            else:
                if len(d.down) >= 2:
                    d.release(next(iter(d.down)))
                self.assertIsNone(d.press(code, now))
            now += 0.05
            self.assertIsNone(d.tick(now))

    def test_lehla_si(self):
        d = kocici.Detektor()
        d.press(1, 0.0)
        d.press(2, 0.1)
        self.assertIsNone(d.tick(1.0))
        self.assertIn("držené", d.tick(1.7))

    def test_jedna_drzena_klavesa_neni_kocka(self):
        d = kocici.Detektor()
        d.press(1, 0.0)
        self.assertIsNone(d.tick(10.0))

    def test_autorepetice_nezdrzi_lezici_kocku(self):
        # Windows posílá autorepetici jako další stisk; nesmí posunout čas stisku.
        d = kocici.Detektor()
        d.press(1, 0.0)
        d.press(2, 0.0)
        for i in range(1, 20):
            self.assertIsNone(d.press(1, 0.1 * i))
            d.press(2, 0.1 * i)
        self.assertEqual(len(d.down), 2)
        self.assertIsNotNone(d.tick(2.0))

    def test_dupani(self):
        d = kocici.Detektor()
        d.press(1, 0.0)
        d.press(2, 0.0)
        reasons = []
        for i, t in enumerate([0.1, 0.3, 0.5, 0.7]):
            reasons.append(d.press(10 + i, t))
            d.release(10 + i)
        self.assertIsNone(reasons[2])
        self.assertIn("dupání", reasons[3])

    def test_cooldown(self):
        d = kocici.Detektor()
        d.reset(now=0.0)
        for i in range(5):
            self.assertIsNone(d.press(i, 1.0))
        self.assertIsNone(d.tick(3.0))
        self.assertIsNotNone(d.tick(kocici.COOLDOWN + 0.1))


class OdemykaniTest(unittest.TestCase):
    def test_slovo(self):
        o = kocici.Odemykani("meow")
        self.assertEqual([o.feed(c) for c in "meow"], [False, False, False, True])

    def test_preklep_a_znovu(self):
        o = kocici.Odemykani("meow")
        for c in "mex":
            o.feed(c)
        self.assertEqual(o.progress, 0)
        for c in "mem":
            o.feed(c)
        self.assertEqual(o.progress, 1)  # druhé "m" začíná znovu
        self.assertEqual([o.feed(c) for c in "eow"], [False, False, True])


class NastaveniTest(unittest.TestCase):
    def cfg(self, **env):
        clean = {k: v for k, v in os.environ.items() if not k.startswith("KOCICI_")}
        clean.update(env)
        clean["XDG_CONFIG_HOME"] = clean["APPDATA"] = os.path.join(os.path.dirname(__file__), "neexistuje")
        with mock.patch.dict(os.environ, clean, clear=True):
            return kocici.nastaveni()

    def test_vychozi_pozdrav(self):
        self.assertEqual(self.cfg(KOCICI_LANG="cs")["greeting"], "Ahoj kotě! :)")
        self.assertEqual(self.cfg(KOCICI_LANG="en")["greeting"], "Hi kitty! :)")

    def test_prazdny_pozdrav_schova(self):
        self.assertEqual(self.cfg(KOCICI_LANG="cs", KOCICI_POZDRAV="")["greeting"], "")

    def test_vychozi_slovo(self):
        self.assertEqual(self.cfg(KOCICI_LANG="cs")["unlock"], "mnau")
        self.assertEqual(self.cfg(KOCICI_LANG="en")["unlock"], "meow")

    def test_spatne_slovo(self):
        with self.assertRaises(ValueError):
            self.cfg(KOCICI_UNLOCK="mňau")

    def test_ini(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "kocici-hlidac"))
            with open(os.path.join(d, "kocici-hlidac", "nastaveni.ini"), "w", encoding="utf-8") as f:
                f.write("[kocici]\nlang = cs\nunlock = pusa\ngreeting = Ahoj Micko!\n")
            clean = {k: v for k, v in os.environ.items() if not k.startswith("KOCICI_")}
            clean["XDG_CONFIG_HOME"] = clean["APPDATA"] = d
            with mock.patch.dict(os.environ, clean, clear=True):
                cfg = kocici.nastaveni()
            with mock.patch.dict(os.environ, dict(clean, KOCICI_UNLOCK="mnau"), clear=True):
                self.assertEqual(kocici.nastaveni()["unlock"], "mnau")  # proměnná vyhrává
        self.assertEqual((cfg["lang"], cfg["unlock"], cfg["greeting"]), ("cs", "pusa", "Ahoj Micko!"))


class ScenaTest(unittest.TestCase):
    def test_text_ve_scene(self):
        cfg = {"lang": "en", "unlock": "meow", "greeting": "Hi kitty! :)", "texts": kocici.TEXTS["en"]}
        grid, style = kocici.Scena(cfg).frame(1.0, 80, 30, 2, "meow")
        text = "\n".join("".join(r) for r in grid)
        self.assertIn("Hi kitty! :)", text)
        self.assertIn("m e o w", text)
        self.assertEqual(len(grid), 30)
        self.assertTrue(all(len(r) == 80 for r in grid))

    def test_mala_obrazovka_nespadne(self):
        cfg = {"lang": "cs", "unlock": "mnau", "greeting": "", "texts": kocici.TEXTS["cs"]}
        kocici.Scena(cfg).frame(3.0, 10, 5, 0, "mnau")


if __name__ == "__main__":
    unittest.main()
