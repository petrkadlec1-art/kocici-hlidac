# kocici-hlidac — cat-on-keyboard guard for Linux and Windows

*[Česky níže](#česky)*

A cat lies down on your keyboard. `kocici-hlidac` ("cat guard") notices,
blocks the keyboard so nothing reaches your apps, and shows a sleeping cat
until a human types the unlock word (`meow` by default).

```
                         |\     _,,,----,,_
                         /,`.-'`'     -.  ;-;;,_
                        |,4-  ) )-,_. ,\ (  `'-'
               ╭───────'---''(_/--'──`-'\_)───────────╮
               │ ⇥  q w e r t y u i o p [ ]           │
               ╰──────────────────────────────────────╯
                             Hi kitty! :)
                The cat is asleep. Keyboard is locked.
                       Type to unlock:  m e o w
```

## How it works

- Detects a cat, ignoring modifier keys (Ctrl, Shift, Alt, Win/Super, CapsLock):
  - 4 or more keys held at once,
  - 2 or more keys held together for 1.5 s (the cat lay down),
  - 4 presses within 2 s while 3+ keys were down (stomping).
- Blocks the keyboard. Keys the cat already pressed are released first, so no
  autorepeat gets stuck in your editor. The mouse keeps working.
- Unlocks when you type the unlock word.
- Python 3 standard library only. The detection is shared (`kocici.py`),
  each platform has its own input layer and screensaver.

| | Linux | Windows |
|---|---|---|
| Reads keys | `/dev/input` (evdev), Wayland and X11 | low-level keyboard hook |
| Blocks with | `EVIOCGRAB` | the hook swallows keys |
| Screensaver | [foot](https://codeberg.org/dnkl/foot) terminal | full-screen window |
| Runs as | systemd user service | tray icon, starts at login |

## Windows

Download `kocici-hlidac.exe` from
[Releases](https://github.com/petrkadlec1-art/kocici-hlidac/releases) and run it.
A sleeping-cat icon appears in the tray. On first start it turns on
*Start at login* and shows the unlock word in a notification.

Right-click the tray icon to **test the lock**, toggle **start at login**,
**open settings** or **quit**.

Notes:
- The `.exe` is not code-signed, so SmartScreen may warn you the first time
  (*More info → Run anyway*). You can also run the source directly:
  `pythonw kocici_windows.pyw`.
- Ctrl+Alt+Del always works; Windows does not let any program block it.
- The screensaver covers the main monitor.

## Linux

```bash
# 1. Access to /dev/input (log out and back in afterwards)
sudo usermod -aG input "$USER"

# 2. Scripts and the systemd user service
git clone https://github.com/petrkadlec1-art/kocici-hlidac.git
cd kocici-hlidac
install -Dm755 kocici-hlidac kocici-spanek -t ~/.local/bin/
install -Dm644 kocici.py -t ~/.local/bin/
install -Dm644 kocici-hlidac.service -t ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now kocici-hlidac

# 3. Try it
kocici-hlidac --debug   # logs detections, never locks (stop the service first)
kocici-hlidac --test    # locks after 3 s
```

Being in the `input` group means any program running as you can read raw
keystrokes. That is the usual trade-off for user-space key tools on Linux.

On [Omarchy](https://omarchy.org) the screensaver opens full-screen and keeps
Omarchy's own screensaver away; on other desktops add a window rule for app-id
`org.omarchy.screensaver` if you want it full-screen. Without foot the
keyboard still locks, you just see no cat.

On Linux the unlock word is matched by **physical key position on a US
layout**: on a QWERTZ keyboard `y` and `z` are swapped. Windows follows your
actual layout.

## Settings

Edit `nastaveni.ini` (Windows: tray icon → *Open settings*, i.e.
`%APPDATA%\kocici-hlidac\nastaveni.ini`; Linux: `~/.config/kocici-hlidac/nastaveni.ini`):

```ini
[kocici]
lang = en
unlock = meow
greeting = Hi kitty! :)
```

| Key | Environment variable | Meaning | Default |
|---|---|---|---|
| `lang` | `KOCICI_LANG` | `cs` or `en` | system language |
| `unlock` | `KOCICI_UNLOCK` | unlock word, letters a–z only | `mnau` / `meow` |
| `greeting` | `KOCICI_POZDRAV` | line above the text; empty hides it | `Ahoj kotě! :)` / `Hi kitty! :)` |

Environment variables win over the file. Restart the guard after a change.
Detection thresholds are constants at the top of `kocici.py`.

## Similar projects

- [PawSense](https://www.bitboost.com/pawsense/) — the original (Windows,
  commercial), Ig Nobel Prize 2000.
- [joeyvigil/pawsense](https://github.com/joeyvigil/pawsense) — Omarchy
  shell plugin with the same idea plus a deterrent sound.
- [TechPreacher/CatPaws](https://github.com/TechPreacher/CatPaws) — macOS
  menu bar app with automatic detection.
- [phoen-ix/pawse](https://github.com/phoen-ix/pawse),
  [timothywarner-org/pawgate](https://github.com/timothywarner-org/pawgate) —
  manual keyboard locks for Windows.

## Development

```bash
python3 -m unittest discover -s tests
```

GitHub Actions runs the tests on Linux and Windows, builds the `.exe` with
PyInstaller and runs `tests/smoke_windows.py` on a real Windows desktop:
it plays the cat with `SendInput` and checks the lock, the released keys,
the screensaver on a screenshot and unlocking. Tag `v*` to publish a release.

## Credits

The sleeping cat is the classic ASCII art by Felix Lee.

## License

MIT

---

## Česky

Kočka si lehne na klávesnici. `kocici-hlidac` to pozná, klávesnici zamkne,
takže do aplikací nic neprojde, a ukáže spící kočku, dokud člověk nenapíše
odemykací slovo (česky `mnau`).

**Windows:** stáhni `kocici-hlidac.exe` z
[Releases](https://github.com/petrkadlec1-art/kocici-hlidac/releases) a spusť.
V oznamovací oblasti se objeví spící kočka; pravým tlačítkem zámek vyzkoušíš,
vypneš spouštění po přihlášení, otevřeš nastavení nebo hlídače ukončíš.
Windows může poprvé varovat, že aplikace není podepsaná (*Další informace →
Přesto spustit*).

**Linux:** příkazy v sekci *Linux* výše.

**Nastavení** v `nastaveni.ini` (viz *Settings*): `lang = cs`,
`unlock = mnau`, `greeting = Ahoj kotě! :)`. Prázdný `greeting` pozdrav schová.

**Detekce** (modifikátory se nepočítají): 4+ klávesy naráz; 2+ klávesy držené
1,5 s; 4 stisky za 2 s, když byly dole 3+ klávesy.
