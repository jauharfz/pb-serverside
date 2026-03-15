from flask import Flask
from flask_cors import CORS
from app.config import Config


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ── Blueprints ────────────────────────────────────────────────────────
    from app.blueprints.auth.routes     import auth_bp
    from app.blueprints.nfc.routes      import nfc_bp
    from app.blueprints.members.routes  import members_bp
    from app.blueprints.visitors.routes import visitors_bp
    from app.blueprints.dashboard.routes import dashboard_bp
    from app.blueprints.reports.routes  import reports_bp
    from app.blueprints.discounts.routes import discounts_bp
    from app.blueprints.umkm.routes     import umkm_bp

    app.register_blueprint(auth_bp,      url_prefix="/api/auth")
    app.register_blueprint(nfc_bp,       url_prefix="/api")
    app.register_blueprint(members_bp,   url_prefix="/api")
    app.register_blueprint(visitors_bp,  url_prefix="/api")
    app.register_blueprint(dashboard_bp, url_prefix="/api")
    app.register_blueprint(reports_bp,   url_prefix="/api")
    app.register_blueprint(discounts_bp, url_prefix="/api")
    app.register_blueprint(umkm_bp,      url_prefix="/api")

    return app
