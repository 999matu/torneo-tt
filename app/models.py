from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


# ─── USUARIOS ───────────────────────────────────────────
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(20), default='jugador')
    activo = db.Column(db.Boolean, default=False)
    aprobado = db.Column(db.Boolean, default=False)
    jugador_id = db.Column(db.Integer, db.ForeignKey('jugador.id'), nullable=True)
    creado = db.Column(db.DateTime, default=datetime.utcnow)

    jugador = db.relationship('Jugador', backref='usuario', foreign_keys=[jugador_id])


# ─── JUGADORES ──────────────────────────────────────────
CATEGORIAS = ['TC', 'Master', 'Juvenil', 'Infantil', 'Sub13', 'Sub15', 'Sub19', 'Sub20']


class Jugador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(20), nullable=False)
    club = db.Column(db.String(100), nullable=True)
    activo = db.Column(db.Boolean, default=True)
    puntos_ranking = db.Column(db.Integer, default=0)
    creado = db.Column(db.DateTime, default=datetime.utcnow)

    def nombre_completo(self):
        return self.nombre


# ─── TORNEOS ────────────────────────────────────────────
class Torneo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    logo = db.Column(db.String(200), nullable=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)
    sets_por_partido = db.Column(db.Integer, default=5)
    puntos_por_set = db.Column(db.Integer, default=11)
    pasan_segundo = db.Column(db.Boolean, default=False)
    pts_campeon = db.Column(db.Integer, default=100)
    pts_finalista = db.Column(db.Integer, default=70)
    pts_semifinalista = db.Column(db.Integer, default=50)
    pts_cuartos = db.Column(db.Integer, default=30)
    pts_grupos_victoria = db.Column(db.Integer, default=15)
    pts_participacion = db.Column(db.Integer, default=5)


# ─── INSCRIPCIONES ──────────────────────────────────────
class Inscripcion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    torneo_id = db.Column(db.Integer, db.ForeignKey('torneo.id'), nullable=False)
    jugador_id = db.Column(db.Integer, db.ForeignKey('jugador.id'), nullable=False)
    categoria = db.Column(db.String(20), nullable=False)
    es_seed = db.Column(db.Boolean, default=False)
    numero_seed = db.Column(db.Integer, nullable=True)

    torneo = db.relationship('Torneo', backref='inscripciones')
    jugador = db.relationship('Jugador', backref='inscripciones')


# ─── GRUPOS ─────────────────────────────────────────────
class Grupo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    torneo_id = db.Column(db.Integer, db.ForeignKey('torneo.id'), nullable=False)
    categoria = db.Column(db.String(20), nullable=False)
    numero = db.Column(db.Integer, nullable=False)

    torneo = db.relationship('Torneo', backref='grupos')
    jugadores = db.relationship('GrupoJugador', backref='grupo')


class GrupoJugador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    grupo_id = db.Column(db.Integer, db.ForeignKey('grupo.id'), nullable=False)
    jugador_id = db.Column(db.Integer, db.ForeignKey('jugador.id'), nullable=False)
    posicion_final = db.Column(db.Integer, nullable=True)
    partidos_jugados = db.Column(db.Integer, default=0)
    partidos_ganados = db.Column(db.Integer, default=0)
    sets_ganados = db.Column(db.Integer, default=0)
    sets_perdidos = db.Column(db.Integer, default=0)

    jugador = db.relationship('Jugador')


# ─── PARTIDOS ───────────────────────────────────────────
class Partido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    torneo_id = db.Column(db.Integer, db.ForeignKey('torneo.id'), nullable=False)
    categoria = db.Column(db.String(20), nullable=False)
    fase = db.Column(db.String(30), nullable=False)  # grupos / cuartos / semi / final / tercer_lugar
    ronda = db.Column(db.Integer, nullable=True)      # posición en bracket
    grupo_id = db.Column(db.Integer, db.ForeignKey('grupo.id'), nullable=True)
    jugador1_id = db.Column(db.Integer, db.ForeignKey('jugador.id'), nullable=True)
    jugador2_id = db.Column(db.Integer, db.ForeignKey('jugador.id'), nullable=True)
    ganador_id = db.Column(db.Integer, db.ForeignKey('jugador.id'), nullable=True)
    resultado = db.Column(db.String(100), nullable=True)
    jugado = db.Column(db.Boolean, default=False)
    fecha_partido = db.Column(db.DateTime, nullable=True)

    jugador1 = db.relationship('Jugador', foreign_keys=[jugador1_id])
    jugador2 = db.relationship('Jugador', foreign_keys=[jugador2_id])
    ganador = db.relationship('Jugador', foreign_keys=[ganador_id])


# ─── RANKING INTERNO ────────────────────────────────────
class PuntosRanking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jugador_id = db.Column(db.Integer, db.ForeignKey('jugador.id'), nullable=False)
    torneo_id = db.Column(db.Integer, db.ForeignKey('torneo.id'), nullable=False)
    categoria = db.Column(db.String(20), nullable=False)
    posicion_final = db.Column(db.String(30), nullable=True)
    puntos = db.Column(db.Integer, default=0)

    jugador = db.relationship('Jugador', backref='puntos_historial')
    torneo = db.relationship('Torneo')


# ─── SOLICITUDES DE REGISTRO ────────────────────────────
class SolicitudRegistro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    nombre_jugador = db.Column(db.String(200), nullable=False)
    creado = db.Column(db.DateTime, default=datetime.utcnow)
    procesado = db.Column(db.Boolean, default=False)
