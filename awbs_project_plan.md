# Projeto: Aircraft Weight & Balance System (AWBS)

## 1. Visão Geral
Sistema cloud-based de controlo de peso e centragem (Weight and Balance) destinado a Load Controllers e Ground Handling Agents. O objetivo é automatizar e otimizar o carregamento de aeronaves, garantindo a máxima segurança e eficiência de combustível (*Ideal Trim*), com emissão de documentação standard IATA.

## 2. Normas e Compliance (IATA / ICAO)
O motor de cálculo e estruturação de dados deve seguir rigorosamente as normativas do setor:
*   **IATA AHM 560:** Formato standard para os dados semipermanentes da aeronave.
*   **IATA AHM 514:** Standard para o Loading Instruction/Report (LIR).
*   **IATA AHM 517:** Standard para a Loadsheet (manual e eletrónica).
*   **IATA DGR (Dangerous Goods Regulations):** Segregação e NOTOC.
*   **Mensagens IATA Tipo B e ACARS:** Geração de LDM, CPM, UCM e envio de Electronic Loadsheet via SITA/ARINC para a aeronave.

## 3. Core Features e Módulos

### 3.1 Gestão de Dados (Aircraft & Flight Data)
*   Parser de ficheiros AHM 560 para criação automática de perfis de aeronaves.
*   Gestão de DOW (Dry Operating Weight) e DOI (Dry Operating Index).
*   **Passenger Distribution & LOPA:** Zonas de cabine (OA, OB, OC...), standard weights (Adult, Male, Female, Child, Infant) e impacto no ZFW CG.

### 3.2 Gestão de Carga (Hold Management)
*   **Lower & Main Deck Loading:** Suporte para aeronaves de passageiros (Belly cargo) e Freighters/Combi (Main deck), incluindo restrições de *floor bearing*, contornos de ULDs e assimetria.
*   **ULDs & Bulk Items:** Controlo de tara, limites de peso, categorias.
*   **Dangerous Goods (DG) & NOTOC:** Motor de regras de segregação (UN numbers, ERG codes) integrado com a emissão do NOTOC.

### 3.3 Motor de Cálculo e Otimização
*   **EZFW (Estimated Zero Fuel Weight):** Projeções iniciais baseadas no PNL/ADL e estimativas de carga para efeitos de planeamento de combustível (Dispatch).
*   Cálculo contínuo de ZFW, TOW (Take-Off Weight) e LAW (Landing Weight).
*   **Automatic Loading (Auto-Load):** Algoritmo para *Ideal Trim* otimizando a distribuição para eficiência de combustível.

### 3.4 Outputs e Reporting
*   **LIR (Loading Instruction Report):** Interface visual para a placa.
*   **Loadsheet (Final & LMC):** Folha de carga com suporte a Datalink/ACARS.

## 4. Arquitetura e Tech Stack Sugerida
*   **Frontend:** Next.js com React (SPA / PWA para tablets usando Capacitor).
*   **Backend & API:** Python (FastAPI) para algoritmos matemáticos e *message brokers* (telex validators).
*   **Base de Dados:** PostgreSQL via Supabase (autenticação e RLS).
*   **Alojamento:** Railway para backend/workers e Vercel para frontend.

## 5. Roadmap de Desenvolvimento (Fases)
*   [ ] **Fase 1:** Setup da infraestrutura (Railway/Supabase) e modelação de dados (Aeronaves, Voos, AHM 560).
*   [ ] **Fase 2:** Ingestão de dados e motor matemático (Pesos, Índices, Limites, EZFW).
*   [ ] **Fase 3:** Interface de Hold Management (Lower Deck, Main Deck, ULDs, Bulk).
*   [ ] **Fase 4:** Gestão de Passageiros (Distribuição por zonas, Cabin Trim).
*   [ ] **Fase 5:** Algoritmo de Otimização (*Ideal Trim* e *Auto-Load*).
*   [ ] **Fase 6:** Regras de Dangerous Goods, NOTOC e Segregação.
*   [ ] **Fase 7:** Outputs (Loadsheet PDF, LIR) e Integrações (Mensagens Tipo B, ACARS Datalink).

---

## 6. Database Schema Base (PostgreSQL)
Para execução via Supabase.

```sql
-- 1. Companhias Aéreas (Para suportar ambiente SaaS / Multi-Tenant)
CREATE TABLE airlines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    iata_code VARCHAR(2) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Frota (Registo da Aeronave e Dados Base AHM 560)
CREATE TABLE aircraft (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    airline_id UUID REFERENCES airlines(id) ON DELETE CASCADE,
    registration VARCHAR(10) UNIQUE NOT NULL,
    type_designator VARCHAR(10) NOT NULL,

    mzfw NUMERIC(10,2) NOT NULL,
    mtow NUMERIC(10,2) NOT NULL,
    mlaw NUMERIC(10,2) NOT NULL,

    dow NUMERIC(10,2) NOT NULL,
    doi NUMERIC(10,5) NOT NULL,

    lemac NUMERIC(10,5) NOT NULL,
    mac_length NUMERIC(10,5) NOT NULL,
    k_constant NUMERIC(10,5) NOT NULL,
    c_constant NUMERIC(10,5) NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Zonas de Cabine (Passenger Distribution - LOPA)
CREATE TABLE cabin_zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aircraft_id UUID REFERENCES aircraft(id) ON DELETE CASCADE,
    zone_code VARCHAR(2) NOT NULL,
    max_capacity INTEGER NOT NULL,
    balance_arm NUMERIC(10,5) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(aircraft_id, zone_code)
);

-- 4. Porões (Hold Management & ULD/Bulk Compartments)
CREATE TABLE cargo_holds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aircraft_id UUID REFERENCES aircraft(id) ON DELETE CASCADE,
    hold_code VARCHAR(10) NOT NULL,
    hold_type VARCHAR(10) CHECK (hold_type IN ('LOWER', 'MAIN')),
    max_weight NUMERIC(10,2) NOT NULL,
    balance_arm NUMERIC(10,5) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(aircraft_id, hold_code)
);

ALTER TABLE airlines ENABLE ROW LEVEL SECURITY;
ALTER TABLE aircraft ENABLE ROW LEVEL SECURITY;
ALTER TABLE cabin_zones ENABLE ROW LEVEL SECURITY;
ALTER TABLE cargo_holds ENABLE ROW LEVEL SECURITY;
```
