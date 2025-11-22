from langchain_community.document_loaders import PyPDFLoader
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.graph.message import add_messages
from typing import TypedDict, Sequence, Literal, Annotated, List, Dict
from langchain_core.tools import tool, BaseTool
from langchain_core.messages import BaseMessage, ToolMessage
from dotenv import load_dotenv
import os
import logging
import re
from sqlmodel import SQLModel, Session, select
from memoria import Memory, engine
from langgraph.graph.state import CompiledStateGraph
from pydantic import ValidationError
from langchain_google_genai import ChatGoogleGenerativeAI
from rich import print
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

logging.basicConfig(
    filename="AIDoctor.log",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)                                                           

# CRIANDO UMA VARIAVEL GLOBAL, ONDE TODOS OS EXAMES MEDICOS ESTÃO

FILE_FOLDER = os.getenv("EXAMS_FOLDER", "C:\\Users\\55319\\Documents\\exames")

#DEFININDO O ESTADO DO AGENT

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


@tool
def check_patient(patient_name: str):
    """ Função que verifica o banco de daods"""
    try:
        with Session(engine) as session:
            statements = select(Memory).where(Memory.patient_name == patient_name)
            results = session.exec(statements).all()

            if not results:
                return "Nenhum paciente encontrado com esse nome"

            response = "Paciente(s), encontrado(s): \n"
            for p in results:
                response += f" - Nome:{p.patient_name}, Idade:{p.age}, Tel:{p.telephone}"

            return response
    except Exception as e:
        return f"Erro ao consultar banco de dados: {str(e)}"


@tool
def create_patient(patient_name: str, age: int, telephone: int) -> str:
    """ Função que salva paciente no banco de dados para consulta"""
    try:
        with Session(engine) as session:
            patient = Memory(
                patient_name=patient_name,
                age=age,
                telephone=telephone
            )
            session.add(patient)
            session.commit()
            session.refresh(patient)
            logging.info(f"Paciente '{patient_name}' cadastrado com sucesso")
            return f"Paciente '{patient_name}' cadastrado com sucesso no banco de dados."
    except Exception as e:
        error_msg = f"Erro ao cadastrar paciente: {str(e)}"
        logging.error(error_msg)
        return error_msg

def virtual_assistant(state: AgentState) -> AgentState:
    """ Chamando a assistente"""
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key = "(SUA CHAVE API AQUI)"
    )
    SYSTEM_MESSAGE = SystemMessage(
    content="""Você é a Clara, Recepcionista.
    FLUXO:
    1. Cadastro: Use 'check_patient' e 'create_patient'.
    2. Médico: Se o usuário quiser falar com médico ou ver exames, NUNCA responda com texto. 
       USE IMEDIATAMENTE a ferramenta 'transfer_to_physician'.
    """)
    
    TOOL: List[BaseTool] = [create_patient, check_patient, transfer_to_physician]
    llm_with_tool = llm.bind_tools(TOOL)
    llm_messages = [SYSTEM_MESSAGE] + list(state["messages"])
    llm_result = llm_with_tool.invoke(llm_messages)
    return {
        "messages": [llm_result]
    }


@tool
def load_exams(path: str = FILE_FOLDER) -> str:
    """Carrega e extrai o conteúdo de arquivos PDF de exames médicos.
    
    Esta função busca todos os arquivos PDF em um diretório especificado,
    extrai o texto de cada arquivo e retorna uma string formatada contendo
    todo o conteúdo dos exames separados por um delimitador.
    
    Args:
        path: Caminho do diretório contendo os arquivos PDF de exames médicos.
            Por padrão, usa a variável global FILE_FOLDER.
            
    Returns:
        String formatada contendo:
        - Mensagem de sucesso com o número de exames encontrados
        - Conteúdo completo de todos os exames separados por delimitador
        - Mensagem de erro caso nenhum arquivo seja encontrado ou ocorra exceção
        
    Raises:
        FileNotFoundError: Quando o diretório especificado não existe.
        Exception: Quando ocorre erro ao extrair conteúdo dos PDFs.
        
    Example:
        >>> result = load_exams("C:\\Users\\55319\\Documents\\exames")
        >>> print(result)
        "Exames carregador com sucesso: total de '3' encontrados, conteudo..."
    """

    try:
        exams_file = [os.path.join(path, f) for f in os.listdir(path) if f.endswith(".pdf")]
        exams = [] # lista para armazenar os exames extraidos

        if not exams_file:
            return f" Nenhum arquivo encontado na pasta: {path}"

        for file in exams_file:
            load = PyPDFLoader(file)
            docs = load.load()

            text_exams = "\n".join(p.page_content for p in docs)
            exams.append(text_exams)

        # Definindo um separador entre os exames

        separador = "\n--- NOVO CURRÍCULO ---\n"
        text = separador.join(exams) 

        return f"Exames carregador com sucesso: total de '{len(exams)}' encontrados, conteudo a ser analisado '{text}'"


    except FileNotFoundError:
        print("Erro ao carregar exames")
    except Exception as e:
        return f" Erro ao estrair conteudo de {exams}"

@tool
def transfer_to_physician():
    """
    Use esta ferramenta APENAS quando o usuário quiser:
    - Falar com o médico.
    - Analisar exames.
    - Tirar dúvidas de saúde.
    Não precisa de argumentos.
    """
    return "Solicitação de transferência para o médico recebida."

#Chamada da LLM
def physician_analyst(state: AgentState) -> AgentState:
    "Chamamando o modelo da llm"
    print(">call_llm")
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1, # Temperatura baixa para ser preciso nos números
        google_api_key = "(SUA CHAVE API AQUI)" 
    )
    SYSTEM_PROMPT = SystemMessage(
        content="""Seu nome é josé
Você é um médico especialista, com amplo conhecimento em todas as áreas da medicina, 
incluindo clínica geral, cardiologia, nefrologia, hematologia, endocrinologia, bioquímica 
e interpretação laboratorial.

Sua função é analisar exames médicos enviados pelo paciente, explicando de forma clara, 
detalhada e compreensível.

Sempre que necessário, você deve extrair os dados dos exames utilizando a ferramenta 
'load_exams'. Após obter as informações, faça uma análise completa que contenha:
- Interpretação dos valores encontrados;
- Comparação com valores de referência (sem inventar valores, só use se o exame fornecer);
- Possíveis significados clínicos dos achados;
- Alertas quando houver risco potencial;
- Orientação geral baseada no exame (sem diagnóstico definitivo nem prescrição).

O tom da comunicação deve ser empático, profissional e educativo. 
Nunca faça diagnósticos fechados, não prescreva medicamentos e sempre lembre o paciente 
da importância de consultar um médico presencial para confirmação.

IMPORTANTE: Responda apenas com o conteúdo solicitado, sem adicionar disclaimers, assinaturas, avisos ou informações sobre o modelo."""
    )
    TOOL: List[BaseTool] = [load_exams, ]
    llm_with_tools = llm.bind_tools(TOOL)
    messages_to_llm = [SYSTEM_PROMPT] + list(state["messages"])
    llm_result = llm_with_tools.invoke(messages_to_llm)

    return {
        "messages": [llm_result]
    }


def tool_node(state: AgentState) -> AgentState:
    print("> tool_node")
    last_message = state["messages"][-1]

    tool_map = {
        "load_exams": load_exams,
        "create_patient": create_patient,
        "check_patient": check_patient,
        "transfer_to_physician": transfer_to_physician
    }

    outputs = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        if tool_name in tool_map:
            print(f" Execultando: {tool_name}")
            try:
                res = tool_map[tool_name].invoke(tool_call["args"])
            except Exception as e:
                res = f"Erro:{e}"
        else:
            res = "Ferramenta não encontrada"

        outputs.append(ToolMessage(content=str(res), tool_call_id=tool_call["id"], name=tool_name))
    return {
        "messages": outputs
    }

def router(state: AgentState) -> Literal["tool_node", "physician_analyst",  "END", "transfer_to_physician" , "virtual_assistant", "transfer_to_physician"]:
    print(">router")
    last_message= state["messages"][-1]
    print(f"\n🔍 DEBUG ROUTER:")
    print(f"Conteúdo: {last_message.content}")
    print(f"Tool Calls: {getattr(last_message, 'tool_calls', 'Nenhuma')}")

    if getattr(last_message, "tool_calls", None):
        tool_name = last_message.tool_calls[0]["name"]
        if tool_name == "transfer_to_physician":
            return "physician_analyst"
        return "tool_node"

        #Palavra chave de encaminhamento
    if "ENCAMINHAR_MEDICO" in str(last_message.content):
        return "physician_analyst"
    return "END"


builder = StateGraph(AgentState)

builder.add_node("virtual_assistant", virtual_assistant)
builder.add_node("physician_analyst", physician_analyst)
builder.add_node("tool_node", tool_node)

builder.set_entry_point("virtual_assistant")

#Eges da recepcionista
builder.add_conditional_edges(
    "virtual_assistant",
    router,
    {
        "tool_node": "tool_node",
        "physician_analyst": "physician_analyst",
        "END": END
    }
)

#EDGE DO MEDICO
builder.add_conditional_edges(
    "physician_analyst",
    router,
    {
        "tool_node": "tool_node",
        "physician_analyst": "physician_analyst",
        "END": END,
        "virtual_assistant": "virtual_assistant"
    }
)
builder.add_edge("tool_node", "virtual_assistant")
memory = MemorySaver()

graph = builder.compile(checkpointer=memory)
graph.get_graph().draw_mermaid_png(output_file_path="ark.png")

thread_id = "paciente_01"
config = {"configurable": {"thread_id": thread_id}}
# --- LOOP ---
print("--- SISTEMA INICIADO ---")
while True:
    user_input = input("👤 Você: ")
    if user_input.lower() in ["sair"]: break
    
    # O stream permite ver o processo passo a passo
    for event in graph.stream(
        {"messages": [HumanMessage(content=user_input)]},
        config=config
    ):
        for key, value in event.items():
            if "messages" in value:
                msg = value["messages"][-1]
                if isinstance(msg, AIMessage) and msg.content:
                    print(f"AI {key}: {msg.content}")



