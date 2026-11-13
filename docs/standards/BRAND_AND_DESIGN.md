# Identidad y diseño de The Vault

Estado: **IMPLEMENTADO** en `index.html`, revisión 13/11/2026. Fuente: CSS y componentes de la web; las adaptaciones de marketing se señalan aparte.

## Tokens web observados

| Función | Token | Valor |
|---|---|---|
| Fondo | `--bg`, `--bg2`, `--bg3` | `#0a0a0f`, `#0f0f18`, `#141422` |
| Superficie, borde | `--card`, `--border` | `#12121e`, `#2a2a45` |
| Acento | `--amber`, `--amber2` | `#7dbb3f`, `#5f9f32` |
| Texto | `--text`, `--text2`, `--text3` | `#e8e8f0`, `#9090b0`, `#5a5a80` |
| Otros estados | `--red`, `--green`, `--blue`, `--gold` | `#e63946`, `#06d6a0`, `#4cc9f0`, `#f0f0ea` |

La interfaz usa Rajdhani para texto, Cinzel para títulos y Share Tech Mono para etiquetas y metadatos; la hoja de Google Fonts está enlazada en `index.html`. Las tarjetas, botones, pestañas y modales usan bordes definidos y superficies oscuras. Los estilos responsive existentes gobiernan ancho, espaciado y navegación: reutilizarlos antes de introducir puntos de corte nuevos. Conservar el logotipo y los iconos PNG originales.

**APROBADO**: El Secreto de los Krugger es la referencia visual para las fichas de escape, con Precio añadido. **IMPLEMENTADO**: `openDetail()` y las clases `detail-*` renderizan el modal. **RECOMENDADO**: revisar contraste de los textos secundarios antes de cambiar tokens; cualquier cambio requiere prueba a 390 y 1440 px en Chromium y WebKit.

La identidad promocional de redes tiene formatos propios descritos en [SOCIAL_MEDIA.md](SOCIAL_MEDIA.md); no se infiere automáticamente del CSS de la web. No presentar imágenes generadas o de terceros como fotografías oficiales.
