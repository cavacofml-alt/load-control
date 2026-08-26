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
