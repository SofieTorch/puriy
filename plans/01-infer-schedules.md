# Plan #1 — Inferir horarios y frecuencia de servicio

Cierra: **CU-12, RF-23, RF-24** (y deja preparado el camino para
**RF-04** que se cierra en #2).

## Qué entra en este plan y qué no

**Sí entra:**
- Algoritmo de inferencia de horario (`service_start_at`,
  `service_end_at`) y frecuencia (`headway_min`) por línea.
- Decisión de "frecuencia confiable" según coeficiente de variación
  (RF-24 — si no es confiable, solo publicamos horario).
- Persistencia en `Line` (columnas nuevas + migración).
- Paso de pipeline `infer_schedules` integrado al runner existente.
- `LineRead` y `LineNearby` exponen los nuevos campos.
- Pruebas unitarias del algoritmo, integración del paso de pipeline,
  e2e API contra base de datos real de prueba.

**No entra (pertenece a #2):**
- UI de la app mostrando frecuencia/horario en `explore.tsx` o
  `favorites.tsx`.
- Inyección de `frequency_min` en `DirectionsLeg` y suma para
  `total_frequency`. Vamos a *exponer* el dato en `LineRead`, pero
  consumirlo en `/directions/` se hará junto con la integración de
  tarifa porque las dos modificaciones tocan el mismo schema y el
  mismo handler.

## Decisiones de diseño

### Granularidad temporal: tres cubos (weekday / saturday / sunday)

Calculamos un horario y una frecuencia distintos para cada uno de tres
cubos: días laborables (L–V), sábado y domingo. Esto refleja el patrón
real del transporte público de Cochabamba (los micros operan menos
horas y con menor frecuencia los fines de semana) sin llegar a la
granularidad por día individual, que requeriría tener mucho más datos
por línea para ser estadísticamente confiable.

Los días feriados se tratan como el día de la semana en que caen
(v1). Documentar como simplificación en el capítulo de Diseño.

### Zona horaria: convertir UTC → America/La_Paz para el cómputo

`TripSession.started_at` es `datetime.utcnow()` (naïve UTC). Para
calcular "horas de servicio" como las percibe un usuario tenemos que
convertir a la zona local (UTC-4, sin DST). Esto se hace solo dentro
del paso de inferencia; lo persistido en `Line` es la hora **local**
(porque eso es lo que el usuario va a ver: "el servicio inicia a las
06:00").

### Definición de "frecuencia confiable" (RF-24)

Para cada línea con ≥ N sesiones:
- Convertir `started_at` a hora local.
- Agrupar por día calendario, filtrar días con < `min_sessions_per_day`
  (default 5).
- Para cada día válido, ordenar por hora y calcular las diferencias
  entre arranques consecutivos (en minutos). Filtrar diferencias > 60
  min (probablemente cierre/apertura, no headway real).
- Concatenar las diferencias de todos los días válidos.
- Calcular **mediana** (más robusta que media frente a outliers) y
  **coeficiente de variación** (`stddev / mean`).
- **Es confiable si CV < 0.5** (umbral configurable). Si confiable,
  publicar `headway_min` redondeado a entero. Si no, dejar
  `headway_min = NULL`.

### Definición de horas de servicio

Independiente de la frecuencia (siempre la calculamos si hay datos):
- Convertir `started_at` a hora local, extraer la componente `time`.
- `service_start_at = percentil 5` de los times.
- `service_end_at = percentil 95` de los times.
- Solo se persiste si hay ≥ 10 sesiones (umbral pequeño porque queremos
  cobertura amplia).

## Cambios al modelo de datos

### Nueva tabla `line_schedules`

Decidimos modelar los tres cubos como filas de una tabla aparte (no
como nueve columnas en `Line`) porque (a) deja la tabla `Line` limpia,
(b) es trivialmente extensible si después queremos cubos por día de
la semana o por feriado, y (c) la elección es defendible en el
capítulo de Diseño como un caso aplicado de normalización.

```python
# packages/database/src/database/models/line.py (o nuevo line_schedule.py)
from datetime import time
from enum import Enum

class DayBucket(str, Enum):
    WEEKDAY = "weekday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class LineSchedule(SQLModel, table=True):
    __tablename__ = "line_schedules"

    line_id: UUID = Field(foreign_key="lines.id", primary_key=True)
    day_bucket: DayBucket = Field(primary_key=True)
    service_start_at: Optional[time] = Field(default=None)
    service_end_at: Optional[time] = Field(default=None)
    headway_min: Optional[int] = Field(default=None)
    inferred_at: datetime = Field(default_factory=datetime.utcnow)

    line: Optional["Line"] = Relationship(back_populates="schedules")


# In Line:
schedules: list["LineSchedule"] = Relationship(back_populates="line")
```

PK compuesta `(line_id, day_bucket)` garantiza que cada línea tiene a
lo más una fila por cubo. `time` (sin tz) representa la hora local de
Cochabamba.

### Migración alembic

Una sola revisión que crea `line_schedules` con su FK a `lines.id` y
su PK compuesta. No se modifica la tabla `lines`.

## Algoritmo (pure functions, testeables aisladamente)

Ubicación: `packages/geodata/src/geodata/schedule.py`

```python
from dataclasses import dataclass
from datetime import datetime, time, timezone, timedelta
from enum import Enum
from typing import Optional

LOCAL_TZ = timezone(timedelta(hours=-4))  # America/La_Paz (sin DST)
DEFAULT_MIN_SESSIONS_TOTAL = 10
DEFAULT_MIN_SESSIONS_PER_DAY = 5
DEFAULT_HEADWAY_CV_THRESHOLD = 0.5
DEFAULT_MAX_HEADWAY_MINUTES = 60  # over this = day boundary, not headway


class DayBucket(str, Enum):
    WEEKDAY = "weekday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


@dataclass(frozen=True)
class ScheduleInference:
    service_start_at: Optional[time]
    service_end_at: Optional[time]
    headway_min: Optional[int]
    headway_cv: Optional[float]   # for diagnostics, not persisted
    n_sessions: int
    n_valid_days: int


def day_bucket_of(local_dt: datetime) -> DayBucket:
    """0=Mon … 5=Sat, 6=Sun."""
    weekday = local_dt.weekday()
    if weekday == 5: return DayBucket.SATURDAY
    if weekday == 6: return DayBucket.SUNDAY
    return DayBucket.WEEKDAY


def infer_schedule_for_bucket(starts_local: list[datetime]) -> ScheduleInference:
    """Compute service hours + headway for ONE day bucket."""
    ...


def infer_line_schedule(starts_utc: list[datetime]) -> dict[DayBucket, ScheduleInference]:
    """Convert UTC → local, bucket by day type, infer per bucket."""
    buckets: dict[DayBucket, list[datetime]] = {b: [] for b in DayBucket}
    for dt_utc in starts_utc:
        dt_local = dt_utc.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
        buckets[day_bucket_of(dt_local)].append(dt_local)
    return {b: infer_schedule_for_bucket(s) for b, s in buckets.items()}
```

Cada cubo se infiere de manera independiente, lo que significa que un
cubo puede tener `headway_min = 12` y otro `None` si no hay datos
suficientes (RF-24).

## Paso de pipeline

Ubicación: `packages/pipeline/src/pipeline/steps/infer_schedules.py`

Pseudo-código:

```python
def infer_schedules(db: Session, *, run: PipelineRun) -> None:
    lines = db.execute(
        select(Line).where(Line.status == LineStatus.APPROVED)
    ).scalars().all()
    now = datetime.utcnow()
    for line in lines:
        starts = db.execute(
            select(TripSession.started_at).where(
                TripSession.line_id == line.id,
                TripSession.status.in_([
                    SessionStatus.COMPLETED, SessionStatus.PROCESSED,
                ]),
            )
        ).scalars().all()
        per_bucket = infer_line_schedule(starts)
        for bucket, result in per_bucket.items():
            sched = db.get(LineSchedule, (line.id, bucket)) or LineSchedule(
                line_id=line.id, day_bucket=bucket,
            )
            sched.service_start_at = result.service_start_at
            sched.service_end_at = result.service_end_at
            sched.headway_min = result.headway_min
            sched.inferred_at = now
            db.merge(sched)
    db.commit()
```

Hook al runner — añadir el paso después de `reconstruct_routes` (no
depende de él, pero por orden lógico va en la fase de "consolidación
de la línea").

## API surface

`server/schemas/line.py`:

```python
class DayScheduleRead(BaseModel):
    day_bucket: str   # "weekday" | "saturday" | "sunday"
    service_start_at: Optional[time] = None
    service_end_at: Optional[time] = None
    headway_min: Optional[int] = None
    inferred_at: Optional[datetime] = None


class LineRead(BaseModel):
    ...
    schedules: list[DayScheduleRead] = []
```

`schedules` es siempre una lista de hasta 3 elementos (puede tener
menos si nunca se infirió un cubo determinado, p. ej. si la línea no
tiene sesiones registradas en sábado). Los reads existentes
(`LineRead`, `LineNearbyRead`, etc.) se extienden — no se añaden
endpoints.

## Plan de pruebas

### Pruebas unitarias (geodata)

`packages/geodata/tests/test_schedule.py`:

**Single-bucket (`infer_schedule_for_bucket`):**
- `test_empty_input_returns_all_none`.
- `test_few_sessions_only_service_hours`: 3 sesiones → headway None.
- `test_regular_headway_is_confident`: 30 sesiones a intervalos de
  10 min → headway_min = 10, CV = 0.
- `test_irregular_headway_is_unreliable`: 30 sesiones con headways
  variables (5, 25, 5, 25, …) → headway_min = None (CV > 0.5).
- `test_service_hours_robust_to_outliers`: 30 sesiones entre 06:00 y
  22:00 + una a 03:00 → service_start_at ≈ 06:00.
- `test_max_headway_filter_excludes_day_gaps`: gaps > 60 min se
  excluyen del cálculo.

**Bucketing (`infer_line_schedule` / `day_bucket_of`):**
- `test_weekday_dt_goes_to_weekday_bucket`: martes → WEEKDAY.
- `test_saturday_dt_goes_to_saturday_bucket`.
- `test_sunday_dt_goes_to_sunday_bucket`.
- `test_buckets_are_independent`: dataset con sesiones distintas en
  weekday y sunday → cubos retornan resultados distintos.
- `test_utc_to_local_conversion_in_bucketing`: una sesión a las
  03:00 UTC del lunes (= sábado 23:00 local en realidad solo si
  fuera UTC+8, en nuestro caso UTC-4 = domingo 23:00 → ojo). Caso
  borde: UTC-4 cambia el día solamente si la hora UTC < 04:00 — un
  test específico para una sesión a las 02:00 UTC del lunes (=
  domingo 22:00 local) que debe ir al cubo `SUNDAY`, no `WEEKDAY`.

**Timezone:**
- `test_timezone_conversion`: input UTC, output local en
  `service_start_at`.

### Pruebas de integración (pipeline)

`packages/pipeline/tests/test_infer_schedules.py`:

- `test_pipeline_step_populates_three_buckets`: seed Line + 30
  TripSessions distribuidas en weekday/saturday/sunday → correr paso
  → tres filas en `line_schedules` con valores razonables.
- `test_pipeline_step_skips_lines_without_data`: Line sin sessions
  → ninguna fila creada en `line_schedules`, no crash.
- `test_pipeline_step_idempotent`: correr dos veces seguidas →
  mismo número de filas, `inferred_at` se actualiza.
- `test_pipeline_step_only_completed_sessions`: sesiones canceladas
  no entran al cálculo.
- `test_partial_bucket_data`: línea con sesiones solo en weekday
  → solo se inserta la fila WEEKDAY, no SATURDAY ni SUNDAY (o se
  insertan con campos NULL, según definamos al implementar).

### Pruebas e2e (server API)

`server/tests/test_lines.py` (extender):

- `test_get_line_includes_schedules_array`: línea con 3 cubos
  inferidos → GET /lines/{id} devuelve `schedules: [...]` con los 3
  elementos.
- `test_get_line_no_schedule_returns_empty_array`: línea sin
  inferencia → `schedules: []`.
- `test_get_line_partial_schedules`: línea con solo el cubo WEEKDAY
  → `schedules` tiene 1 elemento.
- `test_nearby_lines_includes_schedules`: GET /lines/nearby/
  devuelve `schedules` por línea.

### Prueba e2e de pipeline + API combinados

`server/tests/test_schedule_e2e.py` (nuevo):

- Seed: una Line con sesiones distribuidas en los 3 cubos:
  - Weekday: 30 sesiones de 06:00 a 22:00 con headway de 8 min.
  - Saturday: 20 sesiones de 07:00 a 20:00 con headway de 12 min.
  - Sunday: 10 sesiones de 08:00 a 18:00 con headway irregular
    (inconfiable).
- Invocar el paso de pipeline directamente.
- GET /lines/{id} → assert:
  - `schedules` tiene 3 elementos.
  - WEEKDAY: `headway_min == 8`, `service_start_at == 06:00`.
  - SATURDAY: `headway_min == 12`, `service_start_at == 07:00`.
  - SUNDAY: `headway_min == None` (inconfiable), pero
    `service_start_at == 08:00` se mantiene.

(Lo de Playwright queda para #2 cuando haya UI que verificar.)

## Orden de ejecución

| # | Paso | Archivos | Tiempo estimado |
|---|---|---|---|
| 1 | Nuevo modelo `LineSchedule` + relación + alembic migration | `models/line.py` (o nuevo), `alembic/versions/` | 45 min |
| 2 | Inferencia pura + bucketing + tests unitarios | `geodata/schedule.py`, `tests/test_schedule.py` | 2.5 h |
| 3 | Paso de pipeline + tests integración (3 cubos) | `pipeline/steps/infer_schedules.py`, `pipeline/tests/` | 2 h |
| 4 | Schemas (DayScheduleRead) + endpoint tests | `server/schemas/line.py`, `server/tests/test_lines.py` | 1 h |
| 5 | Test e2e pipeline → API con tres cubos | `server/tests/test_schedule_e2e.py` | 1 h |
| 6 | Run migration + suite completa + ruff | — | 30 min |

Total: **~7.5 horas**.

## Cosas que voy a confirmar mientras implemento

- [ ] Si `packages/pipeline/tests/` no existe, hay que crearlo con su
      `pyproject.toml` o agregar `pytest` como dev dep al package.
      Confirmar con `ls` antes.
- [ ] El `runner.py` actual cómo orquesta los pasos. Si es una lista
      ordenada, añadir el paso al final; si es un grafo, modelarlo
      como dependiente solo del estado base de las sesiones.
- [ ] Si `LineNearbyRead` es un schema separado o reusa `LineRead`.
- [ ] El cliente Drizzle del app: ¿el cambio de schema rompe el
      cache local de líneas? Si sí, bumpear la versión del schema
      cliente y dejar que regenere.
- [ ] Verificar que la zona horaria UTC-4 se mantiene todo el año en
      Bolivia (no DST). Confirmado: Bolivia no observa DST desde 1932.

## Riesgos y mitigaciones

- **Pocos datos reales en la DB de desarrollo:** los tests usarán
  fixtures sintéticas, así que esto no bloquea. Pero al desplegar a
  producción los `service_start_at` quedarán en NULL hasta que
  acumulemos suficientes sesiones por línea. Documentar esto.
- **El umbral CV de 0.5 es arbitrario:** lo dejamos configurable y
  documentamos en el capítulo de Diseño que el valor se eligió
  empíricamente y puede ajustarse al observar el patrón real de los
  datos.
- **Sesiones nocturnas (líneas que operan 24h):** el filtro de
  "diferencias > 60 min se excluyen" funciona porque el cálculo de
  headway agrupa por día calendario; si una línea opera de 22:00 a
  04:00 los datos quedarán en dos días distintos y el cálculo será
  por separado. Aceptable para v1; mencionar.
