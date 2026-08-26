# Progresso — AWBS (load-control)

Registo do que foi feito, decisão a decisão. Atualizado a cada trabalho relevante.

## 2026-08-26

- **Infraestrutura**: scaffold inicial — `/frontend` (Next.js 15, TypeScript, Tailwind, App Router), `/backend` (venv Python, FastAPI + uvicorn + supabase + pydantic, `main.py` com `/health`).
- **Base de dados**: schema inicial aplicado ao Supabase via `supabase db push` (ligado por CLI com personal access token) — tabelas `airlines`, `aircraft`, `cabin_zones`, `cargo_holds`, todas com RLS ativo e sem policies (fail-closed por omissão; falta tabela `flights` e as policies reais).
- **Motor de cálculo (`backend/core`)**:
  - `models.py` — `AircraftEnvelope` (Pydantic): limites estruturais (MZFW/MTOW/MLAW), DOW/DOI, constantes de MAC (LEMAC, mac_length, k/c), e `reference_station` (datum).
  - `calculator.py` — `BalanceCalculator`: `calculate_cg`, `calculate_mac_percentage`, `check_weight_limits`.
  - `parsers/ahm560.py` — parser mock (retorna A320 fixo; TODO: regex real sobre secções AH/AL do AHM 560).
- **Testes**: `backend/tests/test_calculator.py` (pytest) — CG/`%MAC` e limites estruturais. Passam ambos.
  - Nota: a primeira versão do teste de CG usava dados não fisicamente consistentes (índice/constantes produziam CG atrás do LEMAC, `%MAC` negativo); corrigido o `total_index` do teste, não a fórmula — a fórmula estava correta.
- **Repo**: pushed para `github.com/cavacofml-alt/load-control` (branch `main`).

### A minha opinião no momento

- A fundação está sólida para um MVP, mas o parser AHM 560 continua mockado — antes de avançar para Hold Management (Fase 3) vale a pena validar o parser real contra pelo menos 2-3 aeronaves diferentes, para não construir UI em cima de dados fictícios.
- Falta a tabela `flights` e as RLS policies reais — sem elas, ninguém (exceto `service_role`) consegue ler/escrever nas tabelas atuais. Não é urgente enquanto estamos só a testar o motor matemático localmente, mas bloqueia qualquer integração com o frontend/Supabase Auth.
- Os valores de `k_constant`/`c_constant` do mock (`1000.0`/`50.0`) estão trocados relativamente à convenção usada nos testes (`50.0`/`1000.0`) — não corrigi porque não sei qual é a convenção real da aeronave; vale a pena confirmar antes de ligar o parser real.

## Próximos passos possíveis (não decididos)

- [ ] Parser AHM 560 real (regex sobre secções AH/AL)
- [ ] Tabela `flights` + RLS policies reais
- [ ] EZFW/TOW/LAW acumulados a partir de PNL/ADL
- [ ] Testes unitários adicionais (casos-limite: pesos negativos, índice extremo)
