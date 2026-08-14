Autoría de Luis Fontecilla

# Alcance y requisitos iniciales

## 1. Propósito

Este documento define el límite funcional de la primera versión del sistema de optimización de rutas para camiones recolectores. Los requisitos son preliminares y deben validarse con usuarios, datos reales y restricciones del sistema de tickets existente.

## 2. Actores

- Administrador: mantiene usuarios, camiones, parámetros y configuraciones.
- Despachador: revisa tickets, crea jornadas, solicita rutas y controla la operación.
- Conductor: consulta la ruta vigente y registra el resultado de cada visita.
- Sistema de tickets: entrega los requerimientos y recibe, si se acuerda, actualizaciones de estado.
- Proveedor cartográfico: entrega geocodificación, matriz de tiempos o direcciones de conducción.

## 3. Alcance del MVP

### 3.1 Incluido

- Autenticación y autorización por roles.
- Consulta o importación de tickets pendientes.
- Validación de los datos mínimos de una solicitud.
- Conversión de direcciones a coordenadas y corrección manual controlada.
- Registro de vehículos, capacidad, disponibilidad y conductor asignado.
- Creación de una jornada o ruta a partir de tickets seleccionados.
- Cálculo de una secuencia de paradas considerando distancia y restricciones básicas.
- Visualización de la ruta y de sus paradas en un mapa.
- Cambio de estado de una parada y propuesta de reordenamiento.
- Registro de llegada, resultado, incidencia y finalización.
- Historial y métricas operacionales básicas.
- Despliegue seguro en un VPS Debian y respaldo de la base de datos.

### 3.2 Excluido de la primera versión

- Sensores IoT en contenedores.
- Predicción con inteligencia artificial.
- Navegación giro a giro propia.
- Facturación y gestión contable.
- Mantenimiento mecánico de la flota.
- Optimización avanzada de múltiples depósitos o flotas de gran escala.
- Aplicaciones móviles nativas independientes.

## 4. Requisitos funcionales

### Integración y solicitudes

- RF-01. El sistema debe obtener tickets pendientes desde la interfaz de integración definida.
- RF-02. El sistema debe evitar la duplicación de un ticket mediante un identificador externo único.
- RF-03. El sistema debe validar dirección, contacto, tipo de residuo, prioridad y ventana horaria cuando estos datos existan.
- RF-04. El sistema debe registrar los errores de integración y permitir su revisión.
- RF-05. El sistema debe mantener trazabilidad entre el ticket externo y la parada creada.

### Georreferenciación

- RF-06. El sistema debe geocodificar direcciones mediante el proveedor cartográfico configurado.
- RF-07. El despachador debe poder confirmar o corregir la posición de un punto antes de incluirlo en una ruta.
- RF-08. El sistema debe conservar la dirección original, la dirección normalizada y las coordenadas utilizadas.

### Planificación y optimización

- RF-09. El despachador debe poder seleccionar tickets y vehículos para una jornada.
- RF-10. El sistema debe generar una propuesta de ruta con orden de visita, distancia y duración estimadas.
- RF-11. El optimizador debe considerar como mínimo disponibilidad, punto de inicio, capacidad, prioridad y ventana horaria cuando sean aplicables.
- RF-12. El sistema debe informar las solicitudes que no puedan ser asignadas y su motivo.
- RF-13. El despachador debe poder aceptar la propuesta o efectuar ajustes manuales con trazabilidad.
- RF-14. El sistema debe permitir recalcular las paradas pendientes sin modificar el historial de las ya completadas.

### Ejecución

- RF-15. El conductor debe visualizar la secuencia vigente y el detalle de la siguiente parada.
- RF-16. El conductor debe registrar llegada, recolección completada, punto no disponible o incidencia.
- RF-17. El sistema debe registrar fecha, hora, usuario y ubicación disponible para cada cambio operacional.
- RF-18. Un cambio relevante debe notificarse al conductor y quedar registrado en el historial de la ruta.

### Administración y resultados

- RF-19. El administrador debe gestionar usuarios, roles, vehículos y parámetros operacionales.
- RF-20. El sistema debe mostrar el estado de las rutas activas y las solicitudes pendientes.
- RF-21. El sistema debe generar indicadores de distancia, duración, cumplimiento, incidencias y tiempo improductivo.
- RF-22. El sistema debe permitir exportar resultados de una jornada en un formato tabular.

## 5. Requisitos no funcionales

- RNF-01. Toda comunicación pública debe utilizar HTTPS.
- RNF-02. Las contraseñas deben almacenarse mediante un algoritmo de derivación seguro; nunca en texto plano.
- RNF-03. Los permisos deben aplicarse en el servidor y no depender solamente de la interfaz.
- RNF-04. Las claves de APIs y credenciales deben mantenerse fuera del repositorio.
- RNF-05. Los eventos críticos deben quedar en registros de auditoría.
- RNF-06. La base de datos debe contar con respaldos automatizados y una prueba periódica de restauración.
- RNF-07. El sistema debe tolerar de forma controlada la indisponibilidad temporal del proveedor de mapas.
- RNF-08. La interfaz del conductor debe ser utilizable en una pantalla móvil y bajo conectividad inestable.
- RNF-09. Las operaciones habituales de consulta deben responder en un tiempo objetivo que se definirá después de medir el entorno real.
- RNF-10. El módulo de optimización debe ser reemplazable y ejecutable con conjuntos de prueba reproducibles.
- RNF-11. Fechas y horas deben almacenarse con zona horaria explícita y presentarse en la zona operacional.
- RNF-12. La información personal debe limitarse a lo necesario y contar con una política de retención.

## 6. Reglas de negocio preliminares

- Un ticket no puede originar más de una parada activa para el mismo servicio.
- Una parada completada no puede volver al estado pendiente sin una corrección autorizada y auditada.
- Solo las paradas con ubicación validada pueden ser optimizadas.
- El recalculo afecta únicamente a las paradas pendientes de la ruta.
- La ruta publicada al conductor mantiene una versión; cada cambio genera una versión nueva.
- Una propuesta inviable debe mostrar el motivo y no descartarse silenciosamente.
- La edición manual prevalece para la operación inmediata, pero debe quedar registrada para evaluar el algoritmo.

## 7. Criterios de aceptación del MVP

- Se puede completar una jornada de demostración desde la importación del ticket hasta el cierre de la visita.
- La misma entrada y configuración produce resultados reproducibles.
- El sistema distingue entre ruta propuesta, ruta aceptada y ruta ejecutada.
- Las solicitudes no asignadas y las incidencias permanecen visibles.
- La evaluación puede comparar una planificación de referencia con la propuesta por el sistema.

## 8. Supuestos que requieren validación

- El sistema de tickets dispone de una API o mecanismo de exportación autorizado.
- Las direcciones poseen una calidad suficiente para ser geocodificadas.
- La operación puede proporcionar capacidad de los camiones y restricciones horarias.
- Existe un conjunto de rutas históricas o escenarios representativos para construir una línea base.
- La conectividad móvil permite al menos sincronización eventual durante la jornada.
