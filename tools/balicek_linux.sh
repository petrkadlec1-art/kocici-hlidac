#!/bin/sh
# Zabalí linuxovou verzi do jednoho archivu: rozbalit a spustit ./install.sh.
#   sh tools/balicek_linux.sh [cíl.tar.gz]
set -eu

CIL=${1:-dist/kocici-hlidac-linux.tar.gz}
KOREN=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

mkdir "$TMP/kocici-hlidac"
for f in install.sh kocici-hlidac kocici-spanek kocici.py telemetrie.py \
         kocici-hlidac.service README.md LICENSE; do
    cp "$KOREN/$f" "$TMP/kocici-hlidac/"
done
chmod 755 "$TMP/kocici-hlidac/install.sh" "$TMP/kocici-hlidac/kocici-hlidac" \
          "$TMP/kocici-hlidac/kocici-spanek"

mkdir -p "$(dirname "$CIL")"
tar -czf "$CIL" -C "$TMP" kocici-hlidac
echo "$CIL"
