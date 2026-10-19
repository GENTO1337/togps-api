import json
import os
import time
from urllib.parse import quote

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://iuthmyruvnxuvomobtum.supabase.co")
PUBLISHABLE_KEY = os.getenv(
    "PUBLISHABLE_KEY",
    "sb_publishable_WvAc-cIdwqXj8jLGHS6cjg_PlKY9-pD",
)
EMAIL = os.getenv("TOGPS_EMAIL", "tikanoviya074@gmail.com")
PASSWORD = os.getenv("TOGPS_PASSWORD", "Togps2026Ops!")
TOGPS_ACCOUNTS = os.getenv(
    "TOGPS_ACCOUNTS",
    "tikanoviya074@gmail.com:Togps2026Ops!,tikanoviya074+ops2@gmail.com:TogpsBackup2#26",
)
API_KEY = os.getenv("API_KEY", "")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"

FN_RUNSEARCH = "008e0fe9f532059196cf5ca3eb37b4056ff9317f4ef99c9eb866669a698617e6"
FN_STATUS = "43aaf67487bf713a01c288e12cbb11082cc340efa7bfadc1a4be910d6608efda"
FN_HISTORY = "d3a8c2093dcd9bb6004fbe39a1c849a6e50f9e0bc689b5203311befb518fa466"
FN_CASE_LIST = "6680f613726d90780d06f6a675ba455670b94de0548f38bc14b0324f0ead6337"
FN_CASE_CREATE = "09914671bd21fcf5b767ff043e5d3524cb79abae8e9c60b75245518b68e52276"
FN_CASE_DETAIL = "3513532342afed1e9b4bdf3c978499016b975d23f36f00791dc14aa22e555057"

ENDPOINTS = {
    "cek_nik": "cek_nik",
    "nikfoto": "nikfoto",
    "cek_nama": "cek_nama",
    "getcontact": "getcontact",
    "nopol": "nopol",
    "nik2kk": "nik2kk",
    "kk": "kk",
    "data_bocor": "data-bocor",
    "kesehatan": "kesehatan",
}

_session = {"access_token": None, "refresh_token": None, "expires_at": 0}
_cache = {}

_accounts = []
for _pair in TOGPS_ACCOUNTS.split(","):
    _e, _sep, _p = _pair.strip().partition(":")
    if _e and _p:
        _accounts.append((_e, _p))
if not _accounts:
    _accounts.append((EMAIL, PASSWORD))
_account_idx = 0


def ser_str(s):
    return {"s": s, "t": 1}


def ser_num(n):
    return {"s": n, "t": 0}


def ser_bool(b):
    return {"s": 2 if b else 3, "t": 2}


def ser_obj(d):
    return {"o": 0, "t": 10, "p": {"v": list(d.values()), "k": list(d.keys())}, "i": 0}


def encode_value(v):
    if isinstance(v, dict):
        return ser_obj({k: encode_value(x) for k, x in v.items()})
    if isinstance(v, bool):
        return ser_bool(v)
    if isinstance(v, str):
        return ser_str(v)
    if isinstance(v, (int, float)):
        return ser_num(v)
    return ser_str(str(v))


def encode_payload(data):
    tree = ser_obj({"data": encode_value(data)})
    return {"m": [], "t": tree, "f": 127}


def decode(v):
    if not isinstance(v, dict):
        return v
    t = v.get("t")
    if t == 0:
        return v.get("s")
    if t == 1:
        return v.get("s")
    if t == 2:
        return {0: None, 1: None, 2: True, 3: False}.get(v.get("s"))
    if t == 9:
        return [decode(x) for x in v.get("a", [])]
    if t == 10 or t == 11:
        keys = v.get("p", {}).get("k", [])
        vals = [decode(x) for x in v.get("p", {}).get("v", [])]
        return dict(zip(keys, vals))
    if t == 25:
        return {"__error__": decode(v.get("s"))}
    return None


def login():
    global _account_idx
    last_err = None
    for i in range(len(_accounts)):
        email, password = _accounts[(_account_idx + i) % len(_accounts)]
        try:
            r = requests.post(
                f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
                headers={"apikey": PUBLISHABLE_KEY, "Content-Type": "application/json"},
                json={"email": email, "password": password},
                timeout=30,
            )
            r.raise_for_status()
            d = r.json()
            _session.update(
                access_token=d["access_token"],
                refresh_token=d.get("refresh_token"),
                expires_at=d.get("expires_at", time.time() + 3600),
            )
            _account_idx = (_account_idx + i) % len(_accounts)
            return
        except Exception as e:
            last_err = e
    raise RuntimeError(f"semua akun gagal login: {last_err}")


def refresh():
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
        headers={"apikey": PUBLISHABLE_KEY, "Content-Type": "application/json"},
        json={"refresh_token": _session["refresh_token"]},
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    _session.update(
        access_token=d["access_token"],
        refresh_token=d.get("refresh_token"),
        expires_at=d.get("expires_at", time.time() + 3600),
    )


def ensure_session():
    if not _session["access_token"] or time.time() > _session["expires_at"] - 60:
        if _session["refresh_token"]:
            try:
                refresh()
                return
            except Exception:
                pass
        login()


def call_fn(fn_hash, data=None, method="POST"):
    ensure_session()
    url = f"https://ai.togps.id/_serverFn/{fn_hash}"
    headers = {
        "x-tsr-serverFn": "true",
        "accept": "application/x-tss-framed, application/x-ndjson, application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {_session['access_token']}",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": UA,
    }
    if method == "GET":
        if data is not None:
            url += "?payload=" + quote(json.dumps(encode_payload(data), separators=(",", ":")))
        r = requests.get(url, headers=headers, timeout=60)
    else:
        body = None if data is None else json.dumps(encode_payload(data), separators=(",", ":"))
        r = requests.post(url, headers=headers, data=body, timeout=90)
    if r.status_code == 403:
        raise RuntimeError("403 Forbidden dari server target")
    env = r.json()
    keys = env.get("p", {}).get("k", [])
    vals = [decode(x) for x in env.get("p", {}).get("v", [])]
    res = dict(zip(keys, vals))
    err = res.get("error")
    if isinstance(err, dict) and "__error__" in err:
        msg = err["__error__"].get("message", "unknown error")
        raise RuntimeError(msg)
    return res.get("result")


def search(endpoint, query):
    key = (endpoint, query)
    if key in _cache:
        out = dict(_cache[key])
        out["cached"] = True
        return out
    result = call_fn(FN_RUNSEARCH, {"endpoint": endpoint, "query": query}) or {}
    payload = result.get("json") or ""
    try:
        payload = json.loads(payload.replace('\\"', '"'))
    except Exception:
        payload = payload
    out = {
        "endpoint": endpoint,
        "query": query,
        "ok": result.get("ok") is True,
        "result": payload,
        "error": result.get("error") or "",
        "ms": result.get("ms"),
        "tokens_remaining": payload.get("tokens_remaining") if isinstance(payload, dict) else None,
        "cached": False,
    }
    if out["ok"]:
        _cache[key] = dict(out)
    return out


def guard():
    if API_KEY:
        if request.args.get("key") != API_KEY and request.headers.get("X-API-Key") != API_KEY:
            return False
    return True


@app.route("/")
def index():
    return jsonify(
        {
            "name": "TOGPS IntelID API clone",
            "endpoints": sorted(ENDPOINTS.keys()),
            "extra": ["status", "quota", "riwayat", "kasus"],
        }
    )


@app.route("/api/search/<ep>")
def api_search(ep):
    if not guard():
        return jsonify({"error": "invalid key"}), 401
    if ep not in ENDPOINTS:
        return jsonify({"error": "unknown endpoint", "valid": sorted(ENDPOINTS.keys())}), 404
    q = request.args.get("q") or request.args.get("query") or ""
    if not q.strip():
        return jsonify({"error": "query wajib diisi (?q=...)"}), 400
    try:
        return jsonify(search(ENDPOINTS[ep], q.strip()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/cek_nik")
def api_cek_nik():
    return api_search("cek_nik")


@app.route("/api/nikfoto")
def api_nikfoto():
    return api_search("nikfoto")


@app.route("/api/cek_nama")
def api_cek_nama():
    return api_search("cek_nama")


@app.route("/api/getcontact")
def api_getcontact():
    return api_search("getcontact")


@app.route("/api/nopol")
def api_nopol():
    return api_search("nopol")


@app.route("/api/nik2kk")
def api_nik2kk():
    return api_search("nik2kk")


@app.route("/api/kk")
def api_kk():
    return api_search("kk")


@app.route("/api/data_bocor")
def api_data_bocor():
    return api_search("data_bocor")


@app.route("/api/kesehatan")
def api_kesehatan():
    return api_search("kesehatan")


@app.route("/api/status")
def api_status():
    if not guard():
        return jsonify({"error": "invalid key"}), 401
    try:
        return jsonify(call_fn(FN_STATUS, data=None, method="GET"))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/quota")
def api_quota():
    if not guard():
        return jsonify({"error": "invalid key"}), 401
    try:
        ensure_session()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/service_settings?select=quota_remaining,quota_updated_at,quota_source",
            headers={
                "apikey": PUBLISHABLE_KEY,
                "Authorization": f"Bearer {_session['access_token']}",
            },
            timeout=30,
        )
        rows = r.json()
        return jsonify({"quota": rows[0] if rows else None})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/riwayat")
def api_riwayat():
    if not guard():
        return jsonify({"error": "invalid key"}), 401
    try:
        limit = int(request.args.get("limit", "10"))
        limit = max(1, min(limit, 50))
        rows = call_fn(FN_HISTORY, limit, method="GET")
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/kasus", methods=["GET", "POST"])
def api_kasus():
    if not guard():
        return jsonify({"error": "invalid key"}), 401
    try:
        if request.method == "GET":
            return jsonify(call_fn(FN_CASE_LIST, data=None, method="GET"))
        d = request.get_json(silent=True) or {}
        title = d.get("title") or ""
        description = d.get("description") or ""
        if not title.strip():
            return jsonify({"error": "title wajib"}), 400
        return jsonify(call_fn(FN_CASE_CREATE, {"title": title.strip(), "description": description.strip()}))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/kasus/<case_id>")
def api_kasus_detail(case_id):
    if not guard():
        return jsonify({"error": "invalid key"}), 401
    try:
        return jsonify(call_fn(FN_CASE_DETAIL, {"id": case_id}))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
