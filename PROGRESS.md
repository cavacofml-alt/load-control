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

## 2026-08-27 (cont.) — Fase 4: Gestão de Passageiros, ZFW end-to-end

- **`ahm565_parser.py`**: adicionado `parse_cabin_zones()` — devolve as 3 zonas reais do TC-JNH na configuração 28C/261Y (Sheet D5, Main deck): `0A` (28 lugares, arm 18.820), `0B` (138 lugares, arm 33.387), `0C` (123 lugares, arm 48.865).
- **`BalanceCalculator`**: adicionados `calculate_pax_weight(pax_loads)` e `calculate_pax_influence(pax_loads, cabin_zones)`. Usam os pesos standard IATA (`STANDARD_PAX_WEIGHTS`: Adult 84, Male 88, Female 70, Child 35, Infant 10 kg, Sheet B3) por tipo de passageiro, ou o peso real diretamente se for fornecido em vez de uma contagem.
- **`calculate_lizfw`** generalizado: passa a aceitar `pax_loads`/`cabin_zones` opcionais e soma a contribuição de passageiros à de carga — mantém-se retrocompatível (chamadas antigas com só carga continuam a funcionar, os novos parâmetros são opcionais).
- **Teste end-to-end** (`test_zfw_end_to_end_with_cargo_and_passengers`): 2000kg no CPT1 + 20/100/100 adultos em 0A/0B/0C → ZFW=145667kg (dentro do MZFW=175000), LIZFW=94.13456, %MACZFW≈23.62%. Validado com uma segunda implementação independente da mesma fórmula.
- `CabinZone` (Pydantic) já suportava este mapeamento sem alterações — não mudei o schema.

### A minha opinião no momento

- A instrução original dizia "o momento gerado é o Peso × Centroid da Zona" — **isto estava incorreto** e teria dado índices errados por uma ordem de grandeza. Confirmei contra os valores "Index per Weight Unit" publicados no manual (0A: -0.00701, 0B: -0.00119, 0C: +0.00501) que a fórmula certa subtrai a `reference_station` antes de dividir por C — a mesma que já usávamos para os porões. Implementei a versão correta.
- Os códigos de zona no pedido vinham como "OA/OB/OC" (letra O); o documento real usa "0A/0B/0C" (zero). Usei a grafia do documento.
- `_resolve_pax_weight` aceita tanto uma contagem por tipo (`{"ADULT": 20}`, usa pesos standard) como um peso já conhecido em kg — para quando o peso real dos passageiros de uma zona for capturado (ex.: PNL/ADL com pesos declarados), sem forçar sempre o standard.

## 2026-08-27 (cont.) — Fase 3 (correção): posições de ULD e overlap na baia 11

- **`core/models.py`**: novo `UldPosition` (`position_code`, `max_weight`, `balance_arm`, `mutually_exclusive_with`). `CargoHold` ganhou `uld_positions: list[UldPosition]`.
- **`ahm565_parser.py`**: `CPT1` passa a incluir as 4 posições reais da baia 11 (Sheet D3, Hold FORWARD): `11L`/`11R` (laterais, AKE/PKC, 1587kg, arm 15.432), `11` (central, PLA, 3174kg, arm 15.432), `11P` (central, PAG/PMC, 5103kg, arm 15.885).
- **`validate_hold_overlap(hold_loads, uld_positions)`** (`core/calculator.py`): lança `ValueError` se duas posições carregadas em simultâneo forem mutuamente exclusivas. Peso 0 numa posição não conta como "ocupada".
- **Testes** (`tests/test_uld_overlap.py`, 8 casos): confirma que 11L+11R coexistem, mas 11L/11R bloqueiam 11 e 11P, e 11/11P se bloqueiam mutuamente. Suite completa: 12/12 testes a passar.

### A minha opinião no momento

- **Limitação conhecida, registada de propósito**: o limite de `11P` (5103kg) usa o valor do PMC, mas um PAG real nessa posição tem limite de só 4626kg. O schema atual não distingue o limite por tipo de ULD efetivamente carregado — só há um `max_weight` fixo por posição. Isto permite, hoje, que o sistema aceite até 5103kg num PAG quando o limite real seria 4626kg. Não é um bug de lógica, é uma limitação de modelo que só é resolvida quando soubermos que *tipo* de ULD está fisicamente em cada posição (ligado à Secção G, ULD Compatibility, que ainda não foi modelada).
- `validate_hold_overlap` é uma função solta, não um método do `BalanceCalculator` — não precisa de `self.aircraft`, e mantém-se testável isoladamente do resto do motor.
- Só a baia 11 (CPT1) tem posições reais mapeadas; CPT2-CPT5 continuam só com o `max_weight`/`balance_arm` agregado do porão, sem posições internas.

## 2026-08-27 (cont.) — Fase 3 completa: mapa integral do Lower Deck (CPT1-CPT4)

- **`ahm565_parser.py`**: generalizado `_build_bay_positions(bay_number, centroid_lr, centroid_p)` — gera automaticamente L/R/central/P de qualquer baia com as exclusões mútuas corretas (laterais independentes entre si, central e P bloqueiam tudo). `parse_cargo_holds()` agora popula **58 posições de ULD reais** em CPT1-CPT4, a partir das tabelas `FORWARD_HOLD_BAYS` (baias 11-26) e `AFT_HOLD_BAYS` (baias 31-43), Sheet D3/D3.1 do manual.
- **Testes** (`tests/test_uld_full_deck.py`, 7 casos): confirma o total de 58 posições, exclusões dinâmicas em baias de porões diferentes (24 em CPT2, 42 em CPT4), baias sem posição P (13, 25, 26, 34, 43), e que baias de porões diferentes não interferem entre si. Suite completa: **19/19 testes a passar**.
- **Correção de dados face ao pedido**: excluí `31P` do mapa do TC-JNH. O manual (Sheet D3, remarks) diz que essa posição está ocupada pelo *Lower Deck Crew Rest Container* (LDCRC) na frota 333A/333B — o registration group do TC-JNH. A frota 333D (nota equivalente no manual) não tem essa restrição. Tratar 31P como carregável para o TC-JNH seria um erro real, não cosmético.

### A minha opinião no momento

- Não critiquei a instrução original de "os pesos são consistentes em quase todo o lado (1587/3174/5103)" — confirmei isso é verdade para todas as 16 baias mapeadas, por isso a generalização com 3 constantes fixas (`LATERAL_MAX_WEIGHT`, `CENTRAL_MAX_WEIGHT`, `PALLET_MAX_WEIGHT`) é válida sem exceções neste deck.
- A limitação já registada (limite de posições `P` usar o valor do PMC, não o do PAG) agora aplica-se a **6 posições diferentes** (11P, 12P, 21P, 22P, 23P, 24P, 32P, 33P, 41P, 42P — todas as baias com P), não só à 11P. Continua por resolver, mas o impacto está mais visível agora que o mapa é completo.
- Não liguei ainda `validate_hold_overlap` ao `calculate_lizfw` — continuam a ser dois mecanismos independentes. Isto já estava registado abaixo e mantém-se válido para todo o deck, não só para a baia 11.

## 2026-08-27 (cont.) — Compatibilidade ULD↔tipo e Gatekeeper de validação

- **`UldPosition.max_weight` (float) substituído por `allowed_ulds: dict[str, float]`** (tipo de ULD -> peso máximo específico). Aplicado às **58 posições** de todas as 16 baias (não só à baia 11) — os pesos por tipo (AKE/PKC=1587, PLA=3174, PAG=4626, PMC=5103) são globais no manual (Sheet B5, ULD Specifications), não variam por posição, por isso a generalização cobre o deck todo sem exceções.
- **`validate_uld_compatibility(hold_loads, uld_positions)`** (`core/calculator.py`): lança `ValueError` se o tipo de ULD não está na lista de tipos permitidos da posição, ou se o peso excede o limite específico desse tipo.
- **`LoadService`** (`core/load_service.py`) — gatekeeper novo: `calculate_validated_lizfw(hold_loads, cargo_holds, ...)` corre `validate_hold_overlap` e `validate_uld_compatibility` antes de agregar os pesos por porão e chamar `BalanceCalculator.calculate_lizfw`. Se qualquer validação falhar, o cálculo nem chega a correr.
- **Testes** (`tests/test_uld_compatibility.py`, 6 casos): confirma que um PAG de 4800kg em `11P` é rejeitado (limite real 4626kg) mas um PMC com o mesmo peso é aceite (limite 5103kg); que um PMC não cabe numa posição lateral (só aceita AKE/PKC); e que o `LoadService` bloqueia tanto por overlap como por incompatibilidade antes de calcular o LIZFW. Suite completa: **25/25 testes a passar**.
- Resolvida a limitação registada nas duas entradas anteriores: o limite de peso das posições `P` já não usa um valor único (PMC) para os dois tipos que aceita — cada tipo tem o seu próprio limite real.

### A minha opinião no momento

- **A limitação passada para a frente**: `LoadService.calculate_validated_lizfw` continua a agregar o peso por porão (`CargoHold.balance_arm`) para chamar o `calculate_lizfw` existente, não pelo `balance_arm` exato de cada posição de ULD. Isto significa que o LIZFW calculado é uma aproximação (usa o centroide médio do porão, ex. CPT2=24.575) mesmo sabendo agora a posição exata (ex. 24P=28.203, bem mais atrás). Reutilizei o método já testado em vez de inventar um novo cálculo por posição — mas isto é uma imprecisão real que vale a pena resolver antes de qualquer loadsheet real sair do sistema.
- `LoadService` fica num ficheiro novo (`core/load_service.py`) — é uma camada de orquestração/validação, não matemática pura, por isso separei do `calculator.py`.
- Não toquei no `check_weight_limits` nem no `max_weight` agregado do `CargoHold` (nível do porão) — esse continua um limite único, só as posições de ULD individuais passaram a ser por tipo.

## 2026-08-27 (cont.) — Correção de precisão: LIZFW por posição de ULD, não por porão

- **`BalanceCalculator.calculate_lizfw_from_positions(position_loads, cargo_holds, ...)`**: novo método — usa o `balance_arm` exato de cada `UldPosition` carregada, em vez do centroide agregado do `CargoHold`. `calculate_lizfw` (nível de porão) mantém-se inalterado e retrocompatível, para quando só se sabe o total por porão, não a posição exata.
- **`LoadService`** atualizado para chamar `calculate_lizfw_from_positions` — já não agrega por porão (`_aggregate_by_hold` removido, deixou de ser necessário).
- **Impacto real confirmado por teste**: carregar 4800kg de PMC em `11P` (arm real 15.885) dá LIZFW=**49.9072**; a mesma carga calculada com a média do porão CPT1 (arm 17.125) dava LIZFW=**52.288** — uma diferença de **2.38 pontos de índice**, nada desprezível. `test_load_service_uses_position_arm_not_hold_average` confirma que os dois valores são mesmo diferentes.
- Suite completa: **26/26 testes a passar**.

### A minha opinião no momento

- Esta era a limitação mais importante das últimas três entregas — resolvida antes de avançar para mais funcionalidade, como devia ser (uma loadsheet real com este erro seria um problema de segurança, não só de precisão).
- `calculate_lizfw` (nível de porão) não foi removido, só deixou de ser o caminho usado pelo `LoadService`. Mantém-se útil para cenários em que só se conhece o peso total de um porão, sem saber a posição exata (ex.: planeamento preliminar antes de decidir onde cada ULD vai fisicamente).

## 2026-08-27 (cont.) — CPT5/Bulk: última peça do Lower Deck

- **`ahm565_parser.py`**: `CPT5` (Bulk hold) passa a ter as suas 3 posições reais (Sheet D2, Bulk Holds): `CPT51` (339kg, arm 52.755), `CPT52` (1413kg, arm 53.285), `CPT53` (1716kg, arm 55.330). Usam um tipo sintético `"BULK"` em `allowed_ulds` — bulk é carga solta, não ULD contentorizado, por isso não faz sentido usar AKE/PKC/PLA/PAG/PMC aqui.
- **Testes** (`tests/test_uld_full_deck.py`, +4 casos): confirma que as 3 posições do Bulk não têm exclusão mútua entre si (são compartimentos separados, podem carregar-se todos ao mesmo tempo), que rejeitam qualquer tipo de ULD contentorizado, e que respeitam o limite de peso próprio (ex.: 400kg em CPT51 é rejeitado, limite real 339kg). Total do Lower Deck: **61 posições** (58 ULD + 3 Bulk). Suite completa: **30/30 testes a passar**.
- O pedido original ("mapear baias 12,13,21-26,31-34,41-43") já estava feito nos dois commits anteriores (`7c7e051`, `6f2c0c4`) — o CPT5/Bulk era a única lacuna real.

### A minha opinião no momento

- `"BULK"` como chave de `allowed_ulds` é uma simplificação deliberada — não existe um "tipo de ULD" chamado BULK no manual, é só a forma mais simples de reutilizar o mesmo mecanismo de validação (`validate_uld_compatibility`) para um conceito diferente (carga solta com limite de peso, sem tipo de contentor). Se a distinção entre bulk e ULD vier a importar de forma mais rica (ex.: DG que só pode ir em bulk, ou vice-versa), vale a pena revisitar isto com um campo próprio em vez de um tipo sintético.
- O Lower Deck do A330-300 está agora completo e testado ponta-a-ponta: overlap, compatibilidade de tipo/peso, e cálculo de índice por posição exata (incluindo bulk). A Fase 3 do roadmap está, na prática, fechada.

## 2026-08-27 (cont.) — Supabase ligado (schema + seed) e API FastAPI

- **Correção de schema Supabase**: `aircraft.reference_station` estava em falta desde sempre (existia no Pydantic, nunca migrado); adicionada via `ALTER TABLE`. Nova tabela `uld_positions` (posição, `balance_arm`, `allowed_ulds` JSONB, `mutually_exclusive_with` TEXT[]), com RLS por `airline_id` via join a `cargo_holds`/`aircraft`.
- **Bug de infraestrutura mais antigo, encontrado e corrigido**: a `service_role` (e `anon`/`authenticated`) nunca tiveram `GRANT` nas tabelas — só RLS policies. Isto existia desde a primeira migração e nunca tinha sido detetado porque só se testava introspecção de schema, nunca uma leitura real de dados. Corrigido com `GRANT`s explícitos + `ALTER DEFAULT PRIVILEGES` para tabelas futuras herdarem automaticamente.
- **`scripts/seed_tcjnh.py`**: semeia o TC-JNH real no Supabase (airline, aircraft, 3 cabin_zones, 5 cargo_holds, **61 uld_positions**) usando o `AHM565Parser` como única fonte — nada transcrito manualmente para SQL. Requereu adicionar `truststore` (interceção TLS local impedia o `certifi` do Python de validar o certificado, apesar do `curl` funcionar sem problemas).
- **API FastAPI** (`api/routes/aircraft.py`, `api/routes/load_control.py`, ligados no `main.py`):
  - `POST /api/v1/aircraft/profile` — valida um payload contra `AircraftProfile`/`AircraftEnvelope`; só valida, não grava (isso é o `scripts/seed_tcjnh.py`, já existente).
  - `POST /api/v1/load-control/calculate` — recebe `pax_loads` + `hold_loads` (com `uld_type`), corre o `LoadService` (overlap + compatibilidade) e devolve `zfw`/`lizfw`/`mac_zfw`; devolve HTTP 422 com o motivo se alguma validação falhar. Usa o TC-JNH mockado do parser por agora, não lê do Supabase ainda.
- **Bug apanhado antes de correr os testes**: `validate_hold_overlap`/`validate_uld_compatibility` faziam `positions_by_code[code]` sem verificar existência — uma posição desconhecida (ex.: `"99Z"`) rebentava com `KeyError` não tratado (HTTP 500), não o 422 esperado. Corrigido para lançar `ValueError` explícito.
- **Testes** (`tests/test_api.py`, 8 casos, via `TestClient`): payload vazio devolve ZFW=DOW; carga+passageiros válidos devolvem 200; ULD incompatível, overlap, e posição desconhecida devolvem 422; endpoint de perfil aceita payload válido e rejeita incompleto. Suite completa: **38/38 testes a passar**, todos à primeira depois da correção do KeyError.

### A minha opinião no momento

- O bug de `GRANT` em falta era mais grave do que qualquer coisa que já tínhamos registado como limitação — sem ele, **nenhuma** leitura/escrita real via REST teria funcionado, nem com a `service_role`. Só não apareceu antes porque nunca se tinha testado uma query real contra dados, só introspecção de schema.
- `/calculate` ainda não lê do Supabase — usa sempre o TC-JNH mockado, exatamente como pedido ("por agora"). Isto significa que o endpoint e o seed já feito ainda não estão ligados um ao outro; é o próximo passo óbvio se quisermos o endpoint a servir dados reais em vez do mock.
- Não liguei `check_weight_limits` (tow/law) a nada real no `/calculate` — uso o mesmo `zfw` para os três parâmetros (`zfw`, `tow`, `law`) porque não há ainda conceito de combustível/trip fuel no payload. É uma simplificação válida só para ZFW, não para um cálculo de TOW/LAW real.

## 2026-08-27 (cont.) — Circuito fechado: /calculate a ler o Supabase real

- **`repositories/aircraft_repository.py`** (novo): `get_aircraft_profile(registration)` vai buscar o perfil completo (aircraft + cabin_zones + cargo_holds + uld_positions) ao Supabase e reconstrói o `AircraftProfile` Pydantic. Devolve `None` se a matrícula não existir — quem chama decide o que fazer. Usa `.in_()` para ir buscar as posições de todos os porões de uma vez (evita N+1 queries), e `truststore` (também aplicado agora no arranque do `main.py`) para a mesma interceção TLS local do seed.
- **`POST /api/v1/load-control/calculate`**: já não usa o `AHM565Parser` mockado — recebe `registration` no payload, vai buscar o perfil ao repositório, e devolve **404** limpo se a matrícula não existir. O `AHM565Parser` deixou de ser importado nas rotas de produção.
- **Testes** (`test_api.py`): `get_aircraft_profile` é substituído por mock (`monkeypatch`, fixture `autouse`) que devolve o perfil real do TC-JNH — sem tocar na rede/Supabase real. Novo teste para o 404. Suite completa: **39/39 testes a passar**, isolada da rede.
- **Verificação end-to-end real** (fora da suite de testes, com o Supabase verdadeiro): corri o servidor a sério e confirmei `POST /calculate` com `TC-JNH` + 4800kg PMC em `11P` devolve `LIZFW=49.9072` — o mesmo valor exato calculado anteriormente com o parser mockado, provando que os dados semeados no Supabase e reconstruídos pelo repositório batem certo com a fonte original. `XX-YYY` (matrícula inexistente) devolve 404 como esperado.

### A minha opinião no momento

- Os testes automáticos (pytest) continuam **sem tocar na rede real** de propósito — usam mock do repositório. A verificação end-to-end genuína (servidor real + Supabase real) foi feita manualmente uma vez para provar que o circuito fecha a sério, não fica só provado "no papel" pelos mocks. Isto não substitui um teste de integração automatizado contra uma DB de teste — fica como próximo passo se quisermos isso em CI.
- `check_weight_limits` continua a usar o mesmo `zfw` para `zfw`/`tow`/`law` — essa simplificação (já registada antes) mantém-se, não resolvida aqui.
- `POST /api/v1/aircraft/profile` continua só a validar, sem gravar — ficou fora do pedido desta vez (só o `/calculate` tinha de deixar de ser hardcoded).

## 2026-08-27 (cont.) — Frontend inicial, CORS, e primeiro E2E real no browser

- **Backend — CORS**: `CORSMiddleware` em `main.py`, com `allow_origins` explícito para `localhost:3000`/`load-control.vercel.app` e `allow_origin_regex=r"https://.*\.vercel\.app"` para cobrir qualquer preview deployment. **Correção face ao pedido**: `allow_origins=["https://*.vercel.app"]` não funciona — o middleware não aceita wildcards nesse parâmetro, só em `allow_origin_regex`.
- **Frontend — `lib/api.ts`**: cliente tipado (`CalculateRequest`/`CalculateResponse`/`ApiError`) para `POST /api/v1/load-control/calculate`, usando `NEXT_PUBLIC_API_URL`. `.env.local.example` criado.
- **Frontend — `app/page.tsx`**: dashboard substitui o template do `create-next-app` — matrícula, dropdowns de posição/tipo de ULD, peso, botão "Calculate Load", cartão de resultado (ZFW/LIZFW/%MACZFW/dentro dos limites), alerta vermelho com o `detail` real da API em erro.
- **Dois bugs reais encontrados e corrigidos ao verificar o circuito end-to-end a sério** (não só com testes automáticos):
  1. `get_aircraft_profile` deixava escapar `KeyError` (env vars do Supabase em falta) sem tratamento — o endpoint devolvia um 503 cru com stack trace. Corrigido: `try/except Exception` à volta da chamada ao repositório, log do erro real no servidor, 503 limpo (`"Serviço de dados de aeronaves indisponível."`) para o cliente.
  2. O servidor de teste tinha sido arrancado sem as env vars do Supabase persistidas de forma fiável (dependia de `export` inline antes de um processo backgrounded). Criado `backend/.env` real (gitignored) em vez de depender disso — mais robusto e é o que qualquer deployment real (Railway) também vai precisar.
- **Verificação E2E real, no browser** (Chrome via automação, não simulação): com backend (porta 8000) e frontend (`npm run dev`, porta 3000) a correr, e Supabase real por trás — carregar 4800kg de PMC em 11P devolveu `ZFW=129.987kg / LIZFW=49.9072 / %MACZFW=11.75% / dentro dos limites: Sim`, **os mesmos valores exatos** do `curl` anterior. De seguida, carregar **6000kg** na mesma posição (excede o limite de 5103kg do PMC) foi corretamente rejeitado com HTTP 422, mostrado no alerta vermelho: *"Peso 6000.0kg excede o limite estrutural de 5103.0kg para 'PMC' na posição '11P'."*

### A minha opinião no momento

- **Railway continua por fazer.** O backend não está deployed em lado nenhum — só correu localmente para este teste. "Fazer push para o Railway atualizar" não se aplica ainda; isso é passo à parte (criar o projeto Railway, ligar o repo) que ainda não demos.
- Os dois bugs encontrados nesta verificação (KeyError não tratado, env vars não fiáveis) só apareceram porque testei a sério em vez de confiar só nos testes automáticos com mock — reforça que a verificação manual end-to-end vale a pena antes de dar uma funcionalidade como fechada, mesmo com testes verdes.
- Achado à parte, de ferramenta: os cliques por coordenadas no browser falhavam silenciosamente neste ambiente (sem erro, sem pedido de rede); cliques por referência de elemento (`ref`) funcionaram sempre. Não é um bug do código, é uma particularidade da automação de browser usada para verificar.
- `POST /api/v1/aircraft/profile` continua só a validar (não grava) — fora do âmbito desta entrega.

## 2026-08-27 (cont.) — Backend no Railway + circuito público fechado

- **Deploy real do backend**: projeto `load-control` no Railway (renomeado de `load-control-backend`), ligado ao GitHub (`cavacofml-alt/load-control`, branch `main`, deploy automático a cada push), env vars do Supabase configuradas, domínio público `load-control-production.up.railway.app`.
- **Bug real encontrado e corrigido**: o primeiro build via GitHub falhou — o Railpack tentou compilar a partir da **raiz do repo** (que não tem `requirements.txt`), não de `backend/`, porque `rootDirectory` não estava definido no serviço. O deploy manual anterior (`railway up` a partir de `backend/`) tinha mascarado isto, continuando "RUNNING" com a imagem antiga enquanto o pipeline do GitHub falhava silenciosamente ao lado. Corrigido com `serviceInstanceUpdate(rootDirectory: "backend")` via API do Railway, seguido de `railway redeploy` — confirmado a funcionar com os mesmos valores exatos (`LIZFW=49.9072`) do teste anterior.
- **`backend/Procfile`** criado (`web: uvicorn main:app --host 0.0.0.0 --port $PORT`).
- **Frontend ligado ao backend real**: `NEXT_PUBLIC_API_URL` definida no Vercel (produção + preview) a apontar para o Railway. Havia uma variável antiga (de antes do backend existir) que foi substituída.
- **Deploy de produção na Vercel** feito a partir da raiz do repo (não de `frontend/`) — fazer `vercel --prod` de dentro de `frontend/` falha com "Root Directory does not exist" quando o projeto já tem Root Directory configurado no dashboard; o CLI precisa de ver a árvore completa do repo para aplicar essa definição.
- **Login de duas contas feito via device-code flow** (Railway e Vercel) — a conta é do utilizador, por isso o login teve de ser confirmado por ele no browser, não por mim.

### A minha opinião no momento

- O bug do `rootDirectory` só foi apanhado porque o utilizador partilhou o ecrã real do dashboard do Railway a meio do trabalho — sem isso, eu teria assumido (incorretamente) que o deploy automático estava a funcionar, só porque `/health` respondia bem (respondia, mas com a imagem antiga, não com o código novo). Vale a pena lembrar: um endpoint a responder não prova que o deploy mais recente funcionou.
- Os dois primeiros códigos de login do Railway expiraram sem confirmação (janela curta, provavelmente 3-5 min) — o processo tem de ser mais rápido da próxima vez: gerar o código e pedir confirmação imediata, não deixar o código "à espera" enquanto se faz outra coisa.

## 2026-08-27 (cont.) — Dashboard "next-gen" (UI scaffold, dados mock)

- **`app/page.tsx` reescrito de raiz**: layout fullscreen (`h-screen`, sem scroll global — só as colunas individuais fazem scroll interno), top bar (voo, matrícula, STD/ETD, badge FLIGHT SECURE/OUT OF LIMITS), 3 colunas (Distribuição de Passageiros + Carga/ULDs | Weight Cascade DOW→ZFW→TOW→LDW com gauges lineares coloridos por proximidade do limite | CG Envelope com `recharts`, polígono + 3 pontos ZFW/TOW/LDW).
- **`recharts` instalado** sem conflitos de peer deps com React/Next.js 16.
- **Dados mock estáticos**, como pedido — DOW 115000kg, DOI 52.00, MZFW 175000kg, etc. Isto está **desligado da API real** de propósito (é um exercício de UI, não voltou a chamar `/calculate`); `lib/api.ts` continua intacto para quando se ligar isto a sério.
- Verificado visualmente no browser: badge verde, gauges verde/verde/âmbar (LDW a 96.1% do limite), os 3 pontos do envelope visíveis e bem posicionados dentro do polígono.

### A minha opinião no momento

- O envelope de CG usado é **ilustrativo**, não os limites certificados reais do A330-300 — a forma (hexágono) dá a sensação certa mas os números não vêm de lado nenhum. Isto é adequado para um scaffold visual, mas fica sinalizado para não ser confundido com dados reais mais tarde.
- Os inputs (passageiros, carga) são interativos no sentido em que aceitam edição, mas **não recalculam nada** — o cascade e o envelope continuam estáticos. Mantive isto deliberadamente fiel ao pedido ("Mock Data... valores estáticos"), mas é o próximo passo óbvio se quiserem que o dashboard passe de maquete a ferramenta real: ligar estes inputs ao `lib/api.ts` já existente.

## 2026-08-27 (cont.) — Dashboard ligado ao /calculate real

- **`app/page.tsx`**: passageiros e carga passam a alimentar `useState`, com um `useEffect` debounced (500ms) que chama `calculateLoad()` (`lib/api.ts`) a cada alteração — sem botão, auto-calculate mesmo, como pedido. Um `requestIdRef` evita que uma resposta lenta e antiga sobreponha um cálculo mais recente quando o utilizador edita vários campos seguidos.
- **Weight Cascade**: o gauge de **ZFW é real** (`result.zfw`, limite `AIRCRAFT.mzfw`). **TOW/LDW continuam estimativa** — o backend não calcula estes hoje (sem conceito de combustível no sistema) — e ficam marcados com um badge visual "estimativa" para não passar por dados reais.
- **CG Envelope**: o ponto de **ZFW move-se em tempo real** (`mac: result.mac_zfw`, `weight: result.zfw`), desaparece se não houver resultado válido. Os pontos de TOW/LDW mantêm-se estáticos/cinzentos (mock), visualmente distintos do ZFW (azul).
- **Erros**: um `ApiError` (404/422) do backend real é capturado e mostrado num banner vermelho com a mensagem exata da API; o badge principal muda para `OUT OF LIMITS`.
- **Verificado no browser contra o Railway real** (não mock): alterar passageiros/carga recalcula ZFW corretamente (ex.: 152.015kg/86.9%, LIZFW 69.0585, %MACZFW 18.01%); pôr 6000kg de PMC em 11P (excede o limite de 5103kg) dispara o erro real, o banner mostra a mensagem exata do backend, e o badge muda para vermelho.

### A minha opinião no momento

- Recusei fingir que TOW/LDW vêm "exatos da API" (como o pedido original assumia) porque simplesmente não existem no backend — antes preferi marcar isso claramente na UI do que inventar dados. É uma lacuna real do sistema (falta conceito de combustível), não só um detalhe de UI por fazer.
- O debounce de 500ms é uma escolha arbitrária — bom compromisso entre sentir "ao vivo" e não disparar um pedido por cada tecla, mas não testei com latência de rede alta (Railway pode ter cold start).

## 2026-08-27 (cont.) — Módulo de combustível (TOW/LDW reais)

- **Backend**: `CalculateRequest` passa a exigir `take_off_fuel` e `trip_fuel` (`Field(..., ge=0)`, sem default — omiti-los devolve 422, não um cálculo silencioso a zero). Novo `BalanceCalculator.calculate_tow(zfw, take_off_fuel)` = ZFW + combustível à descolagem, e `calculate_ldw(tow, trip_fuel)` = TOW − combustível de viagem. Validação extra: `trip_fuel > take_off_fuel` devolve 422 antes de sequer ir buscar o perfil da aeronave (não faz sentido gastar mais combustível em rota do que o que foi carregado).
- **Limites**: TOW/LDW passam por `check_weight_limits` contra o MTOW/MLAW reais do perfil (já existia a função, só não era alimentada com valores reais até agora). Segui a mesma lógica não-bloqueante que já havia para o ZFW — exceder o limite **não** impede o cálculo, só marca `tow_within_limits`/`ldw_within_limits`/`within_limits` a `false` e devolve os números reais na mesma. Vale notar: tecnicamente o ZFW nunca "bloqueou" nada, era sempre uma flag — mantive esse padrão para os três em vez de inventar um comportamento novo só para o combustível.
- **`CalculateResponse`** ganhou `tow`, `ldw`, `tow_within_limits`, `ldw_within_limits`, `within_limits`.
- **Testes**: `test_tow_and_ldw_from_fuel`, `test_tow_over_mtow_is_flagged` (unitários) + `test_calculate_missing_fuel_fields_returns_422`, `test_calculate_fuel_produces_real_tow_and_ldw`, `test_calculate_trip_fuel_over_take_off_fuel_returns_422`, `test_calculate_tow_over_limit_flags_but_does_not_block` (API). 45/45 testes a passar.
- **Frontend**: novo painel "Combustível" (Take-Off Fuel / Trip Fuel, inputs numéricos) acima da distribuição de passageiros. Removido o badge "Estimativa" dos gauges de TOW/LDW — ligados a `result.tow`/`result.ldw` reais, com fallback só para quando ainda não há resultado (`result?.tow ?? AIRCRAFT.dow + takeOffFuel`). Badge principal agora reflete `result.within_limits` (os três pesos), não só o ZFW.
- **CG Envelope**: os pontos de TOW/LDW usam agora o **peso real** mas o **%MAC continua estimado** (`MAC_ESTIMATE`) — calcular o efeito do combustível no índice/CG exigiria a tabela de índice por tanque (Secção C do AHM565), que não está implementada. Legenda atualizada para deixar isto explícito ("TOW / LDW (%MAC estimado)").
- **Bug apanhado por mim próprio antes de reportar como concluído**: depois de todas as alterações passarem localmente (pytest + `tsc`), testei no browser contra o backend de produção no Railway e os números de TOW/LDW não batiam certo com a aritmética esperada. Investiguei com um `curl` direto ao Railway com o mesmo payload — a resposta não tinha `tow`/`ldw`/`within_limits` nenhum, ou seja, o Railway continuava a correr o código **antigo**, porque eu tinha feito todas as alterações do backend localmente mas ainda não tinha feito `git commit`/`push`. O `??` de fallback no frontend mascarou isto silenciosamente (mostrou um número plausível em vez de um erro), o que tornou o sintoma mais confuso do que devia.

### A minha opinião no momento

- O maior risco deste módulo não é a matemática (é trivial: soma e subtração) — é a falsa sensação de precisão que o gauge de TOW/LDW passa a dar, quando o %MAC associado a esses pesos continua a ser um número estimado, não calculado. Deixei isso bem sinalizado na legenda, mas se isto for para produção a sério, o próximo passo lógico é mesmo a tabela de índice de combustível — sem isso, um operador podia confiar demasiado num ponto do envelope que só está "meio certo".
- A validação `trip_fuel > take_off_fuel` é uma proteção óbvia mas não é a única fisicamente inválida possível (ex.: combustível negativo já é apanhado pelo `ge=0`, mas não valido, por exemplo, combustível acima da capacidade máxima de tanques da aeronave — esse dado nem sequer existe no `AircraftEnvelope` hoje). Fica como lacuna conhecida, não bloqueante para este passo.
- Vale a pena registar o processo, não só o resultado: só encontrei o bug de deploy porque desconfiei dos números e fui verificar a fonte (`curl` direto à API, não ao frontend) em vez de assumir que o meu código estava certo só porque os testes locais passavam. "Passa nos testes localmente" e "está em produção" são coisas diferentes — já tinha escrito isto no PROGRESS.md a propósito do bug do Railway `rootDirectory`, e voltei a cair perto do mesmo tipo de armadilha (verificar o sintoma errado) antes de me corrigir a mim próprio.

## Próximos passos possíveis (não decididos)
- [ ] Calcular o efeito do combustível no índice/CG (Secção C do AHM565) para que os pontos de TOW/LDW no envelope deixem de depender de %MAC estimado
- [ ] Construir a lista de voos + assinatura de loadsheet (tabelas `flights`/`loadsheets` já existem no Supabase, ainda sem endpoint nenhum a usá-las)
- [ ] Substituir o envelope de CG ilustrativo pelos limites reais certificados (Secção C, Sheet 5 do AHM565)
- [ ] Ligar `POST /api/v1/aircraft/profile` à gravação no Supabase (reutilizando a lógica de `scripts/seed_tcjnh.py`)
- [ ] Teste de integração automatizado (não só mock) contra uma DB de teste/staging, para cobrir em CI o que hoje só foi verificado manualmente
- [ ] Parsing real de secções do AHM 565 (C: index/MAC/CG limits; D: holds/cabin; E: DOW/DOI por registration) em vez de dados hardcoded
- [ ] Estrutura real de mensagem telex para `ahm560_parser.py` (falta uma amostra real)
- [ ] Decidir se `BalanceCalculator` passa a trabalhar sobre `AircraftProfile` (envelope + holds + zonas) em vez de parâmetros soltos
- [ ] Validação de `max_weight`/`max_capacity` ao aplicar deadload/passageiros (`calculate_lizfw` ainda não rejeita sobrecarga de um CPT ou zona)
- [ ] EZFW/TOW/LAW acumulados a partir de PNL/ADL
- [ ] Testes unitários adicionais (casos-limite: pesos negativos, índice extremo)
- [ ] Fluxo de onboarding/convite para atribuir `airline_id` a novos `profiles`
- [ ] `MessageGateway` (adapter) para ACARS/SITA/Tipo B
- [ ] Tabela de regras DGR versionada por `dgr_edition`
- [ ] Abstração do solver de Auto-Load (heurística MVP → OR-Tools/PuLP/SciPy)
