# Pendientes, identidad y compatibilidad de estados — 2026-09-09

## Diagnóstico

El botón principal de pendiente guardaba directamente en la lista personal. Los controles de grupo existían dentro de la ficha, pero no formaban parte de esa elección. Las listas compartidas ya estaban modeladas: no se necesita copiar pendientes a cada cuenta.

Se verificó `/users` mediante una lectura de Firebase, sin escrituras. En las ocho cuentas con estados guardados había cinco con identidades duplicadas (diez duplicidades), incluyendo cuatro pares contradictorios hecho/pendiente: dos Parasomnia, uno Highschool y uno Exorcista. Son cuentas con `roomStates`, no el censo total de Firebase Authentication. La copia permanece en `private/firebase_backups/users-consistency-20260909-185533.json`, ignorada por Git.

En Parasomnia coexistían `parasomnia_bajo_segunda` pendiente antiguo y `parasomnia_bajo_2` hecho posterior. Faltaba el primer alias; además las escrituras solo cambiaban la clave del nombre vigente. No era un problema de caché ni exclusivo de una sala. La copia antigua `users-panel-test.json` tenía tres casos Parasomnia; el diagnóstico vigente usa la lectura nueva (dos).

## Modelo e invariantes

- Personal: `users/{uid}/roomStates/{key}` con `pending`, `done`, tiempo opcional y metadatos. El último estado explícito por `updatedAt` prevalece; si no hay fecha o empatan, prevalece hecho. No sumar recompensas por cada alias.
- Grupo: `groupRooms/{groupId}/{key}` y `groupPendingRooms/{groupId}/{key}`. En el mismo grupo, hecho excluye pendiente. Otro grupo o la lista personal pueden tener un estado diferente.
- `room-state.js` aplica alias explícitos de `room_aliases.json`, conserva claves originales para la limpieza y no muta el snapshot leído. No fusiona dos claves distintas solo por tener el mismo título; un renombre sin alias conocido requiere revisión.
- `scopeRoomKey()` es la identidad de estas listas. No se ha cambiado el modelo de votos/reviews ni introducido una migración global a IDs nuevos.
- La normalización de lectura no escribe en Firebase. Toda cuenta que cargue la app corregida obtiene listas coherentes aunque conserve datos antiguos.
- Las acciones de usuario vuelven a leer su ámbito, construyen un PATCH disperso con todas sus claves equivalentes y lo envían en una única petición. La memoria de la app se actualiza después de confirmar el guardado. No se borra ningún otro grupo/usuario.
- Quitar un pendiente desde una vista antigua conserva un hecho que otro miembro haya registrado antes de esa lectura. Añadir pendiente se rechaza si la lectura nueva ya lo muestra hecho. Una escritura simultánea posterior a la lectura sigue usando la semántica de última escritura de RTDB: no se ha implantado un sistema de transacciones/compare-and-swap.
- Un fallo de carga de grupos conserva la última vista válida y no borra membresías por confundir un error de red con una expulsión.

## UX y propagación

«Pendiente…» / «Gestionar pendiente» abre «¿Con quién quieres hacerlo?»: Solo para mí y cada grupo activo, con su estado y opción de añadir/quitar. Un destino ya realizado se muestra deshabilitado. Cada acción modifica solo la lista elegida; se puede guardar también en otra repitiendo la elección.

Todos los miembros leen el mismo registro del grupo. Se refrescan listas al entrar en Pendientes y al recuperar foco en esa pestaña, además del refresco existente de la app. No hay duplicación por miembro ni polling continuo. Los tags indican Tu pendiente / Pendiente con el nombre del grupo.

## Migración y operación

No se ejecutó limpieza masiva ni escritura en Firebase. No es necesaria una migración previa para corregir la visualización: lectura compatible y consolidación al editar. La copia original permite revisar/restaurar registros si alguna vez se planifica una limpieza explícita.

Auditoría agregada y solo de lectura, desde la raíz de la web:

```powershell
node scripts/audit_room_states.cjs private/firebase_backups/users-consistency-20260909-185533.json
```

El script no imprime UID, nombres de usuarios ni correos. No publica la copia de entrada. La cifra puede cambiar con datos nuevos.

Al validar el despliegue, comprobar con una cuenta real los permisos de RTDB para PATCH multipath. Las pruebas automatizadas simulan la base de datos; no se han cambiado reglas ni escrito con cuentas reales durante la implementación.

## Portadas y modal

Cinco originales JFIF copiados a `images/catalgo_propio_web_escape/optimizads con IA/`, con overrides explícitos a `olimpo`, `space-base-extermination`, `tu-tambien-sonaras`, `enterprises`, `katrina`. Se añadió `.jfif` al planificador local ignorado. El plan tenía exactamente cinco cambios antes de aplicar. JPEG publicados de 900×1350, sin recorte; Tú También Soñarás sustituye su WebP anterior. Se regeneraron las cinco páginas SEO afectadas, conservando la fecha del snapshot de contenido y las tarjetas sociales ajenas a este encargo.

El cierre de la ficha pasa a una carcasa estacionaria fuera del contenedor desplazable. Se reservan safe areas, objetivo táctil de 44 px y espacio superior; se contempla `visualViewport`, altura dinámica y orientación. Se reinicia scroll al abrir una ficha, se conserva al actualizarla y se devuelve foco al cerrar; Escape y ciclo Tab funcionan sin cerrar la ficha detrás del selector. Se detienen vídeos/iframes al cerrar. Service worker v41 y artifact de Pages incluyen el módulo nuevo, también disponible offline desde la caché.

## Pruebas

```powershell
python -B -m unittest discover -s tests -v
node --test tests/room_state.test.cjs
pip install -r tests/browser/requirements.txt
python -m playwright install chromium webkit
python -B -m unittest discover -s tests/browser -v
$env:VAULT_TEST_BROWSER = 'webkit'
python -B -m unittest discover -s tests/browser -v
```

La suite de navegador bloquea tráfico externo, usa configuración ficticia y simula Firebase compartido entre dos usuarios. Cubre selección de ámbito, visibilidad para otro miembro, aislamiento personal, alias, escritura rechazada, limpieza atómica, edición personal, vista desactualizada, cierre táctil en varios tamaños/orientación y ratón/foco en escritorio. CI incluye Chromium y WebKit. La interacción táctil usa coordenadas con comprobación previa de hit testing, sin clicks forzados a través de capas.

Resultados finales del 9 de septiembre de 2026:

- `node --test tests/room_state.test.cjs`: 9/9 casos correctos.
- `python -B -m unittest discover -s tests -v`: 11/11 pruebas correctas; incluye la ejecución del modelo Node.
- Suite de navegador: 7/7 en Chromium y 7/7 en WebKit.
- Sintaxis: `room-state.js`, `service-worker.js` y el script principal de `index.html` correctos con `node --check`.
- Validador público: 0 errores y 4 avisos editoriales ya existentes (348 sinopsis cortas/ausentes, 74 vídeos sin fecha, 66 sin miniatura y 1 review sin texto publicable).
- Las cinco portadas y sus referencias de catálogo/SEO se comprobaron; todos los JPEG son 900×1350.

## Vista local

El servidor de comprobación debe publicar directamente la raíz `escaperooms-work`. En la última validación `http://127.0.0.1:8769/` servía esta versión y `index.html`, `data.json`, `catalog.json`, `room-state.js`, `room_aliases.json` y `service-worker.js` respondían 200. Chromium completó una carga real con la app visible, la pantalla de error oculta y 1.728 salas. Si vuelve a aparecer «Error al cargar datos», comprobar primero que el servidor siga vivo y reiniciarlo desde esa carpeta:

```powershell
cd C:\Users\Isaac\Documents\SCAPEROOMS\escaperooms-work
python -m http.server 8769 --bind 127.0.0.1
```

Una pestaña que permanecía abierta cuando el servidor estaba detenido puede mostrar una shell antigua del service worker. Tras arrancarlo, hacer una recarga forzada; un puerto nuevo permite comprobar sin la caché de ese origen.

Queda la comprobación en hardware móvil/PWA y con permisos reales antes del despliegue. No se ha auditado toda la seguridad de Firebase ni inferido automáticamente alias de salas homónimas.
