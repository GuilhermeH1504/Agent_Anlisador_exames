Este projeto implementa um agente médico especializado, utilizando LangChain, LangGraph e o modelo GPT-OSS-120B (Groq) para:

Ler PDFs de exames médicos;

Extrair e unificar o conteúdo dos arquivos;

Analisar e interpretar exames conforme um System Prompt altamente especializado;

Seguir fluxo estruturado com uso de ferramentas (tools) e raciocínio controlado;

Interagir com o usuário de forma contínua em linha de comando.

🧠 Funcionalidades Principais

🩺 Agente médico inteligente com instruções detalhadas para interpretação correta de exames.

📄 Carregamento automático de PDFs de exames via ferramenta load_exams.

🔗 Integração com LangGraph para fluxo de execução baseado em estados e ferramentas.

⚙️ Chamadas ao modelo ChatGroq (GPT-OSS-120B).

🔍 Separador automático entre exames para facilitar a leitura do conteúdo.

📝 Log automático das interações em arquivo AIDoctor.log.

💬 Sistema interativo CLI, onde o usuário envia perguntas e o agente responde.

📂 Estrutura do Projeto
AI-Doctor/
│── main.py                  # Código principal com agente, ferramentas e loop interativo
│── AIDoctor.log             # Arquivo de logs
│── exames/                  # Pasta contendo arquivos PDF de exames
│── .env                     # Chaves e variáveis de ambiente
│── README.md                # Este arquivo

🔧 Dependências

Certifique-se de instalar:

pip install langchain langchain-core langchain-community
pip install langgraph
pip install langchain-groq
pip install python-dotenv
pip install pypdf

📌 Configuração

Crie um arquivo .env:

GROQ_API_KEY=SUAS_CHAVE_AQUI


Certifique-se de alterar o caminho da pasta dos exames, caso necessário:

FILE_FOLDER = "C:\\Users\\55319\\Documents\\exames"

🧰 Ferramenta: load_exams

A função:

Vasculha a pasta por arquivos .pdf;

Extrai todo o texto com PyPDFLoader;

Junta com separadores personalizados;

Retorna o texto completo para análise pelo LLM.

Exemplo de retorno:

Exames carregados com sucesso: total de '3' encontrados.
--- NOVO CURRÍCULO ---
[conteúdo do exame 1]
--- NOVO CURRÍCULO ---
[conteúdo do exame 2]
...

🧩 Arquitetura com LangGraph

O fluxo contém:

📌 Nós:

call_llm — Envia mensagens ao modelo Groq.

tool_node — Executa ferramentas chamadas pela IA.

📌 Rotas:

Se o modelo pedir ferramenta → vai para tool_node

Caso contrário → encerra (END)

Fluxo:

User → call_llm → (usa ferramenta?) → tool_node → call_llm → ... → END

🩺 System Prompt Médico

O prompt define um agente médico especialista com:

Interpretação de exames

Comparação com referências (somente se o exame fornecer)

Linguagem empática e profissional

Sem diagnósticos fechados

Sem prescrição de medicamentos

O agente também é instruído a usar obrigatoriamente a ferramenta load_exams quando necessário.

🖥️ Como Executar

Execute o script:

python main.py


Interaja com o agente:

👤Você: Pode analisar meus exames?
🤖 AI: Claro! Vou carregar e interpretar seus exames...


Para sair:

quit
sair
exit

🧪 Exemplo de Uso
👤Você: Meus exames já estão na pasta, pode carregar?
🤖 AI: Exames carregados com sucesso: total de '2' encontrados...
