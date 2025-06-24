from app import create_app
from flask_migrate import Migrate, upgrade
from app import db

app = create_app()
migrate = Migrate(app, db)

if __name__ == '__main__':
    upgrade()
