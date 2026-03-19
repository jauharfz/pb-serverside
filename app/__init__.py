import sys
import logging

from flask import Flask, jsonify, request
from flask_cors import CORS
from app.config import Config

logging.basicConfig(
    stream=sys.stderr,
    level=logging.DEBUG if (
        __import__('os').environ.get("FLASK_DEBUG", "false").lower() == "true"
    ) else logging.INFO,
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
    from app.blueprints.events.routes import events_bp
    app.register_blueprint(events_bp, url_prefix="/api")

    return app