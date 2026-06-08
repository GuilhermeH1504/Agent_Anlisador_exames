from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Sequence, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool, tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from patient_store import create_patient_record, find_patients, init_db


load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_EXAMS_FOLDER = PROJECT_DIR / "exames"
DEFAULT_THREAD_ID = "paciente_01"
DEFAULT_MODEL = "gemini-2.5-flash"

logging.basicConfig(
    filename=str(PROJECT_DIR / "AIDoctor.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


RECEPTION_PROMPT = SystemMessage(
    content=(
        "Voce e a Clara, atendente virtual de uma clinica.\n"
        "Seu papel e acolher o paciente, localizar ou cadastrar dados basicos "
        "e encaminhar para o medico quando o assunto exigir avaliacao clinica.\n\n"
        "Fluxo:\n"
        "1. Para consultar paciente, use check_patient.\n"
        "2. Para cadastrar paciente, use create_patient.\n"
        "3. Se o usuario quiser falar com medico, analisar exames ou tirar duvidas "
        "de saude, use imediatamente transfer_to_physician. Nao responda como medico.\n"
        "4. Seja breve, educada e profissional."
    )
)

PHYSICIAN_PROMPT = SystemMessage(
    content=(
        "Seu nome e Dr. Jose. Voce e um medico assistente especializado em "
        "interpretacao inicial de exames e orientacao clinica educativa.\n\n"
        "Quando precisar ler PDFs de exames, use a ferramenta load_exams. Depois "
        "analise o conteudo encontrado com clareza, incluindo:\n"
        "- valores identificados no exame;\n"
        "- comparacao com referencias apenas quando o proprio exame trouxer referencias;\n"
        "- possiveis significados clinicos;\n"
        "- sinais de alerta quando houver risco potencial;\n"
        "- orientacao geral sem diagnostico definitivo e sem prescrever medicamentos.\n\n"
        "Mantenha tom empatico, profissional e educativo. Sempre deixe claro que "
        "a avaliacao presencial com um profissional de saude e necessaria para "
        "confirmacao e conduta."
    )
)

NODE_LABELS = {
    "virtual_assistant": "Clara",
    "physician_analyst": "Dr. Jose",
    "reception_tools": "Sistema",
    "physician_tools": "Sistema",
    "handoff_tools": "Sistema",
}


def get_exams_folder() -> Path:
    folder = os.getenv("EXAMS_FOLDER")
    if folder:
        return Path(folder).expanduser()
    return DEFAULT_EXAMS_FOLDER


def is_api_configured() -> bool:
    return bool(_get_google_api_key())


def _get_google_api_key() -> str | None:
    return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")


def _build_llm(*, temperature: float = 0.2) -> ChatGoogleGenerativeAI:
    api_key = _get_google_api_key()
    if not api_key:
        raise RuntimeError(
            "Configure GOOGLE_API_KEY ou GEMINI_API_KEY no arquivo .env antes "
            "de conversar com a IA."
        )

    return ChatGoogleGenerativeAI(
        model=os.getenv("AIDOCTOR_MODEL", DEFAULT_MODEL),
        temperature=temperature,
        google_api_key=api_key,
    )


@tool
def check_patient(patient_name: str) -> str:
    """Consulta pacientes cadastrados pelo nome."""
    try:
        patients = find_patients(patient_name)
        if not patients:
            return "Nenhum paciente encontrado com esse nome."

        lines = ["Paciente(s) encontrado(s):"]
        for patient in patients:
            lines.append(
                f"- Nome: {patient.patient_name}, Idade: {patient.age}, "
                f"Telefone: {patient.telephone}"
            )
        return "\n".join(lines)
    except Exception as exc:
        logging.exception("Erro ao consultar paciente")
        return f"Erro ao consultar banco de dados: {exc}"


@tool
def create_patient(patient_name: str, age: int, telephone: str) -> str:
    """Cadastra um novo paciente com nome, idade e telefone."""
    try:
        patient = create_patient_record(
            patient_name=patient_name,
            age=age,
            telephone=telephone,
        )
        logging.info("Paciente '%s' cadastrado com sucesso", patient.patient_name)
        return f"Paciente '{patient.patient_name}' cadastrado com sucesso."
    except Exception as exc:
        logging.exception("Erro ao cadastrar paciente")
        return f"Erro ao cadastrar paciente: {exc}"


@tool
def transfer_to_physician() -> str:
    """Encaminha a conversa para o medico quando houver assunto clinico."""
    return "Solicitacao de transferencia para o medico recebida."


@tool
def load_exams(path: str = "") -> str:
    """Carrega PDFs de exames medicos de uma pasta e extrai o texto."""
    folder = Path(path).expanduser() if path else get_exams_folder()

    if not folder.exists():
        return f"Pasta de exames nao encontrada: {folder}"
    if not folder.is_dir():
        return f"O caminho informado nao e uma pasta: {folder}"

    pdf_files = sorted(folder.glob("*.pdf"))
    if not pdf_files:
        return f"Nenhum arquivo PDF encontrado na pasta: {folder}"

    exams: list[str] = []
    errors: list[str] = []
    for pdf_file in pdf_files:
        try:
            exams.append(_extract_pdf_text(pdf_file))
        except Exception as exc:
            logging.exception("Erro ao extrair exame %s", pdf_file)
            errors.append(f"{pdf_file.name}: {exc}")

    if not exams:
        return "Nao foi possivel extrair texto dos exames. " + " | ".join(errors)

    separator = "\n\n--- NOVO EXAME ---\n\n"
    content = separator.join(exams)
    result = (
        f"Exames carregados com sucesso: total de {len(exams)} encontrado(s).\n"
        f"{content}"
    )
    if errors:
        result += "\n\nArquivos com erro:\n" + "\n".join(errors)
    return result


def _extract_pdf_text(pdf_file: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Instale a dependencia pypdf: pip install pypdf") from exc

    reader = PdfReader(str(pdf_file))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(page.strip() for page in pages if page.strip())
    if not text:
        return f"Arquivo: {pdf_file.name}\n[PDF sem texto extraivel]"
    return f"Arquivo: {pdf_file.name}\n{text}"


def virtual_assistant(state: AgentState) -> AgentState:
    llm = _build_llm(temperature=0.3)
    tools: list[BaseTool] = [create_patient, check_patient, transfer_to_physician]
    result = llm.bind_tools(tools).invoke([RECEPTION_PROMPT] + list(state["messages"]))
    return {"messages": [result]}


def physician_analyst(state: AgentState) -> AgentState:
    llm = _build_llm(temperature=0.1)
    tools: list[BaseTool] = [load_exams]
    result = llm.bind_tools(tools).invoke([PHYSICIAN_PROMPT] + list(state["messages"]))
    return {"messages": [result]}


def _execute_tools(state: AgentState, tool_map: dict[str, BaseTool]) -> AgentState:
    last_message = state["messages"][-1]
    outputs: list[ToolMessage] = []

    for tool_call in getattr(last_message, "tool_calls", []):
        tool_name = tool_call["name"]
        tool_to_run = tool_map.get(tool_name)

        if not tool_to_run:
            result = f"Ferramenta nao encontrada: {tool_name}"
        else:
            try:
                logging.info("Executando ferramenta %s", tool_name)
                result = tool_to_run.invoke(tool_call.get("args", {}))
            except Exception as exc:
                logging.exception("Erro ao executar ferramenta %s", tool_name)
                result = f"Erro ao executar {tool_name}: {exc}"

        outputs.append(
            ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
                name=tool_name,
            )
        )

    return {"messages": outputs}


def reception_tools(state: AgentState) -> AgentState:
    return _execute_tools(
        state,
        {
            "create_patient": create_patient,
            "check_patient": check_patient,
        },
    )


def handoff_tools(state: AgentState) -> AgentState:
    return _execute_tools(state, {"transfer_to_physician": transfer_to_physician})


def physician_tools(state: AgentState) -> AgentState:
    return _execute_tools(state, {"load_exams": load_exams})


def route_reception(
    state: AgentState,
) -> Literal["reception_tools", "handoff_tools", "END"]:
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None)
    if not tool_calls:
        return "END"

    if tool_calls[0]["name"] == "transfer_to_physician":
        return "handoff_tools"
    return "reception_tools"


def route_physician(state: AgentState) -> Literal["physician_tools", "END"]:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "physician_tools"
    return "END"


@lru_cache(maxsize=1)
def get_graph():
    init_db()

    builder = StateGraph(AgentState)
    builder.add_node("virtual_assistant", virtual_assistant)
    builder.add_node("physician_analyst", physician_analyst)
    builder.add_node("reception_tools", reception_tools)
    builder.add_node("handoff_tools", handoff_tools)
    builder.add_node("physician_tools", physician_tools)

    builder.set_entry_point("virtual_assistant")
    builder.add_conditional_edges(
        "virtual_assistant",
        route_reception,
        {
            "reception_tools": "reception_tools",
            "handoff_tools": "handoff_tools",
            "END": END,
        },
    )
    builder.add_edge("reception_tools", "virtual_assistant")
    builder.add_edge("handoff_tools", "physician_analyst")
    builder.add_conditional_edges(
        "physician_analyst",
        route_physician,
        {
            "physician_tools": "physician_tools",
            "END": END,
        },
    )
    builder.add_edge("physician_tools", "physician_analyst")

    return builder.compile(checkpointer=MemorySaver())


def ask_agent(user_input: str, thread_id: str = DEFAULT_THREAD_ID) -> list[dict[str, str]]:
    config = {"configurable": {"thread_id": thread_id}}
    responses: list[dict[str, str]] = []

    for event in get_graph().stream(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
    ):
        for node_name, value in event.items():
            messages = value.get("messages", [])
            if not messages:
                continue

            message = messages[-1]
            if isinstance(message, AIMessage) and message.content:
                responses.append(
                    {
                        "agent": NODE_LABELS.get(node_name, node_name),
                        "content": str(message.content),
                    }
                )

    if responses:
        return responses

    return [
        {
            "agent": "AIDoctor",
            "content": "A IA processou a mensagem, mas nao retornou conteudo em texto.",
        }
    ]


def run_cli() -> None:
    print("--- SISTEMA INICIADO ---")
    print("Digite 'sair', 'exit' ou 'quit' para encerrar.")

    while True:
        user_input = input("Voce: ").strip()
        if user_input.lower() in {"sair", "exit", "quit"}:
            break
        if not user_input:
            continue

        try:
            for response in ask_agent(user_input):
                print(f"{response['agent']}: {response['content']}")
        except Exception as exc:
            print(f"Erro: {exc}")


if __name__ == "__main__":
    run_cli()
