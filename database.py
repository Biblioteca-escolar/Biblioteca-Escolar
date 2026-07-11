from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = "sqlite:///escolar.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # necessário para SQLite + FastAPI
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Classe base para todos os modelos ORM."""
    pass


def get_session():
    """Gerador de sessão — usado com FastAPI Depends."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db():
    """Cria as tabelas no banco a partir dos modelos ORM."""
    import models  # garante que os modelos estão registrados no Base.metadata
    Base.metadata.create_all(bind=engine)
