Autoría de Luis Fontecilla

# Arquitectura inicial

## 1. Objetivo

Definir una arquitectura de referencia para el MVP sin fijar prematuramente un framework ni un proveedor cartográfico. La solución debe poder desplegarse en un VPS Debian, integrarse con el sistema de tickets y mantener separada la lógica de optimización.

## 2. Vista lógica

### Cliente web

Interfaz adaptable para administrador, despachador y conductor. Consume la API del sistema y no accede directamente a la base de datos ni a las claves del proveedor de mapas.

### API de aplicación

Centraliza autenticación, permisos, reglas de negocio, validaciones, auditoría y exposición de datos a la interfaz. También coordina la integración con tickets, mapas y optimización.

### Adaptador del sistema de tickets

Encapsula el mecanismo real de integración. Debe permitir consultar o recibir tickets, transformar campos, aplicar idempotencia y registrar errores. Esta separación evita acoplar todo el sistema al contrato actual.

### Servicio cartográfico

Encapsula geocodificación, matriz de tiempos y, si corresponde, geometría de la ruta. La aplicación debe conservar una interfaz propia para poder cambiar de proveedor y controlar cuotas, errores y reintentos.

### Módulo de optimización

Recibe vehículos, depósitos, paradas, tiempos y restricciones en un formato interno. Devuelve una propuesta con secuencia, asignaciones, estimaciones y solicitudes no atendidas. No debe modificar directamente los datos operacionales.

### Base de datos

Almacena usuarios, tickets sincronizados, ubicaciones, vehículos, rutas, versiones, eventos e indicadores. PostgreSQL con PostGIS es una alternativa propuesta por su soporte transaccional y geográfico; debe confirmarse mediante una prueba técnica.

### Procesamiento en segundo plano

Ejecuta tareas que no deben bloquear una solicitud web, por ejemplo sincronización de tickets, geocodificación masiva, cálculo de matrices, optimización y generación de reportes. Para el prototipo puede comenzar de forma simple y evolucionar a una cola dedicada si la carga lo exige.

## 3. Flujo principal

1. El adaptador obtiene un ticket pendiente y valida su identificador externo.
2. La aplicación normaliza los datos y solicita la geocodificación de la dirección.
3. El despachador revisa los puntos y selecciona una jornada y los vehículos disponibles.
4. La API prepara un problema de optimización con restricciones explícitas.
5. El módulo de optimización entrega una propuesta y las razones de cualquier exclusión.
6. El despachador acepta o ajusta la propuesta y publica una versión de la ruta.
7. El conductor recibe la secuencia vigente y registra eventos de ejecución.
8. Los cambios de estado pueden activar un nuevo cálculo para las paradas pendientes.
9. Al cerrar la jornada se calculan métricas y se comparan con la línea base.

## 4. Despliegue propuesto en el VPS

- Debian estable con actualizaciones de seguridad.
- Usuario de servicio sin privilegios administrativos para ejecutar la aplicación.
- Proxy inverso para HTTPS y límites de solicitud.
- Aplicación y trabajos en segundo plano como servicios o contenedores, decisión pendiente.
- PostgreSQL accesible solo desde la red o host autorizados.
- Cortafuegos con únicamente los puertos necesarios.
- Certificados TLS con renovación automática.
- Respaldos cifrados fuera del mismo VPS y prueba de restauración.
- Registros con rotación, métricas de salud y alertas básicas.
- Separación entre configuración, secretos y código versionado.

## 5. Seguridad inicial

- Control de acceso basado en roles.
- Sesiones seguras, expiración y revocación.
- Validación de entradas y consultas parametrizadas.
- Protección contra abuso de endpoints e integración.
- Auditoría de cambios en rutas, estados y parámetros.
- Redacción de datos sensibles en los registros.
- Dependencias actualizadas y revisión de vulnerabilidades antes de desplegar.

## 6. Integración con mapas

La selección del proveedor debe comparar cobertura en la zona de operación, calidad de geocodificación, tráfico, límites de uso, costo, términos de almacenamiento y disponibilidad de matrices de viaje. El optimizador no debe depender de estructuras propietarias del proveedor.

Se recomienda almacenar el resultado normalizado y la fecha de consulta. La posibilidad de almacenar respuestas completas debe revisarse según los términos del proveedor seleccionado.

## 7. Disponibilidad y manejo de fallos

- Un ticket inválido pasa a revisión y no detiene la sincronización completa.
- Una falla de geocodificación conserva la solicitud y solicita corrección manual.
- Una falla del proveedor de mapas usa datos en caché permitidos o informa indisponibilidad controlada.
- Una optimización fallida conserva la última ruta publicada.
- Un evento enviado con conectividad intermitente utiliza un identificador idempotente para evitar duplicados.
- La restauración de base de datos debe formar parte de la validación operacional.

## 8. Observabilidad

Como mínimo deben observarse disponibilidad de la API, errores por integración, duración de geocodificación, duración de optimización, cantidad de rutas activas, eventos pendientes de sincronización, uso de almacenamiento y estado de respaldos.

## 9. Decisiones no cerradas

- Framework de frontend y backend.
- Proveedor de mapas y modalidad de contratación.
- Motor o biblioteca de optimización.
- Uso de contenedores en producción.
- Mecanismo de cola de trabajos.
- Estrategia exacta de integración con el sistema de tickets.
- Necesidad de operación sin conexión en la interfaz del conductor.
