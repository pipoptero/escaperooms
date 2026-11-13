# Ficha única de Escape Room

Estado: **APROBADO** por el propietario el 13/11/2026; **IMPLEMENTADO** en `index.html` (`openDetail`, `detailScoreComparisonHtml`, `globalSourcesDetailHtml`, `detailAwardsHtml`, `reviewSynopsisHtml`). Revisión 13/11/2026.

La ficha de El Secreto de los Krugger es la referencia visual. La tarjeta Precio procede del modelo ya visible en ¡Oh Fortuna!. Todas las entradas (catálogo, ranking, búsqueda, hechos, pendientes, favoritos, grupos y hash directo) deben pasar por `openDetail`.

## Contrato de presentación

1. Cabecera: portada o fallback, nombre, empresa, ubicación, etiquetas y reconocimientos con contenido real.
2. Índice global siempre visible: nota real `/10`, o `Pendiente de valoración`; nunca sintetizar `0/10`.
3. Seis tarjetas, siempre en este orden: Duración, Jugadores, Dificultad, Precio, Ubicación, País. Usar `No disponible` cuando falte el valor. `priceLabel()` emplea `precio`, `precio_min`, `precio_max`; no convierte precio por grupo a precio por persona.
4. Fuentes siempre visibles: datos verdaderos o `Sin valoraciones disponibles`.
5. Premios siempre visibles: reconocimientos registrados o `Sin premios registrados en The Vault`.
6. Sinopsis siempre visible: texto existente completo o `Sinopsis pendiente`.
7. Reviews, multimedia oficial, estados, grupos, enlaces y acciones permanecen contextuales. No renderizar reproductores vacíos.

Krugger ilustra una review propia con puntuación; en la base inspeccionada no muestra premios registrados. ¡Oh Fortuna! ilustra datos parciales; los huecos son estados de presentación, no cambios de `catalog.json`. La revisión del grupo conserva su contenido y sus acciones; la sinopsis procede de la sala canónica cuando existe.

Pruebas asociadas: `tests/browser/` en Chromium y WebKit, `scripts/validate_site_data.py --strict`, tests de identidad y SEO. No modificar IDs para conseguir un aspecto uniforme.
