# DB Schema Usage Report (actualizado Nov 2025)

- Limpieza aplicada: removidas categories.is_leaf, categories.level, categories.parent_id y categories.vision_hint
  - Se eliminaron o neutralizaron archivos y referencias dependientes.
- [only_local] images.crop_h -> usos: 10
  - Archivos: clip_admin_backend\app\blueprints\embeddings.py, clip_admin_backend\app\blueprints\images.py, clip_admin_backend\app\models\image.py, clip_admin_backend\app\templates\embeddings\test_multicrop.html, clip_admin_backend\app\templates\images\view.html, clip_admin_backend\app\templates\products\view.html, clip_admin_backend\tools\auto_optimize_crops.py, clip_admin_backend\tools\manual_add_image_crop_columns.py, clip_admin_backend\tools\verify_autocrop_regeneration.py, docs\DB_SCHEMA_DIFF.md
- [only_local] images.crop_w -> usos: 10
  - Archivos: clip_admin_backend\app\blueprints\embeddings.py, clip_admin_backend\app\blueprints\images.py, clip_admin_backend\app\models\image.py, clip_admin_backend\app\templates\embeddings\test_multicrop.html, clip_admin_backend\app\templates\images\view.html, clip_admin_backend\app\templates\products\view.html, clip_admin_backend\tools\auto_optimize_crops.py, clip_admin_backend\tools\manual_add_image_crop_columns.py, clip_admin_backend\tools\verify_autocrop_regeneration.py, docs\DB_SCHEMA_DIFF.md
- [only_local] images.crop_x -> usos: 10
  - Archivos: clip_admin_backend\app\blueprints\embeddings.py, clip_admin_backend\app\blueprints\images.py, clip_admin_backend\app\models\image.py, clip_admin_backend\app\templates\embeddings\test_multicrop.html, clip_admin_backend\app\templates\images\view.html, clip_admin_backend\app\templates\products\view.html, clip_admin_backend\tools\auto_optimize_crops.py, clip_admin_backend\tools\manual_add_image_crop_columns.py, clip_admin_backend\tools\verify_autocrop_regeneration.py, docs\DB_SCHEMA_DIFF.md
- [only_local] images.crop_y -> usos: 10
  - Archivos: clip_admin_backend\app\blueprints\embeddings.py, clip_admin_backend\app\blueprints\images.py, clip_admin_backend\app\models\image.py, clip_admin_backend\app\templates\embeddings\test_multicrop.html, clip_admin_backend\app\templates\images\view.html, clip_admin_backend\app\templates\products\view.html, clip_admin_backend\tools\auto_optimize_crops.py, clip_admin_backend\tools\manual_add_image_crop_columns.py, clip_admin_backend\tools\verify_autocrop_regeneration.py, docs\DB_SCHEMA_DIFF.md
- [only_local] images.is_crop_manual -> usos: 7
  - Archivos: clip_admin_backend\app\blueprints\embeddings.py, clip_admin_backend\app\blueprints\images.py, clip_admin_backend\app\models\image.py, clip_admin_backend\tools\auto_optimize_crops.py, clip_admin_backend\tools\manual_add_image_crop_columns.py, clip_admin_backend\tools\verify_autocrop_regeneration.py, docs\DB_SCHEMA_DIFF.md
- images.refined: se mantiene en uso
