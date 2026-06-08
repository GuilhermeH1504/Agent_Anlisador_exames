# AIDoctor

AIDoctor e um prototipo de atendimento para clinica com uma interface web em Django.

O fluxo tem dois agentes:

- Clara: atendente virtual que acolhe, cadastra/localiza pacientes e encaminha assuntos clinicos.
- Dr. Jose: medico assistente que analisa exames em PDF e responde com orientacao educativa.

## Funcionalidades

- Interface web local com Django.
- Cadastro local de pacientes em SQLite.
- Upload e leitura de exames em PDF.
- Conversa com a IA usando LangGraph.
- Encaminhamento da atendente para o medico.
- Modo terminal preservado em `AIDoctor.py`.

## Estrutura

```text
.
|-- manage.py
|-- aidoctor_site/      # Configuracao Django
|-- clinic/             # App web da clinica
|-- AIDoctor.py         # Motor do agente e modo terminal
|-- patient_store.py    # Banco SQLite de pacientes usado pelo agente
|-- requirements.txt
|-- exames/             # PDFs enviados pela interface
`-- README.md
```

## Instalacao

```bash
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha sua chave:

```env
GOOGLE_API_KEY=SUA_CHAVE_AQUI
EXAMS_FOLDER=exames
AIDOCTOR_MODEL=gemini-2.5-flash
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_SECRET_KEY=troque-essa-chave-em-producao
```

Tambem e aceito `GEMINI_API_KEY` no lugar de `GOOGLE_API_KEY`.

## Rodar Interface Django

```bash
python manage.py runserver 127.0.0.1:8000
```

Abra no navegador:

```text
http://127.0.0.1:8000
```

## Rodar no Terminal

```bash
python AIDoctor.py
```

Para sair:

```text
sair
exit
quit
```

## Proximas Melhorias

- Login para atendente e medico.
- Historico de atendimentos por paciente.
- Dashboard de exames pendentes.
- Admin Django para gerenciar registros.
- Separacao entre ambiente local e producao.

Este projeto nao substitui consulta medica presencial. O agente medico deve ser usado apenas como apoio educativo e triagem inicial.
