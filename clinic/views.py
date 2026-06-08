from __future__ import annotations

import json
from dataclasses import asdict

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from AIDoctor import ask_agent, get_exams_folder, is_api_configured
from patient_store import create_patient_record, list_recent_patients


@ensure_csrf_cookie
@require_GET
def index(request: HttpRequest):
    return render(request, "clinic/index.html")


@require_GET
def status(request: HttpRequest) -> JsonResponse:
    return JsonResponse(_build_status())


@require_POST
def chat(request: HttpRequest) -> JsonResponse:
    try:
        payload = _read_json(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    message = str(payload.get("message", "")).strip()
    thread_id = str(payload.get("thread_id", "paciente_web")).strip() or "paciente_web"

    if not message:
        return JsonResponse({"error": "Mensagem vazia."}, status=400)

    try:
        return JsonResponse({"messages": ask_agent(message, thread_id=thread_id)})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@require_POST
def patients(request: HttpRequest) -> JsonResponse:
    try:
        payload = _read_json(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        patient = create_patient_record(
            patient_name=str(payload.get("patient_name", "")),
            age=int(payload.get("age", 0)),
            telephone=str(payload.get("telephone", "")),
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"patient": asdict(patient)}, status=201)


@require_POST
def exams(request: HttpRequest) -> JsonResponse:
    uploaded_files = request.FILES.getlist("exam")
    if not uploaded_files:
        return JsonResponse({"error": "Nenhum PDF foi enviado."}, status=400)

    folder = get_exams_folder()
    folder.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, str]] = []

    for uploaded_file in uploaded_files:
        original_name = uploaded_file.name.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        if not original_name.lower().endswith(".pdf"):
            return JsonResponse({"error": "Somente arquivos PDF sao aceitos."}, status=400)

        target = _unique_path(folder / original_name)
        with target.open("wb") as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        saved.append({"name": target.name, "path": str(target)})

    return JsonResponse({"saved": saved}, status=201)


def _build_status() -> dict:
    folder = get_exams_folder()
    folder.mkdir(parents=True, exist_ok=True)
    exams = [
        {"name": file.name, "size": file.stat().st_size}
        for file in sorted(folder.glob("*.pdf"))
    ]
    return {
        "api_configured": is_api_configured(),
        "exams_folder": str(folder),
        "exams": exams,
        "patients": [asdict(patient) for patient in list_recent_patients()],
    }


def _read_json(request: HttpRequest) -> dict:
    if not request.body:
        return {}

    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("JSON invalido.")


def _unique_path(path):
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2
    while True:
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1
