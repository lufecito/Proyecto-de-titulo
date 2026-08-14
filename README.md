Autoría de Luis Fontecilla

# Optimización de rutas para camiones recolectores

Proyecto de título orientado al diseño de una plataforma web para planificar y ajustar rutas de camiones recolectores a partir de solicitudes de recolección, ubicación de los puntos, restricciones operacionales y estado de cada servicio.

## Estado del proyecto

El proyecto se encuentra en fase de definición. En esta etapa se documentan el problema, el alcance, los requisitos, la arquitectura inicial y el método de validación. Todavía no se ha iniciado la implementación.

## Problema

Una planificación estática puede enviar un camión a puntos que aún no están disponibles, producir recorridos innecesarios y aumentar los tiempos improductivos. El proyecto busca utilizar los requerimientos registrados en el sistema de tickets existente para proponer una secuencia de visitas más eficiente y permitir su actualización durante la operación.

## Objetivo general

Diseñar e implementar una plataforma web que apoye la planificación y optimización de rutas de recolección, integrando las solicitudes existentes, información geográfica y restricciones operacionales, con el fin de reducir distancia recorrida, tiempo improductivo y costo operacional.

## Alcance inicial

- Integración con el sistema de tickets ya desarrollado.
- Registro y normalización de direcciones y coordenadas de recolección.
- Administración de camiones, conductores, rutas y estados de servicio.
- Visualización cartográfica mediante una API de mapas.
- Generación de una ruta propuesta para un conjunto de tickets.
- Reordenamiento de paradas cuando cambie el estado de un punto.
- Interfaz web adaptable para administración y uso del conductor.
- Persistencia en una base de datos alojada en el servidor.
- Despliegue en un VPS con Debian.
- Registro de métricas para comparar la ruta planificada con la ejecutada.

Quedan fuera del MVP los sensores IoT, la predicción mediante inteligencia artificial, la telemetría avanzada y la optimización de múltiples depósitos. Estas capacidades se consideran extensiones futuras.

## Componentes previstos

- Sistema de tickets existente como fuente de solicitudes.
- Aplicación web para administración, despacho y conductor.
- Servicio de aplicación para reglas de negocio e integración.
- Módulo de optimización de rutas.
- API externa de mapas, geocodificación y cálculo de trayectos.
- Base de datos PostgreSQL con extensión PostGIS, sujeta a validación técnica.
- VPS Debian con proxy inverso, certificados TLS, respaldos y monitoreo.

## Documentación

- [Alcance y requisitos](docs/alcance-y-requisitos.md)
- [Arquitectura inicial](docs/arquitectura-inicial.md)
- [Modelo de datos conceptual](docs/modelo-datos-conceptual.md)
- [Plan de validación](docs/plan-de-validacion.md)
- [Decisiones pendientes](docs/decisiones-pendientes.md)
- Documento formal del proyecto: `Proyecto_de_Titulo_Optimizacion_Rutas.docx`

## Criterios de éxito preliminares

- El sistema importa o consulta tickets válidos sin duplicarlos.
- Cada parada utilizada por el optimizador posee coordenadas verificables.
- La ruta propuesta respeta capacidad, horarios, prioridad y disponibilidad cuando corresponda.
- El conductor puede consultar la secuencia vigente y registrar el resultado de una visita.
- El sistema conserva trazabilidad entre ticket, parada, ruta y resultado.
- La evaluación compara distancia, duración, cumplimiento y tiempo improductivo frente a una línea base.

## Principios de trabajo

- Documentar decisiones antes de comprometer una tecnología.
- Mantener el sistema de tickets como fuente de verdad de la solicitud mientras no se acuerde otra regla.
- Separar la lógica de optimización del proveedor de mapas.
- Evitar almacenar secretos en el repositorio.
- Diseñar respaldos, registros y seguridad desde la primera versión desplegable.
- Validar el aporte del optimizador con datos y escenarios reproducibles.

## Estructura prevista del repositorio

```text
.
|-- README.md
|-- docs/
|   |-- alcance-y-requisitos.md
|   |-- arquitectura-inicial.md
|   |-- modelo-datos-conceptual.md
|   |-- plan-de-validacion.md
|   `-- decisiones-pendientes.md
|-- src/                  Futuro código fuente
|-- tests/                Futuras pruebas
|-- deploy/               Futura configuración de despliegue
`-- scripts/              Futuras tareas operacionales
```

## Próximo hito

Confirmar con el profesor guía y el responsable del sistema de tickets los límites del MVP, el contrato de integración, el conjunto de datos disponible y las métricas que se utilizarán para demostrar la mejora.
