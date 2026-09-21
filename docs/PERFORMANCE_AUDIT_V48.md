# Auditoría de rendimiento v48

Fecha de medición: 21 de septiembre de 2026. Esta auditoría compara la producción v48 publicada con la revisión local del sprint de estabilidad. Las cifras son mediciones de laboratorio con Playwright/Chromium y una conexión local sin limitación artificial. No sustituyen datos de campo. `interactionLatency` mide el tiempo de una navegación interna de prueba hasta dos frames estables; es una aproximación útil, no el INP de usuarios reales.

## Metodología

- Producción: `https://thevaultescape.com/`, sesión anónima, cold y warm, desktop 1365×768 y móvil 390×844.
- Local: `http://127.0.0.1:8769/`, anónimo y fixture autenticada, desktop, móvil y modo `display-mode: standalone` equivalente.
- Service Worker bloqueado durante la captura para medir el documento y sus recursos, evitando que una caché previa falsee el cold load.
- Se registraron Navigation/Resource/Long Task/LCP/Layout Shift Performance APIs, número de nodos DOM, peticiones y bytes por tipo.
- No se usó una cuenta real para automatizar el escenario autenticado de producción. La comparación autenticada es local, con el mismo render de aplicación y datos fixture.

Los resultados completos están en `private/stability-v48-20260920-203919/performance-results.json` y permanecen fuera de Git.

## Baseline de producción v48

| Escenario | TTFB | FCP | LCP | CLS | DCL | Load | Peticiones | Transferencia | Imágenes | JSON | DOM | Long tasks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Desktop anónimo cold | 26 ms | 1.272 s | 1.272 s | 0,064 | 1.111 s | 1.268 s | 119 | 16,28 MB | 16,01 MB | 253 KB | 10.450 | 4 |
| Desktop anónimo warm | 0 ms | 384 ms | 384 ms | 0 | 285 ms | 286 ms | 27 | 217 KB | 0 | 217 KB | 10.450 | 2 |
| Móvil 390 anónimo cold | 17 ms | 432 ms | 432 ms | 0 | 438 ms | 512 ms | 24 | 555 KB | 287 KB | 253 KB | 10.450 | 5 |
| Móvil 390 anónimo warm | <1 ms | 516 ms | 548 ms | 0,184 | 545 ms | 546 ms | 83 | 217 KB | 0 | 217 KB | 10.450 | 4 |

El cold load desktop de 16,28 MB fluctuó según qué imágenes llegaron a descargarse durante la ventana de medición. La señal estable y reproducible es el DOM inicial de 10.450 nodos y la creación anticipada de paneles ocultos.

## Resultado local después de los cambios

| Escenario | TTFB | FCP | LCP | CLS | DCL | Load | Peticiones | Transferencia | Imágenes | JSON | DOM | Latencia interacción |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Desktop anónimo cold | 1 ms | 1.396 s | 1.396 s | 0,066 | 1.142 s | 1.564 s | 23 | 426 KB | 236 KB | 144 KB | 626 | 486 ms |
| Desktop autenticado cold | 1 ms | 580 ms | 1.068 s | 0,072 | 388 ms | 443 ms | 29 | 559 KB | 369 KB | 144 KB | 643 | 460 ms |
| Móvil 390 anónimo cold | 1 ms | 416 ms | 416 ms | 0 | 424 ms | 580 ms | 23 | 382 KB | 192 KB | 144 KB | 626 | 546 ms |
| Móvil 390 autenticado cold | 1 ms | 392 ms | 392 ms | 0 | 398 ms | 544 ms | 29 | 515 KB | 325 KB | 144 KB | 643 | 452 ms |
| Móvil standalone autenticado | 2 ms | 384 ms | 384 ms | 0 | 392 ms | 639 ms | 29 | 515 KB | 325 KB | 144 KB | 643 | 510 ms |

La comparación temporal producción/local incluye red distinta, por lo que el resultado arquitectónico más fiable es:

- DOM inicial: 10.450 → 626/643 nodos, reducción aproximada del 94 %.
- Peticiones iniciales anónimas: 119 en el cold desktop observado → 23 local.
- Portada autenticada: las cinco portadas grandes de actividad/descubrimiento sumaban ~1,57 MB. Al reutilizar `images/seo/latest/*.webp`, imágenes iniciales bajaron de ~1,89 MB a ~0,33 MB y la transferencia total de ~2,08 MB a ~0,51 MB.
- Catálogo, ranking y reviews dejan de renderizarse ocultos al arrancar; se generan al abrir la pestaña.
- Leaflet, relaciones, catálogo ampliado y mapas dejan de inicializarse desde la portada. El mapa carga al pulsar `Abrir mapa`.

## Cuellos de botella identificados

1. El arranque llamaba a renders de todos los paneles, incluido el catálogo completo de 1.735 salas. Esto explicaba el DOM de más de diez mil nodos aunque el usuario estuviera en Home.
2. El mapa/Leaflet y sus datos se preparaban en la portada autenticada sin que el usuario abriera el mapa.
3. Actividad reciente y descubrimiento reutilizaban portadas de catálogo de 230–390 KB para miniaturas de unos 64 px.
4. La navegación a una pestaña pesada todavía puede generar varios MB y long tasks de 150–430 ms. Ese coste se ha desplazado al momento en que el usuario solicita el contenido, pero el catálogo sigue sin virtualización.
5. El HTML monolítico y los estilos inline hacen que Resource Timing atribuya poco CSS/JS externo aunque exista coste de parseo y ejecución. El JS externo medido ronda 44 KB; esta métrica no incluye el script inline principal.
6. En warm móvil aparece CLS de laboratorio entre 0,18 y 0,23. Parte procede del fixture y de la sustitución de la portada tras Auth. Conviene medirlo de nuevo con datos de campo tras una futura publicación.

## Cambios aplicados localmente

- Solo se renderiza la pestaña activa; las demás se cargan bajo demanda.
- La precarga secundaria se retrasa y deja de bloquear la primera interacción.
- Leaflet y los datos del mapa se cargan al abrir el mapa.
- `loading="lazy"` y `decoding="async"` se mantienen en miniaturas.
- Home usa las miniaturas SEO existentes para cualquier sala con review publicada y conserva la portada canónica como fallback.
- El Service Worker sirve código con estrategia network-first para que una shell antigua no mantenga indefinidamente HTML/JS incompatibles.

## Trabajo posterior recomendado

- Separar el script inline principal para medir, cachear y perfilar su coste con mayor precisión.
- Virtualizar o paginar el catálogo si la latencia al abrirlo sigue siendo alta en dispositivos modestos.
- Reducir duplicación de peticiones de iconos de navegación con URLs versionadas coherentes.
- Añadir telemetría de campo consentida para Core Web Vitals; las cifras actuales son de laboratorio.
- Revisar el CLS warm móvil con una sesión Firebase real antes de publicar una siguiente versión.
