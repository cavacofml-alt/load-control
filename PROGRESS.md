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

## 2026-08-27

- **Revisão crítica de arquitetura** (DCS/W&B): identificados 5 riscos que a stack proposta não cobria — auditoria imutável de loadsheets, ACARS/SITA como contrato externo (não código), RLS sem contexto de utilizador, solver do Auto-Load em Python puro, e regras DGR não versionadas por edição anual. Registo aceite; prioridade definida para o modelo de dados primeiro.
- **Base de dados — `users/roles`, `flights`, `loadsheets`** (`supabase/migrations/20260826010000_users_flights_loadsheets.sql`, aplicada via `supabase db push`):
  - `profiles` — 1:1 com `auth.users`, guarda `airline_id` + `role` (admin/dispatcher/load_controller/viewer).
  - `public.current_airline_id()` — função `SECURITY DEFINER` usada pelas RLS policies para evitar recursão ao consultar `profiles`.
  - `flights` — voo por `airline_id`/`aircraft_id`, `flight_number`, rota, `std`, `status`.
  - `loadsheets` — **ledger append-only**: `version` + `supersedes_id`, `document_type` (FINAL/LMC), snapshot dos resultados do `BalanceCalculator` + `raw_payload` JSONB, `signed_by`/`signed_at`. Um trigger (`prevent_loadsheet_mutation`) bloqueia `UPDATE`/`DELETE` ao nível da base de dados — não é só convenção da aplicação, uma correção é sempre um novo `INSERT`.
  - RLS policies reais aplicadas a todas as tabelas (`airlines`, `aircraft`, `cabin_zones`, `cargo_holds`, `flights`, `loadsheets`, `profiles`), isoladas por `airline_id` via `current_airline_id()`.
- Confirmado via REST: as 7 tabelas existem no schema `public`.

### A minha opinião no momento

- O trigger de imutabilidade em `loadsheets` é mais forte do que o pedido original (que falava em `supersedes_id` como convenção) — decidi impor isto ao nível do Postgres porque disciplina de aplicação sozinha não sobrevive a bugs nem a alguém a correr uma query manual no dashboard. Se algum dia for preciso mesmo apagar uma linha (ex.: erro de teste em produção), é preciso `DROP TRIGGER` manualmente — de propósito, para não ser trivial.
- `profiles.airline_id` é opcional (`REFERENCES airlines(id)`, sem `NOT NULL`) porque o fluxo de convite/onboarding ainda não existe — um utilizador pode ter conta sem airline atribuída ainda. Isto tem de ser fechado antes de haver sign-up público.
- Ainda não criei a tabela de regras DGR nem o `MessageGateway` — ficou combinado que a prioridade agora era só o modelo de dados de users/flights/loadsheets.

## Próximos passos possíveis (não decididos)

- [ ] Parser AHM 560 real (regex sobre secções AH/AL)
- [ ] EZFW/TOW/LAW acumulados a partir de PNL/ADL
- [ ] Testes unitários adicionais (casos-limite: pesos negativos, índice extremo)
- [ ] Fluxo de onboarding/convite para atribuir `airline_id` a novos `profiles`
- [ ] `MessageGateway` (adapter) para ACARS/SITA/Tipo B
- [ ] Tabela de regras DGR versionada por `dgr_edition`
- [ ] Abstração do solver de Auto-Load (heurística MVP → OR-Tools/PuLP/SciPy)
