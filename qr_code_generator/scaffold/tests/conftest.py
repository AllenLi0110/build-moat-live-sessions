import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app import routes

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_SessionLocal = sessionmaker(bind=_engine)


@pytest.fixture(autouse=True)
def reset_state():
    Base.metadata.create_all(bind=_engine)
    routes.redirect_cache.clear()
    yield
    routes.redirect_cache.clear()
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def db(reset_state):
    session = _SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, follow_redirects=False) as c:
        yield c
    app.dependency_overrides.clear()
