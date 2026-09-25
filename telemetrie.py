"""Teploty, větráky, baterie a jas pro kocici-hlidac (Linux, jen /sys a /proc).

Každý údaj je nepovinný: co stroj nemá, zůstane v CSV prázdné.
"""
import glob
import os
import time

STATE = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
CSV_PATH = os.path.join(STATE, "kocici-hlidac", "telemetrie.csv")
CSV_MAX = 5 * 1024 * 1024
CLK_TCK = os.sysconf("SC_CLK_TCK")

COLUMNS = ["cas", "zamceno", "displej", "cpu_c", "gpu_c", "deska_c", "nvme_c",
           "vetraky_rpm", "gpu_w", "baterie_pct", "baterie_stav", "baterie_w",
           "jas_pct", "profil", "zatez_1min", "sporic_cpu_pct", "hlidac_cpu_pct"]


def _read(path, conv=str):
    try:
        with open(path) as f:
            return conv(f.read().strip())
    except (OSError, ValueError):
        return None


def _hwmon():
    """Jméno čidla -> adresář (k10temp, coretemp, amdgpu, acpitz, nvme, asus, …)."""
    found = {}
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        name = _read(d + "/name")
        if name and name not in found:
            found[name] = d
    return found


def _temp(d, label=None):
    if not d:
        return None
    for inp in sorted(glob.glob(d + "/temp*_input")):
        if label and _read(inp.replace("_input", "_label")) != label:
            continue
        v = _read(inp, int)
        if v is not None:
            return round(v / 1000, 1)
    return None


def _proc_ticks(pid):
    """CPU tiky procesu a všech jeho potomků (spořič = foot + python)."""
    total = 0
    stack = [pid]
    while stack:
        p = stack.pop()
        stat = _read(f"/proc/{p}/stat")
        if not stat:
            continue
        fields = stat.rsplit(")", 1)[1].split()
        total += int(fields[11]) + int(fields[12])  # utime + stime
        for kids in glob.glob(f"/proc/{p}/task/*/children"):
            stack += [int(k) for k in (_read(kids) or "").split()]
    return total


class Telemetrie:
    def __init__(self):
        self.prev = {}  # klíč -> (čas, tiky) pro výpočet CPU %

    def _cpu_pct(self, key, pid, now):
        if not pid:
            self.prev.pop(key, None)
            return None
        ticks = _proc_ticks(pid)
        last = self.prev.get(key)
        self.prev[key] = (now, ticks, pid)
        if not last or last[2] != pid or now <= last[0]:
            return None
        return round(100 * (ticks - last[1]) / CLK_TCK / (now - last[0]), 1)

    def sample(self, locked, screen_off, saver_pid):
        now = time.monotonic()
        hw = _hwmon()
        row = {
            "cas": time.strftime("%Y-%m-%d %H:%M:%S"),
            "zamceno": int(locked),
            "displej": "vyp" if screen_off else "zap",
            "cpu_c": _temp(hw.get("k10temp"), "Tctl") or _temp(hw.get("coretemp")),
            "gpu_c": _temp(hw.get("amdgpu"), "edge") or _temp(hw.get("amdgpu")),
            "deska_c": _temp(hw.get("acpitz")),
            "nvme_c": _temp(hw.get("nvme")),
        }
        fans = []
        for d in (hw.get("asus"), hw.get("acpi_fan")):
            for f in sorted(glob.glob(d + "/fan*_input")) if d else []:
                v = _read(f, int)
                if v is not None:
                    fans.append(str(v))
        row["vetraky_rpm"] = "/".join(fans) or None
        gpu = hw.get("amdgpu")
        if gpu:
            w = _read(gpu + "/power1_input", int) or _read(gpu + "/power1_average", int)
            row["gpu_w"] = round(w / 1e6, 1) if w is not None else None

        bat = next(iter(glob.glob("/sys/class/power_supply/BAT*")), None)
        if bat:
            row["baterie_pct"] = _read(bat + "/capacity", int)
            row["baterie_stav"] = _read(bat + "/status")
            p = _read(bat + "/power_now", int)
            if p is None:
                i, u = _read(bat + "/current_now", int), _read(bat + "/voltage_now", int)
                p = i * u / 1e6 if i is not None and u is not None else None
            row["baterie_w"] = round(p / 1e6, 1) if p is not None else None

        bl = next(iter(glob.glob("/sys/class/backlight/*")), None)
        if bl:
            cur, mx = _read(bl + "/brightness", int), _read(bl + "/max_brightness", int)
            if cur is not None and mx:
                row["jas_pct"] = round(100 * cur / mx)
        row["profil"] = _read("/sys/firmware/acpi/platform_profile")
        load = _read("/proc/loadavg")
        row["zatez_1min"] = load.split()[0] if load else None
        row["sporic_cpu_pct"] = self._cpu_pct("saver", saver_pid, now)
        row["hlidac_cpu_pct"] = self._cpu_pct("self", os.getpid(), now)
        return row

    @staticmethod
    def summary(row):
        """Krátký řádek do journalu."""
        parts = [f"CPU {row.get('cpu_c')} °C", f"GPU {row.get('gpu_c')} °C",
                 f"větráky {row.get('vetraky_rpm')}", f"baterie {row.get('baterie_pct')} % "
                 f"({row.get('baterie_stav')}, {row.get('baterie_w')} W)",
                 f"jas {row.get('jas_pct')} %", f"displej {row.get('displej')}",
                 f"profil {row.get('profil')}", f"spořič {row.get('sporic_cpu_pct')} % CPU"]
        return ", ".join(parts).replace("None", "–")

    @staticmethod
    def write(row, path=CSV_PATH):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if os.path.exists(path) and os.path.getsize(path) > CSV_MAX:
                os.replace(path, path + ".1")
            new = not os.path.exists(path)
            with open(path, "a", encoding="utf-8") as f:
                if new:
                    f.write(";".join(COLUMNS) + "\n")
                f.write(";".join("" if row.get(c) is None else str(row[c]) for c in COLUMNS) + "\n")
        except OSError:
            pass
