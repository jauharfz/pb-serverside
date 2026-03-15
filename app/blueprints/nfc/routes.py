"""
Blueprint: NFC Tap
──────────────────
POST /api/tap  → REQ-NFC-001, REQ-NFC-002, REQ-NFC-003, REQ-NFC-004

Endpoint ini TIDAK memerlukan JWT karena dipanggil langsung
oleh NFC Reader 13.56 MHz melalui HTTP POST standar.
Keamanan dijamin via HTTPS/TLS (SDD §3.1.4).

Logika tap masuk/keluar ditentukan oleh fn_validate_nfc_uid():
  is_inside = False  →  Tap Masuk  (insert kunjungan baru)
  is_inside = True   →  Tap Keluar (update waktu_keluar)
"""

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.extensions import supabase

nfc_bp = Blueprint("nfc", __name__)


@nfc_bp.route("/tap", methods=["POST"])
def tap():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "status": "error",
            "message": "Format UID atau timestamp tidak valid",
        }), 422

    uid = (data.get("uid") or "").strip()
    timestamp_str = (data.get("timestamp") or "").strip()

    if not uid or not timestamp_str:
        return jsonify({
            "status": "error",
            "message": "Format UID atau timestamp tidak valid",
        }), 422

    # ── Validasi format timestamp ─────────────────────────────────────────
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        ts_iso = timestamp.isoformat()
    except ValueError:
        return jsonify({
            "status": "error",
            "message": "Format UID atau timestamp tidak valid",
        }), 422

    try:
        # ── 1. Validasi UID via database function ─────────────────────────
        validate_res = supabase.rpc("fn_validate_nfc_uid", {"p_uid": uid}).execute()

        if not validate_res.data:
            return jsonify({
                "status": "error",
                "message": "UID NFC tidak terdaftar dalam sistem",
            }), 404

        member = validate_res.data[0]

        if not member.get("is_valid"):
            return jsonify({
                "status": "error",
                "message": "UID NFC tidak terdaftar dalam sistem",
            }), 404

        member_id = member["member_id"]
        nama_member = member["nama"]

        # ── 2. Cari event aktif ──────────────────────────────────────────
        event_res = (
            supabase.table("event")
            .select("id, nama_event")
            .eq("status", "aktif")
            .limit(1)
            .execute()
        )

        if not event_res.data:
            return jsonify({
                "status": "error",
                "message": "Tidak ada event aktif saat ini",
            }), 404

        active_event = event_res.data[0]
        event_id = active_event["id"]

        # ── 3. Ambil admin sistem untuk field dicatat_oleh ───────────────
        admin_res = (
            supabase.table("admin")
            .select("id")
            .eq("role", "admin")
            .limit(1)
            .execute()
        )

        if not admin_res.data:
            return jsonify({
                "status": "error",
                "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
            }), 500

        dicatat_oleh = admin_res.data[0]["id"]

        # ── 4. Tap masuk atau keluar ─────────────────────────────────────
        is_inside = member.get("is_inside", False)

        if not is_inside:
            # ── TAP MASUK: insert kunjungan baru ─────────────────────────
            insert_res = (
                supabase.table("kunjungan")
                .insert({
                    "event_id": event_id,
                    "member_id": member_id,
                    "tipe_pengunjung": "member",
                    "waktu_masuk": ts_iso,
                    "waktu_keluar": None,
                    "status": "di_dalam",
                    "dicatat_oleh": dicatat_oleh,
                })
                .execute()
            )

            if not insert_res.data:
                return jsonify({
                    "status": "error",
                    "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
                }), 500

            k = insert_res.data[0]
            return jsonify({
                "status": "success",
                "message": "Tap masuk berhasil dicatat",
                "data": {
                    "kunjungan_id": k["id"],
                    "event_id": event_id,
                    "member_id": member_id,
                    "nama_member": nama_member,
                    "aksi": "masuk",
                    "waktu_masuk": k["waktu_masuk"],
                    "waktu_keluar": None,
                    "status": "di_dalam",
                },
            }), 200

        else:
            # ── TAP KELUAR: update kunjungan yang masih di_dalam ─────────
            update_res = (
                supabase.table("kunjungan")
                .update({"waktu_keluar": ts_iso})
                .eq("member_id", member_id)
                .eq("event_id", event_id)
                .eq("status", "di_dalam")
                .execute()
            )

            if not update_res.data:
                return jsonify({
                    "status": "error",
                    "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
                }), 500

            k = update_res.data[0]
            return jsonify({
                "status": "success",
                "message": "Tap keluar berhasil dicatat",
                "data": {
                    "kunjungan_id": k["id"],
                    "event_id": event_id,
                    "member_id": member_id,
                    "nama_member": nama_member,
                    "aksi": "keluar",
                    "waktu_masuk": k["waktu_masuk"],
                    "waktu_keluar": k["waktu_keluar"],
                    "status": "keluar",
                },
            }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
        }), 500
