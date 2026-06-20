# The Vault - Escape Room Chronicles

Web estática para registrar, consultar y valorar escape rooms: los que el grupo ya ha jugado, los pendientes y un catálogo amplio de salas para descubrir nuevas experiencias.

El proyecto está pensado para funcionar en GitHub Pages. La parte del grupo se actualiza desde un Excel, mientras que el catálogo general, las imágenes y los premios se guardan en archivos JSON e imágenes locales.

## Qué Incluye

- Catálogo general de escape rooms con imágenes, ubicación, precio, jugadores, dificultad, terror, descripción y estado.
- Lista de pendientes del grupo, generada desde el Excel.
- Reviews del grupo, también desde el Excel, con puntuación, reseña y valoración por categorías.
- Ranking del grupo basado en las salas jugadas y puntuadas.
- Login con Google mediante Firebase Auth.
- Listas personales por usuario: mis pendientes, mis hechos y favoritos.
- Favoritos con corazón directamente desde el catálogo.
- Votaciones y likes sincronizados con Firebase Realtime Database.
- Popup de detalle de cada sala con portada, sinopsis, datos técnicos, premios y acciones personales.
- Recomendador flotante para buscar salas por ciudad/provincia, estilo, jugadores, dificultad y estado.
- Badges de premios para TERPECA, 10Escapes, Escape Room Awards y Giba Awards.
- GitHub Action para regenerar `data.json` automáticamente cuando se sube el Excel.

## Captura Mental del Flujo

```text
Excel del grupo
  -> convert.py
  -> data.json
  -> Pendientes, Reviews y Ranking grupo

Catálogo externo
  -> scripts/build_catalog.py
  -> catalog.json
  -> Catálogo general

Premios
  -> scripts/build_terpeca_awards.py
  -> terpeca_awards.json

Premios extra
  -> scripts/build_extra_awards.py
  -> extra_awards.json

Firebase
  -> login Google
  -> votos, likes y estados personales por usuario
```

## Estructura del Proyecto

```text
.
├── index.html
├── data.json
├── catalog.json
├── terpeca_awards.json
├── extra_awards.json
├── escape_rooms_tracker_mejorado.xlsx
├── convert.py
├── images/
│   ├── ec-all/
│   └── awards/
│       ├── 10escapes-logo.png
│       ├── escape-room-awards-logo.png
│       └── giba-awards-logo.svg
├── scripts/
│   ├── build_catalog.py
│   ├── build_terpeca_awards.py
│   ├── build_extra_awards.py
│   ├── download_escape_collector_catalog.py
│   └── download_images.py
└── .github/
    └── workflows/
        └── update-data.yml
```

## Archivos Principales

### `index.html`

Contiene toda la aplicación: interfaz, estilos, carga de JSON, filtros, popup, login, Firebase, recomendador y renderizado de tarjetas.

Es una web estática, así que puede publicarse directamente en GitHub Pages sin servidor backend.

### `escape_rooms_tracker_mejorado.xlsx`

Excel principal del grupo. Es la fuente de datos para:

- Pendientes del grupo.
- Reviews del grupo.
- Ranking del grupo.
- Estadísticas superiores: hechos, pendientes, total, media y horas jugadas.

Cuando se sube una nueva versión del Excel a GitHub, la Action ejecuta `convert.py` y actualiza `data.json`.

### `data.json`

Archivo generado desde el Excel. Lo consume la web para mostrar los datos propios del grupo.

No se edita manualmente salvo casos puntuales.

### `catalog.json`

Catálogo general de salas. Contiene datos amplios de escape rooms: nombre, empresa, ciudad, provincia, comunidad autónoma, país, duración, jugadores, precio, dificultad, rating, votos, terror, web, descripción e imagen.

Este archivo alimenta la pestaña `Catálogo`.

### `terpeca_awards.json`

Datos de premios TERPECA normalizados para poder cruzarlos con el catálogo.

### `extra_awards.json`

Datos de premios adicionales:

- 10Escapes.
- Escape Room Awards.
- Giba Awards.

La web cruza estos premios con las salas del catálogo y muestra los badges correspondientes.

## Vistas de la Web

### Catálogo

Es la vista principal. Muestra salas del catálogo general con:

- Imagen de portada.
- Nombre y empresa.
- Ciudad y provincia.
- Dificultad.
- Terror.
- Precio.
- Duración.
- Jugadores.
- Resumen de sinopsis.
- Rating externo.
- Botón de favorito.
- Acciones personales si el usuario está logado.
- Badges de premios.

La carga inicial muestra un bloque limitado de salas y permite ampliar con el botón `Mostrar más`.

### Mis Pendientes / Pendientes Grupo

Sin login se muestra la lista de pendientes del grupo.

Con login, la pestaña pasa a mostrar los pendientes personales del usuario. Esto permite que cada persona tenga su propia lista sin modificar los datos del grupo.

### Mis Hechos

Solo aparece con login. Permite ver las salas que el usuario ha marcado como hechas.

Importante: marcar una sala como `Hecho por mí` no la mete en las reviews del grupo. Las reviews del grupo solo salen del Excel.

### Reviews

Muestra las salas jugadas por el grupo y sus reseñas.

Incluye:

- Valoración del grupo.
- Review personal del grupo.
- Datos de sala.
- Valoraciones por categoría si existen en el Excel.
- Acceso al popup de detalle.

### Ranking Grupo

Ranking basado en las salas jugadas por el grupo. Está pensado como escaparate de nuestras opiniones, no como ranking personal de cada usuario.

Al clicar una sala se abre el popup con detalle, imagen, datos técnicos y review del grupo.

## Popup de Detalle

El popup de sala reúne la información más completa:

- Portada.
- Nombre y empresa.
- Ubicación.
- Duración.
- Jugadores.
- Precio.
- Dificultad.
- Terror.
- Estado.
- Sinopsis completa.
- Premios detectados.
- Review del grupo, si existe.
- Acciones personales del usuario logado.

## Premios y Badges

La web muestra badges de premios sobre la imagen de la tarjeta y como tags en el detalle.

Premios soportados:

- TERPECA.
- 10Escapes.
- Escape Room Awards.
- Giba Awards.

En tarjetas se muestran hasta 3 badges visibles. Si una sala tiene Giba Awards, la web intenta que al menos uno de los badges visibles sea Giba para que no quede oculto por otros premios.

### Regenerar TERPECA

```bash
python scripts/build_terpeca_awards.py
```

Genera:

```text
terpeca_awards.json
```

### Regenerar 10Escapes, Escape Room Awards y Giba Awards

```bash
python scripts/build_extra_awards.py
```

Genera:

```text
extra_awards.json
```

Fuentes actuales:

- https://10escapes.com/
- https://escaperoomawardsoficial.com/
- https://www.gibaescape.com/proyectos/escape-room-giba-awards

## Imágenes

Las imágenes de salas se guardan localmente en:

```text
images/ec-all/
```

Los logos de premios se guardan en:

```text
images/awards/
```

Si una sala no tiene imagen, la web muestra un fallback visual con la inicial.

## Recomendador

La web incluye un asistente flotante en la esquina inferior izquierda.

Permite recomendar salas filtrando por:

- Ciudad, provincia o comunidad.
- Número de jugadores.
- Estilo: terror, aventura, familiar, investigación, etc.
- Dificultad.
- Estado: disponibles, abiertas o favoritas.

El recomendador no usa IA externa ni envía datos fuera. Trabaja directamente con `catalog.json`, los premios y los estados personales disponibles en el navegador/Firebase.

## Login con Google

El login se hace con Firebase Authentication y proveedor Google.

Cuando el usuario inicia sesión puede guardar:

- Favoritos.
- Mis pendientes.
- Mis hechos.
- Votos personales.

Los datos personales se guardan bajo:

```text
users/{uid}/roomStates/{room}
```

## Firebase

Firebase se usa para:

- Login con Google.
- Likes/favoritos.
- Votos.
- Estados personales por usuario.

### Configuración en `index.html`

En la zona de configuración se encuentran:

```js
const FIREBASE_URL = '...';
const FIREBASE_CONFIG = {
  apiKey: '...',
  authDomain: '...',
  projectId: '...',
  appId: '...',
  databaseURL: FIREBASE_URL
};
```

Para que funcione el login:

1. Crear un proyecto en Firebase.
2. Crear una app web.
3. Activar Authentication con Google.
4. Autorizar `localhost` y el dominio de GitHub Pages.
5. Crear Realtime Database.
6. Publicar reglas de seguridad.

### Reglas Orientativas

```json
{
  "rules": {
    "votes": {
      ".read": true,
      "$room": {
        "$uid": {
          ".write": "auth != null && auth.uid === $uid",
          ".validate": "newData.isNumber() && newData.val() >= 0.5 && newData.val() <= 5"
        }
      }
    },
    "likes": {
      ".read": true,
      "$room": {
        "$uid": {
          ".write": "auth != null && auth.uid === $uid",
          ".validate": "newData.val() === true || !newData.exists()"
        }
      }
    },
    "users": {
      "$uid": {
        ".read": "auth != null && auth.uid === $uid",
        ".write": "auth != null && auth.uid === $uid"
      }
    }
  }
}
```


### Reglas adicionales para grupos escapistas

Para activar perfiles, grupos privados, invitaciones por enlace y salas hechas por grupo, anade tambien estas ramas a las reglas de Firebase Realtime Database. La invitacion simple funciona mediante un enlace con un identificador largo; para email verificado o auditoria completa, el siguiente paso natural seria Firebase Cloud Functions.

```json
{
  "profiles": {
    "$uid": {
      ".read": "auth != null",
      ".write": "auth != null && auth.uid === $uid"
    }
  },
  "groups": {
    "$groupId": {
      ".read": "auth != null && root.child('groupMembers/' + $groupId + '/' + auth.uid + '/status').val() === 'active'",
      ".write": "auth != null && ((!data.exists() && newData.child('ownerUid').val() === auth.uid) || root.child('groupMembers/' + $groupId + '/' + auth.uid + '/role').val() === 'owner')"
    }
  },
  "groupMembers": {
    "$groupId": {
      ".read": "auth != null && root.child('groupMembers/' + $groupId + '/' + auth.uid + '/status').val() === 'active'",
      "$uid": {
        ".write": "auth != null && (auth.uid === $uid || root.child('groupMembers/' + $groupId + '/' + auth.uid + '/role').val() === 'owner')"
      }
    }
  },
  "userGroups": {
    "$uid": {
      ".read": "auth != null && auth.uid === $uid",
      "$groupId": {
        ".write": "auth != null && auth.uid === $uid"
      }
    }
  },
  "groupRooms": {
    "$groupId": {
      ".read": "auth != null && root.child('groupMembers/' + $groupId + '/' + auth.uid + '/status').val() === 'active'",
      "$room": {
        ".write": "auth != null && root.child('groupMembers/' + $groupId + '/' + auth.uid + '/status').val() === 'active'"
      }
    }
  },
  "groupInvites": {
    "$inviteId": {
      ".read": "auth != null",
      ".write": "auth != null"
    }
  }
}
```

## Excel del Grupo

El Excel debe mantener dos bloques principales:

- Pendientes.
- Hechos / Reviews.

Columnas habituales:

```text
Nombre del Escape
Empresa
Ciudad
Provincia
Comunidad
Temática
Tipo
Duración
Dificultad
Valoración
Valoración Grupo
Web
Descripción
Historia
Ambientación
Jugabilidad
GameMaster
Min_personas
Max_personas
Precio
Imagen
```

No todas son obligatorias, pero cuanta más información haya, más rica será la ficha.

## Actualización Normal

Para actualizar las salas del grupo:

1. Editar el Excel.
2. Subirlo al repositorio.
3. GitHub Actions ejecuta `convert.py`.
4. Se genera `data.json`.
5. GitHub Pages sirve la web actualizada.

## GitHub Actions

El workflow está en:

```text
.github/workflows/update-data.yml
```

Se ejecuta al detectar cambios en archivos `.xlsx`.

Hace:

1. Checkout del repositorio.
2. Instalación de dependencias Python.
3. Conversión del Excel a `data.json`.
4. Commit automático si `data.json` cambia.

## Desarrollo Local

Como la web usa `fetch('data.json')`, `fetch('catalog.json')` y otros JSON, no conviene abrir `index.html` directamente como archivo.

Es mejor servir la carpeta por HTTP local:

```bash
python -m http.server 8765
```

Y abrir:

```text
http://localhost:8765/
```

## Scripts Útiles

### Convertir Excel a JSON del grupo

```bash
python convert.py
```

### Regenerar catálogo

```bash
python scripts/build_catalog.py
```

### Descargar/actualizar catálogo desde Escape Collector

```bash
python scripts/download_escape_collector_catalog.py
```

### Descargar imágenes desde CSV

```bash
python scripts/download_images.py image_sources.ec-all.csv
```

### Regenerar TERPECA

```bash
python scripts/build_terpeca_awards.py
```

### Regenerar premios extra

```bash
python scripts/build_extra_awards.py
```

## Publicación en GitHub Pages

1. Subir el repositorio a GitHub.
2. Ir a `Settings -> Pages`.
3. En `Build and deployment`, elegir `Deploy from a branch`.
4. Seleccionar rama `main` y carpeta `/root`.
5. Guardar.

La web quedará disponible en una URL similar a:

```text
https://pipoptero.github.io/escaperooms/
```

## Notas de Diseño

La estética de la web está inspirada en una caja fuerte/archivo de expediciones:

- Fondo oscuro.
- Detalles dorados.
- Título `THE VAULT`.
- Tarjetas con portadas grandes.
- Badges de premios sobre la imagen.
- Interfaz compacta para móvil.

La prioridad de diseño es que el catálogo sea fácil de explorar y que las acciones personales no confundan los datos del grupo.

## Avisos

- Las reviews del grupo solo se modifican desde el Excel.
- Las listas personales dependen del login con Google.
- Los datos de catálogo y premios proceden de fuentes públicas y pueden requerir regeneración periódica.
- Si no hay Firebase configurado, la web sigue funcionando, pero sin sincronización real de usuario.

## Estado Actual

La web está preparada para:

- Uso público como catálogo.
- Uso del grupo como ranking/reviews.
- Uso personal con login.
- Crecimiento futuro con filtros por premios, mapas, listas personalizadas y más fuentes de datos.
