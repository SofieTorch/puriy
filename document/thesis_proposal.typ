#set page(
  paper: "us-letter",
  margin: (left: 2.54cm, right: 2.54cm, top: 2.54cm, bottom: 2.54cm),
  numbering: "1",
)

#set text(
  font: "Arial",
  size: 11pt,
  lang: "es",
)

#set par(
  justify: true,
  leading: 0.8em,
  first-line-indent: 0pt,
)

#set heading(numbering: none)

#show heading.where(level: 1): it => {
  set text(size: 12pt, weight: "bold")
  block(above: 1.5em, below: 1em, it.body)
}

#show heading.where(level: 2): it => {
  set text(size: 11pt, weight: "bold")
  block(above: 1.2em, below: 0.8em, it.body)
}

#show heading.where(level: 3): it => {
  set text(size: 11pt, weight: "bold", style: "italic")
  block(above: 1em, below: 0.6em, it.body)
}

// ============================================================
// PORTADA
// ============================================================

#set page(numbering: none)

#align(center)[
  #v(1.27cm)

  #text(size: 14pt, weight: "bold")[UNIVERSIDAD PRIVADA DEL VALLE]

  #v(0.2em)
  #text(size: 12pt, weight: "bold")[FACULTAD DE INFORMÁTICA Y ELECTRÓNICA]

  #v(0.2em)
  #text(size: 12pt, weight: "bold")[CARRERA DE LICENCIATURA EN INGENIERÍA DE SISTEMAS INFORMÁTICOS]

  #v(5.08cm)

  #text(size: 14pt, weight: "bold")[
    SISTEMA MÓVIL MULTIPLATAFORMA BASADA EN CROWDSOURCING PARA LA RECOLECCIÓN Y CENTRALIZACIÓN DE INFORMACIÓN DE RUTAS DEL TRANSPORTE PÚBLICO EN EL ÁREA METROPOLITANA DE COCHABAMBA
  ]

  #v(2cm)
]

#align(right)[
  #block(width: 50%)[
    #set par(justify: true)
    PERFIL DE PROYECTO DE GRADO PARA OPTAR AL TÍTULO DE LICENCIATURA EN INGENIERÍA DE SISTEMAS INFORMÁTICOS
  ]
]

#v(2cm)

#align(center)[
  #text(weight: "bold")[POSTULANTE:] SOFIA VALERIA TORO CHAMBI \
  #text(weight: "bold")[TUTOR:] ING. JAVIER MARCELO VASQUEZ CRUZ

  #v(2cm)

  Cochabamba -- Bolivia \
  2026
]

#pagebreak()

// ============================================================
// ÍNDICES
// ============================================================

#set page(numbering: "i")
#counter(page).update(1)

#align(center)[#text(size: 12pt, weight: "bold")[ÍNDICE DE CONTENIDO]]

#v(1em)

#outline(title: none, depth: 3, indent: auto)

#pagebreak()

#align(center)[#text(size: 12pt, weight: "bold")[ÍNDICE DE FIGURAS]]

#v(1em)

#outline(title: none, target: figure.where(kind: image))

#pagebreak()

#align(center)[#text(size: 12pt, weight: "bold")[ÍNDICE DE TABLAS]]

#v(1em)

#outline(title: none, target: figure.where(kind: table))

#pagebreak()

// ============================================================
// CONTENIDO PRINCIPAL
// ============================================================

#set page(numbering: "1")
#counter(page).update(1)

= 1. INTRODUCCIÓN

El departamento de Cochabamba, es una de las tres ciudades más grandes de Bolivia, con más de dos millones de habitantes (Instituto Nacional de Estadística INE, 2024) en donde el 55% se moviliza principalmente por transporte público (Burgos, 2019), y aun así, sin un medio confiable y actualizado que ofrezca información sobre las líneas y rutas que lo conforman.

Debido al carácter local, dinámico y privado del transporte de pasajeros en las ciudades de Bolivia (J. Cabrera et al., 2018), aplicaciones como Moovit o Google Maps no operan en el país o lo hacen de manera limitada, restringiéndose principalmente a funcionalidades de mapas. Alternativas locales como Llajta Rutas o Trufi surgieron debido a esta necesidad; sin embargo, no lograron sostenerse en el tiempo.

Ante esta situación, el presente proyecto propone el desarrollo de una aplicación móvil que centralice información sobre las diferentes líneas, tarifas, rutas y sus variantes dentro del transporte público de la ciudad de Cochabamba. Para ello, se plantea el crowdsourcing como estrategia principal para mantener la información actualizada, así como la adopción de un enfoque open source, permitiendo a la población y a la comunidad de desarrolladores contribuir al mantenimiento y evolución del proyecto a largo plazo.

El sistema de transporte público en Cochabamba presenta diversas particularidades, como los distintos tipos de vehículos y el hecho de que una misma línea pueda recorrer dos o más rutas diferentes, identificadas mediante distintivos como colores o banderas. En este contexto, el proyecto busca identificar y analizar las fortalezas de aplicaciones de referencia en el ámbito del transporte público, como Google Maps, que proporciona información sobre la dirección de las líneas, o SBB Mobile, que registra con precisión las rutas seguidas por los usuarios, con el fin de adaptar dichas funcionalidades a la realidad local y ofrecer un servicio útil y de calidad.

= 2. PLANTEAMIENTO DEL PROBLEMA

El transporte público es vital en la vida de las personas, especialmente cuando no disponen de un vehículo privado para movilizarse, como es el caso de la mayor parte de la población de Cochabamba, donde sólo un 37.2% posee un vehículo automotor o motocicleta (Instituto Nacional de Estadística INE, 2015) y, como se observa en la Figura 1, el 55% de la población utiliza el transporte público como principal medio para movilizarse en el día a día (Burgos, 2019). En estas circunstancias, es esencial para la población saber cómo movilizarse entre todas las líneas disponibles (Holguin et al., 2019).

#figure(
  rect(width: 80%, height: 200pt, stroke: 0.5pt, fill: luma(240))[
    #align(center + horizon)[
      #text(style: "italic", fill: luma(100))[
        Figura 1: Gráfico de barras\
        Transporte público (55%), Caminando o en bicicleta (24%), Transporte privado (20%)
      ]
    ]
  ],
  caption: [Medio de transporte utilizado por la población de Cochabamba],
  supplement: [Figura],
)

#align(center)[#text(style: "italic", size: 10pt)[Fuente: Elaboración propia, 2026, con base en Burgos, 2019.]]

#v(1em)

Sin embargo, como señalan Cabrera et al. (2018), si bien la regulación del transporte público urbano, incluyendo la autorización de líneas, rutas y tarifas, recae formalmente en el Gobierno Autónomo Municipal de Cochabamba, en la práctica la operación del servicio se encuentra descentralizada, siendo la excepción el tren metropolitano. Esto se debe, en parte, al Decreto Supremo Nº 21660 de Reactivación Económica, que permite que cualquier persona natural o jurídica preste libremente servicios de transporte urbano público siempre que se cumplan los requisitos de seguridad y de protección al usuario artículo N° 176.

Esta forma de organización del transporte público, caracterizada por una regulación formal sin una gestión centralizada de la información operativa, hace que el mapeo actualizado de las rutas de movilización resulte complicado. Como consecuencia, aplicaciones como Google Maps o Moovit, que ofrecen información sobre el transporte público en diversos países, no pueden operar de manera adecuada en Bolivia. De este modo, los ciudadanos carecen de acceso a conocimiento sobre las líneas disponibles, sus rutas, horas de operación y conexiones.

Considerando que en Cochabamba se realizan cerca de 2 millones de viajes diarios (J. E. Cabrera & Moyano, 2022), y que en más del 40% de hogares hay al menos un integrante que se traslada diariamente entre municipios (J. Cabrera, 2017), es vital contar con un medio que provea toda esta información faltante, especialmente para los municipios más frecuentados, cuyas rutas más concurridas se pueden observar en la Figura 2.

#figure(
  rect(width: 80%, height: 200pt, stroke: 0.5pt, fill: luma(240))[
    #align(center + horizon)[
      #text(style: "italic", fill: luma(100))[
        Mapa de flujos de transporte\
        Tiquipaya, Colcapirhua, Vinto, Sipe Sipe, Sacaba, Cercado
      ]
    ]
  ],
  caption: [Flujos de transporte en la región metropolitana de Cochabamba],
  supplement: [Figura],
)

#align(center)[#text(style: "italic", size: 10pt)[Fuente: J. E. Cabrera & Moyano, 2022.]]

#v(1em)

Anteriormente se propusieron soluciones como Llajta Rutas (J. Cabrera et al., 2018) y Trufi (Trufi Association, 2025), ambas aplicaciones móviles con mapeo de las líneas y rutas disponibles en Cochabamba; con Llajta Rutas usando crowdsourcing para construir dicho inventario, mientras Trufi lo construyó de forma independiente. Ambas aplicaciones recibieron buena acogida del público, Trufi llegando a 100 mil descargas a la fecha (Google Play, 2023) y Llajta Rutas con 10 mil descargas entre 2017 y 2018 (J. Cabrera et al., 2018).

No obstante, lamentablemente ambas aplicaciones dejaron de recibir soporte y mantenimiento activo. Llajta Rutas ya no se encuentra disponible en Play Store y fue descontinuada debido a falta de apoyo económico (Cabrera, comunicación personal, 28 de diciembre de 2025). Por otro lado, aunque Trufi aún se encuentra disponible en Play Store, su última actualización fue el 14 de diciembre de 2023 (Google Play, 2023), y se observan comentarios recientes mencionando la falta de:

- Distinción de colores de líneas, puesto que una misma línea puede tener diferentes rutas.
- Actualización de líneas disponibles y sus respectivas rutas y tarifas a lo largo del tiempo.
- Paradas y horarios del nuevo tren metropolitano de Cochabamba.

Además, cabe recalcar que las bases de datos que ambas aplicaciones recolectaron sobre las rutas están cerradas al público, por lo que no se las puede extender o consultar con un sistema externo.

En síntesis, la falta de una fuente centralizada y abierta de información actualizada sobre las rutas del transporte público en el área metropolitana de Cochabamba representa una limitación significativa para la movilidad cotidiana de la población. Si bien han existido iniciativas previas que evidencian la utilidad y aceptación de este tipo de herramientas, la ausencia de mecanismos sostenibles para la recolección y mantenimiento de la información ha impedido su continuidad en el tiempo. Esta situación pone de manifiesto la necesidad de una solución que permita recolectar y centralizar de manera colaborativa la información de rutas del transporte público, asegurando su actualización y disponibilidad a largo plazo.

== 2.1 FORMULACIÓN DEL PROBLEMA

El presente proyecto busca proponer una solución a las necesidades descritas, por lo que surge la pregunta: ¿De qué manera podría implementarse una solución tecnológica que permita recolectar y centralizar la información de rutas del transporte público en el área metropolitana de Cochabamba?

= 3. JUSTIFICACIÓN

== 3.1. JUSTIFICACIÓN SOCIAL

La aplicación beneficiará principalmente a los usuarios del transporte público del área metropolitana de Cochabamba, quienes actualmente carecen de información clara y actualizada sobre líneas, rutas, paradas y horarios. Con esta herramienta, los ciudadanos podrán planificar sus viajes de manera más eficiente, optimizando los tiempos de traslado y evitando desplazamientos innecesarios.

Un hallazgo de la aplicación Llajta Rutas mostró que incluso existían usuarios que, aunque disponían de vehículo privado, la utilizaban para "dejar el coche estacionado en algún lugar y tomar algún trufi o micro para llegar al destino final, y así evitar el congestionamiento vehicular" (J. Cabrera et al., 2018). Esto evidencia que la aplicación no solo beneficia a quienes dependen exclusivamente del transporte público, sino también a quienes buscan alternativas más eficientes y sostenibles para su desplazamiento diario.

== 3.2. JUSTIFICACIÓN TÉCNICA

Desde el punto de vista técnico, se propone el desarrollo de un sistema móvil multiplataforma basado en una arquitectura cliente-servidor de tres capas con escalamiento horizontal, como un enfoque adecuado para la recolección y centralización colaborativa de información de rutas del transporte público. Este tipo de arquitectura permite facilitar la participación de múltiples usuarios mediante dispositivos móviles, soportar accesos concurrentes y garantizar la disponibilidad de la información, sin comprometer la consistencia de los datos. Asimismo, su naturaleza escalable resulta pertinente considerando el tamaño de la población del área metropolitana de Cochabamba y la necesidad de mantener actualizada una base de información dinámica.

Además, el proyecto se desarrollará bajo un modelo open source, permitiendo que tanto el código de la aplicación como la información recolectada sobre rutas del transporte público puedan ser consultados y descargados por la comunidad desde un repositorio público. Esta estrategia facilita la continuidad y mantenimiento del sistema a lo largo del tiempo, fomentando la participación de otros desarrolladores y usuarios en la actualización y mejora de la información, y garantizando que el conocimiento generado no quede cerrado a una única instancia del proyecto.

== 3.3 JUSTIFICACIÓN ECONÓMICA

Desde el punto de vista económico, el desarrollo de un sistema móvil multiplataforma basado en crowdsourcing representa una solución rentable para la recolección y centralización de información de rutas del transporte público en Cochabamba. Al permitir que los propios usuarios contribuyan a la actualización de los datos, se reducen los costos asociados a la recopilación y mantenimiento manual de la información. Además, al ser open source, tanto el código como los datos podrán ser reutilizados y mantenidos por la comunidad, evitando gastos de licencias o personal especializado a largo plazo.

Para cubrir los costos de despliegue y operación del sistema, tales como servidores, dominio y servicios asociados, se cuenta con un capital inicial destinado a la realización de pruebas durante el desarrollo del proyecto. La sostenibilidad económica a largo plazo del sistema, que incluye la búsqueda de fondos de posibles organizaciones interesadas como alcaldías del departamento de Cochabamba o federaciones de transporte público, no forma parte del alcance del presente proyecto de grado y se plantea como una etapa posterior a su conclusión.

= 4. OBJETIVOS

== 4.1. OBJETIVO GENERAL

Desarrollar un sistema móvil multiplataforma basado en crowdsourcing para la recolección y centralización de información de rutas del transporte público en el área metropolitana de Cochabamba.

== 4.2. OBJETIVOS ESPECÍFICOS

- Elaborar un sistema de monitoreo colaborativo de rutas, mediante el registro georreferenciado de trayectos y un pipeline de procesamiento estadístico, para recolectar y centralizar progresivamente la información de rutas de las líneas de transporte público de Cochabamba.
- Facilitar el registro de desvíos temporales, mediante el registro georreferenciado con etiquetado respecto a una línea, para que los usuarios notifiquen y consulten cambios inesperados en los recorridos habituales.
- Desarrollar un subsistema de gestión de tarifas, con parametrización por municipio y tramo origen-destino, para que los usuarios reporten y consulten las tarifas del transporte público.
- Gestionar la información de líneas de transporte, con diferenciación de ramales, para que los usuarios registren, consulten y actualicen información sobre las rutas y horarios de operación.
- Proveer un servicio de identificación de trayectos, mediante un algoritmo de búsqueda de rutas con soporte de transbordos sobre grafos de red de transporte, para que los usuarios encuentren las líneas necesarias para desplazarse entre un origen y un destino.

= 5. ALCANCE

A continuación, se especifica el alcance del proyecto a partir de los objetivos específicos.

a) Elaborar un sistema de monitoreo colaborativo de rutas, mediante el registro georreferenciado de trayectos y un pipeline de procesamiento estadístico, para recolectar y centralizar progresivamente la información de rutas de las líneas de transporte público de Cochabamba.

- Registrar recorridos del transporte público mediante coordenadas geográficas capturadas en tiempo real por los usuarios.
- Asociar los recorridos registrados a una línea de transporte específica.
- Construir rutas representativas de cada línea a través de un pipeline de procesamiento de los recorridos registrados por los usuarios.
- Permitir a los usuarios confirmar o rechazar la correspondencia entre una ruta inferida y una línea de transporte.

b) Facilitar el registro de desvíos temporales, mediante el registro georreferenciado con etiquetado respecto a una línea, para que los usuarios notifiquen y consulten cambios inesperados en los recorridos habituales.

- Permitir a los usuarios reportar desvíos temporales en los recorridos habituales de las líneas de transporte.
- Registrar el tramo afectado y la duración estimada del desvío.
- Permitir a otros usuarios confirmar o refutar los desvíos reportados.

c) Desarrollar un subsistema de gestión de tarifas, con parametrización por municipio y tramo origen-destino, para que los usuarios reporten y consulten las tarifas del transporte público.

- Permitir el registro colaborativo de tarifas del transporte público entre un municipio origen y un municipio destino.
- Permitir la consulta de tarifas registradas por los usuarios.
- Consolidar tarifas reportadas cuando existan múltiples registros para un mismo tramo.

d) Gestionar la información de líneas de transporte, con diferenciación de ramales, para que los usuarios registren, consulten y actualicen información sobre las rutas y horarios de operación.

- Permitir el registro de nuevas líneas de transporte público.
- Almacenar información básica de cada línea, incluyendo rutas consolidadas y horarios de operación.
- Permitir la consulta y actualización colaborativa de la información de las líneas registradas.

e) Proveer un servicio de identificación de trayectos, mediante un algoritmo de búsqueda de rutas con soporte de transbordos sobre grafos de red de transporte, para que los usuarios encuentren las líneas necesarias para desplazarse entre un origen y un destino.

- Permitir al usuario ingresar un punto de origen y un punto de destino.
- Identificar las líneas de transporte público que permiten realizar el desplazamiento entre los puntos indicados, a partir de las rutas consolidadas.
- Permitir a los usuarios suscribirse a líneas o rutas específicas.
- Notificar a los usuarios suscritos cuando se registren o confirmen desvíos en las rutas de su interés.

= 6. MARCO TEÓRICO

A continuación, se presenta una revisión de bibliografía en cuanto al estado actual del transporte público en Cochabamba, así como de las tecnologías y estrategias que se plantea utilizar en el presente proyecto, las cuales incluyen crowdsourcing, algoritmos relacionados a sistemas geográficos, el enfoque open source, y las herramientas específicas para la implementación del sistema.

== 6.1. TRANSPORTE PÚBLICO URBANO EN COCHABAMBA

El sistema de transporte público en el Área Metropolitana de Cochabamba se constituye sobre un modelo de paratránsito de carácter privado, informal, autónomo y con escasa regulación estatal (J. Cabrera et al., 2018; J. E. Cabrera & Moyano, 2022). Esta región metropolitana está integrada por las áreas urbanas de siete municipios: Cercado, Quillacollo, Sipe Sipe, Tiquipaya, Vinto, Colcapirhua y Sacaba (J. E. Cabrera & Moyano, 2022; véase Figura 3).

#figure(
  rect(width: 80%, height: 200pt, stroke: 0.5pt, fill: luma(240))[
    #align(center + horizon)[
      #text(style: "italic", fill: luma(100))[
        Mapa del Área Metropolitana de Cochabamba\
        (Tiquipaya, Vinto, Quillacollo, Colcapirhua, Cochabamba, Sipe Sipe, Sacaba)
      ]
    ]
  ],
  caption: [Área Metropolitana de Cochabamba],
  supplement: [Figura],
)

#align(center)[#text(style: "italic", size: 10pt)[Fuente: J. E. Cabrera & Moyano, 2022.]]

#v(1em)

A diferencia de otras ciudades bolivianas, el servicio en su mayoría no depende de una administración estatal centralizada, sino de una compleja red de operadores organizados en sindicatos, asociaciones y cooperativas. Este sistema ha funcionado bajo un régimen de transporte libre institucionalizado desde 1985, lo que permitió una expansión desorganizada y una oferta excesiva de vehículos de baja capacidad que responden más a la lógica del mercado que a la planificación urbana (J. E. Cabrera & Moyano, 2022). Desde una perspectiva socioterritorial, este sistema funciona como un dispositivo de urbanización, consolidando nuevos asentamientos periféricos al proveer la principal red de conectividad física disponible en áreas donde el Estado no ha planificado infraestructuras básicas (J. Cabrera et al., 2018).

=== 6.1.1. MEDIOS DE TRANSPORTE PÚBLICO

Como indican Cabrera et al. (2018), la oferta de movilidad motorizada para pasajeros en la metrópoli se distribuye principalmente en cuatro modalidades de vehículos automotores: micros, coasters, trufis y taxi-trufis (véase Figura 4).

- *Micros:* Constituyen la modalidad más antigua, con unidades de gran envergadura y capacidad para 35 a 40 pasajeros; con mayor presencia en las áreas centrales de Cochabamba y Quillacollo.
- *Coasters (costero, en inglés):* Minibuses con una capacidad de 16 a 30 usuarios, cuya circulación es frecuente en los municipios de Quillacollo, Sipe Sipe y Vinto.
- *Trufis (Transporte de Ruta Fija):* Son furgonetas o minibuses adaptados para transportar entre 7 y 14 pasajeros; es la modalidad con mayor cobertura en toda la conurbación.
- *Taxi-trufis:* Vehículos tipo sedán que operan en rutas fijas con capacidad de 4 a 7 pasajeros; representan, junto a los trufis, la mayor parte de la oferta de transporte público.

En conjunto, este parque automotor supera las 40,000 unidades, lo que genera una saturación de información y tráfico en los nodos centrales (Mejia & Daga, 2014).

#figure(
  rect(width: 80%, height: 150pt, stroke: 0.5pt, fill: luma(240))[
    #align(center + horizon)[
      #text(style: "italic", fill: luma(100))[
        Tipos de vehículos: Micro, Coaster, Trufi, Taxi-trufi
      ]
    ]
  ],
  caption: [Tipos de vehículos de transporte público en la región metropolitana de Cochabamba.],
  supplement: [Figura],
)

#align(center)[#text(style: "italic", size: 10pt)[Fuente: J. E. Cabrera & Moyano, 2022.]]

#v(1em)

=== 6.1.2. CARACTERÍSTICAS OPERATIVAS

De acuerdo con Cabrera (2023), el modelo operativo del transporte en Cochabamba se fundamenta en el concepto de "hombre-camión", donde el transportista ejerce de forma unilateral la propiedad, administración y operación de su unidad vehicular. Técnicamente, el sistema destaca por un dinamismo informal, donde las rutas se crean, extienden o subdividen mediante acuerdos directos entre los operadores y las dirigencias barriales (OTB), operando frecuentemente fuera del registro oficial de los gobiernos municipales (J. E. Cabrera & Moyano, 2022).

Uno de los rasgos más críticos y complejos para el usuario es la extensión de rutas y su subdivisión en ramales. Bajo una misma denominación de "línea", las organizaciones suelen operar múltiples recorridos secundarios para cubrir la demanda de diversos sectores o nuevos barrios (J. E. Cabrera & Moyano, 2022). Esta fragmentación se manifiesta visualmente a través de un código informal de identificación: los vehículos de una misma línea se diferencian entre sí mediante banderines de colores, letras específicas, letreros en los parabrisas o franjas de colores distintivos en la carrocería. Por ejemplo, Cabrera & Moyano (2022) identificaron que el sindicato Santa Rosa de Lima se comprende por 22 ramales utilizando combinaciones de letras, nombres de paradas y colores específicos para orientar a la población. En la Figura 5 se puede observar ejemplos de otras líneas con esta fragmentación, como son los taxi-trufis 150 y el 123.

#figure(
  rect(width: 80%, height: 200pt, stroke: 0.5pt, fill: luma(240))[
    #align(center + horizon)[
      #text(style: "italic", fill: luma(100))[
        Mapas de extensión y subdivisión de rutas\
        Taxi Trufi 150 (Extensión) y Taxi Trufi 123 (Subdivisión)
      ]
    ]
  ],
  caption: [Extensión y subdivisión de rutas],
  supplement: [Figura],
)

#align(center)[#text(style: "italic", size: 10pt)[Fuente: Cabrera & Moyano, 2022.]]

#v(1em)

Esta proliferación de variantes es tan amplia que se han identificado 132 líneas que operan un total de 648 rutas distintas en la región, llegando a concentrarse hasta 500 rutas en el centro comercial del municipio de Cercado, lo que genera una saturación crítica de las vías (J. E. Cabrera & Moyano, 2022).

Lamentablemente, este mapeo de rutas fue realizado de forma privada y los datos no se encuentran disponibles al público (Cabrera, comunicación personal, 28 de diciembre de 2025). Esta falta de transparencia en los recorridos exactos y la dependencia de señales visuales informales (como los colores y banderines) justifican la necesidad técnica de herramientas de información que sistematicen la inteligencia colectiva de la urbe.

=== 6.1.3. DESAFÍOS ACTUALES

Desde la computación urbana, el principal desafío es la ausencia de información oficial, pública y estandarizada sobre las líneas de transporte, sus recorridos, paradas y subdivisiones (J. Cabrera et al., 2018). Esta carencia se divide en los siguientes factores:

- *Inoperatividad de plataformas globales:* En Bolivia, servicios como Google Maps no integran datos del transporte público, dejando al usuario dependiente del conocimiento empírico o la consulta directa.
- *Fragmentación y superposición de datos:* La coexistencia de cientos de rutas que se superponen (hasta 500 rutas en puntos críticos del centro) genera una sobresaturación visual y cognitiva para el ciudadano (J. E. Cabrera & Moyano, 2022).
- *Necesidad de sistematización:* La movilidad actual reside en una "inteligencia colectiva" no digitalizada; la implementación de soluciones basadas en crowdsourcing es fundamental para capturar, procesar y devolver esta información a la población, transformando el sistema informal en una red de datos inteligente (J. Cabrera et al., 2018).

== 6.2. CROWDSOURCING PARA RECOLECCIÓN DE INFORMACIÓN

El crowdsourcing fue acuñado originalmente por Howe (2006) para describir el acto de una empresa, institución u organización que toma una función tradicionalmente realizada por empleados y la externaliza a una red indefinida y generalmente amplia de personas mediante una convocatoria abierta.

Académicamente, se le considera una forma explícita de integrar las aportaciones de los consumidores en las actividades de comercialización y una categoría fundamental dentro del paradigma de la innovación abierta (open innovation) (Kleemann et al., 2008). Este fenómeno se sustenta en la participación masiva a través de Internet y dispositivos móviles, permitiendo resolver problemas científicos o empresariales complejos que, en ocasiones, superan la capacidad de departamentos internos de Innovación y Desarrollo (Hossain & Kauranen, 2015).

Las aplicaciones exitosas del crowdsourcing abarcan desde la generación de ideas y concursos de diseño (Schweitzer et al., 2012) hasta el microtasking (pequeñas tareas que pueden o no ser remuneradas) (Kittur et al., 2011), y la producción de software de calidad empresarial a través del open source (Howe, 2006).

=== 6.2.1. CROWDSOURCING APLICADO A SISTEMAS DE MOVILIDAD

El crowdsourcing móvil (MCS) se define como un paradigma donde individuos con dispositivos móviles recopilan y comparten datos para resolver problemas complejos de forma distribuida (Kong et al., 2019). A diferencia del crowdsourcing tradicional basado en la web, el MCS aprovecha la movilidad de los usuarios y los sensores integrados, como el GPS y el acelerómetro, para capturar información del entorno físico en tiempo real (Kong et al., 2019; Panta et al., 2019). En el ámbito de la movilidad urbana, este enfoque permite que los ciudadanos pasen de ser consumidores pasivos a prosumidores que generan inteligencia colectiva sobre el sistema de transporte (J. E. Cabrera, 2023; Kong et al., 2019).

Esta tecnología es particularmente efectiva para mapear sistemas de paratránsito e informalidad, donde la ausencia de información oficial genera incertidumbre (J. Cabrera et al., 2018). Proyectos similares, como "Llajta Rutas Metropolitana" en Cochabamba o "Digital Matatus" en Nairobi, han demostrado que el seguimiento de trayectorias mediante GPS permite reconstruir rutas y horarios de servicios que no están integrados en plataformas globales como Google Maps (J. Cabrera et al., 2018; Hou et al., 2018). Técnicamente, el sistema puede recolectar datos de forma participativa, donde el usuario selecciona activamente su línea de viaje, u oportunística, capturando la ubicación en segundo plano para inferir patrones de desplazamiento y popularidad de trayectos (Phuttharak & Loke, 2019).

=== 6.2.2. MECANISMOS DE VALIDACIÓN COLABORATIVA DE DATOS

Debido a que los datos generados por la multitud pueden ser ruidosos, incompletos o provenir de usuarios malintencionados, la validación de respuestas es un paso crítico para garantizar la fiabilidad del sistema (Hou et al., 2018; Hung et al., 2017). Existen diversos métodos académicos para realizar esta verificación sin depender exclusivamente de expertos humanos costosos:

- *Votación por Mayoría (Majority Voting):* Es el mecanismo más común de control de calidad basado en la redundancia. Bajo este esquema, una ruta deducida algorítmicamente se considera válida si un número suficiente de usuarios independientes confirman o proporcionan datos coincidentes (Hirth et al., 2013).
- *Enfoque de Grupo de Control (Control Group):* En esta modalidad, un usuario realiza la tarea principal (recolectar el trayecto) y otros miembros de la comunidad actúan como validadores, calificando la veracidad de la información según criterios predefinidos (Hirth et al., 2013).
- *Sistemas de Puntuación de Retroalimentación (Feedback Scoring):* Estos algoritmos calculan la confiabilidad de un reporte basándose en las puntuaciones asignadas por otros usuarios y el historial de contribuciones del informante. Un usuario con alta reputación o "social badge" actúa como un multiplicador de credibilidad, permitiendo que sus validaciones requieran menos confirmaciones adicionales para ser publicadas (Panta et al., 2019).
- *Detección de Usuarios Defectuosos:* Para proteger la integridad de la base de datos, se aplican métodos probabilísticos que identifican a "spammers" o trabajadores descuidados, excluyendo sus respuestas si estas se desvían significativamente del consenso o de la estructura lógica de la red vial (Hung et al., 2017).

Estos mecanismos permitirán reducir la incertidumbre del conjunto de datos y asegurar que el mapa resultante refleje la realidad operativa de las líneas de transporte en Cochabamba.

== 6.3. SOFTWARE DE CÓDIGO ABIERTO (OPEN SOURCE)

El software de código abierto (Open Source Software o OSS) se define como aquel cuyo código fuente es público, permitiendo su uso, modificación y distribución libre de costo (Hossain & Kauranen, 2015). Técnicamente, su éxito radica en la creación de una comunidad sostenible que coevoluciona con el sistema para desarrollar código con rapidez y depurarlo de forma efectiva (Aberdour, 2007). Este modelo se describe mediante el "modelo de cebolla", donde un núcleo pequeño de desarrolladores líderes (core team) es apoyado por capas sucesivas de desarrolladores contribuyentes, informantes de errores (bug reporters) y usuarios finales (Aberdour, 2007).

Uno de los pilares de su calidad es la Ley de Linus, acuñado por Raymond (2001), que establece que "dado un número suficientemente elevado de ojos, todos los errores se vuelven obvios", subrayando el poder del peer review (revisión por pares) masivo para alcanzar niveles de fiabilidad comparables o superiores al software comercial. En el ámbito legal, su gobernanza se apoya en una amplia gama de licencias (como GPL, BSD o MPL) que utilizan el derecho de autor no para restringir, sino para garantizar la libertad de acceso y la reciprocidad en las mejoras del código (Fitzgerald, 2006).

Aplicar este enfoque al desarrollo del sistema permitirá que voluntarios de Cochabamba puedan dar mantenimiento a la aplicación, sin depender de una organización externa para mantenerla actualizada.

== 6.4. SISTEMAS DE INFORMACIÓN GEOGRÁFICA (SIG)

Un Sistema de Información Geográfica (SIG) se define como una colección organizada de hardware, software y datos geográficos diseñada para la captura, almacenamiento, procesamiento y visualización de información espacial compleja (Sobota et al., 2008). En el contexto de la movilidad urbana, un SIG permite modelar la infraestructura vial como un grafo de red $G(V, E)$, donde los segmentos de calle (aristas) poseen atributos específicos como longitud, sentido y restricciones de giro (Bast et al., 2016; Liu et al., 2024). Para una aplicación de transporte, el SIG no solo actúa como un repositorio cartográfico, sino como el motor de análisis espacial que permite transformar nubes de coordenadas crudas en secuencias lógicas de aristas que representan el recorrido real de un vehículo (Sobota et al., 2008).

=== 6.4.1. COINCIDENCIA DE TRAYECTOS (MAP MATCHING)

La Coincidencia de Trayectos o _Map Matching_ es el proceso computacional de asignar una secuencia de posiciones medidas (geopoints) a los segmentos correspondientes de una red vial en un mapa digital (Hou, 2021; Kubička et al., 2015). Dada la naturaleza de la presente propuesta, se prioriza el enfoque de Offline Map Matching, el cual procesa trayectorias completas o conjuntos de datos históricos para generar rutas con una alta precisión, siendo ideal para aplicaciones de análisis de comportamiento de viaje y reconstrucción de itinerarios (Hou, 2021; Hou et al., 2018).

Debido a que los datos recolectados suelen presentar ruido por deriva de señal (GPS drift) o bajas tasas de muestreo, el algoritmo no puede limitarse a una simple asignación geométrica de puntos a la calle más cercana (Hou, 2021; Liu et al., 2024). En su lugar, se emplean modelos probabilísticos como el Modelo Oculto de Márkov (HMM), donde las probabilidades de emisión (distancia del punto a la calle) y de transición (probabilidad de que dos calles formen una ruta lógica) permiten deducir el camino más probable, incluso cuando los puntos están dispersos (Hou, 2021; Hou et al., 2018).

=== 6.4.2. IDENTIFICACIÓN Y RECONSTRUCCIÓN DE RUTAS

La identificación de trayectos a partir de datos masivos etiquetados por "línea" requiere explotar la correlación inter-trayectoria, definida como la relación entre múltiples viajes que comparten segmentos viales comunes (Liu et al., 2024). Al consolidar miles de geopoints registrados por diferentes usuarios bajo una misma etiqueta de línea, el sistema puede construir un grafo de trayectorias utilizando una representación de rejillas (grids) para integrar la información distribuida (Liu et al., 2024).

Este enfoque permite aplicar técnicas de agregación de inteligencia colectiva, donde la ruta final de la línea se determina mediante el concepto de popularidad de ruta (route popularity) (Ghezzi et al., 2017; Hou, 2021). La popularidad se cuantifica según el número de trazas de usuarios que confirman un mismo segmento vial, permitiendo que el sistema identifique y descarte el ruido individual para retener únicamente el itinerario operativo real (Hou, 2021). Finalmente, la alineación en el espacio latente entre las trayectorias de los usuarios y los segmentos del mapa permite que la aplicación proporcione una inferencia robusta, transformando puntos inconexos en una infraestructura de datos inteligente para la población (Liu et al., 2024).

== 6.5. TECNOLOGÍAS BASE DEL SISTEMA

A continuación, se presentan las tecnologías principales que se utilizarán para la implementación del sistema propuesto.

=== 6.5.1. BASE DE DATOS POSTGRESQL

Como señalan Obe & Hsu (2017), PostgreSQL es un sistema de gestión de bases de datos relacionales de clase empresarial y código abierto, reconocido por ser uno de los más avanzados a nivel mundial. Se define no solo como una base de datos, sino como una plataforma de aplicaciones robusta que permite la ejecución de procedimientos almacenados en múltiples lenguajes de programación, tales como PL/pgSQL, Python, Perl y JavaScript (PL/V8).

Una de sus características académicas más distintivas es su extensibilidad, permitiendo a los usuarios definir sus propios tipos de datos, operadores y funciones personalizadas (Obe & Hsu, 2017). Una de las extensiones más favorables para el presente proyecto es la de '_postgis_', que integra tipos de datos de geolocalización como puntos de coordenadas y trayectos.

=== 6.5.2. FASTAPI FRAMEWORK

FastAPI es un framework web moderno y de alto rendimiento diseñado para la construcción de APIs con Python, fundamentado en las anotaciones de tipos estándar del lenguaje. Su arquitectura técnica se apoya en Starlette para la gestión de las partes web y en Pydantic para la validación y serialización de datos, lo que le otorga una velocidad comparable a frameworks en Go o Node.js. FastAPI destaca por su capacidad para manejar la programación asíncrona nativa mediante la sintaxis async/await, optimizando la eficiencia en operaciones de entrada/salida. Además, ofrece funcionalidades automáticas de documentación interactiva (Swagger UI y ReDoc) basadas en el estándar OpenAPI (Luca, 2024).

=== 6.5.3. REACT NATIVE FRAMEWORK

De acuerdo con Sakhniuk (2024), React Native es una biblioteca y framework de JavaScript, desarrollado originalmente por Meta, destinado al desarrollo de aplicaciones móviles nativas. A diferencia de los frameworks híbridos tradicionales, React Native no renderiza una vista web, sino que utiliza bloques de construcción de la interfaz de usuario nativa de sistemas operativos como Android (Java/Kotlin) e iOS (Objective-C/Swift).

Su arquitectura se basa en la comunicación entre un hilo de JavaScript y un hilo nativo a través de un puente (bridge), o mediante la nueva JavaScript Interface (JSI), permitiendo un rendimiento fluido y una experiencia de usuario cercana a las aplicaciones desarrolladas de forma puramente nativa.

= 7. METODOLOGÍA

== 7.1 METODOLOGÍA DE DESARROLLO DEL SISTEMA

Para el desarrollo del sistema se adopta el modelo del Ciclo de Vida de Desarrollo de Software (SDLC, por sus siglas en inglés) en su variante secuencial. Se opta por este enfoque debido a que el proyecto cuenta con un alcance definido desde la etapa de planificación, es desarrollado por un único responsable y se enmarca en un contexto académico con plazos establecidos, condiciones bajo las cuales un modelo secuencial resulta más adecuado que metodologías iterativas orientadas a equipos de desarrollo. Las fases contempladas son las siguientes:

- *Análisis:* Comprende la definición de los requerimientos funcionales y no funcionales del sistema, tomando como base el planteamiento del problema, los objetivos específicos y el alcance del proyecto. En esta fase se identifican las necesidades de los usuarios en relación con la recolección colaborativa de información del transporte público.
- *Diseño:* Comprende la elaboración de la arquitectura del sistema bajo el modelo cliente-servidor, el diseño del esquema de base de datos geoespacial y el prototipado de las interfaces de usuario. Las decisiones de diseño se fundamentan en los requerimientos definidos en la fase anterior.
- *Desarrollo:* Comprende la implementación del sistema siguiendo un orden incremental por funcionalidad: gestión de líneas de transporte, monitoreo colaborativo de rutas, registro de desvíos temporales, gestión de tarifas e identificación de trayectos. Este orden responde a las dependencias entre funcionalidades, dado que el monitoreo de rutas y las funcionalidades subsecuentes dependen de las líneas registradas en el sistema.
- *Pruebas:* Comprende la verificación del funcionamiento del sistema mediante pruebas controladas con usuarios, la evaluación de la precisión en la reconstrucción de rutas y la recopilación de retroalimentación sobre la usabilidad de la aplicación.

Las herramientas tecnológicas empleadas para el desarrollo del sistema se listan en la Tabla 1.

#figure(
  table(
    columns: (auto, auto, 1fr),
    align: left,
    stroke: 0.5pt,
    table.header(
      [*Herramienta*], [*Tipo*], [*Aplicabilidad en el proyecto*],
    ),
    [PostgreSQL + PostGIS], [Base de datos], [Almacenamiento de datos relacionales y geoespaciales (ver sección 6.5.1)],
    [FastAPI], [Framework backend], [Desarrollo de la API REST del sistema (ver sección 6.5.2)],
    [React Native], [Framework frontend], [Desarrollo de la aplicación móvil multiplataforma (ver sección 6.5.3)],
    [Git / GitHub], [Control de versiones], [Gestión y seguimiento del código fuente],
    [Figma], [Herramienta de diseño], [Prototipado y diseño de interfaces de usuario],
  ),
  caption: [Herramientas tecnológicas para el desarrollo del sistema.],
  supplement: [Tabla],
)

#align(center)[#text(style: "italic", size: 10pt)[Fuente: Elaboración propia, 2026.]]

#v(1em)

== 7.2. ENFOQUE DE INVESTIGACIÓN

El presente proyecto adopta un enfoque mixto con predominancia cualitativa. El enfoque cualitativo se aplica en el análisis del problema, la definición de requerimientos, el diseño de la arquitectura del sistema y de los módulos funcionales, así como en la interpretación de la retroalimentación obtenida sobre la utilidad y funcionamiento de la aplicación.

El enfoque cuantitativo se emplea de manera complementaria, mediante la recolección y análisis de datos básicos obtenidos a partir de cuestionarios en línea y métricas simples del sistema durante pruebas controladas.

== 7.3. TIPO DE INVESTIGACIÓN

La investigación es de tipo aplicada, dado que está orientada al desarrollo de una solución tecnológica que responde a un problema concreto relacionado con el acceso a información del transporte público en el área metropolitana de Cochabamba. Como resultado de la investigación se obtendrá una aplicación móvil funcional que implementa un modelo de recopilación colaborativa de datos de transporte público. Se busca dar una solución práctica a la problemática planteada haciendo uso de conceptos y tecnologías existentes.

== 7.4. MÉTODOS

En el desarrollo del proyecto se emplean métodos teóricos y empíricos, seleccionados según su pertinencia para cada fase de la investigación.

- El *método analítico* consiste en la descomposición de un objeto de estudio en cada una de sus partes para estudiarlas de forma individual y luego de forma integral (Bernal Torres, 2016). En este proyecto se aplica durante la fase de análisis, donde la problemática del acceso a la información del transporte público se descompone en necesidades específicas de los usuarios, a partir de las cuales se derivan los casos de uso y requisitos del sistema.
- El *método sintético* consiste en la reconstrucción de un todo a partir de los elementos identificados mediante el análisis, generando un conocimiento superior al integrar los componentes estudiados (Bernal Torres, 2016). Se aplica en el diseño e implementación del sistema, integrando los requisitos identificados en una solución tecnológica coherente.
- La *observación indirecta* es un método empírico de recolección de datos en el que el investigador no estudia el fenómeno directamente, sino a través de instrumentos intermedios o fuentes secundarias (Hernández Sampieri et al., 2014). Se aplica durante las pruebas controladas del sistema, analizando el comportamiento de la aplicación y del pipeline a través de los datos generados, así como mediante el análisis de la retroalimentación recopilada por medios digitales.

== 7.5. TÉCNICAS

Las técnicas de investigación empleadas en el proyecto son las siguientes:

- El *análisis documental* es una forma de investigación técnica que consiste en un conjunto de operaciones intelectuales orientadas a describir y representar documentos de forma sistemática, permitiendo su recuperación y análisis (Hernández Sampieri et al., 2014). En este proyecto se aplica durante la revisión de antecedentes teóricos, trabajos relacionados y aplicaciones similares existentes, con el fin de fundamentar las decisiones de diseño e identificar enfoques previos relevantes para el problema abordado. El instrumento asociado es una guía de análisis documental que permite sistematizar y clasificar la información revisada.
- La *encuesta estructurada* es una técnica de recolección de datos mediante un conjunto predefinido de preguntas aplicadas a una muestra de personas, orientada a identificar opiniones, percepciones y comportamientos de una población (Hernández Sampieri et al., 2014). En este proyecto se aplica mediante cuestionarios distribuidos en línea, orientados a identificar las percepciones y expectativas de los usuarios respecto a la aplicación y al acceso a la información del transporte público. El instrumento asociado es un cuestionario estructurado con preguntas cerradas distribuido a través de medios digitales.
- El *análisis exploratorio de resultados* es una técnica empírica que permite interpretar y organizar la información recolectada para apoyar la evaluación de una solución, identificando patrones, tendencias y aspectos de mejora (Hernández Sampieri et al., 2014). En este proyecto se aplica sobre los datos generados durante las pruebas controladas del sistema y sobre las respuestas obtenidas mediante las encuestas. El instrumento asociado son los registros de funcionamiento del sistema y las herramientas de análisis de datos utilizadas para organizar y procesar la información obtenida.

== 7.6. INSTRUMENTOS

Los instrumentos utilizados en el proyecto se relacionan directamente con las técnicas descritas anteriormente:

- La *guía de análisis documental*, asociada al análisis documental, es un instrumento que permite sistematizar la revisión de fuentes mediante criterios predefinidos de selección, clasificación y síntesis de la información relevante para la investigación.
- El *cuestionario estructurado*, asociado a la encuesta estructurada, consiste en un conjunto de preguntas cerradas distribuidas en línea, diseñadas para recopilar información sobre las percepciones y expectativas de los usuarios respecto a la aplicación.
- Los *registros de funcionamiento del sistema*, asociados al análisis exploratorio de resultados, comprenden los logs, métricas y datos generados durante las pruebas controladas de la aplicación y el pipeline, que permiten evaluar el comportamiento del sistema y detectar áreas de mejora.

== 7.7. POBLACIÓN

La población objeto de estudio estará conformada por usuarios del transporte público del área metropolitana de Cochabamba, conformada por los municipios de Cercado, Quillacollo, Sipe Sipe, Tiquipaya, Vinto, Colcapirhua y Sacaba (J. E. Cabrera & Moyano, 2022). Esta región cuenta con aproximadamente 1.42 millones de habitantes (Instituto Nacional de Estadística INE, 2024), de los cuales el 55% utiliza el transporte público como principal medio de movilización (Burgos, 2019), lo que representa una población potencial de aproximadamente 750.000 personas. Dado el alcance de la investigación, no es viable trabajar con la totalidad de esta población, por lo que se definió una muestra para las pruebas de la aplicación.

La muestra está compuesta por 20 personas seleccionadas mediante muestreo no probabilístico por conveniencia. Este tamaño se fundamenta en Nielsen (1993), quien establece que con 20 usuarios se detecta aproximadamente el 95% de los problemas de usabilidad en pruebas de software, siendo suficiente para los fines de una prueba piloto exploratoria. Se establecieron los siguientes criterios de selección:

*Criterios de inclusión:*

- Residir en el área metropolitana de Cochabamba.
- Utilizar el transporte público de forma habitual.
- Contar con un dispositivo móvil con sistema Android o iOS.
- Contar con acceso a datos móviles fuera del hogar o lugar de trabajo.

*Criterios de exclusión:*

- Ser menor de 18 años.
- No utilizar el transporte público como medio de movilización habitual.
- No contar con dispositivo móvil compatible o acceso a internet móvil.

La validación del sistema se realizará a través de una prueba piloto, en la que los participantes interactuarán con la aplicación en condiciones reales de uso. La aceptación y satisfacción del sistema será medida mediante un cuestionario estructurado basado en la Escala de Likert de cinco puntos, evaluando dimensiones como usabilidad, utilidad percibida y facilidad de uso.

== 7.8. FUENTES

Las fuentes de información se clasifican en:

- *Primarias*, constituidas por los datos obtenidos a través de las encuestas aplicadas a los usuarios del transporte público, los resultados de las pruebas piloto realizadas con la aplicación, artículos científicos de investigación original y documentación técnica oficial de las herramientas utilizadas en el desarrollo del sistema.
- *Secundarias*, conformadas por artículos de revisión bibliográfica, reportes sobre movilidad urbana, y reportes sobre aplicaciones de transporte en otras ciudades.

= 8. ÍNDICE TENTATIVO

*INTRODUCCIÓN*

#align(center)[*CAPÍTULO I* \ *MARCO TEÓRICO*]

#v(0.5em)

#block(inset: (left: 0pt))[
1.1. TRANSPORTE PÚBLICO URBANO EN COCHABAMBA \
#h(2em) 1.1.1. MEDIOS DE TRANSPORTE PÚBLICO \
#h(2em) 1.1.2. CARACTERÍSTICAS OPERATIVAS \
#h(2em) 1.1.3. DESAFÍOS ACTUALES \
1.2. SISTEMAS DE INFORMACIÓN APLICADOS A LA MOVILIDAD URBANA \
#h(2em) 1.2.1. APLICACIONES LOCALES \
#h(4em) 1.2.1.1. Llajta rutas metropolitana \
#h(4em) 1.2.1.2. Trufi app \
#h(2em) 1.2.2. APLICACIONES FUERA DE BOLIVIA \
#h(4em) 1.2.2.1. Google Maps \
#h(4em) 1.2.2.2. Moovit \
#h(4em) 1.2.2.3. Here WeGo \
#h(4em) 1.2.2.4. SBB Mobile \
1.3. CROWDSOURCING PARA RECOLECCIÓN DE INFORMACIÓN \
#h(2em) 1.3.1. CROWDSOURCING APLICADO A SISTEMAS DE MOVILIDAD \
#h(2em) 1.3.2. MECANISMOS DE VALIDACIÓN COLABORATIVA DE DATOS \
1.4. SOFTWARE DE CÓDIGO ABIERTO (OPEN SOURCE) \
1.5. SISTEMAS DE INFORMACIÓN GEOGRÁFICA (SIG) \
#h(2em) 1.5.1 COINCIDENCIA DE TRAYECTOS (MAP MATCHING) \
#h(2em) 1.5.2 IDENTIFICACIÓN Y RECONSTRUCCIÓN DE RUTAS \
1.6. TECNOLOGÍAS BASE DEL SISTEMA \
#h(2em) 1.6.1. ARQUITECTURA CLIENTE SERVIDOR \
#h(2em) 1.6.2. ESCALAMIENTO HORIZONTAL \
#h(2em) 1.6.3. BALANCEO DE CARGA \
#h(2em) 1.6.4. BASE DE DATOS POSTGRESQL \
#h(2em) 1.6.5. FASTAPI FRAMEWORK \
#h(2em) 1.6.6. REACT NATIVE FRAMEWORK
]

#v(1em)

#align(center)[*CAPÍTULO II* \ *INGENIERÍA DEL PROYECTO*]

#v(0.5em)

#block(inset: (left: 0pt))[
2.1. FASE DE ANÁLISIS \
#h(2em) 2.1.1. CARACTERIZACIÓN DE USUARIOS \
#h(2em) 2.1.2. CASOS DE USO \
#h(2em) 2.1.3. REQUERIMIENTOS NO FUNCIONALES \
#h(2em) 2.1.4. REQUERIMIENTOS FUNCIONALES \
2.2. FASE DE DISEÑO \
#h(2em) 2.2.1. DISEÑO DE BASE DE DATOS \
#h(2em) 2.2.2. DISEÑO DE INTERFAZ DE USUARIO \
2.3. FASE DE DESARROLLO \
#h(2em) 2.3.1. ESTRUCTURA DEL REPOSITORIO \
#h(2em) 2.3.2. MÓDULO DE GESTIÓN DE LÍNEAS \
#h(2em) 2.3.3. MÓDULO DE MONITOREO DE RUTAS \
#h(2em) 2.3.4. MÓDULO DE GESTIÓN DE DESVÍOS \
#h(2em) 2.3.5. MÓDULO DE GESTIÓN DE TARIFAS \
#h(2em) 2.3.6. MÓDULO DE IDENTIFICACIÓN DE TRAYECTOS \
#h(2em) 2.3.7. DIAGRAMA DE DESPLIEGUE \
2.4. FASE DE PRUEBAS
]

#v(1em)

#align(center)[*CAPÍTULO III* \ *PRUEBAS DE CALIDAD*]

#v(0.5em)

#block(inset: (left: 0pt))[
3.1. DEFINICIÓN DE CASOS DE PRUEBAS DE CALIDAD \
3.2. PRUEBAS DE CALIDAD AUTOMATIZADAS \
3.3. PRUEBAS CON USUARIOS \
3.4. REPORTE DE RESULTADOS DE PRUEBAS
]

#v(1em)

#align(center)[*CAPÍTULO IV* \ *ESTIMACIÓN DE COSTOS*]

#v(0.5em)

#block(inset: (left: 0pt))[
4.1. COSTOS DE DESPLIEGUE \
4.2. COSTOS DE MANTENIMIENTO
]

#v(1em)

#align(center)[*CAPÍTULO V* \ *RESULTADOS Y DISCUSIÓN*]

#v(0.5em)

#block(inset: (left: 0pt))[
5.1. RESULTADOS \
5.2. CONCLUSIONES \
5.3. RECOMENDACIONES \
5.4. REFERENCIAS BIBLIOGRÁFICAS
]

= 9. CRONOGRAMA

El cronograma del proyecto se estructura en base a las fases del ciclo de vida del desarrollo de software (SDLC), integrando los objetivos específicos del sistema dentro de cada fase. En la Tabla 2, se señalan las actividades y tiempos estimados para cada fase.

#figure(
  table(
    columns: (1.2fr, 2.5fr, 1fr, 1fr, 1fr, 1fr, 1fr, 1fr),
    align: (left, left, center, center, center, center, center, center),
    stroke: 0.5pt,
    table.header(
      [*Etapa*], [*Actividad*], [*Octubre*], [*Noviembre*], [*Diciembre*], [*Enero*], [*Febrero*], [*Marzo*],
    ),
    [], [Elaboración del marco teórico], [X], [X], [], [], [], [],
    [*Análisis*], [Definición de requerimientos funcionales], [], [X], [], [], [], [],
    [], [Definición de requerimientos no funcionales], [], [X], [], [], [], [],
    [*Diseño*], [Diseño de la base de datos], [], [], [X], [], [], [],
    [], [Diseño de la interfaz de usuario], [], [], [X], [], [], [],
    [*Desarrollo*], [Desarrollo del módulo de gestión de líneas], [], [], [X], [], [], [],
    [], [Desarrollo del módulo de monitoreo de rutas], [], [], [X], [], [], [],
    [], [Desarrollo del módulo de gestión de desvíos], [], [], [], [X], [], [],
    [], [Desarrollo del módulo de gestión de tarifas], [], [], [], [X], [], [],
    [], [Desarrollo del módulo de identificación de trayectos], [], [], [], [X], [], [],
    [], [Despliegue del sistema], [], [], [], [X], [], [],
    [*Pruebas*], [Definición de casos de prueba], [], [], [], [], [X], [],
    [], [Pruebas con usuarios], [], [], [], [], [X], [],
    [], [Elaboración de reporte de resultados], [], [], [], [], [X], [],
    [], [Redacción de documento final], [], [], [], [], [], [X],
  ),
  caption: [Cronograma de elaboración del proyecto],
  supplement: [Tabla],
)

#align(center)[#text(style: "italic", size: 10pt)[Fuente: Elaboración propia, 2026.]]

#v(1em)

= 10. REFERENCIAS BIBLIOGRÁFICAS

#set par(first-line-indent: 0pt, hanging-indent: 1.27cm, justify: true)

Aberdour, M. (2007). Achieving Quality in Open-Source Software. _IEEE Software_. Recuperado de https://doi.org/10.1109/MS.2007.2

Bast, H., Delling, D., Goldberg, A., Müller-Hannemann, M., Pajor, T., Sanders, P., Wagner, D., & Werneck, R. F. (2016). Route Planning in Transportation Networks. En L. Kliemann & P. Sanders (Eds.), _Algorithm Engineering: Selected Results and Surveys_ (pp. 19--80). Springer International Publishing. Recuperado de https://doi.org/10.1007/978-3-319-49487-6_2

Bernal Torres, C. A. (2016). _Metodología de la Investigación_ (Cuarta edición). Pearson.

Burgos, C. (2019, junio 7). El negocio del transporte público en Cochabamba. _Los Tiempos_. Recuperado de https://www.lostiempos.com/especial-multimedia/20190610/negocio-del-transporte-publico-cochabamba

Cabrera, J. (2017). _La planificación del territorio, la vialidad, el transporte y la movilidad en Cochabamba_ (pp. 4--13).

Cabrera, J. E. (Ed.). (2023). _Lo urbano y la urbanización en Bolivia: Problemáticas y desafíos_. Instituto Boliviano de Urbanismo. Recuperado de https://www.undp.org/sites/g/files/zskgke326/files/2023-06/desarrollo_urbano_celeste_plomizo_baja.pdf

Cabrera, J. E., & Moyano, B. D. M. (2022). Paratránsito y expansión urbana: El transporte informal como dispositivo de urbanización. _urbe. Revista Brasileira de Gestão Urbana_, 14, e20210408. Recuperado de https://doi.org/https://doi.org/10.1590/2175-3369.014.e20210408

Cabrera, J., Orellana, P., & Perez, A. (2018). _Entre el transporte informal y la ciudad inteligente: La aplicación móvil Llajta Rutas Metropolitana_ (pp. 167--192).

Fitzgerald. (2006). The Transformation of Open Source Software. _MIS Quarterly_. Recuperado de https://doi.org/10.2307/25148740

Ghezzi, A., Gabelloni, D., Martini, A., & Natalicchio, A. (2017). Crowdsourcing: A Review and Suggestions for Future Research. _International Journal of Management Reviews_. Recuperado de: https://doi.org/10.1111/ijmr.12135

Google Play. (2023, diciembre 14). _Trufi---Apps en Google Play_. Recuperado de: https://play.google.com/store/apps/details?id=app.trufi.navigator

Hernández Sampieri, R., Fernández Collado, C., & Del Pilar Baptista, M. (2014). _Metodología de la Investigación_ (6ta edición). Mc Graw Hill Education.

Hirth, M., Hoßfeld, T., & Tran-Gia, P. (2013). Analyzing costs and accuracy of validation mechanisms for crowdsourcing platforms. _Mathematical and Computer Modelling, Information System Security and Performance Modeling and Simulation for Future Mobile Networks_, 57(11), 2918--2932. Recuperado de https://doi.org/10.1016/j.mcm.2012.01.006

Holguin, L., Ochoa-Zezzatti, A., Larios, V. M., Cossio, E., Maciel, R., & Rivera, G. (2019). Small steps towards a smart city: Mobile application that provides options for the use of public transport in Juarez City. _2019 IEEE International Smart Cities Conference (ISC2)_, 100--105. Recuperado de https://doi.org/10.1109/ISC246665.2019.9071728

Hossain, M., & Kauranen, I. (2015). Crowdsourcing: A comprehensive literature review. _Strategic Outsourcing: An International Journal_. Recuperado de https://doi.org/10.1108/SO-12-2014-0029

Hou, X. (2021). _Map matching algorithms for intelligent transportation system_ [Nanyang Technological University]. Recuperado de https://doi.org/10.32657/10356/148923

Hou, X., Luo, L., Cai, W., & Hanai, M. (2018). Fast Online Map Matching for Recovering Travelling Routes from Low-Sampling GPS Data. _2018 IEEE SmartWorld, Ubiquitous Intelligence & Computing, Advanced & Trusted Computing, Scalable Computing & Communications, Cloud & Big Data Computing, Internet of People and Smart City Innovation (SmartWorld/SCALCOM/UIC/ATC/CBDCom/IOP/SCI)_, 917--924. Recuperado de https://doi.org/10.1109/SmartWorld.2018.00165

Howe, J. (2006). _The Rise of Crowdsourcing_. (14).

Hung, N. Q. V., Thang, D. C., Tam, N. T., Weidlich, M., & Et., A. (2017). Answer validation for generic crowdsourcing tasks with minimal efforts. _The VLDB Journal_. Recuperado de https://doi.org/10.1007/s00778-017-0484-3

Instituto Nacional de Estadística INE. (2015). _Censo de Población y Vivienda 2012 Cochabamba_. Estado Plurinacional de Bolivia.

Instituto Nacional de Estadística INE. (2024). _Censo de Población y Vivienda 2024_.

Kittur, A., Smus, B., Khamkar, S., & Kraut, R. E. (2011). _CrowdForge: Crowdsourcing Complex Work_.

Kleemann, F., Voß, G. G., & Rieder, K. (2008). Un(der)paid Innovators: The Commercial Utilization of Consumer Work through Crowdsourcing. _Innovation Studies, Science, Technology & Innovation Studies_, 4(1).

Kong, X., Liu, X., Jedari, B., Li, M., & Et., A. (2019). Mobile Crowdsourcing in Smart Cities: Technologies, Applications, and Future Challenges. _IEEE Internet of Things Journal_. Recuperado de https://doi.org/10.1109/JIOT.2019.2921879

Kubička, M., Cela, A., Moulin, P., Mounier, H., & Niculescu, S. I. (2015). Dataset for testing and training of map-matching algorithms. _2015 IEEE Intelligent Vehicles Symposium (IV)_, 1088--1093. Recuperado de https://doi.org/10.1109/IVS.2015.7225829

Liu, Y., Ge, Q., Luo, W., Huang, Q., Zou, L., Wang, H., Li, X., & Liu, C. (2024). GraphMM: Graph-Based Vehicular Map Matching by Leveraging Trajectory and Road Correlations. _IEEE Transactions on Knowledge and Data Engineering_, 36(1), 184--198. Recuperado de https://doi.org/10.1109/TKDE.2023.3287739

Luca, G. D. (2024). _FastAPI cookbook: Develop high-performance APIs and web applications with Python_. Packt Publishing.

Mejia, I., & Daga, N. (2014). _Poder y superposición de las líneas y rutas de transporte público en el municipio de Cochabamba_. FACH - Universidad Mayor de San Simón.

Nielsen, J. (1993). _Usability engineering_. AP Professional.

Obe, R. O., & Hsu, L. S. (2017). _PostgreSQL: Up and running: a practical guide to the advanced open source database_ (Third edition). O'Reilly Media, Inc.

Panta, Y. R., Azam, S., Shanmugam, B., Yeo, K. C., & Et., A. (2019). Improving Accessibility for Mobility Impaired People in Smart City using Crowdsourcing. _2019 Cybersecurity and Cyberforensics Conference (CCC)_. Recuperado de https://doi.org/10.1109/CCC.2019.00-10

Phuttharak, J., & Loke, S. W. (2019). A Review of Mobile Crowdsourcing Architectures and Challenges: Toward Crowd-Empowered Internet-of-Things. _IEEE Access_, 7, 304--324. Recuperado de https://doi.org/10.1109/ACCESS.2018.2885353

Raymond, E. S. (2001). _The cathedral and the bazaar: Musings on Linux and open source by an accidental revolutionary_. O'Reilly & Associates, Inc. Recuperado de http://choicereviews.org/review/10.5860/CHOICE.39-2841

Sakhniuk, M. (with Boduch, A., & Derks, R.). (2024). _React and React Native: Build cross-platform JavaScript and TypeScript apps for the web, desktop, and mobile_ (1a ed.). Packt Publishing Limited.

Schweitzer, F. M., Buchinger, W., Gassmann, O., & Obrist, M. (2012). Crowdsourcing: Leveraging Innovation through Online Idea Competitions. _Research-Technology Management_. Recuperado de https://doi.org/10.5437/08956308X5503055

Sobota, B., Szabo, Cs., & Perhac, J. (2008). Using path-finding algorithms of graph theory for route-searching in geographical information systems. _2008 6th International Symposium on Intelligent Systems and Informatics_, 1--6. Recuperado de https://doi.org/10.1109/SISY.2008.4664953

Trufi Association. (2025). _Trufi App -- Aplicación móvil para el transporte público en Cochabamba, Bolivia_ [Home page]. Trufi App. Recuperado de https://trufi.app/
