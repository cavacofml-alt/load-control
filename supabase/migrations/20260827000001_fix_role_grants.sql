-- Correção de uma lacuna presente desde a primeira migração: as tabelas
-- criadas via `supabase db push` nunca tiveram GRANTs explícitos para os
-- papéis padrão do Supabase (anon/authenticated/service_role). Isto nunca
-- foi detetado porque só se tinha testado introspecção de schema (que não
-- exige GRANT), nunca uma leitura/escrita real de dados via REST.
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role, authenticated;

-- Garante que tabelas futuras (próximas migrações) herdam os mesmos GRANTs
-- automaticamente, sem repetir isto manualmente de cada vez.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO service_role, authenticated;
