from flask import Flask
from config import Config
from routes.main import main_bp
from routes.auth import auth_bp
from routes.student import student_bp
from routes.teacher import teacher_bp
from routes.admin import admin_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    # Auto-initialize database schema and seed admin user if needed
    try:
        from init_db import init_db
        init_db(reset=False)
    except Exception as e:
        print(f"[Init Warning] Database auto-init check: {e}")

    # Register feature blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(admin_bp)

    # Register global alias endpoints so url_for('login'), url_for('student_dashboard'), etc. work seamlessly
    existing_rules = list(app.url_map.iter_rules())
    for rule in existing_rules:
        if '.' in rule.endpoint:
            short_endpoint = rule.endpoint.split('.', 1)[1]
            existing_endpoints = [r.endpoint for r in app.url_map.iter_rules()]
            if short_endpoint not in existing_endpoints:
                app.add_url_rule(
                    rule.rule,
                    endpoint=short_endpoint,
                    view_func=app.view_functions[rule.endpoint],
                    methods=rule.methods
                )

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)