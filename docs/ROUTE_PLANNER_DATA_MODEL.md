# Planificador de rutas: modelo de datos v1

## Fuentes existentes

El planificador es una capa de lectura y cálculo en el cliente. No crea un modelo nuevo en Firebase.

- `catalog.json` aporta identidad canónica, nombre, empresa, ciudad, provincia, comunidad, duración, jugadores, dificultad, terror, web e imagen. El catálogo actual contiene 1.735 salas. La cobertura no es completa: 1.452 tienen ciudad, 1.288 duración, 1.262 mínimo de jugadores, 1.273 máximo, 848 dificultad y 1.016 una clasificación explícita de terror.
- `room_locations.json` contiene coordenadas y dirección revisada para 987 identidades; 984 corresponden directamente a IDs del catálogo. La v1 considera fiables para cercanía 721 coincidencias directas: precisión marcada como exacta/manual o confianza de al menos 70. Los centros aproximados de ciudad, provincia o comunidad que utiliza el mapa general no se consideran posiciones de una sala.
- El índice global ya calculado por `globalRatingForRoom` se usa como señal de calidad. El planificador no modifica el algoritmo ni el ranking público.
- `users/{uid}/roomStates` aporta el estado personal normalizado mediante `room-state.js`.
- `groupRooms/{groupId}` y `groupPendingRooms/{groupId}` aportan los estados compartidos del grupo, también normalizados mediante `room-state.js`.
- `groupMembers/{groupId}` se usa únicamente para proponer el número inicial de jugadores a partir de miembros activos.

## Alcance y límites del estado de grupo

`groupRooms` representa el historial compartido del grupo. No contiene una lista de participantes por sala. Las reglas actuales tampoco permiten leer el historial personal privado de los demás miembros. Por ello la v1 puede afirmar que una sala está hecha o pendiente **en el grupo**, pero no puede calcular de forma fiable “2 de 4 miembros la han hecho”.

En modo grupo se excluyen por defecto las salas que ya figuran en `groupRooms`. La opción “Excluir también las salas que ya constan en mi historial personal” añade únicamente el estado del usuario actual. No infiere el historial privado de otros miembros. Añadir ese dato exigiría un consentimiento y un modelo de participación por sala; queda fuera de este sprint.

Los estados personales y de grupo se consultan por separado. Marcar una recomendación como pendiente reutiliza el flujo existente de escritura en la lista seleccionada y no copia estados entre ámbitos.

## Cálculo y persistencia

Las configuraciones, resultados, orden y horarios son temporales y viven solo en memoria del navegador. No se guardan rutas, no se crean enlaces públicos y no se añaden ramas Firebase.

Los filtros incompatibles con datos conocidos son estrictos. Una sala con jugadores, terror o dificultad desconocidos puede conservarse cuando el filtro es “cualquiera”; si el usuario exige un valor concreto y falta el dato, se excluye para no inventarlo.

La señal “novedad” no se ofrece: el catálogo no contiene una fecha de apertura fiable y homogénea. La propuesta “más compacta” solo aparece cuando todas las salas necesarias tienen coordenadas propias en `room_locations.json`.

## Puntuación independiente

La puntuación interna ordena candidatos y nunca se publica como ranking:

- base común: hasta 60 puntos por el índice global existente (`índice × 6`), 5 puntos por compatibilidad conocida con el tamaño del equipo (1 si faltan límites) y hasta 5 por reconocimientos;
- “Mejor valoradas”: usa solo la base común y ordena primero por índice global. Un pendiente no recibe bonificación;
- “Pendientes”: suma 20 puntos si la sala está pendiente en el ámbito elegido. Es una señal importante, pero una diferencia grande de valoración todavía puede prevalecer;
- “Sin realizar”: las salas hechas en el ámbito ya se excluyen como regla de elegibilidad, y las restantes se ordenan por la base común. En grupo significa exclusivamente “sin registrar como hecha en el grupo”;
- “Recomendada”: suma 10 puntos por pendiente y 4 por no constar como hecha en el ámbito. Su bonificación máxima de estado es 14, frente a los 30 anteriores.

La puntuación es interna y no se muestra al usuario. El itinerario compacto busca el recorrido geodésico más corto mediante vecino próximo desde cada posible inicio entre los 30 candidatos elegibles mejor puntuados (o seis veces el tamaño solicitado si fuera mayor). Solo aparece si todas las salas incluidas tienen coordenadas fiables y produce una alternativa distinta. Los horarios usan duraciones disponibles más un margen fijo de 30 minutos y se rotulan como horas orientativas; no representan disponibilidad, reserva ni horarios oficiales.

## Posible evolución

Guardar o compartir rutas requeriría un modelo separado con propietario, ámbito, participantes autorizados, IDs canónicos de sala, orden, configuración, fecha de creación y versión del algoritmo. Una participación individual por sala debería ser explícita y compatible con la privacidad de perfiles. Ese diseño requeriría reglas y pruebas nuevas antes de cualquier escritura.
