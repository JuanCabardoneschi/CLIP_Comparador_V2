-- Restaurar API Keys de Railway (PRODUCCION)
DELETE FROM api_keys;
INSERT INTO api_keys (id, client_id, api_key, created_at) VALUES ('a1c70025-f793-494a-ac01-dd16bf3c5519','60231500-ca6f-4c46-a960-2e17298fcdb0','test-api-key-demo-fashion-store-2024','2025-10-16 05:06:06.143287');
