import os

import truststore

# Usa o certificate store do próprio SO em vez do bundle do certifi — neste
# ambiente há interceção TLS (proxy/antivírus) que o certifi não reconhece.
# Tem de correr antes de qualquer cliente HTTPS ser construído (ex.: Supabase).
truststore.inject_into_ssl()

from dotenv import load_dotenv  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.routes import aircraft, load_control  # noqa: E402

load_dotenv()

app = FastAPI(title="AWBS Backend", version="0.1.0")

# CORSMiddleware não aceita wildcards em allow_origins (ex.: "https://*.vercel.app"
# não funciona ali — só origens exatas). Para cobrir qualquer preview/branch
# deployment em *.vercel.app, usa-se allow_origin_regex.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://load-control.vercel.app"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(aircraft.router)
app.include_router(load_control.router)


@app.get("/health")
def health():
    return {"status": "ok"}
