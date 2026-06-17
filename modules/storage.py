import json
import os
import threading
from datetime import date, datetime

_DATA_FILE = "data.json"

FREE_DAILY       = 1
PREMIUM_DAILY    = 50
COOLDOWN_SECONDS = 60
TEMPLATE_COUNT   = 3

_data: dict = {"users": {}, "template_counter": 0}
_lock = threading.Lock()

def _load() -> None:
    global _data
    if os.path.exists(_DATA_FILE):
        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                _data = json.load(f)
        except Exception:
            _data = {"users": {}, "template_counter": 0}
    _data.setdefault("template_counter", 0)
    _data.setdefault("users", {})

def _save() -> None:
    with _lock:
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(_data, f, ensure_ascii=False, indent=2)

_load()

def _user(user_id: int) -> dict:
    key = str(user_id)
    if key not in _data["users"]:
        _data["users"][key] = {}
    return _data["users"][key]

def get_email(user_id: int) -> dict | None:
    u = _user(user_id)
    if "email" not in u:
        return None
    return {"email": u["email"], "password": u["password"]}

def set_email(user_id: int, email: str, password: str) -> None:
    u = _user(user_id)
    u["email"]      = email
    u["password"]   = password
    u["is_used"]    = False
    u["created_at"] = datetime.now().timestamp()
    _save()

def mark_used(user_id: int) -> None:
    u = _user(user_id)
    u["is_used"] = True
    _save()

def is_used(user_id: int) -> bool:
    return _user(user_id).get("is_used", False)

def delete_email(user_id: int) -> None:
    u = _user(user_id)
    for key in ("email", "password", "template_index", "is_used", "created_at"):
        u.pop(key, None)
    _save()

def has_email(user_id: int) -> bool:
    return "email" in _user(user_id)

def is_premium(user_id: int) -> bool:
    return bool(_user(user_id).get("premium", False))

def set_premium(user_id: int, value: bool) -> None:
    _user(user_id)["premium"] = value
    _save()

def get_max_daily(user_id: int) -> int:
    return PREMIUM_DAILY if is_premium(user_id) else FREE_DAILY

def assign_template(user_id: int) -> int:
    idx = _data["template_counter"] % TEMPLATE_COUNT
    _data["template_counter"] += 1
    _user(user_id)["template_index"] = idx
    _save()
    return idx

def get_template_index(user_id: int) -> int:
    idx = _user(user_id).get("template_index", 0)
    if idx >= TEMPLATE_COUNT:
        idx = 0
        _user(user_id)["template_index"] = idx
        _save()
    return idx

def can_send(user_id: int) -> tuple[bool, str]:
    today = str(date.today())
    now   = datetime.now().timestamp()
    u     = _user(user_id)
    rl    = u.get("rate_limit", {"date": "", "count": 0, "last_send": 0})
    
    if rl.get("date") != today:
        rl = {"date": today, "count": 0, "last_send": 0}
        
    elapsed = now - rl.get("last_send", 0)
    if elapsed < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - elapsed)
        return False, f"┌─〔 ⊗ **AKSES DITOLAK** 〕─┐\n│\n├─ ◈ **Status** : `JEDA WAKTU`\n├─ ◈ **Waktu** : `{remaining} dtk`\n│\n└─〔 **Sistem Terkunci** 〕─┘"
        
    max_daily = get_max_daily(user_id)
    tier      = "**PREMIUM**" if is_premium(user_id) else "**TAMU**"
    
    if rl.get("count", 0) >= max_daily:
        return False, f"┌─〔 ⊗ **AKSES TERBATAS** 〕─┐\n│\n├─ ◈ **Lisensi** : {tier}\n├─ ◈ **Kuota** : `{max_daily}/{max_daily}`\n│\n└─〔 **Reset Dalam 24 Jam** 〕─┘"
        
    return True, ""

def log_send(user_id: int) -> None:
    today = str(date.today())
    now   = datetime.now().timestamp()
    u     = _user(user_id)
    rl    = u.get("rate_limit", {"date": "", "count": 0, "last_send": 0})
    
    if rl.get("date") != today:
        rl = {"date": today, "count": 0, "last_send": 0}
        
    rl["count"]     = rl.get("count", 0) + 1
    rl["last_send"] = now
    u["rate_limit"] = rl
    _save()

def get_send_count(user_id: int) -> int:
    today = str(date.today())
    u     = _user(user_id)
    rl    = u.get("rate_limit", {})
    if rl.get("date") != today:
        return 0
    return rl.get("count", 0)

def get_expired_or_used_accounts() -> list:
    now = datetime.now().timestamp()
    expired = []
    with _lock:
        for uid, u_data in list(_data["users"].items()):
            if "email" in u_data:
                created_at = u_data.get("created_at", now)
                is_used = u_data.get("is_used", False)
                if is_used or (now - created_at > 86400):
                    expired.append((int(uid), u_data["email"]))
    return expired

def get_all_users() -> list:
    with _lock:
        return list(_data["users"].keys())

def get_global_metrics() -> dict:
    today = str(date.today())
    total_users = len(_data["users"])
    premium_count = 0
    sends_today = 0
    with _lock:
        for u_data in _data["users"].values():
            if u_data.get("premium"):
                premium_count += 1
            rl = u_data.get("rate_limit", {})
            if rl.get("date") == today:
                sends_today += rl.get("count", 0)
    return {
        "total_users": total_users,
        "premium_users": premium_count,
        "guest_users": total_users - premium_count,
        "sends_today": sends_today
    }
