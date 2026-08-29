import os
from functools import lru_cache

from supabase import Client, create_client

from core.models import Loadsheet
from services.calculation_service import CalculationResult


@lru_cache
def _client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def list_loadsheets(flight_id: str) -> list[Loadsheet]:
    """Histórico de versões de um voo, mais recente primeiro."""
    client = _client()
    rows = (
        client.table("loadsheets")
        .select("*")
        .eq("flight_id", flight_id)
        .order("version", desc=True)
        .execute()
        .data
    )
    return [Loadsheet(**row) for row in rows]


def create_loadsheet(
    flight_id: str,
    result: CalculationResult,
    raw_payload: dict,
    signed_by: str,
    document_type: str = "FINAL",
) -> Loadsheet:
    """Insere uma nova versão de loadsheet (nunca UPDATE — a tabela é
    append-only, reforçado por trigger na base de dados).

    NOTA: ler a última versão e inserir a seguinte não é atómico (não há
    aqui uma transação serializável) — em teoria duas assinaturas em
    paralelo para o mesmo voo podiam calcular o mesmo `next_version`. A
    constraint UNIQUE(flight_id, version) impede duas versões duplicadas
    de coexistirem (a segunda falha), mas não resolve o conflito de forma
    graciosa. Aceitável para um único operador por voo (o caso de uso
    atual); passaria a ser um problema real com signing concorrente.
    """
    client = _client()
    existing = (
        client.table("loadsheets")
        .select("version, id")
        .eq("flight_id", flight_id)
        .order("version", desc=True)
        .limit(1)
        .execute()
        .data
    )
    next_version = (existing[0]["version"] + 1) if existing else 1
    supersedes_id = existing[0]["id"] if existing else None

    row = (
        client.table("loadsheets")
        .insert(
            {
                "flight_id": flight_id,
                "version": next_version,
                "supersedes_id": supersedes_id,
                "document_type": document_type,
                "zfw": result.zfw,
                "tow": result.tow,
                "law": result.ldw,
                "zfw_cg": result.cg_zfw,
                "zfw_mac": result.mac_zfw,
                "tow_cg": result.tow_cg,
                "tow_mac": result.tow_mac,
                "total_index": result.lizfw,
                "raw_payload": raw_payload,
                "signed_by": signed_by,
            }
        )
        .execute()
        .data[0]
    )
    return Loadsheet(**row)
