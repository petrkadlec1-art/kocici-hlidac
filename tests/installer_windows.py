"""Test instalátoru na opravdových Windows (GitHub Actions windows-latest).

Ověří: instalace bez autostartu ho nezapne ani prvním spuštěním aplikace,
reinstalace přes běžící hlídač projde a autostart zapne, odinstalace
ukončí hlídač a smaže exe, zástupce i autostart.

Použití: python tests/installer_windows.py dist/kocici-hlidac-setup.exe
"""
import os
import subprocess
import sys
import tempfile
import time
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
SHORTCUT = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs",
                        "Kočičí hlídač.lnk")


def run_value():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            return winreg.QueryValueEx(k, "KociciHlidac")[0]
    except OSError:
        return None


def running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq kocici-hlidac.exe", "/NH"],
                         capture_output=True, text=True).stdout
    return "kocici-hlidac.exe" in out


def wait(cond, secs=30):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.5)
    return cond()


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def check(ok, msg):
    print(("OK   " if ok else "FAIL ") + msg, flush=True)
    if not ok:
        sys.exit(1)


def install(setup, target, tasks):
    r = subprocess.run([setup, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                        "/LANG=cs", f"/DIR={target}", f"/MERGETASKS={tasks}"], timeout=120)
    check(r.returncode == 0, f"instalace ({tasks}) skončila kódem {r.returncode}")


def main():
    setup = os.path.abspath(sys.argv[1])
    target = os.path.join(tempfile.mkdtemp(), "kocici-hlidac")
    exe = os.path.join(target, "kocici-hlidac.exe")
    marker = os.path.join(os.environ["APPDATA"], "kocici-hlidac", ".spusteno")
    log = os.path.join(os.environ["LOCALAPPDATA"], "kocici-hlidac", "hlidac.log")
    if os.path.exists(marker):
        os.remove(marker)

    install(setup, target, "!autostart")
    check(os.path.exists(exe), "exe je nainstalované")
    check(os.path.exists(SHORTCUT), "zástupce ve Startu existuje")
    check(run_value() is None, "bez zaškrtnutí není autostart")

    subprocess.Popen([exe])
    check(wait(running), "nainstalovaný hlídač běží")
    # "hlídám klávesnici" se loguje až po případném zápisu autostartu.
    check(wait(lambda: os.path.exists(marker) and "hlídám klávesnici" in read(log)),
          "hlídač dokončil první spuštění")
    print(read(log), flush=True)
    check(run_value() is None, "první spuštění si autostart samo nezapnulo")

    install(setup, target, "autostart")
    check(run_value() == f'"{exe}"', f"autostart ukazuje na instalaci: {run_value()!r}")

    subprocess.Popen([exe])
    check(wait(running), "hlídač po reinstalaci běží")
    r = subprocess.run([os.path.join(target, "unins000.exe"), "/VERYSILENT",
                        "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=120)
    check(r.returncode == 0, f"odinstalace skončila kódem {r.returncode}")
    check(wait(lambda: not os.path.exists(exe)), "exe je pryč")
    check(not running(), "hlídač neběží")
    check(not os.path.exists(SHORTCUT), "zástupce je pryč")
    check(run_value() is None, "autostart je pryč")


if __name__ == "__main__":
    main()
