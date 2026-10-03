import os
import pytest

test_db_file = os.path.join(os.path.dirname(__file__), "test_quiz.db")
os.environ['DB_ENGINE'] = 'sqlite'
os.environ['SQLITE_PATH'] = test_db_file

from config import Config

Config.DB_ENGINE = 'sqlite'
Config.SQLITE_PATH = test_db_file
Config.SECRET_KEY = 'test_secret_key'
Config.TEACHER_SUPERKEY = '1'
Config.ADMIN_EMAIL = 'admin@annauniv.edu'
Config.ADMIN_PASSWORD = 'admin123'

from app import create_app
from init_db import init_db

@pytest.fixture(scope='function')
def app():
    init_db("schema.sql", reset=True)

    flask_app = create_app(Config)
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False

    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def login_helper(client, email, password):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)
