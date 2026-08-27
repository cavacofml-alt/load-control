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

## Próximos passos possíveis (não decididos)
- [ ] Ligar `/api/v1/load-control/calculate` a dados reais do Supabase (por registration), em vez do TC-JNH sempre mockado
- [ ] Ligar `POST /api/v1/aircraft/profile` à gravação no Supabase (reutilizando a lógica de `scripts/seed_tcjnh.py`)
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
