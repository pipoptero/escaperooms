# Firebase Auth same-origin para la PWA iOS

Estado: candidato Stage A preparado sobre `main` posterior a Reviews y La Vitrina. Solo se publicarán helpers estáticos y su bypass de SW; Firebase Authentication, Google OAuth, RTDB, Rules y la configuración Auth de producción quedan fuera.

## Decisión

The Vault seguirá alojada en GitHub Pages. La solución candidata usa la opción 4 oficial de Firebase, **self-host sign-in helper code**, para que el SDK acceda a los helpers desde el mismo origen que la aplicación.

Configuración candidata del paso B:

```text
app origin    https://thevaultescape.com
authDomain    thevaultescape.com
helper origin https://thevaultescape.com
handler       https://thevaultescape.com/__/auth/handler
```

El código queda protegido por compatibilidad: mientras el `authDomain` efectivo siga siendo `scapesrooms.firebaseapp.com`, escritorio, navegador móvil y standalone siguen usando popup. Solo un contexto standalone con helper realmente same-origin selecciona redirect.

## Helpers y procedencia

Se sincronizan desde `https://scapesrooms.firebaseapp.com` sin reescribir su contenido:

| Ruta pública | SHA-256 | MIME upstream |
|---|---|---|
| `/__/auth/handler` | `ce225ee3bd2a8ad914e3da1ad3c2fb7dfb42e901d54d358b718c449eededb254` | `text/html; charset=utf-8` |
| `/__/auth/handler.js` | `d85408b55b15a4eac503aed04fdb20312f4ba6be52d429d5da40ad413f37015f` | `text/javascript; charset=utf-8` |
| `/__/auth/experiments.js` | `91450aff1a84319cca71087830a639d6dcac4fee5bb60b4b13470374bbeae6dc` | `text/javascript; charset=utf-8` |
| `/__/auth/iframe` | `d1eea8206093f3c645b999e44787c4798a867a5a26bc482313cf9007b778a47d` | `text/html; charset=utf-8` |
| `/__/auth/iframe.js` | `21ec74329fcd1ab30ae6cbad379cad400e8ed47f8ae458ee710751df7a7cf4c2` | `text/javascript; charset=utf-8` |
| `/__/auth/links` | `b0cdfad081aa23ec6d28a5bb53dd58275029220afa10422a2fd21bac3f91ac53` | `text/html; charset=utf-8` |
| `/__/auth/links.js` | `d110cda16ec2926397deb63d944d7465230a648555cceb1638963c55517ba93e` | `text/javascript; charset=utf-8` |
| `/__/firebase/init.json` | `257816bf1acd6af5806f5a2e5d0618c774708a676c16de5c90a6f5ae7506cee6` | `application/json` |

El 21 de septiembre de 2026 el endpoint upstream de `init.json` devolvió HTTP 404 tanto en `firebaseapp.com` como en `web.app`; los siete helpers Auth devolvieron 200. El `--check` del 28 de septiembre confirmó los siete hashes sin cambios y el mismo 404 para `init.json`. Para no inventar la configuración, `init.json` se obtuvo mediante `firebase apps:sdkconfig` de la app web activa `scaperooms-web`. Contiene exclusivamente configuración web pública. El sincronizador conserva y revalida ese archivo mientras el endpoint reservado siga ausente, y registra el 404 en su informe. Esta es una excepción documentada a la descarga de los ocho endpoints: siete vienen del endpoint reservado; el octavo procede de la configuración SDK oficial.

El fallback no acepta cualquier fichero local: exige la procedencia SDK, el proyecto/app exactos y el SHA previamente revisado de `initFallback` en el lock. Si cambia un solo byte, o falta esa procedencia, aborta; no regenera ni normaliza la configuración para ocultar la diferencia. Una revisión futura de la configuración SDK requiere contrastarla de nuevo y aprobar su nuevo pin local. El sincronizador tampoco acepta un upstream alternativo ni redirecciones fuera del origen HTTPS oficial.

`scripts/sync_firebase_auth_helpers.py` descarga primero todo a memoria, acepta redirecciones del upstream solo si permanecen en su origen HTTPS oficial, valida estado/MIME/proyecto, busca patrones de credenciales privadas, compara SHA-256 y escribe atómicamente solo lo que cambió. `--check` detecta drift sin escribir. El lock público guarda hashes, tamaños y MIME; el informe de ejecución queda en `reports/`, ignorado por Git.

## GitHub Pages y rutas sin extensión

La ruta física sin extensión `/CNAME` devolvió `application/octet-stream` en la comprobación de producción. Es evidencia de un riesgo de MIME, pero no demuestra por sí sola cómo servirá Pages los tres documentos Auth. No debemos considerar viable su publicación directa sin comprobarla.

GitHub Pages también resuelve una URL sin extensión a su archivo `.html` y mantiene la URL solicitada. Se comprobó en producción con `/index`, `/escapista/index` y `/privacidad/index`: 200, `text/html; charset=utf-8`, sin añadir `.html` a la URL.

Por ello las fuentes locales se conservan con sus nombres oficiales, pero el artefacto Pages transforma únicamente:

```text
__/auth/handler -> __/auth/handler.html
__/auth/iframe  -> __/auth/iframe.html
__/auth/links   -> __/auth/links.html
```

No cambia ningún byte. El artefacto incluye `.nojekyll`; no existía en el repositorio. Las URLs públicas previstas siguen siendo exactamente `/__/auth/handler`, `/__/auth/iframe` y `/__/auth/links`. Los `.js` y `init.json` conservan sus nombres. Esta adaptación debe comprobarse de forma definitiva en el paso A con `scripts/check_firebase_auth_helpers_http.py`; el paso B queda bloqueado si una sola ruta no devuelve 200, MIME esperado, SHA/tamaño exactos y la URL original sin redirección. La viabilidad es provisional hasta esa prueba: el servidor local de tests implementa expresamente la resolución `.html`, así que acredita el contrato esperado, no el comportamiento real de GitHub Pages.

## Service worker

El fetch handler sale inmediatamente para:

```text
/__/auth/*
/__/firebase/init.json
```

Esas rutas no entran en app shell, navegación fallback ni runtime cache. El caché HTTP de Pages puede aplicar sus cabeceras normales, pero el service worker nunca conserva una copia antigua.

## Configuración pública

`__/firebase/init.json` fue contrastado con la app web oficial:

- `projectId`: `scapesrooms`.
- `authDomain` upstream: `scapesrooms.firebaseapp.com`.
- `apiKey`, `appId` y `databaseURL`: presentes y coincidentes con la configuración web local.
- también están presentes los campos públicos de storage, messaging, measurement, project number y versión.
- no contiene client secret, claves privadas, tokens ni contraseñas.

El helper autoalojado debe conservar en `init.json` el `authDomain` upstream de la configuración Firebase descargada; el cambio same-origin se aplica a la configuración que inicializa la aplicación, representada localmente en `firebase-config.same-origin.example.js`.

## OAuth y dominios autorizados

La consulta pública de Identity Toolkit confirmó estos dominios autorizados relevantes:

- `thevaultescape.com`.
- `www.thevaultescape.com`.
- `scapesrooms.firebaseapp.com`.
- `scapesrooms.web.app`.
- `localhost` y `127.0.0.1` para desarrollo.

No hace falta añadir el dominio principal a Firebase Authentication: ya está autorizado.

El Client ID Google usado por Firebase Auth se identificó, sin iniciar sesión ni acceder a secretos, como:

```text
355203547760-8aaa2p4dqkqufodeunouajr284hlv8jv.apps.googleusercontent.com
```

La API pública no expone la lista administrativa de redirect URIs ni JavaScript origins del cliente OAuth. Esas listas no se han leído en esta auditoría; no afirmamos cuáles son sus entradas actuales. Existe una instalación local de `gcloud` fuera del PATH, pero eso no acredita acceso a esas listas y no se ha consultado una respuesta administrativa que pueda incluir el client secret. Antes del paso B hay que abrir **Google Cloud Console → APIs y servicios → Credenciales → ese Client ID** y, sin retirar entradas existentes, confirmar o añadir:

```text
Authorized JavaScript origin
https://thevaultescape.com

Authorized redirect URI
https://thevaultescape.com/__/auth/handler
```

No se necesita ni debe consultarse el client secret.

## Selección del método y retorno

| Contexto | Configuración actual | Configuración candidata same-origin |
|---|---|---|
| Escritorio | popup | popup |
| Navegador móvil | popup | popup |
| PWA standalone | popup | redirect |

El retorno standalone queda así:

1. se configura `Auth.Persistence.LOCAL`;
2. se marca `vault-auth-redirect-pending` en `sessionStorage`;
3. se inicia `signInWithRedirect()`;
4. Google devuelve al handler de `thevaultescape.com`;
5. al volver a la app, `getRedirectResult()` se ejecuta antes de resolver la sesión;
6. `onAuthStateChanged` confirma el usuario;
7. se limpia la marca pendiente y continúa la carga autenticada.

`getRedirectResult()` sigue ejecutándose también sin marca pendiente para aceptar retornos iniciados por una versión anterior. Error y timeout pasan a estado recuperable; no queda “Conectando” indefinidamente.

El panel de cinco taps incorpora `authDomain`, `helperOrigin`, `sameOriginHelper`, `redirectPending`, `redirectResult`, estado Auth, persistencia y service worker. El saneado existente sigue eliminando email, UID, tokens y credenciales.

## Clasificación de `scapesrooms.firebaseapp.com`

- **A — cambiar en paso B:** `FIREBASE_AUTH_DOMAIN` de GitHub Actions/Secrets y el `firebase-config.js` local ignorado por Git. La muestra candidata ya usa `thevaultescape.com`.
- **B — mantener:** origen `UPSTREAM` del sincronizador, metadatos del lock y `authDomain` de la configuración SDK oficial en `__/firebase/init.json`.
- **C — documentación/pruebas:** aserciones que certifican la procedencia upstream y este documento.

No se hace un reemplazo global.

## Plan de despliegue

### Paso A — helpers inertes

1. separar un commit con `__/`, lock, sincronizador, verificador HTTP, empaquetado Pages, bypass del service worker, pruebas y documentación;
2. mantener `FIREBASE_AUTH_DOMAIN=scapesrooms.firebaseapp.com`, interfaz PWA v52 y selección efectiva popup; el SW usa la versión interna exclusiva `the-vault-v52-auth-helpers` para invalidar cachés tras añadir el bypass, sin anticipar v53;
3. publicar Pages;
4. ejecutar `python scripts/check_firebase_auth_helpers_http.py --base-url https://thevaultescape.com`;
5. exigir ocho HTTP 200, MIME exactos y hashes del lock;
6. comprobar manualmente que `/__/auth/handler` no descarga archivo, no muestra el 404 de Pages y no es el HTML de fallback;
7. comprobar que el cliente v52 sigue seleccionando popup en escritorio, navegador móvil y standalone; no utilizar cuentas reales en el smoke automatizado.

Si GitHub Pages no cumple cualquiera de estos puntos, se detiene el rollout. No se cambia OAuth ni `authDomain`.

### Paso B — activar same-origin

1. confirmar/añadir origin y redirect URI en el cliente OAuth identificado;
2. reconfirmar `thevaultescape.com` en Firebase Auth Authorized domains;
3. cambiar el secret/config publicado a `authDomain=thevaultescape.com`;
4. publicar la selección popup para navegador y redirect para standalone;
5. subir interfaz y cache/versionado PWA a `the-vault-v53`;
6. verificar helpers antes del login y después probar retorno, sesión persistida, cierre/reapertura y diagnóstico en iPhone físico.

## Rollback

Restaurar `FIREBASE_AUTH_DOMAIN=scapesrooms.firebaseapp.com` y el comportamiento efectivo vuelve a popup en todos los contextos. Los helpers publicados son estáticos e inertes mientras no se utilice el dominio same-origin; pueden quedarse publicados. No hay cambios de usuarios, RTDB, Rules, DNS ni hosting.

## Límites y riesgos

- La resolución `.html` de Pages está comprobada con rutas existentes, pero la validación concluyente de `__/auth/*` requiere el paso A publicado.
- Un preview local valida rutas, bytes y state machine, pero no reproduce el contenedor PWA de iOS ni la vuelta real de Google.
- Los helpers deben resincronizarse periódicamente; el lock evita actualizaciones silenciosas.
- La opción 4 de Firebase no soporta Apple ni SAML. The Vault usa Google.
- Cambiar `authDomain` antes de registrar el redirect URI produciría un fallo OAuth; el orden del paso B es obligatorio.

## Verificación local de herramientas

`python -B -m unittest tests.test_firebase_auth_helpers -v` cubre hashes de los ocho archivos, configuración pública, rechazo de campos privados/inesperados, pin del fallback 404, validación de todas las descargas antes de escribir, `--check` sin cambios de assets, MIME/bytes del preview, redirección upstream limitada al mismo origen y rechazo de redirects de los endpoints publicados. La sincronización en modo `--check` confirmó 0 cambios el 28 de septiembre de 2026; no se hizo ninguna escritura Firebase.

## Referencias oficiales

- [Firebase: buenas prácticas de redirect, opción 4 self-host](https://firebase.google.com/docs/auth/web/redirect-best-practices#option-4-self-host-the-sign-in-helper-code-in-your-domain).
- [Firebase: URLs reservadas y service workers](https://firebase.google.com/docs/hosting/reserved-urls).
- [Firebase Authentication: configuración y resolución de problemas](https://firebase.google.com/docs/auth/faq-and-troubleshooting).
