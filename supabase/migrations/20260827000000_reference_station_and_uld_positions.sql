-- Coluna em falta: reference_station foi adicionada ao modelo Pydantic
-- (AircraftEnvelope) mas nunca migrada para a base de dados.
ALTER TABLE aircraft ADD COLUMN reference_station NUMERIC(10,5) NOT NULL DEFAULT 0;
ALTER TABLE aircraft ALTER COLUMN reference_station DROP DEFAULT;

-- Posições de ULD dentro de um porão (Secção D3/D3.1 do AHM565) — nunca
-- tinham sido persistidas, só existiam como modelo Pydantic em memória.
CREATE TABLE uld_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cargo_hold_id UUID NOT NULL REFERENCES cargo_holds(id) ON DELETE CASCADE,
    position_code VARCHAR(10) NOT NULL,
    balance_arm NUMERIC(10,5) NOT NULL,
    allowed_ulds JSONB NOT NULL,
    mutually_exclusive_with TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(cargo_hold_id, position_code)
);

CREATE INDEX idx_uld_positions_cargo_hold ON uld_positions(cargo_hold_id);

ALTER TABLE uld_positions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "uld_positions_tenant_isolation" ON uld_positions
    FOR ALL USING (
        cargo_hold_id IN (
            SELECT ch.id FROM cargo_holds ch
            JOIN aircraft a ON a.id = ch.aircraft_id
            WHERE a.airline_id = public.current_airline_id()
        )
    )
    WITH CHECK (
        cargo_hold_id IN (
            SELECT ch.id FROM cargo_holds ch
            JOIN aircraft a ON a.id = ch.aircraft_id
            WHERE a.airline_id = public.current_airline_id()
        )
    );
