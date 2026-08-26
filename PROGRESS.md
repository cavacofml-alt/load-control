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

## 2026-08-27 (cont.) — Parser AHM 560/565 e dados reais (em curso)

- **Documento de referência recebido**: `THY-AHM565_A330-300_Rev10_12Sep2023.pdf` (Turkish Airlines, A330-300, ~112 páginas) — schema semipermanente real: fórmula de Índice/MAC, limites de CG, holds/ULDs, fuel tables, DOW/DOI por registration, pesos limite por frota.
- **Correção de nomenclatura**: o parser estava a ser chamado `ahm560.py` mas o documento de referência é o **AHM 565** (Semi-Permanent Data, formato estruturado), não o AHM 560 (mensagem telex). Arquitetura clarificada: são dois adapters diferentes, não um erro de digitação —
  - `parsers/ahm560_parser.py` — adapter para telex AHM 560 (**esqueleto só**, `NotImplementedError`, estrutura de campos ainda por definir)
  - `parsers/ahm565_parser.py` — adapter para o documento estruturado AHM 565 (contém a lógica/dados reais)
  - ambos devem convergir no mesmo modelo interno, `AircraftProfile`.
- **`core/models.py`**: adicionado `CabinZone`, `CargoHold`, e `AircraftProfile` (fonte de verdade interna, agnóstica do formato de origem — `envelope: AircraftEnvelope` + `cabin_zones` + `cargo_holds`). Os parsers ainda devolvem só `AircraftEnvelope`; `AircraftProfile` fica pronto para quando os parsers extraírem zonas/holds reais.
- **Dados reais injetados** (`ahm565_parser.py`): substituído o A320 fictício pelo perfil real do **TC-JNH** (A330-300, frota TK 333A) — `mzfw=175000`, `mtow=233000`, `mlaw=187000`, `dow=125187`, `doi=89.2`, `reference_station=36.35`, `lemac=34.532`, `mac_length=7.27`, `k_constant=100`, `c_constant=2500` (Secções C4/E5/F1 do manual).
- **Testes validados contra dado publicado real** (não inventado): a Secção C, Sheet 5 do manual publica, para ZFW=175000kg, o limite forward de %MAC=19.3 (Index=70.83). O `BalanceCalculator` com os dados reais do TC-JNH reproduz 19.27% — a ±0.03pp do publicado, dentro da tolerância que o próprio manual assume (±0.3 de índice por arredondamento do DCS). **Primeira validação do motor contra a fonte real**, não só contra os próprios testes.

### A minha opinião no momento

- A fórmula do `%MAC`/`CG` que já tínhamos implementado (antes de ver este documento) bate certo estruturalmente com a fórmula oficial do AHM 565 (Secção C, Sheet 4) — não foi preciso mudar a matemática, só as constantes. Isso é um bom sinal de que a base está correta.
- `AircraftProfile` existe mas ainda não é usado por nenhum parser real (ambos devolvem só `AircraftEnvelope`) — é preparação para quando o parsing de zonas/holds (Secção D) for implementado, não uma peça funcional ainda.
- O `ahm560_parser.py` é um esqueleto vazio de propósito — não há nenhuma amostra real de mensagem telex AHM 560 ainda para desenhar o parsing; implementar isso agora seria adivinhar a estrutura.

## 2026-08-27 (cont.) — Fase 3: Hold Management, deadload no motor de cálculo

- **`ahm565_parser.py`**: adicionado `parse_cargo_holds()` — devolve os 5 porões reais do TC-JNH/frota 333A-B (Sheet D2, Lower Deck): CPT1 (FWD, 10206kg, arm 17.125), CPT2 (FWD, 20412kg, arm 24.575), CPT3 (AFT, 9522kg, arm 44.650), CPT4 (AFT, 10206kg, arm 49.600), CPT5 (BULK, 3468kg, arm 54.267).
- **`BalanceCalculator.calculate_lizfw(loads, cargo_holds)`**: novo método — soma ao DOI a contribuição de índice de cada porão carregado, usando `index_per_weight_unit = (balance_arm - reference_station) / C`. Esta fórmula foi validada diretamente contra os valores "Index per wt unit" publicados no manual (CPT1: -0.00769, CPT5: +0.00717 — batem exatos).
- **Teste** (`test_deadload_lizfw_and_maczfw`): simula 2000kg em CPT1 + 1000kg em CPT5, recalcula LIZFW e %MACZFW, e confirma que o resultado bate com uma segunda implementação independente da mesma fórmula oficial (não só com o próprio código).
- `CargoHold` (Pydantic) já suportava este mapeamento sem alterações — não mudei o schema.

### A minha opinião no momento

- Não mudei `CargoHold.hold_type` para distinguir FWD/AFT/BULK — o schema atual só tem `LOWER`/`MAIN` (nível de deck), e os 5 porões são todos `LOWER`. A distinção FWD/AFT/BULK importa na prática (bulk não aceita ULD, só carga solta) mas é informação de posição/secção, não de tipo de deck — fica para quando desenharmos o Hold Management UI (Fase 3 seguinte), não para o motor matemático.
- `calculate_lizfw` recebe `cargo_holds` como parâmetro em vez de vir do `self.aircraft` — mantém o `BalanceCalculator` construído só com `AircraftEnvelope` (sem quebrar os testes já existentes) e falta decidir se, a prazo, o calculator deve passar a aceitar `AircraftProfile` completo em vez de `AircraftEnvelope` + holds soltos.
- MACZFW ainda não tem um método próprio — reutilizei `calculate_cg` + `calculate_mac_percentage` diretamente. Não criei `calculate_maczfw` porque seria só uma composição de duas chamadas já existentes.

## Próximos passos possíveis (não decididos)

- [ ] Parsing real de secções do AHM 565 (C: index/MAC/CG limits; D: holds/cabin; E: DOW/DOI por registration) em vez de dados hardcoded
- [ ] Endpoint de ingestão (`POST /api/v1/aircraft/ahm565`) para validar `AircraftProfile`/`AircraftEnvelope` via API antes de gravar no Supabase
- [ ] Estrutura real de mensagem telex para `ahm560_parser.py` (falta uma amostra real)
- [ ] Decidir se `BalanceCalculator` passa a trabalhar sobre `AircraftProfile` (envelope + holds) em vez de `AircraftEnvelope` sozinho
- [ ] Validação de `max_weight` por porão ao aplicar deadload (`calculate_lizfw` ainda não rejeita sobrecarga de um CPT)
- [ ] EZFW/TOW/LAW acumulados a partir de PNL/ADL
- [ ] Testes unitários adicionais (casos-limite: pesos negativos, índice extremo)
- [ ] Fluxo de onboarding/convite para atribuir `airline_id` a novos `profiles`
- [ ] `MessageGateway` (adapter) para ACARS/SITA/Tipo B
- [ ] Tabela de regras DGR versionada por `dgr_edition`
- [ ] Abstração do solver de Auto-Load (heurística MVP → OR-Tools/PuLP/SciPy)
