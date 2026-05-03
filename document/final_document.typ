// =====================================================================
// Proyecto de Grado — Sistema móvil multiplataforma basado en
// crowdsourcing para la recolección y centralización de información
// de rutas del transporte público en el área metropolitana de Cochabamba
//
// Postulante: Sofia Valeria Toro Chambi
// Tutor: Ing. Javier Marcelo Vasquez Cruz
// Universidad Privada del Valle — 2026
// =====================================================================

#set document(
  title: "Sistema móvil multiplataforma basado en crowdsourcing para la recolección y centralización de información de rutas del transporte público en el área metropolitana de Cochabamba",
  author: "Sofia Valeria Toro Chambi",
)

#set page(
  paper: "us-letter",
  margin: (top: 2.5cm, bottom: 2.5cm, left: 3cm, right: 2.5cm),
  numbering: "1",
  number-align: right + top
)

#set text(
  font: "Arial",
  size: 11pt,
  lang: "es",
  region: "bo",
)

#set par(
  justify: true,
  leading: 0.85em,
)

#set table.header(repeat: true)
#show figure.where(kind: table): set figure(placement: none)
#show figure.where(kind: table): set block(breakable: true)

#show heading.where(level: 1): it => {
  set text(size: 16pt, weight: "bold")
  upper(it.body)
}

#show heading.where(level: 2): it => {
  set text(size: 13pt, weight: "bold")
  v(0.3em)
  it
  v(0.3em)
}

#show heading.where(level: 3): it => {
  set text(size: 12pt, weight: "bold")
  v(0.4em)
  it
  v(0.2em)
}

#show heading.where(level: 4): it => {
  set text(size: 11pt, weight: "bold", style: "italic")
  v(0.3em)
  it
  v(0.2em)
}

#show figure.caption: it => [
  #context text(it.supplement, weight: "bold")
  #context text(it.counter.display(it.numbering) + ".", weight: "bold")
  #it.body
]

// Helper: caption for figures and tables
#let fig-caption(num, title) = align(center)[
  #text(weight: "bold")[Figura #num] #title
]
#let tab-caption(num, title) = align(center)[
  #text(weight: "bold")[Tabla #num.] #title
]
#let source(text-content) = align(center)[
  #text(style: "italic", size: 10pt)[Fuente: #text-content]
]
// Helper: gray italic placeholder marker for content pending completion.
#let placeholder(body) = text(fill: gray, style: "italic")[\[#body\]]

// =====================================================================
// COVER PAGE
// =====================================================================

#set page(numbering: none)

#align(center)[
  #v(1cm)
  #image("images/image1.png", width: 3.2cm)

  #v(0.5cm)
  #text(size: 14pt, weight: "bold")[UNIVERSIDAD PRIVADA DEL VALLE]

  #text(size: 13pt, weight: "bold")[FACULTAD DE INFORMÁTICA Y ELECTRÓNICA]

  #text(size: 12pt, weight: "bold")[CARRERA DE LICENCIATURA EN INGENIERÍA DE SISTEMAS INFORMÁTICOS]

  #v(2.5cm)

  #text(size: 14pt, weight: "bold")[
    SISTEMA MÓVIL MULTIPLATAFORMA BASADA EN CROWDSOURCING
    PARA LA RECOLECCIÓN Y CENTRALIZACIÓN DE INFORMACIÓN
    DE RUTAS DEL TRANSPORTE PÚBLICO EN EL ÁREA
    METROPOLITANA DE COCHABAMBA
  ]

  #v(2cm)

  #text(size: 12pt)[
    PROYECTO DE GRADO PARA OPTAR AL TÍTULO DE LICENCIATURA EN
    INGENIERÍA DE SISTEMAS INFORMÁTICOS
  ]

  #v(2cm)

  #text[
    *POSTULANTE:* SOFIA VALERIA TORO CHAMBI

    *TUTOR:* ING. JAVIER MARCELO VASQUEZ CRUZ
  ]

  #v(1fr)

  Cochabamba -- Bolivia

  2026
]

#pagebreak()

// =====================================================================
// DEDICATORIA
// =====================================================================

#v(1fr)
#align(center)[
  #block(
    width: 80%,
    stroke: 0.5pt,
    inset: 1.5em,
  )[
    #align(left)[
      *Dedicatoria*

      #v(0.5em)
      #text(style: "italic")[
        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do
        eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut
        enim ad minim veniam, quis nostrud exercitation ullamco laboris
        nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor
        in reprehenderit in voluptate velit esse cillum dolore eu fugiat
        nulla pariatur. Excepteur sint occaecat cupidatat non proident,
        sunt in culpa qui officia deserunt mollit anim id est laborum.
      ]
    ]
  ]
]
#v(1fr)

#pagebreak()

// =====================================================================
// AGRADECIMIENTOS
// =====================================================================

#v(1fr)
#align(center)[
  #block(
    width: 80%,
    stroke: 0.5pt,
    inset: 1.5em,
  )[
    #align(left)[
      *Agradecimientos*

      #v(0.5em)
      #text(style: "italic")[
        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do
        eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut
        enim ad minim veniam, quis nostrud exercitation ullamco laboris
        nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor
        in reprehenderit in voluptate velit esse cillum dolore eu fugiat
        nulla pariatur. Excepteur sint occaecat cupidatat non proident,
        sunt in culpa qui officia deserunt mollit anim id est laborum.
      ]
    ]
  ]
]
#v(1fr)

#pagebreak()

// =====================================================================
// RESUMEN
// =====================================================================

#align(center)[#text(size: 14pt, weight: "bold")[RESUMEN]]
#v(0.5em)

El presente proyecto...

#pagebreak()

// =====================================================================
// ABSTRACT
// =====================================================================

#align(center)[#text(size: 14pt, weight: "bold")[ABSTRACT]]
#v(0.5em)

This project...

#pagebreak()

// =====================================================================
// ÍNDICE DE CONTENIDO
// =====================================================================

#align(center)[#text(size: 14pt, weight: "bold")[ÍNDICE DE CONTENIDO]]
#v(0.5em)

#outline(
  title: none,
  indent: auto,
  depth: 3,
)

#pagebreak()

// =====================================================================
// ÍNDICE DE FIGURAS
// =====================================================================

#align(center)[#text(size: 14pt, weight: "bold")[ÍNDICE DE FIGURAS]]
#v(0.5em)

#outline(
  title: none,
  target: figure.where(kind: image),
)

#pagebreak()

// =====================================================================
// ÍNDICE DE TABLAS
// =====================================================================

#align(center)[#text(size: 14pt, weight: "bold")[ÍNDICE DE TABLAS]]
#v(0.5em)

#outline(
  title: none,
  target: figure.where(kind: table),
)

#pagebreak()

// =====================================================================
// LISTA DE SIGLAS Y ABREVIATURAS
// =====================================================================

#align(center)[#text(size: 14pt, weight: "bold")[LISTA DE SIGLAS Y ABREVIATURAS]]
#v(1em)

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt,
  inset: 8pt,
  [*Sigla*], [*Significado*],
  [SDLC], [Software Development Life Cycle (Ciclo de Vida de Desarrollo de Software)],
  [HMM], [Hidden Markov Model (Modelo Oculto de Márkov)],
  [SIG], [Sistemas de Información Geográfica],
  [GPS], [Global Positioning System (Sistema de Posicionamiento Global)],
  [API], [Application Programming Interface (Interfaz de Programación de Aplicaciones)],
  [REST], [Representational State Transfer],
  [OSS], [Open Source Software (Software de Código Abierto)],
  [MCS], [Mobile Crowdsourcing (Crowdsourcing Móvil)],
  [OTB], [Organización Territorial de Base],
  [INE], [Instituto Nacional de Estadística],
)

#pagebreak()

// =====================================================================
// MAIN BODY — START PAGE NUMBERING
// =====================================================================

#set page(numbering: "1")
#counter(page).update(1)

= Introducción

El departamento de Cochabamba, es una de las tres ciudades más grandes
de Bolivia, con más de un millón y medio de habitantes (Instituto
Nacional de Estadística INE, 2015) en donde el 65.7% se moviliza
principalmente por transporte público (Cabrera et al., 2018), y aun así,
sin un medio confiable y actualizado que ofrezca información sobre las
líneas y rutas que lo conforman.

Debido al carácter local, dinámico y privado del transporte de pasajeros
en las ciudades de Bolivia (Cabrera et al., 2018), aplicaciones como
Moovit o Google Maps no operan en el país o lo hacen de manera limitada,
restringiéndose principalmente a funcionalidades de mapas. Alternativas
locales como Llajta Rutas o Trufi surgieron debido a esta necesidad; sin
embargo, no lograron sostenerse en el tiempo.

Ante esta situación, el presente proyecto propone la implementación de
una aplicación móvil que centralice información sobre las diferentes
líneas, tarifas, rutas y sus variantes dentro del transporte público de
la ciudad de Cochabamba. Para ello, se plantea el crowdsourcing como
estrategia principal para mantener la información actualizada, así como
la adopción de un enfoque open source, permitiendo a la población y a la
comunidad de desarrolladores contribuir al mantenimiento y evolución del
proyecto a largo plazo.

El sistema de transporte público en Cochabamba presenta diversas
particularidades, como los distintos tipos de vehículos y el hecho de
que una misma línea pueda recorrer dos o más rutas diferentes,
identificadas mediante distintivos como colores o banderas. En este
contexto, el proyecto busca identificar y analizar las fortalezas de
aplicaciones de referencia en el ámbito del transporte público, como
Google Maps, que proporciona información sobre la dirección de las
líneas, o SBB Mobile, que registra con precisión las rutas seguidas por
los usuarios, con el fin de adaptar dichas funcionalidades a la realidad
local y ofrecer un servicio útil y de calidad.

Finalmente, en los siguientes apartados se profundiza en el
planteamiento del problema, los antecedentes y las propuestas
existentes, junto con los objetivos, el alcance y la metodología del
proyecto, proporcionando el contexto necesario sobre la solución
propuesta.

= Planteamiento del problema

El transporte público es vital en la vida de las personas, especialmente
cuando no disponen de un vehículo privado para movilizarse, como es el
caso de la mayor parte de la población de Cochabamba, donde sólo un
37.2% posee un vehículo automotor o motocicleta (Instituto Nacional de
Estadística INE, 2015) y, como se observa en la Figura 1, el 65.7% de la
población utiliza el transporte público como principal medio para
movilizarse en el día a día (Cabrera et al., 2018). En estas
circunstancias, es esencial para la población saber cómo movilizarse
entre todas las líneas disponibles (Holguin et al., 2019).

#figure(
  image("images/image2.png", width: 80%),
  caption: [Medio de transporte utilizado por la población de Cochabamba],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026, con base en Cabrera et al., 2018.]

Sin embargo, como señalan Cabrera et al. (2018), si bien la regulación
del transporte público urbano, incluyendo la autorización de líneas,
rutas y tarifas, recae formalmente en el Gobierno Autónomo Municipal de
Cochabamba, en la práctica la operación del servicio se encuentra
descentralizada, siendo la excepción el tren metropolitano. Esto se
debe, en parte, al Decreto Supremo Nº 21660 de Reactivación Económica,
que permite que cualquier persona natural o jurídica preste libremente
servicios de transporte urbano público siempre que se cumplan los
requisitos de seguridad y de protección al usuario artículo N° 176.

Esta forma de organización del transporte público, caracterizada por una
regulación formal sin una gestión centralizada de la información
operativa, hace que el mapeo actualizado de las rutas de movilización
resulte complicado. Como consecuencia, aplicaciones como Google Maps o
Moovit, que ofrecen información sobre el transporte público en diversos
países, no pueden operar de manera adecuada en Bolivia. De este modo,
los ciudadanos carecen de acceso a conocimiento sobre las líneas
disponibles, sus rutas, horas de operación y conexiones.

Considerando que en Cochabamba se realizan cerca de 2 millones de viajes
diarios (Cabrera & Moyano, 2022), y que en más del 40% de hogares hay al
menos un integrante que se traslada diariamente entre municipios
(Cabrera, 2017), es vital contar con un medio que provea toda esta
información faltante, especialmente para los municipios más
frecuentados, cuyas rutas más concurridas se pueden observar en la
Figura 2.

#figure(
  image("images/image3.jpg", width: 100%),
  caption: [Flujos de transporte en la región metropolitana de Cochabamba],
  supplement: "Figura",
  kind: image,
)

#source[Cabrera & Moyano, 2022.]

Anteriormente se propusieron soluciones como Llajta Rutas (Cabrera
et al., 2018) y Trufi (Trufi Association, 2025), ambas aplicaciones
móviles con mapeo de las líneas y rutas disponibles en Cochabamba; con
Llajta Rutas usando crowdsourcing para construir dicho inventario,
mientras Trufi lo construyó de forma independiente. Ambas aplicaciones
recibieron buena acogida del público, Trufi llegando a 100 mil descargas
a la fecha (Google Play, 2023) y Llajta Rutas con 10 mil descargas entre
2017 y 2018 (Cabrera et al., 2018).

No obstante, lamentablemente ambas aplicaciones dejaron de recibir
soporte y mantenimiento activo. Llajta Rutas ya no se encuentra
disponible en Play Store y fue descontinuada debido a falta de apoyo
económico (Cabrera, comunicación personal, 28 de diciembre de 2025). Por
otro lado, aunque Trufi aún se encuentra disponible en Play Store, su
última actualización fue el 14 de diciembre de 2023 (Google Play, 2023),
y se observan comentarios recientes mencionando la falta de:

- Distinción de colores de líneas, puesto que una misma línea puede
  tener diferentes rutas.

- Actualización de líneas disponibles y sus respectivas rutas y
  tarifas a lo largo del tiempo.

- Paradas y horarios del nuevo tren metropolitano de Cochabamba.

Además, cabe recalcar que las bases de datos que ambas aplicaciones
recolectaron sobre las rutas están cerradas al público, por lo que no se
las puede extender o consultar con un sistema externo.

En síntesis, la falta de una fuente centralizada y abierta de
información actualizada sobre las rutas del transporte público en el
área metropolitana de Cochabamba representa una limitación significativa
para la movilidad cotidiana de la población. Si bien han existido
iniciativas previas que evidencian la utilidad y aceptación de este tipo
de herramientas, la ausencia de mecanismos sostenibles para la
recolección y mantenimiento de la información ha impedido su continuidad
en el tiempo. Esta situación pone de manifiesto la necesidad de una
solución que permita recolectar y centralizar de manera colaborativa la
información de rutas del transporte público, asegurando su actualización
y disponibilidad a largo plazo.

== Formulación del problema

El presente proyecto busca proponer una solución a las necesidades
descritas, por lo que surge la pregunta: ¿De qué manera podría
implementarse una solución tecnológica que permita recolectar y
centralizar la información de rutas del transporte público en el área
metropolitana de Cochabamba?

= Justificación

== Justificación social

La aplicación beneficiará principalmente a los usuarios del transporte
público del área metropolitana de Cochabamba, quienes actualmente
carecen de información clara y actualizada sobre líneas, rutas, paradas
y horarios. Con esta herramienta, los ciudadanos podrán planificar sus
viajes de manera más eficiente, optimizando los tiempos de traslado y
evitando desplazamientos innecesarios.

Un hallazgo de la aplicación Llajta Rutas mostró que incluso existían
usuarios que, aunque disponían de vehículo privado, la utilizaban para
"dejar el coche estacionado en algún lugar y tomar algún trufi o micro
para llegar al destino final, y así evitar el congestionamiento
vehicular" (Cabrera et al., 2018). Esto evidencia que la aplicación no
solo beneficia a quienes dependen exclusivamente del transporte público,
sino también a quienes buscan alternativas más eficientes y sostenibles
para su desplazamiento diario.

== Justificación técnica

Desde el punto de vista técnico, se propone el desarrollo de un sistema
móvil multiplataforma basado en una arquitectura cliente-servidor de
tres capas con escalamiento horizontal, como un enfoque adecuado para la
recolección y centralización colaborativa de información de rutas del
transporte público. Este tipo de arquitectura permite facilitar la
participación de múltiples usuarios mediante dispositivos móviles,
soportar accesos concurrentes y garantizar la disponibilidad de la
información, sin comprometer la consistencia de los datos. Asimismo, su
naturaleza escalable resulta pertinente considerando el tamaño de la
población del área metropolitana de Cochabamba y la necesidad de
mantener actualizada una base de información dinámica.

Además, el proyecto se desarrollará bajo un modelo open source,
permitiendo que tanto el código de la aplicación como la información
recolectada sobre rutas del transporte público puedan ser consultados y
descargados por la comunidad desde un repositorio público. Esta
estrategia facilita la continuidad y mantenimiento del sistema a lo
largo del tiempo, fomentando la participación de otros desarrolladores y
usuarios en la actualización y mejora de la información, y garantizando
que el conocimiento generado no quede cerrado a una única instancia del
proyecto.

== Justificación económica

Desde el punto de vista económico, el desarrollo de un sistema móvil
multiplataforma basado en crowdsourcing representa una solución rentable
para la recolección y centralización de información de rutas del
transporte público en Cochabamba. Al permitir que los propios usuarios
contribuyan a la actualización de los datos, se reducen los costos
asociados a la recopilación y mantenimiento manual de la información.
Además, al ser open source, tanto el código como los datos podrán ser
reutilizados y mantenidos por la comunidad, evitando gastos de licencias
o personal especializado a largo plazo.

Para cubrir los costos de despliegue y operación del sistema, tales como
servidores, dominio y servicios asociados, se cuenta con un capital
inicial destinado a la realización de pruebas durante el desarrollo del
proyecto. La sostenibilidad económica a largo plazo del sistema, que
incluye la búsqueda de fondos de posibles organizaciones interesadas
como alcaldías del departamento de Cochabamba o federaciones de
transporte público, no forma parte del alcance del presente proyecto de
grado y se plantea como una etapa posterior a su conclusión.

= Objetivos

== Objetivo general

Desarrollar un sistema móvil multiplataforma basado en crowdsourcing
para la recolección y centralización de información de rutas del
transporte público en el área metropolitana de Cochabamba.

== Objetivos específicos

- Elaborar un sistema de monitoreo colaborativo de rutas, mediante el
  registro georreferenciado de trayectos y un pipeline de procesamiento
  estadístico, para recolectar y centralizar progresivamente la
  información de rutas de las líneas de transporte público de Cochabamba.

- Facilitar el registro de desvíos temporales, mediante el registro
  georreferenciado con etiquetado respecto a una línea, para que los
  usuarios notifiquen y consulten cambios inesperados en los recorridos
  habituales.

- Desarrollar un subsistema de gestión de tarifas, con parametrización
  por municipio y tramo origen-destino, para que los usuarios reporten y
  consulten las tarifas del transporte público.

- Gestionar la información de líneas de transporte, con diferenciación
  de ramales, para que los usuarios registren, consulten y actualicen
  información sobre las rutas y horarios de operación.

- Proveer un servicio de identificación de trayectos, mediante un
  algoritmo de búsqueda de rutas con soporte de transbordos sobre grafos
  de red de transporte, para que los usuarios encuentren las líneas
  necesarias para desplazarse entre un origen y un destino.

= Alcance

A continuación, se especifica el alcance del proyecto a partir de los
objetivos específicos.

*a) Elaborar un sistema de monitoreo colaborativo de rutas*, mediante el
registro georreferenciado de trayectos y un pipeline de procesamiento
estadístico, para recolectar y centralizar progresivamente la
información de rutas de las líneas de transporte público de Cochabamba.

- Registrar recorridos del transporte público mediante coordenadas
  geográficas capturadas en tiempo real por los usuarios.

- Asociar los recorridos registrados a una línea de transporte
  específica.

- Construir rutas representativas de cada línea a través de un pipeline
  de procesamiento de los recorridos registrados por los usuarios.

- Permitir a los usuarios confirmar o rechazar la correspondencia entre
  una ruta inferida y una línea de transporte.

*b) Facilitar el registro de desvíos temporales*, mediante el registro
georreferenciado con etiquetado respecto a una línea, para que los
usuarios notifiquen y consulten cambios inesperados en los recorridos
habituales.

- Permitir a los usuarios reportar desvíos temporales en los recorridos
  habituales de las líneas de transporte.

- Registrar el tramo afectado y la duración estimada del desvío.

- Permitir a otros usuarios confirmar o refutar los desvíos reportados.

*c) Desarrollar un subsistema de gestión de tarifas*, con parametrización
por municipio y tramo origen-destino, para que los usuarios reporten y
consulten las tarifas del transporte público.

- Permitir el registro colaborativo de tarifas del transporte público
  entre un municipio origen y un municipio destino.

- Permitir la consulta de tarifas registradas por los usuarios.

- Consolidar tarifas reportadas cuando existan múltiples registros para
  un mismo tramo.

*d) Gestionar la información de líneas de transporte*, con diferenciación
de ramales, para que los usuarios registren, consulten y actualicen
información sobre las rutas y horarios de operación.

- Permitir el registro de nuevas líneas de transporte público.

- Almacenar información básica de cada línea, incluyendo rutas
  consolidadas y horarios de operación.

- Permitir la consulta y actualización colaborativa de la información de
  las líneas registradas.

*e) Proveer un servicio de identificación de trayectos*, mediante un
algoritmo de búsqueda de rutas con soporte de transbordos sobre grafos
de red de transporte, para que los usuarios encuentren las líneas
necesarias para desplazarse entre un origen y un destino.

- Permitir al usuario ingresar un punto de origen y un punto de destino.

- Identificar las líneas de transporte público que permiten realizar el
  desplazamiento entre los puntos indicados, a partir de las rutas
  consolidadas.

- Permitir a los usuarios suscribirse a líneas o rutas específicas.

- Notificar a los usuarios suscritos cuando se registren o confirmen
  desvíos en las rutas de su interés.

= Metodología

== Metodología de desarrollo del sistema

Para el desarrollo del sistema se adopta el modelo del Ciclo de Vida de
Desarrollo de Software (SDLC, por sus siglas en inglés) en su variante
secuencial. Se opta por este enfoque debido a que el proyecto cuenta con
un alcance definido desde la etapa de planificación, es desarrollado por
un único responsable y se enmarca en un contexto académico con plazos
establecidos, condiciones bajo las cuales un modelo secuencial resulta
más adecuado que metodologías iterativas orientadas a equipos de
desarrollo. Las fases contempladas son las siguientes:

- *Análisis:* Comprende la definición de los requerimientos
  funcionales y no funcionales del sistema, tomando como base el
  planteamiento del problema, los objetivos específicos y el alcance
  del proyecto. En esta fase se identifican las necesidades de los
  usuarios en relación con la recolección colaborativa de información
  del transporte público.

- *Diseño:* Comprende la elaboración de la arquitectura del sistema
  bajo el modelo cliente-servidor, el diseño del esquema de base de
  datos geoespacial y el prototipado de las interfaces de usuario.
  Las decisiones de diseño se fundamentan en los requerimientos
  definidos en la fase anterior.

- *Desarrollo:* Comprende la implementación del sistema siguiendo un
  orden incremental por funcionalidad: gestión de líneas de
  transporte, monitoreo colaborativo de rutas, registro de desvíos
  temporales, gestión de tarifas e identificación de trayectos. Este
  orden responde a las dependencias entre funcionalidades, dado que
  el monitoreo de rutas y las funcionalidades subsecuentes dependen
  de las líneas registradas en el sistema.

- *Pruebas:* Comprende la verificación del funcionamiento del sistema
  mediante pruebas controladas con usuarios, la evaluación de la
  precisión en la reconstrucción de rutas y la recopilación de
  retroalimentación sobre la usabilidad de la aplicación.

Las herramientas tecnológicas empleadas para el desarrollo del sistema
se listan en la Tabla 1.

#figure(
  table(
    columns: (auto, auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [*Herramienta*], [*Tipo*], [*Aplicabilidad en el proyecto*],
    [PostgreSQL + PostGIS], [Base de datos], [Almacenamiento de datos relacionales y geoespaciales (ver sección 6.5.1)],
    [FastAPI], [Framework backend], [Desarrollo de la API REST del sistema (ver sección 6.5.2)],
    [React Native], [Framework frontend], [Desarrollo de la aplicación móvil multiplataforma (ver sección 6.5.3)],
    [Git / GitHub], [Control de versiones], [Gestión y seguimiento del código fuente],
    [Figma], [Herramienta de diseño], [Prototipado y diseño de interfaces de usuario],
  ),
  caption: [Herramientas tecnológicas para el desarrollo del sistema.],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

== Enfoque de investigación

El presente proyecto adopta un enfoque mixto con predominancia
cualitativa. El enfoque cualitativo se aplica en el análisis del
problema, la definición de requerimientos, el diseño de la arquitectura
del sistema y de los módulos funcionales, así como en la interpretación
de la retroalimentación obtenida sobre la utilidad y funcionamiento de
la aplicación.

El enfoque cuantitativo se emplea de manera complementaria, mediante la
recolección y análisis de datos básicos obtenidos a partir de
cuestionarios en línea y métricas simples del sistema durante pruebas
controladas.

== Tipo de investigación

La investigación es de tipo aplicada, dado que está orientada al
desarrollo de una solución tecnológica que responde a un problema
concreto relacionado con el acceso a información del transporte público
en el área metropolitana de Cochabamba.

== Métodos

En el desarrollo del proyecto se emplearán métodos teóricos y empíricos.
Entre los métodos teóricos a utilizar están el método analítico y el
método sintético, los cuales permiten descomponer el problema del acceso
a la información del transporte público y estructurar una solución
tecnológica acorde a dicho análisis.

Como método empírico se utilizará la observación indirecta, aplicada
durante pruebas controladas del sistema y el análisis de la
retroalimentación recopilada a través de medios digitales.

== Técnicas

Las técnicas de investigación a emplear en el proyecto son:

- Análisis documental, para la revisión de antecedentes teóricos,
  normativos y aplicaciones similares.

- Encuestas estructuradas en línea, orientadas a identificar
  percepciones generales y expectativas de los usuarios respecto a la
  aplicación.

- Análisis exploratorio de resultados, para interpretar la información
  recolectada y apoyar la evaluación de la solución desarrollada.

== Instrumentos

Los instrumentos a utilizar en el proyecto incluyen:

- Guías de análisis documental para sistematizar la revisión de fuentes
  y antecedentes.

- Cuestionarios estructurados distribuidos en línea para la recolección
  de información.

- Registros de funcionamiento del sistema y herramientas básicas de
  análisis de datos para organizar y procesar la información obtenida.

== Población

La población objeto de estudio estará conformada por usuarios del
transporte público del área metropolitana de Cochabamba, conformada por
los municipios de Cercado, Quillacollo, Sipe Sipe, Tiquipaya, Vinto,
Colcapirhua y Sacaba (Cabrera & Moyano, 2022). Para las pruebas de la
aplicación se trabajará con una muestra de usuarios seleccionada
mediante muestreo no probabilístico por conveniencia, compuesta por
personas que utilicen habitualmente el transporte público y cuenten con
un dispositivo móvil con sistema Android o iOS.

La validación del sistema se realizará a través de una prueba piloto, en
la que los participantes interactuarán con la aplicación en condiciones
reales de uso. La aceptación y satisfacción del sistema será medida
mediante un cuestionario estructurado basado en la Escala de Likert de
cinco puntos, evaluando dimensiones como usabilidad, utilidad percibida
y facilidad de uso.

== Fuentes

Las fuentes de información se clasifican en:

- Primarias, constituidas por los datos obtenidos a través de las
  encuestas aplicadas a los usuarios del transporte público, los
  resultados de las pruebas piloto realizadas con la aplicación,
  artículos científicos de investigación original y documentación
  técnica oficial de las herramientas utilizadas en el desarrollo del
  sistema.

- Secundarias, conformadas por artículos de revisión bibliográfica,
  reportes sobre movilidad urbana, y reportes sobre aplicaciones de
  transporte en otras ciudades.

// =====================================================================
// CAPÍTULO I — MARCO TEÓRICO
// =====================================================================

#pagebreak()
#align(center)[
  #v(2cm)
  #text(size: 18pt, style: "italic")[CAPÍTULO I]

  #v(0.5em)
  #text(size: 16pt, weight: "bold")[MARCO TEÓRICO]
]
#pagebreak()

= Marco teórico

A continuación, se presenta una revisión de bibliografía en cuanto al
estado actual del transporte público en Cochabamba, así como de las
tecnologías y estrategias que se utilizaron en el presente proyecto, las
cuales incluyen crowdsourcing, algoritmos relacionados a sistemas
geográficos, el enfoque open source, y las herramientas específicas para
la implementación del sistema.

== Transporte público urbano en Cochabamba

El sistema de transporte público en el Área Metropolitana de Cochabamba
se constituye sobre un modelo de paratránsito de carácter privado,
informal, autónomo y con escasa regulación estatal (Cabrera et al.,
2018; Cabrera & Moyano, 2022). Esta región metropolitana está integrada
por las áreas urbanas de siete municipios: Cercado, Quillacollo, Sipe
Sipe, Tiquipaya, Vinto, Colcapirhua y Sacaba (Cabrera & Moyano, 2022;
véase Figura 3).

#figure(
  image("images/image4.jpg", width: 100%),
  caption: [Área Metropolitana de Cochabamba],
  supplement: "Figura",
  kind: image,
)

#source[Cabrera & Moyano, 2022.]

A diferencia de otras ciudades bolivianas, el servicio en su mayoría no
depende de una administración estatal centralizada, sino de una compleja
red de operadores organizados en sindicatos, asociaciones y
cooperativas. Este sistema ha funcionado bajo un régimen de transporte
libre institucionalizado desde 1985, lo que permitió una expansión
desorganizada y una oferta excesiva de vehículos de baja capacidad que
responden más a la lógica del mercado que a la planificación urbana
(Cabrera & Moyano, 2022). Desde una perspectiva socioterritorial, este
sistema funciona como un dispositivo de urbanización, consolidando
nuevos asentamientos periféricos al proveer la principal red de
conectividad física disponible en áreas donde el Estado no ha
planificado infraestructuras básicas (Cabrera et al., 2018).

=== Medios de transporte público

Como indican Cabrera et al. (2018), la oferta de movilidad motorizada
para pasajeros en la metrópoli se distribuye principalmente en cuatro
modalidades de vehículos automotores: micros, coasters, trufis y
taxi-trufis (véase Figura 4).

- *Micros:* Constituyen la modalidad más antigua, con unidades de gran
  envergadura y capacidad para 35 a 40 pasajeros; con mayor presencia en
  las áreas centrales de Cochabamba y Quillacollo.

- *Coasters (costero, en inglés):* Minibuses con una capacidad de 16 a
  30 usuarios, cuya circulación es frecuente en los municipios de
  Quillacollo, Sipe Sipe y Vinto.

- *Trufis (Transporte de Ruta Fija):* Son furgonetas o minibuses
  adaptados para transportar entre 7 y 14 pasajeros; es la modalidad con
  mayor cobertura en toda la conurbación.

- *Taxi-trufis:* Vehículos tipo sedán que operan en rutas fijas con
  capacidad de 4 a 7 pasajeros; representan, junto a los trufis, la
  mayor parte de la oferta de transporte público.

En conjunto, este parque automotor supera las 40,000 unidades, lo que
genera una saturación de información y tráfico en los nodos centrales
(Mejia & Daga, 2014).

#figure(
  image("images/image5.png", width: 100%),
  caption: [Tipos de vehículos de transporte público en la región metropolitana de Cochabamba.],
  supplement: "Figura",
  kind: image,
)

#source[Cabrera & Moyano, 2022.]

=== Características operativas

De acuerdo con Cabrera (2023), el modelo operativo del transporte en
Cochabamba se fundamenta en el concepto de "hombre-camión", donde el
transportista ejerce de forma unilateral la propiedad, administración y
operación de su unidad vehicular. Técnicamente, el sistema destaca por
un dinamismo informal, donde las rutas se crean, extienden o subdividen
mediante acuerdos directos entre los operadores y las dirigencias
barriales (OTB), operando frecuentemente fuera del registro oficial de
los gobiernos municipales (Cabrera & Moyano, 2022).

Uno de los rasgos más críticos y complejos para el usuario es la
extensión de rutas y su subdivisión en ramales. Bajo una misma
denominación de "línea", las organizaciones suelen operar múltiples
recorridos secundarios para cubrir la demanda de diversos sectores o
nuevos barrios (Cabrera & Moyano, 2022). Esta fragmentación se
manifiesta visualmente a través de un código informal de identificación:
los vehículos de una misma línea se diferencian entre sí mediante
banderines de colores, letras específicas, letreros en los parabrisas o
franjas de colores distintivos en la carrocería. Por ejemplo, Cabrera &
Moyano (2022) identificaron que el sindicato Santa Rosa de Lima se
comprende por 22 ramales utilizando combinaciones de letras, nombres de
paradas y colores específicos para orientar a la población. En la Figura
5 se puede observar ejemplos de otras líneas con esta fragmentación,
como son los taxi-trufis 150 y el 123.

#figure(
  image("images/image6.jpg", width: 100%),
  caption: [Extensión y subdivisión de rutas],
  supplement: "Figura",
  kind: image,
)

#source[Cabrera & Moyano, 2022.]

Esta proliferación de variantes es tan amplia que se han identificado
132 líneas que operan un total de 648 rutas distintas en la región,
llegando a concentrarse hasta 500 rutas en el centro comercial del
municipio de Cercado, lo que genera una saturación crítica de las vías
(Cabrera & Moyano, 2022).

Lamentablemente, este mapeo de rutas fue realizado de forma privada y
los datos no se encuentran disponibles al público (Cabrera, comunicación
personal, 28 de diciembre de 2025). Esta falta de transparencia en los
recorridos exactos y la dependencia de señales visuales informales (como
los colores y banderines) justifican la necesidad técnica de
herramientas de información que sistematicen la inteligencia colectiva
de la urbe.

=== Desafíos actuales

Desde la computación urbana, el principal desafío es la ausencia de
información oficial, pública y estandarizada sobre las líneas de
transporte, sus recorridos, paradas y subdivisiones (Cabrera et al.,
2018). Esta carencia se divide en los siguientes factores:

- *Inoperatividad de plataformas globales:* En Bolivia, servicios como
  Google Maps no integran datos del transporte público, dejando al
  usuario dependiente del conocimiento empírico o la consulta directa.

- *Fragmentación y superposición de datos:* La coexistencia de cientos
  de rutas que se superponen (hasta 500 rutas en puntos críticos del
  centro) genera una sobresaturación visual y cognitiva para el
  ciudadano (Cabrera & Moyano, 2022).

- *Necesidad de sistematización:* La movilidad actual reside en una
  "inteligencia colectiva" no digitalizada; la implementación de
  soluciones basadas en crowdsourcing es fundamental para capturar,
  procesar y devolver esta información a la población, transformando el
  sistema informal en una red de datos inteligente (Cabrera et al.,
  2018).

== Crowdsourcing para recolección de información

El crowdsourcing fue acuñado originalmente por Howe (2006) en 2006 para
describir el acto de una empresa, institución u organización que toma
una función tradicionalmente realizada por empleados y la externaliza a
una red indefinida y generalmente amplia de personas mediante una
convocatoria abierta.

Académicamente, se le considera una forma explícita de integrar las
aportaciones de los consumidores en las actividades de comercialización
y una categoría fundamental dentro del paradigma de la innovación
abierta (open innovation) (Kleemann et al., 2008). Este fenómeno se
sustenta en la participación masiva a través de Internet y dispositivos
móviles, permitiendo resolver problemas científicos o empresariales
complejos que, en ocasiones, superan la capacidad de departamentos
internos de Innovación y Desarrollo (Hossain & Kauranen, 2015).

Las aplicaciones exitosas del crowdsourcing abarcan desde la generación
de ideas y concursos de diseño (Schweitzer et al., 2012) hasta el
microtasking (pequeñas tareas que pueden o no ser remuneradas) (Kittur
et al., 2011), y la producción de software de calidad empresarial a
través del open source (Howe, 2006).

=== Crowdsourcing aplicado a sistemas de movilidad

El crowdsourcing móvil (MCS) se define como un paradigma donde
individuos con dispositivos móviles recopilan y comparten datos para
resolver problemas complejos de forma distribuida (Kong et al., 2019). A
diferencia del crowdsourcing tradicional basado en la web, el MCS
aprovecha la movilidad de los usuarios y los sensores integrados, como
el GPS y el acelerómetro, para capturar información del entorno físico
en tiempo real (Kong et al., 2019; Panta et al., 2019). En el ámbito de
la movilidad urbana, este enfoque permite que los ciudadanos pasen de
ser consumidores pasivos a prosumidores que generan inteligencia
colectiva sobre el sistema de transporte (Cabrera, 2023; Kong et al.,
2019).

Esta tecnología es particularmente efectiva para mapear sistemas de
paratránsito e informalidad, donde la ausencia de información oficial
genera incertidumbre (Cabrera et al., 2018). Proyectos similares, como
"Llajta Rutas Metropolitana" en Cochabamba o "Digital Matatus" en
Nairobi, han demostrado que el seguimiento de trayectorias mediante GPS
permite reconstruir rutas y horarios de servicios que no están
integrados en plataformas globales como Google Maps (Cabrera et al.,
2018; Hou et al., 2018). Técnicamente, el sistema puede recolectar datos
de forma participativa, donde el usuario selecciona activamente su línea
de viaje, u oportunística, capturando la ubicación en segundo plano para
inferir patrones de desplazamiento y popularidad de trayectos
(Phuttharak & Loke, 2019).

=== Mecanismos de validación colaborativa de datos

Debido a que los datos generados por la multitud pueden ser ruidosos,
incompletos o provenir de usuarios malintencionados, la validación de
respuestas es un paso crítico para garantizar la fiabilidad del sistema
(Hou et al., 2018; Hung et al., 2017). Existen diversos métodos
académicos para realizar esta verificación sin depender exclusivamente
de expertos humanos costosos:

- *Votación por Mayoría (Majority Voting):* Es el mecanismo más común
  de control de calidad basado en la redundancia. Bajo este esquema, una
  ruta deducida algorítmicamente se considera válida si un número
  suficiente de usuarios independientes confirman o proporcionan datos
  coincidentes (Hirth et al., 2013).

- *Enfoque de Grupo de Control (Control Group):* En esta modalidad, un
  usuario realiza la tarea principal (recolectar el trayecto) y otros
  miembros de la comunidad actúan como validadores, calificando la
  veracidad de la información según criterios predefinidos (Hirth
  et al., 2013).

- *Sistemas de Puntuación de Retroalimentación (Feedback Scoring):*
  Estos algoritmos calculan la confiabilidad de un reporte basándose en
  las puntuaciones asignadas por otros usuarios y el historial de
  contribuciones del informante. Un usuario con alta reputación o
  "social badge" actúa como un multiplicador de credibilidad, permitiendo
  que sus validaciones requieran menos confirmaciones adicionales para
  ser publicadas (Panta et al., 2019).

- *Detección de Usuarios Defectuosos:* Para proteger la integridad de
  la base de datos, se aplican métodos probabilísticos que identifican a
  "spammers" o trabajadores descuidados, excluyendo sus respuestas si
  estas se desvían significativamente del consenso o de la estructura
  lógica de la red vial (Hung et al., 2017).

Estos mecanismos permitirán reducir la incertidumbre del conjunto de
datos y asegurar que el mapa resultante refleje la realidad operativa de
las líneas de transporte en Cochabamba.

== Sistemas de información geográfica (SIG)

Un Sistema de Información Geográfica (SIG) se define como una colección
organizada de hardware, software y datos geográficos diseñada para la
captura, almacenamiento, procesamiento y visualización de información
espacial compleja (Sobota et al., 2008). En el contexto de la movilidad
urbana, un SIG permite modelar la infraestructura vial como un grafo de
red $G(V,E)$, donde los segmentos de calle (aristas) poseen atributos
específicos como longitud, sentido y restricciones de giro (Bast et al.,
2016; Liu et al., 2024). Para una aplicación de transporte, el SIG no
solo actúa como un repositorio cartográfico, sino como el motor de
análisis espacial que permite transformar nubes de coordenadas crudas en
secuencias lógicas de aristas que representan el recorrido real de un
vehículo (Sobota et al., 2008).

=== Datos de GPS y sus limitaciones

// (Sección por desarrollar)

=== Coincidencia de trayectos (Map Matching)

La Coincidencia de Trayectos o _Map Matching_ es el proceso
computacional de asignar una secuencia de posiciones medidas (geopoints)
a los segmentos correspondientes de una red vial en un mapa digital
(Hou, 2021; Kubička et al., 2015). Dada la naturaleza de la presente
propuesta, se prioriza el enfoque de Offline Map Matching, el cual
procesa trayectorias completas o conjuntos de datos históricos para
generar rutas con una alta precisión, siendo ideal para aplicaciones de
análisis de comportamiento de viaje y reconstrucción de itinerarios
(Hou, 2021; Hou et al., 2018).

Debido a que los datos recolectados suelen presentar ruido por deriva de
señal (GPS drift) o bajas tasas de muestreo, el algoritmo no puede
limitarse a una simple asignación geométrica de puntos a la calle más
cercana (Hou, 2021; Liu et al., 2024). En su lugar, se emplean modelos
probabilísticos como el Modelo Oculto de Márkov (HMM), donde las
probabilidades de emisión (distancia del punto a la calle) y de
transición (probabilidad de que dos calles formen una ruta lógica)
permiten deducir el camino más probable, incluso cuando los puntos están
dispersos (Hou, 2021; Hou et al., 2018).

==== Algoritmo Modelo Oculto de Markov (HMM)

// (Subsección por desarrollar)

=== Identificación y reconstrucción de rutas

La identificación de trayectos a partir de datos masivos etiquetados por
"línea" requiere explotar la correlación inter-trayectoria, definida
como la relación entre múltiples viajes que comparten segmentos viales
comunes (Liu et al., 2024). Al consolidar miles de geopoints registrados
por diferentes usuarios bajo una misma etiqueta de línea, el sistema
puede construir un grafo de trayectorias utilizando una representación
de rejillas (grids) para integrar la información distribuida (Liu
et al., 2024).

Este enfoque permite aplicar técnicas de agregación de inteligencia
colectiva, donde la ruta final de la línea se determina mediante el
concepto de popularidad de ruta (route popularity) (Ghezzi et al., 2017;
Hou, 2021). La popularidad se cuantifica según el número de trazas de
usuarios que confirman un mismo segmento vial, permitiendo que el
sistema identifique y descarte el ruido individual para retener
únicamente el itinerario operativo real (Hou, 2021). Finalmente, la
alineación en el espacio latente entre las trayectorias de los usuarios
y los segmentos del mapa permite que la aplicación proporcione una
inferencia robusta, transformando puntos inconexos en una
infraestructura de datos inteligente para la población (Liu et al.,
2024).

==== Algoritmo DBSCAN

// (Subsección por desarrollar)

== Software de código abierto (Open Source)

El software de código abierto (Open Source Software o OSS) se define
como aquel cuyo código fuente es público, permitiendo su uso,
modificación y distribución libre de costo (Hossain & Kauranen, 2015).
Técnicamente, su éxito radica en la creación de una comunidad sostenible
que coevoluciona con el sistema para desarrollar código con rapidez y
depurarlo de forma efectiva (Aberdour, 2007). Este modelo se describe
mediante el "modelo de cebolla", donde un núcleo pequeño de
desarrolladores líderes (core team) es apoyado por capas sucesivas de
desarrolladores contribuyentes, informantes de errores (bug reporters) y
usuarios finales (Aberdour, 2007).

Uno de los pilares de su calidad es la Ley de Linus, acuñado por Raymond
(2001), que establece que "dado un número suficientemente elevado de
ojos, todos los errores se vuelven obvios", subrayando el poder del peer
review (revisión por pares) masivo para alcanzar niveles de fiabilidad
comparables o superiores al software comercial. En el ámbito legal, su
gobernanza se apoya en una amplia gama de licencias (como GPL, BSD o
MPL) que utilizan el derecho de autor no para restringir, sino para
garantizar la libertad de acceso y la reciprocidad en las mejoras del
código (Fitzgerald, 2006).

Aplicar este enfoque al desarrollo del sistema permitirá que voluntarios
de Cochabamba puedan dar mantenimiento a la aplicación, sin depender de
una organización externa para mantenerla actualizada.

== Marco tecnológico

A continuación, se presentan las tecnologías principales que se
utilizaron para la implementación del sistema propuesto.

=== Recolección de datos — Aplicación móvil

React Native / Expo --- cross-platform, single codebase for Android/iOS,
background location support.

TypeScript --- why over plain JS.

AsyncStorage / local buffering --- why local-first before syncing.

=== API REST y backend

Python --- ecosystem for geodata processing.

FastAPI --- why over Django/Flask (async, automatic OpenAPI docs, type
hints).

REST --- why over GraphQL for this use case.

Telemetry --- one paragraph explaining what distributed tracing is and
why it's useful for a multi-step pipeline like this one.

=== Base de datos

PostgreSQL --- reliability, extensibility.

PostGIS --- spatial types and functions (storing LineStrings, querying
by distance, etc.) --- worth a small explanation since it's central to
the project.

SQLAlchemy + GeoAlchemy2 --- ORM with spatial support.

=== Procesamiento geodésico

OpenStreetMap --- open road network data, why this matters for HMM.

Road network library (whichever you use for map matching --- OSRM,
Valhalla).

Shapely --- geometric operations in Python.

NumPy / scikit-learn --- numerical computing and DBSCAN implementation.

=== Análisis y visualización

Marimo --- reactive notebooks, why over Jupyter (reproducibility, no
hidden state).

pydeck --- WebGL map rendering for large point clouds.

GeoJSON files --- as seed storage for reproducibility.

=== Base de datos PostgreSQL

Como señalan Obe & Hsu (2017), PostgreSQL es un sistema de gestión de
bases de datos relacionales de clase empresarial y código abierto,
reconocido por ser uno de los más avanzados a nivel mundial. Se define
no solo como una base de datos, sino como una plataforma de aplicaciones
robusta que permite la ejecución de procedimientos almacenados en
múltiples lenguajes de programación, tales como PL/pgSQL, Python, Perl y
JavaScript (PL/V8).

Una de sus características académicas más distintivas es su
extensibilidad, permitiendo a los usuarios definir sus propios tipos de
datos, operadores y funciones personalizadas (Obe & Hsu, 2017). Una de
las extensiones más favorables para el presente proyecto es la de
'_postgis_', que integra tipos de datos de geolocalización como puntos
de coordenadas y trayectos.

=== FastAPI Framework

FastAPI es un framework web moderno y de alto rendimiento diseñado para
la construcción de APIs con Python, fundamentado en las anotaciones de
tipos estándar del lenguaje. Su arquitectura técnica se apoya en
Starlette para la gestión de las partes web y en Pydantic para la
validación y serialización de datos, lo que le otorga una velocidad
comparable a frameworks en Go o Node.js. FastAPI destaca por su
capacidad para manejar la programación asíncrona nativa mediante la
sintaxis async/await, optimizando la eficiencia en operaciones de
entrada/salida. Además, ofrece funcionalidades automáticas de
documentación interactiva (Swagger UI y ReDoc) basadas en el estándar
OpenAPI (Luca, 2024).

=== React Native Framework

De acuerdo con Sahniuk (2024), React Native es una biblioteca y
framework de JavaScript, desarrollado originalmente por Meta, destinado
al desarrollo de aplicaciones móviles nativas. A diferencia de los
frameworks híbridos tradicionales, React Native no renderiza una vista
web, sino que utiliza bloques de construcción de la interfaz de usuario
nativa de sistemas operativos como Android (Java/Kotlin) e iOS
(Objective-C/Swift).

Su arquitectura se basa en la comunicación entre un hilo de JavaScript y
un hilo nativo a través de un puente (bridge), o mediante la nueva
JavaScript Interface (JSI), permitiendo un rendimiento fluido y una
experiencia de usuario cercana a las aplicaciones desarrolladas de forma
puramente nativa.

// =====================================================================
// CAPÍTULO II — INGENIERÍA DEL PROYECTO
// =====================================================================

#pagebreak()
#align(center)[
  #v(2cm)
  #text(size: 18pt, style: "italic")[CAPÍTULO II]

  #v(0.5em)
  #text(size: 16pt, weight: "bold")[INGENIERÍA DEL PROYECTO]
]
#pagebreak()

= Ingeniería del proyecto

== Visión general del sistema

// (Sección por desarrollar)

== Fase de análisis

La fase de análisis tiene como objetivo comprender el contexto de uso de
la aplicación y formalizar las funcionalidades que el sistema debe
ofrecer. Para ello se siguió una secuencia estructurada en tres etapas:
primero, una caracterización de los posibles usuarios de la aplicación
mediante perfiles que describen su situación, limitaciones y
necesidades; segundo, la especificación de casos de uso que describen
las interacciones previstas entre los usuarios y el sistema; y tercero,
la definición de requisitos funcionales y no funcionales derivados de
dichos casos de uso. Esta secuencia garantiza que cada decisión de
diseño pueda ser trazada hasta una necesidad real identificada en el
análisis.

=== Caracterización de usuarios

Para diseñar el sistema de modo que aporte un valor real a los usuarios
primero se deben entender sus necesidades. Para esto se realizó una
caracterización de posibles perfiles de usuarios que harían uso de la
aplicación, tomando en cuenta su situación, frustraciones y qué
necesidades debe cubrir el sistema. A continuación se presentan los
casos estudiados.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    align: left,
    table.header(table.cell(colspan: 2)[*Carla Velasco Salazar, 18 años, Potosí*]),
    [Situación],
    [Carla viajó a Cochabamba porque desea entrar a una universidad de
     allí. Había visitado Cochabamba antes, pero no lo suficiente para
     movilizarse con confianza. Además, se encuentra buscando un
     departamento para alquilar que la conecte con diferentes puntos de
     la ciudad.],
    [Frustraciones],
    [
    - Al llegar, no sabe qué micro, trufi o taxi-trufi tomar para ir a
     inscribirse a la universidad. Puede preguntar a alguien, pero
     entonces no sabe dónde bajar. Puede tomar un taxi, pero eso también
     implica pagar más.

    - Tiene que visitar los posibles departamentos que alquilará, pero
     tampoco sabe cómo movilizarse entre ellos. Preguntar a alguien
     empieza a sentirse más pesado al ser repetitivo.

    - No sabe qué departamento le conviene más, ya que no conoce qué
     micros o trufis se encuentran cerca y a dónde llevan. Puede
     preguntar al dueño, pero teme que le mienta a fin de convencerla
     para alquilarlo.
    ],
    [Necesidades],
    [Carla necesita poder orientarse en una ciudad que no conoce bien,
     tanto para llegar a destinos puntuales como para conocer las
     conexiones entre zonas. Esta segunda necesidad es especialmente
     relevante al momento de elegir dónde vivir, ya que quiere tomar esa
     decisión con información real sobre la conectividad del lugar, sin
     depender de lo que le digan terceros.],
  ),
  caption: [Caracterización de usuario Carla Velasco Salazar],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    table.header(table.cell(colspan: 2)[*Marco Antonio Quispe Flores, 34 años, Cochabamba*]),
    [Situación],
    [Marco trabaja en el centro de Quillacollo y vive en Cochabamba.
     Cada día realiza un viaje de aproximadamente dos horas entre su
     hogar y su trabajo, utilizando trufis que recorren la avenida
     Blanco Galindo. Conoce bien su ruta habitual, pero escuchó en las
     noticias que esta semana habrá un bloqueo.],
    [Frustraciones],
    [
    - El bloqueo corta la avenida principal, obligando a los micros y
     trufis a tomar desvíos improvisados. Marco no sabía qué día empezaba
     el bloqueo y ya está dentro del trufi cuando ve que la ruta cambia.
     Puede bajar y tomar un taxi para no llegar tarde, pero también
     implica un gasto imprevisto adicional.

    - Otro día de bloqueo, su trufi se detuvo en el punto de corte y no
     tomó ningún desvío. Marco no conoce las líneas locales que circulan
     por calles alternativas menos conocidas, y termina caminando desde
     el bloqueo hasta un punto libre de la carretera principal,
     perdiendo tiempo adicional.
    ],
    [Necesidades],
    [En situaciones de bloqueo, Marco necesita poder anticiparse antes
     de salir de casa, conociendo el estado real de las rutas que utiliza.
     También necesita poder identificar líneas de transporte alternativas
     en zonas que no conoce bien, para no quedarse sin opciones cuando su
     ruta habitual queda interrumpida y evitar así tanto el costo extra
     del taxi como la pérdida de tiempo caminando.],
  ),
  caption: [Caracterización de usuario Marco Antonio Quispe Flores],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    table.header(table.cell(colspan: 2)[*Ximena Molina Ocampo, 41 años, Sacaba*]),
    [Situación],
    [Ximena trabaja en el centro de Cochabamba y vive en Sacaba. Para el
     trayecto entre municipios utiliza su vehículo propio, ya que le
     permite llegar más rápido que el transporte público. Sin embargo,
     para evitar el tráfico del centro, prefiere estacionar en algún
     punto periférico de la ciudad y completar el recorrido final en
     micro o trufi.],
    [Frustraciones],
    [
    - No siempre encuentra espacio para estacionar en el mismo sitio, ya
     que otras personas hacen lo mismo y las calles cercanas a su zona
     habitual a veces están ocupadas. Esto la obliga a buscar en calles
     diferentes, alejándose de las paradas que ya conoce.

    - Al estacionar en una calle distinta a la habitual y no conocer con
     certeza las líneas cercanas, tomó una línea que creía conocer, pero
     resultó ser una variante de la misma y terminó en una zona
     completamente desconocida.
    ],
    [Necesidades],
    [Ximena necesita poder orientarse desde puntos de la ciudad que
     varían día a día, identificando qué transporte público tiene
     disponible cerca y si efectivamente lo lleva hacia su destino.
     También necesita contar con suficiente información contextual para
     no cometer errores de dirección que le hagan perder tiempo o
     terminar en un lugar desconocido.],
  ),
  caption: [Caracterización de usuario Ximena Molina Ocampo],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

Por otro lado, así como existen personas que necesitan orientación para
movilizarse, hay quienes cumplen un rol opuesto: son consultadas con
frecuencia por familiares, conocidos o incluso desconocidos que buscan
indicaciones sobre cómo llegar a un destino en transporte público. Si
bien estas personas suelen estar dispuestas a ayudar, la situación
presenta limitaciones que reducen la utilidad de esa ayuda o generan
inconvenientes para quien la presta. En la Tabla 5 se detallan estos
casos.

#figure(
  table(
    columns: (1fr, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [*Situación*], [*Limitación*],
    [*Jorge Mamani, 52 años.* Jorge conoce gran parte de las rutas de la
     ciudad por años de experiencia movilizándose en transporte público.
     En su círculo familiar y laboral es la persona de referencia cuando
     alguien necesita saber cómo llegar a algún lugar.],
    [Recibe consultas repetidas por mensajes y en persona, a veces sobre
     los mismos destinos. Aunque quiere ayudar, responder individualmente
     cada vez le demanda tiempo y atención.],
    [*Carmen Flores, 47 años.* Carmen tiene una tienda de barrio que, por
     su ubicación, es punto de referencia habitual en la zona. Con
     frecuencia, transeúntes entran a su local únicamente para preguntar
     cómo llegar a algún destino.],
    [Las consultas interrumpen su actividad y provienen de personas que
     no hacen ninguna compra. La situación se repite varias veces al día
     y escapa a su control.],
    [*Rodrigo Peña, 24 años.* Rodrigo conoce bien su zona y las rutas que
     frecuenta. Cuando alguien le pregunta cómo llegar a un lugar,
     intenta ayudar, pero le cuesta transmitir la información de forma
     clara a alguien que no conoce las calles.],
    [Al no poder referirse a nombres de calles que el otro reconozca,
     recurre a referencias visuales como señales o edificios, lo que hace
     sus indicaciones poco precisas y difíciles de seguir y recordar sin
     conocer la zona.],
    table.cell(colspan: 2)[*Necesidad en común.* Los tres casos reflejan
     una disposición a compartir conocimiento sobre rutas, pero sin un
     medio adecuado para hacerlo de forma eficiente. Contar con una manera
     sencilla de contribuir con información que otros puedan aprovechar
     representaría un beneficio colectivo, aliviando al mismo tiempo la
     carga que recae sobre estas personas de forma individual.],
  ),
  caption: [Caracterización de usuarios contribuidores],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

En conjunto, los perfiles analizados permiten identificar dos tipos de
valor que el sistema debe generar: por un lado, facilitar el acceso a
información de movilidad para quienes la necesitan; por otro, ofrecer un
medio simple y accesible para que quienes ya poseen ese conocimiento
puedan compartirlo. Es precisamente la interacción entre estos dos roles
la que sostiene el modelo de crowdsourcing sobre el que se basa la
aplicación, donde la utilidad del sistema crece a medida que más
usuarios participan, ya sea consultando o contribuyendo.

=== Casos de uso

A partir de los perfiles descritos en la sección anterior se
identificaron las necesidades más representativas, que se desarrollan en
esta sección en forma de casos de uso y que servirán de base para la
definición de requerimientos del sistema. Adicionalmente, durante el
análisis se identificaron necesidades de información complementaria
--- como tarifas y horarios de servicio --- que, si bien no están
asociadas a un perfil específico, representan datos de valor para
cualquier usuario que planifique movilizarse.

Para la especificación de los casos de uso se identificaron tres
actores, cuyos roles se describen a continuación.

El *Usuario* representa a cualquier persona que utiliza la aplicación
para consultar información sobre el transporte público. No requiere
registro previo y puede planificar rutas, consultar líneas cercanas,
revisar desvíos activos y guardar rutas de su interés.

El *Usuario Contribuidor* es un Usuario que, además de consultar
información, decide aportar datos al sistema. Puede grabar recorridos,
reportar desvíos, registrar tarifas y validar rutas inferidas. Al
heredar del Usuario, tiene acceso a todas las funcionalidades de
consulta. Su participación es voluntaria y constituye la base del modelo
colaborativo de la aplicación.

El *Sistema* representa los procesos automáticos que se ejecutan de
forma autónoma, sin intervención del usuario. Es responsable de
reconstruir rutas a partir de los recorridos grabados, inferir horarios
de operación y enviar notificaciones a los usuarios.

La Figura 6 presenta el diagrama de casos de uso del sistema, mostrando
los actores identificados, los casos de uso asociados a cada uno y las
relaciones entre ellos.

#figure(
  image("images/image7.png", width: 100%),
  caption: [Diagrama de Casos de Uso],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

Las Tablas 6 a 19 detallan cada caso de uso mediante fichas descriptivas
que especifican el objetivo, los actores involucrados, las
precondiciones, los flujos de interacción y las postcondiciones. Se
presentan agrupados según el actor principal: primero los casos de uso
del Usuario, luego los del Usuario Contribuidor y finalmente los del
Sistema.

*a) Casos de uso del Usuario.* Los siguientes casos de uso corresponden
a las funcionalidades de consulta disponibles para cualquier usuario de
la aplicación.

La Tabla 6 describe el caso de uso principal del sistema, que permite al
usuario planificar un trayecto en transporte público entre dos puntos.

// Helper macro for use case tables
#let caso-uso(num, datos) = figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    ..datos,
  ),
  caption: [Caso de Uso: #datos.at(3)],
  supplement: "Tabla",
  kind: table,
)

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-01],
    [Caso de Uso], [Planificar ruta entre dos puntos],
    [Objetivo],
    [Permitir al usuario identificar qué líneas de transporte público
     utilizar para desplazarse desde un punto de origen hasta un destino,
     con información de tarifa estimada y frecuencia de servicio],
    [Actor], [Usuario],
    [Precondición], [El sistema cuenta con al menos una ruta registrada],
    [Flujo principal],
    [+ Ingresar un punto de origen
     + Ingresar un punto de destino
     + Solicitar la planificación de ruta
     + Visualizar las opciones de ruta disponibles, incluyendo líneas a
       tomar, puntos de abordaje y descenso, tarifa estimada y frecuencia
       aproximada de servicio],
    [Flujo alternativo],
    [a. Si no existe una ruta que conecte el origen con el destino,
     notificar al usuario que no se encontraron resultados],
    [Postcondición],
    [El usuario visualiza las opciones de ruta disponibles entre los dos
     puntos indicados],
  ),
  caption: [Caso de Uso: Planificar ruta entre dos puntos],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

La Tabla 7 describe el caso de uso que permite al usuario explorar qué
líneas de transporte público operan cerca de una ubicación específica,
independientemente de si tiene un destino definido.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-02],
    [Caso de Uso], [Consultar líneas cercanas a una ubicación],
    [Objetivo],
    [Permitir al usuario conocer qué líneas de transporte público operan
     cerca de un punto específico y hacia qué destinos se dirigen],
    [Actor], [Usuario],
    [Precondición], [El sistema cuenta con al menos una ruta registrada],
    [Flujo principal],
    [+ Ingresar o seleccionar una ubicación en el mapa
     + Solicitar las líneas cercanas a esa ubicación
     + Visualizar las líneas disponibles en el área, con información sobre
       su recorrido y destinos],
    [Flujo alternativo],
    [a. Si no existen líneas registradas cerca de la ubicación indicada,
     notificar al usuario que no se encontraron resultados],
    [Postcondición],
    [El usuario visualiza las líneas de transporte público disponibles
     cerca de la ubicación consultada],
  ),
  caption: [Caso de Uso: Consultar líneas cercanas a una ubicación],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

Cuando una línea presenta un desvío activo, el usuario puede acceder al
detalle del recorrido alternativo directamente desde los resultados de
CU-01 o CU-02. Este comportamiento se especifica en la Tabla 8.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-03],
    [Caso de Uso], [Consultar desvío activo de una línea],
    [Objetivo],
    [Permitir al usuario conocer el recorrido alternativo que está
     tomando una línea de transporte público cuando presenta un desvío
     activo],
    [Actor], [Usuario],
    [Precondición],
    [El usuario visualiza una línea que presenta un desvío activo, ya sea
     en los resultados de CU-01 o CU-02],
    [Flujo principal],
    [+ Identificar en los resultados de búsqueda una línea marcada con
       alerta de desvío activo
     + Seleccionar la alerta de desvío de esa línea
     + Visualizar el recorrido alternativo registrado para ese desvío],
    [Postcondición],
    [El usuario visualiza el recorrido alternativo vigente para la línea
     seleccionada],
  ),
  caption: [Caso de Uso: Consultar desvío activo de una línea],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

La Tabla 9 describe el caso de uso que permite al usuario guardar una
ruta planificada para consultarla posteriormente o recibir
notificaciones relacionadas a ella.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-04],
    [Caso de Uso], [Guardar ruta],
    [Objetivo],
    [Permitir al usuario guardar una ruta planificada para consultarla
     posteriormente o recibir notificaciones relacionadas a ella],
    [Actor], [Usuario],
    [Precondición],
    [El usuario visualiza los resultados de una planificación de ruta
     (CU-01)],
    [Flujo principal],
    [+ Seleccionar la opción de guardar una ruta planificada
     + Elegir el tipo de guardado: día actual o viaje recurrente
     + Opcionalmente ingresar la hora estimada de salida
     + Confirmar el guardado de la ruta],
    [Flujo alternativo],
    [a. Si se guarda para el día actual: la ruta estará visible únicamente
     durante el día actual

     b. Si se guarda como viaje recurrente: la ruta quedará visible
     diariamente y generará notificaciones ante desvíos activos],
    [Postcondición],
    [La ruta queda guardada y disponible según el tipo de guardado
     elegido],
  ),
  caption: [Caso de Uso: Guardar ruta],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

*b) Casos de uso del Usuario Contribuidor.* Los siguientes casos de uso
corresponden a las funcionalidades de contribución disponibles para los
usuarios que deciden aportar datos al sistema.

La Tabla 10 describe el caso de uso central del modelo colaborativo,
mediante el cual los usuarios registran recorridos georreferenciados que
alimentan el pipeline de reconstrucción de rutas.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-05],
    [Caso de Uso], [Grabar recorrido de una línea],
    [Objetivo],
    [Permitir al usuario contribuir al sistema registrando el recorrido
     georreferenciado de una línea de transporte público durante un
     trayecto real],
    [Actor], [Usuario Contribuidor],
    [Precondición], [El usuario cuenta con GPS activo en su dispositivo],
    [Flujo principal],
    [+ Iniciar la grabación del recorrido
     + El sistema registra la ubicación del usuario a lo largo del
       trayecto
     + Detener la grabación al finalizar el trayecto
     + Seleccionar la línea de transporte público correspondiente al
       recorrido grabado
     + Confirmar y enviar el recorrido registrado],
    [Flujo alternativo],
    [a. Si la línea correspondiente no existe en el sistema, ingresar los
     datos de la nueva línea y confirmar su creación antes de asociar el
     recorrido (CU-06)],
    [Postcondición],
    [El recorrido grabado queda registrado en el sistema y disponible
     para ser procesado por el pipeline de reconstrucción de rutas
     (CU-11)],
  ),
  caption: [Caso de Uso: Grabar recorrido de una línea],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

En caso de que la línea correspondiente a un recorrido grabado no exista
en el sistema, el usuario puede proponerla en el mismo flujo. Este
comportamiento, que extiende a CU-05, se detalla en la Tabla 11.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-06],
    [Caso de Uso], [Proponer nueva línea],
    [Objetivo],
    [Permitir al usuario registrar una nueva línea de transporte público
     en el sistema cuando no existe al momento de asociar un recorrido
     grabado],
    [Actor], [Usuario Contribuidor],
    [Precondición],
    [El usuario finalizó la grabación de un recorrido (CU-05) y la línea
     correspondiente no existe en el sistema],
    [Flujo principal],
    [+ Identificar que la línea buscada no existe en el sistema
     + Seleccionar la opción de proponer una nueva línea
     + Ingresar los datos de la nueva línea
     + Confirmar el registro de la nueva línea
     + Asociar el recorrido grabado a la línea recién creada],
    [Postcondición],
    [La nueva línea queda registrada en el sistema y el recorrido grabado
     queda asociado a ella],
  ),
  caption: [Caso de Uso: Proponer nueva línea],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

La Tabla 12 describe el caso de uso que permite al usuario reportar en
tiempo real que una línea está tomando un recorrido alternativo al
habitual, compartiendo el trayecto del desvío para que otros usuarios
puedan consultarlo.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-07],
    [Caso de Uso], [Reportar desvío activo],
    [Objetivo],
    [Permitir al usuario informar en tiempo real que una línea de
     transporte público está tomando un recorrido alternativo al habitual,
     compartiendo el trayecto del desvío para que otros usuarios puedan
     consultarlo],
    [Actor], [Usuario Contribuidor],
    [Precondición], [El usuario cuenta con GPS activo en su dispositivo],
    [Flujo principal],
    [+ Seleccionar la línea de transporte público que está tomando el
       desvío
     + Iniciar el registro del desvío
     + El sistema registra la ubicación del usuario a lo largo del
       recorrido alternativo
     + Detener el registro al llegar al destino
     + Finalizar y enviar el recorrido del desvío registrado],
    [Postcondición],
    [El desvío queda publicado inmediatamente y visible para otros
     usuarios al consultar la línea afectada (CU-03)],
  ),
  caption: [Caso de Uso: Reportar desvío activo],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

La Tabla 13 describe el caso de uso que permite al usuario registrar el
costo del pasaje de una línea entre dos municipios, contribuyendo a la
base de información tarifaria del sistema. La identificación de los
municipios de origen y destino se realiza automáticamente a partir de
las coordenadas GPS del recorrido grabado, evitando que el usuario tenga
que conocer y seleccionar las fronteras administrativas — el sistema
muestra los municipios identificados antes de la confirmación para que
el usuario pueda corregirlos si es necesario.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-08],
    [Caso de Uso], [Registrar tarifa],
    [Objetivo],
    [Permitir al usuario contribuir al sistema registrando el costo del
     pasaje de una línea de transporte público entre dos municipios o
     zonas (ej.: Cochabamba — Sacaba, Quillacollo — Tiquipaya, etc.)],
    [Actor], [Usuario Contribuidor],
    [Precondición],
    [La línea a la que se desea asociar la tarifa existe en el sistema],
    [Flujo principal],
    [+ Seleccionar la línea de transporte público
     + Identificar el municipio de origen (a partir de la ubicación GPS
       de abordaje del recorrido)
     + Identificar el municipio de destino (a partir de la ubicación GPS
       de descenso del recorrido)
     + Ingresar el monto de la tarifa
     + Confirmar el registro, visualizando los municipios identificados
       para verificación],
    [Postcondición],
    [La tarifa queda registrada en el sistema y asociada a la línea y al
     par de municipios indicados],
  ),
  caption: [Caso de Uso: Registrar tarifa],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

Al finalizar la grabación de un recorrido, el sistema invita al usuario
a confirmar cuánto pagó de pasaje. Este comportamiento, que extiende a
CU-05, se detalla en la Tabla 14.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-09],
    [Caso de Uso], [Confirmar tarifa],
    [Objetivo],
    [Permitir al usuario reportar el costo de su pasaje en base a las
     tarifas registradas anteriormente cuando finaliza la grabación de un
     recorrido, contribuyendo a la confiabilidad de la información
     tarifaria del sistema],
    [Actor], [Usuario Contribuidor],
    [Precondición],
    [El usuario finalizó la grabación de un recorrido (CU-05)],
    [Flujo principal],
    [+ El sistema pregunta al usuario por el costo de su pasaje al
       finalizar la grabación
     + Visualizar las opciones de tarifa registradas para ese tramo
     + Seleccionar el valor que corresponde al pasaje pagado],
    [Postcondición],
    [El valor seleccionado queda registrado como confirmación de la
     tarifa para ese tramo],
  ),
  caption: [Caso de Uso: Confirmar tarifa],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

La Tabla 15 describe el caso de uso que permite al usuario emitir un
voto sobre la precisión de una ruta inferida por el sistema,
contribuyendo a la confiabilidad de la información disponible.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-10],
    [Caso de Uso], [Validar ruta inferida],
    [Objetivo],
    [Permitir al usuario confirmar o rechazar una ruta reconstruida por
     el sistema, contribuyendo a la precisión de la información del
     transporte público del sistema.],
    [Actor], [Usuario Contribuidor],
    [Precondición],
    [Existe al menos una ruta inferida pendiente de validación para una
     línea a la que el usuario ha contribuido el número mínimo de veces
     requerido],
    [Flujo principal],
    [+ Visualizar una ruta inferida por el sistema
     + Revisar el recorrido propuesto en el mapa
     + Emitir un voto indicando si el recorrido es correcto o incorrecto],
    [Postcondición],
    [El voto queda registrado en el sistema y contribuye a determinar la
     confiabilidad de la ruta inferida],
  ),
  caption: [Caso de Uso: Validar ruta inferida],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

*c) Casos de uso del Sistema.* Los siguientes casos de uso corresponden
a los procesos automáticos que el sistema ejecuta de forma autónoma.

La Tabla 16 describe el proceso central del pipeline, mediante el cual
el sistema procesa los recorridos grabados para inferir o actualizar el
trazado representativo de cada línea.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-11],
    [Caso de Uso], [Reconstruir rutas],
    [Objetivo],
    [Procesar los recorridos georreferenciados registrados por los
     usuarios para inferir o actualizar el trazado representativo de cada
     línea de transporte público],
    [Actor], [Sistema],
    [Precondición],
    [Existen recorridos grabados pendientes de procesamiento],
    [Flujo principal],
    [+ Recopilar los recorridos grabados desde la última ejecución del
       pipeline de procesamiento
     + Agrupar los recorridos por línea
     + Inferir el trazado representativo de cada línea a partir de los
       recorridos agrupados
     + Comparar el trazado inferido con el trazado vigente de la línea
     + Si el trazado ha cambiado significativamente, proponer la
       actualización de la ruta
     + Publicar los trazados nuevos o actualizados],
    [Flujo alternativo],
    [a. Si una línea no cuenta con suficientes recorridos para inferir un
     trazado confiable, omitirla y dejarla pendiente para la siguiente
     ejecución],
    [Postcondición],
    [Las rutas inferidas o actualizadas quedan disponibles en el sistema
     para ser consultadas y validadas],
  ),
  caption: [Caso de Uso: Reconstruir rutas],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

A partir de los mismos recorridos grabados, el sistema estima los
horarios de operación y la frecuencia de servicio de cada línea, como se
detalla en la Tabla 17.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-12],
    [Caso de Uso], [Inferir horarios],
    [Objetivo],
    [Estimar automáticamente el horario de operación y la frecuencia de
     servicio de cada línea a partir de los recorridos grabados por los
     usuarios],
    [Actor], [Sistema],
    [Precondición],
    [Existen recorridos grabados con marca de tiempo en cantidad
     suficiente para identificar patrones de horario y frecuencia por
     línea],
    [Flujo principal],
    [+ Recopilar los recorridos grabados agrupados por línea
     + Identificar la hora más temprana y la hora más tardía en que se
       registraron recorridos para cada línea
     + Estimar la frecuencia de servicio en base al intervalo promedio
       entre recorridos consecutivos
     + Publicar los horarios y frecuencias estimados asociados a cada
       línea],
    [Flujo alternativo],
    [a. Si una línea no cuenta con suficientes recorridos para estimar una
     frecuencia confiable, publicar únicamente el rango horario sin
     frecuencia estimada],
    [Postcondición],
    [Los horarios y frecuencias estimados quedan disponibles en el
     sistema y se muestran al usuario al planificar una ruta (CU-01)],
  ),
  caption: [Caso de Uso: Inferir horarios],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

Las Tablas 18 y 19 describen los dos procesos de notificación automática
del sistema, orientados a mantener informado al usuario sobre el estado
de sus rutas guardadas.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-13],
    [Caso de Uso], [Notificar desvíos en rutas recurrentes],
    [Objetivo],
    [Alertar automáticamente al usuario cuando una de sus rutas
     recurrentes guardadas presenta un desvío activo, para que pueda
     anticiparse antes de salir],
    [Actor], [Usuario Contribuidor],
    [Precondición],
    [El usuario tiene al menos una ruta guardada como recurrente y se ha
     registrado un desvío activo en alguna de las líneas que la componen],
    [Flujo principal],
    [+ Detectar que se ha publicado un nuevo desvío activo (CU-07)
     + Identificar los usuarios que tienen rutas recurrentes que incluyen
       la línea afectada
     + Enviar una notificación a cada usuario afectado informando del
       desvío en su ruta],
    [Postcondición],
    [El usuario recibe una notificación y puede consultar el desvío
     activo (CU-03) antes de iniciar su trayecto],
  ),
  caption: [Caso de Uso: Notificar desvíos en rutas recurrentes],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    [Identificador], [CU-14],
    [Caso de Uso], [Notificar inicio de ruta],
    [Objetivo],
    [Alertar automáticamente al usuario cuando se aproxima la hora de
     salida de una ruta guardada, para que pueda prepararse con
     anticipación],
    [Actor], [Usuario Contribuidor],
    [Precondición],
    [El usuario tiene al menos una ruta guardada con hora de salida
     definida y la hora de salida está próxima],
    [Flujo principal],
    [+ Detectar que la hora de salida de una ruta guardada está próxima
     + Verificar si existen desvíos activos en alguna de las líneas que
       componen esa ruta
     + Enviar una notificación al usuario informando que su ruta está por
       iniciar],
    [Postcondición],
    [El usuario recibe una notificación con el recordatorio de su ruta],
  ),
  caption: [Caso de Uso: Notificar inicio de ruta],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

Los casos de uso presentados describen de forma exhaustiva las
interacciones previstas entre los usuarios y el sistema, cubriendo tanto
las funcionalidades de consulta como las de contribución y los procesos
automáticos. A partir de estos casos de uso se derivarán los
requerimientos funcionales y no funcionales del sistema, que se detallan
en la sección siguiente.

=== Requerimientos funcionales

A partir de los casos de uso definidos previamente se identificaron los
requerimientos funcionales del sistema, organizados en cinco módulos que
agrupan las funcionalidades según su naturaleza: consulta, desvíos,
contribución de rutas, tarifas, y rutas guardadas y notificaciones.

*a) Módulo de consulta.* El módulo de consulta agrupa los requerimientos
relacionados con las funcionalidades de búsqueda y visualización de
información de transporte público, correspondientes a los casos de uso
de planificación de ruta y consulta de líneas cercanas. Los
requerimientos de este módulo se presentan en la Tabla 20.

#figure(
  table(
    columns: (auto, 1fr, auto, auto),
    stroke: 0.5pt,
    inset: 6pt,
    align: (left, left, center, center),
    [*ID*], [*Requerimiento*], [*CU*], [*Prioridad*],
    [RF-01], [El sistema debe permitir al usuario ingresar un origen y un destino para obtener opciones de ruta en transporte público], [CU-01], [Alta],
    [RF-02], [El sistema debe mostrar las líneas a tomar, los puntos de abordaje y descenso para cada opción de ruta], [CU-01], [Alta],
    [RF-03], [El sistema debe mostrar la tarifa estimada del trayecto en los resultados de planificación], [CU-01], [Alta],
    [RF-04], [El sistema debe mostrar la frecuencia aproximada de servicio de cada línea en los resultados de planificación], [CU-01], [Media],
    [RF-05], [El sistema debe notificar al usuario cuando no exista una ruta disponible entre el origen y el destino indicados], [CU-01], [Alta],
    [RF-06], [El sistema debe permitir al usuario consultar qué líneas de transporte público operan cerca de una ubicación específica], [CU-02], [Alta],
    [RF-07], [El sistema debe mostrar el recorrido y los destinos de cada línea cercana encontrada], [CU-02], [Alta],
    [RF-08], [El sistema debe notificar al usuario cuando no existan líneas registradas cerca de la ubicación consultada], [CU-02], [Media],
  ),
  caption: [Requerimientos Funcionales: Módulo de consulta],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

*b) Módulo de desvíos.* El módulo de desvíos agrupa los requerimientos
relacionados con el reporte y la visualización de recorridos
alternativos en tiempo real. Los requerimientos de este módulo se
presentan en la Tabla 21.

#figure(
  table(
    columns: (auto, 1fr, auto, auto),
    stroke: 0.5pt,
    inset: 6pt,
    align: (left, left, center, center),
    [*ID*], [*Requerimiento*], [*CU*], [*Prioridad*],
    [RF-09], [El sistema debe permitir al usuario contribuidor iniciar y detener el registro georreferenciado de un desvío activo], [CU-07], [Alta],
    [RF-10], [El sistema debe permitir al usuario contribuidor asociar el desvío registrado a una línea de transporte público existente], [CU-07], [Alta],
    [RF-11], [El sistema debe publicar el recorrido del desvío inmediatamente una vez enviado, sin pasar por el proceso de reconstrucción de rutas], [CU-07], [Alta],
    [RF-12], [El sistema debe mostrar una alerta visual en los resultados de CU-01 y CU-02 cuando una línea presenta un desvío activo], [CU-03], [Alta],
    [RF-13], [El sistema debe permitir al usuario consultar el recorrido alternativo de una línea con desvío activo], [CU-03], [Alta],
  ),
  caption: [Requerimientos Funcionales: Módulo de desvíos],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

*c) Módulo de contribución de rutas.* Este módulo agrupa los
requerimientos relacionados con la grabación de recorridos, la
reconstrucción automática de rutas y su validación colaborativa. Es el
módulo más extenso, ya que concentra la lógica central del modelo de
crowdsourcing de la aplicación. Los requerimientos de este módulo se
presentan en la Tabla 22.

#figure(
  table(
    columns: (auto, 1fr, auto, auto),
    stroke: 0.5pt,
    inset: 6pt,
    align: (left, left, center, center),
    [*ID*], [*Requerimiento*], [*CU*], [*Prioridad*],
    [RF-14], [El sistema debe permitir al usuario contribuidor iniciar y detener el registro georreferenciado de un recorrido durante un trayecto real], [CU-05], [Alta],
    [RF-15], [El sistema debe registrar la ubicación del usuario a lo largo del trayecto mientras la grabación está activa], [CU-05], [Alta],
    [RF-16], [El sistema debe permitir al usuario contribuidor asociar el recorrido grabado a una línea de transporte público existente], [CU-05], [Alta],
    [RF-17], [El sistema debe permitir al usuario contribuidor proponer una nueva línea cuando la línea correspondiente no exista en el sistema], [CU-06], [Alta],
    [RF-18], [El sistema debe procesar los recorridos grabados para inferir o actualizar la ruta representativa de cada línea], [CU-11], [Alta],
    [RF-19], [El sistema debe detectar cambios significativos en la ruta de una línea y proponer su actualización a partir de los recorridos recientes], [CU-11], [Alta],
    [RF-20], [El sistema debe omitir del procesamiento las líneas que no cuenten con suficientes recorridos grabados para inferir una ruta confiable], [CU-11], [Media],
    [RF-21], [El sistema debe mostrar al usuario contribuidor las rutas inferidas de líneas a las que ha contribuido el mínimo requerido de veces, para su validación], [CU-10], [Media],
    [RF-22], [El sistema debe registrar el voto del usuario contribuidor sobre la precisión de una ruta inferida], [CU-10], [Media],
    [RF-23], [El sistema debe inferir el horario de operación y la frecuencia de servicio de cada línea a partir de las marcas de tiempo de los recorridos grabados], [CU-12], [Media],
    [RF-24], [El sistema debe publicar únicamente el rango horario de una línea cuando no existan suficientes recorridos para estimar una frecuencia confiable], [CU-12], [Media],
  ),
  caption: [Requerimientos Funcionales: Módulo de contribución de rutas],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

*d) Módulo de tarifas.* El módulo de tarifas agrupa los requerimientos
relacionados con el registro, confirmación y consulta de costos de
pasaje entre municipios. Los requerimientos de este módulo se presentan
en la Tabla 23.

#figure(
  table(
    columns: (auto, 1fr, auto, auto),
    stroke: 0.5pt,
    inset: 6pt,
    align: (left, left, center, center),
    [*ID*], [*Requerimiento*], [*CU*], [*Prioridad*],
    [RF-25], [El sistema debe permitir al usuario contribuidor registrar el costo del pasaje de una línea entre dos municipios], [CU-08], [Media],
    [RF-26], [El sistema debe notificar al usuario contribuidor cuando ya exista una tarifa registrada para el par de municipios y línea seleccionados, invitándolo a confirmarla], [CU-08], [Media],
    [RF-27], [El sistema debe presentar al usuario contribuidor la pregunta "¿Cuánto salió tu pasaje?" al finalizar la grabación de un recorrido], [CU-09], [Media],
    [RF-28], [El sistema debe mostrar las opciones de tarifa registradas para el tramo correspondiente al recorrido grabado], [CU-09], [Media],
    [RF-29], [El sistema debe registrar la selección del usuario como confirmación de la tarifa para ese tramo], [CU-09], [Media],
    [RF-30], [El sistema debe calcular y mostrar la tarifa estimada total de una ruta planificada como la suma de las tarifas de cada tramo], [CU-01], [Media],
  ),
  caption: [Requerimientos Funcionales: Módulo de tarifas],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

*e) Módulo de rutas guardadas y notificaciones.* Este módulo agrupa los
requerimientos relacionados con el almacenamiento de rutas de interés
para el usuario y el envío de alertas ante eventos relevantes. Los
requerimientos de este módulo se presentan en la Tabla 24.

#figure(
  table(
    columns: (auto, 1fr, auto, auto),
    stroke: 0.5pt,
    inset: 6pt,
    align: (left, left, center, center),
    [*ID*], [*Requerimiento*], [*CU*], [*Prioridad*],
    [RF-31], [El sistema debe permitir al usuario guardar una ruta planificada como ruta para día actual o como ruta recurrente], [CU-04], [Alta],
    [RF-32], [El sistema debe permitir al usuario ingresar opcionalmente una hora estimada de salida al guardar una ruta], [CU-04], [Media],
    [RF-33], [El sistema debe mostrar las rutas guardadas como para día actual únicamente durante el día en que fueron guardadas], [CU-04], [Alta],
    [RF-34], [El sistema debe mostrar las rutas recurrentes diariamente al usuario], [CU-04], [Alta],
    [RF-35], [El sistema debe enviar una notificación al usuario cuando se registre un desvío activo en alguna de las líneas que componen una de sus rutas recurrentes], [CU-13], [Alta],
    [RF-36], [El sistema debe enviar una notificación al usuario cuando se aproxime la hora de salida de una ruta guardada con hora definida], [CU-14], [Media],
    [RF-37], [El sistema debe incluir en la notificación de inicio de ruta el aviso de desvío activo si alguna de las líneas de esa ruta se encuentra afectada], [CU-14], [Alta],
  ),
  caption: [Requerimientos Funcionales: Módulo de rutas guardadas y notificaciones],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

En total se identificaron 37 requerimientos funcionales distribuidos en
los cinco módulos descritos, cubriendo tanto las funcionalidades
orientadas al usuario consultante como las del usuario contribuidor y
los procesos automáticos del sistema.

=== Requerimientos no funcionales

Los requerimientos no funcionales definen los atributos de calidad que
el sistema debe cumplir independientemente de su funcionalidad. A
diferencia de los requerimientos funcionales, no describen qué hace el
sistema sino cómo debe comportarse en términos de rendimiento,
usabilidad, disponibilidad, privacidad y escalabilidad. Los
requerimientos identificados se presentan en la Tabla 25.

#figure(
  table(
    columns: (auto, 1fr, auto, auto),
    stroke: 0.5pt,
    inset: 6pt,
    align: (left, left, center, center),
    [*ID*], [*Requerimiento*], [*Categoría*], [*Prioridad*],
    [RNF-01], [El sistema debe responder a las consultas de planificación de ruta en un tiempo máximo de 3 segundos bajo condiciones normales de uso], [Rendimiento], [Alta],
    [RNF-02], [El sistema debe registrar la ubicación del usuario durante la grabación de recorridos con una frecuencia suficiente para garantizar la precisión del trazado], [Rendimiento], [Alta],
    [RNF-03], [El pipeline de reconstrucción de rutas debe iniciar su ejecución durante la noche para no afectar la disponibilidad de la aplicación para los usuarios], [Rendimiento], [Alta],
    [RNF-04], [Las opciones de contribución deben estar claramente diferenciadas de las de consulta, de modo que el usuario comprenda en todo momento qué tipo de acción está realizando], [Usabilidad], [Alta],
    [RNF-05], [La aplicación debe funcionar correctamente en dispositivos Android e iOS de gama media con versiones de sistema operativo vigentes], [Usabilidad], [Alta],
    [RNF-06], [La aplicación debe estar disponible al menos el 95% del tiempo], [Disponibilidad], [Alta],
    [RNF-07], [El sistema debe garantizar que un fallo en el pipeline no afecte la consulta de rutas ya publicadas], [Disponibilidad], [Alta],
    [RNF-08], [El sistema no debe requerir autenticación para acceder a las funcionalidades de consulta], [Privacidad], [Alta],
    [RNF-09], [El sistema debe informar al usuario de forma clara que su ubicación será registrada antes de iniciar una grabación de recorrido o reporte de desvío], [Privacidad], [Alta],
    [RNF-10], [Los datos de ubicación recopilados durante las grabaciones no deben estar asociados a ningún identificador personal del usuario], [Privacidad], [Alta],
    [RNF-11], [El sistema debe ser capaz de procesar un volumen creciente de recorridos grabados sin degradación significativa en el rendimiento del pipeline], [Escalabilidad], [Media],
  ),
  caption: [Requerimientos no Funcionales],
  supplement: "Tabla",
  kind: table,
)

#source[Elaboración propia, 2026.]

Los requisitos funcionales y no funcionales presentados en esta sección
constituyen la base formal sobre la que se sustenta el diseño e
implementación del sistema. Su derivación a partir de los casos de uso
garantiza que cada decisión de desarrollo pueda ser trazada hasta una
necesidad concreta identificada en el análisis de usuarios.

== Fase de diseño

=== Arquitectura del sistema

La arquitectura del sistema está organizada en cuatro capas, cada una
con responsabilidades claramente definidas. La Figura 7 presenta la
arquitectura en un diagrama de componentes del sistema.

#figure(
  image("images/image8.png", width: 100%),
  caption: [Diagrama de componentes del sistema],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

La capa de _cliente_ comprende la aplicación móvil, disponible para
Android e iOS, y una base de datos local que permite el registro de
recorridos cuando el usuario no tiene conexión a internet. Los datos
recopilados localmente se sincronizan con el servidor una vez que el
dispositivo recupera la conectividad.

La capa de _servicios del sistema_ está compuesta por tres componentes.
La API REST actúa como interfaz HTTP principal del sistema, recibiendo y
respondiendo las peticiones de la aplicación móvil. El pipeline es el
componente responsable del procesamiento nocturno de los recorridos
grabados, ejecutándose de forma periódica mediante un cronjob para
reconstruir y actualizar las rutas de cada línea. El entorno
exploratorio es una aplicación basada en notebooks Marimo que permite
simular trayectos e inspeccionar el comportamiento del pipeline, siendo
de utilidad tanto durante el desarrollo como para el diagnóstico en
producción.

La capa de _paquetes internos_ contiene dos paquetes compartidos
desarrollados como parte del proyecto. El paquete database centraliza la
definición de modelos de datos y la gestión de migraciones mediante
Alembic, siendo el único punto de acceso a la base de datos. El paquete
geodata concentra la lógica de procesamiento geoespacial utilizada por
el pipeline y el entorno exploratorio, e integra a Valhalla para la
limpieza de trayectos mediante el algoritmo HMM.

Finalmente, la capa de _dependencias externas_ comprende la base de
datos PostgreSQL con la extensión PostGIS, que provee soporte para datos
geoespaciales, y Valhalla, un motor de enrutamiento que incorpora el
mapa de Bolivia y se ejecuta como servicio independiente.

Adicionalmente, el sistema incorpora un stack de telemetría basado en
Grafana, Prometheus, Loki y Tempo, que permite monitorear el
rendimiento, registrar logs y trazar peticiones a lo largo del sistema.
Este componente opera de forma independiente y no forma parte de la
lógica funcional del sistema, por lo que se detalla en el diagrama de
despliegue.

=== Diseño del pipeline de procesamiento

El pipeline de procesamiento es el componente central del modelo
colaborativo de la aplicación. Su función es procesar los trayectos
georreferenciados grabados por los usuarios para inferir las rutas
representativas de cada línea de transporte público. Se ejecuta
periódicamente de forma automática, aunque también puede activarse
manualmente para fines de desarrollo y diagnóstico.

La Figura 8 presenta el diagrama de actividades del pipeline.

El diseño del pipeline responde a tres decisiones principales. La
primera es aplicar map matching como paso inicial obligatorio, ya que
los datos GPS provenientes de dispositivos móviles contienen ruido que
haría inviable cualquier comparación o agrupación posterior sin una
corrección previa. La segunda es distinguir entre trayectos limpios y
trayectos desviados antes de aplicar el algoritmo de reconstrucción, ya
que incluir trayectos que no corresponden al recorrido habitual de la
línea distorsionaría el resultado. La tercera es requerir validación por
votos antes de publicar una ruta inferida como definitiva, reconociendo
que el algoritmo puede cometer errores y que los usuarios que grabaron
recorridos de esa línea son quienes mejor pueden validarla.

#figure(
  image("images/image9.png", width: 50%),
  caption: [Diagrama de actividades del pipeline de procesamiento de trayectos por línea],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

Respecto a la segunda decisión, existe una limitación inherente al
enfoque colaborativo: en la primera ejecución de la inferencia para una
línea, si la mayoría de los trayectos registrados son incorrectos (por
ejemplo, porque un usuario olvidó detener la grabación o eligió una
línea equivocada al guardar) la ruta inferida se vería afectada. Para
mitigar este riesgo, el pipeline solo procede con la inferencia si se
alcanza un mínimo definido de trayectos registrados, reduciendo la
probabilidad de que este escenario se produzca.

El resultado del pipeline alimenta directamente las funcionalidades de
consulta de la aplicación: las rutas confirmadas se muestran en la
planificación de trayectos y en la consulta de líneas cercanas, mientras
que las rutas pendientes de validación quedan disponibles en la sección
de contribución para que los usuarios emitan sus votos.

=== Diseño de base de datos

// (Sección por desarrollar)

=== Diseño de aplicación móvil

La aplicación móvil está organizada en cuatro módulos principales de
navegación, accesibles desde una barra de tabs en la parte inferior de
la pantalla: Explorar, Trazar, Contribuir y Favoritos. Esta estructura
refleja los dos roles identificados en el análisis (usuario y
contribuidor) agrupando las funcionalidades de consulta en Explorar y
Favoritos, y las de contribución en Trazar y Contribuir.

La Figura 9 presenta los wireframes de las pantallas de exploración y
rutas guardadas. La pantalla Explorar permite al usuario buscar líneas
cercanas a su ubicación o planificar un trayecto ingresando un origen y
un destino. La pantalla Favoritos organiza las rutas guardadas en dos
categorías (Agendado y Recurrentes) correspondientes a los dos tipos de
guardado definidos en CU-04.

#figure(
  image("images/image10.png", width: 60%),
  caption: [Diseño de wireframes de búsqueda y guardado de rutas],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

La Figura 10 presenta los wireframes de la pantalla de grabación de
recorridos. El flujo está diseñado para minimizar la fricción y reducir
el riesgo de activaciones accidentales: el usuario inicia la grabación
mediante un gesto de deslizar en lugar de un botón, ya que un botón
convencional es más susceptible de ser pulsado involuntariamente. La
selección de la línea correspondiente se realiza al detener la grabación
y no al iniciarla, de modo que el usuario solo necesita deslizar para
comenzar a contribuir, reduciendo la barrera de entrada a la
funcionalidad de grabación.

#figure(
  image("images/image11.png", width: 90%),
  caption: [Diseño de wireframes de grabación de recorridos],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

La Figura 11 presenta los wireframes de la pantalla de contribución y
validación. La sección Contribuir agrupa dos tipos de validación: la
confirmación de líneas propuestas y la validación de rutas inferidas por
el pipeline. En ambos casos el usuario puede aprobar o rechazar mediante
botones de confirmación, y en el caso de las rutas puede visualizar el
trazado completo en el mapa antes de emitir su voto.

#figure(
  image("images/image12.png", width: 60%),
  caption: [Diseño de wireframes de votación para confirmar líneas y rutas],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

== Fase de desarrollo

=== Estructura del repositorio

El sistema está organizado como un monorepo, agrupando en un único
repositorio todos los componentes del sistema. Si bien cada proyecto
mantiene su propio entorno y gestión de dependencias de forma
independiente, esta organización facilita la navegación entre
componentes, el versionado conjunto y la visibilidad de las dependencias
entre proyectos. La Figura 12 presenta el diagrama de paquetes del
repositorio.

#figure(
  image("images/image13.png", width: 90%),
  caption: [Diagrama de paquetes de la organización del repositorio],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

El repositorio está compuesto por los siguientes proyectos:

- *app* es la aplicación móvil desarrollada con React Native y Expo.
  Contiene la lógica de navegación, los componentes de interfaz, los
  servicios de grabación de recorridos en segundo plano y sincronización
  con el servidor, y la base de datos local basada en SQLite gestionada
  mediante Drizzle ORM.

- *server* es la API REST desarrollada con FastAPI. Expone los
  endpoints consumidos por la aplicación móvil y depende de los paquetes
  database y geodata para acceder a los datos y ejecutar operaciones
  geoespaciales.

- *packages/database* es el paquete compartido que centraliza la
  definición de modelos de datos mediante SqlModel y la gestión de
  migraciones con Alembic. Es el único punto de acceso a la base de
  datos PostgreSQL y es utilizado tanto por el servidor como por el
  entorno exploratorio.

- *packages/geodata* es el paquete compartido que concentra la lógica
  de procesamiento geoespacial del sistema, incluyendo el pipeline de
  reconstrucción de rutas. Expone además una interfaz de línea de
  comandos que permite al pipeline ejecutarse de forma autónoma mediante
  un cronjob. Depende del paquete database para persistir y consultar
  los datos procesados.

- *transit-lab* es el entorno exploratorio basado en notebooks Marimo,
  desplegado como aplicación web de acceso restringido. Contiene los
  notebooks de desarrollo del pipeline y los datos de semilla utilizados
  para las pruebas, asegurando reproducibilidad. Depende de los paquetes
  database y geodata para crear, manipular y procesar los datos de
  desarrollo.

- *infra* contiene la configuración de infraestructura del sistema,
  organizada en dos entornos: local, con la configuración de Docker
  Compose para el entorno de desarrollo incluyendo el stack de
  telemetría y el servidor de mapas Valhalla, y prod, con la
  configuración equivalente para el entorno de producción.

=== Módulo de gestión de líneas

El módulo de gestión de líneas es responsable del ciclo de vida de una
línea de transporte público desde que un usuario contribuidor la
propone por primera vez hasta que queda aprobada y disponible para
todos los usuarios. La entidad central es `Line`
(`packages/database/src/database/models/line.py`), que mantiene un
estado entre cuatro valores: `DRAFT` (recién creada por un
contribuidor), `PENDING` (lista para validación comunitaria, ya
deduplicada), `APPROVED` (ratificada por la comunidad y visible para
todos los usuarios) y `MERGED` (consolidada con otra línea durante la
deduplicación). Las transiciones entre estos estados se delegan en
distintos componentes del sistema: la creación inicial sucede desde
la aplicación móvil cuando el usuario guarda un recorrido y elige
"proponer línea nueva"; la deduplicación y promoción a `PENDING`
sucede en el paso `deduplicate_lines` del pipeline; y la promoción
final a `APPROVED` sucede en el paso `resolve_line_votes` cuando se
acumulan suficientes votos positivos.

La Figura 13 muestra el flujo de la propuesta de una nueva línea, en
el que intervienen el usuario contribuidor, la aplicación móvil, el
servidor y la base de datos. El usuario, al cerrar una grabación que
no asigna a ninguna línea existente, ingresa el nombre de la línea
propuesta en el modal de guardado. El cliente envía la petición
`POST /recordings/{id}/end` con `line_name` en el cuerpo; el
servidor crea la `Line` con estado `DRAFT` y la asocia a la
`TripSession` en una sola transacción.

#figure(
  // Diagrama de secuencia — Proponer nueva línea (CU-06)
  // Lifelines: Usuario contribuidor → App móvil → Server → BaseDatos
  // Mensajes:
  //   1. Usuario guarda recorrido y selecciona "proponer línea nueva".
  //   2. App: POST /recordings/{id}/end {line_name: "..."}
  //   3. Server: validar nombre + crear Line(status=DRAFT).
  //   4. Server: actualizar TripSession.line_id.
  //   5. Server → App: 200 OK (TripSession con line_id).
  //   6. App: navegar a la pantalla de "Mis contribuciones".
  // Notas: incluir indicación de que la línea aún no es visible
  // para otros usuarios hasta resolver_line_votes.
  rect(width: 100%, height: 70mm, stroke: 0.5pt + gray)[
    #align(center + horizon)[#text(size: 8pt, fill: gray, style: "italic")[
      Diagrama de secuencia — Proponer nueva línea (CU-06)\
      Lifelines: Usuario, App, Server, BaseDatos
    ]]
  ],
  caption: [Diagrama de secuencia: Propuesta de una nueva línea por un usuario contribuidor (CU-06)],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

La deduplicación de líneas (`packages/pipeline/src/pipeline/steps/deduplicate_lines.py`)
combina dos estrategias complementarias: una textual y una espacial.
La estrategia textual normaliza el nombre — minúsculas, descomposición
unicode para eliminar tildes y eliminación de prefijos comunes como
"Línea", "Line" o "L." — de modo que "Línea 230", "linea 230" y
"L. 230" colapsen al mismo valor canónico. Las líneas DRAFT con el
mismo nombre normalizado se fusionan, conservando la más antigua. Si
una línea DRAFT coincide en nombre normalizado con una línea ya
`APPROVED` o `PENDING`, se fusiona en la existente.

La estrategia espacial actúa como red de seguridad para detectar
duplicados con nombres distintos: para cada par de líneas DRAFT
restantes, computa la superposición de sus envolventes geográficas
(bounding boxes) tomadas como `ST_Envelope(ST_Collect(computed_path))`
sobre todas las sesiones de la línea. Si la intersección cubre al
menos el 70 % de la envolvente más pequeña, las líneas se fusionan.
Originalmente esta verificación operaba sobre la unión bufferizada
de los recorridos individuales, pero se simplificó a envolventes
porque sobre datos densos (decenas de sesiones por línea) la
operación `ST_Intersection` sobre polígonos de miles de vértices
saturaba la memoria de PostgreSQL. La versión actual es más
conservadora pero acotada y nunca falla por agotamiento de
recursos. La Figura 14 ilustra el flujo de decisión completo.

#figure(
  // Diagrama de actividad — Deduplicación de líneas
  // Inicio → Cargar todas las Line[DRAFT]
  //   ↓
  // (¿Hay líneas DRAFT?) ── No ──→ Fin
  //   │ Sí
  //   ↓
  // Agrupar por nombre normalizado
  //   ↓
  // Por cada grupo con ≥2 líneas: fusionar las posteriores en la más antigua
  //   ↓
  // Por cada DRAFT restante: ¿coincide con APPROVED/PENDING por nombre?
  //   │ Sí → fusionar en la existente
  //   │ No
  //   ↓
  // Para las DRAFT restantes: computar bbox por línea (ST_Envelope(ST_Collect))
  //   ↓
  // Self-join con ST_Intersects + ratio de área mínima común
  //   ↓
  // Para cada par con ratio ≥ 0.7: fusionar la más reciente en la más antigua
  //   ↓
  // Promover a PENDING todas las DRAFT no fusionadas
  //   ↓
  // Fin
  rect(width: 100%, height: 90mm, stroke: 0.5pt + gray)[
    #align(center + horizon)[#text(size: 8pt, fill: gray, style: "italic")[
      Diagrama de actividad — Deduplicación de líneas\
      Nodos: cargar DRAFTs · normalizar nombres · fusionar por nombre ·\
      fusionar contra APPROVED/PENDING · superposición de bboxes (≥70 %) ·\
      promover supervivientes a PENDING
    ]]
  ],
  caption: [Diagrama de actividad: Estrategia de deduplicación textual y espacial de líneas DRAFT],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

La promoción a `APPROVED` ocurre en el paso `resolve_line_votes` del
pipeline. Cada usuario puede votar (aprobar o rechazar) una línea en
estado `PENDING` desde la pantalla de Contribuir; los votos se
almacenan en `LineVote` con la restricción de unicidad por
`(line_id, device_id)`. El paso considera aprobada una línea cuando
acumula al menos 3 votos totales y la proporción de votos a favor
alcanza 60 %, umbrales configurables por argumento.

=== Módulo de monitoreo y reconstrucción de rutas

Este módulo es el núcleo algorítmico del sistema. Su responsabilidad
es transformar las grabaciones brutas que envían los usuarios en
representaciones publicables del trazado de cada línea, detectar
cambios significativos cuando aparecen recorridos divergentes y
agruparlos en ramales independientes cuando una línea opera más de
una variante geográfica.

El módulo está implementado como un pipeline de pasos discretos en
`packages/pipeline/src/pipeline/`, donde cada paso es una función pura
que recibe una sesión de base de datos y retorna un diccionario de
estadísticas. El orquestador `run_pipeline` (`runner.py`) ejecuta los
pasos en orden, registra cada ejecución como una fila `PipelineRun`
con su `trigger`, captura las estadísticas y los errores en
`PipelineStepResult`, y maneja la política de continuación ante fallos
(`continue_on_error`). Este registro de ejecuciones es la fuente de
auditoría del pipeline y permite consultar el historial via
`puriy pipeline history`. La Figura 15 presenta el flujo completo del
pipeline.

#figure(
  // Diagrama de actividad — Pipeline de procesamiento (CU-11)
  // Inicio → cleanup (sesiones colgadas, desvíos vencidos)
  //   ↓
  // deduplicate_lines (ver módulo anterior)
  //   ↓
  // clean_traces (Valhalla map-matching, paralelizado en 6 workers)
  //   ↓
  // reconstruct_routes (clustering por ramal + reconstrucción por cluster)
  //   ↓
  // resolve_edge_votes (promueve aristas con votos suficientes)
  //   ↓
  // resolve_routes (promueve rutas con ≥80 % de aristas confirmadas)
  //   ↓
  // resolve_line_votes (promueve líneas con votos suficientes)
  //   ↓
  // rebuild_graph (reconstruye grafo de direcciones)
  //   ↓
  // infer_schedules (frecuencias por banda horaria + día)
  //   ↓
  // Fin (PipelineRun con status COMPLETED/FAILED)
  rect(width: 100%, height: 110mm, stroke: 0.5pt + gray)[
    #align(center + horizon)[#text(size: 8pt, fill: gray, style: "italic")[
      Diagrama de actividad — Flujo del pipeline\
      9 pasos secuenciales con tracking de PipelineRun/PipelineStepResult
    ]]
  ],
  caption: [Diagrama de actividad: Flujo completo del pipeline de procesamiento (CU-11 / RF-18)],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

El paso `clean_traces` (`packages/pipeline/src/pipeline/steps/clean_traces.py`)
mapea las sesiones brutas (`processing_status = RAW`) al grafo vial
mediante el algoritmo HMM de Valhalla. Cada sesión se procesa
individualmente: se cargan sus puntos GPS, se envían al endpoint
`/trace_attributes` de Valhalla, y los resultados — la geometría
ajustada al callejero, los puntos coincidentes con su tipo
(`matched`/`interpolated`/`unmatched`) y la lista ordenada de aristas
del grafo recorridas — se persisten como un `Trip` con su
`computed_path` y un conjunto de `TripPoint` y `TripMatchedEdge`. El
estado de procesamiento de la sesión avanza de `RAW` a `PROCESSING`
durante la operación y a `PROCESSED` o `FAILED` al terminar, lo que
hace que ejecuciones repetidas del paso sean idempotentes — solo se
reprocesan sesiones que aún están en `RAW`. Para reducir el tiempo de
pared dominado por la latencia HTTP a Valhalla, las sesiones de una
misma línea se procesan en paralelo con un grupo de hasta 6 hilos
trabajadores; cada uno abre su propia sesión SQLAlchemy porque el
ORM no es seguro para hilos.

El paso `reconstruct_routes` (`packages/pipeline/src/pipeline/steps/reconstruct_routes.py`)
toma los `Trip` limpios y produce los objetos `Route` y `RouteEdge`
que son consultados por la aplicación móvil. La novedad respecto al
modelo más simple de "una línea, una ruta" es la detección automática
de ramales: para cada línea, los recorridos limpios se agrupan
mediante clustering jerárquico aglomerativo de enlace completo
sobre la matriz de distancias de Fréchet (`packages/geodata/src/geodata/ramales.py`).
El enlace completo se prefirió sobre alternativas más permisivas
porque evita el problema de encadenamiento — un recorrido ruidoso
no puede unir dos ramales reales solo por estar a media distancia
de ambos. Cada cluster resultante representa un ramal candidato y
se reconstruye independientemente con la estrategia
`edge_sequence_overlap_assembly_preview`, que ensambla la geometría
representativa a partir de las secuencias de aristas del grafo
compartidas por los recorridos del cluster. La Figura 16 detalla este
flujo por ramal.

#figure(
  // Diagrama de actividad — Reconstrucción por ramal
  // Inicio → cargar Trip[CLEAN] de la línea
  //   ↓
  // ¿len(traces) ≥ min_trips? ── No ──→ Saltar línea (Fin)
  //   │ Sí
  //   ↓
  // Cargar ramales activos existentes (Route[!SUPERSEDED] keyed por ramal_label)
  //   ↓
  // cluster_traces_into_ramales(traces, existing_ramales)
  //   ├─ Resamplear cada traza a 25m
  //   ├─ Filtro por bbox (descartar pares evidentemente lejanos)
  //   ├─ Matriz de Fréchet pareada
  //   ├─ Clustering complete-linkage al threshold (200m)
  //   ├─ Descartar clusters menores a min_cluster_size
  //   └─ Asignar etiquetas (best-match contra existentes, fresh r2/r3/...)
  //   ↓
  // Por cada cluster:
  //   ├─ Ejecutar strategy.reconstruct(traces_del_cluster)
  //   ├─ ¿geojson tiene exactamente 1 feature? ── No ──→ ramal saltado
  //   │   Sí
  //   ├─ ¿Existe ya un Route con esta ramal_label?
  //   │   No → _save_reconstruction (crea Route v1 con status=PENDING)
  //   │   Sí → discrete_frechet_distance_m(existing, candidate)
  //   │     ├─ < 50m → bumpear existing.last_compared_at (unchanged)
  //   │     └─ ≥ 50m → _save_reconstruction (supersede + nueva versión)
  //   ↓
  // Fin
  rect(width: 100%, height: 130mm, stroke: 0.5pt + gray)[
    #align(center + horizon)[#text(size: 8pt, fill: gray, style: "italic")[
      Diagrama de actividad — Reconstrucción por ramal (RF-18, RF-19)\
      Clustering complete-linkage → estrategia por cluster → decisión RF-19 por ramal
    ]]
  ],
  caption: [Diagrama de actividad: Reconstrucción por ramal, incluyendo clustering, decisión RF-19 y persistencia],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

La detección de cambios significativos (RF-19) se aplica por ramal:
si para un cluster ya existía un `Route` con la misma `ramal_label`,
se compara la geometría candidata con la existente mediante distancia
de Fréchet. Por debajo del umbral (50 m por defecto) se mantiene el
ramal vigente y solo se actualiza la marca `last_compared_at`. Por
encima, se marca el ramal vigente como `SUPERSEDED` y se publica una
nueva versión con `version = previous + 1`. Las cadenas de versión son
independientes por ramal, lo que permite que el ramal "directo" de
una línea evolucione sin afectar la cadena del ramal "vía Simón
Lopez". Una decisión de diseño explícita es rechazar reconstrucciones
fragmentadas — cuando la estrategia produce más de un fragmento para
un cluster, el ramal se salta hasta acumular más datos, garantizando
que toda ruta publicada sea un único polilínea continuo.

Para reducir la latencia entre que un usuario contribuye un recorrido
y lo ve reflejado en el sistema, el pipeline funciona bajo un esquema
híbrido evento-cron: el paso `clean_traces` se dispara por evento
desde el endpoint `POST /recordings/{id}/end` mediante
`BackgroundTasks` de FastAPI, scope-ado a la línea recién contribuida;
los pasos pesados de agregación por línea se ejecutan periódicamente
desde cron contra el servicio one-shot `pipeline` declarado en el
docker-compose de despliegue. El detalle de la programación se
documenta en la sección 6.7 (Despliegue).

=== Módulo de gestión de desvíos

El módulo de gestión de desvíos permite a los usuarios contribuidores
reportar desviaciones temporales de una línea respecto a su trazado
habitual — bloqueos viales, marchas, obras — y al resto de los
usuarios consultar estos desvíos cuando están planificando un viaje.
La entidad central es `Detour`
(`packages/database/src/database/models/detour.py`), que persiste el
trazado real recorrido durante el desvío, el motivo y descripción
opcionales, una marca de tiempo de creación y la última confirmación
recibida (`last_confirmed_at`), y un contador de confirmaciones
acumuladas (`confirmed_count`). El estado del desvío vive en el campo
`status: DetourStatus` que toma valores `ACTIVE`, `EXPIRED` y
`RESOLVED`.

La Figura 17 muestra el flujo de reporte de un desvío. El usuario, al
cerrar una grabación, puede marcar la sesión como desvío e ingresar
opcionalmente el motivo y una descripción. El cliente envía esa
información en el cuerpo de `POST /recordings/{id}/end`; el servidor
detecta el flag, intenta refinar la geometría del recorrido grabado
mediante un map-match adicional contra Valhalla — para que la
geometría persistida coincida con el callejero — y crea el `Detour`.
La notificación a los suscriptores de la línea (CU-13) se delega a
una tarea de fondo `BackgroundTasks` para no bloquear la respuesta
HTTP.

#figure(
  // Diagrama de secuencia — Reportar desvío activo (CU-07)
  // Lifelines: Usuario, App, Server, Valhalla, BaseDatos, BackgroundTasks
  // Mensajes:
  //   1. Usuario marca grabación como desvío + ingresa motivo/descripción.
  //   2. App: POST /recordings/{id}/end {is_detour: true, detour_reason, detour_description, line_id}
  //   3. Server: cargar TripSession + sus puntos.
  //   4. Server → Valhalla: trace_attributes (snap del recorrido al callejero).
  //   5. Valhalla → Server: geometría snapped.
  //   6. Server: crear Detour(line_id, session_id, path, reason, description, status=ACTIVE).
  //   7. Server → BackgroundTasks: dispatch_detour_notifications(line_id, detour_id, exclude=device).
  //   8. Server → App: 200 OK (TripSession actualizada).
  //   9. BackgroundTasks → BaseDatos: insertar NotificationDispatch por suscriptor.
  rect(width: 100%, height: 75mm, stroke: 0.5pt + gray)[
    #align(center + horizon)[#text(size: 8pt, fill: gray, style: "italic")[
      Diagrama de secuencia — Reportar desvío activo (CU-07)\
      Lifelines: Usuario, App, Server, Valhalla, BaseDatos, BackgroundTasks
    ]]
  ],
  caption: [Diagrama de secuencia: Reporte de un desvío activo durante el cierre de una grabación],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

Cuando otro usuario consulta direcciones o las líneas cercanas, los
desvíos `ACTIVE` que afectan a las líneas relevantes se devuelven
junto con un `confidence_pct` calculado dinámicamente por
`server/services/detour_confidence.py`. El cálculo combina dos
factores: un decaimiento lineal por tiempo desde la última
confirmación (cero a los 14 días) y un refuerzo logarítmico por
número de confirmaciones (0.5 con un solo reportante, asintótico a
1.0 con muchas). Esta combinación traduce la "validación
colaborativa" prometida por el caso de uso CU-13 en una métrica
visible para el usuario: un desvío recién reportado por una sola
persona muestra ~50 % de confianza, mientras que el mismo desvío con
diez confirmaciones independientes muestra ~88 % aún el mismo día.
La Figura 18 detalla este cálculo.

#figure(
  // Diagrama de actividad — Cálculo de confidence_pct
  // Inicio → recibir Detour
  //   ↓
  // Computar days_since_confirmed = now() - last_confirmed_at
  //   ↓
  // time_factor = max(0, min(1, 1 - days/14))
  //   ↓
  // ¿time_factor == 0? ── Sí ──→ retornar 0
  //   │ No
  //   ↓
  // log_boost = log1p(max(0, confirmed_count - 1)) / log1p(20)
  //   ↓
  // corroboration_factor = min(1.0, 0.5 + 0.5 * log_boost)
  //   ↓
  // confidence = round(100 * time_factor * corroboration_factor)
  //   ↓
  // clamp a [0, 100]
  //   ↓
  // Fin (retornar confidence_pct)
  rect(width: 100%, height: 95mm, stroke: 0.5pt + gray)[
    #align(center + horizon)[#text(size: 8pt, fill: gray, style: "italic")[
      Diagrama de actividad — Cálculo de confidence_pct\
      Producto de decaimiento por tiempo × refuerzo logarítmico por corroboraciones
    ]]
  ],
  caption: [Diagrama de actividad: Fórmula híbrida de confianza para desvíos activos (RF-12 / RF-13)],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

El paso `cleanup` del pipeline expira automáticamente los desvíos
cuyo `last_confirmed_at` supera los 7 días sin nuevas confirmaciones,
cambiando su estado a `EXPIRED`. Adicionalmente, el endpoint
`POST /detours/cleanup` permite forzar esta limpieza manualmente y
está incluido en el cron de despliegue como salvaguarda. El servicio
`detour_analysis.py` complementa al desvío persistido analizando
dónde diverge y dónde reune con la ruta original
(`diverges_at`/`rejoins_at`), información que se devuelve al cliente
para presentar al usuario un mensaje legible del tipo "desde la calle
X hasta la calle Y" en lugar de un genérico "hay un desvío".

=== Módulo de gestión de tarifas

El módulo de gestión de tarifas captura el costo del pasaje reportado
por los usuarios después de un viaje y lo agrega para producir
estimaciones útiles a la hora de planificar otros viajes. La entidad
`FareReport`
(`packages/database/src/database/models/fare.py`) almacena cada
reporte individual con la línea, el dispositivo del contribuidor, el
monto en bolivianos, las coordenadas de abordaje y descenso, los
identificadores de las zonas tarifarias resueltas
automáticamente (`boarding_zone_id` y `alighting_zone_id`) y el origen
del reporte (`source`, que distingue entre `REGISTRATION` —
tipeo libre — y `CONFIRMATION` — selección de un monto previamente
reportado por otro usuario, RF-26). Las zonas tarifarias se modelan
como polígonos en `FareZone`, lo que permite resolver el municipio
de origen y destino mediante una consulta `ST_Contains` contra el
punto GPS sin pedirle al usuario que conozca las fronteras
administrativas.

La Figura 19 presenta el flujo del reporte de tarifa con
identificación automática de zonas (CU-08). Después de cerrar la
grabación, el cliente solicita al servidor una vista previa de las
zonas que serían identificadas para los puntos de abordaje y
descenso, mostrando al usuario un mensaje del tipo "Tarifa para
Cochabamba → Sacaba" antes de la confirmación. Este paso
intermedio convierte la inferencia automática — que de otro modo
sería invisible al usuario — en retroalimentación transparente que
permite verificar la zona identificada antes del envío. Si las zonas
resueltas son correctas el usuario confirma; si no, descarta o
re-graba. El POST final persiste el `FareReport` con las zonas ya
resueltas en el servidor, no en el cliente, lo que evita confiar en
datos manipulables.

#figure(
  // Diagrama de secuencia — Reporte de tarifa con identificación de zonas (CU-08)
  // Lifelines: Usuario, App, Server, BaseDatos
  // Mensajes:
  //   1. Usuario ingresa monto en el modal post-grabación.
  //   2. App: POST /fares/zones/resolve {boarding_lat/lon, alighting_lat/lon}
  //   3. Server → BaseDatos: ST_Contains(FareZone.boundary, ST_MakePoint(...)) por endpoint.
  //   4. BaseDatos → Server: zone_id_origen, zone_id_destino.
  //   5. Server → App: {boarding_zone: "Cochabamba", alighting_zone: "Sacaba"}
  //   6. App: render "Tarifa para Cochabamba → Sacaba" sobre el input.
  //   7. Usuario confirma.
  //   8. App: POST /fares/reports {line_id, device_id, amount_bob, lat/lon, source}
  //   9. Server → BaseDatos: insertar FareReport con zonas re-resueltas.
  //   10. Server → App: 201 Created (FareReportRead con boarding_zone, alighting_zone).
  rect(width: 100%, height: 80mm, stroke: 0.5pt + gray)[
    #align(center + horizon)[#text(size: 8pt, fill: gray, style: "italic")[
      Diagrama de secuencia — Registrar tarifa con zonas identificadas (CU-08)\
      Lifelines: Usuario, App, Server, BaseDatos
    ]]
  ],
  caption: [Diagrama de secuencia: Reporte de tarifa con identificación automática de municipios (CU-08 / RF-25 / RF-27)],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

La estimación de tarifa para una línea (`server/routes/fares.py`)
agrega los `FareReport` activos en dos vistas complementarias. La
vista por línea computa la moda de los montos reportados y los
expone como "chips" tap-to-confirm en el modal de grabación, lo que
permite a un usuario que tomó una micro 110 confirmar rápidamente la
tarifa más reportada en lugar de tipearla. La vista por par de zonas
(`_aggregate_zone_fares`) computa la mediana del monto por cada par
`(boarding_zone, alighting_zone)` con suficientes reportes y se
consume desde el módulo de identificación de trayectos para mostrar
la tarifa estimada de cada leg de bus en la pantalla de planificación
(RF-03 / RF-30).

=== Módulo de identificación de trayectos

El módulo de identificación de trayectos resuelve la pregunta
fundamental del usuario: dado un punto de origen y un destino,
¿cómo combino caminata y transporte público para llegar de la
manera más práctica? La implementación se apoya en un grafo de
tránsito en memoria construido a partir de las rutas confirmadas
(`packages/geodata/src/geodata/transit_graph.py`), sobre el cual se
ejecuta una búsqueda de costo mínimo que considera tiempo de
caminata, tiempo de espera, tiempo a bordo y un pequeño costo fijo
por transferencia para penalizar itinerarios con muchos transbordos.
La salida es una secuencia ordenada de "legs" — cada uno de modo
`walk` o `bus` — que el cliente renderiza en el mapa y como una
lista de pasos legibles.

#figure(
  // Diagrama de secuencia — Búsqueda de itinerario multi-modal (CU-01)
  // Lifelines: Usuario, App, Server, TransitGraph (en memoria), BaseDatos
  // Mensajes:
  //   1. Usuario ingresa origen y destino (textbox o mapa).
  //   2. App: POST /directions/ {origin, destination, include_pending_*}
  //   3. Server: encontrar paradas (nodos del grafo) cercanas al origen y destino.
  //   4. Server → TransitGraph: shortest_path(origen_node, destino_node, costing).
  //   5. TransitGraph → Server: secuencia de aristas (bus + walk + transfer).
  //   6. Server → BaseDatos: para cada bus_leg, fetch fare_estimate + frequency + active_detours.
  //   7. Server: enriquecer cada leg con fare_bob, frequency_min, detour_alert.
  //   8. Server → App: DirectionsResponse {legs[], total_distance_m, total_duration_s, total_fare_bob}.
  //   9. App: renderizar mapa con polylines por leg + lista de pasos.
  rect(width: 100%, height: 80mm, stroke: 0.5pt + gray)[
    #align(center + horizon)[#text(size: 8pt, fill: gray, style: "italic")[
      Diagrama de secuencia — Búsqueda de itinerario multi-modal (CU-01)\
      Lifelines: Usuario, App, Server, TransitGraph, BaseDatos
    ]]
  ],
  caption: [Diagrama de secuencia: Búsqueda de un itinerario combinando caminata y transporte público (CU-01)],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

El grafo de tránsito se reconstruye en cada ejecución del paso
`rebuild_graph` del pipeline: las aristas de bus provienen de los
`RouteEdge` de los `Route` no superseded, las aristas de transferencia
conectan paradas próximas entre líneas (umbral de caminata
configurable), y las aristas de caminata permiten al algoritmo de
búsqueda salir y entrar al sistema desde un punto arbitrario de
origen/destino. La marca `is_confirmed` en cada arista de bus
distingue rutas ya validadas por la comunidad (`RouteStatus.CONFIRMED`)
de rutas aún en validación (`PENDING`), información que se propaga
hasta el cliente para que pueda decidir mostrarlas u ocultarlas según
las preferencias del usuario. La Figura 21 ilustra este proceso de
construcción.

#figure(
  // Diagrama de actividad — Construcción del transit_graph (rebuild_graph)
  // Inicio → invalidate_graph() (descartar cache previo)
  //   ↓
  // SELECT Line + Route + RouteEdge WHERE Line.status IN {APPROVED, PENDING}
  //                                  AND Route.status != SUPERSEDED
  //   ↓
  // Por cada línea:
  //   ↓
  //   Por cada ruta no superseded de la línea:
  //   │   ├─ is_confirmed = (route.status == CONFIRMED)
  //   │   ├─ Por cada RouteEdge ordenado por sequence:
  //   │   │   ├─ Crear/recuperar nodos por endpoints de la arista
  //   │   │   └─ Agregar arista de bus (line_id, route_id, is_confirmed)
  //   │   └─ Si forward y reversed según `forward` flag, agregar arista direccionada
  //   ↓
  // Computar transferencias: para cada par de nodos cuya distancia ≤ walking_threshold,
  //   agregar arista "transfer" con costo derivado del tiempo de caminata.
  //   ↓
  // Cachear grafo en memoria (módulo-level)
  //   ↓
  // Fin (estadísticas: nodes, bus_edges, transfer_edges)
  rect(width: 100%, height: 105mm, stroke: 0.5pt + gray)[
    #align(center + horizon)[#text(size: 8pt, fill: gray, style: "italic")[
      Diagrama de actividad — Construcción del grafo de tránsito\
      Aristas de bus desde RouteEdge + transferencias por proximidad
    ]]
  ],
  caption: [Diagrama de actividad: Reconstrucción del grafo de tránsito a partir de rutas confirmadas y pendientes],
  supplement: "Figura",
  kind: image,
)

#source[Elaboración propia, 2026.]

Cada respuesta de direcciones se enriquece con metadatos extraídos
de los demás módulos: la tarifa estimada por leg de bus se obtiene
del módulo de gestión de tarifas (RF-03), la frecuencia esperada
(`frequency_min`) viene de los `LineSchedule` producidos por
`infer_schedules` (RF-04), y los desvíos activos se anexan al leg
correspondiente (`detour_alert`, RF-12). El total agregado
`total_fare_bob` (RF-30) se computa sumando los `fare_bob` de todos
los legs de bus, lo que da al usuario una proyección directa del
costo total del itinerario.

=== Parches a dependencias de terceros

Durante el desarrollo se identificó un defecto en el SDK
`expo-sqlite` v16.0.10 que afectaba a la API síncrona de la base de
datos local en el navegador (la utilizada indirectamente por Drizzle
ORM al invocar `.get()` / `.run()` / `.all()`). El defecto consiste en
que el worker de SQLite escribe la longitud del resultado serializado
asignando un `Uint32Array` sobre un `Uint8Array` mediante
`TypedArray.set(...)`, operación que realiza una conversión implícita
módulo 256 — es decir, solo conserva el byte menos significativo de
la longitud. En consecuencia, cualquier resultado de consulta que
superara los 255 bytes era truncado silenciosamente al volver al hilo
principal y producía un error de parseo de JSON en una posición
arbitraria, lejos del lugar real del problema.

La corrección consiste en una única línea: reemplazar la asignación
por `DataView.setUint32(offset, length, true)`, que escribe los
cuatro bytes de la longitud sin conversión. Para mantener esta
corrección frente a futuras instalaciones de dependencias —sin
necesidad de mantener un fork del SDK— se incorporó la herramienta
`patch-package` y se versionó el archivo
`patches/expo-sqlite+16.0.10.patch` (17 líneas) dentro del proyecto.
La aplicación del parche queda automatizada mediante el script
`postinstall` del `package.json` de la aplicación móvil. El parche
está anclado a la versión exacta del paquete: si en una versión
posterior el equipo de Expo corrige el defecto upstream, la aplicación
del parche fallará explícitamente avisando al desarrollador para que
revise y elimine el parche local.

=== Despliegue

==== Topología de servicios

El despliegue productivo se orquesta con `docker compose`
(`infra/deploy/docker-compose.yml`) y consta de los siguientes
servicios: `db` (PostgreSQL con extensión PostGIS), `migrate` (one-shot
que aplica migraciones Alembic antes de levantar el server), `server`
(API FastAPI), `valhalla` (motor de map-matching y costing),
`marimo` (notebooks de exploración), un stack de observabilidad
(`otel-collector`, `tempo`, `loki`, `prometheus`, `grafana`) y `caddy`
como proxy reverso con TLS automático.

El procesamiento del pipeline se aloja en un servicio adicional
`pipeline` declarado en el perfil `jobs` — no se inicia con
`docker compose up`, sino que se invoca puntualmente con
`docker compose --profile jobs run --rm pipeline run --steps ...`.
Esto permite reutilizar la imagen del `server` (que ya contiene los
paquetes `database`, `geodata` y `pipeline`) sin mantener un contenedor
de larga vida adicional.

==== Programación del pipeline (CU-11)

El caso de uso CU-11 ("Reconstruir rutas") se ejecuta bajo un esquema
híbrido evento+cron, sin orquestador externo dedicado:

+ *Trigger por evento* — cuando una sesión de grabación finaliza con
  línea asignada (`POST /recordings/{id}/end`), el handler encola una
  tarea en `BackgroundTasks` de FastAPI que invoca únicamente
  `clean_traces(line_id=...)` sobre la línea recién contribuida. El
  usuario obtiene retroalimentación rápida ("mi viaje ya quedó como
  Trip limpio") sin esperar al siguiente tick del cron. Cada ejecución
  se registra en `PipelineRun` con `trigger="event:recording_end"`.

+ *Trigger por cron* — los pasos pesados de agregación por línea
  (`reconstruct_routes`, `resolve_edge_votes`, `resolve_routes`,
  `resolve_line_votes`, `rebuild_graph`, `infer_schedules`,
  `cleanup`) se ejecutan periódicamente con `cron` del sistema host
  contra el servicio `pipeline`. El archivo
  `infra/deploy/cron/crontab.example` documenta la cadencia: agregación
  cada 6 horas, inferencia de horarios diaria a las 03:15 y limpieza
  diaria a las 04:00. Cada ejecución se registra con
  `trigger="cron"`.

La cadencia balancea la frescura de los datos (rutas y horarios
visibles para los usuarios) contra el costo computacional y la
estabilidad de las versiones de `Route` —ejecutar `reconstruct_routes`
con cada subida de viaje generaría versiones nuevas constantemente y
afectaría la confianza de los usuarios contribuidores que validan
secciones.

==== Telemetría y trazabilidad de ejecuciones

Cada ejecución del pipeline, sin importar su origen, queda registrada
en la tabla `pipeline_runs` con su trigger, estado terminal
(`COMPLETED`, `FAILED`) y timestamps; cada paso individual se registra
en `pipeline_step_results` con su propio estado, duración, diccionario
de estadísticas devuelto por la función del paso, y traza completa de
error si aplica. La consulta `pipeline history --limit N` desde el CLI
del paquete pipeline permite auditar las últimas ejecuciones sin
necesidad de acceder directamente a la base de datos.

==== Migración a un orquestador event-driven (Trabajo futuro)

La arquitectura actual está diseñada para ser compatible con una
migración futura a un orquestador como Prefect: el contrato del
runner (`run_pipeline`) recibe un `trigger` opaco y registra cada
ejecución con su lifecycle completo. Migrar a Prefect implicaría
reemplazar el cron del host por flujos Prefect que invoquen las
mismas funciones `execute()` de los pasos, manteniendo `PipelineRun`
y `PipelineStepResult` como fuente de verdad de auditoría. La interfaz
de monitoreo, los reintentos automáticos y los triggers basados en
eventos del bus serían beneficios añadidos sin reescribir la lógica
de los pasos.

== Fase de pruebas

Durante el desarrollo se aplicaron pruebas en cada nivel del modelo
piramidal — pruebas unitarias para la lógica de negocio aislada, pruebas
de integración y end-to-end para la interacción entre componentes, y
una checklist manual de humo previa a cada despliegue. Esta práctica
asegura que cada cambio en el código se valide automáticamente antes de
llegar al usuario final. La descripción detallada de la cobertura
alcanzada en cada nivel, junto con los casos de prueba ejecutados y sus
resultados, se presenta en el capítulo III (Pruebas de calidad). El
estudio de campo con usuarios reales, complementario a las pruebas
técnicas, se documenta en el Plan de Pruebas adjunto al presente
proyecto de grado.

// =====================================================================
// CAPÍTULO III — PRUEBAS DE CALIDAD
// =====================================================================

#pagebreak()
#align(center)[
  #v(2cm)
  #text(size: 18pt, style: "italic")[CAPÍTULO III]

  #v(0.5em)
  #text(size: 16pt, weight: "bold")[PRUEBAS DE CALIDAD]
]
#pagebreak()

= Pruebas de calidad

== Estrategia de pruebas

La validación del sistema combina cuatro niveles de pruebas
complementarios, aplicados desde la prueba aislada de funciones
individuales hasta la validación con usuarios reales en condiciones de
campo. La distribución sigue el modelo de pirámide de pruebas, donde la
mayor parte del esfuerzo de validación se concentra en los niveles
inferiores —rápidos, deterministas y ejecutables ante cada cambio en el
código fuente—, reservando los niveles superiores —más costosos en
tiempo y recursos— para la verificación extremo-a-extremo y la
aceptación con usuarios.

Los cuatro niveles aplicados se resumen en la siguiente tabla.

#figure(
  table(
    columns: (auto, 1.5fr, 1fr, 1.2fr, 1fr),
    stroke: 0.5pt,
    align: left + horizon,
    table.header(
      [*Nivel*], [*Alcance*], [*Herramienta*],
      [*Disparador*], [*Criterio de aprobación*],
    ),
    [Unitarias],
      [Funciones puras y lógica de negocio aislada (validaciones,
       transformaciones geoespaciales, helpers).],
      [`pytest`],
      [Cada commit (CI) y antes de cada despliegue.],
      [100 % de pruebas en estado Pass.],
    [Integración / E2E],
      [Endpoints HTTP contra una base de datos PostgreSQL real de
       prueba, y flujos de UI completos en el cliente web.],
      [`pytest` con `TestClient`; Playwright],
      [Cada commit (CI) y antes de cada despliegue.],
      [100 % de pruebas en estado Pass.],
    [Humo manual],
      [Verificación end-to-end de funcionalidades críticas en
       dispositivos físicos antes de cada despliegue.],
      [Checklist firmada (Plan de Pruebas, Anexo G).],
      [Antes de cada despliegue al entorno de producción.],
      [Cero ítems en estado Fail.],
    [Aceptación (UAT)],
      [Estudio de campo de tres días con 20 participantes usuarios
       reales del transporte público de Cochabamba.],
      [Plan de Pruebas (documento adjunto).],
      [Una sola ejecución, previo despliegue del build de prueba.],
      [Cumplimiento de los criterios definidos en el Plan de Pruebas
       §7.],
  ),
  caption: [Niveles de pruebas aplicados al sistema],
)

A diferencia de la práctica de duplicar la documentación de cada
prueba en el presente capítulo, la implementación viva de las pruebas
reside en el código fuente del proyecto y se referencia desde aquí
mediante las rutas de archivo correspondientes. Esta decisión asegura
que la documentación no se desactualice respecto a la implementación.

== Pruebas unitarias

Las pruebas unitarias verifican el comportamiento de funciones puras y
componentes lógicos aislados, sin dependencias de red, base de datos ni
servicios externos. Se ejecutan en la suite del desarrollador y en
integración continua ante cada modificación del código fuente,
proporcionando retroalimentación inmediata sobre regresiones. La
herramienta principal es `pytest` para los componentes en Python.

#figure(
  table(
    columns: (1.2fr, 1.5fr, auto, 2fr),
    stroke: 0.5pt,
    align: left + horizon,
    table.header(
      [*Módulo*], [*Archivos de prueba*], [*Pruebas*], [*Enfoque*],
    ),
    [Servidor — recordings],
      [`server/tests/test_recordings.py`], [#placeholder("N")],
      [Validación de transiciones de estado de sesión, persistencia
       de puntos GPS y lecturas de sensores, generación del path
       computado.],
    [Servidor — voting],
      [`server/tests/test_voting.py`], [#placeholder("N")],
      [Cómputo de secciones votables, agregación de votos por arista,
       criterios de validez (mínimo de viajes por dispositivo).],
    [Servidor — detours / lines / fares],
      [`server/tests/test_detours.py`, `test_lines.py`], [#placeholder("N")],
      [Creación, listado y expiración de desvíos; gestión de líneas;
       reportes de tarifas.],
    [Servidor — push notifications],
      [`server/tests/test_push.py`], [8],
      [Reglas de coalescencia (3 individuales seguidas de una
       coalescida en ventana de 24 h), exclusión del reportador,
       resiliencia ante fallas de la API de Expo.],
    [Servidor — devices],
      [`server/tests/test_devices.py`], [8],
      [Registro de dispositivos, alta/baja de suscripciones, manejo
       de tokens nulos.],
    [Geodata — algoritmos],
      [`packages/geodata/tests/`], [#placeholder("N")],
      [Simplificación de trazos, remuestreo a intervalos uniformes,
       clustering DBSCAN, simulación de trayectos.],
  ),
  caption: [Cobertura de pruebas unitarias por módulo],
)

== Pruebas de integración y end-to-end

Las pruebas de integración verifican la cooperación entre componentes
del sistema —API, base de datos, paquetes internos— bajo condiciones
cercanas a producción. Las pruebas end-to-end (E2E) extienden este
alcance hasta el cliente, ejercitando la interfaz de usuario en un
navegador real.

Se utilizan dos herramientas complementarias: `pytest` con
`TestClient` para los endpoints HTTP del servidor (con una base de
datos PostgreSQL real de prueba que se levanta y descarta por
ejecución), y Playwright para los escenarios de interfaz en el
cliente web, principalmente los flujos de gestión de viajes
recurrentes y de votación por secciones.

#figure(
  table(
    columns: (1.2fr, 1.5fr, auto, 2fr),
    stroke: 0.5pt,
    align: left + horizon,
    table.header(
      [*Categoría*], [*Archivos de prueba*], [*Pruebas*], [*Enfoque*],
    ),
    [Endpoints HTTP — recordings],
      [`server/tests/test_recordings.py`], [#placeholder("N")],
      [Ciclo completo de una sesión de grabación: creación, ingestión
       de puntos en lotes, finalización con/sin desvío.],
    [Endpoints HTTP — devices y subscriptions],
      [`server/tests/test_devices.py`], [8],
      [Alta de dispositivos, reemplazo de suscripciones, eliminación.],
    [Despacho de notificaciones],
      [`server/tests/test_push.py`], [8],
      [Disparo del despacho desde el endpoint de fin de grabación;
       integración entre `recordings.py`, `services/push.py` y la
       cola de tareas en segundo plano de FastAPI.],
    [E2E web — viajes recurrentes],
      [`app/e2e/saved-trips.spec.ts`], [#placeholder("N")],
      [Guardar y eliminar viajes recurrentes, verificando que la app
       sincroniza correctamente las suscripciones con el servidor.],
    [E2E web — votación],
      [`app/e2e/voting.spec.ts`], [#placeholder("N")],
      [Flujo de votación por secciones desde la pestaña Contribuir
       hasta el envío de votos.],
  ),
  caption: [Cobertura de pruebas de integración y end-to-end],
)

== Pruebas manuales de humo

Las pruebas manuales de humo se ejecutan por la investigadora antes de
cada despliegue al entorno de producción y antes del inicio del estudio
de campo. Validan funcionalidades cuya naturaleza —dependencia de
hardware específico, asincronía multi-usuario, integraciones con
servicios de terceros— hace inviable o desproporcionadamente costoso
automatizarlas. El caso paradigmático es la entrega de notificaciones
push, que requiere dos dispositivos físicos pareados y la
infraestructura de Apple/Google.

La checklist operativa completa, con los doce ítems verificados y el
espacio para la firma de la investigadora, se incluye en el Anexo G
del Plan de Pruebas adjunto. La siguiente tabla documenta las tres
especificaciones formales correspondientes a la funcionalidad F-04
(notificaciones push), que constituyen el núcleo de complejidad de
este nivel de pruebas; los demás ítems de la checklist son
verificaciones binarias cuya descripción se reserva al Plan.

#figure(
  table(
    columns: (auto, 1.5fr, 1.8fr, 1.5fr, auto),
    stroke: 0.5pt,
    align: left + horizon,
    table.header(
      [*ID*], [*Caso de prueba*], [*Pasos clave*],
      [*Resultado esperado*], [*Estado*],
    ),
    [TC-11],
      [Notificación push individual a usuario con viaje recurrente.
       Pre-condiciones: dos dispositivos físicos; usuario A guardó la
       línea L como recurrente y otorgó permiso de notificaciones.],
      [1. Usuario B reporta un desvío sobre la línea L.
       2. Esperar hasta 30 s observando el dispositivo de A.
       3. A toca la notificación recibida.],
      [A recibe una notificación con título "Desvío en \{línea\}";
       al tocarla, la app se abre en la pestaña Explorar con la línea
       L y el desvío visibles. Se registra una fila en
       `notification_dispatches` con `kind = detour_individual`.],
      [#placeholder("___")],
    [TC-12],
      [Coalescencia tras 3 notificaciones individuales en 24 h.
       Pre-condición: A ya recibió 3 notificaciones individuales
       sobre la línea L en las últimas 24 h.],
      [1. Usuario B reporta un cuarto desvío sobre la línea L.
       2. Esperar la notificación.
       3. Reportar un quinto desvío.],
      [El cuarto desvío genera una notificación con título "Más
       desvíos en \{línea\}". El quinto desvío no produce
       notificación adicional. Se registra una fila con
       `kind = detour_coalesced`.],
      [#placeholder("___")],
    [TC-13],
      [Supresión de notificación al reportador.
       Pre-condición: el usuario que reporta el desvío también está
       suscrito a la línea como recurrente.],
      [1. Usuario A (suscrito y reportador) reporta un desvío sobre
       su propia línea recurrente.],
      [El propio dispositivo A no recibe notificación. Otros
       suscriptores sí la reciben con normalidad.],
      [#placeholder("___")],
    [TC-14],
      [Notificación local de inicio de ruta. Pre-condición:
       dispositivo físico con la app instalada; permiso de
       notificaciones otorgado; un viaje "solo por hoy" guardado con
       hora de salida HH:mm y al menos una línea de bus.],
      [1. Cerrar la app por completo.
       2. Esperar hasta 10 minutos antes de la hora indicada.],
      [El dispositivo dispara una notificación con título "Salida a
       \{destino\} a las HH:mm" y cuerpo que enumera la(s) línea(s)
       que toca tomar. Se registra el evento en el sistema operativo.],
      [#placeholder("___")],
    [TC-15],
      [Notificación incluye aviso de desvío. Pre-condición: existe un
       desvío activo en alguna línea del viaje guardado al momento de
       (re)programar la notificación (sucede al guardar el viaje o al
       reabrir la app).],
      [1. Reportar un desvío activo sobre la línea L del viaje.
       2. Reabrir la app para forzar el `rescheduleAllSavedTrips`.
       3. Esperar a que se dispare la notificación.],
      [El cuerpo incluye el sufijo "⚠ Desvío activo: Línea L
       (motivo)".],
      [#placeholder("___")],
    [TC-16],
      [Notificación recurrente. Pre-condición: viaje guardado de
       tipo `commute` con hora de salida.],
      [1. Verificar la notificación 3 días consecutivos a la misma
       hora.],
      [La notificación se dispara cada día (calendar trigger nativo
       con `repeats: true`) sin requerir abrir la app entre eventos.],
      [#placeholder("___")],
    [TC-17],
      [Cancelación al eliminar viaje. Pre-condición: existe un
       viaje guardado con hora de salida y notificación programada.],
      [1. Eliminar el viaje desde la pestaña Favoritos.
       2. Esperar a la hora a la que debería dispararse la
       notificación.],
      [Ninguna notificación se dispara para ese viaje.],
      [#placeholder("___")],
  ),
  caption: [Casos de prueba manuales de humo
   correspondientes a F-04 (Notificaciones push) y F-05
   (Notificaciones locales programadas de inicio de ruta)],
)

== Pruebas de aceptación con usuarios

Las pruebas de aceptación se realizan en el marco de un estudio de
campo de tres días consecutivos con veinte participantes usuarios
habituales del transporte público del área metropolitana de
Cochabamba. Cada participante valida una funcionalidad por día,
siguiendo un diseño longitudinal que respeta las dependencias
funcionales entre escenarios: la línea mapeada el Día 1 alimenta el
desvío reportado el Día 2, que a su vez alimenta el reporte de fin de
desvío del Día 3.

La justificación metodológica del diseño, los criterios de inclusión
de la muestra, la logística del estudio, los instrumentos de
recolección de datos (instrumentación PostHog y cuestionarios
post-tarea con escala Likert) y los criterios de aceptación detallados
se documentan íntegramente en el Plan de Pruebas adjunto. Las
especificaciones de los casos de prueba ejecutados en el estudio se
presentan en las siguientes subsecciones, organizadas por funcionalidad
para reflejar la asignación de tareas por día.

=== F-01 — Mapeo de línea de transporte público

#figure(
  table(
    columns: (auto, 1.5fr, 1.8fr, 1.5fr, auto),
    stroke: 0.5pt,
    align: left + horizon,
    table.header(
      [*ID*], [*Caso de prueba*], [*Pasos clave*],
      [*Resultado esperado*], [*Estado*],
    ),
    [TC-01],
      [Inicio de grabación con permiso de ubicación otorgado.],
      [1. Abrir pestaña Grabar.
       2. Otorgar permiso de ubicación.
       3. Deslizar para iniciar.],
      [La aplicación registra puntos GPS cada 2 s o cada 5 m de
       desplazamiento. La sesión queda en estado `in_progress`.],
      [#placeholder("___")],
    [TC-02],
      [Grabación denegando permiso de ubicación.],
      [1. Abrir pestaña Grabar.
       2. Denegar el permiso de ubicación.
       3. Intentar deslizar para iniciar.],
      [La aplicación muestra un mensaje informativo y no inicia la
       grabación.],
      [#placeholder("___")],
    [TC-03],
      [Detención y guardado con asignación a línea existente.],
      [1. Tras una grabación válida, deslizar para detener.
       2. Seleccionar una línea existente.
       3. Confirmar.],
      [La sesión cambia a `completed`; los puntos se sincronizan en
       lotes; la base de datos contiene la sesión con su `line_id`
       asignado.],
      [#placeholder("___")],
    [TC-04],
      [Detención y guardado creando una nueva línea.],
      [1. Tras una grabación válida, deslizar para detener.
       2. Escribir un nombre de línea nueva.
       3. Confirmar.],
      [Se crea una fila en `lines` con estado `draft`; la sesión
       queda asociada a esa línea.],
      [#placeholder("___")],
    [TC-05],
      [Cancelación de grabación en curso.],
      [1. Iniciar grabación.
       2. Tocar "Cancelar".],
      [La sesión cambia a `cancelled` y los puntos locales se
       descartan.],
      [#placeholder("___")],
  ),
  caption: [Casos de prueba UAT para F-01 (Mapeo de línea)],
)

=== F-02 — Reporte de inicio de desvío

#figure(
  table(
    columns: (auto, 1.5fr, 1.8fr, 1.5fr, auto),
    stroke: 0.5pt,
    align: left + horizon,
    table.header(
      [*ID*], [*Caso de prueba*], [*Pasos clave*],
      [*Resultado esperado*], [*Estado*],
    ),
    [TC-06],
      [Reporte de desvío con motivo y descripción.],
      [1. Tras grabar la ruta del desvío, abrir el modal de guardado.
       2. Activar "Es un desvío".
       3. Seleccionar motivo "Construcción" y describirlo.
       4. Publicar.],
      [Se crea una fila en `detours` con `status = active`, `reason`
       y `description` correctamente almacenados.],
      [#placeholder("___")],
    [TC-07],
      [Validación: descripción excede el límite de 500 caracteres.],
      [1. En el modal de desvío, escribir 501 caracteres en la
       descripción.
       2. Intentar publicar.],
      [La aplicación bloquea el envío y muestra el contador en rojo.],
      [#placeholder("___")],
    [TC-08],
      [Reporte sin línea seleccionada.],
      [1. Tras grabar, intentar publicar como desvío sin elegir línea.],
      [La aplicación bloquea el envío e indica que se requiere una
       línea.],
      [#placeholder("___")],
  ),
  caption: [Casos de prueba UAT para F-02 (Reporte de inicio de desvío)],
)

=== F-03 — Reporte de fin de desvío

#figure(
  table(
    columns: (auto, 1.5fr, 1.8fr, 1.5fr, auto),
    stroke: 0.5pt,
    align: left + horizon,
    table.header(
      [*ID*], [*Caso de prueba*], [*Pasos clave*],
      [*Resultado esperado*], [*Estado*],
    ),
    [TC-09],
      [Confirmación de que el desvío sigue activo.],
      [1. Recorrer una línea con desvío activo.
       2. En el modal post-grabación, responder "Sí, sigue" al prompt
       de confirmación.],
      [La columna `last_confirmed_at` del desvío se actualiza y
       `confirmed_count` se incrementa en 1.],
      [#placeholder("___")],
    [TC-10],
      [Expiración automática tras 7 días sin confirmación.],
      [1. Pre-condición: `last_confirmed_at` del desvío fijado a hace
       más de 7 días.
       2. Ejecutar el endpoint de limpieza.],
      [El desvío cambia a estado `expired` y deja de aparecer en la
       lista de desvíos activos.],
      [#placeholder("___")],
  ),
  caption: [Casos de prueba UAT para F-03 (Reporte de fin de desvío)],
)


== Reporte de resultados

La presente sección consolida los resultados obtenidos en la ejecución
de los cuatro niveles de pruebas descritos previamente, junto con la
evidencia post-ejecución de cobertura sobre los casos de uso y los
requisitos funcionales del sistema. Los datos crudos —logs de
integración continua, reporte de cobertura por paquete, respuestas
individuales del cuestionario post-tarea y transcripciones de las
preguntas abiertas— se incluyen en los apéndices correspondientes; el
presente capítulo se limita al análisis interpretativo.

=== Resultados de pruebas automatizadas

#figure(
  table(
    columns: (1.5fr, auto, auto, auto, auto, auto),
    stroke: 0.5pt,
    align: left + horizon,
    table.header(
      [*Suite*], [*Total*], [*Pass*], [*Fail*],
      [*Cobertura*], [*Duración*],
    ),
    [Servidor — pytest unitarias e integración],
      [#placeholder("N")], [#placeholder("N")], [#placeholder("N")],
      [#placeholder("N %")], [#placeholder("Ns")],
    [Geodata — pytest],
      [#placeholder("N")], [#placeholder("N")], [#placeholder("N")],
      [#placeholder("N %")], [#placeholder("Ns")],
    [Cliente web — Playwright E2E],
      [#placeholder("N")], [#placeholder("N")], [#placeholder("N")],
      [—], [#placeholder("Ns")],
  ),
  caption: [Resultados de la última ejecución de la suite
   automatizada en integración continua],
)

#placeholder("Comentar brevemente: tasa de éxito agregada, cobertura
consolidada, módulos con cobertura por debajo del umbral, regresiones
detectadas durante el desarrollo y resueltas antes del despliegue.")

=== Resultados del estudio de campo

El estudio de campo se ejecutó del #placeholder("___") al #placeholder("___")
con #placeholder("N") participantes finales (de los 20 reclutados
originalmente, descontando #placeholder("N") inasistencias y
#placeholder("N") exclusiones por incompatibilidad del dispositivo).
Los resultados se presentan en tres dimensiones complementarias:
cumplimiento de criterios objetivos por día, percepción del usuario
medida con preguntas Likert, y hallazgos cualitativos emergentes de
las preguntas abiertas.

==== Cumplimiento de criterios diarios

#figure(
  table(
    columns: (auto, 2fr, 1fr, auto),
    stroke: 0.5pt,
    align: left + horizon,
    table.header(
      [*Día*], [*Métrica objetiva*], [*Resultado obtenido*],
      [*Cumple criterio*],
    ),
    [Día 1],
      [≥ 80 % de participantes completan el mapeo sin asistencia
       externa, con cobertura de ruta ≥ 90 %.],
      [#placeholder("__ % completaron — cobertura promedio __ %")],
      [#placeholder("Sí / No")],
    [Día 2],
      [≥ 80 % de participantes reportan correctamente inicio y fin
       del desvío.],
      [#placeholder("__ % reportaron correctamente")],
      [#placeholder("Sí / No")],
    [Día 3],
      [≥ 90 % de participantes confirman correctamente el fin del
       desvío.],
      [#placeholder("__ % confirmaron correctamente")],
      [#placeholder("Sí / No")],
  ),
  caption: [Cumplimiento de criterios objetivos por día],
)

==== Resultados del cuestionario Likert

La tabla resume el promedio obtenido por cada afirmación Likert (escala
1–5) a lo largo de los tres días del estudio. El criterio de aceptación
definido en el Plan de Pruebas §7.2 establece un umbral mínimo de 4.0/5
en la afirmación "La aplicación fue fácil de usar" (L1); se reporta
también el resultado del resto de afirmaciones por completitud
analítica.

#figure(
  table(
    columns: (auto, 2fr, auto, auto, auto, auto, auto),
    stroke: 0.5pt,
    align: left + horizon,
    table.header(
      [*Nº*], [*Afirmación*], [*Día 1*], [*Día 2*], [*Día 3*],
      [*Promedio*], [*Cumple ≥ 4.0*],
    ),
    [L1], [La aplicación fue fácil de usar.],
      [#placeholder("__")], [#placeholder("__")], [#placeholder("__")],
      [#placeholder("__")], [#placeholder("Sí / No")],
    [L2], [Las instrucciones fueron claras.],
      [#placeholder("__")], [#placeholder("__")], [#placeholder("__")],
      [#placeholder("__")], [#placeholder("Sí / No")],
    [L3], [Pude completar la tarea sin ayuda externa.],
      [#placeholder("__")], [#placeholder("__")], [#placeholder("__")],
      [#placeholder("__")], [#placeholder("Sí / No")],
    [L4], [El tiempo de respuesta fue adecuado.],
      [#placeholder("__")], [#placeholder("__")], [#placeholder("__")],
      [#placeholder("__")], [#placeholder("Sí / No")],
    [L5], [Confío en que los datos se registraron correctamente.],
      [#placeholder("__")], [#placeholder("__")], [#placeholder("__")],
      [#placeholder("__")], [#placeholder("Sí / No")],
    [L6], [Volvería a usar esta aplicación.],
      [#placeholder("__")], [#placeholder("__")], [#placeholder("__")],
      [#placeholder("__")], [#placeholder("Sí / No")],
    [L7], [Recomendaría esta aplicación a otros usuarios.],
      [#placeholder("__")], [#placeholder("__")], [#placeholder("__")],
      [#placeholder("__")], [#placeholder("Sí / No")],
  ),
  caption: [Promedios del cuestionario Likert por
   afirmación y día (escala 1–5)],
)

#placeholder("Comentar brevemente: dimensiones de mayor y menor
puntuación, diferencias notables entre días, y comparación contra el
criterio de aceptación. Las respuestas individuales por participante
se incluyen en el Apéndice X.")

==== Hallazgos cualitativos

Las preguntas abiertas del cuestionario post-tarea revelaron temas
recurrentes que complementan los datos cuantitativos. A continuación
se sintetizan los hallazgos más relevantes; las transcripciones
completas se incluyen en el Apéndice #placeholder("X").

- *#placeholder("Tema 1 — p. ej. fricciones en el flujo de inicio
  de grabación")*: #placeholder("síntesis del tema en 1–2 frases.")
  Cita ilustrativa: "#placeholder("quote textual de un participante")"
  (Participante #placeholder("PNN"), Día #placeholder("X")).

- *#placeholder("Tema 2 — p. ej. valoración positiva del flujo de
  reporte de desvío")*: #placeholder("síntesis del tema.")
  Cita: "#placeholder("quote")" (Participante #placeholder("PNN")).

- *#placeholder("Tema 3 — p. ej. solicitudes recurrentes de funciones
  no implementadas")*: #placeholder("síntesis.")
  Cita: "#placeholder("quote")" (Participante #placeholder("PNN")).

- *#placeholder("Tema 4 — opcional")*: #placeholder("síntesis.")

=== Defectos identificados

#figure(
  table(
    columns: (auto, 1.8fr, auto, 1fr, auto),
    stroke: 0.5pt,
    align: left + horizon,
    table.header(
      [*ID*], [*Descripción del defecto*], [*Severidad*],
      [*Caso de prueba*], [*Estado*],
    ),
    [D-#placeholder("01")], [#placeholder("Descripción del defecto")],
      [#placeholder("Crítica / Alta / Media / Baja")],
      [#placeholder("TC-NN")], [#placeholder("Resuelto / Pendiente")],
    [#placeholder("___")], [#placeholder("___")],
      [#placeholder("___")], [#placeholder("___")],
      [#placeholder("___")],
  ),
  caption: [Defectos identificados durante la fase de
   pruebas],
)

#placeholder("Comentar brevemente: distribución por severidad,
defectos resueltos antes del cierre del estudio, defectos diferidos
a versiones posteriores y su justificación.")

=== Matriz de trazabilidad post-ejecución

La siguiente matriz constituye la evidencia consolidada de que cada
caso de uso y cada requisito funcional del sistema fue verificado
durante la fase de pruebas. Se basa en la matriz vacía del Anexo A del
Plan de Pruebas adjunto, completada con el estado real de cada caso de
prueba tras su ejecución y los identificadores de defectos detectados,
si los hubiera.

#figure(
  table(
    columns: (auto, auto, auto, 1.5fr, auto, auto),
    stroke: 0.5pt,
    align: left + horizon,
    table.header(
      [*Caso de uso*], [*Requisito funcional*], [*Funcionalidad*],
      [*Casos de prueba*], [*Estado*], [*Defectos*],
    ),
    [UC-#placeholder("__")], [RF-#placeholder("__")], [F-01],
      [TC-01, TC-02],
      [#placeholder("Pass / Fail / Parcial")], [#placeholder("Ninguno")],
    [UC-#placeholder("__")], [RF-#placeholder("__")], [F-01],
      [TC-03],
      [#placeholder("Pass / Fail / Parcial")], [#placeholder("Ninguno")],
    [UC-#placeholder("__")], [RF-#placeholder("__")], [F-01],
      [TC-04, TC-05],
      [#placeholder("Pass / Fail / Parcial")], [#placeholder("Ninguno")],
    [UC-#placeholder("__")], [RF-#placeholder("__")], [F-02],
      [TC-06, TC-07],
      [#placeholder("Pass / Fail / Parcial")], [#placeholder("Ninguno")],
    [UC-#placeholder("__")], [RF-#placeholder("__")], [F-02],
      [TC-08],
      [#placeholder("Pass / Fail / Parcial")], [#placeholder("Ninguno")],
    [UC-#placeholder("__")], [RF-#placeholder("__")], [F-03],
      [TC-09, TC-10],
      [#placeholder("Pass / Fail / Parcial")], [#placeholder("Ninguno")],
    [UC-13], [RF-#placeholder("__")], [F-04],
      [TC-11, TC-12, TC-13],
      [#placeholder("Pass / Fail / Parcial")], [#placeholder("Ninguno")],
  ),
  caption: [Matriz de trazabilidad post-ejecución entre
   casos de uso, requisitos funcionales, funcionalidades y casos de
   prueba],
)

#placeholder("Comentar brevemente: número total de UC y RF cubiertos,
porcentaje de cobertura alcanzado, y casos de prueba que requirieron
re-ejecución tras corrección de defectos.")

=== Conclusión de la validación

#placeholder("Veredicto de aceptación según el criterio global del
Plan de Pruebas §7.3: cumplimiento de al menos dos de los tres
criterios diarios y ausencia de defectos críticos. Articular este
veredicto explícitamente — \"el sistema se considera aceptado\" o
\"el sistema requiere correcciones antes de su aceptación\" — y
sustentarlo con los resultados consolidados de las subsecciones
anteriores.")

// =====================================================================
// CAPÍTULO IV — ESTIMACIÓN DE COSTOS
// =====================================================================

#pagebreak()
#align(center)[
  #v(2cm)
  #text(size: 18pt, style: "italic")[CAPÍTULO IV]

  #v(0.5em)
  #text(size: 16pt, weight: "bold")[ESTIMACIÓN DE COSTOS]
]
#pagebreak()

= Estimación de costos

== Costos de despliegue

// (Sección por desarrollar)

== Costos de mantenimiento

// (Sección por desarrollar)

// =====================================================================
// CAPÍTULO V — RESULTADOS
// =====================================================================

#pagebreak()
#align(center)[
  #v(2cm)
  #text(size: 18pt, style: "italic")[CAPÍTULO V]

  #v(0.5em)
  #text(size: 16pt, weight: "bold")[RESULTADOS]
]
#pagebreak()

= Resultados

== Resultados

// (Sección por desarrollar)

== Conclusiones

// (Sección por desarrollar)

== Recomendaciones

// (Sección por desarrollar)

// =====================================================================
// REFERENCIAS BIBLIOGRÁFICAS
// =====================================================================

#pagebreak()

= Referencias bibliográficas

#set par(first-line-indent: 0em, hanging-indent: 1.25em, justify: true)
#set text(size: 10.5pt)

Aberdour, M. (2007). Achieving Quality in Open-Source Software. _IEEE
Software_. https://doi.org/10.1109/MS.2007.2

Bast, H., Delling, D., Goldberg, A., Müller-Hannemann, M., Pajor, T.,
Sanders, P., Wagner, D., & Werneck, R. F. (2016). Route Planning in
Transportation Networks. En L. Kliemann & P. Sanders (Eds.), _Algorithm
Engineering: Selected Results and Surveys_ (pp. 19--80). Springer
International Publishing. https://doi.org/10.1007/978-3-319-49487-6_2

Cabrera, J. (2017). _La planificación del territorio, la vialidad, el
transporte y la movilidad en Cochabamba_ (pp. 4--13).

Cabrera, J. E. (Ed.). (2023). _Lo urbano y la urbanización en Bolivia:
Problemáticas y desafíos_. Instituto Boliviano de Urbanismo.
https://www.undp.org/sites/g/files/zskgke326/files/2023-06/desarrollo_urbano_celeste_plomizo_baja.pdf

Cabrera, J. E., & Moyano, B. D. M. (2022). Paratránsito y expansión
urbana: El transporte informal como dispositivo de urbanización. _urbe.
Revista Brasileira de Gestão Urbana_, _14_, e20210408.
https://doi.org/10.1590/2175-3369.014.e20210408

Cabrera, J., Orellana, P., & Perez, A. (2018). _Entre el transporte
informal y la ciudad inteligente: La aplicación móvil Llajta Rutas
Metropolitana_ (pp. 167--192).

Fitzgerald. (2006). The Transformation of Open Source Software. _MIS
Quarterly_. https://doi.org/10.2307/25148740

Ghezzi, A., Gabelloni, D., Martini, A., & Natalicchio, A. (2017).
Crowdsourcing: A Review and Suggestions for Future Research.
_International Journal of Management Reviews_.
https://doi.org/10.1111/ijmr.12135

Google Play. (2023, diciembre 14). _Trufi---Apps en Google Play_.
https://play.google.com/store/apps/details?id=app.trufi.navigator

Hirth, M., Hoßfeld, T., & Tran-Gia, P. (2013). Analyzing costs and
accuracy of validation mechanisms for crowdsourcing platforms.
_Mathematical and Computer Modelling, Information System Security and
Performance Modeling and Simulation for Future Mobile Networks_,
_57_(11), 2918--2932. https://doi.org/10.1016/j.mcm.2012.01.006

Holguin, L., Ochoa-Zezzatti, A., Larios, V. M., Cossio, E., Maciel, R.,
& Rivera, G. (2019). Small steps towards a smart city: Mobile
application that provides options for the use of public transport in
Juarez City. _2019 IEEE International Smart Cities Conference (ISC2)_,
100--105. https://doi.org/10.1109/ISC246665.2019.9071728

Hossain, M., & Kauranen, I. (2015). Crowdsourcing: A comprehensive
literature review. _Strategic Outsourcing: An International Journal_.
https://doi.org/10.1108/SO-12-2014-0029

Hou, X. (2021). _Map matching algorithms for intelligent transportation
system_ [Nanyang Technological University].
https://doi.org/10.32657/10356/148923

Hou, X., Luo, L., Cai, W., & Hanai, M. (2018). Fast Online Map Matching
for Recovering Travelling Routes from Low-Sampling GPS Data. _2018 IEEE
SmartWorld, Ubiquitous Intelligence & Computing, Advanced & Trusted
Computing, Scalable Computing & Communications, Cloud & Big Data
Computing, Internet of People and Smart City Innovation
(SmartWorld/SCALCOM/UIC/ATC/CBDCom/IOP/SCI)_, 917--924.
https://doi.org/10.1109/SmartWorld.2018.00165

Howe, J. (2006). _The Rise of Crowdsourcing_. (14).

Hung, N. Q. V., Thang, D. C., Tam, N. T., Weidlich, M., & Et., A.
(2017). Answer validation for generic crowdsourcing tasks with minimal
efforts. _The VLDB Journal_. https://doi.org/10.1007/s00778-017-0484-3

Instituto Nacional de Estadística INE. (2015). _Censo de Población y
Vivienda 2012 Cochabamba_. Estado Plurinacional de Bolivia.

Kittur, A., Smus, B., Khamkar, S., & Kraut, R. E. (2011). _CrowdForge:
Crowdsourcing Complex Work_.

Kleemann, F., Voß, G. G., & Rieder, K. (2008). Un(der)paid Innovators:
The Commercial Utilization of Consumer Work through Crowdsourcing.
_Innovation Studies, Science, Technology & Innovation Studies_, _4_(1).

Kong, X., Liu, X., Jedari, B., Li, M., & Et., A. (2019). Mobile
Crowdsourcing in Smart Cities: Technologies, Applications, and Future
Challenges. _IEEE Internet of Things Journal_.
https://doi.org/10.1109/JIOT.2019.2921879

Kubička, M., Cela, A., Moulin, P., Mounier, H., & Niculescu, S. I.
(2015). Dataset for testing and training of map-matching algorithms.
_2015 IEEE Intelligent Vehicles Symposium (IV)_, 1088--1093.
https://doi.org/10.1109/IVS.2015.7225829

Liu, Y., Ge, Q., Luo, W., Huang, Q., Zou, L., Wang, H., Li, X., & Liu,
C. (2024). GraphMM: Graph-Based Vehicular Map Matching by Leveraging
Trajectory and Road Correlations. _IEEE Transactions on Knowledge and
Data Engineering_, _36_(1), 184--198.
https://doi.org/10.1109/TKDE.2023.3287739

Luca, G. D. (2024). _FastAPI cookbook: Develop high-performance APIs
and web applications with Python_. Packt Publishing.

Mejia, I., & Daga, N. (2014). _Poder y superposición de las líneas y
rutas de transporte público en el municipio de Cochabamba_. FACH -
Universidad Mayor de San Simón.

Obe, R. O., & Hsu, L. S. (2017). _PostgreSQL: Up and running: a
practical guide to the advanced open source database_ (Third edition).
O'Reilly Media, Inc.

Panta, Y. R., Azam, S., Shanmugam, B., Yeo, K. C., & Et., A. (2019).
Improving Accessibility for Mobility Impaired People in Smart City using
Crowdsourcing. _2019 Cybersecurity and Cyberforensics Conference (CCC)_.
https://doi.org/10.1109/CCC.2019.00-10

Phuttharak, J., & Loke, S. W. (2019). A Review of Mobile Crowdsourcing
Architectures and Challenges: Toward Crowd-Empowered Internet-of-Things.
_IEEE Access_, _7_, 304--324.
https://doi.org/10.1109/ACCESS.2018.2885353

Raymond, E. S. (2001). _The cathedral and the bazaar: Musings on Linux
and open source by an accidental revolutionary_. O'Reilly & Associates,
Inc. http://choicereviews.org/review/10.5860/CHOICE.39-2841

Sakhniuk, M. (with Boduch, A., & Derks, R.). (2024). _React and React
Native: Build cross-platform JavaScript and TypeScript apps for the web,
desktop, and mobile_ (1a ed.). Packt Publishing Limited.

Schweitzer, F. M., Buchinger, W., Gassmann, O., & Obrist, M. (2012).
Crowdsourcing: Leveraging Innovation through Online Idea Competitions.
_Research-Technology Management_.
https://doi.org/10.5437/08956308X5503055

Sobota, B., Szabo, Cs., & Perhac, J. (2008). Using path-finding
algorithms of graph theory for route-searching in geographical
information systems. _2008 6th International Symposium on Intelligent
Systems and Informatics_, 1--6.
https://doi.org/10.1109/SISY.2008.4664953

Trufi Association. (2025). _Trufi App -- Aplicación móvil para el
transporte público en Cochabamba, Bolivia_ [Home page]. Trufi App.
https://trufi.app/
