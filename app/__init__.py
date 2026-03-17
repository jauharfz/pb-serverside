import sys
import logging

from flask import Flask, jsonify, request
from flask_cors import CORS
from app.config import Config

# Pastikan error saat startup selalu tercetak ke stderr
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
    # Dicoba import dari package terlebih dahulu.
    # Jika gagal karena alasan apapun (misal Docker cache lama),
    # routes didaftarkan inline dan error dicetak ke log HF Spaces.
    try:
        from app.blueprints.events.routes import events_bp
        app.register_blueprint(events_bp, url_prefix="/api")
        _log.info("events_bp berhasil didaftarkan dari app.blueprints.events.routes")

    except Exception as exc:
        # Cek log HF Spaces (tab Logs → Container) untuk melihat penyebab
        _log.error("GAGAL import events_bp: %s", exc, exc_info=True)
        _log.warning("Mendaftarkan events routes secara inline sebagai fallback.")

        # Inline fallback — identik dengan blueprints/events/routes.py
        import re
        from app.extensions import supabase
        from app.middleware.auth import admin_only

        _DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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
            if not _DATE_RE.match(tanggal):
                return jsonify({"status": "error", "message": "Format tanggal tidak valid. Gunakan YYYY-MM-DD"}), 422

            try:
                result = (
                    supabase.table("event")
                    .insert({"nama_event": nama_event, "tanggal": tanggal, "lokasi": lokasi, "status": "aktif"})
                    .execute()
                )
                created = result.data[0] if result.data else {}
                return jsonify({"status": "success", "message": "Event berhasil dibuat", "data": created}), 201
            except Exception:
                return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500

        @app.route("/api/events/<string:event_id>", methods=["PATCH"])
        @admin_only
        def update_event_status(event_id):
            body       = request.get_json(silent=True) or {}
            new_status = (body.get("status") or "").strip()

            if new_status not in ("aktif", "selesai"):
                return jsonify({"status": "error", "message": "Nilai status tidak valid. Gunakan 'aktif' atau 'selesai'"}), 400

            try:
                check = supabase.table("event").select("id").eq("id", event_id).maybe_single().execute()
                if not check.data:
                    return jsonify({"status": "error", "message": "Event tidak ditemukan"}), 404

                result  = supabase.table("event").update({"status": new_status}).eq("id", event_id).execute()
                updated = result.data[0] if result.data else {}
                return jsonify({"status": "success", "message": f"Status event berhasil diubah menjadi {new_status}", "data": updated}), 200
            except Exception:
                return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500

    return app