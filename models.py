from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    matricula: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # aluno | professor | funcionario
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    senha: Mapped[str] = mapped_column(String(64), nullable=False)  # hash SHA-256
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    emprestimos: Mapped[list["Emprestimo"]] = relationship(
        "Emprestimo", back_populates="usuario"
    )
    reservas: Mapped[list["Reserva"]] = relationship(
        "Reserva", back_populates="usuario"
    )
    multas: Mapped[list["Multa"]] = relationship(
        "Multa", back_populates="usuario"
    )

    def __repr__(self) -> str:
        return f"Usuario(id={self.id!r}, nome={self.nome!r}, matricula={self.matricula!r})"


class Livro(Base):
    __tablename__ = "livros"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    autor: Mapped[str] = mapped_column(String(150), nullable=False)
    isbn: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    quantidade_total: Mapped[int] = mapped_column(Integer, nullable=False)
    quantidade_disponivel: Mapped[int] = mapped_column(Integer, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    emprestimos: Mapped[list["Emprestimo"]] = relationship(
        "Emprestimo", back_populates="livro"
    )
    reservas: Mapped[list["Reserva"]] = relationship(
        "Reserva", back_populates="livro"
    )
    multas: Mapped[list["Multa"]] = relationship(
        "Multa", back_populates="livro"
    )

    def __repr__(self) -> str:
        return f"Livro(id={self.id!r}, titulo={self.titulo!r}, isbn={self.isbn!r})"


class Emprestimo(Base):
    __tablename__ = "emprestimos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    livro_id: Mapped[str] = mapped_column(ForeignKey("livros.id"), nullable=False)
    data_emprestimo: Mapped[str] = mapped_column(String(40), nullable=False)
    data_prevista_devolucao: Mapped[str] = mapped_column(String(40), nullable=False)
    data_devolucao: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ativo")  # ativo | devolvido
    multa: Mapped[float] = mapped_column(Float, default=0.0)

    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="emprestimos")
    livro: Mapped["Livro"] = relationship("Livro", back_populates="emprestimos")
    multas: Mapped[list["Multa"]] = relationship("Multa", back_populates="emprestimo")

    def __repr__(self) -> str:
        return f"Emprestimo(id={self.id!r}, status={self.status!r})"


class Reserva(Base):
    __tablename__ = "reservas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    livro_id: Mapped[str] = mapped_column(ForeignKey("livros.id"), nullable=False)
    data_reserva: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ativa")  # ativa | cancelada | atendida

    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="reservas")
    livro: Mapped["Livro"] = relationship("Livro", back_populates="reservas")

    def __repr__(self) -> str:
        return f"Reserva(id={self.id!r}, status={self.status!r})"


class Multa(Base):
    __tablename__ = "multas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    emprestimo_id: Mapped[str] = mapped_column(ForeignKey("emprestimos.id"), nullable=False)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    livro_id: Mapped[str] = mapped_column(ForeignKey("livros.id"), nullable=False)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    dias_atraso: Mapped[int] = mapped_column(Integer, nullable=False)
    data_registro: Mapped[str] = mapped_column(String(40), nullable=False)

    emprestimo: Mapped["Emprestimo"] = relationship("Emprestimo", back_populates="multas")
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="multas")
    livro: Mapped["Livro"] = relationship("Livro", back_populates="multas")

    def __repr__(self) -> str:
        return f"Multa(id={self.id!r}, valor={self.valor!r})"
