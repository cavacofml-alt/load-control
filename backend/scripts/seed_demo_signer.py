"""Cria a identidade de demonstração usada para `signed_by` nas loadsheets
enquanto não existe autenticação real (ver PROGRESS.md).

Cria um `auth.users` real via a Admin API (só assim `profiles.id`, que é FK
para `auth.users(id)`, pode ser preenchido sem violar a constraint) e o
`profiles` correspondente, ligado à airline TK já semeada por `seed_tcjnh.py`.

É idempotente: se o utilizador demo já existir (procurado por email), reusa-o
em vez de tentar recriar.

Requer SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY.
Imprime o UUID do profile no fim — usar como valor de DEMO_SIGNER_PROFILE_ID
(local .env e variáveis de ambiente do Railway).

Uso: python -m scripts.seed_demo_signer
"""
import os
import sys

import truststore

truststore.inject_into_ssl()

from supabase import create_client  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEMO_EMAIL = "demo-signer@load-control.local"
DEMO_PASSWORD = os.environ.get("DEMO_SIGNER_PASSWORD") or os.urandom(24).hex()


def main() -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    client = create_client(url, key)

    existing = client.auth.admin.list_users()
    user = next((u for u in existing if u.email == DEMO_EMAIL), None)

    if user is None:
        result = client.auth.admin.create_user(
            {
                "email": DEMO_EMAIL,
                "password": DEMO_PASSWORD,
                "email_confirm": True,
                "user_metadata": {"is_demo_signer": True},
            }
        )
        user = result.user
        print(f"auth.users criado: {user.id}")
    else:
        print(f"auth.users já existia: {user.id}")

    airline = client.table("airlines").select("id").eq("iata_code", "TK").limit(1).execute().data
    if not airline:
        raise RuntimeError("Airline 'TK' não encontrada — corre primeiro python -m scripts.seed_tcjnh")
    airline_id = airline[0]["id"]

    profile = client.table("profiles").upsert(
        {
            "id": user.id,
            "airline_id": airline_id,
            "role": "load_controller",
            "full_name": "Demo Signer (sem autenticação real)",
        },
        on_conflict="id",
    ).execute().data[0]

    print(f"profiles upserted: {profile['id']}")
    print()
    print(f"DEMO_SIGNER_PROFILE_ID={profile['id']}")


if __name__ == "__main__":
    main()
