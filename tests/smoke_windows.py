"""Kouřový test Windows verze na opravdovém desktopu (GitHub Actions windows-latest).

Spustí hlídač s --accept-injected, pošle mu klávesy přes SendInput a ověří:
běžné psaní nezamyká, čtyři klávesy naráz zamknou, držené klávesy se pustí,
spořič je vidět, napsání "meow" odemkne a spořič zmizí.

Použití: python tests/smoke_windows.py <cesta k .exe nebo .pyw> [adresář na snímky]
"""
import ctypes
import ctypes.wintypes as w
import os
import subprocess
import sys
import tempfile
import time

from PIL import ImageGrab

user32 = ctypes.WinDLL("user32", use_last_error=True)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("mouseData", w.DWORD),
                ("dwFlags", w.DWORD), ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("u", _U)]


user32.SendInput.argtypes = [w.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.GetAsyncKeyState.restype = w.SHORT


def key(vk, down):
    i = INPUT(type=1)
    i.u.ki = KEYBDINPUT(vk, 0, 0 if down else 2, 0, 0)
    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))
    time.sleep(0.03)


def type_text(s):
    for ch in s:
        vk = 0x20 if ch == " " else ord(ch.upper())
        key(vk, True)
        key(vk, False)
        time.sleep(0.05)


def log_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def wait_for(path, needle, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if needle in log_text(path):
            return True
        time.sleep(0.2)
    return False


def wait_count(path, needle, n, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if log_text(path).count(needle) >= n:
            return True
        time.sleep(0.2)
    return False


def cat_pixels(img):
    """Kolik pixelů má barvu kočky (#ffaf5f) — spořič je vidět."""
    # Tenké vyhlazené písmo: celý snímek, tolerantní odstín. Kalibrováno na snímcích
    # z windows-latest (1024×768): zamčeno ~1000 px, odemčená plocha ~100 px.
    px = img.convert("RGB").tobytes()
    return sum(1 for i in range(0, len(px), 3)
               if px[i] > 200 and 130 < px[i + 1] < 200 and 50 < px[i + 2] < 140
               and px[i] - px[i + 2] > 90)


def main():
    target = sys.argv[1]
    shots = sys.argv[2] if len(sys.argv) > 2 else "."
    os.makedirs(shots, exist_ok=True)
    tmp = tempfile.mkdtemp()
    logp = os.path.join(tmp, "hlidac.log")
    env = dict(os.environ, KOCICI_LOG=logp, KOCICI_LANG="en", KOCICI_POZDRAV="Hi kitty! :)",
               APPDATA=tmp, LOCALAPPDATA=tmp)
    cmd = [target] if target.endswith(".exe") else [sys.executable, target]
    proc = subprocess.Popen(cmd + ["--accept-injected"], env=env)
    failures = []

    def check(ok, what):
        print(("OK   " if ok else "FAIL ") + what, flush=True)
        if not ok:
            failures.append(what)

    try:
        check(wait_for(logp, "hlídám", 60), "hlídač nastartoval")
        time.sleep(1)

        type_text("hello world this is a human typing")
        time.sleep(2)
        check("KOČKA" not in log_text(logp), "běžné psaní nezamyká")

        for vk in (0x41, 0x53, 0x44, 0x46):  # A S D F naráz
            key(vk, True)
        check(wait_for(logp, "KOČKA", 3), "čtyři klávesy naráz zamknou")
        time.sleep(0.5)
        held = [vk for vk in (0x41, 0x53, 0x44) if user32.GetAsyncKeyState(vk) & 0x8000]
        check(not held, f"držené klávesy puštěny (visí: {held})")
        for vk in (0x41, 0x53, 0x44, 0x46):
            key(vk, False)

        check(wait_for(logp, "spořič ukázán", 5), "spořič se ukázal")
        time.sleep(1.5)
        img = ImageGrab.grab()
        img.save(os.path.join(shots, "zamceno.png"))
        n = cat_pixels(img)
        check(n >= 400, f"kočka je na obrazovce ({n} px)")

        type_text("meox")
        time.sleep(0.5)
        check("odemčeno" not in log_text(logp), "překlep neodemkne")
        type_text("meow")
        check(wait_for(logp, "odemčeno", 3), "napsání meow odemkne")
        check(wait_for(logp, "spořič schován", 3), "spořič zmizel")
        time.sleep(1)
        img = ImageGrab.grab()
        img.save(os.path.join(shots, "odemceno.png"))
        n = cat_pixels(img)
        check(n < 250, f"po odemčení kočka zmizela ({n} px)")

        # Kočka si lehne: dvě klávesy držené (s autorepeticí jako na Windows).
        time.sleep(5.5)  # cooldown po odemčení
        for _ in range(12):
            key(0x4A, True)  # J
            key(0x4B, True)  # K
            time.sleep(0.12)
        check(wait_count(logp, "KOČKA", 2, 2), "ležící kočka (2 klávesy s autorepeticí) zamkne")
        key(0x4A, False)
        key(0x4B, False)
        type_text("meow")
        check(wait_count(logp, "odemčeno", 2, 3), "znovu odemčeno")
    finally:
        # /T: onefile .exe spouští sám sebe jako podproces
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        print("---- log ----")
        print(log_text(logp))

    if failures:
        print(f"{len(failures)} selhání")
        sys.exit(1)
    print("vše prošlo")


if __name__ == "__main__":
    main()
