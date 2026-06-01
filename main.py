from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from typing import List, Optional, Literal
import uuid

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field


app = FastAPI(title="API Biblioteca Escolar", version="1.0.0")



TipoUsuario = Literal["aluno", "professor", "funcionario"]


class UsuarioEntrada(BaseModel):
    nome: str
    matricula: str
    tipo: TipoUsuario
    email: str
    senha: str


class Usuario(UsuarioEntrada):
    id: str
    senha: str
    ativo: bool = True


class LoginEntrada(BaseModel):
    matricula: str
    senha: str


class LivroEntrada(BaseModel):
    titulo: str
    autor: str
    isbn: str
    quantidade_total: int = Field(gt=0)


class Livro(LivroEntrada):
    id: str
    quantidade_disponivel: int
    ativo: bool = True


class EmprestimoEntrada(BaseModel):
    usuario_id: str
    livro_id: str


class Emprestimo(BaseModel):
    id: str
    usuario_id: str
    livro_id: str
    data_emprestimo: str
    data_prevista_devolucao: str
    data_devolucao: Optional[str] = None
    status: Literal["ativo", "devolvido"] = "ativo"
    multa: float = 0.0


class RenovarEmprestimoEntrada(BaseModel):
    dias_adicionais: int = Field(default=7, ge=1, le=30)


class ReservaEntrada(BaseModel):
    usuario_id: str
    livro_id: str


class Reserva(BaseModel):
    id: str
    usuario_id: str
    livro_id: str
    data_reserva: str
    status: Literal["ativa", "cancelada", "atendida"] = "ativa"


class Multa(BaseModel):
    id: str
    emprestimo_id: str
    usuario_id: str
    livro_id: str
    valor: float
    dias_atraso: int
    data_registro: str



usuarios_db: List[Usuario] = []
livros_db: List[Livro] = []
emprestimos_db: List[Emprestimo] = []
reservas_db: List[Reserva] = []
multas_db: List[Multa] = []

DIAS_PADRAO_EMPRESTIMO = 7
LIMITE_EMPRESTIMOS_ATIVOS = 3
VALOR_MULTA_POR_DIA = 1.50



def hash_senha(senha: str) -> str:
    return sha256(senha.encode("utf-8")).hexdigest()


def agora() -> datetime:
    return datetime.now()


def encontrar_usuario(usuario_id: str) -> Usuario:
    for usuario in usuarios_db:
        if usuario.id == usuario_id:
            return usuario
    raise HTTPException(status_code=404, detail="Usuário não encontrado")


def encontrar_usuario_por_matricula(matricula: str) -> Usuario:
    for usuario in usuarios_db:
        if usuario.matricula == matricula:
            return usuario
    raise HTTPException(status_code=404, detail="Usuário não encontrado")


def encontrar_livro(livro_id: str) -> Livro:
    for livro in livros_db:
        if livro.id == livro_id:
            return livro
    raise HTTPException(status_code=404, detail="Livro não encontrado")


def encontrar_emprestimo(emprestimo_id: str) -> Emprestimo:
    for emprestimo in emprestimos_db:
        if emprestimo.id == emprestimo_id:
            return emprestimo
    raise HTTPException(status_code=404, detail="Empréstimo não encontrado")


def encontrar_reserva(reserva_id: str) -> Reserva:
    for reserva in reservas_db:
        if reserva.id == reserva_id:
            return reserva
    raise HTTPException(status_code=404, detail="Reserva não encontrada")


def verificar_matricula_duplicada(matricula: str, ignorar_id: Optional[str] = None) -> None:
    for usuario in usuarios_db:
        if usuario.matricula == matricula and usuario.id != ignorar_id:
            raise HTTPException(status_code=409, detail="Já existe um usuário com essa matrícula")


def verificar_isbn_duplicado(isbn: str, ignorar_id: Optional[str] = None) -> None:
    for livro in livros_db:
        if livro.isbn == isbn and livro.id != ignorar_id:
            raise HTTPException(status_code=409, detail="Já existe um livro com esse ISBN")


def emprestimos_ativos_do_usuario(usuario_id: str) -> List[Emprestimo]:
    return [e for e in emprestimos_db if e.usuario_id == usuario_id and e.status == "ativo"]


def emprestimo_ativo_do_livro(livro_id: str) -> bool:
    return any(e for e in emprestimos_db if e.livro_id == livro_id and e.status == "ativo")


def reservas_ativas_do_livro(livro_id: str) -> List[Reserva]:
    return [r for r in reservas_db if r.livro_id == livro_id and r.status == "ativa"]


def tem_atraso(usuario_id: str) -> bool:
    hoje = agora()
    for emprestimo in emprestimos_db:
        if emprestimo.usuario_id == usuario_id and emprestimo.status == "ativo":
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
def login(dados: LoginEntrada):
    usuario = encontrar_usuario_por_matricula(dados.matricula)
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



@app.post("/usuarios", response_model=Usuario, status_code=status.HTTP_201_CREATED)
def criar_usuario(dados: UsuarioEntrada):
    verificar_matricula_duplicada(dados.matricula)
    novo = Usuario(
        id=str(uuid.uuid4()),
        nome=dados.nome,
        matricula=dados.matricula,
        tipo=dados.tipo,
        email=dados.email,
        senha=hash_senha(dados.senha),
        ativo=True,
    )
    usuarios_db.append(novo)
    return novo


@app.get("/usuarios", response_model=List[Usuario])
def listar_usuarios(ativo: Optional[bool] = None, tipo: Optional[TipoUsuario] = None):
    resultado = usuarios_db
    if ativo is not None:
        resultado = [u for u in resultado if u.ativo == ativo]
    if tipo is not None:
        resultado = [u for u in resultado if u.tipo == tipo]
    return resultado


@app.get("/usuarios/{usuario_id}", response_model=Usuario)
def buscar_usuario(usuario_id: str):
    return encontrar_usuario(usuario_id)


@app.put("/usuarios/{usuario_id}", response_model=Usuario)
def editar_usuario(usuario_id: str, dados: UsuarioEntrada):
    usuario = encontrar_usuario(usuario_id)
    verificar_matricula_duplicada(dados.matricula, ignorar_id=usuario_id)
    usuario.nome = dados.nome
    usuario.matricula = dados.matricula
    usuario.tipo = dados.tipo
    usuario.email = dados.email
    usuario.senha = hash_senha(dados.senha)
    return usuario


@app.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_usuario(usuario_id: str):
    usuario = encontrar_usuario(usuario_id)
    if emprestimos_ativos_do_usuario(usuario_id):
        raise HTTPException(status_code=409, detail="Não é possível remover usuário com empréstimos ativos")
    if any(r for r in reservas_db if r.usuario_id == usuario_id and r.status == "ativa"):
        raise HTTPException(status_code=409, detail="Não é possível remover usuário com reservas ativas")
    usuario.ativo = False
    return



@app.post("/livros", response_model=Livro, status_code=status.HTTP_201_CREATED)
def criar_livro(dados: LivroEntrada):
    verificar_isbn_duplicado(dados.isbn)
    novo = Livro(
        id=str(uuid.uuid4()),
        titulo=dados.titulo,
        autor=dados.autor,
        isbn=dados.isbn,
        quantidade_total=dados.quantidade_total,
        quantidade_disponivel=dados.quantidade_total,
        ativo=True,
    )
    livros_db.append(novo)
    return novo


@app.get("/livros", response_model=List[Livro])
def listar_livros(
    disponivel: Optional[bool] = None,
    titulo: Optional[str] = None,
    autor: Optional[str] = None,
    isbn: Optional[str] = None,
):
    resultado = livros_db
    if disponivel is not None:
        resultado = [l for l in resultado if (l.quantidade_disponivel > 0) == disponivel]
    if titulo:
        t = titulo.lower()
        resultado = [l for l in resultado if t in l.titulo.lower()]
    if autor:
        a = autor.lower()
        resultado = [l for l in resultado if a in l.autor.lower()]
    if isbn:
        i = isbn.lower()
        resultado = [l for l in resultado if i in l.isbn.lower()]
    return resultado


@app.get("/livros/{livro_id}", response_model=Livro)
def buscar_livro(livro_id: str):
    return encontrar_livro(livro_id)


@app.put("/livros/{livro_id}", response_model=Livro)
def editar_livro(livro_id: str, dados: LivroEntrada):
    livro = encontrar_livro(livro_id)
    verificar_isbn_duplicado(dados.isbn, ignorar_id=livro_id)

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
    return livro


@app.delete("/livros/{livro_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_livro(livro_id: str):
    livro = encontrar_livro(livro_id)
    if emprestimo_ativo_do_livro(livro_id):
        raise HTTPException(status_code=409, detail="Não é possível remover livro com empréstimo ativo")
    if reservas_ativas_do_livro(livro_id):
        raise HTTPException(status_code=409, detail="Não é possível remover livro com reservas ativas")
    livro.ativo = False
    return



@app.post("/emprestimos", response_model=Emprestimo, status_code=status.HTTP_201_CREATED)
def realizar_emprestimo(dados: EmprestimoEntrada):
    usuario = encontrar_usuario(dados.usuario_id)
    livro = encontrar_livro(dados.livro_id)

    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário inativo")
    if usuario.tipo == "funcionario":
        raise HTTPException(status_code=403, detail="Funcionários não realizam empréstimos")
    if tem_atraso(usuario.id):
        raise HTTPException(status_code=409, detail="Usuário possui empréstimo em atraso")
    if len(emprestimos_ativos_do_usuario(usuario.id)) >= LIMITE_EMPRESTIMOS_ATIVOS:
        raise HTTPException(status_code=409, detail="Usuário atingiu o limite de empréstimos ativos")
    if livro.quantidade_disponivel <= 0:
        raise HTTPException(status_code=409, detail="Livro indisponível")
    if any(r for r in reservas_ativas_do_livro(livro.id) if r.usuario_id != usuario.id):
        raise HTTPException(status_code=409, detail="Livro reservado por outro usuário")

    livro.quantidade_disponivel -= 1
    data_emprestimo = agora()
    data_prevista = data_emprestimo + timedelta(days=DIAS_PADRAO_EMPRESTIMO)

    novo = Emprestimo(
        id=str(uuid.uuid4()),
        usuario_id=usuario.id,
        livro_id=livro.id,
        data_emprestimo=data_emprestimo.isoformat(),
        data_prevista_devolucao=data_prevista.isoformat(),
        data_devolucao=None,
        status="ativo",
        multa=0.0,
    )
    emprestimos_db.append(novo)
    return novo


@app.get("/emprestimos", response_model=List[Emprestimo])
def listar_emprestimos(status_: Optional[Literal["ativo", "devolvido"]] = None):
    resultado = emprestimos_db
    if status_:
        resultado = [e for e in resultado if e.status == status_]
    return resultado


@app.get("/emprestimos/{emprestimo_id}", response_model=Emprestimo)
def buscar_emprestimo(emprestimo_id: str):
    return encontrar_emprestimo(emprestimo_id)


@app.post("/emprestimos/{emprestimo_id}/devolver", response_model=Emprestimo)
def devolver_emprestimo(emprestimo_id: str):
    emprestimo = encontrar_emprestimo(emprestimo_id)
    if emprestimo.status == "devolvido":
        raise HTTPException(status_code=409, detail="Este empréstimo já foi devolvido")

    livro = encontrar_livro(emprestimo.livro_id)

    data_devolucao = agora()
    emprestimo.data_devolucao = data_devolucao.isoformat()
    emprestimo.status = "devolvido"
    livro.quantidade_disponivel = min(livro.quantidade_total, livro.quantidade_disponivel + 1)

    atraso, valor = calcular_multa(emprestimo.data_prevista_devolucao, emprestimo.data_devolucao)
    emprestimo.multa = valor

    if atraso > 0:
        multa = Multa(
            id=str(uuid.uuid4()),
            emprestimo_id=emprestimo.id,
            usuario_id=emprestimo.usuario_id,
            livro_id=emprestimo.livro_id,
            valor=valor,
            dias_atraso=atraso,
            data_registro=data_devolucao.isoformat(),
        )
        multas_db.append(multa)

    return emprestimo


@app.put("/emprestimos/{emprestimo_id}/renovar", response_model=Emprestimo)
def renovar_emprestimo(emprestimo_id: str, dados: RenovarEmprestimoEntrada):
    emprestimo = encontrar_emprestimo(emprestimo_id)
    if emprestimo.status == "devolvido":
        raise HTTPException(status_code=409, detail="Não é possível renovar um empréstimo devolvido")

    livro = encontrar_livro(emprestimo.livro_id)
    if any(r for r in reservas_ativas_do_livro(livro.id) if r.usuario_id != emprestimo.usuario_id):
        raise HTTPException(status_code=409, detail="Não é possível renovar: há reserva ativa para este livro")

    nova_data = datetime.fromisoformat(emprestimo.data_prevista_devolucao) + timedelta(days=dados.dias_adicionais)
    emprestimo.data_prevista_devolucao = nova_data.isoformat()
    return emprestimo


@app.get("/usuarios/{usuario_id}/emprestimos", response_model=List[Emprestimo])
def emprestimos_do_usuario(usuario_id: str):
    encontrar_usuario(usuario_id)
    return [e for e in emprestimos_db if e.usuario_id == usuario_id]


@app.get("/livros/{livro_id}/emprestimos", response_model=List[Emprestimo])
def emprestimos_do_livro(livro_id: str):
    encontrar_livro(livro_id)
    return [e for e in emprestimos_db if e.livro_id == livro_id]



@app.post("/reservas", response_model=Reserva, status_code=status.HTTP_201_CREATED)
def criar_reserva(dados: ReservaEntrada):
    usuario = encontrar_usuario(dados.usuario_id)
    livro = encontrar_livro(dados.livro_id)

    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário inativo")
    if usuario.tipo == "funcionario":
        raise HTTPException(status_code=403, detail="Funcionários não realizam reservas")
    if livro.quantidade_disponivel > 0:
        raise HTTPException(status_code=409, detail="Reserva permitida apenas para livros indisponíveis")
    if any(r for r in reservas_db if r.usuario_id == usuario.id and r.livro_id == livro.id and r.status == "ativa"):
        raise HTTPException(status_code=409, detail="Usuário já possui reserva ativa para este livro")

    nova = Reserva(
        id=str(uuid.uuid4()),
        usuario_id=usuario.id,
        livro_id=livro.id,
        data_reserva=agora().isoformat(),
        status="ativa",
    )
    reservas_db.append(nova)
    return nova


@app.get("/reservas", response_model=List[Reserva])
def listar_reservas(status_: Optional[Literal["ativa", "cancelada", "atendida"]] = None):
    resultado = reservas_db
    if status_:
        resultado = [r for r in resultado if r.status == status_]
    return resultado


@app.get("/reservas/{reserva_id}", response_model=Reserva)
def buscar_reserva(reserva_id: str):
    return encontrar_reserva(reserva_id)


@app.delete("/reservas/{reserva_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_reserva(reserva_id: str):
    reserva = encontrar_reserva(reserva_id)
    if reserva.status != "ativa":
        raise HTTPException(status_code=409, detail="Só é possível cancelar reservas ativas")
    reserva.status = "cancelada"
    return


@app.get("/usuarios/{usuario_id}/reservas", response_model=List[Reserva])
def reservas_do_usuario(usuario_id: str):
    encontrar_usuario(usuario_id)
    return [r for r in reservas_db if r.usuario_id == usuario_id]


@app.get("/livros/{livro_id}/reservas", response_model=List[Reserva])
def reservas_do_livro(livro_id: str):
    encontrar_livro(livro_id)
    return [r for r in reservas_db if r.livro_id == livro_id]



@app.get("/multas", response_model=List[Multa])
def listar_multas():
    return multas_db


@app.get("/usuarios/{usuario_id}/multas", response_model=List[Multa])
def multas_do_usuario(usuario_id: str):
    encontrar_usuario(usuario_id)
    return [m for m in multas_db if m.usuario_id == usuario_id]


@app.get("/notificacoes/atrasos")
def listar_atrasos():
    hoje = agora()
    atrasos = []
    for emprestimo in emprestimos_db:
        if emprestimo.status == "ativo":
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
