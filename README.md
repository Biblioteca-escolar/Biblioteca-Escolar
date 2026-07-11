# Sistema Biblioteca-Escolar

Sistema desenvolvido para a disciplina de Projeto e Desenvolvimento de Software.

## Tecnologias

* Python
* FastAPI
* Banco de dados
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
## Equipe

* Francisco Luan de Sousa Ferreira
* Samuel Lucas dos Santos Oliveira
