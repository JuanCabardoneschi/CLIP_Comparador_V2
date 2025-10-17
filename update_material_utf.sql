UPDATE product_attribute_config
SET options = jsonb_build_object(
  'multiple', false,
  'values', to_json(ARRAY[
     U&'Algod\00F3n',
     U&'Poli\00E9ster',
     U&'Lana',
     U&'Seda',
     U&'Nylon',
     U&'Ray\00F3n',
     U&'Spandex',
     U&'Viscosa',
     U&'Acetato',
     U&'Modal',
     U&'Elastano',
     U&'Cachemira',
     U&'Lino',
     U&'Denim',
     U&'Franela',
     U&'Piel',
     U&'Cuero',
     U&'Gamuza',
     U&'Microfibra',
     U&'Tencel',
     U&'Bamb\00FA',
     U&'Fibras recicladas',
     U&'Mezcla'
  ])
)
WHERE key = 'material' AND client_id = '60231500-ca6f-4c46-a960-2e17298fcdb0';
