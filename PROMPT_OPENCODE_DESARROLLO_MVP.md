Autoría de Luis Fontecilla

# Prompt para OpenCode: módulo inicial de planificación y optimización de rutas

Actúa como ingeniero de software senior responsable de implementar una primera porción funcional del proyecto de título "Sistema web para la optimización dinámica de rutas de camiones recolectores".

Debes trabajar de forma autónoma, conservar la aplicación existente y entregar una vertical funcional verificable. No intentes desarrollar todo el proyecto de título en una sola iteración.

## 1. Rutas de trabajo

Repositorio que debes modificar:

`C:\Users\fonte\Desktop\ticketflow-community-main`

Documentación de requisitos que debes leer antes de modificar código:

`C:\Users\fonte\Desktop\Proyecto Titulo\README.md`

`C:\Users\fonte\Desktop\Proyecto Titulo\docs\alcance-y-requisitos.md`

`C:\Users\fonte\Desktop\Proyecto Titulo\docs\arquitectura-inicial.md`

`C:\Users\fonte\Desktop\Proyecto Titulo\docs\modelo-datos-conceptual.md`

`C:\Users\fonte\Desktop\Proyecto Titulo\docs\plan-de-validacion.md`

No modifiques los documentos del proyecto de título. Todos los cambios de software deben quedar dentro de `ticketflow-community-main`.

## 2. Estado inicial verificado

La aplicación existente utiliza Flask 2.2, Flask-SQLAlchemy, Flask-Login, Jinja y CoreUI. SQLite es la base predeterminada y existe configuración preliminar para una base externa. Los modelos principales actuales son `Cliente`, `Ticket`, `Comentario`, `TicketSoporte`, `Users` y entidades de gobierno TI.

El modelo `Ticket` ya conserva cliente, número, asunto, descripción, estado, prioridad, técnico y fechas. El modelo `Cliente` ya posee dirección y ciudad. No existen todavía coordenadas, solicitudes de recolección, vehículos, jornadas, versiones de ruta, paradas ni eventos operacionales.

Los roles actuales son `Administrador`, `Tecnico`, `Usuario` y `Cliente`. La interfaz es renderizada en el servidor con Jinja; no es una aplicación SPA. Respeta esa arquitectura y el diseño CoreUI existente.

Antes de editar:

1. Revisa el estado de Git y no descartes cambios existentes.
2. Ejecuta `python tests/smoke_test.py` y registra el resultado inicial.
3. Inspecciona completamente los modelos, rutas, plantillas, configuración y pruebas relevantes.
4. Si existe `AGENTS.md`, léelo y respeta sus instrucciones.
5. Presenta un plan breve y continúa con la implementación sin esperar confirmación, salvo que exista un bloqueo real.

## 3. Objetivo de esta iteración

Implementa un módulo separado de recolección que permita completar este flujo:

1. Un administrador o despachador selecciona tickets existentes que representan solicitudes de recolección.
2. Cada ticket se complementa con ubicación validada, demanda estimada, duración de servicio, disponibilidad y ventana horaria opcional.
3. Se registran uno o más camiones con capacidad y punto de inicio.
4. El sistema obtiene una matriz de tiempos y distancias mediante un adaptador cartográfico.
5. El sistema calcula una línea base y una solución optimizada localmente.
6. El despachador revisa los resultados, las paradas no asignadas y la geometría de la ruta en un mapa.
7. El despachador publica una versión inmutable de la ruta.
8. El conductor consulta su ruta vigente y registra llegada, recolección completada, punto no disponible o incidencia.
9. El sistema puede recalcular únicamente las paradas pendientes sin alterar las ya completadas.
10. El sistema muestra métricas que comparan la línea base con la ruta optimizada.

La entrega debe funcionar de extremo a extremo con datos de prueba, incluso cuando no exista una clave real del proveedor cartográfico.

## 4. Decisión cartográfica obligatoria

No inventes ni afirmes que existe una única API pública chilena gratuita capaz de entregar mapa base, geocodificación, matriz vial, rutas y optimización. Usa una arquitectura híbrida y desacoplada.

### 4.1 Mapa web

Utiliza Leaflet en la interfaz. Integra sus archivos de forma versionada y reproducible. Evita depender de una versión no fijada desde una URL externa.

Para desarrollo y demostración de bajo volumen puede utilizarse la capa raster estándar de OpenStreetMap:

`https://tile.openstreetmap.org/{z}/{x}/{y}.png`

Debes cumplir la política oficial de uso:

`https://operations.osmfoundation.org/policies/tiles/`

La atribución `OpenStreetMap contributors` debe permanecer visible. No implementes descarga masiva, precarga de ciudades, modo sin conexión ni un proxy que elimine encabezados o ignore las cabeceras de caché. La URL de teselas debe ser configurable para permitir cambiar de proveedor.

### 4.2 Capa oficial chilena

Agrega como capa opcional y desactivable los límites administrativos publicados por el Ministerio de Obras Públicas mediante ArcGIS REST:

`https://rest-sit.mop.gob.cl/arcgis/rest/services/MAPA_BASE/LIMITES/MapServer`

La capa debe aparecer con el nombre `Límites administrativos de Chile`. Utiliza una integración compatible con Leaflet y fija la versión de la dependencia necesaria. Su falla no debe impedir que el mapa principal funcione.

Esta capa oficial chilena es complementaria. No debe utilizarse para calcular rutas por calles.

### 4.3 Geocodificación, matriz y geometría vial

Implementa un adaptador `MapProvider` y una implementación `OpenRouteServiceProvider` para:

- Geocodificación directa y reversa.
- Matriz de duración y distancia.
- Geometría GeoJSON de una ruta ya ordenada.
- Perfil configurable, con `driving-hgv` como opción preferente para camiones y `driving-car` como alternativa de prueba.

Documentación oficial de los endpoints:

`https://openrouteservice.org/dev/`

Planes y límites del servicio:

`https://account.heigit.org/info/plans`

La clave debe enviarse solamente desde el servidor mediante el encabezado de autorización. Nunca la incluyas en HTML, JavaScript, registros, repositorio ni respuestas al navegador.

Variables de entorno mínimas:

- `ORS_API_KEY`
- `ORS_BASE_URL`
- `ORS_GEOCODE_BASE_URL`
- `ORS_PROFILE`
- `MAP_TILE_URL`
- `MAP_TILE_ATTRIBUTION`
- `CHILE_LIMITS_SERVICE_URL`
- `MAP_HTTP_TIMEOUT_SECONDS`

Define valores públicos y seguros en `.env.example`, pero deja vacía cualquier clave secreta.

Implementa timeout, reintentos limitados solo para errores transitorios, mensajes de error controlados y caché de geocodificación y matrices. La caché debe usar una clave estable derivada del proveedor, perfil, versión y entrada normalizada.

No uses la instancia pública de Nominatim como dependencia automática. Su política limita el uso, prohíbe ciertos patrones y no es apropiada como geocodificador genérico integrado sin una decisión explícita.

### 4.4 Operación sin clave externa

La aplicación debe iniciar aunque `ORS_API_KEY` no esté definida. En ese caso:

- Muestra un estado de configuración claro a los administradores.
- Deshabilita las llamadas cartográficas reales sin provocar errores 500.
- Permite ingresar y confirmar coordenadas manualmente.
- Permite ejecutar pruebas y demostraciones con un `FakeMapProvider` y matrices estáticas.
- No utilices distancia Haversine silenciosamente como si fuera distancia vial. Si se ofrece como modo demostrativo, debe quedar etiquetado como estimación no vial.

## 5. Optimización local obligatoria

La optimización debe ejecutarse en el backend del proyecto. No delegues la contribución principal al endpoint de optimización de openrouteservice.

Utiliza Google OR-Tools para implementar un problema de ruteo de vehículos. Documentación de referencia:

`https://developers.google.com/optimization/routing`

`https://developers.google.com/optimization/routing/vrptw`

El optimizador debe consumir la matriz entregada por `MapProvider` y no llamar directamente a APIs externas.

Implementa una interfaz `RouteOptimizer` con al menos estas dos estrategias:

1. `NearestNeighborBaseline`: línea base determinista mediante vecino más cercano, con desempate estable. Puede aplicar una mejora 2-opt documentada cuando no viole restricciones.
2. `ORToolsVRPOptimizer`: solución con uno o más vehículos, capacidad, duración de servicio, ventanas horarias opcionales y penalización explícita por una parada que no pueda asignarse.

Requisitos del algoritmo:

- Cada parada activa debe aparecer exactamente una vez en una ruta o en la lista de no asignadas.
- La carga acumulada no puede exceder la capacidad del vehículo.
- Las ventanas horarias deben respetarse cuando estén definidas.
- El punto inicial y final debe provenir de la configuración de cada vehículo o jornada.
- El tiempo de servicio se suma al tiempo de viaje.
- Las paradas completadas quedan fijadas y no participan en el recalculo.
- Una parada no disponible puede omitirse temporalmente sin marcarse como completada.
- La búsqueda debe tener un límite de tiempo configurable.
- Registra estado del solver, duración del cálculo, parámetros, valor objetivo y versión de la estrategia.
- No prometas optimalidad absoluta. OR-Tools puede entregar una solución factible o la mejor solución encontrada dentro del límite.
- Si el problema es inviable, devuelve una respuesta explicable y conserva la última ruta publicada.
- El resultado debe ser determinista para los mismos datos, parámetros y límite cuando la biblioteca lo permita.

La función objetivo inicial debe minimizar una combinación documentada de:

- Tiempo o distancia total.
- Penalización por parada no atendida.
- Penalización por incumplimiento de prioridad.
- Penalización por atraso, cuando corresponda.

Conserva las ponderaciones como parámetros del sistema. No inventes valores monetarios ni porcentajes de ahorro.

## 6. Diseño del módulo Flask

Crea un módulo independiente, por ejemplo:

`apps/recoleccion/`

Debe contener, según corresponda:

- `__init__.py` para el blueprint.
- `models.py` para las entidades de recolección.
- `routes.py` para páginas y endpoints.
- `forms.py` para validación de formularios.
- `services/` para mapas, optimización, planificación y métricas.
- `templates/recoleccion/` para las nuevas vistas.
- JavaScript y CSS propios dentro de `apps/static/assets/`.

Registra el blueprint desde la fábrica de aplicación. No agregues más responsabilidades al archivo monolítico `apps/home/routes.py` salvo enlaces o cambios mínimos de navegación.

Separa estrictamente:

- Vistas y controladores HTTP.
- Reglas de negocio.
- Acceso a proveedores cartográficos.
- Construcción del problema de optimización.
- Persistencia de resultados y eventos.

No realices llamadas HTTP externas desde modelos SQLAlchemy ni desde plantillas.

## 7. Modelo de datos mínimo

Implementa las entidades necesarias usando nombres consistentes en español o inglés, pero no mezcles ambos criterios sin una razón. Como mínimo deben quedar representados estos conceptos:

### SolicitudRecoleccion

- Identificador propio.
- `ticket_id` único y obligatorio como clave foránea a `Ticket`.
- Punto de recolección.
- Estado de disponibilidad.
- Demanda estimada y unidad.
- Duración estimada de servicio.
- Inicio y término opcionales de ventana horaria.
- Prioridad normalizada.
- Estado operacional.
- Fechas de creación y actualización.

### PuntoRecoleccion

- Dirección original tomada desde el cliente o ticket.
- Dirección normalizada.
- Comuna, región y referencia.
- Latitud y longitud.
- Proveedor y precisión de geocodificación.
- Estado de validación.
- Fecha y usuario que confirmó la ubicación.

### Vehiculo

- Identificación única, patente y nombre visible.
- Capacidad y unidad.
- Estado de disponibilidad.
- Perfil de ruteo.
- Punto inicial y final.
- Conductor asignado opcional.

### Jornada y Ruta

- Fecha operacional y estado.
- Vehículo y conductor.
- Relación con las versiones publicadas.
- Versión vigente identificable.

### RutaVersion y ParadaRuta

- Número de versión y tipo: línea base, propuesta o publicada.
- Estrategia y parámetros de optimización.
- Secuencia de paradas.
- Distancia, duración, carga y tiempos estimados.
- Geometría GeoJSON validada.
- Lista y motivo de solicitudes no asignadas.
- Inmutabilidad después de publicar.

### EventoRuta

- Ruta, parada, actor, tipo de evento y fecha en UTC.
- Identificador idempotente.
- Ubicación opcional informada por el conductor.
- Observación e incidencia.
- Datos anteriores y nuevos suficientes para auditoría.

### EjecucionOptimizacion o equivalente

- Hash de entrada.
- Estrategia y versión.
- Parámetros.
- Estado del solver.
- Duración.
- Objetivo y advertencias.
- Resultado o referencia a la versión producida.

Usa fechas con zona horaria explícita en las entidades nuevas. No almacenes la geometría o respuestas externas sin validar tamaño y formato. Evita guardar la clave de la API.

La aplicación debe continuar funcionando con SQLite para desarrollo y pruebas. Agrega soporte real para PostgreSQL en producción y documenta la configuración. Si PostGIS se incorpora en esta fase, mantén una ruta de pruebas compatible con SQLite; si no es necesario para la vertical, documenta PostGIS como evolución y conserva latitud y longitud con validación estricta.

Utiliza Flask-Migrate y entrega una migración revisable para las tablas nuevas. No dependas exclusivamente de `db.create_all` para un despliegue productivo.

## 8. Roles y autorización

Agrega los roles `Despachador` y `Conductor` sin romper los existentes.

Permisos mínimos:

- `Administrador`: acceso total al módulo.
- `Despachador`: gestionar solicitudes de recolección, vehículos, jornadas, optimización y publicación.
- `Conductor`: consultar únicamente su ruta vigente y registrar eventos permitidos.
- `Tecnico`, `Usuario` y `Cliente`: no reciben acceso al módulo salvo una decisión explícita documentada.

Aplica la autorización en el servidor. No confíes en ocultar botones. Un conductor no debe poder consultar ni modificar rutas asignadas a otra persona mediante cambios de URL.

Protege las operaciones de escritura contra CSRF de forma compatible con la aplicación existente. No introduzcas una protección global que rompa silenciosamente todos los formularios actuales; actualiza los formularios afectados o limita el cambio de manera explícita y documentada.

## 9. Interfaz web requerida

Mantén CoreUI y Jinja. No introduzcas React, Vue ni otro frontend separado.

Agrega navegación y vistas para:

1. Solicitudes de recolección: listado, filtros, estado geográfico y edición del complemento de recolección.
2. Vehículos: listado, creación y edición.
3. Jornadas: selección de solicitudes y vehículos.
4. Planificación: resultados de línea base y optimización, métricas, advertencias y paradas no asignadas.
5. Mapa de ruta: marcadores numerados, depósito, polilínea y selector de capas.
6. Ruta del conductor: próxima parada, secuencia pendiente y acciones operacionales.
7. Historial: versiones y eventos de una ruta.

Requisitos de experiencia:

- Diseño adaptable a pantallas móviles.
- Estados expresados mediante texto y color; no dependas solo del color.
- Formularios con errores asociados a cada campo.
- Confirmación antes de publicar o recalcular una ruta.
- Mensajes claros cuando falte configuración cartográfica.
- Ningún secreto en el código del navegador.
- No utilices emojis ni iconos decorativos como sustituto de etiquetas.

## 10. Endpoints internos

Expone endpoints JSON versionados solamente cuando aporten al flujo. Como referencia:

- `POST /api/v1/recoleccion/geocodificar`
- `POST /api/v1/recoleccion/jornadas/<id>/optimizar`
- `POST /api/v1/recoleccion/rutas/<id>/publicar`
- `GET /api/v1/recoleccion/rutas/<id>`
- `POST /api/v1/recoleccion/paradas/<id>/eventos`

No copies ciegamente estos nombres si chocan con la convención existente. Documenta el contrato final, códigos HTTP, validaciones y respuestas de error. Las operaciones repetibles deben utilizar identificadores idempotentes.

## 11. Caché y resiliencia

Implementa una caché persistente mínima para geocodificación y matrices, respetando los términos del proveedor. La clave debe considerar el perfil de conducción y el orden normalizado de las coordenadas.

Requisitos:

- Timeout explícito para cada llamada externa.
- Reintentos con espera incremental solo para estados transitorios y nunca para errores de autenticación o validación.
- Límite de tamaño de respuesta.
- Logs sin direcciones personales completas cuando no sean necesarias.
- Estado visible de proveedor no configurado, cuota agotada e indisponibilidad.
- Conservación de la última versión publicada cuando falle un recalculo.
- Proveedores inyectables para que las pruebas no utilicen red.

## 12. Métricas

Calcula y muestra, como mínimo:

- Distancia y duración de la línea base.
- Distancia y duración de la propuesta optimizada.
- Diferencia absoluta y porcentual, sin presentarla como ahorro real si solo usa estimaciones.
- Cantidad de servicios asignados y no asignados.
- Utilización de capacidad por vehículo.
- Tiempo de ejecución del optimizador.
- Cantidad de recalculos y versiones publicadas.

Distingue claramente valores planificados de valores ejecutados. No fabriques datos de combustible, dinero ni emisiones.

## 13. Pruebas obligatorias

Agrega una suite automatizada que no dependa de internet ni de una clave real.

Incluye como mínimo:

- Pruebas unitarias de `NearestNeighborBaseline`.
- Pruebas unitarias de `ORToolsVRPOptimizer`.
- Caso de capacidad insuficiente con parada no asignada y motivo.
- Caso con ventanas horarias.
- Caso de recalculo que mantiene fijas las paradas completadas.
- Caso determinista con matriz estática.
- Pruebas del adaptador cartográfico con respuestas HTTP simuladas.
- Pruebas de timeout, error de autenticación y cuota agotada.
- Pruebas de autorización para administrador, despachador y conductor.
- Prueba de idempotencia de eventos.
- Prueba de publicación inmutable y creación de una nueva versión.
- Prueba de extremo a extremo: ticket, solicitud, jornada, optimización, publicación y evento del conductor.
- El `tests/smoke_test.py` existente debe continuar pasando.

Usa coordenadas y matrices sintéticas para las pruebas. No dependas de direcciones personales reales.

## 14. Datos demostrativos

Agrega un comando CLI idempotente, por ejemplo `flask seed-routing-demo`, que cree:

- Un administrador, un despachador y un conductor de demostración cuando no existan.
- Un vehículo.
- Entre seis y diez tickets sintéticos de recolección.
- Coordenadas explícitas dentro de la Región Metropolitana.
- Demandas y ventanas horarias simples.
- Una jornada preparada para optimizar.

No incluyas contraseñas productivas ni secretos. Las credenciales de demostración deben definirse por argumento o variable de entorno y documentarse como no aptas para producción.

## 15. PostgreSQL y despliegue local

Extiende Docker Compose para ofrecer un perfil de desarrollo con:

- Aplicación TicketFlow.
- PostgreSQL; utiliza una imagen PostGIS solamente si realmente se usa una función geográfica en esta iteración.
- Volumen persistente.
- Healthcheck.
- Variables de entorno sin secretos reales.

Mantén una forma simple de ejecutar la aplicación con SQLite. Documenta ambas rutas.

No despliegues al VPS ni cambies infraestructura externa en esta iteración. Entrega documentación para un despliegue posterior en Debian con Gunicorn, proxy inverso, HTTPS, respaldos y migraciones.

## 16. Documentación a entregar dentro de TicketFlow

Actualiza `README.md` y agrega documentación específica, por ejemplo:

- `docs/recoleccion-arquitectura.md`
- `docs/recoleccion-configuracion-mapas.md`
- `docs/recoleccion-optimizacion.md`
- `docs/recoleccion-pruebas.md`

La documentación debe explicar:

- Arquitectura y responsabilidades.
- Modelo de datos.
- Variables de entorno.
- Obtención y protección de la clave de openrouteservice.
- Límites del plan gratuito y comportamiento ante cuota agotada.
- Política de atribución y uso de OpenStreetMap.
- Diferencia entre la capa oficial chilena y el servicio de ruteo.
- Función objetivo, restricciones y significado de una solución no óptima.
- Cómo ejecutar migraciones, datos demostrativos y pruebas.
- Limitaciones y trabajo pendiente.

Incluye un registro de decisiones técnicas breve. No presentes decisiones provisionales como requisitos confirmados.

## 17. Fuera de alcance

No implementes en esta iteración:

- Sensores IoT.
- Predicción mediante inteligencia artificial.
- Telemetría continua del camión.
- Aplicación móvil nativa.
- Navegación giro a giro propia.
- Facturación.
- Despliegue real al VPS.
- Optimización continua de una flota de gran escala.
- Integración con datos personales o productivos reales.

## 18. Criterios de aceptación

La iteración se considera completa únicamente si:

1. TicketFlow conserva sus funciones actuales y el smoke test original pasa.
2. Un ticket puede transformarse una sola vez en solicitud de recolección.
3. Una ubicación puede geocodificarse con el adaptador o ingresarse manualmente.
4. El sistema funciona sin exponer la clave cartográfica al navegador.
5. Se puede crear un vehículo y una jornada con datos sintéticos.
6. La línea base y OR-Tools producen resultados reproducibles con una matriz estática.
7. Las restricciones de capacidad y ventanas horarias poseen pruebas.
8. Las paradas no asignadas muestran una causa.
9. La propuesta y sus métricas se visualizan en el mapa.
10. Una ruta publicada queda inmutable y el conductor solo ve su asignación.
11. Los eventos operacionales son auditables e idempotentes.
12. Un recalculo conserva las paradas completadas y genera una versión nueva.
13. La aplicación mantiene soporte de SQLite y documenta PostgreSQL.
14. No se agregan secretos, bases de datos, informes generados ni archivos temporales al repositorio.
15. La documentación explica limitaciones, configuración y forma de prueba.

## 19. Control de calidad

Antes de finalizar:

1. Ejecuta todas las pruebas nuevas y el smoke test original.
2. Revisa migraciones, índices, restricciones únicas y claves foráneas.
3. Revisa que ninguna llamada de prueba use internet.
4. Busca claves, tokens, contraseñas o datos personales agregados accidentalmente.
5. Comprueba autorización modificando identificadores en las URLs de prueba.
6. Comprueba que el navegador no reciba `ORS_API_KEY`.
7. Revisa el comportamiento sin variables cartográficas configuradas.
8. Comprueba la atribución visible de OpenStreetMap.
9. Verifica la interfaz en resolución de escritorio y móvil.
10. Ejecuta `git diff --check` y revisa el diff completo.

No silencies pruebas fallidas, no elimines pruebas existentes y no sustituyas código correcto por ejemplos incompletos.

## 20. Formato del informe final

Al terminar, informa:

- Resumen de la vertical implementada.
- Archivos principales creados o modificados.
- Decisiones técnicas y supuestos.
- Esquema de migración.
- Servicios externos y variables necesarias.
- Algoritmos implementados y sus limitaciones.
- Comandos exactos para ejecutar la aplicación, migraciones, datos de demostración y pruebas.
- Resultados de cada prueba.
- Riesgos o trabajo pendiente.

Si una parte no pudo completarse, indícala de forma explícita con evidencia. No declares éxito si el flujo de extremo a extremo o las pruebas obligatorias no funcionan.
