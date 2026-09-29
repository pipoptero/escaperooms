# Firebase Auth same-origin — Stage B, candidato de publicación

Base: commit de Stage A `6a9e6cbddcb425aced501b61c42d5e9ab0a7acc7`. El cambio de Stage B afecta al cliente y al artefacto de GitHub Pages; no requiere escrituras en Firebase Authentication, RTDB, Rules ni el cliente OAuth. La prueba física en iPhone determinará si el flujo queda validado.

## Contrato del candidato

- Config web final: `projectId=scapesrooms`, `authDomain=thevaultescape.com`, demás valores de la app web existentes sin cambios. El workflow genera el `firebase-config.js` real y fija únicamente el dominio público nuevo; `apiKey`, `projectId`, `appId` y `databaseURL` continúan procediendo de sus secrets actuales. `firebase-config.same-origin.example.js` no forma parte del artefacto.
- Helper operativo esperado: `https://thevaultescape.com/__/auth/handler`. Las ocho rutas y el bypass de SW publicados en Stage A permanecen intactos.
- Navegador de escritorio y navegador móvil: `signInWithPopup`. PWA standalone, detectada por `display-mode: standalone` o `navigator.standalone`: `signInWithRedirect` solo cuando helper y app comparten origen. Un navegador integrado incompatible sigue mostrando el mensaje para abrir en navegador.
- `Auth.Persistence.LOCAL` se establece al inicializar Auth antes de cualquier intento. El flujo redirect guarda `vault-auth-redirect-pending` en `sessionStorage` justo antes de llamar al SDK; el popup no usa ese marcador. La ruta redirect no pasa por el timeout de popup de 15 segundos. Si el SDK rechaza, se elimina el marcador y se muestra recuperación. Si el SDK dice haber despachado el redirect pero el documento sigue visible 30 segundos sin navegar, un guard separado muestra error recuperable; se cancela al salir de la página.
- Al iniciar, `getRedirectResult()` sigue ejecutándose también en navegador normal para retornos legacy. `success`, `null` y `error` se registran sin UID/token. Marcador + `null` + sesión inexistente produce `auth/redirect-no-result`; si ya existe usuario LOCAL, prevalece la sesión autenticada. En todos los casos se limpia el marcador. Los errores de retorno no impiden comprobar una sesión LOCAL existente.
- La versión visible y el caché SW son v53. El HTML solicita `firebase-config.js?v=53` para no heredar el caché HTTP del archivo de configuración anterior. El SW no cachea esa configuración ni los helpers. El panel oculto de cinco taps conserva URL saneada, selección de método, dominio, URL/origen del helper, coincidencia de origen, persistencia, fase/error, marcador, resultado y versión SW.

## Sesiones existentes

La aplicación permanece en `https://thevaultescape.com`; no hay cambio del origen donde se guarda la sesión LOCAL. El código no llama a `signOut`, no borra IndexedDB/localStorage y mantiene `projectId`, `apiKey` y `appId`. Según [Firebase Auth persistence](https://firebase.google.com/docs/auth/web/auth-state-persistence), la persistencia LOCAL es por origen y sobrevive al cierre de la ventana; por ello se espera que una sesión existente siga disponible. El `authDomain` determina el origen del helper OAuth, no un nuevo origen de la aplicación. Es una inferencia técnica, no una prueba física: antes de cerrar Stage B habrá que validar en iPhone una sesión existente, nuevo login, cierre completo y reapertura.

## Estado OAuth y límites

El usuario confirmó que en el OAuth Web Client `355203547760-8aaa2p4dqkqufodeunouajr284hlv8jv.apps.googleusercontent.com` añadió el JavaScript origin `https://thevaultescape.com` y el redirect URI `https://thevaultescape.com/__/auth/handler`, conservando el URI anterior. Han transcurrido horas y autorizó Stage B; **la configuración OAuth no se ha verificado administrativamente desde este entorno**. La documentación oficial de [Firebase Option 4](https://firebase.google.com/docs/auth/web/redirect-best-practices#option-4-self-host-the-sign-in-helper-code-in-your-domain) exige mantener sincronizados los helpers autoalojados.

## Despliegue controlado autorizado

1. El usuario confirmó el origin y redirect URI del cliente OAuth, el dominio autorizado Firebase y la propagación. Verificar HTTP 200/MIME/SHA de los ocho helpers y HEAD/CI. No hacer login con cuentas reales en un smoke automatizado.
2. Revalidar el diff local y las pruebas focalizadas sobre el staged. Preparar commit exclusivamente Stage B. No arrastrar cambios del worktree Auth antiguo ni de Reviews.
3. Subir el commit v53, que genera `firebase-config.js` con `authDomain=thevaultescape.com` desde el workflow de Pages, y esperar CI/Pages. `firebase-config.js?v=53` evita reutilizar el archivo de configuración HTTP anterior. Verificar en producción config efectiva, SW v53, helper, método por contexto y ausencia de errores antes de prueba física.
4. Prueba física iPhone instalado: aceptar actualización PWA, cinco taps para confirmar `sameOriginHelper=true` y `selectedMethod=redirect`, iniciar Google, volver, comprobar usuario, cerrar completamente, reabrir y comprobar persistencia. Probar también navegador móvil normal y escritorio con popup.

## Rollback preparado, sin ejecutar

1. Cambiar el `authDomain` generado por Pages a `scapesrooms.firebaseapp.com` y desplegar el cliente Auth anterior con selección popup para todos los contextos. Los ocho helpers pueden permanecer publicados: con el dominio antiguo son inertes.
2. Publicar una versión nueva de SW/cache e indicador, nunca reutilizar `the-vault-v53` para contenido distinto. Cambiar también el query de `firebase-config.js` de la versión de rollback para evitar que un navegador conserve durante el TTL HTTP una configuración v53. Verificar dominio/método efectivos en navegador y PWA, CI y Pages.
3. No borrar sesiones ni datos de Firebase. Si el problema se limita a propagación OAuth, un cliente que aún vea la configuración anterior continúa con popup; la prueba física sigue pendiente hasta activar con seguridad.

El rollback no se ha ejecutado ni autorizado; solo se describe el procedimiento necesario para que sea exacto incluso con caché HTTP.
