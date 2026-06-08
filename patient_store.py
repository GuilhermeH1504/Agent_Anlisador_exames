from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PROJECT_DIR / "aidoctor.db"


@dataclass(frozen=True)
class Patient:
    id: int
    patient_name: str
    age: int
    telephone: str
    created_at: str


def get_db_path() -> Path:
    db_path = Path(os.getenv("AIDOCTOR_DB_PATH", str(DEFAULT_DB_PATH))).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(get_db_path())
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT NOT NULL,
                age INTEGER NOT NULL,
                telephone TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def create_patient_record(patient_name: str, age: int, telephone: str) -> Patient:
    clean_name = patient_name.strip()
    clean_phone = str(telephone).strip()

    if not clean_name:
        raise ValueError("Nome do paciente e obrigatorio.")
    if int(age) <= 0:
        raise ValueError("Idade deve ser maior que zero.")
    if not clean_phone:
        raise ValueError("Telefone e obrigatorio.")

    init_db()
    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO patients (patient_name, age, telephone)
            VALUES (?, ?, ?)
            """,
            (clean_name, int(age), clean_phone),
        )
        patient_id = int(cursor.lastrowid)
        row = connection.execute(
            """
            SELECT id, patient_name, age, telephone, created_at
            FROM patients
            WHERE id = ?
            """,
            (patient_id,),
        ).fetchone()
    return _row_to_patient(row)


def find_patients(patient_name: str) -> list[Patient]:
    query = patient_name.strip()
    if not query:
        return []

    init_db()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, patient_name, age, telephone, created_at
            FROM patients
            WHERE patient_name LIKE ?
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (f"%{query}%",),
        ).fetchall()
    return [_row_to_patient(row) for row in rows]


def list_recent_patients(limit: int = 8) -> list[Patient]:
    init_db()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, patient_name, age, telephone, created_at
            FROM patients
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_patient(row) for row in rows]


def _row_to_patient(row: sqlite3.Row) -> Patient:
    return Patient(
        id=int(row["id"]),
        patient_name=str(row["patient_name"]),
        age=int(row["age"]),
        telephone=str(row["telephone"]),
        created_at=str(row["created_at"]),
    )
