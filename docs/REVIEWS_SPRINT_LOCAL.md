# Reviews editoriales y comunitarias — auditoría local previa a la publicación

Este documento conserva la auditoría y las pruebas de la etapa local. Las referencias posteriores a la editorial aplanada y a una reparación pendiente describen el estado **anterior** a la operación del 28 de septiembre de 2026.

La reparación autorizada ya actualizó únicamente `adminPublishedReviews/la_vitrina/review/descripcion` mediante escritura condicional con ETag. El texto vivo coincide con la copia aprobada (SHA-256 `ff552d83ee7117710f0f236e92b6680aaae02533b0c22b8b2a1881a4e7fbe836`, 285 saltos). El resto de la editorial y `roomReviews` no cambiaron; una segunda pasada de solo lectura informó 0 operaciones pendientes. El snapshot de 42 reviews y las páginas de este documento siguen preparados para su publicación web.

## Mapa de fuentes

| Fuente | Consumidor | Renderer | Persistencia |
| --- | --- | --- | --- |
| `adminPublishedReviews/{roomKey}` | Edición admin de Perfil; ahora también listado/edición de Gestión 8787 en solo lectura | `editorial-review-renderer.js` en la ficha y preview | RTDB editorial; la web pública no la consulta para el visitante |
| `published_reviews.json` | Home, pestaña Reviews, ranking y fichas editoriales; `/reviews/` y páginas SEO mediante `build_seo_pages.py`; Gestión 8787 | `editorial-review-renderer.js` (web, SEO y Gestión) | Export estático de editoriales, 42 registros en el estado local actual |
| `roomReviews/{roomKey}/{uid}` | Formulario del perfil/sala, lista y puntuaciones comunitarias dentro de la ficha | Texto HTML escapado con `white-space: pre-line`; independiente del editorial | RTDB comunitaria; no crea página SEO ni review principal automáticamente |
| `adminReviewDrafts/{draftId}` | Borradores del perfil admin | Formulario admin | RTDB privada de edición |
| `data.json` / `HECHOS` | Historial editorial antiguo, metadatos de sala y compatibilidad | Ficha legacy | Archivo histórico; la review publicada prevalece para la identidad correspondiente |
| `review_photos.json` | Fotos/MP4 de la review en ficha, SEO y Gestión | Galerías propias | Archivo estático de medios, separado del texto |

El perfil normal crea una reseña comunitaria en `roomReviews`. La edición editorial del perfil está protegida por el rol leído de `admins/{uid}`; no depende exclusivamente del email. Gestión es un proceso local independiente. El visitante público usa el snapshot `published_reviews.json`; actualmente una editorial nueva de Firebase no entra en Home ni SEO hasta exportarla y publicar.

## La Vitrina

- Catálogo: `id=la-vitrina`; clave RTDB `la_vitrina`.
- Editorial `adminPublishedReviews/la_vitrina`: publicada el 2026-09-26 18:55:05.969 UTC, autor visible Isaac B.; `descripcion` de 9.953 caracteres y **0** saltos de línea.
- Comunidad `roomReviews/la_vitrina`: tres reseñas, de Anna T., Judit O. e Isaac B. La de Isaac contiene 9.953 caracteres y **285** saltos de línea; al reemplazar cada salto por un espacio, el texto coincide exactamente con el editorial. Es el mismo autor/UID y la misma sala; las otras dos reseñas son independientes.
- La copia superior procede de `adminPublishedReviews` y se presentaba con título “Review del grupo”. Al recibir un párrafo ya aplanado, el renderer no podía reconstruir secciones. La inferior es la copia comunitaria con saltos conservados.
- La secuencia exacta que aplanó el texto **no consta** en el registro: Firebase ya guarda espacios. El formulario admin actual usa `.trim()` y conserva saltos; no hay prueba de que el renderer o la serialización JSON los hayan eliminado. La equivalencia exacta sí permite recuperar localmente el formato desde la copia comunitaria del mismo UID, sin inferencia por nombre.
- Al comenzar esta auditoría La Vitrina no existía en el snapshot estático de 41 reviews. Gestión antes consultaba únicamente ese archivo y por eso no la encontraba. El panel local ahora superpone las editoriales Firebase en modo lectura y etiqueta explícitamente las no exportadas.

Durante la validación apareció una edición local concurrente desde Gestión, ajena a los comandos de este sprint: `catalog.json` amplió la sinopsis de La Vitrina, `review_photos.json` recibió cuatro imágenes y `published_reviews.json` recibió `la_vitrina` con los 285 saltos originales (42 reviews en total). También se añadieron `images/Hechos/la_vitrina_1.jpeg` a `_4.jpeg`. Se han conservado sin revertirlos ni sobrescribirlos. La descripción local coincide **byte a byte** con el texto comunitario de origen (SHA-256 UTF-8 `ff552d83ee7117710f0f236e92b6680aaae02533b0c22b8b2a1881a4e7fbe836`). Esta copia local más reciente es ahora la elegida por la web local; la editorial Firebase original sigue aplanada.

## Cambios locales

- La ficha renderiza la editorial una sola vez con `Review The Vault`. Si una copia comunitaria tiene el **mismo UID y texto exacto** (permitiendo solo el reemplazo comprobado de saltos por espacios), no se repite en la lista ni en su media comunitaria. Anna y Judit siguen visibles. No se fusionan salas ni reseñas por parecido de nombre.
- Cuando se cumplen esas mismas precondiciones, la ficha y Gestión usan el texto original con saltos para mostrar la editorial. No hay cambio de datos en RTDB. En Gestión se informa de que la recuperación todavía no se ha guardado.
- `editorial-review-renderer.js` es la única implementación de HTML editorial: web y preview la cargan como script; el generador SEO la invoca mediante `scripts/render_editorial_review.cjs`. El texto comunitario usa un renderer sencillo, escapado y con saltos conservados.
- Gestión lista estáticas + editoriales Firebase en vivo y restaura `NUEVA REVIEW`: selección de sala por `roomId` exacto, campos, cuatro puntuaciones, preview y guardado **solo local** en `published_reviews.json`. La creación falla cerrada si no se puede comprobar el registro Firebase, si ya existe una editorial o si falta ID canónico.
- El editor admin del perfil ahora exige selección exacta de una sala de catálogo y guarda `review.id` canónico; sigue escribiendo la editorial en el mismo esquema `adminPublishedReviews/{roomKey}` cuando se use en producción tras publicar el código.

No existe un commit que *eliminara* “Nueva review” del portal: `panel-thevault-local.py` no está versionado en el repositorio público y el historial textual documenta que aquella pestaña se implementó deliberadamente primero como “Editar review publicada”, posponiendo la creación. No es posible atribuir una eliminación a un commit verificable.

## Contrato editorial y siguiente paso remoto

La fuente editorial de referencia propuesta es `adminPublishedReviews/{canonicalRoomKey}` con `status`, `roomKey`, `sourceRoomKey`, `roomName`, `review` (`id` canónico, metadatos, cuatro notas, `valoracion`, `descripcion` con `\n`), autor y timestamps. `published_reviews.json` es un **snapshot derivado** para Pages, SEO y Home. Las reseñas de usuario continúan separadas en `roomReviews`.

El panel mantiene de momento su guardado local heredado porque esta fase prohíbe writes en Firebase. Una publicación futura debe resolver la sincronización de esos cambios locales hacia el registro editorial de referencia mediante el flujo aprobado, con comparación de versiones/conflictos y export posterior. Para La Vitrina, debe revisarse y autorizarse una corrección puntual del `descripcion` editorial Firebase usando la copia exacta de 285 saltos; el snapshot local ya tiene el texto correcto. No se debe borrar su reseña comunitaria ni las de Anna/Judit. La página SEO de La Vitrina y el contador 42 se regeneraron **solo en el árbol local**; producción no se ha actualizado ni publicado en esta fase.

Capturas privadas: `private/reviews-sprint/screenshots/`. Los JSON de auditoría en esa carpeta están ignorados por Git. Se mantuvo intacto el fix de contador/mapa.

## Identidad, duplicados y límite del modelo actual

La editorial Firebase de La Vitrina se identifica por `adminPublishedReviews/la_vitrina`: `roomKey` y `sourceRoomKey` son `la_vitrina`, pero **no tiene `reviewId` ni `review.id` explícitos**. El catálogo asigna a esa misma clave el ID `la-vitrina`. La copia estática local sí contiene `review.id=la-vitrina` y genera `/reviews/la-vitrina/`. Las tres reseñas comunitarias están bajo `roomReviews/la_vitrina`; tampoco tienen un `reviewId` opaco propio. Sus autores visibles son Anna T., Judit O. e Isaac B. Solo el texto de Isaac B. reproduce exactamente la editorial al sustituir los 285 saltos por espacios. El informe no reproduce las claves privadas de autor.

El criterio actual de supresión exige simultáneamente: misma sala canónica, editorial publicada, misma identidad de autor registrada en los dos objetos y equivalencia exacta del texto (o la transformación comprobada de salto a espacio). No deduplica por nombre visible ni por parecido de contenido. La Vitrina muestra **1 editorial + 2 comunitarias independientes**; la tercera, origen de la editorial, no se presenta ni participa en la media comunitaria. La copia estática con 285 saltos es autosuficiente y no necesita leer la comunidad para renderizarse. La recuperación temporal desde comunidad sigue existiendo para la editorial Firebase aplanada que aún no se ha saneado.

Para un modelo futuro, cada reseña comunitaria debería recibir al crearse un ID opaco estable y cada editorial derivada debería guardar `originReviewId` junto al ID canónico de sala y el tipo de origen. Entonces la deduplicación se basaría en esa relación explícita, conservando una comprobación de autor y sala. **No se ha añadido ni migrado ese campo en RTDB en este sprint.**

## Publicación futura y separación de cambios

La fuente viva objetivo es `adminPublishedReviews`; el JSON estático es su export público, nunca una segunda editorial independiente. Hoy Gestión 8787 guarda la edición solo en el snapshot local por la prohibición de escrituras remotas. Antes de publicar habrá que comparar la versión local de La Vitrina (texto, puntuaciones, fotos y timestamp) con la editorial Firebase, decidir y ejecutar una actualización editorial autorizada, y después regenerar el snapshot/SEO desde la fuente viva. Publicar únicamente el JSON local sin esa reconciliación podría dejar dos versiones editoriales. Las reseñas comunitarias independientes se conservan.

Inventario de diff: el código de este sprint está en `index.html` (normalización, formulario y renderer), `editorial-review-renderer.js`, `scripts/render_editorial_review.cjs`, `scripts/build_seo_pages.py`, pruebas de reviews/SEO y `panel-thevault-local.py` local. La edición realizada desde Gestión añadió La Vitrina a `published_reviews.json`, ajustó su sinopsis en `catalog.json`, añadió fotos a `review_photos.json` y cuatro JPEG en `images/Hechos/`. La generación SEO produjo `/reviews/la-vitrina/`, su tarjeta, `/salas/la-vitrina/`, sitemap, estadísticas y otros HTML derivados; también generó la tarjeta social y miniatura nuevas. Los cambios preexistentes de Auth same-origin en `__/`, `firebase-config.same-origin.example.js`, `firebase-auth-helpers.lock.json`, `docs/FIREBASE_AUTH_SAME_ORIGIN.md`, scripts/tests de helpers y parte de `index.html`, `service-worker.js` y workflows **no pertenecen a este sprint** y no deben mezclarse en su publicación.

## Inventario editorial local (42 identidades)

| ID catálogo | Clave de estado | Slug review | Nombre |
| --- | --- | --- | --- |
| `enterprises` | `enterprises` | `abduction-enterprises` | Abduction Enterprises |
| `achijira` | `achijira` | `achijira` | Achijira |
| `alkatraz-medieval-santiago-de-compostela` | `alkatraz_medieval_santiago_de_compostela` | `alkatraz-medieval` | Alkatraz Medieval |
| `aradia-insomnia-hotel` | `aradia_insomnia_hotel` | `aradia-insomnia-hotel` | Aradia (Insomnia Hotel) |
| `bank-of-thaqar` | `bank_of_thaqar` | `bank-of-thaqar` | Bank of Thaqar |
| `biohazard` | `biohazard` | `biohazard` | Biohazard |
| `catacumbas` | `catacumbas` | `catacumbas` | Catacumbas |
| `dark-city` | `dark_city` | `dark-city` | Dark City |
| `el-cetro-de-fuego` | `el_cetro_de_fuego` | `el-cetro-de-fuego` | El cetro de Fuego |
| `el-diamante-de-almas` | `el_diamante_de_almas` | `el-diamante-de-almas` | El Diamante de Almas |
| `el-hijo-perdido-del-posadero` | `el_hijo_perdido_del_posadero` | `el-hijo-perdido-del-posadero` | El hijo Perdido del Posadero |
| `el-secreto-de-jaipur` | `el_secreto_de_jaipur` | `el-secreto-de-jaipur` | El Secreto de Jaipur |
| `el-secreto-de-los-krugger` | `el_secreto_de_los_krugger` | `el-secreto-de-los-krugger` | El Secreto de los Krugger |
| `exodus` | `exodus` | `exodus` | Exodus |
| `forbidden-room` | `forbidden_room` | `forbidden-room` | Forbidden Room |
| `freak-show` | `freak_show` | `freak-show` | Freak show |
| `highschool` | `highschool` | `high-school` | High School |
| `inmortum-2` | `inmortum_2` | `inmortum-2` | Inmortum 2 |
| `jurasico` | `jurasico` | `jurasico` | Jurásico |
| `k-o-n-g-protocol` | `k_o_n_g_protocol` | `k-o-n-g-protocol` | K.O.N.G. Protocol |
| `la-historia-de-charlotte` | `la_historia_de_charlotte` | `la-historia-de-charlotte` | La Historia de Charlotte |
| `la-isla-de-las-munecas` | `la_isla_de_las_munecas` | `la-isla-de-las-munecas` | La Isla de las Muñecas |
| `la-llamada-arcana` | `la_llamada_arcana` | `la-llamada-arcana` | La Llamada Arcana |
| `la-posesion` | `la_posesion` | `la-posesion` | La Posesión |
| `la-taberna` | `la_taberna` | `la-taberna` | La Taberna |
| `la-tienda-de-te-del-sr-miyagi` | `la_tienda_de_te_del_sr_miyagi` | `la-tienda-de-te-del-sr-miyagi` | La Tienda de Té del Sr. Miyagi |
| `la-vitrina` | `la_vitrina` | `la-vitrina` | La Vitrina |
| `londium` | `londium` | `londium` | Londium |
| `nightshift` | `nightshift` | `night-shift` | Night Shift |
| `nunca-jamas` | `nunca_jamas` | `nunca-jamas` | Nunca Jamás |
| `olimpo` | `olimpo` | `olimpo` | Olimpo |
| `outline` | `outline` | `outline` | Outline |
| `bajo-segunda` | `bajo_segunda` | `parasomnia-bajo-2` | Parasomnia Bajo 2ª |
| `pesadillas-827641` | `pesadillas_827641` | `pesadillas` | Pesadillas |
| `roomangie-2` | `roomangie_2` | `room-angie-2` | Room Angie 2 |
| `roomions` | `roomions` | `roomions` | Roomions |
| `scubick-doo` | `scubick_doo` | `scubick-doo` | Scubick-Doo |
| `seccion-esoterica-exorcista` | `seccion_esoterica_exorcista` | `seccion-esoterismo-exorcista` | Sección Esoterismo: Exorcista |
| `slasher-party` | `slasher_party` | `slasher-party` | Slasher Party |
| `tao` | `tao` | `tao` | Tao |
| `willy-el-tuerto` | `willy_el_tuerto` | `willy-el-tuerto` | Willy el Tuerto |
| `zombie-outbreak` | `zombie_outbreak` | `zombie-outbreak` | Zombie Outbreak |

La Vitrina es la única incorporación frente a `HEAD`: la clave `la_vitrina` pasa de 41 a 42. Los 42 IDs de catálogo, las 42 claves de estado y los 42 slugs son únicos; las páginas, tarjetas y entradas del sitemap tienen exactamente el mismo conjunto de slugs.

## Validación final local

- Node completo: 69/69 PASS; incluye renderer, SEO y la copia autosuficiente de La Vitrina.
- Python del repositorio web: 40/40 PASS. Gestión local: 3/3 PASS.
- Chromium completo: 56 tests, OK (1 omitido). WebKit completo final: 56 tests, OK (1 omitido). Hubo dos fallos intermitentes en pasadas previas, ajenos a reviews: mock incompleto de diagnóstico Auth (estabilizado en el test) y espera de rutas de grupo (pasó aislada y en la pasada completa final, sin tocar rutas).
- Validación estricta: 0 errores, 35 avisos editoriales/de metadatos no bloqueantes; 42 reviews y 59 medios.
- Sintaxis JS/Python y `git diff --check`: PASS. El aviso CRLF→LF de los tres JSON editoriales no es un error.
- Escaneo de secretos de los 53 archivos modificados/nuevos: ninguna credencial real detectada; dos cadenas `sensitive` son fixtures del test de helpers Auth.
- Capturas ignoradas por Git en `private/reviews-sprint/screenshots/`: Gestión (lista, edición, nueva review y preview), ficha 390 px y desktop, y vistas adicionales de editorial/comunidad. En ambas fichas se verificó por DOM 1 editorial, 2 comunitarias independientes, 10 encabezados y 285 saltos.

La web local se puede consultar en `http://127.0.0.1:8765/` y Gestión en `http://127.0.0.1:8787/`. No hubo commit, push, Pages ni escritura Firebase. `database.rules.json` permanece intacto.
