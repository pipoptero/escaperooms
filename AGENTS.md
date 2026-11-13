# The Vault Escape: entrada para agentes

Antes de modificar código, contenido, diseño o datos de The Vault Escape, lee este archivo y los estándares aplicables de `docs/standards/`. Contrasta la documentación con la implementación real. Respeta la identidad corporativa, los componentes existentes, los contratos de datos, la privacidad y Managed Release. No introduzcas variantes no autorizadas. Si modificas un estándar, actualiza su documentación y pruebas en el mismo cambio. Preserva los cambios locales ajenos y comprueba Git antes de editar.

## Procedimiento obligatorio

1. Identifica el checkout operativo, `origin/main`, los worktrees y cambios locales. Usa un worktree aislado si hay trabajo ajeno.
2. Lee el estándar aplicable: [diseño](docs/standards/BRAND_AND_DESIGN.md), [fichas](docs/standards/ROOM_DETAIL_STANDARD.md), [contenido](docs/standards/EDITORIAL_CONTENT.md), [redes](docs/standards/SOCIAL_MEDIA.md), [datos y release](docs/standards/DATA_AND_RELEASE.md).
3. Inspecciona la ruta real de código y datos. No infieras un contrato de un informe anterior.
4. Aplica cambios mínimos. Conserva IDs, alias, estados personales, reviews y fuentes privadas.
5. Ejecuta pruebas focales, validación estricta, privacidad, navegador y regresión afectada. Documenta los fallos sin rebajar guards.
6. Publica únicamente con autorización y mediante Managed Release; exige Quality, Pages y smoke público. No uses force push.

Los adaptadores de directorios, checkpoints, evidencias, Excel privado y credenciales no pertenecen al repositorio público. `catalog.json` contiene las salas; `data.json` contiene datos del grupo y no sirve para dar de alta salas. Gestión es un checkout separado. Scream Parks conserva identidad y modelo propios.

Estado: **APROBADO** por el propietario el 13/11/2026; entrada normativa versionada. Las instrucciones privadas del workspace siguen aplicando en su ámbito y no se copian aquí.
