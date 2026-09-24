# kocici-hlidac — cat-on-keyboard guard for Linux

*[Česky níže](#česky)*

A cat lies down on your keyboard. `kocici-hlidac` ("cat guard") notices,
grabs the keyboard so nothing reaches your apps, and shows a sleeping cat
screensaver until a human types the unlock word (`meow` by default).

```
                         |\     _,,,----,,_
                         /,`.-'`'     -.  ;-;;,_
                        |,4-  ) )-,_. ,\ (  `'-'
               ╭───────'---''(_/--'──`-'\_)───────────╮
               │ ⇥  q w e r t y u i o p [ ]           │
               ╰──────────────────────────────────────╯
                The cat is asleep. Keyboard is locked.
                       Type to unlock:  m e o w
```

## How it works

- Reads keyboards straight from `/dev/input` (evdev), so it works on Wayland
  and X11 alike. Python 3 standard library only, no dependencies.
- Detects a cat, ignoring modifier keys (Ctrl, Shift, Alt, Super, CapsLock):
  - 4 or more keys held at once,
  - 2 or more keys held together for 1.5 s (the cat lay down),
  - 4 presses within 2 s while 3+ keys were down (stomping).
- Locks with `EVIOCGRAB`: the kernel sends key events only to the guard.
  Held keys are released first, so no autorepeat gets stuck in your editor.
- Unlocks when you type the unlock word. The mouse keeps working.
- Hot-plug: new keyboards are picked up every 5 s.

## Install

```bash
# 1. Access to /dev/input (log out and back in afterwards)
sudo usermod -aG input "$USER"

# 2. Scripts and the systemd user service
git clone https://github.com/petrkadlec1-art/kocici-hlidac.git
cd kocici-hlidac
install -Dm755 kocici-hlidac kocici-spanek -t ~/.local/bin/
install -Dm644 kocici-hlidac.service -t ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now kocici-hlidac

# 3. Try it
kocici-hlidac --debug   # logs detections, never locks (stop the service first)
kocici-hlidac --test    # locks after 3 s
```

Being in the `input` group means any program running as you can read raw
keystrokes. That is the usual trade-off for user-space key tools on Linux.

The screensaver runs in the [foot](https://codeberg.org/dnkl/foot) terminal.
On [Omarchy](https://omarchy.org) it opens full-screen and keeps Omarchy's own
screensaver away; on other desktops add a window rule for app-id
`org.omarchy.screensaver` if you want it full-screen. Without foot the
keyboard still locks, you just see no cat.

## Settings

Set them as environment variables, e.g. with `systemctl --user edit kocici-hlidac`:

```ini
[Service]
Environment=KOCICI_LANG=en
Environment=KOCICI_UNLOCK=meow
Environment="KOCICI_POZDRAV=Hi there :)"
```

| Variable | Meaning | Default |
|---|---|---|
| `KOCICI_LANG` | `cs` or `en` | `cs` if `LANG` starts with `cs`, else `en` |
| `KOCICI_UNLOCK` | unlock word, letters a–z only | `mnau` (cs) / `meow` (en) |
| `KOCICI_POZDRAV` | optional greeting shown above the text | none |

The unlock word is matched by **physical key position on a US layout**. On a
Czech/German QWERTZ keyboard the `y` and `z` keys are swapped, so avoid those
two letters or type them where the US layout has them.

Detection thresholds are constants at the top of `kocici-hlidac`.

## Similar projects

- [PawSense](https://www.bitboost.com/pawsense/) — the original (Windows,
  commercial), Ig Nobel Prize 2000.
- [joeyvigil/pawsense](https://github.com/joeyvigil/pawsense) — Omarchy
  shell plugin with the same idea plus a deterrent sound.
- [TechPreacher/CatPaws](https://github.com/TechPreacher/CatPaws) — macOS
  menu bar app with automatic detection.
- [dnewsholme/Keyboard-Locker](https://github.com/dnewsholme/Keyboard-Locker),
  [felfert/catlock](https://github.com/felfert/catlock) — manual keyboard
  locks for Linux.

## Credits

The sleeping cat is the classic ASCII art by Felix Lee.

## License

MIT

---

## Česky

Kočka si lehne na klávesnici. `kocici-hlidac` to pozná, klávesnici zamkne,
takže do aplikací nic neprojde, a ukáže spící kočku, dokud člověk nenapíše
odemykací slovo (česky výchozí `mnau`).

**Detekce** (modifikátory se nepočítají): 4+ klávesy naráz; 2+ klávesy držené
1,5 s; 4 stisky za 2 s, když byly dole 3+ klávesy. **Zámek** přes `EVIOCGRAB`,
myš funguje dál. Funguje na Waylandu i X11, jen Python 3 bez závislostí.

**Instalace:** stejné příkazy jako výše v sekci *Install*. Češtinu zapneš
`Environment=KOCICI_LANG=cs` (automaticky, když `LANG` začíná `cs`),
vlastní pozdrav `Environment="KOCICI_POZDRAV=Ahoj! :)"`.

Odemykací slovo se čte podle **fyzické pozice kláves v americkém rozložení**
— na české QWERTZ jsou prohozené `y` a `z`, proto je raději nepoužívej.
