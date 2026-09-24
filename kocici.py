"""Společné jádro kočičího hlídače: detekce kočky, odemykání, nastavení a scéna.

Nezávisí na platformě. Linux (kocici-hlidac, kocici-spanek) i Windows
(kocici_windows.pyw) si sem posílají stisky a vykreslují hotovou mřížku znaků.
"""
import configparser
import os
import random
import sys

MANY_KEYS = 4
HOLD_SECONDS = 1.5
MASH_COUNT = 4
MASH_WINDOW = 2.0
COOLDOWN = 5.0


class Detektor:
    """Pozná kočku podle počtu a délky držených kláves (modifikátory sem neposílat)."""

    def __init__(self, log=None):
        self.down = {}  # kód klávesy -> čas stisku
        self.mash = []
        self.cooldown_until = 0.0
        self.log = log

    def press(self, code, now):
        """Vrátí důvod zamčení, nebo None. Autorepetici (už držená klávesa) ignoruje."""
        if code in self.down:
            return None
        self.down[code] = now
        if now < self.cooldown_until:
            return None
        if len(self.down) >= MANY_KEYS:
            return f"{len(self.down)} klávesy naráz"
        if len(self.down) >= 3:
            self.mash = [t for t in self.mash if now - t < MASH_WINDOW] + [now]
            if self.log:
                self.log(f"3+ naráz ({len(self.mash)}/{MASH_COUNT})")
            if len(self.mash) >= MASH_COUNT:
                return "dupání po klávesách"
        return None

    def release(self, code):
        self.down.pop(code, None)

    def tick(self, now):
        """Volat pravidelně (~4× za s): hlídá kočku, která si lehla."""
        if now < self.cooldown_until or len(self.down) < 2:
            return None
        second_oldest = sorted(self.down.values())[-2]
        if now - second_oldest >= HOLD_SECONDS:
            return f"{len(self.down)} klávesy držené {now - second_oldest:.1f} s"
        return None

    def reset(self, now=None):
        """Po zamčení/odemčení: zapomene držené klávesy, volitelně spustí cooldown."""
        self.down.clear()
        self.mash.clear()
        if now is not None:
            self.cooldown_until = now + COOLDOWN


class Odemykani:
    """Sleduje psaní odemykacího slova; kódy kláves dodá platforma."""

    def __init__(self, codes):
        self.codes = list(codes)
        self.progress = 0

    def feed(self, code):
        """Vrátí True, když je slovo celé napsané."""
        if code == self.codes[self.progress]:
            self.progress += 1
        else:
            self.progress = 1 if code == self.codes[0] else 0
        if self.progress == len(self.codes):
            self.progress = 0
            return True
        return False


# --- nastavení ------------------------------------------------------------

TEXTS = {
    "cs": {
        "locked": "Kočka spí. Klávesnice je zamčená.",
        "unlock": "Odemkneš napsáním:  ",
        "word": "mnau",
        "greeting": "Ahoj kotě! :)",
    },
    "en": {
        "locked": "The cat is asleep. Keyboard is locked.",
        "unlock": "Type to unlock:  ",
        "word": "meow",
        "greeting": "Hi kitty! :)",
    },
}


def system_lang():
    if sys.platform == "win32":
        import ctypes
        return "cs" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x05 else "en"
    return "cs" if os.environ.get("LANG", "").startswith("cs") else "en"


def ini_path():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, "kocici-hlidac", "nastaveni.ini")


def nastaveni():
    """Jazyk, odemykací slovo a pozdrav: výchozí < nastaveni.ini < proměnné KOCICI_*."""
    ini = configparser.ConfigParser()
    ini.read(ini_path(), encoding="utf-8")
    sec = ini["kocici"] if ini.has_section("kocici") else {}

    def get(key, env):
        if env in os.environ:
            return os.environ[env]
        return sec.get(key)

    lang = get("lang", "KOCICI_LANG") or system_lang()
    if lang not in TEXTS:
        lang = "en"
    texts = TEXTS[lang]
    word = (get("unlock", "KOCICI_UNLOCK") or texts["word"]).strip().lower()
    if not word or any(not "a" <= c <= "z" for c in word):
        raise ValueError(f"odemykací slovo smí obsahovat jen písmena a–z: {word!r}")
    greeting = get("greeting", "KOCICI_POZDRAV")
    if greeting is None:
        greeting = texts["greeting"]  # prázdný řetězec pozdrav schová
    return {"lang": lang, "unlock": word, "greeting": greeting, "texts": texts}


# --- scéna: kočka spí na klávesnici ----------------------------------------
# Kočka je klasické ASCII od Felixe Lee.

CAT_EXHALE = [
    r"      |\      _,,,---,,_",
    r"      /,`.-'`'    -.  ;-;;,_",
    r"     |,4-  ) )-,_. ,\ (  `'-'",
    r"    '---''(_/--'  `-'\_)",
]
CAT_INHALE = [
    r"      |\     _,,,----,,_",
    r"      /,`.-'`'     -.  ;-;;,_",
    r"     |,4-  ) )-,_. ,\ (  `'-'",
    r"    '---''(_/--'  `-'\_)",
]
KEYBOARDS = {
    "cs": [
        "╭──────────────────────────────────────╮",
        "│ ; ě š č ř ž ý á í é = ´  ⌫           │",
        "│ ⇥  q w e r t z u i o p ú )           │",
        "│ ⇪   a s d f g h j k l ů § ¨   ⏎      │",
        "│ ⇧  \\ y x c v b n m , . -  ⇧          │",
        "│ ctrl  ⌘  alt  ▁▁▁▁▁▁▁▁▁▁  alt  ctrl  │",
        "╰──────────────────────────────────────╯",
    ],
    "en": [
        "╭──────────────────────────────────────╮",
        "│ ` 1 2 3 4 5 6 7 8 9 0 - =  ⌫         │",
        "│ ⇥  q w e r t y u i o p [ ]           │",
        "│ ⇪   a s d f g h j k l ; ' \\   ⏎      │",
        "│ ⇧    z x c v b n m , . /   ⇧         │",
        "│ ctrl  ⌘  alt  ▁▁▁▁▁▁▁▁▁▁  alt  ctrl  │",
        "╰──────────────────────────────────────╯",
    ],
}

# Barvy jako jména; frontend si je přeloží (ANSI v terminálu, hex v Tk).
COLORS = {  # jméno -> (xterm-256, hex)
    "cat": (215, "#ffaf5f"),
    "zz": (117, "#87d7ff"),
    "kb": (244, "#808080"),
    "txt": (252, "#d0d0d0"),
    "ok": (150, "#afd787"),
    "star": (238, "#444444"),
}


class Scena:
    """Drží hvězdy a stoupající Zzz; frame() vrátí mřížku znaků a stylů.

    Styl buňky je "" nebo "barva" s volitelnou příponou "+bold" / "+dim".
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.keyboard = KEYBOARDS.get(cfg["lang"], KEYBOARDS["en"])
        self.size = None
        self.stars = []
        self.zs = []
        self.next_z = 0.0

    def frame(self, t, cols, rows, progress, word):
        if (cols, rows) != self.size:
            self.size = (cols, rows)
            self.stars = [(random.randrange(cols), random.randrange(rows), random.random() * 6)
                          for _ in range(cols * rows // 90)]
        if t >= self.next_z:
            self.zs = [z for z in self.zs if t - z[0] < 6] + [(t, random.uniform(-0.3, 0.3))]
            self.next_z = t + 1.6

        grid = [[" "] * cols for _ in range(rows)]
        style = [[""] * cols for _ in range(rows)]

        def put(y, x, s, c):
            if not 0 <= y < rows:
                return
            for i, ch in enumerate(s):
                if 0 <= x + i < cols and ch != " ":
                    grid[y][x + i] = ch
                    style[y][x + i] = c

        kb = self.keyboard
        texts = self.cfg["texts"]
        greeting = self.cfg["greeting"]
        cat = CAT_INHALE if (t % 4.0) < 2.0 else CAT_EXHALE
        block_h = len(cat) + len(kb) - 1 + 6
        top = max(4, (rows - block_h) // 2)
        kb_w = len(kb[0])
        kb_x = (cols - kb_w) // 2
        cat_x = kb_x + 4
        cat_y = top

        # Hvězdy jen mimo kočku, Zzz, klávesnici a text.
        y0, y1 = cat_y - 7, cat_y + block_h + 2
        x0, x1 = min(kb_x, (cols - 38) // 2) - 3, max(kb_x + kb_w, (cols + 38) // 2) + 3
        for sx, sy, phase in self.stars:
            if sy < rows and sx < cols and not (y0 <= sy <= y1 and x0 <= sx <= x1):
                tw = (t * 0.7 + phase) % 6
                put(sy, sx, "·" if tw < 5 else "✦", "star")

        for i, line in enumerate(cat):
            put(cat_y + i, cat_x, line, "cat")
        # Kočka leží na klávesnici: poslední řádek kočky překrývá horní hranu.
        kb_y = cat_y + len(cat) - 1
        for i, line in enumerate(kb):
            y = kb_y + i
            for j, ch in enumerate(line):
                x = kb_x + j
                if 0 <= y < rows and 0 <= x < cols and grid[y][x] == " " and ch != " ":
                    grid[y][x] = ch
                    style[y][x] = "kb"

        # Zzz stoupají od hlavy (vlevo nahoře).
        head_x, head_y = cat_x + 6, cat_y
        for born, drift in self.zs:
            age = t - born
            if 0 <= age < 6:
                ch = "z" if age < 2 else "Z"
                y = head_y - 1 - int(age * 0.9)
                x = head_x - 2 - int(age * 1.6) + int(drift * age)
                put(y, x, ch, "zz+bold" if age > 4 else "zz")

        msg_y = kb_y + len(kb) + 2
        if greeting:
            put(msg_y, (cols - len(greeting)) // 2, greeting, "cat+bold")
            msg_y += 2
        line1 = texts["locked"]
        put(msg_y, (cols - len(line1)) // 2, line1, "txt")
        typed = " ".join(word)
        label = texts["unlock"]
        x0 = (cols - len(label) - len(typed)) // 2
        put(msg_y + 2, x0, label, "txt+dim")
        for i, ch in enumerate(word):
            put(msg_y + 2, x0 + len(label) + 2 * i, ch, "ok+bold" if i < progress else "txt+dim")
        return grid, style
