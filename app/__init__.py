import sys
import logging
import re
from datetime import date

from flask import Flask, jsonify, request
from flask_cors import CORS
from app.config import Config

logging.basicConfig(
    stream=sys.stderr,
    level=logging.DEBUG,
    format="[%(levelname)s] %(name)s: %(message)s",
)
_log = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ── Blueprints ────────────────────────────────────────────────────────
    from app.blueprints.auth.routes      import auth_bp
    from app.blueprints.nfc.routes       import nfc_bp
    from app.blueprints.members.routes   import members_bp
    from app.blueprints.visitors.routes  import visitors_bp
    from app.blueprints.dashboard.routes import dashboard_bp
    from app.blueprints.reports.routes   import reports_bp
    from app.blueprints.discounts.routes import discounts_bp
    from app.blueprints.umkm.routes      import umkm_bp

    app.register_blueprint(auth_bp,      url_prefix="/api/auth")
    app.register_blueprint(nfc_bp,       url_prefix="/api")
    app.register_blueprint(members_bp,   url_prefix="/api")
    app.register_blueprint(visitors_bp,  url_prefix="/api")
    app.register_blueprint(dashboard_bp, url_prefix="/api")
    app.register_blueprint(reports_bp,   url_prefix="/api")
    app.register_blueprint(discounts_bp, url_prefix="/api")
    app.register_blueprint(umkm_bp,      url_prefix="/api")

    # ── Events blueprint (REQ-EVENT-001) ──────────────────────────────────
    # Dicoba import dari package. Jika gagal (mis. file belum di-push ke server),
    # routes didaftarkan inline sebagai fallback — identik dengan routes_events.py.
    try:
        from app.blueprints.events.routes import events_bp
        app.register_blueprint(events_bp, url_prefix="/api")
        _log.info("events_bp berhasil didaftarkan dari app.blueprints.events.routes")

    except Exception as exc:
        _log.error("GAGAL import events_bp: %s", exc, exc_info=True)
        _log.warning("Mendaftarkan events routes secara inline sebagai fallback.")

        # ── Inline fallback: sinkron dengan blueprints/events/routes.py ──────
        # Aturan bisnis yang harus sama persis:
        #   - POST: tanggal hari ini → aktif, masa depan → selesai, deactivate lain
        #   - PATCH: deteksi dari body — 'status' → toggle, field lain → edit
        #     Toggle aktif: hanya boleh jika tanggal <= hari ini
        #     Edit tanggal: tidak boleh jika event sedang aktif
        #     Tanggal diubah: auto-status berdasarkan tanggal baru
        #   - DELETE: tolak jika aktif; biarkan FK RESTRICT tangani jika ada kunjungan

        from app.extensions import supabase
        from app.middleware.auth import admin_only

        _DATE_RE_INLINE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

        def _today_inline():
            return date.today().isoformat()

        def _deactivate_others_inline(exclude_id=None):
            q = supabase.table("event").update({"status": "selesai"}).eq("status", "aktif")
            if exclude_id:
                q = q.neq("id", exclude_id)
            q.execute()

        @app.route("/api/events", methods=["GET"])
        @admin_only
        def get_events():
            try:
                result = (
                    supabase.table("event")
                    .select("*")
                    .order("status", desc=False)
                    .order("tanggal", desc=True)
                    .execute()
                )
                return jsonify({"status": "success", "data": result.data or []}), 200
            except Exception:
                return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500

        @app.route("/api/events", methods=["POST"])
        @admin_only
        def create_event():
            body       = request.get_json(silent=True) or {}
            nama_event = (body.get("nama_event") or "").strip()
            tanggal    = (body.get("tanggal")    or "").strip()
            lokasi     = (body.get("lokasi")     or "").strip()

            if not nama_event or not tanggal or not lokasi:
                return jsonify({"status": "error", "message": "Field nama_event, tanggal (YYYY-MM-DD), dan lokasi wajib diisi"}), 422
            if not _DATE_RE_INLINE.match(tanggal):
                return jsonify({"status": "error", "message": "Format tanggal tidak valid. Gunakan YYYY-MM-DD"}), 422

            # Hanya tanggal hari ini persis yang auto-aktif
            auto_status = "aktif" if tanggal == _today_inline() else "selesai"
            try:
                if auto_status == "aktif":
                    _deactivate_others_inline(exclude_id=None)
                result  = supabase.table("event").insert({"nama_event": nama_event, "tanggal": tanggal, "lokasi": lokasi, "status": auto_status}).execute()
                created = result.data[0] if result.data else {}
                return jsonify({"status": "success", "message": "Event berhasil dibuat", "data": created}), 201
            except Exception:
                return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500

        @app.route("/api/events/<string:event_id>", methods=["PATCH"])
        @admin_only
        def update_event(event_id):
            body = request.get_json(silent=True) or {}
            try:
                check = supabase.table("event").select("id,status,tanggal").eq("id", event_id).maybe_single().execute()
                if not check.data:
                    return jsonify({"status": "error", "message": "Event tidak ditemukan"}), 404
            except Exception:
                return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500

            current = check.data

            if "status" in body:
                # Toggle
                new_status = (body.get("status") or "").strip()
                if new_status not in ("aktif", "selesai"):
                    return jsonify({"status": "error", "message": "Nilai status tidak valid. Gunakan 'aktif' atau 'selesai'"}), 400
                if new_status == "aktif" and current["tanggal"] > _today_inline():
                    return jsonify({"status": "error", "message": f"Event ini dijadwalkan pada {current['tanggal']} dan belum bisa diaktifkan."}), 422
                try:
                    if new_status == "aktif":
                        _deactivate_others_inline(exclude_id=event_id)
                    result  = supabase.table("event").update({"status": new_status}).eq("id", event_id).execute()
                    updated = result.data[0] if result.data else {}
                    return jsonify({"status": "success", "message": f"Status event berhasil diubah menjadi {new_status}", "data": updated}), 200
                except Exception:
                    return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500

            else:
                # Edit fields
                ALLOWED = {"nama_event", "lokasi", "tanggal"}
                payload = {k: v for k, v in body.items() if k in ALLOWED and v is not None}
                if not payload:
                    return jsonify({"status": "error", "message": "Tidak ada field yang valid untuk diperbarui"}), 422
                if "tanggal" in payload and current["status"] == "aktif":
                    return jsonify({"status": "error", "message": "Tanggal tidak dapat diubah saat event sedang aktif."}), 422
                if "tanggal" in payload and not _DATE_RE_INLINE.match(payload["tanggal"]):
                    return jsonify({"status": "error", "message": "Format tanggal tidak valid. Gunakan YYYY-MM-DD"}), 422
                if "tanggal" in payload:
                    new_auto = "aktif" if payload["tanggal"] == _today_inline() else "selesai"
                    payload["status"] = new_auto
                    if new_auto == "aktif":
                        _deactivate_others_inline(exclude_id=event_id)
                try:
                    result  = supabase.table("event").update(payload).eq("id", event_id).execute()
                    updated = result.data[0] if result.data else {}
                    return jsonify({"status": "success", "message": "Data event berhasil diperbarui", "data": updated}), 200
                except Exception:
                    return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500

        @app.route("/api/events/<string:event_id>", methods=["DELETE"])
        @admin_only
        def delete_event(event_id):
            try:
                check = supabase.table("event").select("id,status").eq("id", event_id).maybe_single().execute()
                if not check.data:
                    return jsonify({"status": "error", "message": "Event tidak ditemukan"}), 404
                if check.data.get("status") == "aktif":
                    return jsonify({"status": "error", "message": "Event yang sedang aktif tidak dapat dihapus. Nonaktifkan terlebih dahulu."}), 409
                result = supabase.table("event").delete().eq("id", event_id).execute()
                if result.data is not None and len(result.data) == 0:
                    return jsonify({"status": "error", "message": "Event tidak ditemukan"}), 404
                return jsonify({"status": "success", "message": "Event berhasil dihapus"}), 200
            except Exception as exc:
                msg = str(exc).lower()
                if "foreign key" in msg or "restrict" in msg or "kunjungan" in msg:
                    return jsonify({"status": "error", "message": "Event tidak dapat dihapus karena sudah memiliki data kunjungan."}), 409
                return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500

    return app