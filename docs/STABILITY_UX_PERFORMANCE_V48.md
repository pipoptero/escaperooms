# Estabilidad, rendimiento y coherencia UX v48

Estado del documento: implementación local validada y Rules de `playedAt` desplegadas de forma controlada antes del cliente. El resultado final de CI/Pages y la validación manual de la PWA instalada se conserva en `CODEX_HANDOFF.md`.

## Reviews

La divergencia 39/38/41 procedía de mezclar fuentes y criterios distintos:

- El registro estático anterior tenía 39 entradas.
- Solo 38 contenían una review publicable real: `encryptroom` tenía puntuaciones/metadatos pero no descripción.
- En producción existían tres reviews promovidas que el registro estático no incluía: `abduction_enterprises`, `aradia_insomnia_hotel` y `olimpo`.
- El resultado canónico correcto es 39 - 1 registro vacío + 3 reviews promovidas = 41.
- `en-la-mente-del-asesino` era la página correspondiente al registro vacío; ahora es una redirección neutral a `/reviews/`, igual que el alias histórico `/reviews/encryptroom/`.

`published_reviews.json` queda como única fuente pública. Las reviews comunitarias en vivo ya no alteran en el cliente el inventario público ni sus contadores. `publicReviewCount()` deriva de ese registro. El generador deriva del mismo origen las páginas, el índice, las tarjetas, los contadores, `site_stats.json` y `sitemap-reviews.xml`.

### Conjuntos A–F

**A. Reviews canónicas (41)**

`abduction-enterprises`, `achijira`, `alkatraz-medieval`, `aradia-insomnia-hotel`, `bank-of-thaqar`, `biohazard`, `catacumbas`, `dark-city`, `el-cetro-de-fuego`, `el-diamante-de-almas`, `el-hijo-perdido-del-posadero`, `el-secreto-de-jaipur`, `el-secreto-de-los-krugger`, `exodus`, `forbidden-room`, `freak-show`, `high-school`, `inmortum-2`, `jurasico`, `k-o-n-g-protocol`, `la-historia-de-charlotte`, `la-isla-de-las-munecas`, `la-llamada-arcana`, `la-posesion`, `la-taberna`, `la-tienda-de-te-del-sr-miyagi`, `londium`, `night-shift`, `nunca-jamas`, `olimpo`, `outline`, `parasomnia-bajo-2`, `pesadillas`, `room-angie-2`, `roomions`, `scubick-doo`, `seccion-esoterismo-exorcista`, `slasher-party`, `tao`, `willy-el-tuerto`, `zombie-outbreak`.

**B. Páginas generadas vivas:** exactamente el mismo conjunto de 41 slugs. Las rutas históricas ajenas al conjunto son redirects y no cuentan como review publicada.

**C. Cards de `/reviews/`:** una por cada elemento de A, 41, sin duplicados.

**D. Últimas reviews de Home:** se ordenan por timestamp fiable. Las primeras son `Olimpo`, `Abduction Enterprises`, `Nunca Jamás`, `Jurásico` y `Forbidden Room`; Home muestra las tres que caben en el bloque de últimas reviews.

**E. Contador Home:** 41, calculado por `publicReviewCount()`.

**F. Contador de navegación:** 41, generado desde la misma fuente.

La regresión automática exige A = B = C = E = F, 41 elementos, slugs únicos y presencia de Abduction en índice/sitemap.

## Abduction Enterprises

- Fuente promovida: `roomReviews/abduction_enterprises`, autor Isaac B., leída durante la auditoría de producción sin escribir datos.
- Identidad canónica de catálogo: `enterprises`; título público: `Abduction Enterprises`.
- Página: `/reviews/abduction-enterprises/`.
- Portada: `images/catalgo_propio_web_escape/optimized/enterprises.jpg` como imagen canónica; Home usa `images/seo/latest/abduction-enterprises.webp` y cae a la portada canónica si falla.
- Share: copiar, WhatsApp y `navigator.share` consumen `getReviewShareUrl(review)`, con URL `https://thevaultescape.com/reviews/abduction-enterprises/`.
- Actividad: entra por su `publishedAt` y queda ordenada junto a estados personales por timestamp.
- SEO: página, tarjeta social, sitemap y enlaces desde índice/Home generados desde el registro canónico.

La solución es genérica: resolver identidad, URL e imagen a través de aliases/catálogo y el registro, sin excepciones para Abduction.

## Auth PWA

### Causa raíz

El flujo anterior arrancaba `signInWithPopup` también en standalone, no consumía de forma efectiva `getRedirectResult()` y no tenía una máquina de estados ni timeout. Si el contexto instalado perdía el popup o retornaba del OAuth sin completar el callback esperado, el texto quedaba indefinidamente en “Conectando”. Una shell antigua cacheada podía prolongar el problema, aunque no era la causa única.

### Solución local

- Estados explícitos: `idle`, `connecting`, `redirecting`, `authenticated`, `unauthenticated`, `error` y `timeout`.
- En standalone se usa redirect; desktop conserva popup.
- Un popup bloqueado cae a redirect.
- `getRedirectResult()` se consume una sola vez y se conserva la intención de retorno en `sessionStorage`.
- Timeout de 15 segundos: abandona `connecting` y muestra “No hemos podido completar el acceso”, `Reintentar` y, en standalone, `Abrir en navegador`.
- Cada transición emite `vault:auth-state` y actualiza `documentElement.dataset.authState`, lo que permite probar y diagnosticar el flujo.

### Service Worker

Los recursos de código pasan a network-first; la caché queda como respaldo offline. Al detectar un nuevo controller se recarga una vez si ya existía un controller anterior, y el registro comprueba actualizaciones al recuperar visibilidad. No se añadió un `skipWaiting/clientsClaim` agresivo.

## Rendimiento

El baseline completo está en `docs/PERFORMANCE_AUDIT_V48.md`.

- Producción v48 construía 10.450 nodos en el arranque.
- Local construye 626 nodos anónimos y 643 autenticados, ~94 % menos.
- Catálogo, ranking, reviews, planificador y mapas se inicializan al solicitarlos.
- Leaflet no se carga en Home.
- Las portadas grandes de Home autenticada se sustituyeron por miniaturas ya existentes: transferencia de imágenes ~1,89 MB → ~0,33 MB; total ~2,08 MB → ~0,51 MB en móvil fixture.
- Sigue existiendo coste al abrir el catálogo completo; queda como candidato a virtualización/paginación, sin introducir framework.

## Navegación

Se mantiene el menú principal superior: The Vault, Catálogo, Pendientes, Hechos, Reviews y Ranking. Se eliminó la segunda fila de accesos redundantes que aparecía tras Identidad/Progreso/Logros. Home continúa directamente con Mi mapa escapista, Progreso escapista, Actividad reciente y Descubre algo nuevo.

## Actividad reciente

La fuente anterior mezclaba una selección estática y carecía de las nuevas publicaciones. La implementación local deriva eventos disponibles:

- reviews publicadas con `publishedAt`/`updatedAt` fiable;
- estados personales hechos o pendientes con `updatedAt`.

Los eventos se ordenan por timestamp descendente. No se inventan fechas para estados legacy. El texto distingue “Review publicada”, “Has registrado esta sala” y “Añadida a pendientes”. Si existe `playedAt`, se muestra aparte como “Jugada DD/MM/AAAA”; la posición del evento continúa usando la fecha técnica de registro/modificación.

No se creó una rama Firebase de eventos. Rutas y logros solo podrán añadirse cuando su modelo aporte un timestamp fiable.

## Fecha de salas hechas

### Modelo

`users/{uid}/roomStates/{roomKey}` conserva el objeto actual y añade opcionalmente:

```json
{
  "done": true,
  "pending": false,
  "playedAt": "2026-09-14",
  "updatedAt": 1789400000000
}
```

Los estados legacy `done` sin `playedAt` siguen siendo válidos. `room-state.js` conserva la fecha cuando el estado final es hecho y la elimina si deja de serlo. Los grupos, rutas guardadas, planner, logros, XP, filtros y mapa continúan leyendo `done`; no requieren migración.

### UI y privacidad

Al marcar como hecho se ofrece Hoy, Elegir fecha o No recuerdo. Una sala hecha permite Editar fecha y eliminarla. Editar la fecha no vuelve a conceder XP/logros. `playedAt` permanece únicamente en el estado personal: no se publica en Perfil Público, grupos, rutas ni payloads públicos.

`database.rules.json` valida una fecha de calendario entre 1900 y 2099, incluido 29 de febrero únicamente en años bisiestos, y solo con `done=true`. Las Rules se desplegaron de forma independiente: SHA anterior `c60805ff86a22ea68a873f059470b4d1f431fca24b3d1cf39651641a8a361eff`; SHA nueva `cd1be579d03065469f69f92a7b4fd073833a100e1453a473e9503b56692a6b9a`. El smoke productivo terminó 25/25 PASS y eliminó cuenta Auth, datos RTDB y binding IAM temporales.

## Pruebas

- Node: 65/65 PASS (`room-state`, route planner, saved routes, public profile).
- Python: 26/26 PASS.
- Firebase Emulator: 40/40 PASS.
- Chromium: 42 PASS + 1 caso Emulator omitido por diseño.
- WebKit: 42 PASS + 1 caso Emulator omitido por diseño.
- Validación estricta: PASS, 1.735 salas, 41 reviews, 0 errores y 35 avisos editoriales ya conocidos.
- `git diff --check`: PASS.

Las regresiones nuevas cubren: 41 reviews en todas las superficies; Abduction, portada y share; ausencia de navegación duplicada; actividad ordenada; fecha hoy/custom/sin fecha/edición/legacy; timeout de Auth; y reglas de `playedAt`.

## Capturas

- `reports/stability-v48/home-authenticated-desktop.png`
- `reports/stability-v48/home-authenticated-mobile-390.png`
- `reports/stability-v48/activity-recent.png`
- `reports/stability-v48/played-at-dialog.png`
- `reports/stability-v48/abduction-latest-review.png`
- `reports/stability-v48/abduction-share.png`

## Riesgos y condición para publicar

- Las Rules de producción ya contienen la validación estricta de `playedAt`; estados `done`/`pending` legacy sin fecha continúan válidos y no se migraron.
- El cambio de Service Worker usa caché `the-vault-v49` y necesita una prueba real v48→v49 en una PWA instalada; el equivalente standalone cubre la lógica, no todos los detalles del contenedor móvil.
- El escenario autenticado de rendimiento usa fixture local, no una cuenta real de producción.
- La apertura del catálogo sigue siendo la interacción más costosa porque genera muchas cards de una vez.
- Firebase solo recibió las Rules RTDB y los registros temporales del smoke, eliminados al terminar. No se modificaron datos reales, proveedores de Authentication ni otros servicios Firebase.
