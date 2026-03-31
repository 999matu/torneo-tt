import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_migrate import Migrate
from flask_mail import Mail
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()
migrate = Migrate()
mail = Mail()


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

    database_url = os.environ.get('DATABASE_URL', 'sqlite:///torneo.db')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    upload_folder = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_folder

    # ── MAIL CONFIG ──
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = ('Rankevo', os.environ.get('MAIL_USERNAME'))

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Debes iniciar sesión.'
    login_manager.login_message_category = 'warning'
    socketio.init_app(app, cors_allowed_origins='*', async_mode='eventlet')
    migrate.init_app(app, db)
    mail.init_app(app)

    from app.routes import auth, main
    app.register_blueprint(auth)
    app.register_blueprint(main)

    with app.app_context():
        _crear_superadmin()

    return app


def _crear_superadmin():
    from app.models import Usuario
    from werkzeug.security import generate_password_hash
    try:
        existente = Usuario.query.filter_by(username='matu').first()
        if not existente:
            superadmin = Usuario(
                username='matu',
                password=generate_password_hash('rankevo2026'),
                rol='superadmin',
                activo=True,
                aprobado=True,
                email_verificado=True
            )
            db.session.add(superadmin)
            db.session.commit()
        else:
            # Asegura que siempre tenga acceso aunque ya exista
            existente.activo = True
            existente.aprobado = True
            existente.email_verificado = True
            db.session.commit()
    except Exception:
        db.session.rollback()


@login_manager.user_loader
def load_user(user_id):
    from app.models import Usuario
    return Usuario.query.get(int(user_id))