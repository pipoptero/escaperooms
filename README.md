# The Vault Escape

Web pública estática de The Vault Escape, desplegada en GitHub Pages. Incluye el catálogo de salas de escape, Scream Parks, reviews editoriales, rankings y funciones personales autenticadas con Firebase.

## Datos públicos

- `catalog.json` conserva las identidades canónicas de las salas de escape. Sus datos tienen procedencias distintas y requieren validación específica; no se presupone que todos los textos o imágenes sean originales.
- `data.json` contiene los datos del grupo necesarios para mostrar pendientes, hechos, reviews y rankings. Se genera desde un Excel privado, que no pertenece al repositorio público.
- `scream-parks/` contiene un catálogo separado por entidad y temporada.
- `published_reviews.json`, `extra_awards.json`, `terpeca_awards.json` y los recursos gráficos autorizados alimentan sus respectivas vistas.
- `room_aliases.json` preserva la continuidad de identidades y enlaces históricos.

Los estados personales, favoritos y autenticación se gestionan mediante Firebase. No se derivan del Excel del grupo.

## Mantenimiento y publicación

El descubrimiento, la investigación, los registros de procedencia, las evidencias, los Excel y las credenciales se guardan en el entorno privado de Gestión. Las fuentes externas pueden aportar pistas, pero no se publica una base de datos de terceros ni se incorporan sinopsis o imágenes sin permiso o base de uso comprobada.

`convert.py` genera una propuesta de `data.json` con rutas explícitas:

```text
python convert.py --input <ruta-al-excel-privado> --output <ruta-de-salida-privada>
```

La salida se compara y valida en un checkout aislado antes de incorporarla selectivamente al producto. El proceso público no necesita ni recibe el Excel. No hay conversión ni commit automático desde GitHub Actions.

Los releases se preparan y comprueban mediante `scripts/validate_site_data.py --strict`, `scripts/check_public_repository.py`, las suites de pruebas y `scripts/managed_release_guard.py`. Solo un commit con el trailer exacto `Vault-Managed-Release: true` puede desplegarse desde `main`. `update-data.yml` valida el release sin writers ni commits hijos; GitHub Pages despliega únicamente el artefacto público enumerado en su workflow.

## Desarrollo local

Servir el checkout por HTTP permite cargar los JSON con `fetch`:

```text
python -m http.server 8765
```

La configuración de Firebase se inyecta durante el despliegue desde secretos de GitHub. No se guarda en Git. Las herramientas de investigación, credenciales y copias privadas permanecen fuera del repositorio.

## Límites de procedencia

Los campos públicos necesarios para presentar las fichas pueden proceder de fuentes oficiales, aportaciones editoriales o investigaciones previas. La presencia de un dato no certifica por sí sola un derecho sobre textos, fotografías o bases de terceros. Los casos pendientes se documentan y resuelven en privado antes de sustituir o ampliar contenido.
