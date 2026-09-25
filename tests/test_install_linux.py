"""Linuxový balíček: archiv z tools/balicek_linux.sh a install.sh z něj.

Instaluje se do dočasného HOME; sudo, systemctl a id jsou atrapy. Zapisují,
s čím je skript zavolal, a sudo usermod opravdu přidá skupinu do atrapy
databáze skupin, kterou čte id.
"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

if sys.platform != "linux":
    raise unittest.SkipTest("linuxová část")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

SUDO = """#!/bin/sh
echo "sudo $*" >> "$ATRAPY_LOG"
if [ "$*" = "usermod -aG input kocour" ] && [ -z "$SUDO_BEZ_UCINKU" ]; then
    printf ' input' >> "$SKUPINY_DB"
fi
"""
SYSTEMCTL = """#!/bin/sh
echo "systemctl $*" >> "$ATRAPY_LOG"
case "$*" in
    *is-active*graphical-session.target) exit "${GRAFIKA:-0}" ;;
    *is-active*) exit "${BEZI:-3}" ;;
esac
"""
ID = """#!/bin/sh
case "$*" in
    -u) echo "${ATRAPA_UID:-1000}" ;;
    -un) echo kocour ;;
    "-nG kocour") cat "$SKUPINY_DB" ;;
    -nG) echo "$SKUPINY_SEZENI" ;;
    *) exit 1 ;;
esac
"""
GRAFIKA = "systemctl --user is-active --quiet graphical-session.target"


class InstalaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        archiv = os.path.join(self.tmp, "k.tar.gz")
        subprocess.run(["sh", os.path.join(ROOT, "tools", "balicek_linux.sh"), archiv],
                       check=True, capture_output=True)
        subprocess.run(["tar", "-xzf", archiv, "-C", self.tmp], check=True)
        self.balicek = os.path.join(self.tmp, "kocici-hlidac")
        self.home = os.path.join(self.tmp, "home")
        os.mkdir(self.home)
        self.bin = os.path.join(self.home, ".local", "bin")
        self.log = os.path.join(self.tmp, "volani.log")
        atrapy = os.path.join(self.tmp, "atrapy")
        os.mkdir(atrapy)
        for jmeno, obsah in (("sudo", SUDO), ("systemctl", SYSTEMCTL), ("id", ID)):
            cesta = os.path.join(atrapy, jmeno)
            with open(cesta, "w") as f:
                f.write(obsah)
            os.chmod(cesta, 0o755)
        self.path = atrapy + ":" + os.environ["PATH"]

    def spust(self, *args, db="kocour", sezeni="kocour", uid="1000", **env_navic):
        if os.path.exists(self.log):
            os.remove(self.log)
        skupiny_db = os.path.join(self.tmp, "skupiny")
        with open(skupiny_db, "w") as f:
            f.write(db)
        env = {"PATH": self.path, "HOME": self.home, "LANG": "C", "ATRAPY_LOG": self.log,
               "SKUPINY_DB": skupiny_db, "SKUPINY_SEZENI": sezeni, "ATRAPA_UID": uid,
               **env_navic}
        r = subprocess.run(["./install.sh", *args], cwd=self.balicek, env=env,
                           capture_output=True, text=True)
        volani = []
        if os.path.exists(self.log):
            with open(self.log) as f:
                volani = f.read().splitlines()
        return r, volani

    def rezim(self, soubor):
        return stat.S_IMODE(os.stat(os.path.join(self.bin, soubor)).st_mode)

    def test_prvni_instalace_prida_skupinu_a_ceka_na_prihlaseni(self):
        r, volani = self.spust()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(volani, [
            "sudo usermod -aG input kocour",
            "systemctl --user daemon-reload",
            "systemctl --user enable kocici-hlidac",
            GRAFIKA,
        ])
        self.assertIn("Log out", r.stdout)
        self.assertNotIn("graphical-session.target", r.stdout)
        for f in ("kocici-hlidac", "kocici-spanek"):
            self.assertEqual(self.rezim(f), 0o755, f)
        for f in ("kocici.py", "telemetrie.py"):
            self.assertEqual(self.rezim(f), 0o644, f)
        unit = os.path.join(self.home, ".config", "systemd", "user", "kocici-hlidac.service")
        self.assertTrue(os.path.isfile(unit))

    def test_ve_skupine_hlidac_rovnou_spusti(self):
        r, volani = self.spust(db="kocour input", sezeni="kocour input")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(volani, [
            "systemctl --user daemon-reload",
            "systemctl --user enable kocici-hlidac",
            GRAFIKA,
            "systemctl --user restart kocici-hlidac",
        ])
        self.assertIn("guard is running", r.stdout)

    def test_skupina_pridana_ale_neprihlaseno(self):
        r, volani = self.spust(db="kocour input", sezeni="kocour")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("sudo usermod -aG input kocour", volani)
        self.assertNotIn("systemctl --user restart kocici-hlidac", volani)
        self.assertIn("Log out", r.stdout)

    def test_usermod_bez_ucinku_nic_nenainstaluje(self):
        r, volani = self.spust(SUDO_BEZ_UCINKU="1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("input group", r.stderr)
        self.assertFalse(os.path.exists(self.bin))
        self.assertEqual(volani, ["sudo usermod -aG input kocour"])

    def test_plocha_bez_graphical_session_varuje(self):
        r, _ = self.spust(db="kocour input", sezeni="kocour input", GRAFIKA="3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("graphical-session.target", r.stdout)
        self.assertIn("systemctl --user start kocici-hlidac", r.stdout)

    def test_nainstalovany_hlidac_najde_sve_moduly(self):
        self.spust()
        # V samostatném procesu a v izolovaném režimu, ať se moduly nevezmou z repa.
        for f in ("kocici-hlidac", "kocici-spanek"):
            kod = f"import runpy; runpy.run_path({os.path.join(self.bin, f)!r}, run_name='kontrola')"
            r = subprocess.run([sys.executable, "-I", "-c", kod], cwd=self.tmp,
                               env={"HOME": self.home, "PATH": os.environ["PATH"]},
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f + ": " + r.stderr)

    def test_odinstalace_vse_smaze(self):
        self.spust()
        r, volani = self.spust("--uninstall")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("systemctl --user disable --now kocici-hlidac", volani)
        self.assertEqual(os.listdir(self.bin), [])
        self.assertIn("removed", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(
            self.home, ".config", "systemd", "user", "kocici-hlidac.service")))

    def test_odinstalace_nesmaze_bezici_hlidac(self):
        self.spust()
        r, _ = self.spust("--uninstall", BEZI="0")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(sorted(os.listdir(self.bin)),
                         ["kocici-hlidac", "kocici-spanek", "kocici.py", "telemetrie.py"])

    def test_pod_rootem_odmitne(self):
        r, volani = self.spust(uid="0")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(volani, [])
        self.assertFalse(os.path.exists(self.bin))


if __name__ == "__main__":
    unittest.main()
