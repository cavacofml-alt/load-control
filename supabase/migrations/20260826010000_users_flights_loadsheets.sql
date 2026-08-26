-- =========================================================================
-- 1. PROFILES — liga auth.users (Supabase Auth) a uma airline + role
-- =========================================================================
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    airline_id UUID REFERENCES airlines(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'load_controller'
        CHECK (role IN ('admin', 'dispatcher', 'load_controller', 'viewer')),
    full_name VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Helper SECURITY DEFINER: devolve o airline_id do utilizador autenticado.
-- Corre com privilégios do criador para evitar recursão de RLS ao consultar profiles.
CREATE OR REPLACE FUNCTION public.current_airline_id()
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT airline_id FROM profiles WHERE id = auth.uid();
$$;

-- =========================================================================
-- 2. FLIGHTS
-- =========================================================================
CREATE TABLE flights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    airline_id UUID NOT NULL REFERENCES airlines(id) ON DELETE CASCADE,
    aircraft_id UUID REFERENCES aircraft(id),

    flight_number VARCHAR(10) NOT NULL,
    origin VARCHAR(4) NOT NULL,       -- ICAO
    destination VARCHAR(4) NOT NULL,  -- ICAO
    std TIMESTAMPTZ NOT NULL,         -- Scheduled Time of Departure

    status VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED'
        CHECK (status IN ('SCHEDULED', 'CLOSED', 'DEPARTED', 'CANCELLED')),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_flights_airline_std ON flights(airline_id, std);

-- =========================================================================
-- 3. LOADSHEETS — ledger append-only (auditoria IATA/ICAO)
-- =========================================================================
CREATE TABLE loadsheets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flight_id UUID NOT NULL REFERENCES flights(id) ON DELETE CASCADE,

    version INTEGER NOT NULL,
    supersedes_id UUID REFERENCES loadsheets(id),
    document_type VARCHAR(10) NOT NULL DEFAULT 'FINAL'
        CHECK (document_type IN ('FINAL', 'LMC')),

    -- Resultados do motor de cálculo (backend/core/calculator.py)
    zfw NUMERIC(10,2) NOT NULL,
    tow NUMERIC(10,2) NOT NULL,
    law NUMERIC(10,2) NOT NULL,
    zfw_cg NUMERIC(10,5) NOT NULL,
    zfw_mac NUMERIC(10,2) NOT NULL,
    tow_cg NUMERIC(10,5) NOT NULL,
    tow_mac NUMERIC(10,2) NOT NULL,
    total_index NUMERIC(10,5) NOT NULL,

    -- Snapshot completo dos inputs usados para gerar esta versão (reconstrução/auditoria)
    raw_payload JSONB,

    signed_by UUID NOT NULL REFERENCES profiles(id),
    signed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(flight_id, version)
);

CREATE INDEX idx_loadsheets_flight ON loadsheets(flight_id);

-- Torna a tabela verdadeiramente append-only: bloqueia UPDATE/DELETE ao nível
-- do motor de base de dados, não apenas por convenção da aplicação. Uma
-- correção (LMC) é sempre um INSERT com supersedes_id a apontar para a versão anterior.
CREATE OR REPLACE FUNCTION prevent_loadsheet_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'loadsheets is append-only: % is not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_loadsheets_no_mutation
BEFORE UPDATE OR DELETE ON loadsheets
FOR EACH ROW EXECUTE FUNCTION prevent_loadsheet_mutation();

-- =========================================================================
-- 4. RLS — isolamento multi-tenant por airline_id via profiles
-- =========================================================================
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE flights ENABLE ROW LEVEL SECURITY;
ALTER TABLE loadsheets ENABLE ROW LEVEL SECURITY;

-- profiles: cada um vê o seu próprio perfil, ou perfis da mesma airline
CREATE POLICY "profiles_select_own_or_airline" ON profiles
    FOR SELECT USING (id = auth.uid() OR airline_id = public.current_airline_id());

CREATE POLICY "profiles_update_own" ON profiles
    FOR UPDATE USING (id = auth.uid());

-- airlines: só a própria airline do utilizador
CREATE POLICY "airlines_select_own" ON airlines
    FOR SELECT USING (id = public.current_airline_id());

-- aircraft: filtrado por airline_id direto
CREATE POLICY "aircraft_tenant_isolation" ON aircraft
    FOR ALL USING (airline_id = public.current_airline_id())
    WITH CHECK (airline_id = public.current_airline_id());

-- cabin_zones / cargo_holds: filtrados via aircraft.airline_id
CREATE POLICY "cabin_zones_tenant_isolation" ON cabin_zones
    FOR ALL USING (
        aircraft_id IN (SELECT id FROM aircraft WHERE airline_id = public.current_airline_id())
    )
    WITH CHECK (
        aircraft_id IN (SELECT id FROM aircraft WHERE airline_id = public.current_airline_id())
    );

CREATE POLICY "cargo_holds_tenant_isolation" ON cargo_holds
    FOR ALL USING (
        aircraft_id IN (SELECT id FROM aircraft WHERE airline_id = public.current_airline_id())
    )
    WITH CHECK (
        aircraft_id IN (SELECT id FROM aircraft WHERE airline_id = public.current_airline_id())
    );

-- flights: filtrado por airline_id direto
CREATE POLICY "flights_tenant_isolation" ON flights
    FOR ALL USING (airline_id = public.current_airline_id())
    WITH CHECK (airline_id = public.current_airline_id());

-- loadsheets: filtrado via flights.airline_id. Sem policy de UPDATE/DELETE
-- de propósito — o trigger acima já bloqueia essas operações para todos.
CREATE POLICY "loadsheets_select_tenant" ON loadsheets
    FOR SELECT USING (
        flight_id IN (SELECT id FROM flights WHERE airline_id = public.current_airline_id())
    );

CREATE POLICY "loadsheets_insert_tenant" ON loadsheets
    FOR INSERT WITH CHECK (
        flight_id IN (SELECT id FROM flights WHERE airline_id = public.current_airline_id())
    );
