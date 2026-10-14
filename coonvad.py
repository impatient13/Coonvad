import json
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageTk

try:
    import pystray
except Exception:
    pystray = None
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "pystray", "-q"], timeout=180,
                       creationflags=0x08000000 if os.name == "nt" else 0)
        import pystray
    except Exception:
        pystray = None

_OrigBtn, _OrigEntry = ctk.CTkButton, ctk.CTkEntry


_LIGHT_BG = ("transparent", "#F7EEEF", "#FBF6F6", "#EBDADC", "#FFFFFF", "#E8D9DB", "#E7D6D8")


class _Btn(_OrigBtn):
    def __init__(self, *a, **k):
        k.setdefault("corner_radius", 10)
        k.setdefault("text_color", INK if k.get("fg_color") in _LIGHT_BG else "#FFFFFF")
        super().__init__(*a, **k)


class _Entry(_OrigEntry):
    def __init__(self, *a, **k):
        k.setdefault("corner_radius", 10)
        super().__init__(*a, **k)


ctk.CTkButton, ctk.CTkEntry = _Btn, _Entry

APP_NAME = "Coonvad VPN"
MAX_DEVICES = 5

BG = "#FFFFFF"
PANEL = "#F7EEEF"
PANEL_HOVER = "#EBDADC"
PANEL_ROW = "#FBF6F6"
DIVIDER = "#E8D9DB"
INK = "#2A1416"
GREEN = "#D52B1E"
GREEN_HOVER = "#B7241A"
GREEN_DARK = "#B7241A"
GREEN_DIS = "#D98F88"
HDR_OFF = "#8E241E"
RED = "#9E2018"
RED_DARK = "#701B16"
RED_HOVER = "#7F1A14"
RED_BTN = "#9E2018"
WHITE = "#FFFFFF"
WHITE60 = "#8A7174"
LAND = "#FFFFFF"
BORDER = "#E2CFD1"
CORNER_R = 14
MAP_SEA = "#F2E6E7"
ERR = "#C0281C"

RES_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
W, H = 320, 568
HEADER_H = 76
MAP_H = H - HEADER_H


def config_path():
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "Coonvad", "config.json")
    return os.path.join(os.path.expanduser("~"), ".config", "coonvad", "config.json")


def load_config():
    try:
        with open(config_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(cfg):
    try:
        p = config_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
    except Exception:
        pass


CFG = load_config()


AUTOSTART_NAME = "Coonvad"
BACKGROUND = "--background" in sys.argv


def _autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --background'
    exe = sys.executable
    if os.name == "nt" and exe.lower().endswith("python.exe"):
        exe = exe[:-10] + "pythonw.exe"
    return f'"{exe}" "{os.path.abspath(__file__)}" --background'


def autostart_enabled():
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
            winreg.QueryValueEx(k, AUTOSTART_NAME)
            return True
    except Exception:
        return False


def set_autostart(enabled):
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, AUTOSTART_NAME, 0, winreg.REG_SZ, _autostart_command())
            else:
                try:
                    winreg.DeleteValue(k, AUTOSTART_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


def first_run_autostart():
    if CFG.get("autostart_done"):
        if CFG.get("autostart", True) and autostart_enabled():
            set_autostart(True)
        return
    CFG["autostart_done"] = True
    CFG["autostart"] = bool(set_autostart(True))
    save_config(CFG)


def load_private_fonts():
    d = os.path.join(RES_DIR, "fonts")
    if os.name != "nt" or not os.path.isdir(d):
        return
    try:
        import ctypes
        for fn in os.listdir(d):
            if fn.lower().endswith((".ttf", ".otf")):
                ctypes.windll.gdi32.AddFontResourceExW(os.path.join(d, fn), 0x10, 0)
    except Exception:
        pass


load_private_fonts()
if os.name == "nt":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("xera.coonvad.vpn")
    except Exception:
        pass

FONT_REG = "Segoe UI"
FONT_SB = "Segoe UI"
FONT_SB_BOLD = True


def resolve_fonts():
    global FONT_REG, FONT_SB, FONT_SB_BOLD
    fams = {f.lower(): f for f in tkfont.families()}
    if "open sans" in fams:
        FONT_REG = fams["open sans"]
        if "open sans semibold" in fams:
            FONT_SB, FONT_SB_BOLD = fams["open sans semibold"], False
        else:
            FONT_SB, FONT_SB_BOLD = FONT_REG, True
    else:
        FONT_REG = FONT_SB = "Segoe UI" if os.name == "nt" else "Helvetica"
        FONT_SB_BOLD = True


def fnt(size, sb=True):
    if sb:
        return ctk.CTkFont(family=FONT_SB, size=size, weight="bold" if FONT_SB_BOLD else "normal")
    return ctk.CTkFont(family=FONT_REG, size=size, weight="normal")


def pil_font(size, sb=True):
    name = "OpenSans-SemiBold.ttf" if sb else "OpenSans-Regular.ttf"
    for p in (os.path.join(RES_DIR, "fonts", name),
              r"C:\Windows\Fonts\segoeuib.ttf" if sb else r"C:\Windows\Fonts\segoeui.ttf",
              "DejaVuSans-Bold.ttf" if sb else "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def find_cli():
    custom = CFG.get("cli_path")
    if custom and os.path.exists(custom):
        return custom
    found = shutil.which("mullvad")
    if found:
        return found
    pf = [os.environ.get("ProgramFiles", r"C:\Program Files"),
          os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
    cands = [os.path.join(p, "Mullvad VPN", "resources", "mullvad.exe") for p in pf]
    cands += ["/usr/bin/mullvad", "/usr/local/bin/mullvad",
              "/Applications/Mullvad VPN.app/Contents/Resources/mullvad"]
    for p in cands:
        if os.path.exists(p):
            return p
    return None


CLI = find_cli()


def cli(*args, timeout=25):
    if not CLI:
        return 127, "Mullvad CLI not found."
    try:
        r = subprocess.run(
            [CLI, *args], capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace", creationflags=CREATE_NO_WINDOW,
        )
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return 124, "La commande a expiré."
    except Exception as exc:
        return 1, str(exc)


def cli_first_ok(*variants, timeout=25):
    last = (1, "")
    for v in variants:
        last = cli(*v, timeout=timeout)
        if last[0] == 0:
            return last
    return last


FR_COUNTRIES = {
    "Albania": "Albanie", "Argentina": "Argentine", "Australia": "Australie", "Austria": "Autriche",
    "Belgium": "Belgique", "Bosnia and Herzegovina": "Bosnie-Herzégovine", "Brazil": "Brésil",
    "Bulgaria": "Bulgarie", "Canada": "Canada", "Chile": "Chili", "China": "Chine",
    "Colombia": "Colombie", "Croatia": "Croatie", "Cyprus": "Chypre", "Czech Republic": "Tchéquie",
    "Czechia": "Tchéquie", "Denmark": "Danemark", "Egypt": "Égypte", "Estonia": "Estonie",
    "Finland": "Finlande", "France": "France", "Georgia": "Géorgie", "Germany": "Allemagne",
    "Greece": "Grèce", "Hong Kong": "Hong Kong", "Hungary": "Hongrie", "Iceland": "Islande",
    "India": "Inde", "Indonesia": "Indonésie", "Ireland": "Irlande", "Israel": "Israël",
    "Italy": "Italie", "Japan": "Japon", "Kenya": "Kenya", "Latvia": "Lettonie",
    "Lithuania": "Lituanie", "Luxembourg": "Luxembourg", "Malaysia": "Malaisie", "Malta": "Malte",
    "Mexico": "Mexique", "Moldova": "Moldavie", "Montenegro": "Monténégro", "Morocco": "Maroc",
    "Netherlands": "Pays-Bas", "New Zealand": "Nouvelle-Zélande", "Nigeria": "Nigéria",
    "North Macedonia": "Macédoine du Nord", "Norway": "Norvège", "Peru": "Pérou",
    "Philippines": "Philippines", "Poland": "Pologne", "Portugal": "Portugal", "Romania": "Roumanie",
    "Russia": "Russie", "Serbia": "Serbie", "Singapore": "Singapour", "Slovakia": "Slovaquie",
    "Slovenia": "Slovénie", "South Africa": "Afrique du Sud", "South Korea": "Corée du Sud",
    "Spain": "Espagne", "Sweden": "Suède", "Switzerland": "Suisse", "Taiwan": "Taïwan",
    "Thailand": "Thaïlande", "Turkey": "Turquie", "UK": "Royaume-Uni",
    "United Kingdom": "Royaume-Uni", "Ukraine": "Ukraine", "United Arab Emirates": "Émirats arabes unis",
    "UAE": "Émirats arabes unis", "USA": "États-Unis", "United States": "États-Unis",
    "United States of America": "États-Unis", "Uruguay": "Uruguay", "Vietnam": "Vietnam",
}
GEO_ALIASES = {
    "USA": "United States of America", "United States": "United States of America",
    "UK": "United Kingdom", "Czechia": "Czech Republic", "Serbia": "Republic of Serbia",
    "North Macedonia": "Macedonia", "UAE": "United Arab Emirates", "Tanzania": "United Republic of Tanzania",
}
MONTHS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def fr_country(name):
    return FR_COUNTRIES.get(name, name)


def fmt_paid_until(dt):
    return f"{dt.day} {MONTHS_FR[dt.month - 1]} {dt.year}, {dt:%H:%M}"


def fmt_time_left(dt):
    secs = (dt - datetime.now()).total_seconds()
    if secs <= 0:
        return "expiré"
    days = int(secs // 86400)
    if days >= 1:
        return f"{days} jour{'s' if days > 1 else ''}"
    hours = int(secs // 3600)
    if hours >= 1:
        return f"{hours} heure{'s' if hours > 1 else ''}"
    mins = max(1, int(secs // 60))
    return f"{mins} minute{'s' if mins > 1 else ''}"


def fmt_account(d):
    d = re.sub(r"\D", "", d or "")
    return " ".join(d[i:i + 4] for i in range(0, len(d), 4))


def translate_error(out):
    low = (out or "").lower()
    table = (
        ("account does not exist", "Numéro de compte incorrect. Vérifiez-le et réessayez."),
        ("invalid account", "Numéro de compte incorrect. Vérifiez-le et réessayez."),
        ("too many devices", "Il y a trop d'appareils sur le compte."),
        ("voucher code is invalid", "Ce code de bon est invalide."),
        ("already been used", "Ce code de bon a déjà été utilisé."),
        ("no such device", "Cet appareil n'existe pas (ou plus)."),
        ("timed out", "Délai dépassé. Vérifiez votre connexion et réessayez."),
        ("failed to connect to daemon", "Le service Mullvad ne répond pas. Lancez l'application Mullvad VPN."),
        ("management rpc", "Le service Mullvad ne répond pas. Lancez l'application Mullvad VPN."),
        ("out of time", "Votre compte n'a plus de temps. Ajoutez du temps dans « Compte »."),
        ("expired", "Votre compte a expiré. Ajoutez du temps dans « Compte »."),
    )
    for key, fr in table:
        if key in low:
            return fr
    return out or "Une erreur est survenue."


def parse_status(out):
    first = out.strip().splitlines()[0].lower() if out.strip() else ""
    state = "disconnected"
    err = ""
    if first.startswith("connected"):
        state = "connected"
    elif first.startswith("connecting"):
        state = "connecting"
    elif first.startswith("disconnecting"):
        state = "disconnecting"
    elif first.startswith("blocked") or first.startswith("error"):
        state, err = "error", out.strip().splitlines()[0]
    host = country = city = ip = ""
    m = re.search(r"Relay:\s*(\S+)", out)
    if m:
        host = m.group(1)
    m = re.search(r"Visible location:\s*(.+)", out)
    if m:
        s = re.split(r"\.\s*IPv[46]:|,\s*IPv6:", m.group(1).strip())[0]
        parts = [p.strip() for p in s.split(",")]
        country = parts[0] if parts else ""
        city = parts[1] if len(parts) > 1 else ""
    m = re.search(r"IPv4:\s*([\d.]+)", out)
    if m:
        ip = m.group(1)
    return {"state": state, "host": host, "country": country, "city": city, "ip": ip, "error": err}


def parse_relays(out):
    countries = []
    for line in out.splitlines():
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            m = re.match(r"(.+?)\s*\((\w+)\)\s*$", line)
            if m:
                countries.append({"name": m.group(1), "code": m.group(2), "cities": []})
        elif re.match(r"^(\t| {1,6})\S", line) and not re.match(r"^(\t\t| {7,})", line):
            m = re.match(r"^\s+(.+?)\s*\((\w+)\)(?:\s*@\s*(-?[\d.]+)°N,\s*(-?[\d.]+)°[WE])?", line)
            if m and countries:
                lat = float(m.group(3)) if m.group(3) else None
                lon = float(m.group(4)) if m.group(4) else None
                countries[-1]["cities"].append(
                    {"name": m.group(1), "code": m.group(2), "lat": lat, "lon": lon})
    return countries


def parse_constraint(text):
    t = (text or "").strip().lower()
    m = re.search(r"city\s+(\w+),\s*(\w+)", t)
    if m:
        return m.group(2), m.group(1)
    m = re.search(r"country\s+(\w+)", t)
    if m:
        return m.group(1), None
    return None, None


def parse_account(out):
    low = out.lower()
    if "not logged in" in low:
        return {"state": "out"}
    num = re.search(r"Mullvad account:\s*(\d+)", out)
    if "revoked" in low:
        return {"state": "revoked", "number": num.group(1) if num else ""}
    if not num:
        return {"state": "error", "error": out}
    exp = None
    m = re.search(r"Expires at:\s*(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})", out)
    if m:
        exp = datetime(*(int(x) for x in m.groups()))
    dev = re.search(r"Device name:\s*(.+)", out)
    return {"state": "ok", "number": num.group(1), "expiry": exp,
            "device": dev.group(1).strip() if dev else ""}


def parse_devices(out):
    res = []
    for ln in out.splitlines():
        s = ln.strip()
        if not s or s.lower().startswith("devices on the account"):
            continue
        if s not in res:
            res.append(s)
    return res


def is_on(out):
    return bool(re.search(r"\b(on|always|allow|yes|true)\b", out.lower().split(":")[-1]))


def _draw(size, fn, scale=4):
    im = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    fn(ImageDraw.Draw(im), size * scale)
    return im.resize((size, size), Image.LANCZOS)


def icon_gear(size=44, color=WHITE):
    def f(d, s):
        c = s / 2
        for i in range(8):
            a = math.radians(i * 45)
            w = s * 0.085
            pts = []
            for r, off in ((s * 0.30, -w), (s * 0.46, -w), (s * 0.46, w), (s * 0.30, w)):
                pts.append((c + r * math.cos(a) - off * math.sin(a), c + r * math.sin(a) + off * math.cos(a)))
            d.polygon(pts, fill=color)
        d.ellipse([c - s * .36, c - s * .36, c + s * .36, c + s * .36], fill=color)
        d.ellipse([c - s * .15, c - s * .15, c + s * .15, c + s * .15], fill=(0, 0, 0, 0))
    return _draw(size, f)


def icon_user(size=44, color=WHITE):
    def f(d, s):
        d.ellipse([s * .04, s * .04, s * .96, s * .96], fill=color)
        d.ellipse([s * .37, s * .22, s * .63, s * .48], fill=(0, 0, 0, 0))
        d.pieslice([s * .27, s * .52, s * .73, s * .98], 180, 360, fill=(0, 0, 0, 0))
    return _draw(size, f)


def icon_chevron(size=32, color=WHITE, direction="right"):
    def f(d, s):
        d.line([(s * .36, s * .2), (s * .66, s * .5), (s * .36, s * .8)],
               fill=color, width=max(2, int(s * .1)), joint="curve")
    im = _draw(size, f)
    angle = {"right": 0, "down": -90, "left": 180, "up": 90}[direction]
    return im.rotate(angle) if angle else im


def icon_back(size=48):
    def f(d, s):
        d.ellipse([0, 0, s - 1, s - 1], fill=GREEN)
        d.line([(s * .3, s * .42), (s * .5, s * .62), (s * .7, s * .42)],
               fill="#FFFFFF", width=max(3, int(s * .09)), joint="curve")
    return _draw(size, f)


def icon_close(size=32, color=WHITE):
    def f(d, s):
        w = max(2, int(s * .1))
        d.line([(s * .25, s * .25), (s * .75, s * .75)], fill=color, width=w)
        d.line([(s * .75, s * .25), (s * .25, s * .75)], fill=color, width=w)
    return _draw(size, f)


def icon_eye(size=36, color=WHITE, slashed=False):
    def f(d, s):
        d.ellipse([s * .08, s * .28, s * .92, s * .72], outline=color, width=max(2, int(s * .07)))
        d.ellipse([s * .38, s * .38, s * .62, s * .62], fill=color)
        if slashed:
            d.line([(s * .15, s * .85), (s * .85, s * .15)], fill=color, width=max(2, int(s * .08)))
    return _draw(size, f)


def icon_copy(size=36, color=WHITE):
    def f(d, s):
        w = max(2, int(s * .07))
        d.rounded_rectangle([s * .30, s * .10, s * .82, s * .70], radius=s * .06, outline=color, width=w)
        d.rounded_rectangle([s * .16, s * .28, s * .68, s * .90], radius=s * .06, outline=color,
                            width=w, fill=BG)
    return _draw(size, f)


def icon_external(size=36, color=WHITE):
    def f(d, s):
        w = max(2, int(s * .08))
        d.line([(s * .52, s * .22), (s * .22, s * .22), (s * .22, s * .80), (s * .80, s * .80),
                (s * .80, s * .50)], fill=color, width=w)
        d.line([(s * .48, s * .52), (s * .84, s * .16)], fill=color, width=w)
        d.line([(s * .58, s * .16), (s * .84, s * .16), (s * .84, s * .42)], fill=color, width=w)
    return _draw(size, f)


def icon_minus(size=32, color=(255, 255, 255, 210)):
    def f(d, s):
        d.line([(s * .22, s * .5), (s * .78, s * .5)], fill=color, width=max(2, int(s * .09)))
    return _draw(size, f)


MAPLE_LEAF = [
    (50,  2),
    (43, 22), (26, 17), (36, 33),
    ( 2, 42), (20, 48),
    (10, 62), (30, 58),
    (32, 75), (50, 62),
    (50, 98),
    (50, 62), (68, 75),
    (70, 58), (90, 62),
    (80, 48), (98, 42),
    (64, 33), (74, 17), (57, 22),
]


def leaf_pts(cx, cy, size):
    k = size / 100.0
    return [(cx + (x - 50) * k, cy + (y - 50) * k) for x, y in MAPLE_LEAF]


def icon_check(size=32, color=WHITE):
    def f(d, s):
        d.line([(s * .2, s * .55), (s * .42, s * .76), (s * .8, s * .28)],
               fill=color, width=max(3, int(s * .11)), joint="curve")
    return _draw(size, f)


def ctk_img(im, size=None):
    return ctk.CTkImage(light_image=im, dark_image=im, size=size or im.size)


def logo_candidates():
    import glob
    names = ["coonvad_logo.png", "coonvad_logo.jpg", "coonvad_logo.jpeg", "logo.png", "logo.jpg"]
    paths = [os.path.join(d, n) for d in (RES_DIR, os.getcwd()) for n in names]
    for d in (RES_DIR, os.getcwd()):
        for pat in ("*logo*.png", "*logo*.jpg", "*logo*.jpeg", "*logo*.webp", "*logo*.ico"):
            paths += glob.glob(os.path.join(d, pat))
    return paths


def load_logo():
    for p in logo_candidates():
        if os.path.exists(p):
            try:
                im = Image.open(p).convert("RGBA")
                side = min(im.size)
                left, top = (im.width - side) // 2, (im.height - side) // 2
                return im.crop((left, top, left + side, top + side))
            except Exception:
                pass
    im = Image.new("RGBA", (256, 256), BG)
    d = ImageDraw.Draw(im)
    d.pieslice([40, 30, 216, 200], 180, 360, fill="#F9CB1C")
    d.ellipse([90, 120, 170, 200], fill="#8F8F8F")
    return im


def circle(im, size):
    im = im.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size * 4 - 1, size * 4 - 1], fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def tray_image(logo, state):
    base = circle(logo, 64)
    color = {"connected": "#22A822", "connecting": "#F9CB1C", "disconnecting": "#F9CB1C"}.get(state, RED)
    d = ImageDraw.Draw(base)
    d.ellipse([38, 38, 62, 62], fill=color, outline=BG, width=3)
    return base


class WorldMap:

    def __init__(self, path):
        self.polys = []
        self.by_name = {}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for ft in data.get("features", []):
                name = (ft.get("properties") or {}).get("name", "")
                geom = ft.get("geometry") or {}
                polys = geom.get("coordinates", [])
                if geom.get("type") == "Polygon":
                    polys = [polys]
                for poly in polys:
                    if not poly:
                        continue
                    ring = [(p[0], p[1]) for p in poly[0]]
                    lons, lats = [p[0] for p in ring], [p[1] for p in ring]
                    bbox = (min(lons), min(lats), max(lons), max(lats))
                    self.polys.append((name, ring, bbox))
                    cur = self.by_name.get(name)
                    area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                    if not cur or area > cur[0]:
                        self.by_name[name] = (area, ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2))
        except Exception:
            self.polys = []

    @property
    def ok(self):
        return bool(self.polys)

    def center_of(self, country):
        name = GEO_ALIASES.get(country, country)
        hit = self.by_name.get(name)
        if hit:
            lon, lat = hit[1]
            return lat, lon
        return None

    def render(self, lat, lon, w, h, py, scale=2, px_per_deg=12.5):
        s = scale
        im = Image.new("RGB", (w * s, h * s), MAP_SEA)
        if self.polys:
            d = ImageDraw.Draw(im)
            k = px_per_deg * s
            cx, cy = w * s / 2, py * s
            c = max(0.35, math.cos(math.radians(lat)))
            for _name, ring, bb in self.polys:
                if abs(((bb[0] + bb[2]) / 2 - lon + 180) % 360 - 180) > 60 + (bb[2] - bb[0]) / 2:
                    continue
                pts = []
                for lo, la in ring:
                    dl = ((lo - lon + 180) % 360) - 180
                    pts.append((cx + dl * k * c, cy - (la - lat) * k))
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                if max(xs) < 0 or min(xs) > w * s or max(ys) < 0 or min(ys) > h * s:
                    continue
                if len(pts) > 2:
                    d.polygon(pts, fill=LAND, outline=BORDER)
        return im


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        if BACKGROUND:
            self.withdraw()
        ctk.set_appearance_mode("light")
        resolve_fonts()
        self.title(APP_NAME)
        self.overrideredirect(True)
        try:
            sc = self._get_window_scaling()
        except Exception:
            sc = 1.0
        margin = 16
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x0 = max(0, sw - int(W * sc) - margin)
        y0 = max(0, sh - int(H * sc) - margin - 40)
        self.geometry(f"{W}x{H}+{x0}+{y0}")
        self._drag = None
        self._hidden_at = 0.0
        self._armed = False
        self._no_autohide = False
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self.q = queue.Queue()
        self.running = True
        self.view = ""
        self.tray = None
        self.vpn = {"state": "disconnected", "host": "", "country": "", "city": "", "ip": "", "error": ""}
        self.daemon_err = ""
        self.cmd_err = ""
        self.acct = {"number": "", "expiry": None, "device": ""}
        self.opts = {}
        self.countries = []
        self.sel_label = ""
        self.sel_codes = (None, None)
        self.entry_label = ""
        self.cli_version = ""
        self.loc_target = "exit"
        self._base_key = None
        self._base_img = None
        self._map_key = None
        self._map_ctk = None
        self.world = WorldMap(os.path.join(RES_DIR, "world.geo.json"))

        self.logo = load_logo()
        self.logo_hdr = ctk_img(circle(self.logo, 80), (38, 38))
        self.ic_gear = ctk_img(icon_gear(48, (255, 255, 255, 150)), (26, 26))
        self.ic_user = ctk_img(icon_user(48, (255, 255, 255, 150)), (26, 26))
        self.ic_right = ctk_img(icon_chevron(32, INK, "right"), (14, 14))
        self.ic_down = ctk_img(icon_chevron(32, INK, "down"), (14, 14))
        self.ic_back = ctk_img(icon_back(56), (28, 28))
        self.ic_close = ctk_img(icon_close(32, WHITE60), (14, 14))
        self.ic_eye = ctk_img(icon_eye(36, INK), (20, 20))
        self.ic_eye_off = ctk_img(icon_eye(36, INK, True), (20, 20))
        self.ic_copy = ctk_img(icon_copy(36, INK), (20, 20))
        self.ic_ext = ctk_img(icon_external(36), (16, 16))
        self.ic_check = ctk_img(icon_check(32), (16, 16))

        self._ico_path = None
        try:
            self._tkicon = ImageTk.PhotoImage(circle(self.logo, 64))
            base = os.path.join(os.environ.get("TEMP") or os.path.expanduser("~"), "coonvad_icon.ico")
            big = circle(self.logo, 256)
            big.save(base, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
            self._ico_path = base
        except Exception:
            pass
        for delay in (200, 400, 900):
            self.after(delay, self._set_icon)

        self.box = ctk.CTkFrame(self, fg_color=BG, corner_radius=0, width=W, height=H)
        self.box.pack(fill="both", expand=True)

        self.bind_all("<ButtonPress-1>", self._drag_start, add="+")
        self.bind_all("<B1-Motion>", self._drag_move, add="+")
        self.bind("<Map>", self._on_map, add="+")
        self.bind("<FocusIn>", self._on_focus_in, add="+")
        self.bind("<FocusOut>", self._on_focus_out, add="+")
        self.after(30, self._fix_taskbar)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(50, self._drain)
        self.start_tray()
        if not CLI:
            self.show("nocli")
            return
        threading.Thread(target=self._poll_loop, daemon=True).start()
        self.bg(lambda: cli("--version"), self._got_version)
        self.bg(lambda: cli("relay", "list", timeout=40), self._got_relays_bg)
        self.bg(lambda: cli("account", "get"), self._startup)

    def _fix_taskbar(self):
        if os.name != "nt":
            return
        try:
            import ctypes
            u = ctypes.windll.user32
            hwnd = u.GetParent(self.winfo_id()) or self.winfo_id()
            st = u.GetWindowLongW(hwnd, -20)
            if self.tray:
                st = (st | 0x80) & ~0x40000
            else:
                st = (st & ~0x80) | 0x40000
            u.SetWindowLongW(hwnd, -20, st)
            self.withdraw()
            if not (BACKGROUND and self.tray):
                self.after(20, self.deiconify)
            self.after(120, self._round_corners)
        except Exception:
            pass

    def _round_corners(self):
        if os.name != "nt":
            return
        try:
            import ctypes
            u = ctypes.windll.user32
            g = ctypes.windll.gdi32
            hwnd = u.GetParent(self.winfo_id()) or self.winfo_id()
            self.update_idletasks()
            sc = self._get_window_scaling()
            w, h, r = self.winfo_width(), self.winfo_height(), int(CORNER_R * sc * 2)
            rgn = g.CreateRoundRectRgn(0, 0, w + 1, h + 1, r, r)
            u.SetWindowRgn(hwnd, rgn, True)
        except Exception:
            pass

    def minimize(self):
        if self.tray:
            self.hide_window()
            return
        if os.name == "nt":
            self.overrideredirect(False)
        self.iconify()

    def _on_map(self, e):
        if e.widget is self and os.name == "nt" and not self.overrideredirect():
            self.after(30, lambda: (self.overrideredirect(True), self._fix_taskbar(), self.after(150, self._round_corners)))

    def _drag_start(self, e):
        try:
            sc = self._get_window_scaling()
            ry = e.y_root - self.winfo_rooty()
            inzone = 0 <= ry < HEADER_H * sc and not isinstance(e.widget, (tk.Entry, tk.Text))
        except Exception:
            inzone = False
        self._drag = (e.x_root, e.y_root, self.winfo_x(), self.winfo_y()) if inzone else None

    def _drag_move(self, e):
        if self._drag:
            x, y, wx, wy = self._drag
            tk.Wm.geometry(self, f"+{wx + e.x_root - x}+{wy + e.y_root - y}")

    def _set_icon(self):
        try:
            if self._ico_path and os.name == "nt":
                self.iconbitmap(self._ico_path)
            self.iconphoto(True, self._tkicon)
        except Exception:
            pass

    def bg(self, fn, cb=None):
        def run():
            try:
                res = fn()
            except Exception as exc:
                res = (1, str(exc))
            if cb:
                self.q.put((cb, (res,)))
        threading.Thread(target=run, daemon=True).start()

    def _drain(self):
        try:
            while True:
                fn, args = self.q.get_nowait()
                try:
                    fn(*args)
                except tk.TclError:
                    pass
        except queue.Empty:
            pass
        if self.running:
            self.after(60, self._drain)

    def _poll_loop(self):
        n = 0
        while self.running:
            rc, out = cli("status", timeout=8)
            self.q.put((self.apply_status, (rc, out)))
            n += 1
            if n % 20 == 0:
                self.bg(lambda: cli("account", "get"), self.apply_account_poll)
            for _ in range(20):
                if not self.running:
                    return
                time.sleep(0.1)

    def clear(self):
        for w in self.box.winfo_children():
            w.destroy()

    def show(self, name, **kw):
        self.clear()
        getattr(self, "build_" + name)(**kw)

    def page(self, bg=BG):
        f = ctk.CTkFrame(self.box, fg_color=bg, corner_radius=0)
        f.pack(fill="both", expand=True)
        return f

    def _got_version(self, res):
        m = re.search(r"\d{4}\.\d+(?:-\S+)?", res[1] or "")
        self.cli_version = m.group(0) if m else (res[1] or "").strip()

    def _got_relays_bg(self, res):
        if res[0] == 0:
            self.countries = parse_relays(res[1])
            self.bg(self._read_relay_get, self._got_relay_get)

    def _read_relay_get(self):
        return cli("relay", "get")

    def _got_relay_get(self, res):
        out = res[1]
        m = re.search(r"^\s*Location:\s*(.+)$", out, re.M)
        self.sel_codes = parse_constraint(m.group(1)) if m else (None, None)
        self.sel_label = self.label_for(*self.sel_codes)
        m = re.search(r"Multihop entry:\s*(.+)$", out, re.M)
        self.entry_label = self.label_for(*parse_constraint(m.group(1))) if m else ""
        self.refresh_main()

    def label_for(self, ccode, city_code):
        if not ccode:
            return ""
        for c in self.countries:
            if c["code"].lower() == ccode.lower():
                if city_code:
                    for ci in c["cities"]:
                        if ci["code"].lower() == city_code.lower():
                            return ci["name"]
                return fr_country(c["name"])
        return ccode.upper()

    def _startup(self, res):
        rc, out = res
        if rc == 127:
            return self.show("nocli")
        info = parse_account(out)
        if info["state"] == "ok" and CFG.get("login_each_launch"):
            def work():
                cli("disconnect")
                return cli("account", "logout")
            return self.bg(work, lambda r: self._route_account({"state": "out"}))
        self._route_account(info, out)

    def _route_account(self, info, out=""):
        st = info["state"]
        if st == "ok":
            self.acct = info
            self.show("main")
        elif st == "revoked":
            self.acct = {"number": "", "expiry": None, "device": ""}
            self.show("login", msg="Cet appareil a été supprimé de votre compte. Reconnectez-vous.",
                      prefill=info.get("number", ""))
        elif st == "out":
            self.acct = {"number": "", "expiry": None, "device": ""}
            self.show("login")
        else:
            self.show("error", msg=translate_error(out))

    def apply_account_poll(self, res):
        info = parse_account(res[1])
        if info["state"] in ("out", "revoked"):
            if self.view not in ("login", "devices_login", "nocli", "error"):
                self._route_account(info, res[1])
        elif info["state"] == "ok":
            self.acct = info
            if self.view == "main":
                self.refresh_header()

    def enter_app(self):
        self.bg(lambda: cli("account", "get"), self._entered)

    def _entered(self, res):
        info = parse_account(res[1])
        if info["state"] == "ok":
            self.acct = info
            self.show("main")
        else:
            self._route_account(info, res[1])

    def topbar(self, parent, title, back):
        h = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0, height=56)
        h.pack(fill="x")
        h.pack_propagate(False)
        ctk.CTkButton(h, text="", image=self.ic_back, width=32, height=32, fg_color="transparent",
                      hover_color=BG, command=back).place(x=12, y=12)
        if title:
            ctk.CTkLabel(h, text=title, font=fnt(18), text_color=INK).place(relx=0.5, rely=0.5, anchor="center")
        return h

    def row(self, parent, text, cmd, right="", chevron=True):
        lines = text.count("\n") + 1
        r = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0, height=44 + 18 * (lines - 1))
        r.pack(fill="x", padx=2)
        r.pack_propagate(False)
        b = ctk.CTkButton(r, text=text, anchor="w", corner_radius=0, fg_color="transparent",
                          hover_color=PANEL_HOVER, text_color=INK, font=fnt(14), command=cmd)
        b.pack(fill="both", expand=True)
        overlay = []
        if chevron:
            c = ctk.CTkLabel(r, text="", image=self.ic_right, fg_color=PANEL)
            c.place(relx=1.0, x=-12, rely=0.5, anchor="e")
            overlay.append(c)
        rl = ctk.CTkLabel(r, text=right, font=fnt(12, False), text_color=WHITE60, fg_color=PANEL)
        rl.place(relx=1.0, x=-34 if chevron else -12, rely=0.5, anchor="e")
        overlay.append(rl)

        def inside():
            x, y = r.winfo_pointerxy()
            return (r.winfo_rootx() <= x < r.winfo_rootx() + r.winfo_width()
                    and r.winfo_rooty() <= y < r.winfo_rooty() + r.winfo_height())

        def hover(on):
            col = PANEL_HOVER if on else PANEL
            for w in overlay:
                w.configure(fg_color=col)
        for w in [b] + overlay:
            w.bind("<Enter>", lambda e: hover(True), add="+")
            w.bind("<Leave>", lambda e: hover(inside()), add="+")
        for w in overlay:
            w.bind("<Button-1>", lambda e: cmd())
        return rl

    def group(self, parent, items, pady=(0, 14)):
        g = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=10)
        g.pack(fill="x", padx=16, pady=pady)
        ctk.CTkFrame(g, fg_color=PANEL, height=6, corner_radius=0).pack(fill="x", padx=10)
        labels = []
        for i, it in enumerate(items):
            text, right, cmd = it
            if i:
                ctk.CTkFrame(g, fg_color=DIVIDER, height=1, corner_radius=0).pack(fill="x")
            labels.append(self.row(g, text, cmd, right))
        ctk.CTkFrame(g, fg_color=PANEL, height=6, corner_radius=0).pack(fill="x", padx=10)
        return labels

    def switch_row(self, parent, text, key, on_toggle):
        r = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=8, height=46)
        r.pack(fill="x", padx=16, pady=(0, 4))
        r.pack_propagate(False)
        ctk.CTkLabel(r, text=text, font=fnt(14), text_color=INK, anchor="w").pack(side="left", padx=14)
        sw = ctk.CTkSwitch(r, text="", width=44, progress_color=GREEN, button_color=WHITE,
                           fg_color="#CDB9BB", command=lambda: on_toggle(key, sw))
        sw.pack(side="right", padx=12)
        if self.opts.get(key):
            sw.select()
        self.switches[key] = sw
        return sw

    def note(self, parent, text, pady=(0, 10)):
        ctk.CTkLabel(parent, text=text, wraplength=280, justify="left", anchor="w",
                     font=fnt(12, False), text_color=WHITE60).pack(fill="x", padx=18, pady=pady)

    def confirm(self, title, text, ok_text, on_ok, danger=True):
        ov = ctk.CTkFrame(self.box, fg_color="#EADFE0", corner_radius=0)
        ov.place(x=0, y=0, relwidth=1, relheight=1)
        card = ctk.CTkFrame(ov, fg_color=WHITE, corner_radius=14, border_width=1, border_color=DIVIDER)
        card.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(card, text=title, font=fnt(16), text_color=INK, wraplength=240,
                     justify="left", anchor="w").pack(fill="x", padx=18, pady=(18, 6))
        ctk.CTkLabel(card, text=text, font=fnt(12, False), text_color=WHITE60, wraplength=240,
                     justify="left", anchor="w").pack(fill="x", padx=18, pady=(0, 14))

        def go():
            ov.destroy()
            on_ok()
        ctk.CTkButton(card, text=ok_text, height=34, width=240, font=fnt(14),
                      fg_color=RED if danger else GREEN, hover_color=RED_HOVER if danger else GREEN_HOVER,
                      command=go).pack(padx=18, pady=(0, 8))
        ctk.CTkButton(card, text="Annuler", height=34, width=240, font=fnt(14), fg_color=BG,
                      hover_color=PANEL_ROW, command=ov.destroy).pack(padx=18, pady=(0, 18))
        ov.lift()

    def header_logo(self, f, bg):
        ctk.CTkLabel(f, text="", image=self.logo_hdr, fg_color=bg).place(x=16, y=12)
        ctk.CTkLabel(f, text=APP_NAME.upper(), font=fnt(20), text_color=WHITE, fg_color=bg
                     ).place(x=64, y=31, anchor="w")

    def build_nocli(self):
        self.view = "nocli"
        f = self.page()
        ctk.CTkLabel(f, text="Mullvad introuvable", font=fnt(24), text_color=INK
                     ).pack(anchor="w", padx=22, pady=(120, 8))
        self.note(f, "Coonvad pilote la ligne de commande « mullvad ». Installez l'application "
                     "Mullvad VPN, ou indiquez où se trouve mullvad.exe "
                     r"(en général C:\Program Files\Mullvad VPN\resources).")
        ctk.CTkButton(f, text="Choisir mullvad.exe", height=34, font=fnt(14), fg_color=PANEL,
                      hover_color=PANEL_HOVER, command=self.pick_cli).pack(fill="x", padx=22, pady=(10, 6))
        ctk.CTkButton(f, text="Réessayer", height=34, font=fnt(14), fg_color=GREEN, hover_color=GREEN_HOVER,
                      command=self.restart).pack(fill="x", padx=22)

    def pick_cli(self):
        self._no_autohide = True
        try:
            p = filedialog.askopenfilename(title="Choisir mullvad.exe",
                                           filetypes=[("Programme", "*.exe *"), ("Tous", "*.*")])
        finally:
            self._no_autohide = False
        if p:
            CFG["cli_path"] = p
            save_config(CFG)
            self.restart()

    def restart(self):
        self.running = False
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def build_error(self, msg=""):
        self.view = "error"
        f = self.page()
        ctk.CTkLabel(f, text="Oups…", font=fnt(28), text_color=INK).pack(anchor="w", padx=22, pady=(120, 8))
        self.note(f, msg or "Impossible de joindre le service Mullvad.")
        ctk.CTkButton(f, text="Réessayer", height=34, font=fnt(14), fg_color=GREEN, hover_color=GREEN_HOVER,
                      command=lambda: self.bg(lambda: cli("account", "get"), self._startup)
                      ).pack(fill="x", padx=22, pady=(10, 0))

    def build_login(self, msg="", prefill=""):
        self.view = "login"
        f = self.page(BG)
        band = ctk.CTkFrame(f, fg_color=GREEN, corner_radius=0, width=W, height=HEADER_H)
        band.place(x=0, y=0)
        self.header_logo(band, GREEN)
        ctk.CTkButton(band, text="", image=self.ic_gear, width=34, height=34, corner_radius=17,
                      fg_color="transparent", hover_color=GREEN_DARK,
                      command=lambda: self.show("settings", back="login")).place(x=274, y=14)
        body = ctk.CTkFrame(f, fg_color=BG, corner_radius=0, width=W, height=H - HEADER_H - 40)
        body.place(x=0, y=HEADER_H + 40)
        body.pack_propagate(False)
        ctk.CTkLabel(body, text="Connexion", font=fnt(32), text_color=INK, anchor="w"
                     ).pack(fill="x", padx=24, pady=(26, 0))
        ctk.CTkLabel(body, text="Saisissez votre numéro de compte", font=fnt(12), text_color=WHITE60,
                     anchor="w").pack(fill="x", padx=24, pady=(0, 8))

        box = ctk.CTkFrame(body, fg_color=WHITE, corner_radius=10, border_width=1, border_color="#D9C6C8")
        box.pack(fill="x", padx=24)
        self.acc_entry = ctk.CTkEntry(box, placeholder_text="0000 0000 0000 0000", height=44, fg_color=WHITE,
                                      text_color=INK, border_width=0, corner_radius=10,
                                      placeholder_text_color="#B79FA2", font=fnt(16))
        self.acc_entry.pack(fill="x", padx=2, pady=2)
        self.hist_box = ctk.CTkFrame(box, fg_color=PANEL, corner_radius=8)
        self.acc_entry.bind("<KeyRelease>", self._on_account_key)
        self.acc_entry.bind("<Return>", lambda e: self.do_login())
        self.login_msg = ctk.CTkLabel(body, text=msg, text_color=ERR, wraplength=270, justify="left",
                                      anchor="w", font=fnt(12, False))
        self.login_msg.pack(fill="x", padx=24, pady=(8, 0))
        self.login_btn = ctk.CTkButton(body, text="Connexion", height=34, font=fnt(14), fg_color=GREEN_DIS,
                                       hover_color=GREEN_HOVER, text_color=WHITE60, command=self.do_login)
        self.login_btn.pack(fill="x", padx=24, pady=(12, 0))
        orr = ctk.CTkFrame(body, fg_color=BG, corner_radius=0, height=20)
        orr.pack(fill="x", padx=24, pady=(26, 0))
        orr.pack_propagate(False)
        ctk.CTkFrame(orr, fg_color="#D9C6C8", height=1, corner_radius=0).place(relx=0, rely=0.5, relwidth=1)
        ctk.CTkLabel(orr, text="Ou", font=fnt(12), text_color=WHITE60, fg_color=BG, width=40
                     ).place(relx=0.5, rely=0.5, anchor="center")
        link = ctk.CTkLabel(body, text="Créer un nouveau compte", font=ctk.CTkFont(
            family=FONT_SB, size=14, weight="bold" if FONT_SB_BOLD else "normal", underline=True),
            text_color=INK)
        link.pack(pady=(22, 0))
        link.bind("<Button-1>", lambda e: self.create_account())
        if prefill:
            self.acc_entry.insert(0, fmt_account(prefill))
        self._on_account_key()
        self.acc_entry.focus_set()

    def _history(self):
        return [h for h in CFG.get("history", []) if re.fullmatch(r"\d{16}", h)]

    def _on_account_key(self, _e=None):
        digits = re.sub(r"\D", "", self.acc_entry.get())[:16]
        txt = fmt_account(digits)
        if txt != self.acc_entry.get():
            self.acc_entry.delete(0, "end")
            self.acc_entry.insert(0, txt)
        ready = len(digits) == 16
        self.login_btn.configure(fg_color=GREEN if ready else GREEN_DIS,
                                 text_color=WHITE)
        for w in self.hist_box.winfo_children():
            w.destroy()
        self.hist_box.pack_forget()
        hist = [h for h in self._history() if not digits or h.startswith(digits)] if len(digits) < 16 else []
        if hist:
            self.hist_box.pack(fill="x", padx=2, pady=(0, 2))
            for h in hist[:3]:
                r = ctk.CTkFrame(self.hist_box, fg_color="transparent", height=44, corner_radius=0)
                r.pack(fill="x")
                r.pack_propagate(False)
                b = ctk.CTkButton(r, text=fmt_account(h), anchor="w", fg_color="transparent", corner_radius=0,
                                  hover_color="#EBDADC", text_color=INK, font=fnt(14),
                                  command=lambda h=h: self._pick_history(h))
                b.pack(side="left", fill="both", expand=True)
                x = ctk.CTkButton(r, text="", width=30, height=30, corner_radius=15, fg_color="#E7D6D8",
                                  hover_color="#DCC8CA", image=self.ic_close,
                                  command=lambda h=h: self._forget_history(h))
                x.pack(side="right", padx=10)

    def _pick_history(self, h):
        self.acc_entry.delete(0, "end")
        self.acc_entry.insert(0, fmt_account(h))
        self._on_account_key()
        self.do_login()

    def _forget_history(self, h):
        CFG["history"] = [x for x in self._history() if x != h]
        save_config(CFG)
        self._on_account_key()

    def remember_account(self, digits):
        hist = [digits] + [x for x in self._history() if x != digits]
        CFG["history"] = hist[:3]
        save_config(CFG)

    def do_login(self):
        digits = re.sub(r"\D", "", self.acc_entry.get())
        if len(digits) != 16:
            self.login_msg.configure(text="Saisissez un numéro de compte à 16 chiffres.")
            return
        self.login_btn.configure(state="disabled", text="Connexion…")
        self.login_msg.configure(text="")
        self.bg(lambda: cli("account", "login", digits), lambda r: self.after_login(r, digits))

    def after_login(self, res, digits):
        rc, out = res
        low = out.lower()
        if self.view != "login":
            return
        if rc == 0 or "already logged in" in low:
            self.remember_account(digits)
            self.enter_app()
        elif "too many devices" in low or ("too many" in low and "device" in low):
            self.show("devices", account=digits, mode="login")
        else:
            self.login_btn.configure(state="normal", text="Connexion")
            self.login_msg.configure(text=translate_error(out))

    def create_account(self):
        def go():
            self.login_btn.configure(state="disabled")
            self.login_msg.configure(text="Création du compte…", text_color=WHITE60)
            self.bg(lambda: cli("account", "create"), self._created)
        self.confirm("Créer un compte ?", "Un nouveau numéro de compte Mullvad sera généré et "
                     "cet appareil y sera connecté.", "Créer un compte", go, danger=False)

    def _created(self, res):
        if self.view != "login":
            return
        if res[0] == 0:
            self.enter_app()
        else:
            self.login_btn.configure(state="normal")
            self.login_msg.configure(text=translate_error(res[1]), text_color=ERR)

    def build_devices(self, account=None, mode="manage"):
        self.view = "devices_login" if mode == "login" else "devices"
        self.dev_account = account
        self.dev_mode = mode
        self.dev_names = []
        f = self.page()
        back = (lambda: self.show("login", prefill=account or "")) if mode == "login" \
            else (lambda: self.show("account"))
        self.topbar(f, "", back)
        ctk.CTkLabel(f, text="Trop d'appareils" if mode == "login" else "Gérer les appareils",
                     font=fnt(26), text_color=INK, anchor="w").pack(fill="x", padx=20, pady=(0, 6))
        if mode == "login":
            txt = ("Veuillez vous déconnecter d'au moins un appareil en le supprimant de la liste "
                   "ci-dessous. Le nom de l'appareil figure dans les paramètres de son compte.")
        else:
            txt = "Voici les appareils actuellement connectés à votre compte."
        self.note(f, txt)
        if mode == "login":
            self.dev_continue = ctk.CTkButton(f, text="Continuer la connexion", height=36, font=fnt(14),
                                              fg_color=GREEN_DIS, hover_color=GREEN_HOVER, text_color=WHITE60,
                                              state="disabled", command=self.retry_login)
            self.dev_continue.pack(side="bottom", fill="x", padx=16, pady=(6, 16))
        self.dev_msg = ctk.CTkLabel(f, text="", text_color=ERR, wraplength=280, justify="left",
                                    anchor="w", font=fnt(12, False))
        self.dev_msg.pack(side="bottom", fill="x", padx=18)
        self.dev_list = ctk.CTkScrollableFrame(f, fg_color=BG, corner_radius=0)
        self.dev_list.pack(fill="both", expand=True, padx=6)
        self.load_devices()

    def _acc_args(self):
        return ["--account", self.dev_account] if self.dev_account else []

    def load_devices(self):
        for w in self.dev_list.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.dev_list, text="Chargement…", text_color=WHITE60, font=fnt(13, False)).pack(pady=20)
        self.bg(lambda: cli("account", "list-devices", *self._acc_args()), self._show_devices)

    def _show_devices(self, res):
        if not self.view.startswith("devices"):
            return
        rc, out = res
        for w in self.dev_list.winfo_children():
            w.destroy()
        if rc != 0:
            self.dev_msg.configure(text=translate_error(out))
            return
        names = parse_devices(out)
        self.dev_names = names
        if self.dev_mode == "login":
            ok = len(names) < MAX_DEVICES
            self.dev_continue.configure(state="normal" if ok else "disabled",
                                        fg_color=GREEN if ok else GREEN_DIS,
                                        text_color=WHITE)
        current = (self.acct.get("device") or "").lower() if self.dev_mode == "manage" else ""
        if not names:
            ctk.CTkLabel(self.dev_list, text="Aucun appareil.", text_color=WHITE60).pack(pady=20)
        for name in names:
            row = ctk.CTkFrame(self.dev_list, fg_color=PANEL, corner_radius=6, height=46)
            row.pack(fill="x", pady=2, padx=6)
            row.pack_propagate(False)
            is_cur = name.lower() == current
            ctk.CTkLabel(row, text=name + ("  (cet appareil)" if is_cur else ""), text_color=INK,
                         font=fnt(14), anchor="w").pack(side="left", padx=12)
            if not is_cur:
                ctk.CTkButton(row, text="", image=self.ic_close, width=34, height=34, fg_color="transparent",
                              hover_color="#F3D3D0", command=lambda n=name: self.ask_remove(n)).pack(side="right", padx=6)

    def ask_remove(self, name):
        self.confirm("Supprimer cet appareil ?",
                     f"« {name} » sera retiré de votre compte et déconnecté du VPN.",
                     "Supprimer", lambda: self.remove_device(name))

    def remove_device(self, name):
        self.dev_msg.configure(text="Suppression de l'appareil…", text_color=WHITE60)
        self.bg(lambda: cli("account", "revoke-device", name, *self._acc_args()), self._after_remove)

    def _after_remove(self, res):
        if not self.view.startswith("devices"):
            return
        rc, out = res
        if rc == 0:
            self.dev_msg.configure(text="")
            self.load_devices()
        else:
            self.dev_msg.configure(text=translate_error(out), text_color=ERR)

    def retry_login(self):
        digits = self.dev_account
        self.dev_continue.configure(state="disabled", text="Connexion…")
        self.bg(lambda: cli("account", "login", digits), lambda r: self._retry_done(r, digits))

    def _retry_done(self, res, digits):
        rc, out = res
        if self.view != "devices_login":
            return
        if rc == 0 or "already logged in" in out.lower():
            self.remember_account(digits)
            self.enter_app()
        else:
            self.dev_continue.configure(state="normal", text="Continuer la connexion")
            self.dev_msg.configure(text=translate_error(out), text_color=ERR)
            self.load_devices()

    def build_main(self):
        self.view = "main"
        f = self.page()
        st = self.vpn["state"]
        init = GREEN if st in ("connected", "connecting", "disconnecting") else HDR_OFF
        self._hdr_cur = self._hdr_target = init
        self.hdr = ctk.CTkFrame(f, corner_radius=0, fg_color=init, width=W, height=HEADER_H)
        self.hdr.place(x=0, y=0)
        self.hdr_logo = ctk.CTkLabel(self.hdr, text="", image=self.logo_hdr, fg_color=init)
        self.hdr_logo.place(x=16, y=12)
        self.hdr_title = ctk.CTkLabel(self.hdr, text=APP_NAME.upper(), font=fnt(20), text_color=WHITE, fg_color=init)
        self.hdr_title.place(x=64, y=31, anchor="w")
        self.btn_user = ctk.CTkButton(self.hdr, text="", image=self.ic_user, width=34, height=34, corner_radius=17,
                                      fg_color="transparent", hover_color=GREEN_DARK,
                                      command=lambda: self.show("account"))
        self.btn_user.place(x=218, y=14)
        self.btn_gear = ctk.CTkButton(self.hdr, text="", image=self.ic_gear, width=34, height=34, corner_radius=17,
                                      fg_color="transparent", hover_color=GREEN_DARK,
                                      command=lambda: self.show("settings", back="main"))
        self.btn_gear.place(x=262, y=14)
        self.hdr_dev = ctk.CTkLabel(self.hdr, text="", font=fnt(11, False), text_color=WHITE, fg_color=init)
        self.hdr_dev.place(x=16, y=64, anchor="w")
        self.hdr_time = ctk.CTkLabel(self.hdr, text="", font=fnt(11, False), text_color=WHITE, fg_color=init)
        self.hdr_time.place(x=296, y=64, anchor="e")

        self.map_lbl = ctk.CTkLabel(f, text="", width=W, height=MAP_H, corner_radius=0, fg_color=MAP_SEA)
        self.map_lbl.place(x=0, y=HEADER_H)
        self.btn_loc = ctk.CTkButton(f, text="", width=256, height=38, corner_radius=12, fg_color=PANEL,
                                     hover_color=PANEL_HOVER, font=fnt(14),
                                     command=lambda: self.show("locations", target="exit"))
        self.btn_loc.place(x=32, y=450)
        self.btn_main = ctk.CTkButton(f, text="", width=256, height=38, corner_radius=12, font=fnt(15),
                                      command=self.toggle_connection)
        self.btn_main.place(x=32, y=498)
        self._map_key = None
        self._anim_job = None
        self.refresh_main()

    @staticmethod
    def _rgb(c):
        return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))

    def tween_header(self, target, steps=10):
        if self._hdr_target == target:
            return
        self._hdr_target = target
        self._hdr_token = getattr(self, "_hdr_token", 0) + 1
        tok, a, b = self._hdr_token, self._rgb(self._hdr_cur), self._rgb(target)

        def step(i):
            if tok != self._hdr_token or self.view != "main":
                return
            t = i / steps
            t = t * t * (3 - 2 * t)
            col = "#%02x%02x%02x" % tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))
            self._hdr_cur = col
            for w in (self.hdr, self.hdr_logo, self.hdr_title, self.hdr_dev, self.hdr_time):
                w.configure(fg_color=col)
        for i in range(1, steps + 1):
            self.after(i * 22, lambda i=i: step(i))

    def refresh_header(self):
        if self.view != "main":
            return
        st = self.vpn["state"]
        green = st in ("connected", "connecting", "disconnecting")
        self.tween_header(GREEN if green else HDR_OFF)
        dark = GREEN_DARK if green else RED_DARK
        self.btn_user.configure(hover_color=dark)
        self.btn_gear.configure(hover_color=dark)
        exp = self.acct.get("expiry")
        right = "Temps restant : " + (fmt_time_left(exp) if exp else "—")
        self.hdr_time.configure(text=right)
        dev = self.acct.get("device") or ""
        label = "Nom de l'appareil : "
        f = tkfont.Font(family=FONT_REG, size=-11)
        avail = (W - 32) - f.measure(right) - 6
        if dev and f.measure(label + dev) > avail:
            while dev and f.measure(label + dev + "...") > avail:
                dev = dev[:-1]
            dev = dev.rstrip() + "..."
        self.hdr_dev.configure(text=label + dev if dev else "")

    def geo_point(self):
        v = self.vpn
        for c in self.countries:
            if c["name"] == v["country"]:
                for ci in c["cities"]:
                    if ci["name"] == v["city"] and ci["lat"] is not None:
                        return ci["lat"], ci["lon"]
                pts = [(ci["lat"], ci["lon"]) for ci in c["cities"] if ci["lat"] is not None]
                if pts and not self.world.ok:
                    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        if v["country"] and self.world.ok:
            hit = self.world.center_of(v["country"])
            if hit:
                return hit
        return 48.0, 8.0

    def panel_error(self):
        v = self.vpn
        if self.daemon_err:
            return self.daemon_err
        if self.cmd_err:
            return self.cmd_err
        if v["state"] == "error":
            return re.sub(r"^Blocked:\s*", "Bloqué : ", v["error"])
        exp = self.acct.get("expiry")
        if exp and exp < datetime.now() and v["state"] == "disconnected":
            return "Votre compte n'a plus de temps. Ajoutez-en dans « Compte »."
        return ""

    def refresh_main(self):
        if self.view != "main":
            return
        v = self.vpn
        st = v["state"]
        self.refresh_header()
        lat, lon = self.geo_point()
        err = self.panel_error()
        if st == "disconnected":
            self.btn_main.configure(text="Connexion", fg_color=GREEN, hover_color=GREEN_HOVER, state="normal")
        elif st in ("connected", "error"):
            self.btn_main.configure(text="Déconnexion", fg_color=RED_BTN, hover_color=RED_HOVER, state="normal")
        elif st == "disconnecting":
            self.btn_main.configure(text="Déconnexion…", state="disabled")
        else:
            self.btn_main.configure(text="Annuler", fg_color=RED_BTN, hover_color=RED_HOVER, state="normal")
        self.btn_loc.configure(text=(self.sel_label or "Choisir un lieu") if st == "disconnected"
                               else "Changer de lieu")
        key = (round(lat, 2), round(lon, 2), st, v["country"], err, bool(self.countries))
        if key != self._map_key:
            self._map_key = key
            S = 2
            bk = (round(lat, 1), round(lon, 1))
            if bk != self._base_key:
                self._base_key = bk
                self._base_img = self.world.render(lat, lon, W, MAP_H, 128, scale=S).convert("RGBA")
                if not self.world.ok:
                    d0 = ImageDraw.Draw(self._base_img)
                    for y in range(8, MAP_H, 9):
                        for x in range(10, W, 9):
                            if ((x - 160) / 146) ** 2 + ((y - 130) / 110) ** 2 < 1:
                                d0.ellipse([(x - 1.5) * S, (y - 1.5) * S, (x + 1.5) * S, (y + 1.5) * S], fill="#E2CFD1")
            self._static = self.build_static(st, err)
            self._paint(0.0)
        if st in ("connecting", "disconnecting") and not self._anim_job:
            self._anim_job = self.after(10, self._anim_tick)

    def build_static(self, st, err):
        S = 2
        ov = Image.new("RGBA", (W * S, MAP_H * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        v = self.vpn
        status, scol = {
            "disconnected": ("DÉCONNECTÉ", (138, 113, 116)),
            "connecting": ("CRÉATION D'UNE CONNEXION SÉCURISÉE", (213, 43, 30)),
            "disconnecting": ("DÉCONNEXION…", (138, 113, 116)),
            "connected": ("CONNEXION SÉCURISÉE", (34, 139, 34)),
            "error": ("CONNEXION BLOQUÉE", (213, 43, 30)),
        }[st]
        country = fr_country(v["country"]) if v["country"] else ""
        f_err = pil_font(11 * S, False)
        err_lines = []
        if err:
            cur = ""
            for w_ in err.split():
                t = (cur + " " + w_).strip()
                if f_err.getlength(t) > 256 * S and cur:
                    err_lines.append(cur)
                    cur = w_
                else:
                    cur = t
            err_lines.append(cur)
            err_lines = err_lines[:3]
        top = 380 - 15 * len(err_lines)
        d.rounded_rectangle([16 * S, (top - HEADER_H) * S, 304 * S, (551 - HEADER_H) * S], radius=16 * S,
                            fill=(255, 255, 255, 244), outline=(226, 207, 209, 255), width=S)

        def fit(text, font, maxw):
            while font.getlength(text) > maxw * S and len(text) > 1:
                text = text[:-2] + "…"
            return text

        y = top + 26 - HEADER_H
        fs = pil_font(12 * S)
        d.text((32 * S, y * S), fit(status, fs, 256), font=fs, fill=scol + (255,), anchor="lm")
        y += 26
        fc = pil_font(20 * S)
        if country:
            d.text((32 * S, y * S), fit(country, fc, 256), font=fc, fill=(42, 20, 22, 255), anchor="lm")
        for ln in err_lines:
            y += 15
            d.text((32 * S, y * S), ln, font=f_err, fill=(192, 40, 28, 255), anchor="lm")
        return ov

    def _paint(self, phase):
        if self.view != "main" or self._base_img is None:
            return
        S = 2
        st = self.vpn["state"]
        col = {"connected": (213, 43, 30), "connecting": (213, 43, 30),
               "disconnecting": (150, 125, 128)}.get(st, (150, 125, 128))
        im = self._base_img.copy()
        pl = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(pl)
        px, py = W * S // 2, 128 * S
        if st in ("connecting", "disconnecting"):
            r = (26 + 20 * phase) * S
            d.ellipse([px - r, py - r, px + r, py + r], fill=col + (int(120 * (1 - phase)),))
        d.ellipse([px - 26 * S, py - 26 * S, px + 26 * S, py + 26 * S], fill=col + (70,))
        d.ellipse([px - 11 * S, py - 11 * S, px + 11 * S, py + 11 * S], fill=col + (255,),
                  outline=(255, 255, 255, 240), width=S)
        if st == "connected":
            leaf_size = 18 * S
            d.polygon(leaf_pts(px + S, py + S, leaf_size), fill=(0, 0, 0, 60))
            d.polygon(leaf_pts(px, py, leaf_size), fill=(255, 255, 255, 255))
        im = Image.alpha_composite(Image.alpha_composite(im, pl), self._static).convert("RGB").reduce(S)
        self._map_ctk = ctk_img(im, (W, MAP_H))
        self.map_lbl.configure(image=self._map_ctk)

    def _anim_tick(self):
        self._anim_job = None
        if self.view != "main":
            return
        if self.vpn["state"] not in ("connecting", "disconnecting"):
            self._paint(0.0)
            return
        self._paint((time.time() % 1.3) / 1.3)
        self._anim_job = self.after(70, self._anim_tick)

    def apply_status(self, rc, out):
        first = out.strip().lower()
        known = first.startswith(("connected", "connecting", "disconnect", "blocked"))
        self.daemon_err = "" if (rc == 0 or known) else translate_error(out)
        new = parse_status(out)
        if new["state"] == "connected":
            self.cmd_err = ""
        changed = new != self.vpn
        self.vpn = new
        if changed or self.daemon_err:
            self.refresh_main()
            self.update_tray()

    def toggle_connection(self):
        st = self.vpn["state"]
        self.cmd_err = ""
        if st in ("connected", "connecting", "error"):
            self.vpn = dict(self.vpn, state="disconnecting")
            self.refresh_main()
            self.bg(lambda: cli("disconnect"))
        elif st == "disconnected":
            self.vpn = dict(self.vpn, state="connecting")
            self.refresh_main()
            self.bg(lambda: cli("connect"), self._after_cmd)
        self.update_tray()

    def _after_cmd(self, res):
        rc, out = res
        if rc != 0:
            self.cmd_err = translate_error(out)
            self.refresh_main()

    def build_locations(self, target="exit"):
        self.view = "locations"
        self.loc_target = target
        f = self.page()
        self.topbar(f, "Lieu d'entrée" if target == "entry" else "Sélectionner un lieu",
                    (lambda: self.show("multihop")) if target == "entry" else (lambda: self.show("main")))
        self.search = ctk.CTkEntry(f, placeholder_text="Rechercher…", height=36, fg_color=PANEL, border_width=0,
                                   text_color=INK, placeholder_text_color=WHITE60, font=fnt(13, False))
        self.search.pack(fill="x", padx=16, pady=(0, 8))
        self.search.bind("<KeyRelease>", lambda e: self.render_locations())
        self.loc_list = ctk.CTkScrollableFrame(f, fg_color=BG, corner_radius=0)
        self.loc_list.pack(fill="both", expand=True, padx=6)
        self.expanded = set()
        if self.countries:
            self.render_locations()
        else:
            ctk.CTkLabel(self.loc_list, text="Chargement…", text_color=WHITE60).pack(pady=20)
            self.bg(lambda: cli("relay", "list", timeout=40), self._got_relays)

    def _got_relays(self, res):
        if self.view != "locations":
            return
        rc, out = res
        if rc != 0:
            for w in self.loc_list.winfo_children():
                w.destroy()
            ctk.CTkLabel(self.loc_list, text=translate_error(out), text_color=ERR, wraplength=260).pack(pady=20)
            return
        self.countries = parse_relays(out)
        self.render_locations()

    def render_locations(self):
        for w in self.loc_list.winfo_children():
            w.destroy()
        q = self.search.get().strip().lower()
        sel_c, sel_city = self.sel_codes if self.loc_target == "exit" else (None, None)
        for c in sorted(self.countries, key=lambda c: fr_country(c["name"]).lower()):
            name, code, cities = fr_country(c["name"]), c["code"], c["cities"]
            match_country = q in name.lower() or q in c["name"].lower()
            shown = cities if (not q or match_country) else [ci for ci in cities if q in ci["name"].lower()]
            if q and not match_country and not shown:
                continue
            open_ = (code in self.expanded) or bool(q)
            row = ctk.CTkFrame(self.loc_list, fg_color=PANEL, corner_radius=4, height=44)
            row.pack(fill="x", pady=1, padx=4)
            row.pack_propagate(False)
            is_sel = sel_c and sel_c.lower() == code.lower() and not sel_city
            ctk.CTkButton(row, text=name, anchor="w", fg_color="transparent", hover_color=PANEL_HOVER,
                          text_color=INK, font=fnt(14), image=self.ic_check if is_sel else None,
                          compound="right", command=lambda n=name, cc=code: self.pick_location(n, cc)
                          ).pack(side="left", fill="both", expand=True)
            if cities:
                ctk.CTkButton(row, text="", width=40, fg_color="transparent", hover_color=PANEL_HOVER,
                              image=self.ic_down if open_ else self.ic_right,
                              command=lambda cc=code: self.toggle_country(cc)).pack(side="right", fill="y")
            if open_:
                for ci in shown:
                    sel2 = sel_c and sel_c.lower() == code.lower() and sel_city and sel_city.lower() == ci["code"].lower()
                    ctk.CTkButton(self.loc_list, text=ci["name"], anchor="w", height=38, corner_radius=4,
                                  fg_color=PANEL_ROW, hover_color=PANEL_HOVER, text_color=INK, font=fnt(13),
                                  image=self.ic_check if sel2 else None, compound="right",
                                  command=lambda cc=code, cn=ci["code"], lab=ci["name"]: self.pick_location(lab, cc, cn)
                                  ).pack(fill="x", pady=1, padx=(24, 4))

    def toggle_country(self, code):
        self.expanded.symmetric_difference_update({code})
        self.render_locations()

    def pick_location(self, label, country, city=None):
        loc = [country.lower()] + ([city.lower()] if city else [])
        if self.loc_target == "entry":
            self.entry_label = label

            def work():
                return cli_first_ok(("relay", "set", "entry", "location", *loc),
                                    ("relay", "set", "tunnel", "wireguard", "entry-location", *loc))
            self.bg(work, lambda r: self.show("multihop", err=translate_error(r[1]) if r[0] else ""))
            return
        self.sel_label = label
        self.sel_codes = (country.lower(), city.lower() if city else None)
        self.cmd_err = ""

        def work():
            rc, out = cli("relay", "set", "location", *loc)
            if rc == 0:
                cli("connect")
            return rc, out
        self.vpn = dict(self.vpn, state="connecting")
        self.bg(work, self._after_cmd)
        self.show("main")
        self.update_tray()

    def build_settings(self, back="main"):
        self.view = "settings"
        self.settings_back = back
        f = self.page()
        self.topbar(f, "Paramètres", lambda: self.show(back))
        sc = ctk.CTkScrollableFrame(f, fg_color=BG, corner_radius=0)
        sc.pack(fill="both", expand=True)
        onoff = lambda k: "Activé" if self.opts.get(k) else "Désactivé"
        labs = self.group(sc, [
            ("DAITA", onoff("daita"), lambda: self.show("daita")),
            ("Multihop", onoff("multihop"), lambda: self.show("multihop")),
            ("Paramètres VPN", "", lambda: self.show("vpnsettings")),
            ("Paramètres d'interface\nutilisateur", "", lambda: self.show("uisettings")),
        ])
        self.group(sc, [("Split tunneling", "", lambda: self.show("splittunnel"))])
        self.group(sc, [("Accès à l'API", "", lambda: self.show("apiaccess"))])
        self.group(sc, [("Assistance", "", lambda: self.show("support")),
                        ("Infos sur l'application", self.cli_version, lambda: self.show("about"))])
        ctk.CTkButton(sc, text="Quitter", height=40, corner_radius=8, fg_color=RED, hover_color=RED_HOVER,
                      font=fnt(14), command=self.quit_app).pack(fill="x", padx=16, pady=(2, 16))
        if CLI:
            self.bg(self.read_options, lambda o: self._opts_for_settings(o, labs))

    def _opts_for_settings(self, o, labs):
        self.opts.update(o)
        if self.view != "settings":
            return
        labs[0].configure(text="Activé" if o.get("daita") else "Désactivé")
        labs[1].configure(text="Activé" if o.get("multihop") else "Désactivé")

    @staticmethod
    def read_options():
        o = {}
        o["auto"] = is_on(cli("auto-connect", "get")[1])
        o["lan"] = is_on(cli("lan", "get")[1])
        o["lockdown"] = is_on(cli("lockdown-mode", "get")[1])
        t = cli("tunnel", "get")[1]
        m = re.search(r"DAITA:\s*(\w+)", t)
        o["daita"] = bool(m and m.group(1).lower() == "on")
        r = cli("relay", "get")[1]
        m = re.search(r"Multihop(?: state)?:\s*(\w+)", r)
        o["multihop"] = bool(m and m.group(1).lower() in ("always", "on", "yes", "true"))
        m = re.search(r"Multihop entry:\s*(.+)$", r, re.M)
        o["entry"] = m.group(1).strip() if m else ""
        return o

    def set_option(self, key, on):
        onoff = "on" if on else "off"
        if key == "auto":
            return cli("auto-connect", "set", onoff)
        if key == "lan":
            return cli("lan", "set", "allow" if on else "block")
        if key == "lockdown":
            return cli("lockdown-mode", "set", onoff)
        if key == "daita":
            return cli_first_ok(("tunnel", "set", "daita", onoff), ("tunnel", "wireguard", "daita", "set", onoff))
        if key == "multihop":
            return cli_first_ok(("relay", "set", "multihop", "always" if on else "never"),
                                ("relay", "set", "tunnel", "wireguard", "--use-multihop", onoff))
        return 1, "?"

    def toggle_option(self, key, sw):
        on = bool(sw.get())
        self.opt_msg.configure(text="")

        def done(res):
            if res[0] == 0:
                self.opts[key] = on
            else:
                (sw.deselect if on else sw.select)()
                if self.view in ("daita", "multihop", "vpnsettings"):
                    self.opt_msg.configure(text=translate_error(res[1]))
        self.bg(lambda: self.set_option(key, on), done)

    def option_page(self, view, title, rows, desc="", extra=None):
        self.view = view
        self.switches = {}
        f = self.page()
        self.topbar(f, title, lambda: self.show("settings", back=getattr(self, "settings_back", "main")))
        if desc:
            self.note(f, desc, pady=(0, 12))
        for key, text in rows:
            self.switch_row(f, text, key, self.toggle_option)
        self.opt_msg = ctk.CTkLabel(f, text="", text_color=ERR, wraplength=280, justify="left", anchor="w",
                                    font=fnt(12, False))
        self.opt_msg.pack(fill="x", padx=18, pady=4)
        if extra:
            extra(f)
        if CLI:
            self.bg(self.read_options, self._apply_opts)
        return f

    def _apply_opts(self, o):
        self.opts.update(o)
        for k, sw in getattr(self, "switches", {}).items():
            try:
                (sw.select if o.get(k) else sw.deselect)()
            except tk.TclError:
                return

    def build_daita(self):
        self.option_page("daita", "DAITA", [("daita", "Activer DAITA")],
                         "DAITA (défense contre l'analyse de trafic guidée par l'IA) masque les schémas de votre "
                         "activité en ligne en ajoutant du trafic factice. Peut ralentir la connexion et n'est "
                         "disponible que sur certains serveurs.")

    def build_multihop(self, err=""):
        def extra(f):
            self.entry_btn = ctk.CTkButton(f, text="Lieu d'entrée : " + (self.entry_label or "—"), height=40,
                                           fg_color=PANEL, hover_color=PANEL_HOVER, font=fnt(14), anchor="w",
                                           command=lambda: self.show("locations", target="entry"))
            self.entry_btn.pack(fill="x", padx=16, pady=(6, 0))
            if err:
                self.opt_msg.configure(text=err)
        self.option_page("multihop", "Multihop", [("multihop", "Activer Multihop")],
                         "Multihop fait passer votre trafic par deux serveurs VPN : un serveur d'entrée puis le "
                         "serveur de sortie choisi sur l'écran principal. C'est plus lent, mais plus difficile à tracer.",
                         extra)
        if CLI:
            self.bg(self.read_options, self._multihop_entry)

    def _multihop_entry(self, o):
        if self.view == "multihop":
            lab = self.label_for(*parse_constraint(o.get("entry", ""))) or self.entry_label
            self.entry_label = lab
            self.entry_btn.configure(text="Lieu d'entrée : " + (lab or "—"))

    def build_vpnsettings(self):
        self.option_page("vpnsettings", "Paramètres VPN",
                         [("auto", "Connexion automatique"), ("lan", "Partage du réseau local"),
                          ("lockdown", "Mode verrouillage")],
                         "Connexion automatique : le VPN se connecte au démarrage du service. "
                         "Mode verrouillage : tout le trafic est bloqué quand le VPN est déconnecté.")

    def build_uisettings(self):
        self.view = "uisettings"
        f = self.page()
        self.topbar(f, "Interface utilisateur",
                    lambda: self.show("settings", back=getattr(self, "settings_back", "main")))
        r = ctk.CTkFrame(f, fg_color=PANEL, corner_radius=8, height=56)
        r.pack(fill="x", padx=16, pady=(8, 4))
        r.pack_propagate(False)
        ctk.CTkLabel(r, text="Réduire dans la zone de\nnotification à la fermeture", font=fnt(13), text_color=INK,
                     anchor="w", justify="left").pack(side="left", padx=14)

        def toggle():
            CFG["close_to_tray"] = bool(sw.get())
            save_config(CFG)
        sw = ctk.CTkSwitch(r, text="", width=44, progress_color=GREEN, button_color=WHITE, fg_color="#CDB9BB",
                           command=toggle)
        sw.pack(side="right", padx=12)
        if CFG.get("close_to_tray", True):
            sw.select()
        r2 = ctk.CTkFrame(f, fg_color=PANEL, corner_radius=8, height=56)
        r2.pack(fill="x", padx=16, pady=(4, 4))
        r2.pack_propagate(False)
        ctk.CTkLabel(r2, text="Page de connexion à chaque\nlancement (déconnecte le compte)", font=fnt(13),
                     text_color=INK, anchor="w", justify="left").pack(side="left", padx=14)

        def toggle2():
            CFG["login_each_launch"] = bool(sw2.get())
            save_config(CFG)
        sw2 = ctk.CTkSwitch(r2, text="", width=44, progress_color=GREEN, button_color=WHITE, fg_color="#CDB9BB",
                            command=toggle2)
        sw2.pack(side="right", padx=12)
        if CFG.get("login_each_launch"):
            sw2.select()
        r3 = ctk.CTkFrame(f, fg_color=PANEL, corner_radius=8, height=56)
        r3.pack(fill="x", padx=16, pady=(4, 4))
        r3.pack_propagate(False)
        ctk.CTkLabel(r3, text="Lancer au démarrage de Windows\n(en arrière-plan)", font=fnt(13),
                     text_color=INK, anchor="w", justify="left").pack(side="left", padx=14)

        def toggle3():
            on = bool(sw3.get())
            CFG["autostart"] = on
            set_autostart(on)
            save_config(CFG)
        sw3 = ctk.CTkSwitch(r3, text="", width=44, progress_color=GREEN, button_color=WHITE, fg_color="#CDB9BB",
                            command=toggle3)
        sw3.pack(side="right", padx=12)
        if autostart_enabled():
            sw3.select()
        if not pystray:
            self.note(f, "Installez « pystray » (pip install pystray) pour avoir une icône dans la zone de notification.")

    def build_splittunnel(self):
        self.view = "splittunnel"
        f = self.page()
        self.topbar(f, "Split tunneling", lambda: self.show("settings", back=getattr(self, "settings_back", "main")))
        self.note(f, "Les applications ajoutées ici n'utilisent pas le tunnel VPN.")
        self.st_switch_row = ctk.CTkFrame(f, fg_color=PANEL, corner_radius=8, height=46)
        self.st_switch_row.pack(fill="x", padx=16, pady=(0, 6))
        self.st_switch_row.pack_propagate(False)
        ctk.CTkLabel(self.st_switch_row, text="Activer le split tunneling", font=fnt(14), text_color=INK
                     ).pack(side="left", padx=14)
        self.st_sw = ctk.CTkSwitch(self.st_switch_row, text="", width=44, progress_color=GREEN, button_color=WHITE,
                                   fg_color="#CDB9BB", command=self.st_toggle)
        self.st_sw.pack(side="right", padx=12)
        self.st_msg = ctk.CTkLabel(f, text="", text_color=ERR, wraplength=280, justify="left", anchor="w",
                                   font=fnt(12, False))
        self.st_msg.pack(side="bottom", fill="x", padx=18)
        ctk.CTkButton(f, text="Ajouter une application", height=36, font=fnt(14), fg_color=PANEL,
                      hover_color=PANEL_HOVER, command=self.st_add).pack(side="bottom", fill="x", padx=16, pady=(4, 8))
        self.st_list = ctk.CTkScrollableFrame(f, fg_color=BG, corner_radius=0)
        self.st_list.pack(fill="both", expand=True, padx=6)
        self.st_load()

    def st_load(self):
        self.bg(lambda: cli("split-tunnel", "get"), self._st_loaded)

    def _st_loaded(self, res):
        if self.view != "splittunnel":
            return
        rc, out = res
        for w in self.st_list.winfo_children():
            w.destroy()
        if rc != 0:
            self.st_msg.configure(text="Le split tunneling n'est pas disponible via la CLI sur ce système.")
            self.st_sw.configure(state="disabled")
            return
        m = re.search(r"Split tunneling state:\s*(\w+)", out)
        (self.st_sw.select if m and m.group(1).lower() == "on" else self.st_sw.deselect)()
        apps, grab = [], False
        for ln in out.splitlines():
            if ln.lower().startswith("excluded applications"):
                grab = True
                continue
            if grab and ln.strip():
                apps.append(ln.strip())
        if not apps:
            ctk.CTkLabel(self.st_list, text="Aucune application exclue.", text_color=WHITE60,
                         font=fnt(13, False)).pack(pady=16)
        for p in apps:
            row = ctk.CTkFrame(self.st_list, fg_color=PANEL, corner_radius=6, height=44)
            row.pack(fill="x", pady=2, padx=6)
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=os.path.basename(p) or p, font=fnt(13), text_color=INK, anchor="w"
                         ).pack(side="left", padx=12)
            ctk.CTkButton(row, text="", image=self.ic_close, width=34, height=34, fg_color="transparent",
                          hover_color="#F3D3D0", command=lambda p=p: self.st_remove(p)).pack(side="right", padx=6)

    def st_toggle(self):
        on = "on" if self.st_sw.get() else "off"
        self.bg(lambda: cli("split-tunnel", "set", on), self._st_done)

    def st_add(self):
        p = filedialog.askopenfilename(title="Choisir une application", filetypes=[("Programmes", "*.exe"), ("Tous", "*.*")])
        if p:
            self.bg(lambda: cli("split-tunnel", "app", "add", p), self._st_done)

    def st_remove(self, p):
        self.bg(lambda: cli("split-tunnel", "app", "remove", p), self._st_done)

    def _st_done(self, res):
        if self.view != "splittunnel":
            return
        self.st_msg.configure(text=translate_error(res[1]) if res[0] else "")
        self.st_load()

    def build_apiaccess(self):
        self.view = "apiaccess"
        f = self.page()
        self.topbar(f, "Accès à l'API", lambda: self.show("settings", back=getattr(self, "settings_back", "main")))
        self.note(f, "Méthode utilisée par l'application pour joindre l'API de Mullvad. "
                     "* = activée. Touchez une méthode pour l'essayer et l'utiliser.")
        self.api_msg = ctk.CTkLabel(f, text="", text_color=WHITE60, wraplength=280, justify="left", anchor="w",
                                    font=fnt(12, False))
        self.api_msg.pack(side="bottom", fill="x", padx=18, pady=(0, 10))
        self.api_list = ctk.CTkScrollableFrame(f, fg_color=BG, corner_radius=0)
        self.api_list.pack(fill="both", expand=True, padx=6)
        self.bg(lambda: cli("api-access", "list"), self._api_loaded)

    def _api_loaded(self, res):
        if self.view != "apiaccess":
            return
        rc, out = res
        for w in self.api_list.winfo_children():
            w.destroy()
        if rc != 0:
            self.api_msg.configure(text=translate_error(out), text_color=ERR)
            return
        for ln in out.splitlines():
            m = re.match(r"\s*(\d+)\.\s*(.+?)\s*$", ln)
            if not m:
                continue
            idx, label = m.groups()
            row = ctk.CTkButton(self.api_list, text=label, anchor="w", height=44, corner_radius=6, fg_color=PANEL,
                                hover_color=PANEL_HOVER, font=fnt(14),
                                command=lambda i=idx: self.api_use(i))
            row.pack(fill="x", pady=2, padx=6)

    def api_use(self, idx):
        self.api_msg.configure(text="Essai de la méthode…", text_color=WHITE60)

        def done(res):
            if self.view == "apiaccess":
                ok = res[0] == 0
                self.api_msg.configure(text="Méthode d'accès appliquée." if ok else translate_error(res[1]),
                                       text_color=WHITE60 if ok else ERR)
        self.bg(lambda: cli("api-access", "use", idx), done)

    def build_support(self):
        self.view = "support"
        f = self.page()
        self.topbar(f, "Assistance", lambda: self.show("settings", back=getattr(self, "settings_back", "main")))
        g = ctk.CTkFrame(f, fg_color=PANEL, corner_radius=12)
        g.pack(fill="x", padx=16)
        self.row(g, "FAQ et guides", lambda: webbrowser.open("https://mullvad.net/help/tag/mullvad-app/"), chevron=True)
        ctk.CTkFrame(g, fg_color=DIVIDER, height=1, corner_radius=0).pack(fill="x")
        self.row(g, "Contacter l'assistance", lambda: webbrowser.open("https://mullvad.net/help/contact/"))

    def build_about(self):
        self.view = "about"
        f = self.page()
        self.topbar(f, "Infos sur l'application", lambda: self.show("settings", back=getattr(self, "settings_back", "main")))
        big = ctk_img(circle(self.logo, 192), (96, 96))
        ctk.CTkLabel(f, text="", image=big).pack(pady=(20, 8))
        ctk.CTkLabel(f, text=APP_NAME, font=fnt(22), text_color=INK).pack()
        ctk.CTkLabel(f, text="Mullvad CLI " + (self.cli_version or "—"), font=fnt(12, False),
                     text_color=WHITE60).pack(pady=(2, 12))
        ctk.CTkLabel(f, text="Client de bureau non officiel basé sur la ligne de commande de Mullvad VPN.",
                     wraplength=270, text_color=WHITE60, font=fnt(12, False)).pack(padx=20)

    def build_account(self):
        self.view = "account"
        f = self.page()
        ctk.CTkButton(f, text="", image=self.ic_back, width=32, height=32, fg_color="transparent", hover_color=BG,
                      command=lambda: self.show("main")).place(x=8, y=10)
        ctk.CTkLabel(f, text="Compte", font=fnt(30), text_color=INK).place(x=8, y=70, anchor="w")
        lab = dict(font=fnt(12, False), text_color=WHITE60)
        ctk.CTkLabel(f, text="Nom de l'appareil", **lab).place(x=8, y=108, anchor="w")
        self.dev_lbl = ctk.CTkLabel(f, text=self.acct.get("device") or "—", font=fnt(14), text_color=INK)
        self.dev_lbl.place(x=8, y=131, anchor="w")
        link = ctk.CTkLabel(f, text="Gérer les appareils", text_color=INK,
                            font=ctk.CTkFont(family=FONT_REG, size=13, underline=True))
        link.place(x=312, y=131, anchor="e")
        link.bind("<Button-1>", lambda e: self.show("devices", account=None, mode="manage"))
        ctk.CTkLabel(f, text="Numéro de compte", **lab).place(x=8, y=176, anchor="w")
        self.acc_shown = False
        self.acc_lbl = ctk.CTkLabel(f, text="•••• •••• •••• ••••", font=fnt(14), text_color=INK)
        self.acc_lbl.place(x=8, y=201, anchor="w")
        self.eye_btn = ctk.CTkButton(f, text="", image=self.ic_eye, width=32, height=32, fg_color="transparent",
                                     hover_color=PANEL, command=self.toggle_account_visibility)
        self.eye_btn.place(x=224, y=185)
        ctk.CTkButton(f, text="", image=self.ic_copy, width=32, height=32, fg_color="transparent", hover_color=PANEL,
                      command=self.copy_account).place(x=266, y=185)
        ctk.CTkLabel(f, text="Payé jusqu'au", **lab).place(x=8, y=250, anchor="w")
        self.paid_lbl = ctk.CTkLabel(f, text="…", font=fnt(14), text_color=INK)
        self.paid_lbl.place(x=8, y=272, anchor="w")
        self.acc_msg = ctk.CTkLabel(f, text="", font=fnt(12, False), text_color=ERR, wraplength=290,
                                    justify="left")
        self.acc_msg.place(x=8, y=380, anchor="w")
        ctk.CTkButton(f, text="Acheter plus de crédits", image=self.ic_ext, compound="right", height=32, width=304,
                      fg_color=GREEN, hover_color=GREEN_HOVER, font=fnt(14),
                      command=lambda: webbrowser.open("https://mullvad.net/account")
                      ).place(x=8, y=418)
        ctk.CTkButton(f, text="Échangez un bon", height=32, width=304, fg_color=GREEN, hover_color=GREEN_HOVER, font=fnt(14),
                      command=lambda: self.show("redeem")).place(x=8, y=464)
        ctk.CTkButton(f, text="Déconnexion", height=32, width=304, fg_color=RED, hover_color=RED_HOVER, font=fnt(14),
                      command=lambda: self.confirm("Se déconnecter ?", "Le VPN sera coupé et cet appareil sera "
                                                   "retiré de votre compte.", "Déconnexion", self.logout)
                      ).place(x=8, y=512)
        self._fill_account()
        self.bg(lambda: cli("account", "get"), self._show_account)

    def _fill_account(self):
        if self.view != "account":
            return
        self.dev_lbl.configure(text=self.acct.get("device") or "—")
        exp = self.acct.get("expiry")
        if exp:
            self.paid_lbl.configure(text=fmt_paid_until(exp), text_color=INK if exp > datetime.now() else ERR)

    def _show_account(self, res):
        info = parse_account(res[1])
        if info["state"] == "ok":
            self.acct = info
            self._fill_account()
        elif info["state"] in ("out", "revoked"):
            self._route_account(info, res[1])
        elif self.view == "account":
            self.acc_msg.configure(text=translate_error(res[1]))

    def toggle_account_visibility(self):
        self.acc_shown = not self.acc_shown
        d = self.acct.get("number", "")
        self.acc_lbl.configure(text=fmt_account(d) if self.acc_shown and d else "•••• •••• •••• ••••")
        self.eye_btn.configure(image=self.ic_eye_off if self.acc_shown else self.ic_eye)

    def copy_account(self):
        d = self.acct.get("number", "")
        if d:
            self.clipboard_clear()
            self.clipboard_append(d)
            self.acc_msg.configure(text="Numéro de compte copié.", text_color=WHITE60)

    def logout(self):
        def work():
            cli("disconnect")
            return cli("account", "logout")

        def done(res):
            if res[0] == 0:
                self.acct = {"number": "", "expiry": None, "device": ""}
                self.show("login")
            elif self.view == "account":
                self.acc_msg.configure(text=translate_error(res[1]), text_color=ERR)
        self.bg(work, done)

    def build_redeem(self):
        self.view = "redeem"
        f = self.page()
        self.topbar(f, "", lambda: self.show("account"))
        ctk.CTkLabel(f, text="Échangez un bon", font=fnt(26), text_color=INK, anchor="w"
                     ).pack(fill="x", padx=20, pady=(0, 6))
        self.note(f, "Saisissez le code de votre bon pour ajouter du temps à votre compte.")
        self.v_entry = ctk.CTkEntry(f, placeholder_text="XXXX-XXXX-XXXX-XXXX", height=44, fg_color=WHITE,
                                    text_color=INK, border_width=1, border_color="#D9C6C8", placeholder_text_color="#B79FA2", font=fnt(15))
        self.v_entry.pack(fill="x", padx=20)
        self.v_entry.bind("<Return>", lambda e: self.do_redeem())
        self.v_msg = ctk.CTkLabel(f, text="", font=fnt(12, False), text_color=ERR, wraplength=270,
                                  justify="left", anchor="w")
        self.v_msg.pack(fill="x", padx=20, pady=(8, 0))
        self.v_btn = ctk.CTkButton(f, text="Échanger", height=34, fg_color=GREEN, hover_color=GREEN_HOVER,
                                   font=fnt(14), command=self.do_redeem)
        self.v_btn.pack(fill="x", padx=20, pady=(8, 0))

    def do_redeem(self):
        code = re.sub(r"[^A-Za-z0-9]", "", self.v_entry.get())
        if not code:
            self.v_msg.configure(text="Saisissez un code de bon.", text_color=ERR)
            return
        self.v_btn.configure(state="disabled", text="Échange…")

        def done(res):
            if self.view != "redeem":
                return
            self.v_btn.configure(state="normal", text="Échanger")
            if res[0] == 0:
                self.v_msg.configure(text="Bon échangé : du temps a été ajouté à votre compte.", text_color=GREEN)
                self.bg(lambda: cli("account", "get"), lambda r: self.acct.update(parse_account(r[1]))
                        if parse_account(r[1])["state"] == "ok" else None)
            else:
                self.v_msg.configure(text=translate_error(res[1]), text_color=ERR)
        self.bg(lambda: cli("account", "redeem", code), done)

    def start_tray(self):
        if not pystray:
            return
        try:
            menu = pystray.Menu(
                pystray.MenuItem(f"Ouvrir {APP_NAME}", lambda i, it: self.q.put((self.toggle_window, ())), default=True),
                pystray.MenuItem(
                    lambda it: "Déconnexion" if self.vpn["state"] in ("connected", "connecting") else "Connexion",
                    lambda i, it: self.q.put((self.toggle_connection, ()))),
                pystray.MenuItem("Quitter", lambda i, it: self.q.put((self.quit_app, ()))),
            )
            self.tray = pystray.Icon("coonvad", tray_image(self.logo, self.vpn["state"]), APP_NAME, menu)
            threading.Thread(target=self.tray.run, daemon=True).start()
        except Exception:
            self.tray = None

    def update_tray(self):
        if not self.tray:
            return
        try:
            self.tray.icon = tray_image(self.logo, self.vpn["state"])
            label = {"connected": "Connecté", "connecting": "Connexion…", "disconnecting": "Déconnexion…",
                     "error": "Bloqué"}.get(self.vpn["state"], "Déconnecté")
            self.tray.title = f"{APP_NAME} - {label}"
            self.tray.update_menu()
        except Exception:
            pass

    def _place_bottom_right(self):
        try:
            sc = self._get_window_scaling()
        except Exception:
            sc = 1.0
        x0 = max(0, self.winfo_screenwidth() - int(W * sc) - 16)
        y0 = max(0, self.winfo_screenheight() - int(H * sc) - 16 - 40)
        tk.Wm.geometry(self, f"{W}x{H}+{x0}+{y0}")

    def show_window(self):
        self._place_bottom_right()
        self.deiconify()
        self.lift()
        self.focus_force()
        self.after(60, self._round_corners)

    def hide_window(self):
        self._hidden_at = time.time()
        self.withdraw()

    def toggle_window(self):
        if time.time() - self._hidden_at < 0.4:
            return
        if self.state() == "withdrawn":
            self.show_window()
        else:
            self.hide_window()

    def _on_focus_in(self, _e=None):
        self._armed = True

    def _on_focus_out(self, _e=None):
        if self.tray and self._armed and not self._no_autohide:
            self.after(150, self._autohide)

    def _autohide(self):
        try:
            if self.state() != "withdrawn" and not self.focus_displayof():
                self.hide_window()
        except Exception:
            pass

    def on_close(self):
        if self.tray and CFG.get("close_to_tray", True):
            self.hide_window()
        else:
            self.quit_app()

    def quit_app(self):
        self.running = False
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    first_run_autostart()
    App().mainloop()
