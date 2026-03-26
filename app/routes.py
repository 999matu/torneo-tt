from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from app import db
from app.models import Usuario, Jugador, CATEGORIAS
import openpyxl
import os


# ─── BLUEPRINTS ─────────────────────────────────────────
auth = Blueprint('auth', __name__)
main = Blueprint('main', __name__)


# ─── ALLOWED FILES ──────────────────────────────────────
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ─── MAPA DE CATEGORÍAS ─────────────────────────────────
MAPA_CATEGORIAS = {
    'TC': 'TC', 'MASTER': 'Master', 'JUVENIL': 'Juvenil',
    'INFANTIL': 'Infantil', 'PENECA': 'Infantil',
    'SUB 13': 'Sub13', 'SUB 15': 'Sub15',
    'SUB 19': 'Sub19', 'SUB 20': 'Sub20',
}


def parsear_categorias(texto):
    cats = []
    texto = texto.upper().replace(' E ', ' Y ')
    for parte in texto.split(' Y '):
        parte = parte.strip()
        if parte in MAPA_CATEGORIAS:
            cats.append(MAPA_CATEGORIAS[parte])
    return cats


# ─── AUTH ROUTES ────────────────────────────────────────
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        usuario = Usuario.query.filter_by(username=username).first()
        if usuario and check_password_hash(usuario.password, password):
            if not usuario.activo:
                flash('Tu cuenta está desactivada.', 'danger')
                return redirect(url_for('auth.login'))
            login_user(usuario)
            return redirect(url_for('main.dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('auth/login.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        nombre_jugador = request.form.get('nombre_jugador').strip()
        if Usuario.query.filter_by(username=username).first():
            flash('Ese nombre de usuario ya existe.', 'danger')
            return redirect(url_for('auth.registro'))
        from app.models import SolicitudRegistro
        solicitud = SolicitudRegistro(
            username=username,
            password_hash=generate_password_hash(password),
            nombre_jugador=nombre_jugador
        )
        db.session.add(solicitud)
        db.session.commit()
        flash('Solicitud enviada. El administrador aprobará tu cuenta pronto.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/registro.html')


# ─── SETUP ADMIN ────────────────────────────────────────
@main.route('/setup')
def setup():
    if Usuario.query.filter_by(rol='admin').first():
        flash('Ya existe un administrador.', 'warning')
        return redirect(url_for('auth.login'))
    admin = Usuario(
        username='admin',
        password=generate_password_hash('admin123'),
        rol='admin',
        activo=True
    )
    db.session.add(admin)
    db.session.commit()
    flash('Admin creado: usuario=admin, contraseña=admin123.', 'success')
    return redirect(url_for('auth.login'))


# ─── MIGRACIÓN BD ───────────────────────────────────────
@main.route('/migrar-db')
def migrar_db():
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text('ALTER TABLE inscripcion ADD COLUMN solo_en_grupo BOOLEAN DEFAULT 0'))
            conn.commit()
        return '✅ Migración exitosa - columna solo_en_grupo agregada'
    except Exception as e:
        return f'ℹ️ {str(e)}'


# ─── MAIN ROUTES ────────────────────────────────────────
@main.route('/')
def index():
    from app.models import Torneo, PuntosRanking, Partido
    torneos_activos = Torneo.query.filter_by(activo=True).order_by(Torneo.fecha.desc()).limit(5).all()
    total_torneos   = Torneo.query.filter_by(activo=True).count()
    total_jugadores = Jugador.query.filter_by(activo=True).count()
    total_partidos  = Partido.query.filter_by(jugado=True).count()
    ranking_top = db.session.query(
        Jugador,
        db.func.sum(PuntosRanking.puntos).label('total_puntos')
    ).join(PuntosRanking, Jugador.id == PuntosRanking.jugador_id)\
     .group_by(Jugador.id)\
     .order_by(db.desc('total_puntos')).limit(5).all()
    return render_template('landing.html',
        torneos=torneos_activos,
        ranking_top=ranking_top,
        total_torneos=total_torneos,
        total_jugadores=total_jugadores,
        total_partidos=total_partidos
    )


@main.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', usuario=current_user)


# ─── JUGADORES ──────────────────────────────────────────
@main.route('/jugadores')
@login_required
def jugadores():
    categoria = request.args.get('categoria', 'todas')
    if categoria == 'todas':
        todos = Jugador.query.filter_by(activo=True).order_by(Jugador.nombre).all()
        agrupados = {}
        for j in todos:
            if j.nombre not in agrupados:
                agrupados[j.nombre] = {'jugador': j, 'categorias': []}
            agrupados[j.nombre]['categorias'].append(j.categoria)
        lista = list(agrupados.values())
        return render_template('jugadores/lista.html', jugadores=lista, categorias=CATEGORIAS,
                               categoria_actual=categoria, agrupado=True)
    else:
        lista = Jugador.query.filter_by(activo=True, categoria=categoria).order_by(Jugador.nombre).all()
        return render_template('jugadores/lista.html', jugadores=lista, categorias=CATEGORIAS,
                               categoria_actual=categoria, agrupado=False)


@main.route('/jugadores/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_jugador():
    if request.method == 'POST':
        nombre = request.form.get('nombre').strip()
        categoria = request.form.get('categoria')
        if not nombre or not categoria:
            flash('Todos los campos son obligatorios.', 'danger')
            return redirect(url_for('main.nuevo_jugador'))
        jugador = Jugador(nombre=nombre, categoria=categoria)
        db.session.add(jugador)
        db.session.commit()
        flash(f'Jugador {nombre} agregado correctamente.', 'success')
        return redirect(url_for('main.jugadores'))
    return render_template('jugadores/nuevo.html', categorias=CATEGORIAS)


@main.route('/jugadores/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_jugador(id):
    jugador = Jugador.query.get_or_404(id)
    if request.method == 'POST':
        jugador.nombre = request.form.get('nombre').strip()
        jugador.categoria = request.form.get('categoria')
        db.session.commit()
        flash('Jugador actualizado.', 'success')
        return redirect(url_for('main.jugadores'))
    return render_template('jugadores/editar.html', jugador=jugador, categorias=CATEGORIAS)


@main.route('/jugadores/eliminar/<int:id>')
@login_required
def eliminar_jugador(id):
    jugador = Jugador.query.get_or_404(id)
    jugador.activo = False
    db.session.commit()
    flash(f'Jugador {jugador.nombre_completo()} eliminado.', 'warning')
    return redirect(url_for('main.jugadores'))


@main.route('/jugadores/importar', methods=['GET', 'POST'])
@login_required
def importar_jugadores():
    if request.method == 'POST':
        if 'archivo' not in request.files:
            flash('No se seleccionó archivo.', 'danger')
            return redirect(request.url)
        archivo = request.files['archivo']
        if not allowed_file(archivo.filename):
            flash('Solo se permiten archivos .xlsx o .xls', 'danger')
            return redirect(request.url)
        from flask import current_app
        filename = secure_filename(archivo.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        archivo.save(filepath)
        wb = openpyxl.load_workbook(filepath)
        ws = wb.active
        importados = 0
        errores = 0
        for row in ws.iter_rows(min_row=6, values_only=True):
            try:
                nombre = str(row[1]).strip() if row[1] else None
                cat_raw = str(row[2]).strip() if row[2] else None
                if not nombre or not cat_raw or nombre == 'NOMBRE':
                    continue
                categorias = parsear_categorias(cat_raw)
                for cat in categorias:
                    existe = Jugador.query.filter_by(nombre=nombre, categoria=cat).first()
                    if not existe:
                        db.session.add(Jugador(nombre=nombre, categoria=cat))
                        importados += 1
            except:
                errores += 1
        db.session.commit()
        flash(f'Importación completa: {importados} jugadores agregados, {errores} errores omitidos.', 'success')
        return redirect(url_for('main.jugadores'))
    return render_template('jugadores/importar.html')


# ─── TORNEOS ────────────────────────────────────────────
from app.models import Torneo
from flask import current_app


@main.route('/torneos')
@login_required
def torneos():
    lista = Torneo.query.order_by(Torneo.fecha.desc()).all()
    return render_template('torneos/lista.html', torneos=lista)


@main.route('/torneos/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_torneo():
    if request.method == 'POST':
        torneo = Torneo(
            nombre=request.form.get('nombre').strip(),
            descripcion=request.form.get('descripcion', '').strip(),
            sets_por_partido=int(request.form.get('sets_por_partido', 5)),
            puntos_por_set=int(request.form.get('puntos_por_set', 11)),
            pasan_segundo=request.form.get('pasan_segundo') == 'on',
            pts_campeon=int(request.form.get('pts_campeon', 100)),
            pts_finalista=int(request.form.get('pts_finalista', 70)),
            pts_semifinalista=int(request.form.get('pts_semifinalista', 50)),
            pts_cuartos=int(request.form.get('pts_cuartos', 30)),
            pts_grupos_victoria=int(request.form.get('pts_grupos_victoria', 15)),
            pts_participacion=int(request.form.get('pts_participacion', 5))
        )
        if 'logo' in request.files:
            logo = request.files['logo']
            if logo and logo.filename != '':
                filename = secure_filename(logo.filename)
                logo.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                torneo.logo = filename
        db.session.add(torneo)
        db.session.commit()
        flash(f'Torneo "{torneo.nombre}" creado correctamente.', 'success')
        return redirect(url_for('main.torneos'))
    return render_template('torneos/nuevo.html')


@main.route('/torneos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_torneo(id):
    torneo = Torneo.query.get_or_404(id)
    if request.method == 'POST':
        torneo.nombre = request.form.get('nombre').strip()
        torneo.descripcion = request.form.get('descripcion', '').strip()
        torneo.sets_por_partido = int(request.form.get('sets_por_partido', 5))
        torneo.puntos_por_set = int(request.form.get('puntos_por_set', 11))
        torneo.pasan_segundo = request.form.get('pasan_segundo') == 'on'
        torneo.pts_campeon = int(request.form.get('pts_campeon', 100))
        torneo.pts_finalista = int(request.form.get('pts_finalista', 70))
        torneo.pts_semifinalista = int(request.form.get('pts_semifinalista', 50))
        torneo.pts_cuartos = int(request.form.get('pts_cuartos', 30))
        torneo.pts_grupos_victoria = int(request.form.get('pts_grupos_victoria', 15))
        torneo.pts_participacion = int(request.form.get('pts_participacion', 5))
        if 'logo' in request.files:
            logo = request.files['logo']
            if logo and logo.filename != '':
                filename = secure_filename(logo.filename)
                logo.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                torneo.logo = filename
        db.session.commit()
        flash('Torneo actualizado.', 'success')
        return redirect(url_for('main.torneos'))
    return render_template('torneos/editar.html', torneo=torneo)


@main.route('/torneos/eliminar/<int:id>')
@login_required
def eliminar_torneo(id):
    torneo = Torneo.query.get_or_404(id)
    torneo.activo = False
    db.session.commit()
    flash(f'Torneo "{torneo.nombre}" eliminado.', 'warning')
    return redirect(url_for('main.torneos'))


# ─── INSCRIPCIONES ──────────────────────────────────────
from app.models import Inscripcion


@main.route('/torneos/<int:torneo_id>/inscripciones')
@login_required
def inscripciones(torneo_id):
    torneo = Torneo.query.get_or_404(torneo_id)
    categoria = request.args.get('categoria', CATEGORIAS[0])
    inscritos = db.session.query(Inscripcion, Jugador)\
        .join(Jugador, Inscripcion.jugador_id == Jugador.id)\
        .filter(Inscripcion.torneo_id == torneo_id, Inscripcion.categoria == categoria)\
        .order_by(Inscripcion.es_seed.desc(), Jugador.nombre).all()
    ids_inscritos = [i.jugador_id for i, j in inscritos]
    disponibles = Jugador.query.filter_by(activo=True, categoria=categoria)\
        .filter(~Jugador.id.in_(ids_inscritos) if ids_inscritos else db.true())\
        .order_by(Jugador.nombre).all()
    resumen = {}
    for cat in CATEGORIAS:
        resumen[cat] = Inscripcion.query.filter_by(torneo_id=torneo_id, categoria=cat).count()
    return render_template('inscripciones/lista.html',
        torneo=torneo, inscritos=inscritos, disponibles=disponibles,
        categorias=CATEGORIAS, categoria_actual=categoria, resumen=resumen)


@main.route('/torneos/<int:torneo_id>/inscripciones/agregar', methods=['POST'])
@login_required
def agregar_inscripcion(torneo_id):
    jugador_id = request.form.get('jugador_id')
    categoria = request.form.get('categoria')
    existe = Inscripcion.query.filter_by(torneo_id=torneo_id, jugador_id=jugador_id, categoria=categoria).first()
    if not existe:
        db.session.add(Inscripcion(torneo_id=torneo_id, jugador_id=jugador_id, categoria=categoria, es_seed=False))
        db.session.commit()
    return redirect(url_for('main.inscripciones', torneo_id=torneo_id, categoria=categoria))


@main.route('/torneos/<int:torneo_id>/inscripciones/eliminar/<int:inscripcion_id>')
@login_required
def eliminar_inscripcion(torneo_id, inscripcion_id):
    categoria = request.args.get('categoria', CATEGORIAS[0])
    inscripcion = Inscripcion.query.get_or_404(inscripcion_id)
    db.session.delete(inscripcion)
    db.session.commit()
    flash('Jugador removido de la inscripción.', 'warning')
    return redirect(url_for('main.inscripciones', torneo_id=torneo_id, categoria=categoria))


@main.route('/torneos/<int:torneo_id>/inscripciones/seed/<int:inscripcion_id>', methods=['POST'])
@login_required
def toggle_seed(torneo_id, inscripcion_id):
    categoria = request.form.get('categoria', CATEGORIAS[0])
    inscripcion = Inscripcion.query.get_or_404(inscripcion_id)
    inscripcion.es_seed = not inscripcion.es_seed
    db.session.commit()
    return redirect(url_for('main.inscripciones', torneo_id=torneo_id, categoria=categoria))


@main.route('/torneos/<int:torneo_id>/inscripciones/solo-grupo/<int:inscripcion_id>', methods=['POST'])
@login_required
def toggle_solo_grupo(torneo_id, inscripcion_id):
    categoria = request.form.get('categoria', CATEGORIAS[0])
    inscripcion = Inscripcion.query.get_or_404(inscripcion_id)
    inscripcion.solo_en_grupo = not inscripcion.solo_en_grupo
    db.session.commit()
    return redirect(url_for('main.inscripciones', torneo_id=torneo_id, categoria=categoria))


@main.route('/torneos/<int:torneo_id>/inscripciones/agregar-todos', methods=['POST'])
@login_required
def agregar_todos_categoria(torneo_id):
    categoria = request.form.get('categoria')
    jugadores = Jugador.query.filter_by(activo=True, categoria=categoria).all()
    agregados = 0
    for j in jugadores:
        existe = Inscripcion.query.filter_by(torneo_id=torneo_id, jugador_id=j.id, categoria=categoria).first()
        if not existe:
            db.session.add(Inscripcion(torneo_id=torneo_id, jugador_id=j.id, categoria=categoria))
            agregados += 1
    db.session.commit()
    flash(f'{agregados} jugadores inscritos en {categoria}.', 'success')
    return redirect(url_for('main.inscripciones', torneo_id=torneo_id, categoria=categoria))


# ─── PERFIL JUGADOR ─────────────────────────────────────
from app.models import SolicitudRegistro, Partido, PuntosRanking


@main.route('/mi-perfil')
@login_required
def mi_perfil():
    if not current_user.jugador_id:
        flash('Tu cuenta aún no está vinculada a un jugador.', 'warning')
        return redirect(url_for('main.dashboard'))
    jugador = Jugador.query.get(current_user.jugador_id)
    inscripciones = Inscripcion.query.filter_by(jugador_id=jugador.id).all()
    partidos = Partido.query.filter(
        (Partido.jugador1_id == jugador.id) | (Partido.jugador2_id == jugador.id)
    ).order_by(Partido.id.desc()).all()
    puntos = PuntosRanking.query.filter_by(jugador_id=jugador.id).all()
    total_puntos = sum(p.puntos for p in puntos)
    return render_template('perfil/mi_perfil.html',
        jugador=jugador, inscripciones=inscripciones,
        partidos=partidos, puntos=puntos, total_puntos=total_puntos)


# ─── ADMIN USUARIOS ─────────────────────────────────────
@main.route('/admin/usuarios')
@login_required
def admin_usuarios():
    if current_user.rol != 'admin':
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.dashboard'))
    usuarios = Usuario.query.order_by(Usuario.creado.desc()).all()
    solicitudes = SolicitudRegistro.query.filter_by(procesado=False).all()
    jugadores_sin_cuenta = Jugador.query.filter(
        ~Jugador.id.in_(
            db.session.query(Usuario.jugador_id).filter(Usuario.jugador_id != None)
        )
    ).order_by(Jugador.nombre).all()
    return render_template('admin/usuarios.html',
        usuarios=usuarios, solicitudes=solicitudes,
        jugadores_sin_cuenta=jugadores_sin_cuenta)


@main.route('/admin/usuarios/aprobar/<int:solicitud_id>', methods=['POST'])
@login_required
def aprobar_usuario(solicitud_id):
    if current_user.rol != 'admin':
        return redirect(url_for('main.dashboard'))
    solicitud = SolicitudRegistro.query.get_or_404(solicitud_id)
    jugador_id = request.form.get('jugador_id')
    db.session.add(Usuario(
        username=solicitud.username,
        password=solicitud.password_hash,
        rol='jugador', activo=True, aprobado=True,
        jugador_id=int(jugador_id) if jugador_id else None
    ))
    solicitud.procesado = True
    db.session.commit()
    flash(f'Usuario {solicitud.username} aprobado.', 'success')
    return redirect(url_for('main.admin_usuarios'))


@main.route('/admin/usuarios/crear', methods=['POST'])
@login_required
def crear_usuario():
    if current_user.rol != 'admin':
        return redirect(url_for('main.dashboard'))
    username = request.form.get('username').strip()
    password = request.form.get('password')
    rol = request.form.get('rol', 'jugador')
    jugador_id = request.form.get('jugador_id')
    if Usuario.query.filter_by(username=username).first():
        flash('Ese usuario ya existe.', 'danger')
        return redirect(url_for('main.admin_usuarios'))
    db.session.add(Usuario(
        username=username, password=generate_password_hash(password),
        rol=rol, activo=True, aprobado=True,
        jugador_id=int(jugador_id) if jugador_id else None
    ))
    db.session.commit()
    flash(f'Usuario {username} creado.', 'success')
    return redirect(url_for('main.admin_usuarios'))


@main.route('/admin/usuarios/desactivar/<int:usuario_id>')
@login_required
def desactivar_usuario(usuario_id):
    if current_user.rol != 'admin':
        return redirect(url_for('main.dashboard'))
    u = Usuario.query.get_or_404(usuario_id)
    u.activo = not u.activo
    db.session.commit()
    flash(f'Usuario {u.username} {"activado" if u.activo else "desactivado"}.', 'success')
    return redirect(url_for('main.admin_usuarios'))


# ─── FIXTURE ────────────────────────────────────────────
from app.models import Grupo, GrupoJugador
from app import socketio as sio
import random


def ordenar_partidos_sin_consecutivos(partidos):
    pendientes = list(partidos)
    ordenados = []
    ultimos_ids = set()
    while pendientes:
        encontrado = False
        for p in pendientes:
            jugadores = {p.jugador1_id, p.jugador2_id}
            if not jugadores & ultimos_ids:
                ordenados.append(p)
                pendientes.remove(p)
                ultimos_ids = jugadores
                encontrado = True
                break
        if not encontrado:
            p = pendientes.pop(0)
            ordenados.append(p)
            ultimos_ids = {p.jugador1_id, p.jugador2_id}
    return ordenados


@main.route('/torneos/<int:torneo_id>/fixture')
@login_required
def fixture(torneo_id):
    torneo = Torneo.query.get_or_404(torneo_id)
    categoria = request.args.get('categoria', None)
    cats_con_inscritos = []
    for cat in CATEGORIAS:
        count = Inscripcion.query.filter_by(torneo_id=torneo_id, categoria=cat).count()
        if count > 0:
            cats_con_inscritos.append({'cat': cat, 'count': count})
    if not categoria and cats_con_inscritos:
        categoria = cats_con_inscritos[0]['cat']
    elif not categoria:
        categoria = CATEGORIAS[0]
    grupos = Grupo.query.filter_by(torneo_id=torneo_id, categoria=categoria).order_by(Grupo.numero).all()
    partidos_generados = Partido.query.filter_by(torneo_id=torneo_id, categoria=categoria, fase='grupos').count() > 0
    grupo_partidos = {}
    for grupo in grupos:
        partidos_raw = Partido.query.filter_by(torneo_id=torneo_id, categoria=categoria, fase='grupos', grupo_id=grupo.id).all()
        grupo_partidos[grupo.id] = ordenar_partidos_sin_consecutivos(partidos_raw)
    return render_template('fixture/index.html',
        torneo=torneo, categoria_actual=categoria,
        cats_con_inscritos=cats_con_inscritos,
        grupos=grupos, partidos_generados=partidos_generados,
        grupo_partidos=grupo_partidos, categorias=CATEGORIAS)


@main.route('/torneos/<int:torneo_id>/fixture/generar', methods=['POST'])
@login_required
def generar_fixture(torneo_id):
    torneo = Torneo.query.get_or_404(torneo_id)
    categoria = request.form.get('categoria')
    num_grupos = int(request.form.get('num_grupos', 2))
    for p in Partido.query.filter_by(torneo_id=torneo_id, categoria=categoria, fase='grupos').all():
        db.session.delete(p)
    for g in Grupo.query.filter_by(torneo_id=torneo_id, categoria=categoria).all():
        for gj in g.jugadores:
            db.session.delete(gj)
        db.session.delete(g)
    db.session.commit()
    inscritos = db.session.query(Inscripcion, Jugador)\
        .join(Jugador, Inscripcion.jugador_id == Jugador.id)\
        .filter(Inscripcion.torneo_id == torneo_id, Inscripcion.categoria == categoria).all()
    solos = [(i, j) for i, j in inscritos if getattr(i, 'solo_en_grupo', False)]
    seeds = [(i, j) for i, j in inscritos if i.es_seed and not getattr(i, 'solo_en_grupo', False)]
    no_seeds = [(i, j) for i, j in inscritos if not i.es_seed and not getattr(i, 'solo_en_grupo', False)]
    random.shuffle(no_seeds)
    total_grupos = num_grupos + len(solos)
    for n in range(1, total_grupos + 1):
        db.session.add(Grupo(torneo_id=torneo_id, categoria=categoria, numero=n))
    db.session.commit()
    grupos = Grupo.query.filter_by(torneo_id=torneo_id, categoria=categoria).order_by(Grupo.numero).all()
    grupos_normales = grupos[:num_grupos]
    grupos_solos = grupos[num_grupos:]
    for idx, (insc, jug) in enumerate(solos):
        db.session.add(GrupoJugador(grupo_id=grupos_solos[idx].id, jugador_id=jug.id))
    for idx, (insc, jug) in enumerate(seeds):
        db.session.add(GrupoJugador(grupo_id=grupos_normales[idx % num_grupos].id, jugador_id=jug.id))
    for idx, (insc, jug) in enumerate(no_seeds):
        db.session.add(GrupoJugador(grupo_id=grupos_normales[idx % num_grupos].id, jugador_id=jug.id))
    db.session.commit()
    for grupo in grupos:
        jugadores_grupo = [gj.jugador_id for gj in grupo.jugadores]
        for i in range(len(jugadores_grupo)):
            for j in range(i + 1, len(jugadores_grupo)):
                db.session.add(Partido(
                    torneo_id=torneo_id, categoria=categoria, fase='grupos',
                    grupo_id=grupo.id, jugador1_id=jugadores_grupo[i],
                    jugador2_id=jugadores_grupo[j], jugado=False))
    db.session.commit()
    flash(f'Fixture generado: {num_grupos} grupos + {len(solos)} grupo(s) individual(es) para {categoria}.', 'success')
    return redirect(url_for('main.fixture', torneo_id=torneo_id, categoria=categoria))


@main.route('/torneos/<int:torneo_id>/fixture/resultado/<int:partido_id>', methods=['POST'])
@login_required
def registrar_resultado(torneo_id, partido_id):
    partido = Partido.query.get_or_404(partido_id)
    categoria = request.form.get('categoria')
    ganador_id = int(request.form.get('ganador_id'))
    resultado = request.form.get('resultado', '')
    partido.ganador_id = ganador_id
    partido.resultado = resultado
    partido.jugado = True
    perdedor_id = partido.jugador2_id if ganador_id == partido.jugador1_id else partido.jugador1_id
    gj_ganador = GrupoJugador.query.filter_by(grupo_id=partido.grupo_id, jugador_id=ganador_id).first()
    gj_perdedor = GrupoJugador.query.filter_by(grupo_id=partido.grupo_id, jugador_id=perdedor_id).first()
    if gj_ganador:
        gj_ganador.partidos_jugados += 1
        gj_ganador.partidos_ganados += 1
    if gj_perdedor:
        gj_perdedor.partidos_jugados += 1
    torneo = Torneo.query.get(torneo_id)
    _sumar_puntos(ganador_id, torneo_id, categoria, 'victoria_grupo', torneo.pts_grupos_victoria)
    db.session.commit()
    sio.emit('resultado_actualizado', {
        'torneo_id': torneo_id, 'categoria': categoria,
        'partido_id': partido_id, 'ganador_id': ganador_id, 'resultado': resultado
    })
    flash('Resultado registrado.', 'success')
    return redirect(url_for('main.fixture', torneo_id=torneo_id, categoria=categoria))


@main.route('/torneos/<int:torneo_id>/fixture/live/<int:partido_id>', methods=['POST'])
@login_required
def marcador_live(torneo_id, partido_id):
    data = request.get_json()
    sio.emit('marcador_live', {
        'torneo_id': torneo_id, 'partido_id': partido_id,
        'categoria': data.get('categoria'),
        'j1': data.get('j1'), 'j2': data.get('j2'),
        'pts1': data.get('pts1'), 'pts2': data.get('pts2'),
        'sets1': data.get('sets1'), 'sets2': data.get('sets2'),
        'set_actual': data.get('set_actual'),
        'historial': data.get('historial', [])
    })
    return {'ok': True}


# ─── BRACKET ELIMINATORIO ───────────────────────────────
@main.route('/torneos/<int:torneo_id>/bracket')
@login_required
def bracket(torneo_id):
    torneo = Torneo.query.get_or_404(torneo_id)
    categoria = request.args.get('categoria', None)
    cats_con_inscritos = []
    for cat in CATEGORIAS:
        count = Inscripcion.query.filter_by(torneo_id=torneo_id, categoria=cat).count()
        if count > 0:
            cats_con_inscritos.append({'cat': cat, 'count': count})
    if not categoria and cats_con_inscritos:
        categoria = cats_con_inscritos[0]['cat']
    elif not categoria:
        categoria = CATEGORIAS[0]
    fases = ['cuartos', 'semi', 'final', 'tercer_lugar']
    partidos_bracket = {}
    for fase in fases:
        partidos_bracket[fase] = Partido.query.filter_by(
            torneo_id=torneo_id, categoria=categoria, fase=fase
        ).order_by(Partido.ronda).all()
    bracket_generado = len(partidos_bracket['semi']) > 0 or len(partidos_bracket['final']) > 0
    grupos = Grupo.query.filter_by(torneo_id=torneo_id, categoria=categoria).order_by(Grupo.numero).all()
    clasificados = []
    for grupo in grupos:
        sorted_jug = sorted(grupo.jugadores, key=lambda x: (-x.partidos_ganados, x.partidos_jugados))
        if sorted_jug:
            clasificados.append({'pos': '1°', 'grupo': grupo.numero, 'jugador': sorted_jug[0].jugador})
        if len(sorted_jug) > 1:
            clasificados.append({'pos': '2°', 'grupo': grupo.numero, 'jugador': sorted_jug[1].jugador})
    return render_template('bracket/index.html',
        torneo=torneo, categoria_actual=categoria,
        cats_con_inscritos=cats_con_inscritos,
        partidos_bracket=partidos_bracket,
        bracket_generado=bracket_generado,
        clasificados=clasificados,
        categorias=CATEGORIAS)


@main.route('/torneos/<int:torneo_id>/bracket/generar', methods=['POST'])
@login_required
def generar_bracket(torneo_id):
    torneo = Torneo.query.get_or_404(torneo_id)
    categoria = request.form.get('categoria')
    for fase in ['cuartos', 'semi', 'final', 'tercer_lugar']:
        for p in Partido.query.filter_by(torneo_id=torneo_id, categoria=categoria, fase=fase).all():
            db.session.delete(p)
    db.session.commit()
    grupos = Grupo.query.filter_by(torneo_id=torneo_id, categoria=categoria).order_by(Grupo.numero).all()
    primeros = []
    segundos = []
    for grupo in grupos:
        sorted_jug = sorted(grupo.jugadores, key=lambda x: (-x.partidos_ganados, x.partidos_jugados))
        if sorted_jug:
            primeros.append(sorted_jug[0].jugador_id)
        if len(sorted_jug) > 1:
            segundos.append(sorted_jug[1].jugador_id)
    num_grupos = len(grupos)
    if num_grupos >= 4:
        cruces = [
            (primeros[0], segundos[1] if len(segundos) > 1 else None),
            (primeros[1], segundos[0] if len(segundos) > 0 else None),
            (primeros[2], segundos[3] if len(segundos) > 3 else None),
            (primeros[3] if len(primeros) > 3 else None, segundos[2] if len(segundos) > 2 else None),
        ]
        for ronda, (j1, j2) in enumerate(cruces, 1):
            if j1:
                db.session.add(Partido(
                    torneo_id=torneo_id, categoria=categoria, fase='cuartos', ronda=ronda,
                    jugador1_id=j1, jugador2_id=j2,
                    jugado=j2 is None, ganador_id=j1 if j2 is None else None))
        db.session.commit()
        for ronda in [1, 2]:
            db.session.add(Partido(torneo_id=torneo_id, categoria=categoria, fase='semi', ronda=ronda, jugado=False))
    elif num_grupos >= 2:
        cruces_semi = [
            (primeros[0], segundos[1] if len(segundos) > 1 else None),
            (primeros[1], segundos[0] if len(segundos) > 0 else None),
        ]
        for ronda, (j1, j2) in enumerate(cruces_semi, 1):
            if j1:
                db.session.add(Partido(
                    torneo_id=torneo_id, categoria=categoria, fase='semi', ronda=ronda,
                    jugador1_id=j1, jugador2_id=j2,
                    jugado=j2 is None, ganador_id=j1 if j2 is None else None))
    db.session.add(Partido(torneo_id=torneo_id, categoria=categoria, fase='final', ronda=1, jugado=False))
    db.session.add(Partido(torneo_id=torneo_id, categoria=categoria, fase='tercer_lugar', ronda=1, jugado=False))
    db.session.commit()
    inscritos = Inscripcion.query.filter_by(torneo_id=torneo_id, categoria=categoria).all()
    for insc in inscritos:
        _sumar_puntos(insc.jugador_id, torneo_id, categoria, 'participacion', torneo.pts_participacion)
    db.session.commit()
    flash(f'Bracket generado para {categoria}.', 'success')
    return redirect(url_for('main.bracket', torneo_id=torneo_id, categoria=categoria))


@main.route('/torneos/<int:torneo_id>/bracket/resultado/<int:partido_id>', methods=['POST'])
@login_required
def resultado_bracket(torneo_id, partido_id):
    partido = Partido.query.get_or_404(partido_id)
    categoria = request.form.get('categoria')
    ganador_id = int(request.form.get('ganador_id'))
    resultado = request.form.get('resultado', '')
    perdedor_id = partido.jugador2_id if ganador_id == partido.jugador1_id else partido.jugador1_id
    partido.ganador_id = ganador_id
    partido.resultado = resultado
    partido.jugado = True
    db.session.commit()
    torneo = Torneo.query.get(torneo_id)
    if partido.fase == 'cuartos':
        semi_ronda = 1 if partido.ronda in [1, 2] else 2
        semi = Partido.query.filter_by(torneo_id=torneo_id, categoria=categoria, fase='semi', ronda=semi_ronda).first()
        if semi:
            if not semi.jugador1_id:
                semi.jugador1_id = ganador_id
            else:
                semi.jugador2_id = ganador_id
        _sumar_puntos(perdedor_id, torneo_id, categoria, 'cuartos', torneo.pts_cuartos)
    elif partido.fase == 'semi':
        final = Partido.query.filter_by(torneo_id=torneo_id, categoria=categoria, fase='final', ronda=1).first()
        if final:
            if not final.jugador1_id:
                final.jugador1_id = ganador_id
            else:
                final.jugador2_id = ganador_id
        tercero = Partido.query.filter_by(torneo_id=torneo_id, categoria=categoria, fase='tercer_lugar', ronda=1).first()
        if tercero:
            if not tercero.jugador1_id:
                tercero.jugador1_id = perdedor_id
            else:
                tercero.jugador2_id = perdedor_id
        _sumar_puntos(perdedor_id, torneo_id, categoria, 'semifinalista', torneo.pts_semifinalista)
    elif partido.fase == 'tercer_lugar':
        _sumar_puntos(ganador_id, torneo_id, categoria, 'tercer_lugar', torneo.pts_semifinalista)
        _sumar_puntos(perdedor_id, torneo_id, categoria, 'cuarto_lugar', torneo.pts_cuartos)
    elif partido.fase == 'final':
        _sumar_puntos(ganador_id, torneo_id, categoria, 'campeon', torneo.pts_campeon)
        _sumar_puntos(perdedor_id, torneo_id, categoria, 'finalista', torneo.pts_finalista)
        _actualizar_puntos_globales(ganador_id)
        _actualizar_puntos_globales(perdedor_id)
    db.session.commit()
    sio.emit('resultado_actualizado', {
        'torneo_id': torneo_id, 'categoria': categoria,
        'partido_id': partido_id, 'ganador_id': ganador_id
    })
    flash('Resultado registrado.', 'success')
    return redirect(url_for('main.bracket', torneo_id=torneo_id, categoria=categoria))


@main.route('/torneos/<int:torneo_id>/bracket/live/<int:partido_id>', methods=['POST'])
@login_required
def bracket_live(torneo_id, partido_id):
    data = request.get_json()
    sio.emit('marcador_live', {
        'torneo_id': torneo_id, 'partido_id': partido_id,
        'categoria': data.get('categoria'),
        'j1': data.get('j1'), 'j2': data.get('j2'),
        'pts1': data.get('pts1'), 'pts2': data.get('pts2'),
        'sets1': data.get('sets1'), 'sets2': data.get('sets2'),
        'set_actual': data.get('set_actual'),
        'historial': data.get('historial', [])
    })
    return {'ok': True}


# ─── HELPERS RANKING ────────────────────────────────────
def _sumar_puntos(jugador_id, torneo_id, categoria, posicion, puntos):
    if not jugador_id or puntos <= 0:
        return
    existente = PuntosRanking.query.filter_by(
        jugador_id=jugador_id, torneo_id=torneo_id,
        categoria=categoria, posicion_final=posicion
    ).first()
    if not existente:
        db.session.add(PuntosRanking(
            jugador_id=jugador_id, torneo_id=torneo_id,
            categoria=categoria, posicion_final=posicion, puntos=puntos
        ))


def _actualizar_puntos_globales(jugador_id):
    if not jugador_id:
        return
    total = db.session.query(db.func.sum(PuntosRanking.puntos))\
        .filter_by(jugador_id=jugador_id).scalar() or 0
    jugador = Jugador.query.get(jugador_id)
    if jugador:
        jugador.puntos_ranking = total


# ─── RANKING PÚBLICO ────────────────────────────────────
@main.route('/ranking')
def ranking():
    categoria = request.args.get('categoria', CATEGORIAS[0])
    torneo_id = request.args.get('torneo_id', None)
    torneos_lista = Torneo.query.order_by(Torneo.fecha.desc()).all()
    ranking_data = db.session.query(
        Jugador,
        db.func.sum(PuntosRanking.puntos).label('total_puntos'),
        db.func.count(PuntosRanking.id).label('torneos_jugados')
    ).join(PuntosRanking, Jugador.id == PuntosRanking.jugador_id)\
     .filter(PuntosRanking.categoria == categoria)\
     .group_by(Jugador.id)\
     .order_by(db.desc('total_puntos')).all()
    if torneo_id:
        ranking_data = db.session.query(
            Jugador,
            db.func.sum(PuntosRanking.puntos).label('total_puntos'),
            db.func.count(PuntosRanking.id).label('torneos_jugados')
        ).join(PuntosRanking, Jugador.id == PuntosRanking.jugador_id)\
         .filter(PuntosRanking.categoria == categoria, PuntosRanking.torneo_id == torneo_id)\
         .group_by(Jugador.id)\
         .order_by(db.desc('total_puntos')).all()
    return render_template('ranking/index.html',
        ranking=ranking_data,
        categorias=CATEGORIAS,
        categoria_actual=categoria,
        torneos=torneos_lista,
        torneo_id_actual=torneo_id
    )


# ─── PANEL PÚBLICO ──────────────────────────────────────
@main.route('/publico')
def panel_publico():
    torneo_id = request.args.get('torneo_id', None)
    categoria = request.args.get('categoria', None)
    torneos_activos = Torneo.query.filter_by(activo=True).order_by(Torneo.fecha.desc()).all()
    if not torneo_id and torneos_activos:
        torneo_id = torneos_activos[0].id
    torneo = Torneo.query.get(torneo_id) if torneo_id else None
    cats_con_inscritos = []
    if torneo:
        for cat in CATEGORIAS:
            count = Inscripcion.query.filter_by(torneo_id=torneo.id, categoria=cat).count()
            if count > 0:
                cats_con_inscritos.append({'cat': cat, 'count': count})
    if not categoria and cats_con_inscritos:
        categoria = cats_con_inscritos[0]['cat']
    grupos = []
    grupo_partidos = {}
    ultimos_resultados = []
    proximo_partido = None
    if torneo and categoria:
        grupos = Grupo.query.filter_by(torneo_id=torneo.id, categoria=categoria).order_by(Grupo.numero).all()
        for grupo in grupos:
            partidos_raw = Partido.query.filter_by(
                torneo_id=torneo.id, categoria=categoria, fase='grupos', grupo_id=grupo.id).all()
            grupo_partidos[grupo.id] = ordenar_partidos_sin_consecutivos(partidos_raw)
        ultimos_resultados = Partido.query.filter_by(
            torneo_id=torneo.id, categoria=categoria, fase='grupos', jugado=True
        ).order_by(Partido.id.desc()).limit(5).all()
        for grupo in grupos:
            for p in grupo_partidos.get(grupo.id, []):
                if not p.jugado:
                    proximo_partido = p
                    break
            if proximo_partido:
                break
    return render_template('publico/panel.html',
        torneos=torneos_activos, torneo=torneo,
        categoria_actual=categoria, cats_con_inscritos=cats_con_inscritos,
        grupos=grupos, grupo_partidos=grupo_partidos,
        ultimos_resultados=ultimos_resultados, proximo_partido=proximo_partido)
