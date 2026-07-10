from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional
import uuid

from fastapi import FastAPI, HTTPException, status, Depends
from models import (
    UsuarioEntrada, Usuario, LoginEntrada,
    LivroEntrada, Livro,
    EmprestimoEntrada, Emprestimo, RenovarEmprestimoEntrada,
    ReservaEntrada, Reserva,
    Multa, TipoUsuario
)
from database import get_conn, init_db
from security import verificar_api_key, hash_senha


app = FastAPI(title="API Biblioteca Escolar", version="1.0.0")

DIAS_PADRAO_EMPRESTIMO = 7
LIMITE_EMPRESTIMOS_ATIVOS = 3
VALOR_MULTA_POR_DIA = 1.50


@app.on_event("startup")
def startup_event():
    init_db()


def agora() -> datetime:
    return datetime.now()


def encontrar_usuario(usuario_id: str) -> Usuario:
    with get_conn() as conn:
        cursor = conn.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,))
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return Usuario(
        id=row["id"],
        nome=row["nome"],
        matricula=row["matricula"],
        tipo=row["tipo"],
        email=row["email"],
        senha=row["senha"],
        ativo=bool(row["ativo"])
    )


def encontrar_usuario_por_matricula(matricula: str) -> Usuario:
    with get_conn() as conn:
        cursor = conn.execute("SELECT * FROM usuarios WHERE matricula = ?", (matricula,))
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return Usuario(
        id=row["id"],
        nome=row["nome"],
        matricula=row["matricula"],
        tipo=row["tipo"],
        email=row["email"],
        senha=row["senha"],
        ativo=bool(row["ativo"])
    )


def encontrar_livro(livro_id: str) -> Livro:
    with get_conn() as conn:
        cursor = conn.execute("SELECT * FROM livros WHERE id = ?", (livro_id,))
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Livro não encontrado")
    return Livro(
        id=row["id"],
        titulo=row["titulo"],
        autor=row["autor"],
        isbn=row["isbn"],
        quantidade_total=row["quantidade_total"],
        quantidade_disponivel=row["quantidade_disponivel"],
        ativo=bool(row["ativo"])
    )


def encontrar_emprestimo(emprestimo_id: str) -> Emprestimo:
    with get_conn() as conn:
        cursor = conn.execute("SELECT * FROM emprestimos WHERE id = ?", (emprestimo_id,))
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Empréstimo não encontrado")
    return Emprestimo(
        id=row["id"],
        usuario_id=row["usuario_id"],
        livro_id=row["livro_id"],
        data_emprestimo=row["data_emprestimo"],
        data_prevista_devolucao=row["data_prevista_devolucao"],
        data_devolucao=row["data_devolucao"],
        status=row["status"],
        multa=row["multa"]
    )


def encontrar_reserva(reserva_id: str) -> Reserva:
    with get_conn() as conn:
        cursor = conn.execute("SELECT * FROM reservas WHERE id = ?", (reserva_id,))
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Reserva não encontrada")
    return Reserva(
        id=row["id"],
        usuario_id=row["usuario_id"],
        livro_id=row["livro_id"],
        data_reserva=row["data_reserva"],
        status=row["status"]
    )


def verificar_matricula_duplicada(matricula: str, ignorar_id: Optional[str] = None) -> None:
    with get_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM usuarios WHERE matricula = ? AND id != ?",
            (matricula, ignorar_id or "")
        )
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Já existe um usuário com essa matrícula")


def verificar_isbn_duplicado(isbn: str, ignorar_id: Optional[str] = None) -> None:
    with get_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM livros WHERE isbn = ? AND id != ?",
            (isbn, ignorar_id or "")
        )
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Já existe um livro com esse ISBN")


def emprestimos_ativos_do_usuario(usuario_id: str) -> List[Emprestimo]:
    with get_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM emprestimos WHERE usuario_id = ? AND status = 'ativo'",
            (usuario_id,)
        )
        rows = cursor.fetchall()
    return [
        Emprestimo(
            id=r["id"],
            usuario_id=r["usuario_id"],
            livro_id=r["livro_id"],
            data_emprestimo=r["data_emprestimo"],
            data_prevista_devolucao=r["data_prevista_devolucao"],
            data_devolucao=r["data_devolucao"],
            status=r["status"],
            multa=r["multa"]
        )
        for r in rows
    ]


def emprestimo_ativo_do_livro(livro_id: str) -> bool:
    with get_conn() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM emprestimos WHERE livro_id = ? AND status = 'ativo'",
            (livro_id,)
        )
        return cursor.fetchone()["count"] > 0


def reservas_ativas_do_livro(livro_id: str) -> List[Reserva]:
    with get_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM reservas WHERE livro_id = ? AND status = 'ativa'",
            (livro_id,)
        )
        rows = cursor.fetchall()
    return [
        Reserva(
            id=r["id"],
            usuario_id=r["usuario_id"],
            livro_id=r["livro_id"],
            data_reserva=r["data_reserva"],
            status=r["status"]
        )
        for r in rows
    ]


def tem_atraso(usuario_id: str) -> bool:
    hoje = agora()
    with get_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM emprestimos WHERE usuario_id = ? AND status = 'ativo'",
            (usuario_id,)
        )
        for row in cursor.fetchall():
            prazo = datetime.fromisoformat(row["data_prevista_devolucao"])
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
    novo_id = str(uuid.uuid4())
    
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO usuarios (id, nome, matricula, tipo, email, senha, ativo) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (novo_id, dados.nome, dados.matricula, dados.tipo, dados.email, hash_senha(dados.senha), 1)
        )
        conn.commit()
    
    return Usuario(
        id=novo_id,
        nome=dados.nome,
        matricula=dados.matricula,
        tipo=dados.tipo,
        email=dados.email,
        senha=hash_senha(dados.senha),
        ativo=True
    )


@app.get("/usuarios", response_model=List[Usuario])
def listar_usuarios(ativo: Optional[bool] = None, tipo: Optional[TipoUsuario] = None):
    with get_conn() as conn:
        query = "SELECT * FROM usuarios WHERE 1=1"
        params = []
        
        if ativo is not None:
            query += " AND ativo = ?"
            params.append(1 if ativo else 0)
        if tipo is not None:
            query += " AND tipo = ?"
            params.append(tipo)
        
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
    
    return [
        Usuario(
            id=r["id"],
            nome=r["nome"],
            matricula=r["matricula"],
            tipo=r["tipo"],
            email=r["email"],
            senha=r["senha"],
            ativo=bool(r["ativo"])
        )
        for r in rows
    ]


@app.get("/usuarios/{usuario_id}", response_model=Usuario)
def buscar_usuario(usuario_id: str):
    return encontrar_usuario(usuario_id)


@app.put("/usuarios/{usuario_id}", response_model=Usuario)
def editar_usuario(usuario_id: str, dados: UsuarioEntrada):
    usuario = encontrar_usuario(usuario_id)
    verificar_matricula_duplicada(dados.matricula, ignorar_id=usuario_id)
    
    with get_conn() as conn:
        conn.execute(
            "UPDATE usuarios SET nome = ?, matricula = ?, tipo = ?, email = ?, senha = ? WHERE id = ?",
            (dados.nome, dados.matricula, dados.tipo, dados.email, hash_senha(dados.senha), usuario_id)
        )
        conn.commit()
    
    return Usuario(
        id=usuario_id,
        nome=dados.nome,
        matricula=dados.matricula,
        tipo=dados.tipo,
        email=dados.email,
        senha=hash_senha(dados.senha),
        ativo=usuario.ativo
    )


@app.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_usuario(usuario_id: str):
    usuario = encontrar_usuario(usuario_id)
    if emprestimos_ativos_do_usuario(usuario_id):
        raise HTTPException(status_code=409, detail="Não é possível remover usuário com empréstimos ativos")
    
    with get_conn() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM reservas WHERE usuario_id = ? AND status = 'ativa'",
            (usuario_id,)
        )
        if cursor.fetchone()["count"] > 0:
            raise HTTPException(status_code=409, detail="Não é possível remover usuário com reservas ativas")
    
    with get_conn() as conn:
        conn.execute("UPDATE usuarios SET ativo = 0 WHERE id = ?", (usuario_id,))
        conn.commit()



@app.post("/livros", response_model=Livro, status_code=status.HTTP_201_CREATED)
def criar_livro(dados: LivroEntrada):
    verificar_isbn_duplicado(dados.isbn)
    novo_id = str(uuid.uuid4())
    
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO livros (id, titulo, autor, isbn, quantidade_total, quantidade_disponivel, ativo) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (novo_id, dados.titulo, dados.autor, dados.isbn, dados.quantidade_total, dados.quantidade_total, 1)
        )
        conn.commit()
    
    return Livro(
        id=novo_id,
        titulo=dados.titulo,
        autor=dados.autor,
        isbn=dados.isbn,
        quantidade_total=dados.quantidade_total,
        quantidade_disponivel=dados.quantidade_total,
        ativo=True
    )


@app.get("/livros", response_model=List[Livro])
def listar_livros(
    disponivel: Optional[bool] = None,
    titulo: Optional[str] = None,
    autor: Optional[str] = None,
    isbn: Optional[str] = None,
):
    with get_conn() as conn:
        query = "SELECT * FROM livros WHERE 1=1"
        params = []
        
        if disponivel is not None:
            if disponivel:
                query += " AND quantidade_disponivel > 0"
            else:
                query += " AND quantidade_disponivel <= 0"
        if titulo:
            query += " AND LOWER(titulo) LIKE LOWER(?)"
            params.append(f"%{titulo}%")
        if autor:
            query += " AND LOWER(autor) LIKE LOWER(?)"
            params.append(f"%{autor}%")
        if isbn:
            query += " AND LOWER(isbn) LIKE LOWER(?)"
            params.append(f"%{isbn}%")
        
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
    
    return [
        Livro(
            id=r["id"],
            titulo=r["titulo"],
            autor=r["autor"],
            isbn=r["isbn"],
            quantidade_total=r["quantidade_total"],
            quantidade_disponivel=r["quantidade_disponivel"],
            ativo=bool(r["ativo"])
        )
        for r in rows
    ]


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

    nova_quantidade_disponivel = dados.quantidade_total - copias_emprestadas
    
    with get_conn() as conn:
        conn.execute(
            "UPDATE livros SET titulo = ?, autor = ?, isbn = ?, quantidade_total = ?, quantidade_disponivel = ? WHERE id = ?",
            (dados.titulo, dados.autor, dados.isbn, dados.quantidade_total, nova_quantidade_disponivel, livro_id)
        )
        conn.commit()
    
    return Livro(
        id=livro_id,
        titulo=dados.titulo,
        autor=dados.autor,
        isbn=dados.isbn,
        quantidade_total=dados.quantidade_total,
        quantidade_disponivel=nova_quantidade_disponivel,
        ativo=livro.ativo
    )


@app.delete("/livros/{livro_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_livro(livro_id: str):
    livro = encontrar_livro(livro_id)
    if emprestimo_ativo_do_livro(livro_id):
        raise HTTPException(status_code=409, detail="Não é possível remover livro com empréstimo ativo")
    if reservas_ativas_do_livro(livro_id):
        raise HTTPException(status_code=409, detail="Não é possível remover livro com reservas ativas")
    
    with get_conn() as conn:
        conn.execute("UPDATE livros SET ativo = 0 WHERE id = ?", (livro_id,))
        conn.commit()



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

    novo_id = str(uuid.uuid4())
    data_emprestimo = agora()
    data_prevista = data_emprestimo + timedelta(days=DIAS_PADRAO_EMPRESTIMO)

    with get_conn() as conn:
        conn.execute(
            "UPDATE livros SET quantidade_disponivel = quantidade_disponivel - 1 WHERE id = ?",
            (livro.id,)
        )
        conn.execute(
            "INSERT INTO emprestimos (id, usuario_id, livro_id, data_emprestimo, data_prevista_devolucao, data_devolucao, status, multa) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (novo_id, usuario.id, livro.id, data_emprestimo.isoformat(), data_prevista.isoformat(), None, "ativo", 0.0)
        )
        conn.commit()

    return Emprestimo(
        id=novo_id,
        usuario_id=usuario.id,
        livro_id=livro.id,
        data_emprestimo=data_emprestimo.isoformat(),
        data_prevista_devolucao=data_prevista.isoformat(),
        data_devolucao=None,
        status="ativo",
        multa=0.0
    )


@app.get("/emprestimos", response_model=List[Emprestimo])
def listar_emprestimos(status_: Optional[str] = None):
    with get_conn() as conn:
        query = "SELECT * FROM emprestimos WHERE 1=1"
        params = []
        
        if status_:
            query += " AND status = ?"
            params.append(status_)
        
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
    
    return [
        Emprestimo(
            id=r["id"],
            usuario_id=r["usuario_id"],
            livro_id=r["livro_id"],
            data_emprestimo=r["data_emprestimo"],
            data_prevista_devolucao=r["data_prevista_devolucao"],
            data_devolucao=r["data_devolucao"],
            status=r["status"],
            multa=r["multa"]
        )
        for r in rows
    ]


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
    atraso, valor = calcular_multa(emprestimo.data_prevista_devolucao, data_devolucao.isoformat())

    with get_conn() as conn:
        conn.execute(
            "UPDATE emprestimos SET data_devolucao = ?, status = ?, multa = ? WHERE id = ?",
            (data_devolucao.isoformat(), "devolvido", valor, emprestimo_id)
        )
        conn.execute(
            "UPDATE livros SET quantidade_disponivel = MIN(quantidade_total, quantidade_disponivel + 1) WHERE id = ?",
            (livro.id,)
        )
        
        if atraso > 0:
            multa_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO multas (id, emprestimo_id, usuario_id, livro_id, valor, dias_atraso, data_registro) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (multa_id, emprestimo_id, emprestimo.usuario_id, emprestimo.livro_id, valor, atraso, data_devolucao.isoformat())
            )
        
        conn.commit()

    return Emprestimo(
        id=emprestimo_id,
        usuario_id=emprestimo.usuario_id,
        livro_id=emprestimo.livro_id,
        data_emprestimo=emprestimo.data_emprestimo,
        data_prevista_devolucao=emprestimo.data_prevista_devolucao,
        data_devolucao=data_devolucao.isoformat(),
        status="devolvido",
        multa=valor
    )


@app.put("/emprestimos/{emprestimo_id}/renovar", response_model=Emprestimo)
def renovar_emprestimo(emprestimo_id: str, dados: RenovarEmprestimoEntrada):
    emprestimo = encontrar_emprestimo(emprestimo_id)
    if emprestimo.status == "devolvido":
        raise HTTPException(status_code=409, detail="Não é possível renovar um empréstimo devolvido")

    livro = encontrar_livro(emprestimo.livro_id)
    if any(r for r in reservas_ativas_do_livro(livro.id) if r.usuario_id != emprestimo.usuario_id):
        raise HTTPException(status_code=409, detail="Não é possível renovar: há reserva ativa para este livro")

    nova_data = datetime.fromisoformat(emprestimo.data_prevista_devolucao) + timedelta(days=dados.dias_adicionais)
    
    with get_conn() as conn:
        conn.execute(
            "UPDATE emprestimos SET data_prevista_devolucao = ? WHERE id = ?",
            (nova_data.isoformat(), emprestimo_id)
        )
        conn.commit()
    
    return Emprestimo(
        id=emprestimo_id,
        usuario_id=emprestimo.usuario_id,
        livro_id=emprestimo.livro_id,
        data_emprestimo=emprestimo.data_emprestimo,
        data_prevista_devolucao=nova_data.isoformat(),
        data_devolucao=emprestimo.data_devolucao,
        status=emprestimo.status,
        multa=emprestimo.multa
    )


@app.get("/usuarios/{usuario_id}/emprestimos", response_model=List[Emprestimo])
def emprestimos_do_usuario(usuario_id: str):
    encontrar_usuario(usuario_id)
    with get_conn() as conn:
        cursor = conn.execute("SELECT * FROM emprestimos WHERE usuario_id = ?", (usuario_id,))
        rows = cursor.fetchall()
    
    return [
        Emprestimo(
            id=r["id"],
            usuario_id=r["usuario_id"],
            livro_id=r["livro_id"],
            data_emprestimo=r["data_emprestimo"],
            data_prevista_devolucao=r["data_prevista_devolucao"],
            data_devolucao=r["data_devolucao"],
            status=r["status"],
            multa=r["multa"]
        )
        for r in rows
    ]


@app.get("/livros/{livro_id}/emprestimos", response_model=List[Emprestimo])
def emprestimos_do_livro(livro_id: str):
    encontrar_livro(livro_id)
    with get_conn() as conn:
        cursor = conn.execute("SELECT * FROM emprestimos WHERE livro_id = ?", (livro_id,))
        rows = cursor.fetchall()
    
    return [
        Emprestimo(
            id=r["id"],
            usuario_id=r["usuario_id"],
            livro_id=r["livro_id"],
            data_emprestimo=r["data_emprestimo"],
            data_prevista_devolucao=r["data_prevista_devolucao"],
            data_devolucao=r["data_devolucao"],
            status=r["status"],
            multa=r["multa"]
        )
        for r in rows
    ]



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
    
    with get_conn() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM reservas WHERE usuario_id = ? AND livro_id = ? AND status = 'ativa'",
            (usuario.id, livro.id)
        )
        if cursor.fetchone()["count"] > 0:
            raise HTTPException(status_code=409, detail="Usuário já possui reserva ativa para este livro")

    novo_id = str(uuid.uuid4())
    
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reservas (id, usuario_id, livro_id, data_reserva, status) VALUES (?, ?, ?, ?, ?)",
            (novo_id, usuario.id, livro.id, agora().isoformat(), "ativa")
        )
        conn.commit()

    return Reserva(
        id=novo_id,
        usuario_id=usuario.id,
        livro_id=livro.id,
        data_reserva=agora().isoformat(),
        status="ativa"
    )


@app.get("/reservas", response_model=List[Reserva])
def listar_reservas(status_: Optional[str] = None):
    with get_conn() as conn:
        query = "SELECT * FROM reservas WHERE 1=1"
        params = []
        
        if status_:
            query += " AND status = ?"
            params.append(status_)
        
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
    
    return [
        Reserva(
            id=r["id"],
            usuario_id=r["usuario_id"],
            livro_id=r["livro_id"],
            data_reserva=r["data_reserva"],
            status=r["status"]
        )
        for r in rows
    ]


@app.get("/reservas/{reserva_id}", response_model=Reserva)
def buscar_reserva(reserva_id: str):
    return encontrar_reserva(reserva_id)


@app.delete("/reservas/{reserva_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_reserva(reserva_id: str):
    reserva = encontrar_reserva(reserva_id)
    if reserva.status != "ativa":
        raise HTTPException(status_code=409, detail="Só é possível cancelar reservas ativas")
    
    with get_conn() as conn:
        conn.execute("UPDATE reservas SET status = 'cancelada' WHERE id = ?", (reserva_id,))
        conn.commit()


@app.get("/usuarios/{usuario_id}/reservas", response_model=List[Reserva])
def reservas_do_usuario(usuario_id: str):
    encontrar_usuario(usuario_id)
    with get_conn() as conn:
        cursor = conn.execute("SELECT * FROM reservas WHERE usuario_id = ?", (usuario_id,))
        rows = cursor.fetchall()
    
    return [
        Reserva(
            id=r["id"],
            usuario_id=r["usuario_id"],
            livro_id=r["livro_id"],
            data_reserva=r["data_reserva"],
            status=r["status"]
        )
        for r in rows
    ]


@app.get("/livros/{livro_id}/reservas", response_model=List[Reserva])
def reservas_do_livro(livro_id: str):
    encontrar_livro(livro_id)
    with get_conn() as conn:
        cursor = conn.execute("SELECT * FROM reservas WHERE livro_id = ?", (livro_id,))
        rows = cursor.fetchall()
    
    return [
        Reserva(
            id=r["id"],
            usuario_id=r["usuario_id"],
            livro_id=r["livro_id"],
            data_reserva=r["data_reserva"],
            status=r["status"]
        )
        for r in rows
    ]


@app.get("/multas", response_model=List[Multa])
def listar_multas():
    with get_conn() as conn:
        cursor = conn.execute("SELECT * FROM multas")
        rows = cursor.fetchall()
    
    return [
        Multa(
            id=r["id"],
            emprestimo_id=r["emprestimo_id"],
            usuario_id=r["usuario_id"],
            livro_id=r["livro_id"],
            valor=r["valor"],
            dias_atraso=r["dias_atraso"],
            data_registro=r["data_registro"]
        )
        for r in rows
    ]


@app.get("/usuarios/{usuario_id}/multas", response_model=List[Multa])
def multas_do_usuario(usuario_id: str):
    encontrar_usuario(usuario_id)
    with get_conn() as conn:
        cursor = conn.execute("SELECT * FROM multas WHERE usuario_id = ?", (usuario_id,))
        rows = cursor.fetchall()
    
    return [
        Multa(
            id=r["id"],
            emprestimo_id=r["emprestimo_id"],
            usuario_id=r["usuario_id"],
            livro_id=r["livro_id"],
            valor=r["valor"],
            dias_atraso=r["dias_atraso"],
            data_registro=r["data_registro"]
        )
        for r in rows
    ]


@app.get("/notificacoes/atrasos")
def listar_atrasos():
    hoje = agora()
    atrasos = []
    
    with get_conn() as conn:
        cursor = conn.execute("SELECT * FROM emprestimos WHERE status = 'ativo'")
        for row in cursor.fetchall():
            prazo = datetime.fromisoformat(row["data_prevista_devolucao"])
            if hoje > prazo:
                dias = max(0, (hoje.date() - prazo.date()).days)
                atrasos.append(
                    {
                        "emprestimo_id": row["id"],
                        "usuario_id": row["usuario_id"],
                        "livro_id": row["livro_id"],
                        "dias_atraso": dias,
                        "multa_estimativa": round(dias * VALOR_MULTA_POR_DIA, 2),
                    }
                )
    
    return {"quantidade": len(atrasos), "atrasos": atrasos}
