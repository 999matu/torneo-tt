import eventlet
eventlet.monkey_patch()

from app import create_app, socketio, db

app = create_app()

with app.app_context():
    db.create_all()
    try:
        db.engine.execute('ALTER TABLE inscripcion ADD COLUMN solo_en_grupo BOOLEAN DEFAULT 0')
        print("✅ Columna solo_en_grupo agregada")
    except Exception as e:
        print(f"ℹ️ {e}")

if __name__ == '__main__':
    socketio.run(app, debug=False)
