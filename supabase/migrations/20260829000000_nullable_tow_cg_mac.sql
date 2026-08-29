-- O motor de cálculo ainda não determina o efeito do combustível no
-- índice/CG (tabela de índice por tanque, Secção C do AHM565 — ver
-- PROGRESS.md, "Próximos passos possíveis"). Sem isso não existe forma
-- honesta de preencher tow_cg/tow_mac ao assinar uma loadsheet: preferimos
-- gravar NULL num registo de auditoria imutável a inventar um número
-- plausível mas não calculado. Ambas as colunas ficam claramente
-- assinaladas como "não certificado" enquanto isto for verdade.
ALTER TABLE loadsheets ALTER COLUMN tow_cg DROP NOT NULL;
ALTER TABLE loadsheets ALTER COLUMN tow_mac DROP NOT NULL;

COMMENT ON COLUMN loadsheets.tow_cg IS
    'NULL até o motor de cálculo suportar o índice de combustível (Secção C do AHM565). Uma loadsheet com tow_cg NULL não é uma loadsheet certificada.';
COMMENT ON COLUMN loadsheets.tow_mac IS
    'NULL pelo mesmo motivo que tow_cg — ver comentário nessa coluna.';
