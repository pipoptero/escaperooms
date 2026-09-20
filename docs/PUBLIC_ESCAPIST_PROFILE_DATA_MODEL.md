# Perfil escapista público / compartible

Estado: MVP con cliente autenticado implementado y validado solo en local. Estas ramas y reglas no están desplegadas.

## Contrato del MVP

- URL: `https://thevaultescape.com/escapista/?u=username`.
- El perfil es privado por defecto y `indexable` permanece en `false`.
- Un visitante solo solicita `publicProfiles/{username}/view`.
- La respuesta pública no contiene UID, email, datos Auth, invitaciones, IDs de grupo ni estados privados.
- Un bloque desactivado se elimina de la proyección; no se oculta mediante CSS.
- Perfil inexistente, privado, retirado o eliminado recibe la misma respuesta: “Este perfil no está disponible.”
- URL limpia, HTML y Open Graph individuales e indexación opt-in quedan para una fase con prerender o servidor.

## Fuentes y límites

`profiles/{uid}` sigue privado y sin cambios. Como el cliente actual guarda esa rama completa, los controles públicos viven fuera para conservar compatibilidad.

La proyección usa nombre público confirmado; avatar, marco y título equipados; XP existente; estados personales explícitos de `progressPersonalDoneRooms()`; logros reales filtrados; rutas guardadas personales y rutas oficiales personales; y, si se autoriza, solo el número de grupos.

`groupRooms` y `groupPendingRooms` no cuentan como historial personal. Las rutas grupales no se publican. No existe un modelo real de auras ni rareza de logros.

## Árbol Firebase propuesto

```text
profiles/{uid}                         # privado existente
publicProfileControls/{uid}            # preferencias privadas
publicProfileOwners/{username}          # reserva/ownership privado
publicProfiles/{username}/view          # única lectura anónima
```

No hay `.read` en `publicProfiles/{username}` ni en sus padres. El UID solo aparece en `publicProfileOwners`, inaccesible para un visitante.

### Control privado

```json
{
  "schemaVersion": 1,
  "published": false,
  "indexable": false,
  "currentUsername": "",
  "pendingUsername": "isaac",
  "previousUsername": "",
  "visibility": {
    "showAvatar": false,
    "showProgress": false,
    "showStats": false,
    "showMap": false,
    "showAchievements": false,
    "showRoutes": false,
    "showRoutesInProgress": false,
    "showGroups": false
  },
  "updatedAt": 1789500000000
}
```

Solo su propietario lo puede leer y escribir. `indexable` está forzado a `false`.

### Reserva privada

```json
{
  "ownerUid": "UID_PRIVADO",
  "state": "reserved",
  "createdAt": 1789500000000,
  "updatedAt": 1789500000000
}
```

Estados: `reserved`, `active` y `retired`. La creación requiere que el control del mismo usuario contenga ese `pendingUsername`. Dos usuarios no pueden crear la misma ruta; `ownerUid` y `createdAt` quedan inmutables.

### Proyección pública mínima

```json
{
  "schemaVersion": 1,
  "published": true,
  "indexable": false,
  "username": "isaac",
  "displayName": "Isaac",
  "visibility": {
    "showAvatar": true,
    "showProgress": true,
    "showStats": true,
    "showMap": true,
    "showAchievements": true,
    "showRoutes": true,
    "showRoutesInProgress": true,
    "showGroups": true
  },
  "appearance": {
    "avatarId": "avatar_vault",
    "avatarImage": "/images/brand/icon-round-192.png",
    "frameId": "gold",
    "titleId": "title_legend"
  },
  "xp": 1865,
  "stats": {
    "personalEscapes": 127,
    "cities": 28,
    "zones": 9,
    "terror": 54,
    "nonTerror": 68,
    "unclassifiedTerror": 5,
    "routesCompleted": 12,
    "reviews": 34,
    "awardedRooms": 41
  },
  "map": { "count": 3, "roomIds": ["olimpo", "katrina", "enterprises"] },
  "achievements": {
    "count": 4,
    "unlocked": ["first_escape", "enthusiast", "veteran", "centurion"],
    "featured": ["centurion", "veteran"]
  },
  "routes": {
    "completedCount": 2,
    "official": [
      { "id": "achoporte", "completed": 4, "target": 4, "state": "completed", "missingRooms": 0 }
    ],
    "personal": [
      { "name": "Ruta con retirada", "completed": 2, "target": 4, "state": "degraded", "missingRooms": 1 }
    ]
  },
  "groupCount": 3,
  "updatedAt": 1789500000000
}
```

Las definiciones, textos e iconos siguen en recursos estáticos. Firebase solo recibe IDs y resúmenes necesarios.

## Privacidad por bloque

| Opción | Campo cuando está activa | Fuente |
| --- | --- | --- |
| Avatar | `appearance` | equipamiento permitido |
| Nivel / XP | `xp` | XP existente |
| Estadísticas | `stats` | hechos personales explícitos |
| Mapa | `map.roomIds` | hechos personales explícitos |
| Logros | `achievements` | logros reales filtrados |
| Rutas | `routes` | rutas personales y oficiales personales |
| En progreso | filtra `routes` | preferencia dependiente de rutas |
| Grupos | `groupCount` | cantidad, nunca identidad |

Las coordenadas no se copian a Firebase. La página cruza IDs públicos con el catálogo estático y solo dibuja puntos con coordenadas de confianza suficiente.

## Username

La normalización aplica NFKD, elimina diacríticos, recorta, convierte a minúsculas, cambia espacios y guiones bajos por guiones y colapsa repeticiones. Admite 3–30 caracteres y `^[a-z0-9]+(?:-[a-z0-9]+)*$`.

Cliente y reglas bloquean nombres técnicos, de aplicación, autenticación, Firebase, soporte y sistema, además del prefijo `codex-smoke-`. `Isaac`, `ISAAC` e `isaac` convergen en una reserva.

## Publicación y retirada

`public-profile-firebase.js` es el único orquestador de escrituras. La interfaz privada no conserva configuración en `localStorage`; carga `publicProfileControls/{uid}` y todas las publicaciones pasan por el constructor central `buildPublicProfileProjection`.

Primera publicación:

1. guardar controles privados con `published=false` y `pendingUsername`;
2. crear la reserva `reserved`;
3. escribir una `view` saneada, todavía oculta;
4. activar la reserva;
5. establecer `currentUsername` y `published=true`.

La lectura anónima exige a la vez: `view.published=true`, owner `active`, control `published=true`, `currentUsername` igual al solicitado y coincidencia exacta de los ocho flags de visibilidad entre control y proyección. Al ocultar una sección se actualiza primero el control: la vista anterior queda inmediatamente ilegible y solo vuelve a ser pública cuando la nueva proyección ya omite el bloque.

Para retirar, primero se pone `published=false`, lo que corta la lectura. Después se elimina `view`. Un fallo de limpieza deja datos inaccesibles y el reintento es idempotente.

## Cambio de username

1. guardar el nuevo `pendingUsername`;
2. reservar el nuevo owner con creación exclusiva;
3. preparar la nueva `view` oculta;
4. activar la nueva reserva;
5. conmutar una vez `currentUsername`;
6. borrar la vista antigua;
7. retirar la reserva antigua;
8. limpiar pending/previous.

El paso 5 hace que antes solo se lea la URL antigua y después solo la nueva. Si el cliente se corta antes, conserva la antigua; si se corta después, la antigua puede quedar almacenada pero no legible. RTDB no ofrece una transacción cliente condicional y multirrama para todo el flujo: es recuperable e idempotente, no una promesa de atomicidad global.

Los usernames retirados permanecen vinculados a su propietario. El MVP no los libera ni crea redirects.

## Recuperación de fallos e idempotencia

Cada paso puede repetirse sin adjudicar el username a otro usuario ni abrir dos URLs simultáneamente:

- Antes de activar el owner, una proyección preparada no es legible.
- Antes de activar el control final, la primera publicación sigue privada.
- Tras conmutar un rename, la URL anterior deja de ser legible aunque su limpieza quede pendiente.
- `pendingUsername` y `previousUsername` permiten terminar un rename interrumpido.
- Al despublicar se corta primero la lectura y se borra la vista después.
- Un username configurado con `published=false` queda reservado sin crear `view`.
- Las reservas antiguas pasan a `retired` y no se reciclan automáticamente.

El cliente reintenta desde el estado persistido. Un conflicto de reserva devuelve `USERNAME_TAKEN`; no sustituye la reserva existente. La aplicación no intenta una compensación que libere usernames porque una liberación automática tras un timeout abriría una carrera de apropiación.

## Refresco y límites

Una proyección publicada se regenera al cambiar perfil/cosméticos, estados personales, reseñas y rutas personales, y también durante el refresco completo de sesión. Los cambios grupales no añaden historial personal. Si un refresco falla, la última proyección coherente permanece; el siguiente cambio o refresco vuelve a intentarlo.

Los límites son explícitos y producen error visible, nunca truncado silencioso:

| Colección | Máximo |
| --- | ---: |
| salas del mapa | 500 |
| logros | 50 |
| logros destacados | 3 |
| rutas oficiales | 30 |
| rutas personales | 30 |

El esquema RTDB aplica los mismos máximos estructurales. Cualquier crecimiento futuro requiere ampliar constructor, reglas y pruebas conjuntamente.

## Reglas locales

`database.rules.json` propone ownership privado, reserva única, esquema cerrado, lectura solo en `/view`, correspondencia estricta entre toggles y bloques, límites de payload, IDs seguros y hosts permitidos para avatar. Una vista exige `published=true` e `indexable=false`.

Las reglas validan forma y privacidad, pero no pueden demostrar que el progreso autopublicado coincide con ramas privadas sin acoplar la proyección a ellas. El cliente genera la vista desde las fuentes correctas.

## Página, compartir y SEO

`/escapista/` implementa loading, público, respuesta neutral, username inválido y error recuperable. Crea DOM seguro con `textContent`. Compartir ofrece Web Share, copia con fallback, WhatsApp y tarjeta 1080×1350, siempre limitada a campos presentes.

El shell incluye `noindex,nofollow,noarchive,nosnippet`. GitHub Pages entrega el mismo HTML para todos los query parameters y no puede generar canonical u Open Graph individual. El futuro podrá usar `/escapista/username` con prerender individual e indexación opt-in.

## Compatibilidad y despliegue futuro

PWA v47 ignora las ramas nuevas. El código local usa v48. Este sprint no escribe Firebase, no cambia Authentication y no despliega servicios.

Despliegue controlado propuesto, pendiente de autorización:

1. Exportar y hashear las reglas RTDB de producción; conservar backup privado de rollback.
2. Confirmar PWA v47, ramas públicas inexistentes o inventariadas y CI verde.
3. Desplegar únicamente las reglas RTDB aditivas. Verificar export remoto contra `database.rules.json`.
4. Ejecutar smoke temporal con propietario, segundo usuario y visitante: carrera de username, publicación completa, ocultación de cada bloque, rename, retirada, ataques cruzados y ausencia de UID/email.
5. Si el smoke de reglas pasa, publicar PWA v48 por GitHub Pages y esperar CI/Pages.
6. Verificar navegador real, service worker v48, perfil privado por defecto, compartir y respuesta neutral.
7. Limpiar cuentas/rutas temporales y comprobar que no queda ningún prefijo de smoke.

Rollback:

- Si fallan reglas o smoke previo a Pages, restaurar el backup de reglas y no publicar v48.
- Si falla el cliente después de Pages y las reglas son compatibles, restaurar Pages a v47; las ramas nuevas permanecen privadas e ignoradas.
- Si se detecta exposición, poner `published=false` en los controles temporales del smoke, retirar vistas temporales, restaurar las reglas anteriores y comprobar lectura anónima denegada antes de continuar.

El smoke de producción deberá usar cuentas y usernames temporales inequívocos, sin historiales reales, y no tocar `profiles`, grupos, rutas o estados de usuarios existentes.
