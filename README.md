# Sistema Biblioteca-Escolar

Sistema desenvolvido para a disciplina de Projeto e Desenvolvimento de Software.

## Tecnologias

* Python
* FastAPI
* SQLAlchemy (ORM)
* SQLite
* API REST

## Metodologia

O projeto foi desenvolvido utilizando a metodologia Scrum, com organização das atividades, divisão de tarefas e acompanhamento das entregas durante o desenvolvimento.

## Segurança da API

A aplicação utiliza autenticação por API Key para proteger os endpoints da API.

A chave de acesso não é armazenada diretamente no sistema. Para aumentar a segurança, a aplicação utiliza um hash SHA-256 da chave, armazenado nas variáveis de ambiente, permitindo validar as requisições sem expor o valor original.

As rotas protegidas exigem o envio da chave através do header:

```http
X-API-Key: chave_de_acesso
```

As rotas públicas, como a página inicial (`/`) e autenticação (`/login`), não necessitam de API Key.

## Arquitetura e Padrões de Projeto

Durante o desenvolvimento foram aplicados padrões de projeto para melhorar a organização e a manutenção do código.

### Singleton

O padrão Singleton foi utilizado na classe `DatabaseConfig`, garantindo uma única configuração compartilhada para acesso ao banco de dados durante toda a execução da aplicação.

### Factory

O padrão Factory foi aplicado por meio da função `get_conn()`, responsável por criar conexões com o banco de dados já configuradas, centralizando a configuração e evitando repetição de código.

## Mapeamento Objeto-Relacional (ORM)

A aplicação utiliza o SQLAlchemy como ORM (Object-Relational Mapping), substituindo o acesso direto ao banco de dados por meio de comandos SQL.

Com o ORM, as tabelas do banco são representadas por classes Python, facilitando a manipulação dos dados, reduzindo a quantidade de código SQL e tornando a aplicação mais organizada e de fácil manutenção.

As principais vantagens da utilização do ORM no projeto são:

- Mapeamento das entidades do sistema para classes Python;
- Operações de persistência utilizando objetos em vez de comandos SQL;
- Maior organização e legibilidade do código;
- Facilidade de manutenção e evolução da aplicação;
- Integração com o banco de dados por meio de sessões (`Session`) do SQLAlchemy.

## Equipe

* Francisco Luan de Sousa Ferreira
* Samuel Lucas dos Santos Oliveira

## Como executar

1. Clone o repositório.
2. Crie um ambiente virtual.

```bash
python -m venv .venv
```

3. Ative o ambiente virtual.

4. Instale as dependências.

```bash
pip install -r requirements.txt
```

5. Configure o arquivo `.env`.

6. Execute a aplicação.

```bash
uvicorn main:app --reload
```
