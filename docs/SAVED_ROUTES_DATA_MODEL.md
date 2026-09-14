# Rutas guardadas y rutas oficiales v2

## Auditoría del modelo anterior

Las rutas existentes en `PROGRESS_ROUTES` son definiciones editoriales estáticas incluidas en `index.html`. Contienen identificador, sigla, nombre, estado editorial, enlace y emblema opcionales, recompensa de avatar opcional y requisitos de sala expresados históricamente como nombre, empresa y alias. `progressRoutes()` cruza esos requisitos con las salas personales hechas y calcula el trofeo. No existe persistencia de una instancia de ruta, ámbito de grupo, fecha, orden editable ni descripción propia.

`profiles/{uid}/featuredRoutes` solo contiene los IDs de hasta tres trofeos oficiales ya completados que el usuario decide mostrar. Las rutas oficiales no aportan XP directamente. Algunas desbloquean un avatar, y su finalización puede aparecer en la vitrina y en los datos públicos ya derivados de las reviews.

## Modelo persistente propuesto

Se separan las dos fronteras de autorización para evitar un índice adicional y operaciones multipath innecesarias:

```text
userRoutes/{uid}/{routeId}
groupRoutes/{groupId}/{routeId}
```

Cada registro contiene:

```json
{
  "name": "Vitoria 2027",
  "description": "",
  "scope": "personal",
  "ownerUid": "uid",
  "roomIds": ["id-canonico-a", "id-canonico-b"],
  "createdAt": 1789320000000,
  "updatedAt": 1789320000000,
  "plannedDate": 1807401600000,
  "status": "active",
  "schemaVersion": 1,
  "officialRouteId": "pain-route-3"
}
```

`groupId` se añade y debe coincidir con la rama cuando el ámbito es grupal. `plannedDate` y `officialRouteId` son opcionales. El límite inicial es 20 salas. Nombre, empresa, portada, ubicación, ranking, coordenadas y duración se obtienen del catálogo; miembros y autoridad se obtienen de los índices actuales del grupo.

No se persisten `done`, `pending`, contador, porcentaje ni fase. Se calculan al renderizar desde `users/{uid}/roomStates` para rutas personales y desde `groupRooms`/`groupPendingRooms` para rutas grupales, pasando por la identidad de `room-state.js`. Una sala retirada del catálogo conserva su ID y aparece como no disponible sin perder la ruta.

## Permisos propuestos

- Ruta personal: solo `auth.uid === uid` puede leer, crear, editar o eliminar.
- Ruta grupal: cualquier miembro activo puede leer; solo el propietario activo del grupo puede crear, editar o eliminar. `groups/{groupId}` no se puede eliminar mientras exista `groupRoutes/{groupId}`. Así, un cliente v46 no puede dejar rutas huérfanas. El flujo v47 elimina primero las rutas y solo después los metadatos y ramas auxiliares; si falla el borrado de metadatos, restaura los payloads de ruta leídos antes de comenzar.
- Ruta oficial: permanece en código versionado y es de lectura pública con el sitio. Los usuarios no pueden modificar su definición. “Registrar esta ruta” crea una instancia personal o grupal que referencia `officialRouteId` y copia únicamente la secuencia de IDs canónicos.

Las reglas propuestas viven solo en `database.rules.json` y deben permanecer sin desplegar hasta aprobación. No requieren migración: no existen ramas antiguas de rutas guardadas. `PROGRESS_ROUTES` y `featuredRoutes` siguen funcionando durante la transición.

Antes de cada alta se resuelve cada identificador con la identidad compartida de `room-state.js` y se persiste el `id` exacto de la única ficha coincidente del catálogo. Las reglas verifican además el formato léxico usado por todos los IDs actuales (`[a-z0-9][a-z0-9_-]*`), el máximo de 20 posiciones y los tipos/timestamps. Una sala retirada ya guardada conserva su ID al editar otros datos y se presenta como “No disponible”.

La resolución local exige una única coincidencia por nombre histórico, empresa y alias ya declarado. Ocho de las diez definiciones actuales pueden registrarse. `movie-route` mantiene pendiente la confirmación editorial de “Room Angie 2” y `panic-tour` la de “IN”; ambas siguen visibles y calculando su trofeo histórico, pero llevan un bloqueo editorial explícito que impide “Registrar esta ruta” aunque una versión concreta del catálogo llegue a producir una sola coincidencia. No se deduce ni se desbloquea una sala solo por similitud o por cambios accidentales en el conjunto de candidatos.

Los candidatos exactos pendientes de decisión editorial son:

- “Room Angie 2”: `roomangie-2` y `room-angie`, ambas de Ilusium Room Escape en Mataró (Barcelona).
- “IN”: `in-barcelona` de Fear Factory Experience en L'Hospitalet de Llobregat (Barcelona), e `in` de Fear Factory Experiences sin ubicación informada.

## Evolución de XP y logros

El modelo expone `officialRouteId` y progreso derivado, suficientes para detectar el paso a 100 %. No se concede XP, crédito, sello ni logro nuevo en esta fase. Una futura recompensa deberá definirse en la ruta oficial editorial, ser idempotente y derivarse del estado real; no debe guardarse como un contador mutable dentro de la instancia.
