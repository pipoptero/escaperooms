# Endurecimiento de Firebase sin interrumpir producción

Estado: `database.rules.json` desplegado el **10 de septiembre de 2026** después de publicar el cliente compatible v43. GitHub Pages no despliega reglas de Realtime Database; el despliegue se hizo por separado con Firebase CLI.

La exportación privada anterior al cambio es `private/firebase_backups/database-rules-live-20260910-095047.json`, SHA-256 `20C35BC0DE6579B61A79DC9D836531D87A68FF170CEA45332DBB4F58BF3AFBD0`. La relectura posterior coincidió semánticamente con este archivo versionado. Las lecturas públicas de votos y reviews respondieron 200; raíz, perfiles e invitaciones sin autenticar respondieron 401.

## Diagnóstico de solo lectura — 10 de septiembre de 2026

- 502 estados personales en 8 nodos de usuario.
- 10 identidades canónicas duplicadas y 4 contradicciones hecho/pendiente: Bajo Segundo, Highschool y Sección Esotérica: Exorcista.
- 58 estados de grupo: 2 identidades duplicadas y 1 solapamiento hecho/pendiente, Bajo Segundo.
- 4 grupos y 9 relaciones de pertenencia. `groupMembers` y `userGroups` coinciden; no hay grupos sin metadatos.
- No hay registros con ambos flags personales a `true`, estados vacíos ni timestamps ausentes.

La lectura compatible de `room-state.js` mantiene la interfaz coherente. No se necesita limpiar Firebase para desplegar las mejoras de autorización.

## Riesgos corregidos por las reglas candidatas

- Un usuario autenticado ya no puede añadirse a un grupo sin una invitación pendiente y vigente.
- Un miembro no puede convertir su propio rol en propietario.
- Un usuario ajeno no puede leer el grupo ni modificar sus salas.
- El perfil completo, que actualmente contiene email, solo puede leerlo su propietario; la identidad social ya se replica en miembros y reviews.
- El propietario puede eliminar en una sola actualización el grupo, miembros, estados e índices de todos los miembros.
- Estados personales y de grupo validan su forma mínima y límites básicos.
- Las ramas no declaradas quedan denegadas por defecto.

## Cambios de cliente compatibles con las reglas actuales

- Crear un grupo guarda metadatos, miembro propietario e índice inverso en un único PATCH; un fallo no deja nodos incompletos.
- Aceptar una invitación usa un único PATCH que añade `groupMembers`, `userGroups` y marca el token como aceptado. El miembro conserva `inviteId` como prueba de entrada.
- Eliminar un grupo intenta un único PATCH para borrar todos sus nodos e índices. Mientras sigan las reglas antiguas, un 403 activa un segundo PATCH compatible que conserva únicamente los índices ajenos, igual que hacía el flujo anterior. Con las reglas nuevas no se usa ese fallback.
- Marcar hecho/pendiente y consolidar alias ya usaba PATCH multipath.

## Orden seguido en el despliegue

1. Se publicó primero el cliente compatible y se comprobó creación/aceptación/eliminación con Firebase simulado.
2. Service worker v43 y assets `20260910-firebase-groups-v2` renovaron la shell; producción se verificó antes de continuar.
3. Se exportaron y validaron las reglas anteriores para rollback.
4. Se auditaron de solo lectura las ramas vivas: todos los grupos, miembros, índices, salas e invitaciones cumplen la forma candidata.
5. Se validó el despliegue con `--dry-run` y se desplegó `database.rules.json` por separado con `firebase deploy --only database`.
6. Se releyeron las reglas activas y se comprobó que coinciden con el archivo versionado.

No restaurar un cliente anterior a v42 mientras estas reglas estén activas: aquel cliente no incluye `inviteId` en el alta de miembros y la aceptación sería rechazada.

## Pruebas locales

Se usa un proyecto `demo-the-vault`, sin recursos reales. Firebase garantiza que los intentos de acceder a servicios no emulados fallan.

```powershell
npm ci
npm run test:firebase-rules
```

La suite comprueba permisos positivos y negativos, invitaciones caducadas/de un solo uso, bloqueo de escalada de rol, PATCH de alias y eliminación integral. CI instala Java 21 y ejecuta la misma suite.

## Migración de datos posterior

La limpieza legacy debe ser otra fase: backup, plan dry-run, revisión de conflictos, aplicación por usuario/grupo y auditoría posterior. Regla de consolidación propuesta: estado explícito más reciente por `updatedAt`; si empatan o no hay fecha, prevalece `done`. No sobrescribir la raíz completa ni mezclar esta migración con el despliegue de reglas.
