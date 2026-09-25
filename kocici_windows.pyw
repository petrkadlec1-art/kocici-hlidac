"""Kočičí hlídač pro Windows: pozná kočku na klávesnici, zamkne ji a pustí spící kočku.

Jen standardní knihovna (ctypes + tkinter). Klávesy chytá nízkoúrovňový hook
WH_KEYBOARD_LL; když je zamčeno, hook stisky zahazuje, takže do aplikací nejde
nic. Detekce, nastavení a scéna jsou společné s Linuxem v kocici.py.

Vlákna: hook, časovač a ikona v oznamovací oblasti běží ve vlastním vlákně se
smyčkou zpráv (hook musí odpovídat rychle). Spořič je Tk okno v hlavním vlákně;
obě strany si píšou přes frontu.

Použití:
  kocici_windows.pyw                 hlídač s ikonou v oznamovací oblasti
  kocici_windows.pyw --debug         jen loguje, co by detekoval, nezamyká
  kocici_windows.pyw --test          za 3 s zamkne (vyzkoušení)
  kocici_windows.pyw --autostart     zapne spouštění po přihlášení a skončí
  kocici_windows.pyw --no-autostart  vypne spouštění po přihlášení a skončí
  --accept-injected                  bere i uměle poslané klávesy (jen pro testy)
"""
import ctypes
import ctypes.wintypes as w
import os
import queue
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import winreg

HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import kocici  # noqa: E402

DEBUG = "--debug" in sys.argv
ACCEPT_INJECTED = "--accept-injected" in sys.argv

APP_DIR = os.path.dirname(kocici.ini_path())
LOG_PATH = os.environ.get("KOCICI_LOG") or os.path.join(
    os.environ.get("LOCALAPPDATA", APP_DIR), "kocici-hlidac", "hlidac.log")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "KociciHlidac"

MENU = {
    "cs": ("Kočičí hlídač", "Vyzkoušet zámek", "Spouštět po přihlášení",
           "Otevřít nastavení", "Ukončit", "Hlídám klávesnici. Odemkneš napsáním: {}"),
    "en": ("Cat guard", "Test the lock", "Start at login",
           "Open settings", "Quit", "Guarding the keyboard. Type to unlock: {}"),
}

INI_TEMPLATE = {
    "cs": """[kocici]
# Jazyk: cs nebo en
lang = cs
# Odemykací slovo, jen písmena a–z
unlock = mnau
# Pozdrav na spořiči; prázdné = bez pozdravu
greeting = Ahoj kotě! :)
# Změny platí po restartu hlídače (ikona → Ukončit a znovu spustit).
""",
    "en": """[kocici]
# Language: cs or en
lang = en
# Unlock word, letters a-z only
unlock = meow
# Greeting on the screensaver; empty = no greeting
greeting = Hi kitty! :)
# Changes apply after restarting the guard (tray icon -> Quit, then start it again).
""",
}

_log_lock = threading.Lock()


def log(*a):
    line = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    with _log_lock:
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
    if sys.stdout:
        try:
            print(line, flush=True)
        except (OSError, UnicodeError):
            pass  # konzole bez UTF-8 nesmí shodit hook


# --- Win32 -----------------------------------------------------------------

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, w.WPARAM, w.LPARAM)
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

WH_KEYBOARD_LL = 13
WM_DESTROY, WM_CLOSE, WM_NULL = 0x0002, 0x0010, 0x0000
WM_KEYDOWN, WM_SYSKEYDOWN = 0x0100, 0x0104
WM_TIMER = 0x0113
WM_LBUTTONUP, WM_RBUTTONUP = 0x0202, 0x0205
WM_APP = 0x8000
WM_KOCKA = WM_APP + 1  # zamčeno: pusť držené klávesy, ukaž spořič
WM_TRAY = WM_APP + 2
LLKHF_INJECTED = 0x10
INPUT_KEYBOARD, KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 1, 0x1, 0x2
MAGIC = 0x6B6F6369  # dwExtraInfo našich vlastních kláves ("koci")
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
NIIF_INFO = 0x1
MF_STRING, MF_CHECKED, MF_SEPARATOR = 0x0, 0x8, 0x800
TPM_RETURNCMD, TPM_NONOTIFY = 0x100, 0x80
IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40
TIMER_TICK, TIMER_TEST = 1, 2
CMD_TEST, CMD_AUTOSTART, CMD_SETTINGS, CMD_QUIT = 1, 2, 3, 4

# Modifikátory se do detekce nepočítají: shift, ctrl, alt (obecné i L/R), win, capslock.
MODIFIERS = {0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C, 0x14}
EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E,
            0x5B, 0x5C, 0x6F, 0x90, 0xA3, 0xA5}
WIN_OR_ALT = {0x5B, 0x5C, 0xA4, 0xA5}
MOUSE_VK = {0x01, 0x02, 0x04, 0x05, 0x06}
GENERIC_MODS = {0x10, 0x11, 0x12}  # pouštíme jejich L/R varianty
VK_MASK = 0xE8  # nepřiřazená klávesa: aby puštěný Win neotevřel Start a Alt menu


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", w.DWORD), ("scanCode", w.DWORD), ("flags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("mouseData", w.DWORD),
                ("dwFlags", w.DWORD), ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("u", _INPUTUNION)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", w.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", w.HINSTANCE), ("hIcon", w.HICON),
                ("hCursor", w.HANDLE), ("hbrBackground", w.HANDLE),
                ("lpszMenuName", w.LPCWSTR), ("lpszClassName", w.LPCWSTR)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", w.DWORD), ("Data2", w.WORD), ("Data3", w.WORD), ("Data4", w.BYTE * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", w.UINT), ("uFlags", w.UINT),
                ("uCallbackMessage", w.UINT), ("hIcon", w.HICON), ("szTip", w.WCHAR * 128),
                ("dwState", w.DWORD), ("dwStateMask", w.DWORD), ("szInfo", w.WCHAR * 256),
                ("uVersion", w.UINT), ("szInfoTitle", w.WCHAR * 64), ("dwInfoFlags", w.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", w.HICON)]


def _sig(fn, res, *args):
    fn.restype = res
    fn.argtypes = list(args)


_sig(user32.SetWindowsHookExW, w.HHOOK, ctypes.c_int, HOOKPROC, w.HINSTANCE, w.DWORD)
_sig(user32.CallNextHookEx, LRESULT, w.HHOOK, ctypes.c_int, w.WPARAM, w.LPARAM)
_sig(user32.UnhookWindowsHookEx, w.BOOL, w.HHOOK)
_sig(user32.DefWindowProcW, LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
_sig(user32.RegisterClassW, w.ATOM, ctypes.POINTER(WNDCLASSW))
_sig(user32.CreateWindowExW, w.HWND, w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int,
     ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID)
_sig(user32.DestroyWindow, w.BOOL, w.HWND)
_sig(user32.GetMessageW, w.BOOL, ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT)
_sig(user32.TranslateMessage, w.BOOL, ctypes.POINTER(w.MSG))
_sig(user32.DispatchMessageW, LRESULT, ctypes.POINTER(w.MSG))
_sig(user32.PostMessageW, w.BOOL, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
_sig(user32.PostQuitMessage, None, ctypes.c_int)
_sig(user32.SetTimer, ctypes.c_size_t, w.HWND, ctypes.c_size_t, w.UINT, w.LPVOID)
_sig(user32.KillTimer, w.BOOL, w.HWND, ctypes.c_size_t)
_sig(user32.SendInput, w.UINT, w.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
_sig(user32.GetAsyncKeyState, w.SHORT, ctypes.c_int)
_sig(user32.RegisterWindowMessageW, w.UINT, w.LPCWSTR)
_sig(user32.CreatePopupMenu, w.HMENU)
_sig(user32.AppendMenuW, w.BOOL, w.HMENU, w.UINT, ctypes.c_size_t, w.LPCWSTR)
_sig(user32.TrackPopupMenu, ctypes.c_int, w.HMENU, w.UINT, ctypes.c_int, ctypes.c_int,
     ctypes.c_int, w.HWND, w.LPVOID)
_sig(user32.DestroyMenu, w.BOOL, w.HMENU)
_sig(user32.GetCursorPos, w.BOOL, ctypes.POINTER(w.POINT))
_sig(user32.SetForegroundWindow, w.BOOL, w.HWND)
_sig(user32.LoadImageW, w.HANDLE, w.HINSTANCE, w.LPCWSTR, w.UINT, ctypes.c_int, ctypes.c_int, w.UINT)
_sig(user32.LoadIconW, w.HICON, w.HINSTANCE, w.LPVOID)
_sig(user32.MessageBoxW, ctypes.c_int, w.HWND, w.LPCWSTR, w.LPCWSTR, w.UINT)
_sig(shell32.Shell_NotifyIconW, w.BOOL, w.DWORD, ctypes.POINTER(NOTIFYICONDATAW))
_sig(kernel32.GetModuleHandleW, w.HMODULE, w.LPCWSTR)
_sig(kernel32.GetCurrentThreadId, w.DWORD)
_sig(kernel32.CreateMutexW, w.HANDLE, w.LPVOID, w.BOOL, w.LPCWSTR)


def send_keys(events):
    """events: [(vk, down)], označené MAGIC, aby je vlastní hook pustil dál."""
    arr = (INPUT * len(events))()
    for i, (vk, down) in enumerate(events):
        flags = (0 if down else KEYEVENTF_KEYUP) | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED else 0)
        arr[i].type = INPUT_KEYBOARD
        arr[i].u.ki = KEYBDINPUT(vk, 0, flags, 0, MAGIC)
    user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))


# --- spouštění po přihlášení -------------------------------------------------

def autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = sys.executable
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return f'"{pythonw if os.path.exists(pythonw) else exe}" "{os.path.abspath(__file__)}"'


def installed():
    """Běží z instalátoru? Pak o autostartu rozhodl instalátor."""
    return os.path.exists(os.path.join(os.path.dirname(sys.executable), "unins000.exe"))


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
        return True
    except OSError:
        return False


def set_autostart(on):
    # CreateKeyEx: na čerstvém profilu klíč Run ještě nemusí existovat.
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


# --- hlídač (vlákno se smyčkou zpráv) ----------------------------------------

class Hlidac:
    def __init__(self, cfg, ui):
        self.cfg = cfg
        self.menu = MENU[cfg["lang"]]
        self.ui = ui
        self.det = kocici.Detektor(log if DEBUG else None)
        self.odem = kocici.Odemykani([ord(c.upper()) for c in cfg["unlock"]])
        self.locked = False
        self.hwnd = None
        self.ready = threading.Event()
        self.first_run = not os.path.exists(os.path.join(APP_DIR, ".spusteno"))

    # -- hook: musí být rychlý, těžší práci posílá oknu přes PostMessage --
    def hook(self, n, wparam, lparam):
        try:
            if n == 0:
                kb = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                injected = kb.flags & LLKHF_INJECTED
                ours = injected and kb.dwExtraInfo == MAGIC
                if not ours and (not injected or ACCEPT_INJECTED):
                    down = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    if self.on_key(kb.vkCode, down, time.monotonic()):
                        return 1
        except Exception as e:  # výjimka v hooku by klávesnici nezamkla, jen zalogujeme
            log("chyba v hooku:", repr(e))
        return user32.CallNextHookEx(None, n, wparam, lparam)

    def on_key(self, vk, down, now):
        """Vrátí True, když se má klávesa zahodit."""
        if self.locked:
            if down and vk not in MODIFIERS and self.odem.feed(vk):
                self.unlock()
            return True
        if vk in MODIFIERS:
            return False
        if not down:
            self.det.release(vk)
            return False
        reason = self.det.press(vk, now)
        if reason:
            return self.lock(reason)
        return False

    def lock(self, reason):
        if DEBUG:
            log("KOČKA (debug, nezamykám):", reason)
            self.det.reset(time.monotonic())
            return False
        log("KOČKA:", reason, "-> zamykám")
        self.locked = True
        self.odem.progress = 0
        self.det.reset()
        user32.PostMessageW(self.hwnd, WM_KOCKA, 0, 0)
        return True

    def unlock(self):
        log("odemčeno")
        self.locked = False
        self.det.reset(time.monotonic())
        self.ui.put("unlock")

    def release_held(self):
        # Klávesy, které kočka stiskla před zamčením, systém pořád drží; jejich
        # puštění už hook zahodí. Pošleme je za ně, jinak by visela autorepetice.
        held = [vk for vk in range(1, 255)
                if vk not in MOUSE_VK and vk not in GENERIC_MODS
                and user32.GetAsyncKeyState(vk) & 0x8000]
        if not held:
            return
        events = []
        if any(vk in WIN_OR_ALT for vk in held):
            events += [(VK_MASK, True), (VK_MASK, False)]
        events += [(vk, False) for vk in held]
        send_keys(events)

    # -- okno: časovač, ikona, menu --
    def wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TIMER and wparam == TIMER_TICK:
                if not self.locked:
                    reason = self.det.tick(time.monotonic())
                    if reason:
                        self.lock(reason)
                return 0
            if msg == WM_TIMER and wparam == TIMER_TEST:
                user32.KillTimer(hwnd, TIMER_TEST)
                self.lock("test")
                return 0
            if msg == WM_KOCKA:
                self.release_held()
                self.ui.put("lock")
                return 0
            if msg == WM_TRAY:
                if lparam in (WM_LBUTTONUP, WM_RBUTTONUP):
                    self.show_menu()
                return 0
            if msg == self.taskbar_created:
                self.tray(NIM_ADD)  # Explorer se restartoval
                return 0
            if msg == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
        except Exception as e:
            log("chyba v okně:", repr(e))
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def tray(self, action, info=None):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self.icon
        nid.szTip = self.menu[0]
        if info:
            nid.uFlags |= NIF_INFO
            nid.szInfoTitle = self.menu[0]
            nid.szInfo = info
            nid.dwInfoFlags = NIIF_INFO
        shell32.Shell_NotifyIconW(action, ctypes.byref(nid))

    def show_menu(self):
        _, test, auto, settings, quit_, _ = self.menu
        m = user32.CreatePopupMenu()
        user32.AppendMenuW(m, MF_STRING, CMD_TEST, test)
        user32.AppendMenuW(m, MF_STRING | (MF_CHECKED if autostart_enabled() else 0), CMD_AUTOSTART, auto)
        user32.AppendMenuW(m, MF_STRING, CMD_SETTINGS, settings)
        user32.AppendMenuW(m, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(m, MF_STRING, CMD_QUIT, quit_)
        pt = w.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(m, TPM_RETURNCMD | TPM_NONOTIFY, pt.x, pt.y, 0, self.hwnd, None)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(m)
        if cmd == CMD_TEST:
            self.lock("test z menu")
        elif cmd == CMD_AUTOSTART:
            set_autostart(not autostart_enabled())
        elif cmd == CMD_SETTINGS:
            open_settings(self.cfg["lang"])
        elif cmd == CMD_QUIT:
            self.quit()

    def quit(self):
        if self.locked:
            self.unlock()
        user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)

    def load_icon(self):
        path = os.path.join(HERE, "kocka.ico")
        if os.path.exists(path):
            h = user32.LoadImageW(None, path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if h:
                return h
        return user32.LoadIconW(None, ctypes.c_void_p(32512))  # IDI_APPLICATION

    def run(self):
        hinst = kernel32.GetModuleHandleW(None)
        self._wndproc = WNDPROC(self.wndproc)  # reference musí žít, jinak GC → pád
        wc = WNDCLASSW(lpfnWndProc=self._wndproc, hInstance=hinst, lpszClassName="KociciHlidac")
        user32.RegisterClassW(ctypes.byref(wc))
        self.taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
        self.hwnd = user32.CreateWindowExW(0, "KociciHlidac", self.menu[0], 0, 0, 0, 0, 0,
                                           None, None, hinst, None)
        self.icon = self.load_icon()
        self._hookproc = HOOKPROC(self.hook)
        hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hookproc, hinst, 0)
        if not hook:
            log("hook nejde nainstalovat, chyba", ctypes.get_last_error())
            self.ui.put("quit")
            self.ready.set()
            return
        user32.SetTimer(self.hwnd, TIMER_TICK, 250, None)
        if "--test" in sys.argv:
            user32.SetTimer(self.hwnd, TIMER_TEST, 3000, None)
        info = None
        if self.first_run:
            info = self.menu[5].format(self.cfg["unlock"])
            try:
                os.makedirs(APP_DIR, exist_ok=True)
                open(os.path.join(APP_DIR, ".spusteno"), "w").close()
                if getattr(sys, "frozen", False) and not ACCEPT_INJECTED and not installed():
                    set_autostart(True)
            except OSError as e:
                log("první spuštění:", e)
        self.tray(NIM_ADD, info)
        log("hlídám klávesnici, odemykací slovo:", self.cfg["unlock"])
        self.ready.set()

        msg = w.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        self.tray(NIM_DELETE)
        user32.UnhookWindowsHookEx(hook)
        log("konec")
        self.ui.put("quit")


def open_settings(lang):
    path = kocici.ini_path()
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(INI_TEMPLATE.get(lang, INI_TEMPLATE["en"]))
    os.startfile(path)


# --- spořič (Tk, hlavní vlákno) ----------------------------------------------

def dim(hexc, k=0.55):
    r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (int(r * k), int(g * k), int(b * k))


class Spanek:
    def __init__(self, cfg, ui, hlidac):
        self.cfg, self.ui, self.hlidac = cfg, ui, hlidac
        self.scena = kocici.Scena(cfg)
        self.shown = False
        self.start = 0.0
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(MENU[cfg["lang"]][0])
        self.root.configure(bg="black")
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)  # okno zavírá jen odemčení
        self.canvas = tk.Canvas(self.root, bg="black", bd=0, highlightthickness=0)
        try:
            self.canvas.configure(cursor="none")
        except tk.TclError:
            pass
        self.canvas.pack(fill="both", expand=True)
        families = set(tkfont.families())
        family = next((f for f in ("Cascadia Mono", "Consolas", "Courier New") if f in families), "Courier")
        px = max(14, self.root.winfo_screenheight() // 42)
        self.font = tkfont.Font(family=family, size=-px)
        self.bold = tkfont.Font(family=family, size=-px, weight="bold")
        self.cw = self.font.measure("M")
        self.ch = self.font.metrics("linespace")
        self.styles = {"": ("#000000", self.font)}
        for name, (_, hexc) in kocici.COLORS.items():
            self.styles[name] = (hexc, self.font)
            self.styles[name + "+bold"] = (hexc, self.bold)
            self.styles[name + "+dim"] = (dim(hexc), self.font)
        self.root.after(100, self.poll)

    def poll(self):
        try:
            while True:
                msg = self.ui.get_nowait()
                if msg == "lock":
                    self.show()
                elif msg == "unlock":
                    self.hide()
                elif msg == "quit":
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        if self.shown:
            self.draw()
        self.root.after(150 if self.shown else 100, self.poll)

    def show(self):
        if self.shown:
            return
        self.shown = True
        self.start = time.monotonic()
        self.root.deiconify()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()
        log("spořič ukázán")

    def hide(self):
        if not self.shown:
            return
        self.shown = False
        self.root.attributes("-fullscreen", False)
        self.root.withdraw()
        log("spořič schován")

    def draw(self):
        c = self.canvas
        cols = max(1, c.winfo_width() // self.cw)
        rows = max(1, c.winfo_height() // self.ch)
        grid, style = self.scena.frame(time.monotonic() - self.start, cols, rows,
                                       self.hlidac.odem.progress, self.cfg["unlock"])
        ox = (c.winfo_width() - cols * self.cw) // 2
        oy = (c.winfo_height() - rows * self.ch) // 2
        c.delete("all")
        for y, (line, st) in enumerate(zip(grid, style)):
            x = 0
            while x < cols:
                if line[x] == " ":
                    x += 1
                    continue
                # ASCII běh stejného stylu jedním kusem; ostatní znaky po jednom
                # na svou buňku, aby záložní font nerozhodil zarovnání.
                end = x + 1
                if line[x] < "\x80":
                    while end < cols and st[end] == st[x] and " " < line[end] < "\x80":
                        end += 1
                fill, font = self.styles[st[x]]
                c.create_text(ox + x * self.cw, oy + y * self.ch, text="".join(line[x:end]),
                              anchor="nw", fill=fill, font=font)
                x = end

    def run(self):
        self.root.mainloop()


def main():
    if "--autostart" in sys.argv or "--no-autostart" in sys.argv:
        set_autostart("--autostart" in sys.argv)
        return
    try:
        cfg = kocici.nastaveni()
    except ValueError as e:
        user32.MessageBoxW(None, f"{e}\n\n{kocici.ini_path()}", "kocici-hlidac", 0x10)
        return
    kernel32.CreateMutexW(None, False, "Local\\kocici-hlidac")  # handle drží zámek do konce procesu
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        open(LOG_PATH, "w").close()
    except OSError:
        pass

    ui = queue.Queue()
    hlidac = Hlidac(cfg, ui)
    spanek = Spanek(cfg, ui, hlidac)
    t = threading.Thread(target=hlidac.run, daemon=True)
    t.start()
    hlidac.ready.wait(10)
    try:
        spanek.run()
    finally:
        if hlidac.hwnd:
            user32.PostMessageW(hlidac.hwnd, WM_CLOSE, 0, 0)
        t.join(2)


if __name__ == "__main__":
    main()
