// =============================================================================
// Plan de Pruebas de Aceptación — TrufiMap
// Documento estructurado según IEEE 829-2008
// =============================================================================

#set document(
  title: "Plan de Pruebas de Aceptación",
  author: "Sofia Valeria Toro Chambi",
)

#set page(
  paper: "a4",
  margin: (x: 2.5cm, y: 2.5cm),
  header: align(right)[
    #text(size: 8pt, fill: gray)[
      _Plan de pruebas de aceptación — v1.0_
    ]
  ],
  footer: align(center)[
    #text(size: 8pt, fill: gray)[
      Página #context counter(page).display("1 de 1", both: true)
    ]
  ],
)

#set text(
  font: "Arial",
  size: 11pt,
  lang: "es",
  region: "bo",
)

#set par(
  justify: true,
  leading: 0.7em,
  first-line-indent: 0pt,
)

#set heading(numbering: none)

#show heading.where(level: 1): it => {
  block(below: 0.8em, above: 1.2em)[
    #text(size: 18pt, weight: "bold")[#it.body]
  ]
}

#show heading.where(level: 2): it => {
  block(below: 0.9em, above: 1.3em)[
    #text(size: 14pt, weight: "bold")[#it.body]
  ]
}

#show heading.where(level: 3): it => {
  block(below: 0.5em, above: 1.2em)[
    #text(size: 12pt, weight: "bold")[#it.body]
  ]
}

// Helper: styled table with header row
#let plan-table(columns: (), header: (), body: ()) = {
  table(
    columns: columns,
    align: left + horizon,
    stroke: 0.5pt,
    table.header(..header.map(h => [*#h*]), repeat: true),
    ..body.flatten(),
  )
}

// Helper: placeholder note (gray italic)
#let placeholder(body) = {
  text(fill: gray, style: "italic")[\[#body\]]
}

// =============================================================================
// COVER PAGE
// =============================================================================

#align(center)[
  #v(4cm)
  #underline(
    text(size: 22pt, weight: "bold")[
      PLAN DE PRUEBAS DE ACEPTACIÓN
    ]
  )

  #v(0.6cm)
  #text(size: 14pt)[
    SISTEMA MÓVIL MULTIPLATAFORMA BASADA EN CROWDSOURCING PARA LA RECOLECCIÓN Y CENTRALIZACIÓN DE INFORMACIÓN DE RUTAS DEL TRANSPORTE PÚBLICO EN EL ÁREA METROPOLITANA DE COCHABAMBA
  ]
  
  #v(1.2cm)
  #text(size: 11pt, style: "italic")[
    Documento estructurado según IEEE 829-2008

    (Standard for Software and System Test Documentation)
  ]

  #v(2cm)

  #plan-table(
    columns: (auto, 1fr),
    header: ("Campo", "Detalle"),
    body: (
      ("Proyecto",              [Sistema Móvil Multiplataforma Basada en Crowdsourcing para la Recolección y Centralización de Información de Rutas del Transporte Público en el Área Metropolitana de Cochabamba]),
      ("Autora",                [Sofia Valeria Toro Chambi]),
      ("Tutor académico",       [Javier Vásquez Cruz]),
      ("Universidad",           [Universidad Privada del Valle]),
      ("Carrera",               [Ingeniería de Sistemas Informáticos ISI]),
      ("Versión del documento", [1.1]),
      ("Fecha",                 [02/05/2026]),
    ),
  )
]

#pagebreak()

// =============================================================================
// CONTROL DE VERSIONES
// =============================================================================

= Control de versiones

Este documento se versiona explícitamente. Cualquier modificación posterior a
su aprobación inicial se registra en la siguiente tabla y motiva un incremento
de versión.

#plan-table(
  columns: (auto, auto, 1fr, 2fr),
  header: ("Versión", "Fecha", "Autor", "Descripción del cambio"),
  body: (
    ("1.0", "28/04/2026", [Sofia Toro Chambi], "Versión inicial."),
    ("1.1", "02/05/2026", [Sofia Toro Chambi],
      [Incorporación de la funcionalidad F-04 (notificaciones push de
      desvíos), retirada de la lista de funcionalidades excluidas en
      §5. Se adiciona el Anexo G (Checklist de pruebas manuales de humo)
      como instrumento adicional de validación pre-despliegue, ejecutado
      por la investigadora antes del estudio de campo. Las
      especificaciones detalladas de los casos de prueba migran al
      capítulo III (Pruebas de calidad) de la tesis para mejorar
      legibilidad por parte del tribunal evaluador; el presente plan
      mantiene la trazabilidad y la plantilla IEEE 829 (Anexo B) como
      referencia.]),
    ("",    "",             "",                                ""),
  ),
)

#pagebreak()
#outline()
#pagebreak()

// =============================================================================
// 1. IDENTIFICADOR
// =============================================================================

= 1. Identificador del plan de pruebas

Identificador del documento: *PP-2026-01*

Tipo de plan: Plan maestro de pruebas de aceptación con usuarios (User
Acceptance Testing).

Versión: 1.0

Este plan de pruebas se basa en la estructura definida por la norma
IEEE 829-2008 (Standard for Software and System Test Documentation), la cual
establece los componentes mínimos que debe contener un plan maestro de
pruebas. La norma fue posteriormente reemplazada por ISO/IEC/IEEE 29119-3,
cuyas directrices son consistentes con las aplicadas en este trabajo. Las
secciones del documento se han adaptado a la naturaleza individual del
proyecto: las secciones de responsabilidades y personal (12 y 13 de
IEEE 829) se han condensado, y la sección de aprobaciones (16) consiste en
la firma del tutor académico.

Este documento describe exclusivamente el plan de pruebas de aceptación con
usuarios. Las pruebas unitarias y de integración / sistema (end-to-end)
realizadas durante la fase de desarrollo se documentan directamente en el
capítulo correspondiente de la tesis.

// =============================================================================
// 2. INTRODUCCIÓN
// =============================================================================

= 2. Introducción

== 2.1. Propósito

El presente plan de pruebas tiene como propósito definir, organizar y
documentar las actividades de validación con usuarios reales que permitirán
verificar que la aplicación móvil cumple con los requisitos funcionales
establecidos en el capítulo de Análisis de la tesis. Las pruebas se centran
en la validación de las funcionalidades principales del sistema mediante un
estudio de campo con usuarios habituales del transporte público del área
metropolitana de Cochabamba.

== 2.2. Antecedentes

El proyecto consiste en una aplicación móvil que permite a los usuarios del
transporte público de Cochabamba mapear de forma colaborativa las rutas de
las líneas de buses, reportar desvíos temporales y reportar el fin de dichos
desvíos. Dado que en Cochabamba el transporte público es informal y no
existe información centralizada sobre las rutas, la única forma rigurosa de
validar el sistema es mediante pruebas de campo en condiciones reales de uso.

== 2.3. Alcance del plan

El presente plan cubre:

- La validación de las tres funcionalidades principales del sistema con
  usuarios reales.
- La definición de los criterios de éxito y fracaso para cada escenario de
  prueba.
- La planificación logística del estudio de campo (3 días, 20 participantes).
- La definición de los instrumentos de recolección de datos (instrumentación
  PostHog, cuestionario post-tarea).
- Los procedimientos para situaciones imprevistas durante la ejecución.

El presente plan *NO* cubre las pruebas unitarias, las pruebas de
integración / sistema (end-to-end), ni las pruebas de carga del backend, las
cuales se documentan por separado en el capítulo de Pruebas de la tesis.

== 2.4. Documentos de referencia

- IEEE Std 829-2008 — Standard for Software and System Test Documentation.
- ISO/IEC/IEEE 29119-3:2013 — Software and systems engineering — Software
  testing — Part 3: Test documentation.
- ISO/IEC 25010:2011 — Systems and software Quality Requirements and
  Evaluation (SQuaRE).
- Capítulo 4 (Análisis) de la tesis: especificación de casos de uso y
  requisitos funcionales.
- Capítulo 5 (Diseño) de la tesis: arquitectura del sistema y diseño de
  módulos.
- Capítulo 6 (Desarrollo) de la tesis: implementación y descripción de
  módulos.

== 2.5. Glosario y abreviaturas

#plan-table(
  columns: (auto, 1fr),
  header: ("Término", "Definición"),
  body: (
    ("UC",      "Caso de uso (Use Case). Descripción narrativa de una interacción entre un actor y el sistema para alcanzar un objetivo."),
    ("RF",      "Requisito Funcional. Especificación precisa y verificable de una capacidad que debe ofrecer el sistema."),
    ("F",       "Funcionalidad agrupada (Feature). Etiqueta de alcance que agrupa uno o más requisitos funcionales para fines de planificación de pruebas."),
    ("TC",      "Caso de prueba (Test Case). Conjunto de condiciones, datos y pasos para verificar el comportamiento de una funcionalidad."),
    ("UAT",     "User Acceptance Testing. Pruebas de aceptación con usuarios reales."),
    ("PostHog", "Plataforma de análisis de producto utilizada para registrar eventos de uso de la aplicación."),
    ("GPS",     "Global Positioning System. Tecnología utilizada por la aplicación para registrar la posición del usuario."),
  ),
)

// =============================================================================
// 3. ELEMENTOS A PROBAR
// =============================================================================

= 3. Elementos a probar

Los elementos sometidos a prueba en el presente plan corresponden a la
versión de la aplicación móvil identificada a continuación, junto con sus
servicios de backend asociados.

#plan-table(
  columns: (auto, 1.2fr, 1.5fr),
  header: ("Elemento", "Identificación / Versión", "Observaciones"),
  body: (
    ([Aplicación móvil], [Puriy v1.1.0], [Build de prueba instalado en dispositivos de los testers.]),
    ([Backend / API],    [https://puriy.sofietorch.dev/api v1.0], [Entorno de pruebas o producción según se defina.]),
    ([Base de datos],    [PostgreSQL esquema v#placeholder("X")], [Snapshot tomado al inicio del estudio.]),
    ([Instrumentación],  [PostHog proyecto #placeholder("ID")], [Eventos según especificación del Anexo D.]),
  ),
)

El identificador de versión del aplicativo y el commit hash se fijan al
inicio del estudio y no se modifican durante su ejecución. Cualquier cambio
requerido durante el estudio implica suspender las pruebas y emitir una
nueva versión del presente plan.

// =============================================================================
// 4. FUNCIONALIDADES A PROBAR
// =============================================================================

= 4. Funcionalidades a probar

El presente plan de pruebas cubre las funcionalidades listadas a
continuación. Cada funcionalidad se define por referencia a los requisitos
funcionales y casos de uso especificados en el capítulo de Análisis de la
tesis. Las descripciones detalladas no se reproducen aquí para evitar
duplicación documental.

#plan-table(
  columns: (auto, 2fr, 1.5fr, 1fr, 1.2fr),
  header: ("ID", "Funcionalidad", "Requisitos funcionales", "Casos de uso", "Nivel de prueba"),
  body: (
    ([F-01], [Mapeo de línea de transporte público], [RF-#placeholder("__"), RF-#placeholder("__"), RF-#placeholder("__")], [UC-#placeholder("__")], [UAT (campo)]),
    ([F-02], [Reporte de inicio de desvío],          [RF-#placeholder("__"), RF-#placeholder("__")], [UC-#placeholder("__")], [UAT (campo)]),
    ([F-03], [Reporte de fin de desvío],             [RF-#placeholder("__"), RF-#placeholder("__")], [UC-#placeholder("__")], [UAT (campo)]),
    ([F-04], [Notificaciones push de desvíos a usuarios con viaje recurrente], [RF-#placeholder("__")], [UC-13], [Humo manual (pareada)]),
    ([F-05], [Notificaciones locales programadas de inicio de ruta], [RF-32, RF-36, RF-37], [UC-14], [Humo manual (un dispositivo)]),
  ),
)

La columna "Nivel de prueba" indica el ámbito específico cubierto por el
presente plan. F-01 a F-03 se validan en el estudio de campo con usuarios;
F-04 se valida mediante una prueba de humo pareada ejecutada por la
investigadora con dos dispositivos (ver Anexo G), dado que su naturaleza
asíncrona y multi-usuario hace inviable su validación con un único
participante en el contexto del estudio de campo.

La trazabilidad completa entre casos de uso, requisitos funcionales,
funcionalidades y casos de prueba se presenta en la matriz de trazabilidad
del Anexo A.

// =============================================================================
// 5. FUNCIONALIDADES NO PROBADAS
// =============================================================================

= 5. Funcionalidades no probadas

Las siguientes funcionalidades del sistema están explícitamente fuera del
alcance del presente plan de pruebas, junto con la justificación
correspondiente:

#plan-table(
  columns: (auto, 1.5fr, 2fr),
  header: ("ID", "Funcionalidad", "Justificación de exclusión"),
  body: (
    ([F-#placeholder("__")], [Registro y autenticación de usuarios], [Validada mediante pruebas unitarias durante el desarrollo. Para el estudio de campo, las cuentas se preconfiguran.]),
    ([F-#placeholder("__")], [Panel de administración del backend], [No es una funcionalidad orientada al usuario final.]),
    ([F-#placeholder("__")], [#placeholder("Otra funcionalidad")], [#placeholder("Justificación")]),
  ),
)

// =============================================================================
// 6. ENFOQUE DE PRUEBAS
// =============================================================================

= 6. Enfoque de pruebas

== 6.1. Estrategia general

Las pruebas se realizan en condiciones reales de uso (campo) con usuarios
habituales del transporte público de Cochabamba. Cada participante ejecuta
una tarea distinta por día durante tres días consecutivos, abordando una
línea de transporte público asignada y utilizando la aplicación bajo un
protocolo controlado.

El estudio adopta un diseño longitudinal con el mismo grupo de participantes
a lo largo de los tres días. Esta decisión es deliberada y se justifica por
la dependencia funcional entre escenarios: el reporte de desvío del Día 2
requiere la existencia de una línea mapeada (Día 1), y el reporte de fin de
desvío del Día 3 requiere la existencia de un desvío reportado (Día 2).

== 6.2. Tipos de prueba aplicados

- *Pruebas funcionales:* verificación de que cada funcionalidad cumple con
  su requisito asociado.
- *Pruebas de usabilidad:* medición de la facilidad de uso percibida por
  el usuario, según criterios derivados de ISO 25010 (efectividad,
  eficiencia, satisfacción).
- *Pruebas de aceptación:* determinación de si el usuario considera que la
  aplicación cumple con su propósito.

== 6.3. Diseño del estudio de campo

#plan-table(
  columns: (1.2fr, 2fr),
  header: ("Parámetro", "Valor"),
  body: (
    ("Tamaño de muestra",                          "20 participantes"),
    ("Duración del estudio",                       "3 días consecutivos"),
    ("Diseño longitudinal",                        "Mismo grupo participa los tres días"),
    ("Compensación por participante",              "15 USD por día (45 USD total por participante completo)"),
    ("Línea de transporte por participante",       "Una línea asignada (controlada para distribución entre líneas)"),
    ("Tiempo estimado por día y participante",     "3 a 4 horas (incluye briefing, ejecución y cuestionario)"),
  ),
)

== 6.4. Distribución de escenarios por día

#plan-table(
  columns: (auto, 1.2fr, 2fr),
  header: ("Día", "Funcionalidad probada", "Tarea principal del participante"),
  body: (
    ([Día 1], [F-01 — Mapeo de línea],              [Recorrer una línea completa, grabando la ruta con la aplicación.]),
    ([Día 2], [F-02 — Reporte de inicio de desvío], [En la línea ya mapeada, reportar un desvío activo identificando dónde inicia y dónde termina.]),
    ([Día 3], [F-03 — Reporte de fin de desvío],    [Confirmar que el desvío reportado el día anterior ya no está activo.]),
  ),
)

== 6.5. Instrumentos de recolección de datos

Se emplean tres instrumentos complementarios:

+ *Instrumentación PostHog:* registro automático de eventos de uso de la
  aplicación (inicio y fin de tarea, errores, tiempos por paso). La
  especificación completa de eventos se incluye en el Anexo D.
+ *Datos del sistema (base de datos del backend):* registros generados
  por las tareas de los participantes (líneas mapeadas, desvíos reportados).
+ *Cuestionario post-tarea:* instrumento autoadministrado tras finalizar
  la tarea de cada día, con preguntas en escala Likert de 5 puntos
  (alineado con la observación del tutor) y campos abiertos. La estructura
  del cuestionario se incluye en el Anexo E.

== 6.6. Selección de la muestra

Se utiliza un muestreo no probabilístico por conveniencia, con criterios de
inclusión definidos. Esta decisión es coherente con el carácter exploratorio
del estudio y con los recursos disponibles para un trabajo de grado.

*Criterios de inclusión:*

- Mayor de 18 años.
- Usuario habitual del transporte público en Cochabamba (uso al menos
  semanal).
- Posee un teléfono inteligente con sistema operativo
  #placeholder("Android X.X+ / iOS X.X+") y plan de datos.
- Disponibilidad para participar los tres días del estudio.

*Criterios de exclusión:*

- Personas con relación profesional o personal cercana con la investigadora
  (para evitar sesgos).
- Personas que hayan participado en pruebas previas de la aplicación
  durante el desarrollo.

// =============================================================================
// 7. CRITERIOS DE ACEPTACIÓN
// =============================================================================

= 7. Criterios de aceptación

Los criterios de aceptación se definen a dos niveles: criterios por caso de
prueba (verifican el comportamiento individual del sistema) y criterios
globales del estudio (determinan si la validación se considera exitosa en
su conjunto).

== 7.1. Criterios por caso de prueba

Cada caso de prueba define explícitamente sus condiciones de éxito en su
especificación individual (ver Anexo B). En general, un caso de prueba se
considera aprobado (Pass) cuando:

- El resultado obtenido coincide con el resultado esperado especificado.
- Los eventos de PostHog asociados se registran correctamente.
- Los datos resultantes se persisten en la base de datos según lo
  especificado.

Un caso de prueba se considera fallido (Fail) cuando alguna de las
condiciones anteriores no se cumple, o cuando el sistema presenta un error
no anticipado durante su ejecución.

== 7.2. Criterios por escenario diario

#plan-table(
  columns: (auto, 2fr, 1.5fr),
  header: ("Día", "Métrica objetiva", "Métrica subjetiva (Likert)"),
  body: (
    ([Día 1], [≥ 80% de participantes completan el mapeo de la línea sin asistencia externa, con cobertura de ruta ≥ 90%.],   [Promedio ≥ 4.0 / 5 en "La aplicación fue fácil de usar".]),
    ([Día 2], [≥ 80% de participantes reportan correctamente el inicio y fin del desvío.],                                    [Promedio ≥ 4.0 / 5 en "La aplicación fue fácil de usar".]),
    ([Día 3], [≥ 90% de participantes confirman correctamente el fin del desvío.],                                            [Promedio ≥ 4.0 / 5 en "La aplicación fue fácil de usar".]),
  ),
)

== 7.3. Criterio global del estudio

La validación del sistema se considera exitosa si se cumplen al menos dos
de los tres criterios diarios definidos en la sección 7.2 y no se identifica
ningún defecto crítico (ver definición en sección 8.2).

// =============================================================================
// 8. CRITERIOS DE SUSPENSIÓN
// =============================================================================

= 8. Criterios de suspensión y reanudación

== 8.1. Criterios de suspensión

La ejecución del plan de pruebas se suspende si ocurre alguna de las
siguientes situaciones:

- Identificación de un defecto crítico (ver definición abajo) durante el
  primer día de ejecución.
- Caída del backend o de la base de datos por más de 30 minutos durante un
  día de prueba.
- Imposibilidad logística de continuar con el estudio (factores externos:
  clima extremo, paro del transporte, situaciones de seguridad).

== 8.2. Definición de severidad de defectos

#plan-table(
  columns: (auto, 1fr),
  header: ("Severidad", "Descripción"),
  body: (
    ("Crítica", "Impide a más del 50% de los participantes completar la tarea del día. Requiere suspensión y corrección inmediata."),
    ("Alta",    "Afecta a entre 20% y 50% de los participantes pero existe forma de continuar. Se documenta y se decide caso a caso."),
    ("Media",   "Afecta a menos del 20% de los participantes. Se documenta y se continúa el estudio."),
    ("Baja",    "Defecto cosmético o de bajo impacto. Se documenta para corrección posterior."),
  ),
)

== 8.3. Requisitos para la reanudación

Para reanudar el estudio tras una suspensión:

- El defecto que motivó la suspensión debe haberse corregido y desplegado
  en una nueva versión.
- Se debe emitir una nueva versión del presente plan documentando el
  cambio.
- Los participantes ya evaluados no se reincorporan: se recluta un nuevo
  grupo o se descartan los datos parciales según el alcance del defecto.

// =============================================================================
// 9. ENTREGABLES
// =============================================================================

= 9. Entregables de las pruebas

Como resultado de la ejecución del presente plan se generan los siguientes
entregables:

#plan-table(
  columns: (auto, 1.2fr, 2fr),
  header: ("ID", "Entregable", "Descripción"),
  body: (
    ([E-01], [Casos de prueba especificados], [Especificación de cada TC, según plantilla del Anexo B.]),
    ([E-02], [Resultados de ejecución],       [Estado pass/fail por TC, defectos encontrados, observaciones.]),
    ([E-03], [Datos PostHog exportados],      [Eventos registrados durante el estudio, en formato CSV.]),
    ([E-04], [Datos del sistema],             [Líneas mapeadas y desvíos reportados, exportados de la base de datos.]),
    ([E-05], [Cuestionarios completados],     [Respuestas de los participantes al cuestionario post-tarea.]),
    ([E-06], [Consentimientos firmados],      [Formularios de consentimiento informado firmados (archivo físico).]),
    ([E-07], [Reporte final de pruebas],      [Documento de resultados consolidados, integrado al capítulo de Pruebas de la tesis.]),
  ),
)

// =============================================================================
// 10. ACTIVIDADES
// =============================================================================

= 10. Actividades de prueba

La ejecución del presente plan se divide en las siguientes fases:

== 10.1. Fase de preparación (previa al estudio)

+ Finalización y revisión del presente plan de pruebas.
+ Especificación de los casos de prueba (Anexo B).
+ Configuración de eventos PostHog según especificación (Anexo D).
+ Despliegue de la versión a probar en el entorno definido.
+ Reclutamiento de participantes y verificación de criterios de inclusión.
+ Preparación de materiales físicos: tarjetas de instrucciones,
  formularios de consentimiento, cuestionarios.
+ Prueba piloto con 2 participantes para validar procedimientos (al menos
  una semana antes del estudio).

== 10.2. Fase de ejecución (durante el estudio)

+ Briefing inicial: explicación del estudio, firma del consentimiento
  informado.
+ Asignación de credenciales, línea, parada de inicio.
+ Entrega de tarjeta de instrucciones del día.
+ Ejecución de la tarea por parte del participante.
+ Encuentro post-tarea: aplicación del cuestionario, pago de la
  compensación.
+ Registro de incidencias y observaciones.

== 10.3. Fase de cierre (posterior al estudio)

+ Exportación de datos de PostHog y del backend.
+ Tabulación de respuestas del cuestionario.
+ Análisis de resultados según criterios de aceptación.
+ Elaboración del reporte final de pruebas.
+ Eliminación de la lista nominal de participantes (anonimización
  definitiva), según compromiso del consentimiento informado.

// =============================================================================
// 11. NECESIDADES DEL ENTORNO
// =============================================================================

= 11. Necesidades del entorno

== 11.1. Hardware

- Dispositivos móviles de los participantes (Android #placeholder("versión mínima") /
  iOS #placeholder("versión mínima")).
- #placeholder("N") dispositivos de respaldo provistos por la
  investigadora, para participantes con dispositivos incompatibles.
- Cargadores y baterías portátiles para los días de prueba.

== 11.2. Software

- Aplicación móvil en su versión de prueba (commit fijado, ver sección 3).
- Backend desplegado en #placeholder("entorno").
- Cuenta y proyecto en PostHog con eventos configurados.
- Software de exportación y análisis de datos:
  #placeholder("especificar — Excel, Python, etc.").

== 11.3. Conectividad

- Conexión a internet móvil (datos celulares) durante toda la ejecución
  de la tarea.
- Plan de contingencia si un participante no dispone de datos: provisión
  de hotspot por parte de la investigadora.

== 11.4. Espacios físicos

- Punto de encuentro inicial: #placeholder("ubicación"), para briefing y
  entrega de materiales.
- Punto de encuentro final: #placeholder("ubicación"), para cuestionario
  y pago.
- Material impreso: tarjetas de instrucciones, consentimientos,
  cuestionarios.

// =============================================================================
// 12. RESPONSABILIDADES
// =============================================================================

= 12. Responsabilidades

Por la naturaleza individual del proyecto, las responsabilidades del plan
de pruebas se concentran en la investigadora, con supervisión académica
del tutor.

#plan-table(
  columns: (1fr, 1fr, 2fr),
  header: ("Rol", "Persona", "Responsabilidades"),
  body: (
    ([Investigadora],    [Sofía #placeholder("Apellido")], [Diseño, ejecución, recolección de datos, análisis y documentación de las pruebas.]),
    ([Tutor académico],  [#placeholder("Nombre")],         [Revisión y aprobación del plan, supervisión metodológica, validación de resultados.]),
    ([Participantes],    [20 testers],                     [Ejecución de las tareas asignadas según las tarjetas de instrucción.]),
  ),
)

// =============================================================================
// 13. PERSONAL Y CAPACITACIÓN
// =============================================================================

= 13. Personal y necesidades de capacitación

Los participantes reciben un briefing inicial de aproximadamente 15 minutos
al comienzo de cada día, en el cual se explican: el propósito de la tarea
del día, el uso básico de la aplicación, el procedimiento ante incidencias
y las condiciones de la compensación. No se requiere capacitación previa
al primer día del estudio.

// =============================================================================
// 14. CRONOGRAMA
// =============================================================================

= 14. Cronograma

== 14.1. Cronograma general

#plan-table(
  columns: (2fr, 1.2fr, auto),
  header: ("Fase", "Fechas estimadas", "Duración"),
  body: (
    ([Preparación (especificación de TCs, configuración de PostHog)], [#placeholder("___") al #placeholder("___")], [#placeholder("X") semanas]),
    ([Prueba piloto (2 participantes)],          [#placeholder("___")], [1 día]),
    ([Ajustes post-piloto],                      [#placeholder("___") al #placeholder("___")], [#placeholder("X") días]),
    ([Reclutamiento final de participantes],     [#placeholder("___") al #placeholder("___")], [#placeholder("X") semanas]),
    ([Día 1 — Mapeo de línea],                   [#placeholder("___")], [1 día]),
    ([Día 2 — Reporte de inicio de desvío],      [#placeholder("___")], [1 día]),
    ([Día 3 — Reporte de fin de desvío],         [#placeholder("___")], [1 día]),
    ([Análisis y reporte],                       [#placeholder("___") al #placeholder("___")], [#placeholder("X") semanas]),
  ),
)

== 14.2. Cronograma típico de un día de prueba

#plan-table(
  columns: (auto, 1fr),
  header: ("Hora", "Actividad"),
  body: (
    ("08:00 – 08:30", "Llegada de participantes al punto de encuentro inicial."),
    ("08:30 – 08:50", "Briefing del día. Firma de consentimiento (Día 1) o re-confirmación (Días 2 y 3)."),
    ("08:50 – 09:00", "Entrega de tarjeta de instrucciones, credenciales y verificación del dispositivo."),
    ("09:00 – 11:30", "Ejecución de la tarea (recorrido de línea, ida y vuelta si aplica)."),
    ("11:30 – 12:00", "Encuentro en punto final. Aplicación del cuestionario post-tarea."),
    ("12:00 – 12:15", "Pago de la compensación. Cierre del día."),
  ),
)

// =============================================================================
// 15. RIESGOS
// =============================================================================

= 15. Riesgos y contingencias

#plan-table(
  columns: (1.5fr, auto, auto, 2fr),
  header: ("Riesgo", "Probabilidad", "Impacto", "Mitigación"),
  body: (
    ("Inasistencia de participantes",                          "Media", "Medio", "Sobre-reclutamiento del 10–15% (22–23 personas en lugar de 20)."),
    ("Falla de la aplicación en algún dispositivo",            "Media", "Alto",  [Disponer de #placeholder("N") dispositivos de respaldo configurados con la versión de prueba.]),
    ("Caída del backend durante el estudio",                   "Baja",  "Alto",  "Verificación del backend la noche anterior. Plan de rollback documentado."),
    ("Falla del GPS o batería del dispositivo",                "Media", "Medio", "Tarjeta de instrucciones incluye protocolo. Provisión de baterías portátiles."),
    ("Participante toma el bus equivocado",                    "Media", "Bajo",  "Tarjeta con foto e identificación de la línea. Pago igualmente garantizado."),
    ("Día 2 sin datos del Día 1 para algún participante",      "Media", "Medio", "Líneas pre-cargadas en el sistema disponibles como respaldo."),
    ("Día 3 sin datos del Día 2 para algún participante",      "Media", "Medio", "Desvíos pre-cargados en el sistema disponibles como respaldo."),
    ("Condiciones meteorológicas adversas",                    "Baja",  "Alto",  "Día de respaldo previsto al final del cronograma."),
    ("Eventos sociales / paro del transporte",                 "Baja",  "Alto",  "Monitoreo de noticias locales. Reprogramación si necesario."),
    ("Pérdida o corrupción de datos exportados",               "Baja",  "Alto",  "Respaldos diarios. Múltiples copias (local + nube)."),
  ),
)

#pagebreak()

// =============================================================================
// 16. APROBACIONES
// =============================================================================

= 16. Aprobaciones

El presente plan de pruebas requiere la aprobación del tutor académico
antes de su ejecución. Cualquier modificación posterior a esta aprobación
requiere nueva revisión y se registra en el control de versiones del
documento.

#v(6cm)

#align(center)[
  #line(length: 60%, stroke: 0.5pt)

  Sofia Valeria Toro Chambi
  
  Investigadora

  Fecha: \_\_\_ / \_\_\_ / 2026
]

#v(6cm)

#align(center)[
  #line(length: 60%, stroke: 0.5pt)

  Javier Vásquez Cruz
  
  Tutor académico

  Fecha: \_\_\_ / \_\_\_ / 2026
]

#pagebreak()

// =============================================================================
// ANEXOS
// =============================================================================

= Anexos

== Anexo A — Matriz de trazabilidad

La matriz de trazabilidad documenta la relación entre casos de uso,
requisitos funcionales, funcionalidades y casos de prueba. Cada fila
corresponde a la verificación de un requisito funcional.

#plan-table(
  columns: (auto, auto, auto, 1.5fr, auto),
  header: ("Caso de uso", "Requisito funcional", "Funcionalidad", "Casos de prueba", "Verificado"),
  body: (
    ([UC-#placeholder("__")], [RF-#placeholder("__")], [F-01], [TC-01, TC-02], [☐]),
    ([UC-#placeholder("__")], [RF-#placeholder("__")], [F-01], [TC-03],         [☐]),
    ([UC-#placeholder("__")], [RF-#placeholder("__")], [F-01], [TC-04, TC-05], [☐]),
    ([UC-#placeholder("__")], [RF-#placeholder("__")], [F-02], [TC-06, TC-07], [☐]),
    ([UC-#placeholder("__")], [RF-#placeholder("__")], [F-02], [TC-08],         [☐]),
    ([UC-#placeholder("__")], [RF-#placeholder("__")], [F-03], [TC-09, TC-10], [☐]),
  ),
)

#placeholder("Completar con los IDs reales de UC y RF del capítulo de Análisis. Añadir filas según corresponda.")

== Anexo B — Plantilla de caso de prueba

Cada caso de prueba se especifica utilizando la siguiente plantilla. Los
casos de prueba completos se incluyen como subdocumento del presente plan.

#plan-table(
  columns: (1.2fr, 2fr),
  header: ("Campo", "Contenido"),
  body: (
    ("ID del caso de prueba",            [TC-#placeholder("NN")]),
    ("Título",                           [#placeholder("Descripción breve de lo que se prueba")]),
    ("Caso de uso relacionado",          [UC-#placeholder("__")]),
    ("Requisito funcional relacionado",  [RF-#placeholder("__")]),
    ("Funcionalidad bajo prueba",        [F-#placeholder("NN")]),
    ("Prioridad",                        "Alta / Media / Baja"),
    ("Tipo de prueba",                   "Funcional / Usabilidad / Aceptación"),
    ("Precondiciones",                   "Condiciones que deben cumplirse antes de ejecutar el caso."),
    ("Datos de prueba",                  "Datos específicos requeridos (línea asignada, credenciales, etc.)."),
    ("Pasos de ejecución",               "Lista numerada de acciones a realizar."),
    ("Resultado esperado",               "Comportamiento que se considera correcto."),
    ("Resultado obtenido",               [#placeholder("Se completa durante la ejecución")]),
    ("Estado",                           [#placeholder("Pass / Fail / Blocked — se completa durante la ejecución")]),
    ("Ejecutado por",                    [#placeholder("Tester ID o investigadora")]),
    ("Fecha de ejecución",               "___ / ___ / 2026"),
    ("Observaciones",                    [#placeholder("Notas, defectos identificados, contexto adicional")]),
  ),
)

== Anexo C — Tarjetas de instrucciones para participantes

Las tarjetas de instrucciones son documentos físicos de una página
entregados a cada participante al inicio de cada día. Contienen el
procedimiento numerado de la tarea, el protocolo ante incidencias y los
datos de contacto de la investigadora.

Se incluyen tres tarjetas (una por día) más una hoja de credenciales
separada. Se imprimen en formato A5 a doble cara.

#placeholder("Adjuntar las tarjetas como subdocumentos o ver documento separado \"Tarjetas de instrucciones — Sofi.docx\".")

== Anexo D — Especificación de eventos PostHog

La instrumentación con PostHog permite registrar el comportamiento de los
participantes durante el uso de la aplicación. Cada evento se especifica
con su nombre, propiedades, descripción y momento de disparo.

#plan-table(
  columns: (1.3fr, 1.5fr, 1.5fr),
  header: ("Nombre del evento", "Propiedades", "Cuándo se dispara"),
  body: (
    ([`line_mapping_started`],          [tester_id, line_id, timestamp, gps_active, battery_level],          [Al tocar "Iniciar grabación" en la pantalla de mapeo.]),
    ([`line_mapping_completed`],        [tester_id, line_id, duration_seconds, points_recorded, route_coverage_pct], [Al confirmar el envío de una línea mapeada.]),
    ([`line_mapping_failed`],           [tester_id, line_id, error_type, last_step],                        [Cuando la grabación termina sin envío exitoso.]),
    ([`detour_report_started`],         [tester_id, line_id, timestamp],                                    [Al iniciar el reporte de un desvío.]),
    ([`detour_start_marked`],           [tester_id, line_id, lat, lng, timestamp],                          [Al marcar el punto de inicio del desvío.]),
    ([`detour_end_marked`],             [tester_id, line_id, lat, lng, timestamp],                          [Al marcar el punto de fin del desvío.]),
    ([`detour_report_submitted`],       [tester_id, line_id, detour_id, duration_seconds],                  [Al confirmar el envío del reporte de desvío.]),
    ([`detour_resolution_submitted`],   [tester_id, line_id, detour_id, timestamp],                         [Al confirmar que un desvío ya finalizó.]),
    ([`app_crashed`],                   [tester_id, screen, error_message],                                 [Ante un crash detectado por el manejador de errores de la app.]),
    ([`task_completed_self_reported`],  [tester_id, day_number, success],                                   [Al recibir el WhatsApp de "LISTO" del participante (registrado manualmente).]),
  ),
)

#placeholder("Ajustar la lista de eventos según la implementación real. Añadir cualquier propiedad adicional necesaria para el análisis.")

== Anexo E — Cuestionario post-tarea

El cuestionario post-tarea se aplica al finalizar la tarea de cada día.
Combina preguntas en escala Likert de 5 puntos (1 = muy en desacuerdo,
5 = muy de acuerdo) con preguntas abiertas. Las preguntas Likert
principales son comunes a los tres días para permitir comparación; las
preguntas específicas varían según la tarea del día.

=== Preguntas Likert (comunes a los tres días)

#plan-table(
  columns: (auto, 2.5fr, 1.5fr),
  header: ("Nº", "Afirmación", "Dimensión (ISO 25010)"),
  body: (
    ("L1", "La aplicación fue fácil de usar durante la tarea de hoy.",                          "Usabilidad / Facilidad de uso"),
    ("L2", "Las instrucciones que recibí fueron claras.",                                       "Usabilidad / Claridad"),
    ("L3", "Pude completar la tarea sin necesidad de ayuda externa.",                           "Eficacia"),
    ("L4", "El tiempo que tomó la aplicación para responder fue adecuado.",                     "Eficiencia"),
    ("L5", "Confío en que los datos que envié fueron registrados correctamente.",               "Confiabilidad"),
    ("L6", "Volvería a usar esta aplicación.",                                                  "Satisfacción"),
    ("L7", "Recomendaría esta aplicación a otros usuarios del transporte público.",             "Satisfacción"),
  ),
)

=== Preguntas abiertas

+ ¿Qué fue lo más fácil de la tarea de hoy?
+ ¿Qué fue lo más difícil?
+ ¿Tuvo algún problema con la aplicación? Si sí, descríbalo.
+ ¿Qué cambiaría o agregaría a la aplicación?

== Anexo F — Formulario de consentimiento informado

#placeholder("Adjuntar el formulario de consentimiento como subdocumento o ver documento separado \"Consentimiento informado — TrufiMap.docx\".")

== Anexo G — Checklist de pruebas manuales de humo

La presente lista de verificación se ejecuta por la investigadora antes
de cada despliegue del sistema en el entorno de producción y antes del
inicio del estudio de campo. Su objetivo es validar que las
funcionalidades críticas operan correctamente extremo-a-extremo en
condiciones reales de uso, complementando la suite de pruebas
automatizadas (descrita en el capítulo III de la tesis).

La checklist se imprime y se firma en cada ejecución. Cualquier ítem
marcado como "Falla" suspende el despliegue hasta su corrección.

#plan-table(
  columns: (auto, 2fr, auto, auto),
  header: ("Nº", "Verificación", "Estado", "Observaciones"),
  body: (
    ("S-01", [Build de la aplicación móvil instala correctamente en un dispositivo físico iOS y otro Android (vía EAS dev build).], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-02", [Al primer arranque, la app solicita permiso de notificaciones y registra el dispositivo en `/devices/register` (verificar fila en tabla `devices` con `expo_push_token` no nulo).], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-03", [Al guardar un viaje con tipo "recurrente", la app sincroniza la suscripción con `PUT /devices/\{id\}/subscriptions` (verificar fila en `line_subscriptions`).], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-04", [Al eliminar un viaje recurrente, la app actualiza la suscripción retirando la línea correspondiente.], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-05", [Grabación corta (~5 minutos): los puntos GPS y las lecturas de sensores se acumulan en SQLite local mientras dura la grabación.], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-06", [Al detener la grabación, los puntos se sincronizan al servidor en lotes y la sesión termina con estado `completed`.], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-07", [TC-11 — Notificación push de desvío activo a usuario con viaje recurrente. Ejecutado con dos dispositivos físicos pareados. Resultado: el dispositivo receptor recibe una notificación con título "Desvío en \{línea\}" y al tocarla la app abre la pestaña de exploración con el desvío visible.], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-08", [TC-12 — Coalescencia tras 3 notificaciones individuales en 24 h. Tras 3 desvíos individuales, el 4.º produce una notificación coalescida ("Más desvíos en \{línea\}") y el 5.º se suprime.], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-09", [Votación por secciones: el usuario puede aprobar/rechazar al menos una sección y la fila correspondiente queda registrada en `edge_votes`.], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-10", [Reporte de desvío durante el cierre de grabación: con `is_detour=true`, se crea una fila en `detours` con estado `active`.], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-11", [Confirmación de desvío activo desde la pantalla de explorar: la columna `last_confirmed_at` se actualiza y `confirmed_count` se incrementa.], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-12", [La instrumentación PostHog registra al menos los eventos `line_mapping_started`, `detour_report_submitted` y `app_crashed` (si aplica).], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-13", [TC-14 — Notificación local de inicio de ruta. Guardar un viaje "solo por hoy" con hora de salida (HH:mm); cerrar la app; verificar que 10 minutos antes de la hora indicada se dispara una notificación con título "Salida a \{destino\} a las HH:mm" y cuerpo que enumera la(s) línea(s) a tomar.], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-14", [TC-15 — Notificación de inicio de ruta incluye aviso de desvío activo. Pre-condición: el día de la prueba existe un desvío activo en alguna de las líneas del viaje guardado. Verificar que el cuerpo de la notificación incluye el sufijo "⚠ Desvío activo: Línea X (motivo)".], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-15", [TC-16 — Notificación recurrente. Guardar un viaje recurrente con hora de salida; verificar que la notificación se dispara cada día a la misma hora durante 3 días consecutivos.], [☐ Pass / ☐ Fail], [#placeholder("___")]),
    ("S-16", [TC-17 — Cancelación al eliminar viaje. Eliminar un viaje guardado con hora de salida; verificar que la notificación programada deja de dispararse.], [☐ Pass / ☐ Fail], [#placeholder("___")]),
  ),
)

#v(1cm)
*Ejecución firmada:*

#v(0.8cm)
Investigadora: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

Fecha: \_\_\_ / \_\_\_ / 2026 #h(2cm) Build identificado: #placeholder("___")

== Anexo H — Casos de prueba detallados

Las especificaciones IEEE 829 completas de cada caso de prueba (TC-01 a
TC-13) se documentan en la sección 6 (Casos de prueba) del capítulo III
de la tesis adjunta. Esta decisión busca priorizar la lectura por parte
del tribunal evaluador y evitar la duplicación documental, manteniendo
la trazabilidad mediante la matriz del Anexo A.

El presente plan conserva la plantilla IEEE 829 (Anexo B) como
referencia normativa para la elaboración de casos de prueba adicionales
durante el ciclo de vida del sistema posterior a la entrega del
proyecto de grado.

== Anexo I — Fin del documento

Este documento es la versión 1.1 del Plan de Pruebas de Aceptación.
Cualquier modificación posterior se registra en la sección de Control
de Versiones del presente plan.
