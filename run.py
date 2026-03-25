import eventlet
eventlet.monkey_patch()

from app import create_app, socketio, db

app = create_app()

with app.app_context():
    db.create_all()
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text('ALTER TABLE inscripcion ADD COLUMN solo_en_grupo BOOLEAN DEFAULT 0'))
            conn.commit()
    except Exception:
        pass

if __name__ == '__main__':
    socketio.run(app, debug=False)
