#!/usr/bin/env python3
"""Export cookies from a copied Edge/Chrome profile into Playwright cookie JSON.

Usage: python tools/export_edge_cookies.py --profile data/edge_profile --hosts script.google.com --out data/cookies.json
"""
import argparse
import base64
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

def dpapi_decrypt(encrypted: bytes) -> bytes:
    # Use Windows CryptUnprotectData via ctypes to decrypt DPAPI blobs
    import ctypes
    from ctypes import wintypes

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    blob_in = DATA_BLOB()
    blob_in.cbData = len(encrypted)
    blob_in.pbData = ctypes.cast(ctypes.create_string_buffer(encrypted), ctypes.POINTER(ctypes.c_char))

    blob_out = DATA_BLOB()
    if crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)) == 0:
        raise RuntimeError("CryptUnprotectData failed")

    ptr = ctypes.cast(blob_out.pbData, ctypes.POINTER(ctypes.c_char * blob_out.cbData))
    result = bytes(ptr.contents)
    kernel32.LocalFree(blob_out.pbData)
    return result

def get_master_key(profile_path: str) -> bytes:
    local_state = Path(profile_path) / "Local State"
    with open(local_state, "r", encoding="utf8") as f:
        data = json.load(f)
    encrypted_key_b64 = data["os_crypt"]["encrypted_key"]
    encrypted_key = base64.b64decode(encrypted_key_b64)
    # remove "DPAPI" prefix if present
    if encrypted_key[:5] == b"DPAPI":
        encrypted_key = encrypted_key[5:]
    return dpapi_decrypt(encrypted_key)

def decrypt_value(enc_value: bytes, master_key: bytes) -> str:
    # Chrome/Edge new format starts with v10 and is AES-GCM, otherwise DPAPI
    if not enc_value:
        return ""
    if enc_value.startswith(b"v10"):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        iv = enc_value[3:3+12]
        ciphertext = enc_value[3+12:]
        aesgcm = AESGCM(master_key)
        try:
            decrypted = aesgcm.decrypt(iv, ciphertext, None)
            return decrypted.decode("utf8", errors="ignore")
        except Exception:
            return ""
    else:
        try:
            dec = dpapi_decrypt(enc_value)
            return dec.decode("utf8", errors="ignore")
        except Exception:
            return ""

def export_cookies(profile_path: str, hosts: list, out_path: str):
    profile = Path(profile_path)
    cookies_db = profile / "Cookies"
    if not cookies_db.exists():
        # search for Cookies file recursively (some Edge/Chrome versions store it under Network/)
        cookies_db = None
        for root, dirs, files in os.walk(profile_path):
            for fname in files:
                if fname.lower() == "cookies":
                    cookies_db = Path(root) / fname
                    break
            if cookies_db:
                break
        if not cookies_db:
            raise FileNotFoundError(f"Cookies DB not found under {profile_path}")

    master_key = get_master_key(profile_path)

    # copy DB to temp to avoid lock
    tmp = tempfile.mkdtemp()
    tmp_db = Path(tmp) / "Cookies"
    shutil.copy2(cookies_db, tmp_db)

    conn = sqlite3.connect(str(tmp_db))
    cur = conn.cursor()

    # build query for hosts
    placeholders = ",".join(["?" for _ in hosts])
    query = f"SELECT host_key, name, path, expires_utc, is_httponly, is_secure, samesite, encrypted_value FROM cookies WHERE " \
            f"(" + " OR ".join([f"host_key LIKE '%' || ? || '%'" for _ in hosts]) + ")"

    cur.execute(query, hosts)
    rows = cur.fetchall()

    cookies = []
    for host_key, name, path, expires_utc, is_httponly, is_secure, samesite, encrypted_value in rows:
        if encrypted_value is None:
            value = ""
        else:
            if isinstance(encrypted_value, memoryview):
                ev = encrypted_value.tobytes()
            else:
                ev = encrypted_value
            value = decrypt_value(ev, master_key)

        # convert Chromium/Edge expires_utc (microseconds since 1601-01-01) to UNIX seconds
        if expires_utc is None or expires_utc == 0:
            expires = 0
        else:
            try:
                expires = int(expires_utc / 1000000 - 11644473600)
            except Exception:
                expires = int(expires_utc)

        cookie = {
            "name": name,
            "value": value,
            "domain": host_key,
            "path": path,
            "expires": expires,
            "httpOnly": bool(is_httponly),
            "secure": bool(is_secure),
            "sameSite": "Lax" if samesite == 1 else ("Strict" if samesite == 2 else "None"),
        }
        cookies.append(cookie)

    with open(out_path, "w", encoding="utf8") as f:
        json.dump(cookies, f, indent=2)

    conn.close()
    shutil.rmtree(tmp)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, help="Path to copied Edge profile folder")
    ap.add_argument("--hosts", required=True, help="Comma-separated host substrings to export (e.g. script.google.com)")
    ap.add_argument("--out", required=True, help="Output JSON file for Playwright cookies")
    args = ap.parse_args()

    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
    export_cookies(args.profile, hosts, args.out)
    print(f"Exported cookies for {hosts} to {args.out}")

if __name__ == "__main__":
    main()
