from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal


TipoUsuario = Literal["aluno", "professor", "funcionario"]


class UsuarioEntrada(BaseModel):
    nome: str
    matricula: str
    tipo: TipoUsuario
    email: str
    senha: str


class Usuario(UsuarioEntrada):
    model_config = ConfigDict(from_attributes=True)

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
    model_config = ConfigDict(from_attributes=True)

    id: str
    quantidade_disponivel: int
    ativo: bool = True


class EmprestimoEntrada(BaseModel):
    usuario_id: str
    livro_id: str


class Emprestimo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    model_config = ConfigDict(from_attributes=True)

    id: str
    usuario_id: str
    livro_id: str
    data_reserva: str
    status: Literal["ativa", "cancelada", "atendida"] = "ativa"


class Multa(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    emprestimo_id: str
    usuario_id: str
    livro_id: str
    valor: float
    dias_atraso: int
    data_registro: str
