#!/bin/sh
# Kočičí hlídač pro Linux: nainstaluje se jen pro tebe a spustí se po přihlášení.
#   ./install.sh                 nainstalovat nebo aktualizovat
#   ./install.sh --uninstall     vypnout a smazat (nastavení zůstane)
# Root je potřeba jen jednou: přidat tě do skupiny `input` kvůli /dev/input.
set -eu

cd "$(dirname "$0")"
BIN="$HOME/.local/bin"  # cestu má pevně i kocici-hlidac.service
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE=kocici-hlidac
SKRIPTY="kocici-hlidac kocici-spanek"
MODULY="kocici.py telemetrie.py"
USER_NAME=$(id -un)

case "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" in
    cs*) CS=1 ;;
    *) CS= ;;
esac

# t "česky" "english"
t() { if [ -n "$CS" ]; then printf '%s\n' "$1"; else printf '%s\n' "$2"; fi; }
fail() { t "Chyba: $1" "Error: $2" >&2; exit 1; }

[ "$(id -u)" -ne 0 ] || fail "spusť mě bez sudo, instaluju se jen pro tebe." "run me without sudo, I install for your user only."
command -v systemctl >/dev/null || fail "chybí systemd (systemctl)." "systemd (systemctl) not found."

if [ "${1:-}" = "--uninstall" ]; then
    systemctl --user disable --now "$SERVICE" 2>/dev/null || true
    ! systemctl --user is-active --quiet "$SERVICE" ||
        fail "hlídač se nepodařilo zastavit, nic jsem nesmazal." "could not stop the guard, nothing was removed."
    for f in $SKRIPTY $MODULY; do rm -f "$BIN/$f"; done
    rm -f "$UNIT_DIR/$SERVICE.service"
    systemctl --user daemon-reload
    t "Kočičí hlídač je pryč. Nastavení zůstalo v ~/.config/kocici-hlidac." \
      "Cat guard removed. Settings are kept in ~/.config/kocici-hlidac."
    t "Ze skupiny input tě vyřadí: sudo gpasswd -d $USER_NAME input" \
      "To leave the input group: sudo gpasswd -d $USER_NAME input"
    exit 0
fi
[ $# -eq 0 ] || fail "neznámý přepínač $1 (umím jen --uninstall)." "unknown option $1 (only --uninstall)."

command -v python3 >/dev/null || fail "chybí python3." "python3 not found."
for f in $SKRIPTY $MODULY $SERVICE.service; do
    [ -f "$f" ] || fail "v balíčku chybí $f." "$f is missing from the package."
done

ma_skupinu() { id -nG "$@" | tr ' ' '\n' | grep -qx input; }

# Skupina dřív než soubory: když sudo selže, na disku se nic nezmění.
if ! ma_skupinu "$USER_NAME"; then
    t "Hlídač čte klávesnici z /dev/input, na to potřebuje skupinu input. Ptám se na heslo:" \
      "The guard reads the keyboard from /dev/input and needs the input group. Asking for your password:"
    sudo usermod -aG input "$USER_NAME" && ma_skupinu "$USER_NAME" ||
        fail "nepodařilo se tě přidat do skupiny input, nic jsem nenainstaloval." \
             "could not add you to the input group, nothing was installed."
fi

for f in $SKRIPTY; do install -Dm755 "$f" "$BIN/$f"; done
for f in $MODULY; do install -Dm644 "$f" "$BIN/$f"; done
install -Dm644 "$SERVICE.service" "$UNIT_DIR/$SERVICE.service"

systemctl --user daemon-reload
systemctl --user enable "$SERVICE"

systemctl --user is-active --quiet graphical-session.target ||
    t "Pozor: tvoje plocha nespouští graphical-session.target, takže hlídač po přihlášení sám nenaběhne. Pusť ho příkazem: systemctl --user start $SERVICE" \
      "Note: your desktop does not start graphical-session.target, so the guard will not start at login. Start it with: systemctl --user start $SERVICE"

if ma_skupinu; then
    systemctl --user restart "$SERVICE"
    t "Hotovo, hlídač běží. Zkus položit dlaň na klávesnici." \
      "Done, the guard is running. Try resting your palm on the keyboard."
else
    t "Hotovo. Odhlas se a přihlas znovu, pak hlídač naběhne sám." \
      "Done. Log out and back in; the guard then starts by itself."
fi

command -v foot >/dev/null || t "Bez terminálu foot se kočka neukáže, klávesnice se ale zamkne. Doinstaluj balíček foot." \
    "Without the foot terminal you will not see the cat, but the keyboard still locks. Install the foot package."
