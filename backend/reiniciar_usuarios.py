from main import app, db, User

with app.app_context():
    User.__table__.drop(db.engine, checkfirst=True)
    User.__table__.create(db.engine, checkfirst=True)

print("La tabla usuarios se eliminó y se creó nuevamente.")
