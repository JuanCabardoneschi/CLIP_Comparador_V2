-- Insertar configuraciones de atributos de ejemplo
-- Cliente: Demo Fashion Store

INSERT INTO product_attribute_config (client_id, key, label, type, required, options, field_order) VALUES
('60231500-ca6f-4c46-a960-2e17298fcdb0', 'material', 'Material', 'list', false, '["Algodón", "Poliéster", "Lana", "Seda", "Lino", "Mezcla"]'::jsonb, 1),
('60231500-ca6f-4c46-a960-2e17298fcdb0', 'talla', 'Talla', 'list', false, '["XS", "S", "M", "L", "XL", "XXL"]'::jsonb, 2),
('60231500-ca6f-4c46-a960-2e17298fcdb0', 'color', 'Color', 'text', false, null, 3),
('60231500-ca6f-4c46-a960-2e17298fcdb0', 'marca', 'Marca', 'text', false, null, 4),
('60231500-ca6f-4c46-a960-2e17298fcdb0', 'url_producto', 'URL del Producto', 'url', false, null, 5);
