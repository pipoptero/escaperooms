# Endurecimiento de Firebase sin interrumpir producción

Estado: preparado y probado localmente; `database.rules.json` **no está desplegado**. GitHub Pages tampoco despliega reglas de Realtime Database.

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

## Orden de despliegue obligatorio

1. Publicar primero el cliente compatible y comprobar creación/aceptación/eliminación con un grupo de prueba.
2. Confirmar que no quedan navegadores/PWA críticos usando una versión anterior. Este bloque prepara service worker v43 y assets `20260910-firebase-groups-v2` para renovar la shell.
3. Desplegar `database.rules.json` por separado con `firebase deploy --only database`, nunca desde el workflow de Pages.
4. Repetir smoke autenticado con propietario, invitado, miembro y usuario ajeno.
5. Mantener una copia exportada de las reglas anteriores para rollback inmediato.

No invertir los pasos 1 y 3: el cliente antiguo no incluye `inviteId` en el alta de miembros y las reglas nuevas rechazarían esa aceptación.

## Pruebas locales

Se usa un proyecto `demo-the-vault`, sin recursos reales. Firebase garantiza que los intentos de acceder a servicios no emulados fallan.

```powershell
npm ci
npm run test:firebase-rules
```

La suite comprueba permisos positivos y negativos, invitaciones caducadas/de un solo uso, bloqueo de escalada de rol, PATCH de alias y eliminación integral. CI instala Java 21 y ejecuta la misma suite.

## Migración de datos posterior

La limpieza legacy debe ser otra fase: backup, plan dry-run, revisión de conflictos, aplicación por usuario/grupo y auditoría posterior. Regla de consolidación propuesta: estado explícito más reciente por `updatedAt`; si empatan o no hay fecha, prevalece `done`. No sobrescribir la raíz completa ni mezclar esta migración con el despliegue de reglas.
