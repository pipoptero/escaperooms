# Datos, privacidad y publicación

Estado: **IMPLEMENTADO** donde se indica ruta de código; **APROBADO** como política por el propietario. Revisión 13/11/2026. Archivos relacionados: `catalog.json`, `data.json`, `convert.py`, `scripts/`, `.github/workflows/`, `scream-parks/`.

`catalog.json` es fuente de altas de escape rooms; conserva IDs canónicos y alias. `data.json` es salida pública del Excel privado del grupo y no fuente de altas. La conversión local exige `convert.py --input` explícito; GitHub Actions no convierte Excel ni ejecuta writers. Scream Parks usa su propio modelo y no se mezcla con escapes. Gestión 8787 pertenece a otro checkout; sus ledgers, credenciales y Excel de investigación siguen privados.

No publicar adaptadores de directorios, checkpoints, respuestas originales, IDs técnicos externos, Excel, SQLite, evidencias, snapshots ni secretos. Para una alta, verificar identidad y campos con la fuente oficial, sin copiar sinopsis o imágenes ajenas. La falta de metadatos públicos no prueba procedencia legítima. No reescribir historial para ocultar exposición pasada sin procedimiento autorizado.

Antes de publicar: revisar Git y staged exacto; ejecutar `python scripts/check_public_repository.py --staged`, `python scripts/check_public_repository.py`, `python scripts/validate_site_data.py --strict`, `git diff --check` y las pruebas pertinentes. Usar commit selectivo con trailer `Vault-Managed-Release: true`, push normal y verificar `update-data` en `VALIDATION_ONLY`, Quality, Pages y smoke público. Preparar rollback con revert controlado sobre HEAD conocido; no usar force push. Cambios de workflow requieren contrastar el monitor de Gestión y `phase6c_remote.py`.

Firebase conserva estados personales y reglas independientes; no realizar escrituras reales para probar un release. SEO y PWA se validan según los cambios. **PENDIENTE**: cualquier migración de datos personales requiere autorización y pruebas propias.
