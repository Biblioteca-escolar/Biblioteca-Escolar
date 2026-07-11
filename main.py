from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional
import uuid

from fastapi import FastAPI, HTTPException, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func

import models
from schemas import (
    UsuarioEntrada, Usuario, LoginEntrada,
    LivroEntrada, Livro,
    EmprestimoEntrada, Emprestimo, RenovarEmprestimoEntrada,
    ReservaEntrada, Reserva,
    Multa, TipoUsuario
)
from database import get_session, init_db
from security import verificar_api_key, hash_senha


app = FastAPI(title="API Biblioteca Escolar", version="2.0.0")

DIAS_PADRAO_EMPRESTIMO = 7
LIMITE_EMPRESTIMOS_ATIVOS = 3
VALOR_MULTA_POR_DIA = 1.50


@app.on_event("startup")
def startup_event():
    init_db()


def agora() -> datetime:
    return datetime.now()


# ---------- helpers de busca (agora via ORM) ----------

def encontrar_usuario(session: Session, usuario_id: str) -> models.Usuario:
    usuario = session.get(models.Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return usuario


def encontrar_usuario_por_matricula(session: Session, matricula: str) -> models.Usuario:
    usuario = session.scalar(
        select(models.Usuario).where(models.Usuario.matricula == matricula)
    )
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return usuario


def encontrar_livro(session: Session, livro_id: str) -> models.Livro:
    livro = session.get(models.Livro, livro_id)
    if not livro:
        raise HTTPException(status_code=404, detail="Livro não encontrado")
    return livro


def encontrar_emprestimo(session: Session, emprestimo_id: str) -> models.Emprestimo:
    emprestimo = session.get(models.Emprestimo, emprestimo_id)
    if not emprestimo:
        raise HTTPException(status_code=404, detail="Empréstimo não encontrado")
    return emprestimo


def encontrar_reserva(session: Session, reserva_id: str) -> models.Reserva:
    reserva = session.get(models.Reserva, reserva_id)
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva não encontrada")
    return reserva


def verificar_matricula_duplicada(session: Session, matricula: str, ignorar_id: Optional[str] = None) -> None:
    stmt = select(models.Usuario).where(models.Usuario.matricula == matricula)
    if ignorar_id:
        stmt = stmt.where(models.Usuario.id != ignorar_id)
    if session.scalar(stmt):
        raise HTTPException(status_code=409, detail="Já existe um usuário com essa matrícula")


def verificar_isbn_duplicado(session: Session, isbn: str, ignorar_id: Optional[str] = None) -> None:
    stmt = select(models.Livro).where(models.Livro.isbn == isbn)
    if ignorar_id:
        stmt = stmt.where(models.Livro.id != ignorar_id)
    if session.scalar(stmt):
        raise HTTPException(status_code=409, detail="Já existe um livro com esse ISBN")


def emprestimos_ativos_do_usuario(session: Session, usuario_id: str) -> List[models.Emprestimo]:
    stmt = select(models.Emprestimo).where(
        models.Emprestimo.usuario_id == usuario_id,
        models.Emprestimo.status == "ativo",
    )
    return list(session.scalars(stmt).all())


def emprestimo_ativo_do_livro(session: Session, livro_id: str) -> bool:
    stmt = select(func.count()).select_from(models.Emprestimo).where(
        models.Emprestimo.livro_id == livro_id,
        models.Emprestimo.status == "ativo",
    )
    return session.scalar(stmt) > 0


def reservas_ativas_do_livro(session: Session, livro_id: str) -> List[models.Reserva]:
    stmt = select(models.Reserva).where(
        models.Reserva.livro_id == livro_id,
        models.Reserva.status == "ativa",
    )
    return list(session.scalars(stmt).all())


def tem_atraso(session: Session, usuario_id: str) -> bool:
    hoje = agora()
    stmt = select(models.Emprestimo).where(
        models.Emprestimo.usuario_id == usuario_id,
        models.Emprestimo.status == "ativo",
    )
    for emprestimo in session.scalars(stmt).all():
        prazo = datetime.fromisoformat(emprestimo.data_prevista_devolucao)
        if hoje > prazo:
            return True
    return False


def calcular_multa(data_prevista: str, data_devolucao: str) -> tuple[int, float]:
    previsto = datetime.fromisoformat(data_prevista)
    devolvido = datetime.fromisoformat(data_devolucao)
    atraso = max(0, (devolvido.date() - previsto.date()).days)
    valor = round(atraso * VALOR_MULTA_POR_DIA, 2)
    return atraso, valor


@app.get("/")
def raiz():
    return {"mensagem": "API Biblioteca Escolar funcionando! 📚"}


@app.post("/login")
def login(dados: LoginEntrada, session: Session = Depends(get_session)):
    usuario = encontrar_usuario_por_matricula(session, dados.matricula)
    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário inativo")
    if usuario.senha != hash_senha(dados.senha):
        raise HTTPException(status_code=401, detail="Senha inválida")
    return {
        "mensagem": "Login realizado com sucesso",
        "usuario_id": usuario.id,
        "nome": usuario.nome,
        "tipo": usuario.tipo,
    }


# ---------------- USUÁRIOS ----------------

@app.post("/usuarios", response_model=Usuario, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verificar_api_key)])
def criar_usuario(dados: UsuarioEntrada, session: Session = Depends(get_session)):
    verificar_matricula_duplicada(session, dados.matricula)

    usuario = models.Usuario(
        id=str(uuid.uuid4()),
        nome=dados.nome,
        matricula=dados.matricula,
        tipo=dados.tipo,
        email=dados.email,
        senha=hash_senha(dados.senha),
        ativo=True,
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario


@app.get("/usuarios", response_model=List[Usuario], dependencies=[Depends(verificar_api_key)])
def listar_usuarios(
    ativo: Optional[bool] = None,
    tipo: Optional[TipoUsuario] = None,
    session: Session = Depends(get_session),
):
    stmt = select(models.Usuario)
    if ativo is not None:
        stmt = stmt.where(models.Usuario.ativo == ativo)
    if tipo is not None:
        stmt = stmt.where(models.Usuario.tipo == tipo)
    return list(session.scalars(stmt).all())


@app.get("/usuarios/{usuario_id}", response_model=Usuario, dependencies=[Depends(verificar_api_key)])
def buscar_usuario(usuario_id: str, session: Session = Depends(get_session)):
    return encontrar_usuario(session, usuario_id)


@app.put("/usuarios/{usuario_id}", response_model=Usuario, dependencies=[Depends(verificar_api_key)])
def editar_usuario(usuario_id: str, dados: UsuarioEntrada, session: Session = Depends(get_session)):
    usuario = encontrar_usuario(session, usuario_id)
    verificar_matricula_duplicada(session, dados.matricula, ignorar_id=usuario_id)

    usuario.nome = dados.nome
    usuario.matricula = dados.matricula
    usuario.tipo = dados.tipo
    usuario.email = dados.email
    usuario.senha = hash_senha(dados.senha)

    session.commit()
    session.refresh(usuario)
    return usuario


@app.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verificar_api_key)])
def remover_usuario(usuario_id: str, session: Session = Depends(get_session)):
    usuario = encontrar_usuario(session, usuario_id)
    if emprestimos_ativos_do_usuario(session, usuario_id):
        raise HTTPException(status_code=409, detail="Não é possível remover usuário com empréstimos ativos")

    reservas_ativas = session.scalar(
        select(func.count()).select_from(models.Reserva).where(
            models.Reserva.usuario_id == usuario_id,
            models.Reserva.status == "ativa",
        )
    )
    if reservas_ativas > 0:
        raise HTTPException(status_code=409, detail="Não é possível remover usuário com reservas ativas")

    usuario.ativo = False
    session.commit()


# ---------------- LIVROS ----------------

@app.post("/livros", response_model=Livro, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verificar_api_key)])
def criar_livro(dados: LivroEntrada, session: Session = Depends(get_session)):
    verificar_isbn_duplicado(session, dados.isbn)

    livro = models.Livro(
        id=str(uuid.uuid4()),
        titulo=dados.titulo,
        autor=dados.autor,
        isbn=dados.isbn,
        quantidade_total=dados.quantidade_total,
        quantidade_disponivel=dados.quantidade_total,
        ativo=True,
    )
    session.add(livro)
    session.commit()
    session.refresh(livro)
    return livro


@app.get("/livros", response_model=List[Livro], dependencies=[Depends(verificar_api_key)])
def listar_livros(
    disponivel: Optional[bool] = None,
    titulo: Optional[str] = None,
    autor: Optional[str] = None,
    isbn: Optional[str] = None,
    session: Session = Depends(get_session),
):
    stmt = select(models.Livro)
    if disponivel is not None:
        if disponivel:
            stmt = stmt.where(models.Livro.quantidade_disponivel > 0)
        else:
            stmt = stmt.where(models.Livro.quantidade_disponivel <= 0)
    if titulo:
        stmt = stmt.where(models.Livro.titulo.ilike(f"%{titulo}%"))
    if autor:
        stmt = stmt.where(models.Livro.autor.ilike(f"%{autor}%"))
    if isbn:
        stmt = stmt.where(models.Livro.isbn.ilike(f"%{isbn}%"))
    return list(session.scalars(stmt).all())


@app.get("/livros/{livro_id}", response_model=Livro, dependencies=[Depends(verificar_api_key)])
def buscar_livro(livro_id: str, session: Session = Depends(get_session)):
    return encontrar_livro(session, livro_id)


@app.put("/livros/{livro_id}", response_model=Livro, dependencies=[Depends(verificar_api_key)])
def editar_livro(livro_id: str, dados: LivroEntrada, session: Session = Depends(get_session)):
    livro = encontrar_livro(session, livro_id)
    verificar_isbn_duplicado(session, dados.isbn, ignorar_id=livro_id)

    copias_emprestadas = livro.quantidade_total - livro.quantidade_disponivel
    if dados.quantidade_total < copias_emprestadas:
        raise HTTPException(
            status_code=409,
            detail="A quantidade total não pode ser menor que a quantidade já emprestada",
        )

    livro.titulo = dados.titulo
    livro.autor = dados.autor
    livro.isbn = dados.isbn
    livro.quantidade_total = dados.quantidade_total
    livro.quantidade_disponivel = dados.quantidade_total - copias_emprestadas

    session.commit()
    session.refresh(livro)
    return livro


@app.delete("/livros/{livro_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verificar_api_key)])
def remover_livro(livro_id: str, session: Session = Depends(get_session)):
    livro = encontrar_livro(session, livro_id)
    if emprestimo_ativo_do_livro(session, livro_id):
        raise HTTPException(status_code=409, detail="Não é possível remover livro com empréstimo ativo")
    if reservas_ativas_do_livro(session, livro_id):
        raise HTTPException(status_code=409, detail="Não é possível remover livro com reservas ativas")

    livro.ativo = False
    session.commit()


# ---------------- EMPRÉSTIMOS ----------------

@app.post("/emprestimos", response_model=Emprestimo, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verificar_api_key)])
def realizar_emprestimo(dados: EmprestimoEntrada, session: Session = Depends(get_session)):
    usuario = encontrar_usuario(session, dados.usuario_id)
    livro = encontrar_livro(session, dados.livro_id)

    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário inativo")
    if usuario.tipo == "funcionario":
        raise HTTPException(status_code=403, detail="Funcionários não realizam empréstimos")
    if tem_atraso(session, usuario.id):
        raise HTTPException(status_code=409, detail="Usuário possui empréstimo em atraso")
    if len(emprestimos_ativos_do_usuario(session, usuario.id)) >= LIMITE_EMPRESTIMOS_ATIVOS:
        raise HTTPException(status_code=409, detail="Usuário atingiu o limite de empréstimos ativos")
    if livro.quantidade_disponivel <= 0:
        raise HTTPException(status_code=409, detail="Livro indisponível")
    if any(r for r in reservas_ativas_do_livro(session, livro.id) if r.usuario_id != usuario.id):
        raise HTTPException(status_code=409, detail="Livro reservado por outro usuário")

    data_emprestimo = agora()
    data_prevista = data_emprestimo + timedelta(days=DIAS_PADRAO_EMPRESTIMO)

    livro.quantidade_disponivel -= 1

    emprestimo = models.Emprestimo(
        id=str(uuid.uuid4()),
        usuario_id=usuario.id,
        livro_id=livro.id,
        data_emprestimo=data_emprestimo.isoformat(),
        data_prevista_devolucao=data_prevista.isoformat(),
        data_devolucao=None,
        status="ativo",
        multa=0.0,
    )
    session.add(emprestimo)
    session.commit()
    session.refresh(emprestimo)
    return emprestimo


@app.get("/emprestimos", response_model=List[Emprestimo], dependencies=[Depends(verificar_api_key)])
def listar_emprestimos(status_: Optional[str] = None, session: Session = Depends(get_session)):
    stmt = select(models.Emprestimo)
    if status_:
        stmt = stmt.where(models.Emprestimo.status == status_)
    return list(session.scalars(stmt).all())


@app.get("/emprestimos/{emprestimo_id}", response_model=Emprestimo, dependencies=[Depends(verificar_api_key)])
def buscar_emprestimo(emprestimo_id: str, session: Session = Depends(get_session)):
    return encontrar_emprestimo(session, emprestimo_id)


@app.post("/emprestimos/{emprestimo_id}/devolver", response_model=Emprestimo, dependencies=[Depends(verificar_api_key)])
def devolver_emprestimo(emprestimo_id: str, session: Session = Depends(get_session)):
    emprestimo = encontrar_emprestimo(session, emprestimo_id)
    if emprestimo.status == "devolvido":
        raise HTTPException(status_code=409, detail="Este empréstimo já foi devolvido")

    livro = encontrar_livro(session, emprestimo.livro_id)
    data_devolucao = agora()
    atraso, valor = calcular_multa(emprestimo.data_prevista_devolucao, data_devolucao.isoformat())

    emprestimo.data_devolucao = data_devolucao.isoformat()
    emprestimo.status = "devolvido"
    emprestimo.multa = valor

    livro.quantidade_disponivel = min(livro.quantidade_total, livro.quantidade_disponivel + 1)

    if atraso > 0:
        multa = models.Multa(
            id=str(uuid.uuid4()),
            emprestimo_id=emprestimo_id,
            usuario_id=emprestimo.usuario_id,
            livro_id=emprestimo.livro_id,
            valor=valor,
            dias_atraso=atraso,
            data_registro=data_devolucao.isoformat(),
        )
        session.add(multa)

    session.commit()
    session.refresh(emprestimo)
    return emprestimo


@app.put("/emprestimos/{emprestimo_id}/renovar", response_model=Emprestimo, dependencies=[Depends(verificar_api_key)])
def renovar_emprestimo(emprestimo_id: str, dados: RenovarEmprestimoEntrada, session: Session = Depends(get_session)):
    emprestimo = encontrar_emprestimo(session, emprestimo_id)
    if emprestimo.status == "devolvido":
        raise HTTPException(status_code=409, detail="Não é possível renovar um empréstimo devolvido")

    if any(r for r in reservas_ativas_do_livro(session, emprestimo.livro_id) if r.usuario_id != emprestimo.usuario_id):
        raise HTTPException(status_code=409, detail="Não é possível renovar: há reserva ativa para este livro")

    nova_data = datetime.fromisoformat(emprestimo.data_prevista_devolucao) + timedelta(days=dados.dias_adicionais)
    emprestimo.data_prevista_devolucao = nova_data.isoformat()

    session.commit()
    session.refresh(emprestimo)
    return emprestimo


@app.get("/usuarios/{usuario_id}/emprestimos", response_model=List[Emprestimo], dependencies=[Depends(verificar_api_key)])
def emprestimos_do_usuario(usuario_id: str, session: Session = Depends(get_session)):
    encontrar_usuario(session, usuario_id)
    stmt = select(models.Emprestimo).where(models.Emprestimo.usuario_id == usuario_id)
    return list(session.scalars(stmt).all())


@app.get("/livros/{livro_id}/emprestimos", response_model=List[Emprestimo], dependencies=[Depends(verificar_api_key)])
def emprestimos_do_livro(livro_id: str, session: Session = Depends(get_session)):
    encontrar_livro(session, livro_id)
    stmt = select(models.Emprestimo).where(models.Emprestimo.livro_id == livro_id)
    return list(session.scalars(stmt).all())


# ---------------- RESERVAS ----------------

@app.post("/reservas", response_model=Reserva, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verificar_api_key)])
def criar_reserva(dados: ReservaEntrada, session: Session = Depends(get_session)):
    usuario = encontrar_usuario(session, dados.usuario_id)
    livro = encontrar_livro(session, dados.livro_id)

    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário inativo")
    if usuario.tipo == "funcionario":
        raise HTTPException(status_code=403, detail="Funcionários não realizam reservas")
    if livro.quantidade_disponivel > 0:
        raise HTTPException(status_code=409, detail="Reserva permitida apenas para livros indisponíveis")

    ja_reservado = session.scalar(
        select(func.count()).select_from(models.Reserva).where(
            models.Reserva.usuario_id == usuario.id,
            models.Reserva.livro_id == livro.id,
            models.Reserva.status == "ativa",
        )
    )
    if ja_reservado > 0:
        raise HTTPException(status_code=409, detail="Usuário já possui reserva ativa para este livro")

    reserva = models.Reserva(
        id=str(uuid.uuid4()),
        usuario_id=usuario.id,
        livro_id=livro.id,
        data_reserva=agora().isoformat(),
        status="ativa",
    )
    session.add(reserva)
    session.commit()
    session.refresh(reserva)
    return reserva


@app.get("/reservas", response_model=List[Reserva], dependencies=[Depends(verificar_api_key)])
def listar_reservas(status_: Optional[str] = None, session: Session = Depends(get_session)):
    stmt = select(models.Reserva)
    if status_:
        stmt = stmt.where(models.Reserva.status == status_)
    return list(session.scalars(stmt).all())


@app.get("/reservas/{reserva_id}", response_model=Reserva, dependencies=[Depends(verificar_api_key)])
def buscar_reserva(reserva_id: str, session: Session = Depends(get_session)):
    return encontrar_reserva(session, reserva_id)


@app.delete("/reservas/{reserva_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verificar_api_key)])
def cancelar_reserva(reserva_id: str, session: Session = Depends(get_session)):
    reserva = encontrar_reserva(session, reserva_id)
    if reserva.status != "ativa":
        raise HTTPException(status_code=409, detail="Só é possível cancelar reservas ativas")

    reserva.status = "cancelada"
    session.commit()


@app.get("/usuarios/{usuario_id}/reservas", response_model=List[Reserva], dependencies=[Depends(verificar_api_key)])
def reservas_do_usuario(usuario_id: str, session: Session = Depends(get_session)):
    encontrar_usuario(session, usuario_id)
    stmt = select(models.Reserva).where(models.Reserva.usuario_id == usuario_id)
    return list(session.scalars(stmt).all())


@app.get("/livros/{livro_id}/reservas", response_model=List[Reserva], dependencies=[Depends(verificar_api_key)])
def reservas_do_livro(livro_id: str, session: Session = Depends(get_session)):
    encontrar_livro(session, livro_id)
    stmt = select(models.Reserva).where(models.Reserva.livro_id == livro_id)
    return list(session.scalars(stmt).all())


# ---------------- MULTAS ----------------

@app.get("/multas", response_model=List[Multa], dependencies=[Depends(verificar_api_key)])
def listar_multas(session: Session = Depends(get_session)):
    return list(session.scalars(select(models.Multa)).all())


@app.get("/usuarios/{usuario_id}/multas", response_model=List[Multa], dependencies=[Depends(verificar_api_key)])
def multas_do_usuario(usuario_id: str, session: Session = Depends(get_session)):
    encontrar_usuario(session, usuario_id)
    stmt = select(models.Multa).where(models.Multa.usuario_id == usuario_id)
    return list(session.scalars(stmt).all())


# ---------------- NOTIFICAÇÕES ----------------

@app.get("/notificacoes/atrasos", dependencies=[Depends(verificar_api_key)])
def listar_atrasos(session: Session = Depends(get_session)):
    hoje = agora()
    atrasos = []

    stmt = select(models.Emprestimo).where(models.Emprestimo.status == "ativo")
    for emprestimo in session.scalars(stmt).all():
        prazo = datetime.fromisoformat(emprestimo.data_prevista_devolucao)
        if hoje > prazo:
            dias = max(0, (hoje.date() - prazo.date()).days)
            atrasos.append(
                {
                    "emprestimo_id": emprestimo.id,
                    "usuario_id": emprestimo.usuario_id,
                    "livro_id": emprestimo.livro_id,
                    "dias_atraso": dias,
                    "multa_estimativa": round(dias * VALOR_MULTA_POR_DIA, 2),
                }
            )

    return {"quantidade": len(atrasos), "atrasos": atrasos}
