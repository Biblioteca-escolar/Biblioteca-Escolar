import sqlite3

DB_PATH = "escolar.db"


class DatabaseConfig:
    """Singleton: configuração única do banco para toda a aplicação."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.db_path = DB_PATH
            cls._instance.foreign_keys = True
            cls._instance.encoding = "UTF-8"
        return cls._instance


def get_conn() -> sqlite3.Connection:
    """Factory: cria e devolve uma conexão configurada."""
    config = DatabaseConfig()

    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row

    if config.foreign_keys:
        conn.execute("PRAGMA foreign_keys = ON")

    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id        TEXT PRIMARY KEY,
                nome      TEXT NOT NULL,
                matricula TEXT NOT NULL UNIQUE,
                tipo      TEXT NOT NULL,
                email     TEXT NOT NULL,
                senha     TEXT NOT NULL,
                ativo     BOOLEAN DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS livros (
                id                    TEXT PRIMARY KEY,
                titulo                TEXT NOT NULL,
                autor                 TEXT NOT NULL,
                isbn                  TEXT NOT NULL UNIQUE,
                quantidade_total      INTEGER NOT NULL,
                quantidade_disponivel INTEGER NOT NULL,
                ativo                 BOOLEAN DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS emprestimos (
                id                        TEXT PRIMARY KEY,
                usuario_id                TEXT NOT NULL,
                livro_id                  TEXT NOT NULL,
                data_emprestimo           TEXT NOT NULL,
                data_prevista_devolucao   TEXT NOT NULL,
                data_devolucao            TEXT,
                status                    TEXT DEFAULT 'ativo',
                multa                     REAL DEFAULT 0.0,
                FOREIGN KEY (usuario_id)  REFERENCES usuarios(id),
                FOREIGN KEY (livro_id)    REFERENCES livros(id)
            );

            CREATE TABLE IF NOT EXISTS reservas (
                id          TEXT PRIMARY KEY,
                usuario_id  TEXT NOT NULL,
                livro_id    TEXT NOT NULL,
                data_reserva TEXT NOT NULL,
                status      TEXT DEFAULT 'ativa',
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                FOREIGN KEY (livro_id)   REFERENCES livros(id)
            );

            CREATE TABLE IF NOT EXISTS multas (
                id            TEXT PRIMARY KEY,
                emprestimo_id TEXT NOT NULL,
                usuario_id    TEXT NOT NULL,
                livro_id      TEXT NOT NULL,
                valor         REAL NOT NULL,
                dias_atraso   INTEGER NOT NULL,
                data_registro TEXT NOT NULL,
                FOREIGN KEY (emprestimo_id) REFERENCES emprestimos(id),
                FOREIGN KEY (usuario_id)    REFERENCES usuarios(id),
                FOREIGN KEY (livro_id)      REFERENCES livros(id)
            );
        """)
        conn.commit()
