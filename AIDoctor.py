from re import S
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.graph.message import add_messages
from typing import Any, TypedDict, Sequence, Literal, Annotated, List
from langchain_core.tools import tool, BaseTool
from langchain_core.messages import BaseMessage, ToolMessage
from dotenv import load_dotenv
import os
from langchain_groq import ChatGroq
import logging

from langgraph.graph.state import CompiledStateGraph
from pydantic import ValidationError

load_dotenv()

logging.basicConfig(
    filename="AIDoctor.log",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)                                                           

# CRIANDO UMA VARIAVEL GLOBAL, ONDE TODOS OS EXAMES MEDICOS ESTÃO

FILE_FOLDER = "C:\\Users\\55319\\Documents\\exames"

#DEFININDO O ESTADO DO AGENT

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

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


#Chamada da LLM

def call_llm(state: AgentState) -> AgentState:
    "Chamamando o modelo da llm"
    print(">call_llm")
    llm = ChatGroq(
        model = "openai/gpt-oss-120b",
        groq_api_key = '(SUA CHAVE AQPI AQUI)'
    )
    SYSTEM_PROMPT = SystemMessage(
    "Você é um médico especialista, com amplo conhecimento em todas as áreas da medicina, "
    "incluindo clínica geral, cardiologia, nefrologia, hematologia, endocrinologia, bioquímica "
    "e interpretação laboratorial."
    
    "Sua função é analisar exames médicos enviados pelo paciente, explicando de forma clara, "
    "detalhada e compreensível."
    
    "Sempre que necessário, você deve extrair os dados dos exames utilizando a ferramenta "
    "'load_exams /C:\\Users\\55319\\Documents\\exames'. Após obter as informações, faça uma análise completa que contenha:"
    "\n- Interpretação dos valores encontrados;"
    "\n- Comparação com valores de referência (sem inventar valores, só use se o exame fornecer);"
    "\n- Possíveis significados clínicos dos achados;"
    "\n- Alertas quando houver risco potencial;"
    "\n- Orientação geral baseada no exame (sem diagnóstico definitivo nem prescrição)."
    
    "O tom da comunicação deve ser empático, profissional e educativo. "
    "Nunca faça diagnósticos fechados, não prescreva medicamentos e sempre lembre o paciente "
    "da importância de consultar um médico presencial para confirmação."
    
    )
    TOOL: List[BaseTool] = [load_exams]
    llm_with_tools = llm.bind_tools(TOOL)
    messages_to_llm = [SYSTEM_PROMPT] + list(state["messages"])
    llm_result = llm_with_tools.invoke(messages_to_llm)

    return {
        "messages": [llm_result]
    }

def tool_node(state: AgentState) -> AgentState:
    print("> tool_node")
    llm_response = state["messages"][-1]
    # Se não houver tool_calls, retorna o state sem alterações
    if isinstance(llm_response, AIMessage) and getattr(
        llm_response, "tool_calls", None
    ):
        return state

    tool_map = {
        "load_exams": load_exams
    }


    tool_messages = []
    for call in llm_response.tool_calls:
        name, args, id = call['name'], call["args"], call["id"]

        try:

            if name in tool_map:
                content=tool_map[name].invoke(args)
                status =  'success'
            
            else:
                content= f"Ferramenta {name}, não encontrada"
                status = "error"

        except (KeyError, IndexError, TypeError, ValidationError, ValueError) as error:
            content = f"Please fiz your mistakes: {error}"
            status = "error"

        tool = ToolMessage(content=str(content), tool_call_id=id, status=status)
        tool_messages.append(tool)
    return {
        "messages": tool_messages
    }

def router(state: AgentState) -> Literal["tool_node", "END"]:
    print(">router")
    llm_response = state["messages"][-1]

    if getattr(llm_response, "tool_calls", None):
        return "tool_node"
    return "END"

builder = StateGraph(AgentState)

builder.add_node("call_llm", call_llm)
builder.add_node("tool_node", tool_node)

builder.set_entry_point("call_llm")
builder.add_conditional_edges(
    "call_llm",
    router,
    {
       "tool_node": "tool_node",
        "END": END 
    }
)
builder.add_edge("tool_node", "call_llm")

graph = builder.compile()

call_llm
while True:
    user_input = input("👤Você: ")
    if user_input.lower() in ["quit", "sair", "exit"]:
        break

    initial_state = {
        "messages": [HumanMessage(content=user_input)]
    }
    result = graph.invoke(initial_state)
    print("-" * 20)

    final_answer = result["messages"][-1].content
    print(f"🤖 AI: {final_answer}")




