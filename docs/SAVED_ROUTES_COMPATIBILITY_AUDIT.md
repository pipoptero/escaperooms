# Auditoría de compatibilidad de rutas guardadas v47

Fecha de cierre local: 14 de septiembre de 2026. Esta auditoría no desplegó reglas, no publicó el cliente y no escribió en Firebase.

## Versiones y reglas

- Producción continúa sirviendo el cliente y service worker v46 (`20260913-route-planner-v46`, `the-vault-v46`).
- Reglas activas reexportadas en modo lectura: SHA-256 canónico `ac4e5651b88cf0edf01c1c3736ccbbbdeb7f7592d64e096033e52ee52b1b3ce7`.
- Reglas candidatas v47: SHA-256 canónico `622007a944d2e6bbf03c5f80f226036ef5aed734604f70e938225765641e3412`.
- Export privado de referencia: `private/firebase_backups/saved-routes-compat-20260914-052018Z/database.rules.current.json`.
- Lectura administrativa de solo lectura: `/userRoutes` y `/groupRoutes` responden `null`; no hay datos que migrar.

## Resultado de compatibilidad

Firebase Emulator con Firebase Tools 15.14.0 y Java 21: 23/23 PASS. Las funciones de v46 cubiertas por la suite siguen permitidas: perfiles propios, estados personales, creación y lectura de grupos, invitaciones, aceptación de un solo uso, estados compartidos, PATCH multipath y eliminación secuencial de grupos sin rutas.

El caso de cruce entre versiones queda protegido por una precondición en `groups/{groupId}`: un grupo no puede eliminarse mientras exista `groupRoutes/{groupId}`. Un v46 que intente borrar el grupo recibe `permission_denied`; `groups`, `groupMembers`, `userGroups`, `groupRooms`, `groupPendingRooms` y `groupRoutes` permanecen intactos.

v47 borra primero cada ruta grupal, después `groups/{groupId}` y finalmente las ramas auxiliares. Si falla el borrado del grupo después de retirar las rutas, el cliente restaura los payloads exactos leídos al comenzar y muestra el error. La prueba de éxito termina sin ninguna de las seis ramas, y la prueba de fallo conserva grupo y rutas.

## Identidad y progreso

Antes de crear una ruta, el cliente usa la identidad compartida de `room-state.js`, exige una única ficha del catálogo y persiste su ID exacto. Las reglas aceptan solo el formato usado por los 1.735 IDs actuales, hasta 20 posiciones. No pueden consultar el catálogo estático, por lo que la pertenencia exacta al catálogo se garantiza en el cliente; una API directa todavía puede escribir un ID sintácticamente válido que no exista. Una ruta ya guardada conserva de forma deliberada el ID de una sala retirada y la interfaz muestra “No disponible”.

Fixtures personal y grupal A/B/C/D: A y B hechas, C pendiente y D sin estado producen 2/4 (50 %); al cambiar C a hecha en los estados externos producen 3/4 (75 %). El JSON serializado de la ruta es idéntico antes y después. El grupo ignora los estados personales.

Las definiciones oficiales permanecen en código y no son editables. Registrar una ruta crea solo una instancia con IDs canónicos y `officialRouteId`; no copia la definición ni estados derivados.

## Ambigüedades editoriales pendientes

- `movie-route`, “Room Angie 2”: `roomangie-2` y `room-angie`, ambas Ilusium Room Escape, Mataró, Barcelona.
- `panic-tour`, “IN”: `in-barcelona`, Fear Factory Experience, L'Hospitalet de Llobregat, Barcelona; e `in`, Fear Factory Experiences, sin ciudad/provincia informadas.

Ambas rutas siguen visibles y mantienen el progreso histórico, pero no ofrecen “Registrar esta ruta”. Las otras ocho definiciones se registran al resolverse de forma inequívoca.

## Validación local

- Node: 27/27 PASS (`room-state.js` 9, planificador 10, rutas guardadas 8).
- Firebase Emulator: 23/23 PASS.
- Python: 20/20 PASS.
- Chromium: 28/28 PASS.
- WebKit: 28/28 PASS.
- Viewports cubiertos: 375, 390, 430, 768 y escritorio; cierre, teclado/foco y overflow incluidos.
- Validador estricto: 0 errores y 36 avisos editoriales conocidos.
- Sintaxis JavaScript y `git diff --check`: PASS; permanece un aviso informativo CRLF de Git en el workflow de Pages.

## Plan de despliegue y rollback

La siguiente operación requiere autorización nueva. Primero se vuelve a exportar `/.settings/rules`, se comprueba que conserva SHA `ac4e5651…` y se guarda como backup privado fechado. Se despliegan exclusivamente reglas RTDB, se reexportan y se exige SHA `622007a9…`. Después se ejecuta el smoke temporal propietario/miembro/ajeno y se limpia Auth, RTDB e IAM.

Si falla cualquier comprobación, se despliega exclusivamente RTDB Rules desde el backup recién exportado, se reexporta y se exige que su SHA canónico vuelva a `ac4e5651…`; no se adapta ningún dato. Solo tras reglas verdes se publica v47 mediante un commit/push separado, CI y Pages. No existe migración y no se crean rutas para usuarios reales.
