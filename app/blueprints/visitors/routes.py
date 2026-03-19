"""
Blueprint: Pengunjung (PATCH — fix nama_member)
────────────────────────────────────────────────
GET  /api/visitors         → Admin only
POST /api/visitors/manual  → Admin & Petugas

FIX: GET /visitors sebelumnya menggunakan select("*") pada tabel kunjungan
yang tidak memiliki kolom nama_member. Dashboard.jsx mengakses act.nama_member
yang selalu undefined, sehingga nama member tidak pernah tampil (hanya fallback "Member").

Perbaikan: gunakan PostgREST nested select untuk join tabel member secara inline.
Response sekarang menyertakan objek nested { member: { nama: "..." } } yang
diakses di Dashboard sebagai act.member?.nama.

Tidak ada perubahan schema — ini murni perubahan query di Flask.
"""

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, g

from app.extensions import supabase
from app.middleware.auth import admin_only, require_auth

visitors_bp = Blueprint("visitors", __name__)


# ── GET /visitors ─────────────────────────────────────────────────────────

@visitors_bp.route("/visitors", methods=["GET"])
@require_auth
def get_visitors():
    tanggal  = request.args.get("tanggal", "")
    event_id = request.args.get("event_id", "")
    tipe     = request.args.get("tipe_pengunjung", "")
    status   = request.args.get("status", "")

    try:
        # [FIX] Tambahkan PostgREST nested select: member:member_id(nama)
        # Ini mengambil nama member sekaligus tanpa query terpisah.
        # Response: { ..., member: { nama: "Budi Santoso" } } atau member: null untuk biasa
        query = (
            supabase.table("kunjungan")
            .select("*, member:member_id(nama)")
            .order("waktu_masuk", desc=True)
        )

        if event_id:
            query = query.eq("event_id", event_id)
        if tipe in ("member", "biasa"):
            query = query.eq("tipe_pengunjung", tipe)
        if status in ("di_dalam", "keluar"):
            query = query.eq("status", status)
        if tanggal:
            query = (
                query
                .gte("waktu_masuk", f"{tanggal}T00:00:00+07:00")
                .lte("waktu_masuk", f"{tanggal}T23:59:59+07:00")
            )

        result = query.execute()
        return jsonify({"status": "success", "data": result.data}), 200

    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


# ── POST /visitors/manual ─────────────────────────────────────────────────
# (tidak ada perubahan dari versi sebelumnya)

@visitors_bp.route("/visitors/manual", methods=["POST"])
@require_auth
def manual_visitor():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "status": "error",
            "message": "Field aksi dan event_id wajib diisi",
        }), 422

    aksi     = (data.get("aksi") or "").strip()
    event_id = (data.get("event_id") or "").strip()

    if aksi not in ("masuk", "keluar"):
        return jsonify({
            "status": "error",
            "message": "Field aksi harus berupa 'masuk' atau 'keluar'",
        }), 422

    if not event_id:
        return jsonify({
            "status": "error",
            "message": "Field aksi dan event_id wajib diisi",
        }), 422

    now = datetime.now(tz=timezone.utc).isoformat()

    try:
        if aksi == "masuk":
            result = (
                supabase.table("kunjungan")
                .insert({
                    "event_id":        event_id,
                    "member_id":       None,
                    "tipe_pengunjung": "biasa",
                    "waktu_masuk":     now,
                    "waktu_keluar":    None,
                    "status":          "di_dalam",
                    "dicatat_oleh":    g.user_id,
                })
                .execute()
            )
            message = "Pengunjung biasa masuk berhasil dicatat"

        else:
            find_res = (
                supabase.table("kunjungan")
                .select("id")
                .eq("event_id", event_id)
                .eq("tipe_pengunjung", "biasa")
                .eq("status", "di_dalam")
                .order("waktu_masuk")
                .limit(1)
                .execute()
            )

            if not find_res.data:
                return jsonify({
                    "status": "error",
                    "message": "Tidak ada pengunjung biasa yang sedang di dalam",
                }), 404

            kunjungan_id = find_res.data[0]["id"]
            result = (
                supabase.table("kunjungan")
                .update({"waktu_keluar": now})
                .eq("id", kunjungan_id)
                .execute()
            )
            message = "Pengunjung biasa keluar berhasil dicatat"

        if not result.data:
            return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500

        return jsonify({
            "status": "success",
            "message": message,
            "data": result.data[0],
        }), 201

    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500