# -*- coding: utf-8 -*-
# Kronos Oculus / Eye — occult_stuff_shh
# v1.1.1 (Kodi 21 Omega, LibreELEC-safe)
# Changes in v1.1.1:
# - If full moon toast fired and Saturn ingress is also due, wait 2.5s before Saturn toast.
#
# v1.1:
# - Abort-safe boot wait via xbmc.Monitor().waitForAbort(60)
# - Atomic JSON state writes (tmp + flush + fsync + os.replace)
# - Minimal logging + guarded I/O & notify try/except

import os
import datetime
import json
import xbmc
import xbmcvfs

# ===== Config / Constants =====
ADDON_ID = 'service.kronos.eye'
ADDON_DATA_PATH = xbmcvfs.translatePath(f'special://profile/addon_data/{ADDON_ID}')
DATA_FILE = os.path.join(ADDON_DATA_PATH, 'saturn_moon_status.txt')  # JSON content, kept .txt by design

# Hardcoded Saturn zodiac entry years (unchanged)
SATURN_ZODIAC_CYCLE = {
    2023: "Pisces",
    2025: "Aries",
    2028: "Taurus",
    2030: "Gemini",
    2033: "Cancer",
    2035: "Leo",
    2038: "Virgo",
    2040: "Libra",
    2043: "Scorpio",
    2045: "Sagittarius",
    2048: "Capricorn",
    2050: "Aquarius",
    2053: "Pisces",
    2055: "Aries",
    2058: "Taurus"
}

# ===== Boot wait (abort-safe) =====
def _boot_wait(seconds=60):
    mon = xbmc.Monitor()
    xbmc.log(f"[Kronos Eye] Boot wait {seconds}s (abort-safe) start", xbmc.LOGINFO)
    if mon.waitForAbort(seconds):
        xbmc.log("[Kronos Eye] Abort requested during boot wait. Exiting cleanly.", xbmc.LOGINFO)
        raise SystemExit

# ===== I/O helpers =====
def _ensure_dirs():
    try:
        if not os.path.exists(ADDON_DATA_PATH):
            os.makedirs(ADDON_DATA_PATH, exist_ok=True)
    except Exception as e:
        xbmc.log(f"[Kronos Eye] Failed to ensure data dir: {e}", xbmc.LOGERROR)

def load_status():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception as e:
        xbmc.log(f"[Kronos Eye] load_status error: {e}", xbmc.LOGERROR)
    return {}

def save_status(data: dict):
    tmp = DATA_FILE + ".tmp"
    try:
        with open(tmp, 'w') as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, DATA_FILE)  # atomic on same filesystem
        xbmc.log("[Kronos Eye] State saved atomically.", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[Kronos Eye] save_status error: {e}", xbmc.LOGERROR)
        # best-effort cleanup
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

# ===== Logic =====
def is_full_moon(date_obj: datetime.date) -> bool:
    """
    Coarse phase check:
    - Reference full moon: 2000-01-06
    - Synodic month: 29.53058867 days
    - 'Full' ≈ age 14.77 ± 0.5 days
    """
    try:
        known_full_moon = datetime.date(2000, 1, 6)
        lunar_cycle = 29.53058867
        days_passed = (date_obj - known_full_moon).days
        moon_age = days_passed % lunar_cycle
        is_full = abs(moon_age - 14.77) < 0.5
        xbmc.log(f"[Kronos Eye] Moon age={moon_age:.2f}d -> full={is_full}", xbmc.LOGINFO)
        return is_full
    except Exception as e:
        xbmc.log(f"[Kronos Eye] is_full_moon error: {e}", xbmc.LOGERROR)
        return False

def notify(title: str, message: str, icon_file: str):
    """
    Fire-and-forget Notification. Uses local icon path under the add-on folder.
    """
    try:
        addon_path = xbmcvfs.translatePath(f'special://home/addons/{ADDON_ID}')
        icon_path = os.path.join(addon_path, 'resources', 'media', icon_file)
        xbmc.executebuiltin(f'Notification({title},{message},10000,{icon_path})')
        xbmc.log(f"[Kronos Eye] Notified: {title} | {message} | icon={icon_file}", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[Kronos Eye] notify error: {e}", xbmc.LOGERROR)

# ===== Main =====
def main():
    xbmc.log("[Kronos Eye] v1.1.1 start", xbmc.LOGINFO)
    _boot_wait(60)

    _ensure_dirs()
    status = load_status()

    now = datetime.datetime.now()
    today = now.date()
    current_year = today.year

    updated = False
    fullmoon_fired = False  # track if first toast fired

    # Full Moon Notification (once per calendar day)
    try:
        last_full = status.get('last_fullmoon')
        if last_full != str(today):
            if is_full_moon(today):
                notify("[B]Kronos Eye[/B]", "Step into the light.", "fullmoon.png")
                status['last_fullmoon'] = str(today)
                updated = True
                fullmoon_fired = True
            else:
                xbmc.log("[Kronos Eye] Not full moon today; no toast.", xbmc.LOGINFO)
        else:
            xbmc.log("[Kronos Eye] Full moon already notified today; skipping.", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[Kronos Eye] Full moon block error: {e}", xbmc.LOGERROR)

    # Saturn Zodiac Ingress Notification (once per year in table)
    try:
        if current_year in SATURN_ZODIAC_CYCLE:
            if status.get('last_saturn_year') != current_year:
                if fullmoon_fired:
                    xbmc.log("[Kronos Eye] Staggering Saturn toast by 2.5s (full moon fired).", xbmc.LOGINFO)
                    xbmc.sleep(3000)  # stagger only when both are triggered in same run
                zodiac = SATURN_ZODIAC_CYCLE[current_year]
                notify("[B]Kronos Eye[/B]", f"Saturn has entered {zodiac}", "saturn.png")
                status['last_saturn_year'] = current_year
                updated = True
            else:
                xbmc.log("[Kronos Eye] Saturn ingress already notified this year; skipping.", xbmc.LOGINFO)
        else:
            xbmc.log("[Kronos Eye] No Saturn ingress configured for this year; skipping.", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[Kronos Eye] Saturn block error: {e}", xbmc.LOGERROR)

    if updated:
        save_status(status)
    else:
        xbmc.log("[Kronos Eye] No state changes; nothing to save.", xbmc.LOGINFO)

    xbmc.log("[Kronos Eye] v1.1.1 done (one-shot).", xbmc.LOGINFO)

if __name__ == '__main__':
    main()