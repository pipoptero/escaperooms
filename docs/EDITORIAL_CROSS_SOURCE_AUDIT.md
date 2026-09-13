# Auditoría editorial catálogo/reviews

Fecha: 2026-09-13

Esta auditoría clasifica las 32 diferencias estructuradas detectadas por `scripts/validate_site_data.py`. Es informativa: no corrige `catalog.json`, `published_reviews.json` ni texto libre. La correspondencia entre sala y review exige ID directo o alias inequívoco; una coincidencia aproximada de nombre no basta.

## Resumen

| Categoría | Casos | Criterio |
| --- | ---: | --- |
| A. Probable error real de datos | 3 | Hay evidencia interna fuerte de un valor erróneo o de un campo que contiene otra identidad. |
| B. Cambio histórico o rebranding esperado | 16 | Los valores describen etapas, marcas o ubicaciones anteriores compatibles con la historia registrada. |
| C. Texto abreviado o evidencia insuficiente | 13 | Es una diferencia de presentación o faltan pruebas para elegir un valor. |

## A. Probables errores reales

| Sala/campo | Catálogo | Review | Fuente interna | Dato probable | Confianza |
| --- | --- | --- | --- | --- | --- |
| Dark City · empresa | `Obscura Experiences` | `Obscura Experiencie` | `catalog.json`, fuente oficial `https://obscuraexperiences.com/`, revisada 2026-08-09; review `dark_city` | Catálogo. La review contiene una errata singular/plural. | Alta |
| En la Mente del Asesino · nombre | `En la Mente del Asesino` | `encryptroom` | `catalog.json`, ID `en-la-mente-del-asesino`, web de Encrypt y fuente histórica de la sala; review `encryptroom` con misma empresa, ciudad, duración y temática | Catálogo. `encryptroom` identifica la empresa/clave antigua, no el nombre de la sala. | Alta |
| Pesadillas (Orihuela) · empresa | `Pesadillas Escape Room` | `Golden Pop` | La review contiene ID `pesadillas-827641`, Orihuela, 66 min y `https://pesadillasescaperoom.com/`, exactamente como esa ficha; existe además otra sala distinta `pesadillas` de Golden Pop en Barcelona, 90 min | Catálogo. La empresa de la review parece copiada de la otra sala homónima. | Alta |

## B. Cambios históricos o rebranding esperados

| Sala/campo | Catálogo actual | Review/histórico | Evidencia y motivo |
| --- | --- | --- | --- |
| Achijira · empresa | Red Dopamine | Awaken | Cambio de marca compatible con la misma experiencia y su alias histórico. |
| Alkatraz Medieval · empresa | Eskapark | Play Escape Room | Explotación/marca histórica distinta en la review. |
| El Cetro de Fuego · empresa | Elements Escape Room | Elements Fuego | Marca general frente a denominación histórica de la sede/experiencia. |
| El hijo del posadero · nombre | El hijo del posadero | El hijo Perdido del Posadero | Renombrado histórico ya documentado por aliases. |
| El hijo del posadero · empresa | Dragon Born Vitoria | Dragonborn | Variante histórica de marca asociada al mismo cambio. |
| Exodus · empresa | Elements Escape Room | Elements Barcelona | Marca general frente a denominación de sede. |
| La Historia de Charlotte · nombre | La Historia de Charlotte | WHITECHAPEL | La review conserva el branding histórico de la experiencia/empresa; la identidad canónica está documentada. |
| La Taberna · empresa | The City Escape Room | The City Escape | Abreviación/marca histórica. |
| La Taberna · ciudad | Terrassa | Barcelona | La review conserva una localización amplia o anterior; el catálogo registra Terrassa desde el primer historial disponible. |
| La Taberna · duración | 120 | 60 | El catálogo pasó de 119 a 120 min al ser revisado el 2026-08-07; la review conserva 60 min. La diferencia puede describir una versión anterior y no debe corregirse sin confirmar la fecha de la partida. |
| Londium · empresa | Londium Escape Room | Saga Escape Room | Rebranding documentado por la web histórica de la review y la marca actual del catálogo. |
| Londium · ciudad | Montcada i Reixac | Barcelona | Municipio actual frente a localización metropolitana/histórica. |
| Londium · duración | 80 | 70 | El primer catálogo conservado indicaba 90 min y la revisión de 2026-08-07 lo dejó en 80; la review registra 70. Es compatible con versiones distintas y requiere fecha de partida para corregir. |
| Room Angie 2 · empresa | Ilusium Room Escape | Ilusium Escape | Variante de marca sin conflicto de identidad. |
| Roomions · empresa | Virus Room Escape | Virus Games | Cambio/variante de marca; la sala queda identificada de forma inequívoca. |
| Tao · empresa | Virus Room Escape | Virus Games | Mismo cambio/variante de marca que Roomions. |

## C. Texto abreviado o evidencia insuficiente

| Sala/campo | Catálogo | Review | Motivo |
| --- | --- | --- | --- |
| El Secreto de Jaipur · nombre | El Secreto de Jaipur | Jaipur | Título abreviado. |
| El Secreto de Jaipur · empresa | Kadabra Escape | Kadabra | Marca abreviada. |
| El Secreto de los Krugger · empresa | Insomnia Corporation | Insomnia Corp. | Abreviación. |
| High School · nombre | High School | Highschool | Espaciado. |
| High School · empresa | Unreal Room Escape | Unreal | Marca abreviada. |
| K.O.N.G Protocol · nombre | K.O.N.G Protocol | K.O.N.G. Protocol | Puntuación tipográfica. |
| K.O.N.G Protocol · ciudad | Santa Coloma de Gramenet | Barcelona | Municipio frente a área metropolitana; no hay fecha suficiente para decidir si es histórico. |
| K.O.N.G Protocol · duración | 120–150 | 120 | La review puede reflejar el modo jugado dentro del rango actual. |
| Night Shift · nombre | Night Shift | Nightshift | Espaciado. |
| Outline · empresa | Outline Escape Room | Outline | Marca abreviada. |
| Sección Esoterismo: Exorcista · nombre | Sección Esoterismo: Exorcista | Exorcista | Título abreviado; el alias histórico se conserva. |
| Slasher Party · empresa | Open Mind Room Escape | Open Mind | Marca abreviada. |
| Tao · nombre | Tao | Tao Room Escape | El sufijo describe el tipo de negocio; no cambia la identidad. |

## Comprobación específica de duraciones

- **La Taberna:** catálogo actual 120 min; review 60 min. El historial del catálogo muestra 119 min el 2026-06-08 y 120 min desde la revisión del 2026-08-07. La fuente del catálogo es `https://thecityescaperoom.com/barcelona/la-taberna/`. El valor actual tiene mejor respaldo para la ficha presente, pero no demuestra que la review histórica esté mal.
- **Londium:** catálogo actual 80 min; review 70 min. El historial muestra 90 min el 2026-06-08 y 80 min desde la revisión del 2026-08-07. La fuente actual es `https://londiumescaperoom.com/`; la review conserva la etapa `Saga Escape Room`. Se clasifica como histórica.
- **Pesadillas:** la review auditada es la sala de Orihuela (`pesadillas-827641`) y tanto catálogo como review indican 66 min. No hay diferencia de duración; el aviso es exclusivamente la empresa incorrecta de la review.
- **Jurásico:** catálogo y review indican 120 min. No forma parte de los 32 avisos.

## Decisión de producto

El validador mantiene las 32 diferencias como `WARNING`. Los tres casos A deberían revisarse editorialmente en un sprint separado. Los casos B necesitan preservar el dato histórico o incorporar fechas antes de normalizarlos. Los casos C no deben bloquear publicación ni activar autocorrecciones.
