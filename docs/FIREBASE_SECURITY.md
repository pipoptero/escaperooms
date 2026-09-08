# Seguridad de Firebase

Esta web usa Firebase Realtime Database directamente desde el navegador. La clave web de Firebase identifica el proyecto, pero la protección real depende de Authentication y de las reglas de la base de datos.

## Revisión antes de publicar

- Denegar por defecto cualquier rama que no aparezca expresamente en las reglas.
- Limitar `users/{uid}` al usuario autenticado con `auth.uid === $uid`.
- Permitir votos y favoritos solo en el nodo del propio UID y validar tipo y rango.
- Reservar borradores y publicaciones administrativas a los UID presentes en `admins/{uid}`.
- Validar tamaño y forma de perfiles, reviews, invitaciones y nombres de grupo.
- Revisar que ninguna rama privada tenga `.read: true`.
- Activar alertas de presupuesto y revisar el uso anómalo en Firebase Console.
- Activar App Check para la aplicación web después de verificar dominio y flujo de acceso.
- Probar las reglas en Firebase Emulator Suite antes de publicarlas.

## Comprobación trimestral

1. Exportar una copia de seguridad de Realtime Database.
2. Revisar usuarios administradores y retirar accesos antiguos.
3. Ejecutar pruebas de lectura y escritura como invitado, usuario A, usuario B y administrador.
4. Confirmar que un usuario no puede leer ni modificar el perfil, grupos o progreso de otro.
5. Revisar dominios autorizados de Authentication y eliminar entornos obsoletos.

No se incluyen reglas desplegables en este repositorio porque deben mantenerse sincronizadas con todas las ramas reales de la base de datos. Las reglas orientativas de `README.md` no sustituyen una exportación verificada desde Firebase Console.
