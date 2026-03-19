"""
Blueprint: NFC Tap (OPTIMIZED)
───────────────────────────────
POST /api/tap  → REQ-NFC-001, REQ-NFC-002, REQ-NFC-003, REQ-NFC-004

Endpoint ini TIDAK memerlukan JWT karena dipanggil langsung
oleh NFC Reader 13.56 MHz melalui HTTP POST standar.
Keamanan dijamin via HTTPS/TLS.

OPTIMASI vs versi sebelumnya:
  - Versi lama: 4 query DB berurutan setiap tap (validate + event + admin + write)
  - Versi baru: cache module-level untuk event aktif dan admin_id
    → warm request hanya butuh 2 DB calls (validate + write)
  - Ini penting di free tier HuggingFace (cold start + throttling)
    yang menyebabkan tap "kadang berhasil kadang tidak"

Cache invalidation:
  - _CACHED_EVENT di-reset jika insert gagal (event mungkin sudah tidak aktif)
  - _CACHED_ADMIN_ID jarang berubah, di-reset jika None saat dibutuhkan
"""

from datetime import datetime, timezone, timedelta

from flask import Blueprint, jsonify, request

from app.extensions import supabase

nfc_bp = Blueprint("nfc", __name__)

# ── Module-level cache (per Gunicorn worker, reset saat restart) ──────────────
# Mengurangi jumlah DB call dari 4 → 2 per tap pada warm request.
# TTL 60 detik: memastikan perubahan event aktif dari dashboard
# terefleksi dalam 1 menit tanpa menunggu error/restart.

_CACHE_TTL = timedelta(seconds=60)

_CACHED_EVENT      = None   # {"id": "...", "nama_event": "..."}
_CACHED_EVENT_AT   = None   # datetime UTC saat cache diisi
_CACHED_ADMIN_ID   = None   # UUID string


def _get_active_event():
    """Ambil event aktif. Gunakan cache jika masih dalam TTL."""
    global _CACHED_EVENT, _CACHED_EVENT_AT
    now = datetime.now(tz=timezone.utc)
    if _CACHED_EVENT and _CACHED_EVENT_AT and (now - _CACHED_EVENT_AT) < _CACHE_TTL:
        return _CACHED_EVENT
    res = (
        supabase.table("event")
        .select("id, nama_event")
        .eq("status", "aktif")
        .limit(1)
        .execute()
    )
    if res.data:
        _CACHED_EVENT    = res.data[0]
        _CACHED_EVENT_AT = now
    else:
        _CACHED_EVENT    = None
        _CACHED_EVENT_AT = None
    return _CACHED_EVENT


def _get_admin_id():
    """Ambil admin ID pertama. Gunakan cache jika tersedia."""
    global _CACHED_ADMIN_ID
    if _CACHED_ADMIN_ID:
        return _CACHED_ADMIN_ID
    res = (
        supabase.table("admin")
        .select("id")
        .eq("role", "admin")
        .limit(1)
        .execute()
    )
    if res.data:
        _CACHED_ADMIN_ID = res.data[0]["id"]
    return _CACHED_ADMIN_ID


def _invalidate_event_cache():
    global _CACHED_EVENT, _CACHED_EVENT_AT
    _CACHED_EVENT    = None
    _CACHED_EVENT_AT = None


# ── Tap Endpoint ──────────────────────────────────────────────────────────────

@nfc_bp.route("/tap", methods=["POST"])
def tap():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "status": "error",
            "message": "Format UID atau timestamp tidak valid",
        }), 422

    uid           = (data.get("uid")       or "").strip()
    timestamp_str = (data.get("timestamp") or "").strip()

    if not uid or not timestamp_str:
        return jsonify({
            "status": "error",
            "message": "Format UID atau timestamp tidak valid",
        }), 422

    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        ts_iso    = timestamp.isoformat()
    except ValueError:
        return jsonify({
            "status": "error",
            "message": "Format UID atau timestamp tidak valid",
        }), 422

    try:
        # ── 1. Validasi UID via RPC (selalu fresh, tidak di-cache) ────────
        validate_res = supabase.rpc("fn_validate_nfc_uid", {"p_uid": uid}).execute()

        if not validate_res.data or not validate_res.data[0].get("is_valid"):
            return jsonify({
                "status": "error",
                "message": "UID NFC tidak terdaftar dalam sistem",
            }), 404

        member      = validate_res.data[0]
        member_id   = member["member_id"]
        nama_member = member["nama"]
        is_inside   = member.get("is_inside", False)

        # ── 2. Event aktif (dari cache) ───────────────────────────────────
        active_event = _get_active_event()
        if not active_event:
            return jsonify({
                "status": "error",
                "message": "Tidak ada event aktif saat ini",
            }), 404
        event_id = active_event["id"]

        # ── 3. Admin ID (dari cache) ──────────────────────────────────────
        dicatat_oleh = _get_admin_id()
        if not dicatat_oleh:
            return jsonify({
                "status": "error",
                "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
            }), 500

        # ── 4. Tap masuk atau keluar ──────────────────────────────────────
        if not is_inside:
            insert_res = (
                supabase.table("kunjungan")
                .insert({
                    "event_id":        event_id,
                    "member_id":       member_id,
                    "tipe_pengunjung": "member",
                    "waktu_masuk":     ts_iso,
                    "waktu_keluar":    None,
                    "status":          "di_dalam",
                    "dicatat_oleh":    dicatat_oleh,
                })
                .execute()
            )

            if not insert_res.data:
                # Insert gagal: event mungkin sudah tidak aktif, reset cache
                _invalidate_event_cache()
                return jsonify({
                    "status": "error",
                    "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
                }), 500

            k = insert_res.data[0]
            return jsonify({
                "status":  "success",
                "message": "Tap masuk berhasil dicatat",
                "data": {
                    "kunjungan_id": k["id"],
                    "event_id":     event_id,
                    "member_id":    member_id,
                    "nama_member":  nama_member,
                    "aksi":         "masuk",
                    "waktu_masuk":  k["waktu_masuk"],
                    "waktu_keluar": None,
                    "status":       "di_dalam",
                },
            }), 200

        else:
            update_res = (
                supabase.table("kunjungan")
                .update({"waktu_keluar": ts_iso, "status": "keluar"})
                .eq("member_id", member_id)
                .eq("event_id",  event_id)
                .eq("status",    "di_dalam")
                .execute()
            )

            if not update_res.data:
                # Update gagal: event mungkin sudah berganti, reset cache
                _invalidate_event_cache()
                return jsonify({
                    "status": "error",
                    "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
                }), 500

            k = update_res.data[0]
            return jsonify({
                "status":  "success",
                "message": "Tap keluar berhasil dicatat",
                "data": {
                    "kunjungan_id": k["id"],
                    "event_id":     event_id,
                    "member_id":    member_id,
                    "nama_member":  nama_member,
                    "aksi":         "keluar",
                    "waktu_masuk":  k["waktu_masuk"],
                    "waktu_keluar": k["waktu_keluar"],
                    "status":       "keluar",
                },
            }), 200

    except Exception:
        # Exception tak terduga: reset cache event sebagai precaution
        _invalidate_event_cache()
        return jsonify({
            "status": "error",
            "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
        }), 500