# Análisis de brechas — requisitos vs. implementación

Este documento es la auditoría completa de los Objetivos específicos
(OE), Casos de uso (UC) y Requerimientos funcionales (RF) declarados en
[`document/final_document.typ`](../document/final_document.typ) frente
al código fuente actual. Se mantiene como documento de trabajo: cada
brecha tiene una casilla para marcar conforme se cierra.

## Cómo usar este documento

1. Las tablas de OE / UC / RF muestran el estado actual de cada
   requisito.
2. La sección **Top 10 — Plan de cierre** lista los huecos priorizados
   con casillas `- [ ]` para tachar conforme se completen.
3. La sección **Hallazgos transversales** captura cosas pequeñas o
   sutiles que no encajan en una sola fila.
4. Cuando se cierra un hueco, actualizar el estado de la fila
   correspondiente y marcar la casilla del Top 10.

## Leyenda de estado

- ✅ **Implementado** — feature completa, integrada extremo-a-extremo.
- 🟡 **Parcial** — existe pero con huecos (UI sin backend, backend sin
  UI, edge cases sin cubrir, comportamiento que difiere del CU).
- ❌ **Faltante** — sin implementación detectada.
- ⚠️ **Ambiguo** — el enunciado del requisito no es preciso; revisar
  redacción.

---

## Tabla 1 — Objetivos específicos

| ID | Descripción breve | Estado | Evidencia | Brecha |
|---|---|---|---|---|
| OE-1 | Sistema de monitoreo colaborativo: registro georreferenciado + pipeline estadístico para rutas | ✅ | `app/services/recording-store.ts`, `app/app/(tabs)/record.tsx`, `server/routes/recordings.py`, `packages/pipeline/src/pipeline/steps/reconstruct_routes.py` | Ninguna |
| OE-2 | Registro de desvíos temporales con etiquetado por línea | ✅ | `app/components/save-record-modal.tsx`, `server/routes/recordings.py:182-224`, `server/routes/detours.py` | Ninguna |
| OE-3 | Subsistema de gestión de tarifas con parametrización por municipio/tramo | ✅ | `server/routes/fares.py`, `packages/database/src/database/models/fare.py`, `app/components/save-record-modal.tsx`, `server/routes/directions.py` | Cubierto: el backend tiene zonas + agregación + estimate; la app llama `GET /fares/estimate` desde `directions.py` (cerrado por #2 el 2026-05-03); la pantalla de planificación muestra la tarifa por leg y total (RF-03/04/30); el flujo post-grabación captura tarifa con identificación automática de zonas (cerrado por #8 el 2026-05-03) |
| OE-4 | Gestión de líneas con diferenciación de ramales | ✅ | `packages/geodata/src/geodata/ramales.py`, `packages/pipeline/src/pipeline/steps/reconstruct_routes.py:execute`, `Route.ramal_label` (migración `c0d1e2f3a4b5`), `RamalDescriptor`/`RamalDescriptorVote` (migración `d2e3f4a5b6c7`), `app/components/ramal-descriptors-screen.tsx` | Cubierto por #7 (2026-05-03): clustering complete-linkage sobre Fréchet detecta ramales automáticamente; cada uno se persiste como Route independiente (`ramal_label`); identidad humana por `endpoint_zones` + `street_summary` (Nominatim + Valhalla); descriptores crowdsourced con UX "vote-on-existing-first" |
| OE-5 | Servicio de identificación de trayectos con transbordos y suscripción a líneas | ✅ | `server/routes/directions.py`, `packages/geodata/src/geodata/transit_graph.py` (TRANSFER_RADIUS_M=400m), `app/app/(tabs)/explore.tsx`, `server/services/push.py` | La suscripción se deriva implícitamente del guardado como "viaje recurrente"; no hay UI explícita para gestionar suscripciones. Aceptable si se documenta así |

## Tabla 2 — Casos de uso

| ID | Descripción breve | Estado | Evidencia | Brecha |
|---|---|---|---|---|
| CU-01 | Planificar ruta entre dos puntos | ✅ | `app/app/(tabs)/explore.tsx`, `server/routes/directions.py`, `server/services/line_metadata.py` | Ninguna. Cubierto por #2 (2026-05-03): `fare_bob`, `frequency_min`, `total_fare_bob` añadidos al schema, populados en el handler, mostrados como badges en results + detail |
| CU-02 | Consultar líneas cercanas | ✅ | `app/app/(tabs)/explore.tsx:146-179`, `server/routes/lines.py:184-302` | Ninguna |
| CU-03 | Consultar desvío activo de una línea | ✅ | `app/app/(tabs)/explore.tsx:296-332`, `server/services/detour_analysis.py`, `app/components/route-map.tsx` | Ninguna |
| CU-04 | Guardar ruta (día actual / recurrente / hora estimada) | ✅ | `app/components/save-trip-modal.tsx`, `app/services/saved-trips.ts`, `app/db/schema.ts`, `app/drizzle/0007_lame_mercury.sql` | Ninguna. Cubierto por #3 (2026-05-03): nueva columna `departureTime` HH:mm, modal con input opcional reemplazando el `Alert.alert` |
| CU-05 | Grabar recorrido | ✅ | `app/app/(tabs)/record.tsx`, `app/services/recording-store.ts`, `server/routes/recordings.py` | Ninguna |
| CU-06 | Proponer nueva línea | ✅ | `app/components/save-record-modal.tsx:325-360`, `server/routes/recordings.py:167-175` | Ninguna |
| CU-07 | Reportar desvío activo | ✅ | `app/components/save-record-modal.tsx`, `server/routes/recordings.py:182-224` | El CU describe un flujo separado ("Iniciar registro → Detener al llegar"). En la implementación, se reporta al final de cualquier grabación marcando un toggle. Funcionalmente equivalente; defendible |
| CU-08 | Registrar tarifa | ✅ | `app/components/save-record-modal.tsx:397-430`, `server/routes/fares.py:55-89` (`/fares/zones/resolve`), `document/final_document.typ:1815-1828` | Cubierto por #8 (2026-05-03): el flujo post-grabación implementa los 5 pasos del CU-08 (línea preseleccionada del recorrido, identificación automática de municipios via `/fares/zones/resolve`, ingreso de monto, confirmación con preview "Tarifa para X → Y"). El use case fue refinado: pasos 2 y 3 ahora dicen "Identificar" en lugar de "Seleccionar" — refleja honestamente que el sistema infiere las zonas desde GPS, evitando fricción de pickers de fronteras administrativas que el usuario no necesariamente conoce |
| CU-09 | Confirmar tarifa con opciones registradas | ✅ | `app/components/save-record-modal.tsx`, `server/routes/fares.py:_common_amounts`, `server/schemas/fare.py:CommonAmountRead` | Ninguna. Cubierto por #4 (2026-05-03): el modal de guardado renderiza chips con los montos más reportados; tap → submit con `source = confirmation` (vs `registration` para entrada libre) |
| CU-10 | Validar ruta inferida | ✅ | `app/app/(tabs)/contribute.tsx`, `app/components/section-vote-screen.tsx`, `server/routes/voting.py` | Ninguna |
| CU-11 | Reconstruir rutas (sistema) | ✅ | `packages/pipeline/src/pipeline/runner.py`, `server/services/pipeline_trigger.py`, `infra/deploy/cron/crontab.example`, `document/final_document.typ` (Despliegue) | Cubierto por #10 (2026-05-03): scheduler híbrido — `clean_traces` se dispara por evento (FastAPI BackgroundTasks al cerrar grabación) y los pasos pesados de agregación corren vía cron del host contra el servicio `pipeline` (perfil `jobs`); cada ejecución se registra con `trigger="event:recording_end"` o `trigger="cron"` |
| CU-12 | Inferir horarios y frecuencia de servicio | ✅ | `packages/pipeline/src/pipeline/steps/infer_schedules.py`, `packages/geodata/src/geodata/schedule.py`, `packages/database/src/database/models/line_schedule.py` | Ninguna. Implementado 2026-05-03: 3 cubos (weekday/saturday/sunday), regla CV<0.5 para "frecuencia confiable" (RF-24), expuesto en `LineRead.schedules` |
| CU-13 | Notificar desvíos en rutas recurrentes | 🟡 | `server/services/push.py`, `server/routes/recordings.py:215-224`, `app/services/saved-trips.ts:104-117` | Implementado pero **no probado end-to-end en dispositivos físicos**. Política de rate-limit (3+1/24h) no aparece en la tesis |
| CU-14 | Notificar inicio de ruta | ✅ | `app/services/trip-notifications.ts`, hook en `app/services/saved-trips.ts` y boot en `app/app/_layout.tsx` | Ninguna. Cubierto por #3: scheduler local (`expo-notifications`) con CALENDAR/DATE triggers; baked detour info al programar; reschedule en cada boot. Validación nativa cubierta por TC-14..17 (Anexo G del Plan) |

## Tabla 3 — Requerimientos funcionales

| ID | Descripción breve | Estado | Evidencia | Brecha |
|---|---|---|---|---|
| RF-01 | Ingresar origen/destino para opciones de ruta | ✅ | `app/app/(tabs)/explore.tsx:229-239`, `server/routes/directions.py:30` | Ninguna |
| RF-02 | Mostrar líneas, puntos de abordaje y descenso | ✅ | `app/app/(tabs)/explore.tsx:354-390` | Ninguna |
| RF-03 | Mostrar tarifa estimada del trayecto | ✅ | `server/schemas/directions.py` (`fare_bob`), `server/services/line_metadata.py:estimate_fare_bob`, `app/app/(tabs)/explore.tsx` | Ninguna. Cubierto por #2 |
| RF-04 | Mostrar frecuencia aproximada | ✅ | `server/services/line_metadata.py:current_headway_min`, `app/app/(tabs)/explore.tsx` | Ninguna. Cubierto por #2; usa el `headway_min` inferido por #1 según el día de la semana actual |
| RF-05 | Notificar cuando no exista ruta | ✅ | `app/app/(tabs)/explore.tsx:234` | Ninguna |
| RF-06 | Consultar líneas cercanas | ✅ | `app/app/(tabs)/explore.tsx:146-179`, `server/routes/lines.py:184-302` | Ninguna |
| RF-07 | Mostrar recorrido y destinos de cada línea cercana | ✅ | `app/app/(tabs)/explore.tsx:665-688`, `Route.endpoint_zones` (Nominatim) + `Route.street_summary` (Valhalla edge names) | Cubierto por #7 (2026-05-03): la card de cada línea cercana muestra `Beijing → Sacaba` como label primario y los principales avenidas/calles como secundario; multi-ramal añade badge "N ramales" |
| RF-08 | Notificar cuando no haya líneas cerca | ✅ | `app/app/(tabs)/explore.tsx:574-587` | Ninguna |
| RF-09 | Iniciar/detener registro de desvío | ✅ | `app/app/(tabs)/record.tsx`, `app/components/save-record-modal.tsx` | El desvío se decide al final, no al inicio (laxo respecto al CU) |
| RF-10 | Asociar desvío a línea existente | ✅ | `app/components/save-record-modal.tsx:283-322` | Ninguna |
| RF-11 | Publicar desvío sin pasar por reconstrucción | ✅ | `server/routes/recordings.py:202-210` | Ninguna |
| RF-12 | Alerta visual cuando línea tiene desvío activo | ✅ | `app/app/(tabs)/explore.tsx:434-441`, `app/app/(tabs)/explore.tsx:600-606`, `server/routes/lines.py:280-290`, `server/routes/directions.py:79-92` | Ninguna |
| RF-13 | Consultar recorrido alternativo de línea con desvío | ✅ | `app/app/(tabs)/explore.tsx:296-332`, `server/services/detour_analysis.py` | Ninguna |
| RF-14 | Iniciar/detener registro de recorrido | ✅ | `app/app/(tabs)/record.tsx`, `app/services/recording-store.ts` | Ninguna |
| RF-15 | Registrar ubicación durante grabación | ✅ | `app/services/background-location.ts`, `server/routes/recordings.py:282-325` | Ninguna |
| RF-16 | Asociar recorrido a línea existente | ✅ | `app/components/save-record-modal.tsx:283-322` | Ninguna |
| RF-17 | Proponer nueva línea | ✅ | `app/components/save-record-modal.tsx:325-360` | Ninguna |
| RF-18 | Procesar recorridos para inferir ruta representativa | ✅ | `packages/pipeline/src/pipeline/steps/reconstruct_routes.py` | Cubierto: scheduler hibrido cron+event-driven (cerrado por #10) |
| RF-19 | Detectar cambios significativos y proponer actualización | ✅ | `packages/pipeline/src/pipeline/steps/reconstruct_routes.py:execute`, `_load_existing_ramales`; columna `Route.last_compared_at` | Ninguna. Cubierto por #6 (2026-05-03) + extendido por #7 (2026-05-03): el sistema solo publica rutas de un único polilínea continuo y la decisión Fréchet (`< 50m` mantiene, `≥ 50m` supersede) se aplica por ramal — version chains independientes |
| RF-20 | Omitir líneas con pocos recorridos | ✅ | `packages/pipeline/src/pipeline/steps/reconstruct_routes.py` (`min_trips=3`) | Ninguna |
| RF-21 | Mostrar rutas para validación según mínimo de contribuciones | ✅ | `server/routes/voting.py:46-107`, `packages/geodata/src/geodata/edge_overlap.py` (`DEFAULT_MIN_TRIPS=3`) | Ninguna |
| RF-22 | Registrar voto sobre precisión de ruta inferida | ✅ | `server/routes/voting.py:253-361` | Ninguna |
| RF-23 | Inferir horario y frecuencia de cada línea | ✅ | `packages/pipeline/src/pipeline/steps/infer_schedules.py` | Ninguna. Cubierto por #1 |
| RF-24 | Publicar solo rango horario si no hay frecuencia confiable | ✅ | `packages/geodata/src/geodata/schedule.py` (umbral CV < 0.5) | Ninguna. Cubierto por #1 |
| RF-25 | Registrar costo de pasaje entre dos municipios | ✅ | `app/components/save-record-modal.tsx:397-430`, `server/routes/fares.py:55-89` | Cubierto por #8 (2026-05-03): los municipios se identifican automáticamente y se muestran al usuario antes de confirmar ("Tarifa para X → Y") — la decisión de UX se documenta en el caso de uso CU-08 actualizado |
| RF-26 | Notificar cuando ya exista tarifa registrada e invitar a confirmar | ✅ | `app/components/save-record-modal.tsx` (chips de `common_amounts`), `server/routes/fares.py:_common_amounts` | Ninguna. Cubierto por #4 |
| RF-27 | Pregunta "¿Cuánto salió tu pasaje?" al finalizar grabación | ✅ | `app/components/save-record-modal.tsx:401` | Cubierto por #8 (2026-05-03): texto literal del requisito |
| RF-28 | Mostrar opciones de tarifa registradas para el tramo | ✅ | `LineFareRead.common_amounts` en `server/schemas/fare.py`, chips en `save-record-modal.tsx` | Ninguna. Cubierto por #4 |
| RF-29 | Registrar selección como confirmación de tarifa | ✅ | `FareSource` enum (`registration` / `confirmation`) en `packages/database/src/database/models/fare.py`, migración `f7a8b9c0d1e2`, propagado por `services/api.ts:submitFareReport` y `routes/fares.py` | Ninguna. Cubierto por #4: chip click → `source=confirmation`, free input → `source=registration` |
| RF-30 | Calcular tarifa estimada total como suma de tramos | ✅ | `server/routes/directions.py` (`total_fare_bob`), `app/app/(tabs)/explore.tsx` (testID `route-N-total-fare`) | Ninguna. Cubierto por #2; suma sólo si todos los bus legs tienen `fare_bob`, sino devuelve null para no sub-prometer el costo |
| RF-31 | Guardar ruta como día actual o recurrente | ✅ | `app/app/(tabs)/explore.tsx:264-270`, `app/services/saved-trips.ts:27-50` | Ninguna |
| RF-32 | Permitir ingresar opcionalmente hora estimada de salida | ✅ | `app/components/save-trip-modal.tsx`, `app/db/schema.ts:97`, migración `0007_lame_mercury.sql` | Ninguna. Cubierto por #3 |
| RF-33 | Mostrar rutas "para día actual" solo el día en que se crearon | ✅ | `app/services/saved-trips.ts:61-69` | Ninguna |
| RF-34 | Mostrar rutas recurrentes diariamente | ✅ | `app/services/saved-trips.ts:66`, `app/app/(tabs)/favorites.tsx:141` | Ninguna |
| RF-35 | Notificar cuando se registre desvío en línea de ruta recurrente | 🟡 | `server/services/push.py`, `server/routes/recordings.py:215-224`, `app/services/saved-trips.ts:104-117`, `app/services/push.ts` | No probado en dispositivos físicos. Política rate-limit (3+1/24h) no aparece en la tesis |
| RF-36 | Notificar próxima hora de salida de ruta guardada | ✅ | `app/services/trip-notifications.ts:scheduleTripNotification` (DATE trigger para one_time, CALENDAR repeats:true para commute) | Ninguna. Cubierto por #3 |
| RF-37 | Incluir aviso de desvío en notificación de inicio de ruta | ✅ | `app/services/trip-notifications.ts:buildNotificationContent` consulta `/detours/active/{line_id}` al programar | Ninguna. Cubierto por #3; reschedule en boot mantiene el aviso fresco |

---

## Top 10 — Plan de cierre

Las prioridades están ordenadas por impacto sobre la narrativa de la
tesis (qué notará primero el tribunal). Las primeras cuatro tocan
flujos visibles al usuario que la tesis describe explícitamente.

### 1. Inferir horarios y frecuencia (CU-12 / RF-23 / RF-24) — ✅ COMPLETADO 2026-05-03

- [x] Nueva tabla `line_schedules` con PK `(line_id, day_bucket)`,
      tres cubos (weekday/saturday/sunday). Migración `e6f7a8b9c0d1`.
- [x] Algoritmo de inferencia puro en
      `packages/geodata/src/geodata/schedule.py` con regla
      "confiable si CV < 0.5" para RF-24.
- [x] Paso de pipeline `infer_schedules` integrado al runner.
- [x] `LineRead.schedules: list[DayScheduleRead]`, expuesto en
      `GET /lines/{id}` y `GET /lines/`.
- [x] Tests: 12 unitarios (geodata), 5 integración (pipeline), 5 endpoint
      (server), 1 e2e completo. Todos pasan.

Plan detallado: [01-infer-schedules.md](01-infer-schedules.md).

### 2. Mostrar tarifa estimada y frecuencia en planificación (RF-03 / RF-04 / RF-30) — ✅ COMPLETADO 2026-05-03

- [x] `fare_bob`, `frequency_min` añadidos a `DirectionsLeg`;
      `total_fare_bob` a `DirectionsResponse`.
- [x] Helper `services/line_metadata.py` con `estimate_fare_bob` y
      `current_headway_min` (usa el cubo del día actual de #1).
- [x] `directions.py` populá ambos por bus-leg, suma fares para total.
- [x] Badges en `explore.tsx` — chip por línea con frecuencia, total
      en el header del card, fare+frecuencia en cada bus leg del detail.
- [x] Tests: 13 unitarios para `line_metadata`, 3 Playwright e2e
      (`directions-fare-frequency.spec.ts`). Suite Playwright completa
      21/21 sin regresiones.

**Pendiente (deliberadamente fuera de alcance de #2):** mostrar
fare/frequency en `favorites.tsx` — los saved trips guardan el JSON
crudo de la `DirectionsResponse` así que ya viaja el dato; basta con
renderizarlo de la misma forma. Lo trato como gap chico al cerrar #3.

### 3. Hora de salida + notificación de inicio (CU-04 / RF-32 / CU-14 / RF-36 / RF-37) — ✅ COMPLETADO 2026-05-03

- [x] Columna `departureTime` (text HH:mm) en `savedTrips`, migración
      drizzle `0007_lame_mercury.sql`.
- [x] Modal `save-trip-modal.tsx` reemplazando el `Alert.alert` con
      input opcional de hora + validación HH:mm.
- [x] Scheduler local en `services/trip-notifications.ts` —
      `DATE` trigger para `one_time`, `CALENDAR` con `repeats:true`
      para `commute`. Lazy-import de `expo-notifications` para no
      romper el bundle web.
- [x] `rescheduleAllSavedTrips()` en `app/_layout.tsx` (componente
      `PostBootEffects` montado bajo `DatabaseProvider`).
- [x] `buildNotificationContent` consulta `GET /detours/active/{line_id}`
      al programar e incluye aviso "⚠ Desvío activo: …" en el body.
- [x] Tests: 4 Playwright e2e (validación HH:mm, persistencia +
      badge en favoritos), TC-14..17 en Anexo G del Plan + Capítulo
      III de la tesis para validación nativa pareada.
- [x] **Bonus:** parche `expo-sqlite+16.0.10.patch` que arregla un
      bug de truncación en `WorkerChannel.ts` (escribir
      `Uint32Array([length])` a un `Uint8Array` solo escribía el
      byte bajo; resultados > 255 bytes se truncaban). Wired vía
      `patch-package` (script `postinstall`).

### 4. UI de confirmación de tarifa con opciones (CU-09 / RF-26 / RF-28) — ✅ COMPLETADO 2026-05-03

- [x] `LineFareRead.common_amounts: list[CommonAmountRead]` añadido,
      populado por `_common_amounts` (top 4 montos por frecuencia).
- [x] `FareSource` enum (`REGISTRATION` / `CONFIRMATION`) en el modelo
      `FareReport`, migración `f7a8b9c0d1e2`.
- [x] `api.getLineFares()` y `api.submitFareReport({source})`.
- [x] Chips en `save-record-modal.tsx` antes del input libre:
      tap → autocompleta el monto y marca `source=confirmation`;
      escribir manualmente → `source=registration`.
- [x] Tests: 5 server pytest (orden por frecuencia, cap a 4, default
      registration, override a confirmation), 3 Playwright e2e
      (chips visibles, tap → confirmation, type → registration).
      Suite completa 28/28 verde, server 107/109 (las 2 voting
      pre-existentes).

### 5. Probar push end-to-end en dispositivos físicos (RF-35 / CU-13)

- [ ] `cd app && npx expo install expo-notifications && npm install`
- [ ] `eas build --profile development --platform ios` y/o android.
- [ ] Instalar en dos teléfonos físicos.
- [ ] Ejecutar TC-11, TC-12, TC-13 según `document/test_plan.typ`
      Anexo G.
- [ ] Documentar resultados en la sección "Pruebas manuales de humo"
      del capítulo III.

### 6. Detección de cambio significativo de ruta (RF-19) — ✅ COMPLETADO 2026-05-03

**Decisión de diseño:** el sistema solo publica rutas que caben en un
único polilínea continuo. Si la reconstrucción produce más de un
fragmento, la línea se queda sin ruta (o con la activa intacta) hasta
que haya datos suficientes para una geometría continua. Esto evita
toda la complejidad de comparar y migrar votos entre topologías
fragmentadas, a costa de que algunas líneas tarden más en tener su
primera ruta publicada.

- [x] Columna `last_compared_at` en `Route` + migración
      `a8b9c0d1e2f3`.
- [x] Migración `b9c0d1e2f3a4` marca como `SUPERSEDED` cualquier ruta
      activa heredada con `fragment_count > 1` para forzar la
      invariante "single-fragment" retroactivamente.
- [x] `_save_reconstruction` rechaza GeoJSON con `len(features) != 1`
      (defensa adicional al pre-check en `execute`).
- [x] `_existing_active_route(db, line_id)` devuelve la única ruta
      activa de la línea o `(None, [])` (defensivo: si encuentra
      multi-fragmento por error, también devuelve `None`).
- [x] `execute()`:
      - rechaza candidatas fragmentadas (cuenta en
        `lines_skipped_fragmented`); la activa (si existe) no se toca;
      - sin activa → crea v1;
      - con activa → Fréchet sobre los polilíneas, `< 50m` bumpea
        `last_compared_at`, `≥ 50m` supersede + nueva versión.
- [x] Métricas en el dict de retorno: `lines_unchanged`,
      `lines_superseded`, `lines_skipped_fragmented`,
      `change_threshold_m`. Visible en `PipelineStepResult.stats`
      para futura UI de historial (ej. Prefect).
- [x] 10 tests pytest cubriendo: `_existing_active_route` (4 casos:
      con datos, sin ruta, ignora `SUPERSEDED`, defensivo
      multi-fragmento); `execute` (creación inicial, unchanged,
      supersede por gran cambio, threshold configurable, default 50m,
      candidata fragmentada rechazada). Pipeline 15/15, server
      107/109 (los 2 fallos preexistentes son de auth en voting,
      no relacionados).

### 7. Detección automática de ramales (OE-4) — ✅ COMPLETADO 2026-05-03

**Decisiones de diseño:** ni Opción A (mapear ramal a `direction`) ni
Opción B (añadir `branch_name` editable por el usuario). Ambas tenían
problemas: A no captura ramales que comparten origen/destino y B
depende de que el usuario sepa qué etiqueta poner. La solución
elegida: **detección automática desde los trazos** + **identidad
humana derivada de geometría** (no de etiquetas internas).

Decisiones tomadas durante la implementación:
- **Algoritmo de clustering:** complete-linkage agglomerativo sobre
  Fréchet pares de trazos (200m default). Justificación: evita el
  problema de chaining donde un trazo ruidoso puente fusiona dos
  ramales reales. Validado contra escenarios sintéticos (test
  unitario `test_complete_linkage_resists_chaining`).
- **Estabilidad de etiquetas entre ejecuciones:** best-match-wins
  cuando dos clusters nuevos quieren heredar la misma etiqueta
  existente — el más cercano gana, el otro recibe etiqueta fresca.
- **`ramal_label` nunca se renderiza al usuario** (decisión #5): la
  identidad de cada ramal se muestra como `endpoint_zones` (Beijing →
  Sacaba) + `street_summary` (Av. Beijing · Av. América · …). Los
  labels internos (`main`, `r2`, `r3`) son solo claves de DB.
- **Descriptores crowdsourced** con UX "vote-on-existing-first":
  cuando un usuario quiere agregar una descripción, primero ve las
  existentes con chips de upvote; solo después de "Ninguna describe
  esta línea" aparece el TextInput. Dedup automático server-side por
  `text_normalized` con respuesta 409 que devuelve el descriptor
  existente para que el cliente ofrezca votarlo.
- **Integración en el flujo de votación:** después de votar la última
  sección, si la línea tiene ≥2 ramales activos, se muestra el
  pantallazo de descriptores scoped al Route que el usuario acaba de
  confirmar (momento de máxima intención). Single-ramal → se salta.

Implementación (Deliverables A/B/C):

- [x] **A1**: Columna `Route.ramal_label` + índice único parcial
      `(line_id, ramal_label) WHERE status != 'SUPERSEDED'`. Migración
      `c0d1e2f3a4b5`.
- [x] **A2**: Módulo `geodata/ramales.py` con
      `cluster_traces_into_ramales` (complete-linkage hierarchical
      agglomerativo). 8 tests unitarios.
- [x] **A3**: Pipeline `execute()` rediseñado: cluster → reconstrucción
      por cluster → decisión RF-19 por ramal. Helper
      `_load_existing_ramales`. Counters nuevos: `ramales_created`,
      `ramales_unchanged`, `ramales_superseded`,
      `lines_with_multiple_ramales`. 14 tests unitarios.
- [x] **A4**: Notebook `transit-lab/07_ramales.py` con escenarios
      sintéticos (3 ramales de línea 230) y slider de threshold para
      calibrar contra ruido GPS realista. Genera figuras de la
      sección de metodología.
- [x] **A5**: 5 tests de integración con clustering real sobre trazos
      ruidosos generados por `geodata.simulate.generate_tracks`.
- [x] **A6**: Escenario "230 con dos ramales" agregado al dev seed
      (`pipeline/seed.py`). `uv run seed-dev` + pipeline → línea 230
      con 2 Routes activos.
- [x] **B1**: Columnas `Route.street_summary` + `Route.endpoint_zones`
      (JSONB). Migración `c1d2e3f4a5b6`.
- [x] **B2**: Módulo `geodata/streets.py` con `summarise_streets`
      (filtro por longitud mínima de 200m descarta cross-streets) y
      `resolve_endpoint_zones` (Nominatim, tolera fallos). 12 tests
      unitarios. Poblados en `_save_reconstruction`.
- [x] **B3**: Schemas `RamalSummary` + `RouteRead.street_summary` +
      properties por feature en `get_line_route`. Mobile
      `explore.tsx` muestra "Beijing → Sacaba" + primeras 4 calles +
      badge "N ramales" para multi-ramal. **Cierra RF-07**.
- [x] **B4**: 6 tests server-side de las respuestas API ramal-aware.
- [x] **C1**: Modelos `RamalDescriptor` + `RamalDescriptorVote` con
      unique constraints (`(route_id, text_normalized)` y
      `(descriptor_id, device_id)`). 4 endpoints (list, create,
      upvote, unvote) con normalización de texto y respuesta 409.
      Migración `d2e3f4a5b6c7`. 9 tests server-side.
- [x] **C2**: Componente `app/components/ramal-descriptors-screen.tsx`
      con UX vote-on-existing-first, optimistic updates,
      pulse-highlight del descriptor existente cuando llega 409.
      Clase `ApiError` para manejo tipado del 409. Header del
      componente identifica el ramal sin renderizar `ramal_label`.
      Integrado en `section-vote-screen.tsx` como step después de
      votar (solo cuando línea tiene ≥2 ramales).
- [x] **E2E**: 4 tests Playwright en
      `app/e2e/ramal-descriptors.spec.ts` cubriendo: aparición de la
      pantalla en línea multi-ramal, upvote de existente, flujo
      "ninguna describe → typing → submit", "Listo" → resumen.

**Test status final:** pipeline 26/26, geodata 60/60, server 122/124
(2 fallos preexistentes en voting/auth no relacionados), Playwright
4/4. Ruff + tsc limpios en lo modificado.

**Bug latente corregido en el camino:** `_save_reconstruction`
accedía a los edges de Valhalla con sintaxis de atributo
(`edge.begin_shape_index`) cuando son dicts. Nunca había crasheado
porque todos los tests mockeaban `trace_match` para devolver `None`.

### 8. CU-08 "Registrar tarifa" (con identificación automática de zonas) — ✅ COMPLETADO 2026-05-03

**Decisión de diseño:** no se construye una pantalla independiente
para "registrar tarifa sin grabar". El caso de uso CU-08 se cubre con
el flujo post-grabación enriquecido, donde el sistema **identifica**
los municipios de origen/destino desde las coordenadas GPS y se los
muestra al usuario antes de la confirmación. El use case en la tesis
se refinó para reflejar honestamente este comportamiento (pasos 2 y 3
ahora dicen "Identificar" en lugar de "Seleccionar").

**Justificación pedagógica:** pedir al usuario que elija municipios
desde un dropdown es alta fricción (no conoce las fronteras
administrativas, los dropdowns en mobile son incómodos) y menos
preciso que la geolocalización GPS — el usuario podría declarar
estar en Sacaba cuando en realidad estaba en Cercado. La
identificación automática es una *feature*, no un workaround.

Implementación:

- [x] Schema `ZoneResolveRequest`/`ZoneResolveResponse` y endpoint
      `POST /fares/zones/resolve` (servidor).
- [x] Helper `_resolve_zone` reutilizado del flujo de submit; el
      endpoint solo hace preview (no persiste).
- [x] 2 tests pytest del endpoint (puntos dentro/fuera de zonas
      definidas + validación de input).
- [x] `api.resolveFareZones` en el cliente mobile.
- [x] `save-record-modal.tsx`: estado `identifiedZones`, llamada al
      preview en `prepareDetourConfirmation`, render del label
      "Tarifa para X → Y" arriba del input de tarifa.
- [x] Mock `**/fares/zones/resolve` en `e2e/mocks.ts` para que los
      tests Playwright existentes sigan funcionando.
- [x] Texto del prompt actualizado a literal del RF-27: "¿Cuánto
      salió tu pasaje? (opcional)".
- [x] Use case CU-08 actualizado en `document/final_document.typ`:
      pasos 2 y 3 → "Identificar"; párrafo introductorio explica que
      la identificación es automática y mostrada al usuario para
      verificación.

**Test status:** server `test_fares.py` 7/7 (5 originales + 2 nuevos),
ruff + tsc limpios. Deja CU-08, RF-25, RF-27, OE-3 todos en ✅.

### 9. Mostrar destinos textuales en líneas cercanas (RF-07) — ✅ COMPLETADO 2026-05-03 (junto con #7)

Cubierto como sub-deliverable del #7 (Deliverable B): los campos
`Route.endpoint_zones` (Nominatim) y `Route.street_summary` (Valhalla)
se exponen en `find_lines_nearby` y la card de explore.tsx los renderiza
("Beijing → Sacaba" + las primeras 4 calles).

### 10. Programar pipeline automáticamente (CU-11) — ✅ COMPLETADO 2026-05-03

**Decisión de diseño:** scheduler híbrido **evento + cron**, sin
orquestador externo dedicado. Se evaluó Prefect (orquestador moderno
con UI y triggers event-driven nativos) pero se descartó para el
alcance del proyecto: agrega un servicio always-on adicional, duplica
parcialmente el tracking de `PipelineRun`/`PipelineStepResult` ya
existente, y la mayoría de los pasos son agregaciones por línea que
no se benefician de event-driven puro. La arquitectura actual queda
diseñada para migrar a Prefect en el futuro sin reescribir los pasos
(documentado en la sección de Trabajos Futuros del capítulo de
Despliegue).

Implementación:

- [x] **Bug latente del runner corregido** durante los tests previos:
      `db.rollback()` en el except revertía la asignación
      `result.status = FAILED` antes de poder commitearla, dejando
      pasos fallidos como `RUNNING` indefinidamente. Fix: rollback
      primero, luego asignar status + error_message + ended_at,
      luego `db.add(result)` y commit.
- [x] **Trigger por evento** —
      `server/services/pipeline_trigger.py:run_clean_traces_for_line`
      abre una `SessionLocal` fresca y ejecuta `run_pipeline(steps=
      ["clean_traces"], trigger="event:recording_end")`. Encolado vía
      `BackgroundTasks` desde `server/routes/recordings.py` cuando
      una sesión se cierra con línea asignada. El usuario obtiene
      retroalimentación rápida ("mi viaje aparece como Trip limpio en
      segundos") sin esperar al cron.
- [x] **Servicio one-shot `pipeline`** en
      `infra/deploy/docker-compose.yml` con perfil `jobs` (no se
      inicia con `compose up`; se invoca con
      `docker compose --profile jobs run --rm pipeline run --steps ...`).
      Reusa la imagen del `server` extendida con el paquete pipeline.
- [x] **Cron del host** —
      `infra/deploy/cron/crontab.example` documenta la cadencia:
      agregación pesada cada 6h, inferencia de horarios diaria,
      housekeeping diaria, endpoints de cleanup
      (`/detours/cleanup`, `/recordings/cleanup/stale`) diariamente.
- [x] **Documentación de despliegue** en
      `document/final_document.typ` (sección "Despliegue" del Capítulo
      II): topología de servicios, programación del pipeline,
      telemetría/trazabilidad de ejecuciones via
      `PipelineRun`/`PipelineStepResult`, trabajos futuros (migración
      a Prefect).
- [x] **README operacional** en `infra/deploy/cron/README.md`:
      instalación, comandos manuales, tabla de cadencias, query de
      historial.
- [x] **Tests** — 2 tests nuevos en `server/tests/test_recordings.py`
      verifican que `BackgroundTasks` encola
      `run_clean_traces_for_line` con el `line_id` correcto al cerrar
      una grabación, y que sesiones sin línea no disparan el pipeline.

**Test status:** server 126 (era 124, +2), pipeline 49.

**Cubre además los hallazgos transversales:**
- ✅ "Cleanup endpoints requieren scheduler" — incluidos en el
  crontab.example.
- ✅ "resolve_*.py periodicidad" — corren cada 6h en el cron
  agregado.

---

## Hallazgos transversales (sutiles)

Estos no encajan en una sola fila pero el tribunal los puede notar:

- [ ] `LineUpdate` schema y `PATCH /lines/{id}` existen pero
      **ninguna pantalla los llama**. Nota: el aspecto de OE-4 sobre
      ramales y actualización del *recorrido* ya está cubierto por #7
      (detección automática + supersede por ramal). Lo que queda
      pendiente es UI para editar metadata de la línea (nombre,
      descripción, tipo) — caso de uso menor.
- [ ] `LineSubscription.kind` solo usa `COMMUTE` — modelo
      sobre-diseñado para una sola variante. **Decisión:** dejar como
      está y mencionarlo en el capítulo de Diseño como extensibilidad
      futura, o restringir el enum a una constante.
- [x] ~~`POST /detours/cleanup` y `/recordings/cleanup/stale` requieren
      invocación manual~~ → cubierto por #10 (incluidos en
      `infra/deploy/cron/crontab.example` con cadencia diaria).
- [x] ~~`confidence_pct` de un desvío usa fórmula simplista que
      ignora `confirmed_count`~~ → cubierto el 2026-05-03: nuevo
      helper `server/services/detour_confidence.py` combina decay
      lineal por tiempo (14 días) con boost log-shaped por
      corroboración (1 confirmador → 50 %, 3 → 68 %, 10 → 88 %,
      saturación asintótica). Refactorizado en
      `schemas/detour.py` y `schemas/directions.py`. 11 tests cubren
      puntos de referencia + monotonía + caps.
- [x] ~~El voting necesita scheduler regular para promover Routes~~ →
      cubierto por #10 (resolve_edge_votes + resolve_routes +
      resolve_line_votes corren cada 6h en el cron) y por la nueva
      step `resolve_routes` (gap detectado durante #10: ningún paso
      promovía Route → CONFIRMED, lo que dejaba a `find_lines_nearby`
      sin rutas con `include_pending=False`).

---

## Estado actual del trabajo

- **Auditoría completada**: 2026-05-02
- **Push notifications (Fases 1–3)**: implementadas y con tests
  unitarios + integración pasando.
- **Push notifications Fase 4 (test físico)**: pendiente — depende de
  Top 10 #5.
- **Capítulo III de la tesis**: estructura completa con TC tables,
  placeholders para resultados de ejecución.
- **Plan de Pruebas v1.1**: Anexo G (checklist de humo) añadido,
  exclusión de "Notificaciones push" retirada.

Total de items con estado distinto a ✅ Implementado:
**0 ❌ Faltantes, 1 🟡 Parcial** sobre 56 requisitos analizados
(OE+CU+RF) — bajó desde el conteo inicial de 8/9 tras cerrar #1, #2,
#3, #4, #6, #7, #8, #9, #10 + el polish de `confidence_pct`. El único
parcial restante es **CU-13 / RF-35** (push end-to-end no probado en
dispositivos físicos — pendiente #5), que es un trabajo de validación
manual que requiere hardware físico (iOS + Android) y un build EAS,
no más código del lado del sistema.
