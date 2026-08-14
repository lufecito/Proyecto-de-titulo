# -*- encoding: utf-8 -*-
"""
Rutas del módulo de recolección: vistas server-rendered y API JSON.

Autorización por rol:
- Despachador / Administrador: planificación, vehículos, jornadas, optimización,
  publicación, recalculo y visualización de mapas.
- Conductor: solo su propia ruta publicada (eventos de parada y lectura).
"""

from functools import wraps

from flask import (abort, flash, jsonify, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf, validate_csrf

from apps import db
from apps.authentication.models import Users
from apps.home.models import Cliente, Ticket
from apps.recoleccion import blueprint
from apps.recoleccion.forms import (JornadaForm, SolicitudRecoleccionForm,
                                    VehiculoForm, parsear_datetime_local,
                                    parsear_float)
from apps.recoleccion.models import (Jornada, ParadaRuta, PuntoRecoleccion,
                                     Ruta, RutaVersion, SolicitudRecoleccion,
                                     Vehiculo, as_utc, from_local, utcnow)
from apps.recoleccion.services.map_provider import MapProviderError
from apps.recoleccion.services.metrics import metricas_jornada, metricas_ruta
from apps.recoleccion.services.planning import (geocodificar_direccion,
                                                geocodificar_reversa,
                                                obtener_estado_proveedor,
                                                optimizar_jornada,
                                                publicar_version,
                                                recalcular_ruta,
                                                version_a_json)

ROLES_DESPACHADOR = ('Administrador', 'Despachador')
ROLES_CONDUCTOR = ('Administrador', 'Despachador', 'Conductor')


def despachador_required(f):
    @wraps(f)
    def decorado(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol not in ROLES_DESPACHADOR:
            abort(403)
        return f(*args, **kwargs)
    return decorado


def conductor_o_despachador(f):
    @wraps(f)
    def decorado(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol not in ROLES_CONDUCTOR:
            abort(403)
        return f(*args, **kwargs)
    return decorado


@blueprint.before_request
def _proteger_csrf():
    """Valida CSRF en métodos de escritura de este blueprint.

    Los formularios FlaskForm validan su propio token oculto; la API JSON
    usa el encabezado X-CSRFToken. Las demás rutas de la aplicación no se
    ven afectadas.
    """
    if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return None
    if request.form.get('csrf_token'):
        return None
    token = request.headers.get('X-CSRFToken') or request.headers.get('X-CSRF-Token')
    if not token:
        return jsonify({'ok': False, 'error': 'Token CSRF faltante.'}), 400
    try:
        validate_csrf(token)
    except Exception:
        return jsonify({'ok': False, 'error': 'Token CSRF inválido o expirado.'}), 400
    return None


@blueprint.context_processor
def _contexto_csrf():
    return {'recoleccion_csrf_token': generate_csrf()}


def _tickets_sin_solicitud():
    con_solicitud = db.session.query(SolicitudRecoleccion.ticket_id)
    return (Ticket.query.filter(~Ticket.id.in_(con_solicitud))
            .order_by(Ticket.numero).all())


def _opciones_ticket():
    return [(t.id, f'{t.numero} - {t.cliente.nombre}') for t in _tickets_sin_solicitud()]


def _opciones_conductores():
    conductores = (Users.query.filter(Users.rol.in_(['Conductor', 'Despachador']))
                   .order_by(Users.username).all())
    return [(u.id, u.username) for u in conductores]


def _coord_de(form, campo):
    valor = getattr(form, campo).data
    if valor is None:
        return None
    return parsear_float(str(valor).replace(',', '.'))


def _errores_formulario(form):
    return '; '.join('{}: {}'.format(campo, ' '.join(map(str, errores)))
                     for campo, errores in form.errors.items())


# ---------------------------------------------------------------------------
# Vistas: solicitudes
# ---------------------------------------------------------------------------

@blueprint.route('/recoleccion/solicitudes')
@login_required
@despachador_required
def solicitudes():
    lista = (SolicitudRecoleccion.query
             .order_by(SolicitudRecoleccion.prioridad,
                       SolicitudRecoleccion.id.desc()).all())
    return render_template('recoleccion/solicitudes.html', solicitudes=lista,
                           segment='recoleccion_solicitudes')


@blueprint.route('/recoleccion/solicitudes/nueva', methods=['GET', 'POST'])
@login_required
@despachador_required
def solicitud_nueva():
    form = SolicitudRecoleccionForm()
    form.ticket_id.choices = _opciones_ticket()
    form.enviar.label.text = 'Crear solicitud'
    if request.method == 'POST':
        if not _opciones_ticket():
            flash('No quedan tickets disponibles para crear solicitudes.', 'warning')
            return redirect(url_for('recoleccion_blueprint.solicitudes'))
        if form.validate_on_submit():
            lat = _coord_de(form, 'latitud')
            lon = _coord_de(form, 'longitud')
            solicitud = SolicitudRecoleccion(
                ticket_id=form.ticket_id.data,
                estado_disponibilidad='disponible',
                demanda=form.demanda.data or 0,
                unidad_demanda=form.unidad_demanda.data,
                duracion_servicio_seg=form.duracion_servicio_seg.data or 0,
                prioridad=form.prioridad.data or 3,
                ventana_inicio=from_local(parsear_datetime_local(form.ventana_inicio.data)),
                ventana_fin=from_local(parsear_datetime_local(form.ventana_fin.data)),
                estado_operacional='pendiente')
            db.session.add(solicitud)
            db.session.flush()
            db.session.add(PuntoRecoleccion(
                solicitud_id=solicitud.id,
                direccion_original=form.direccion_original.data,
                direccion_normalizada=form.direccion_normalizada.data,
                comuna=form.comuna.data, region=form.region.data,
                referencia=form.referencia.data,
                latitud=lat, longitud=lon,
                proveedor='manual', precision='manual',
                estado_validacion='validado' if (lat is not None and lon is not None)
                else 'pendiente'))
            db.session.commit()
            flash('Solicitud de recolección creada.', 'success')
            return redirect(url_for('recoleccion_blueprint.solicitudes'))
        flash('Revise los errores del formulario: ' + _errores_formulario(form),
              'warning')
    return render_template('recoleccion/solicitud_form.html', form=form,
                           modo='nueva', segment='recoleccion_solicitudes')


@blueprint.route('/recoleccion/solicitudes/<int:solicitud_id>/editar',
                 methods=['GET', 'POST'])
@login_required
@despachador_required
def solicitud_editar(solicitud_id):
    solicitud = SolicitudRecoleccion.query.get_or_404(solicitud_id)
    form = SolicitudRecoleccionForm(obj=solicitud)
    form.ticket_id.choices = _opciones_ticket() + [(solicitud.ticket_id,
                                                    solicitud.etiqueta)]
    if request.method == 'POST':
        if form.validate_on_submit():
            lat = _coord_de(form, 'latitud')
            lon = _coord_de(form, 'longitud')
            solicitud.demanda = form.demanda.data or 0
            solicitud.unidad_demanda = form.unidad_demanda.data
            solicitud.duracion_servicio_seg = form.duracion_servicio_seg.data or 0
            solicitud.prioridad = form.prioridad.data or 3
            solicitud.ventana_inicio = from_local(
                parsear_datetime_local(form.ventana_inicio.data))
            solicitud.ventana_fin = from_local(
                parsear_datetime_local(form.ventana_fin.data))
            punto = solicitud.punto
            punto.direccion_original = form.direccion_original.data
            punto.direccion_normalizada = form.direccion_normalizada.data
            punto.comuna = form.comuna.data
            punto.region = form.region.data
            punto.referencia = form.referencia.data
            if lat is not None and lon is not None:
                punto.latitud = lat
                punto.longitud = lon
                punto.estado_validacion = 'validado'
            db.session.commit()
            flash('Solicitud actualizada.', 'success')
            return redirect(url_for('recoleccion_blueprint.solicitudes'))
        flash('Revise los errores del formulario: ' + _errores_formulario(form),
              'warning')
    return render_template('recoleccion/solicitud_form.html', form=form,
                           solicitud=solicitud, modo='editar',
                           segment='recoleccion_solicitudes')


# ---------------------------------------------------------------------------
# Vistas: vehículos
# ---------------------------------------------------------------------------

@blueprint.route('/recoleccion/vehiculos')
@login_required
@despachador_required
def vehiculos():
    lista = Vehiculo.query.order_by(Vehiculo.identificador).all()
    return render_template('recoleccion/vehiculos.html', vehiculos=lista,
                           segment='recoleccion_vehiculos')


def _crear_o_editar_vehiculo(vehiculo=None):
    form = VehiculoForm(obj=vehiculo)
    form.conductor_id.choices = [(0, 'Sin conductor')] + _opciones_conductores()
    if request.method == 'POST' and form.validate_on_submit():
        if vehiculo is None:
            vehiculo = Vehiculo()
            db.session.add(vehiculo)
        vehiculo.identificador = form.identificador.data
        vehiculo.patente = form.patente.data or None
        vehiculo.nombre = form.nombre.data
        vehiculo.capacidad = form.capacidad.data or 0
        vehiculo.unidad = form.unidad.data
        vehiculo.perfil_ruteo = form.perfil_ruteo.data
        lat_i = _coord_de(form, 'lat_inicio')
        lon_i = _coord_de(form, 'lon_inicio')
        lat_f = _coord_de(form, 'lat_fin')
        lon_f = _coord_de(form, 'lon_fin')
        vehiculo.lat_inicio = lat_i or 0
        vehiculo.lon_inicio = lon_i or 0
        vehiculo.lat_fin = lat_f or 0
        vehiculo.lon_fin = lon_f or 0
        vehiculo.conductor_id = form.conductor_id.data or None
        vehiculo.estado_disponibilidad = form.estado_disponibilidad.data
        db.session.commit()
        flash('Vehículo guardado.', 'success')
        return redirect(url_for('recoleccion_blueprint.vehiculos'))
    if request.method == 'POST':
        flash('Revise los errores del formulario: ' + _errores_formulario(form),
              'warning')
    return render_template('recoleccion/vehiculo_form.html', form=form,
                           vehiculo=vehiculo, segment='recoleccion_vehiculos')


@blueprint.route('/recoleccion/vehiculos/nuevo', methods=['GET', 'POST'])
@login_required
@despachador_required
def vehiculo_nuevo():
    return _crear_o_editar_vehiculo()


@blueprint.route('/recoleccion/vehiculos/<int:vehiculo_id>/editar', methods=['GET', 'POST'])
@login_required
@despachador_required
def vehiculo_editar(vehiculo_id):
    vehiculo = Vehiculo.query.get_or_404(vehiculo_id)
    return _crear_o_editar_vehiculo(vehiculo)


# ---------------------------------------------------------------------------
# Vistas: jornadas y planificación
# ---------------------------------------------------------------------------

@blueprint.route('/recoleccion/jornadas')
@login_required
@despachador_required
def jornadas():
    lista = Jornada.query.order_by(Jornada.fecha_operacional.desc(),
                                   Jornada.id.desc()).all()
    return render_template('recoleccion/jornadas.html', jornadas=lista,
                           segment='recoleccion_jornadas')


@blueprint.route('/recoleccion/jornadas/nueva', methods=['GET', 'POST'])
@login_required
@despachador_required
def jornada_nueva():
    form = JornadaForm()
    form.solicitudes.choices = [(s.id, s.etiqueta)
                                for s in SolicitudRecoleccion.query
                                .filter_by(estado_disponibilidad='disponible')
                                .order_by(SolicitudRecoleccion.prioridad).all()]
    form.vehiculos.choices = [(v.id, v.identificador)
                              for v in Vehiculo.query
                              .filter_by(estado_disponibilidad='disponible')
                              .order_by(Vehiculo.identificador).all()]
    form.responsable_id.choices = [(0, 'Sin responsable')] + _opciones_conductores()
    if request.method == 'POST' and form.validate_on_submit():
        dep_lat = parsear_float(str(form.deposito_lat.data).replace(',', '.'))
        dep_lon = parsear_float(str(form.deposito_lon.data).replace(',', '.'))
        jornada = Jornada(
            fecha_operacional=parsear_datetime_local(
                form.fecha_operacional.data).date()
            if parsear_datetime_local(form.fecha_operacional.data) else None,
            estado='preparacion',
            inicio_operacion=from_local(parsear_datetime_local(form.inicio_operacion.data)),
            fin_operacion=from_local(parsear_datetime_local(form.fin_operacion.data)),
            deposito_direccion=form.deposito_direccion.data,
            deposito_lat=dep_lat, deposito_lon=dep_lon,
            responsable_id=form.responsable_id.data or None)
        db.session.add(jornada)
        db.session.flush()
        jornada.solicitudes = (SolicitudRecoleccion.query
                               .filter(SolicitudRecoleccion.id.in_(form.solicitudes.data)).all())
        jornada.vehiculos = (Vehiculo.query
                             .filter(Vehiculo.id.in_(form.vehiculos.data)).all())
        db.session.commit()
        flash('Jornada creada. Ahora puede planificarla.', 'success')
        return redirect(url_for('recoleccion_blueprint.jornada_detalle',
                                jornada_id=jornada.id))
    if request.method == 'POST':
        flash('Revise los errores del formulario: ' + _errores_formulario(form),
              'warning')
    return render_template('recoleccion/jornada_form.html', form=form,
                           modo='nueva', segment='recoleccion_jornadas')


@blueprint.route('/recoleccion/jornadas/<int:jornada_id>')
@login_required
@despachador_required
def jornada_detalle(jornada_id):
    jornada = Jornada.query.get_or_404(jornada_id)
    metricas = metricas_jornada(jornada)
    return render_template('recoleccion/jornada_detalle.html', jornada=jornada,
                           metricas=metricas, segment='recoleccion_jornadas')


@blueprint.route('/recoleccion/jornadas/<int:jornada_id>/optimizar', methods=['POST'])
@login_required
@despachador_required
def jornada_optimizar(jornada_id):
    try:
        resumen = optimizar_jornada(jornada_id)
    except MapProviderError as exc:
        flash(f'Error cartográfico: {exc.mensaje}', 'danger')
        return redirect(url_for('recoleccion_blueprint.jornada_detalle',
                                jornada_id=jornada_id))
    if not resumen.get('ok'):
        flash(resumen.get('error', 'No se pudo optimizar la jornada.'), 'danger')
        return redirect(url_for('recoleccion_blueprint.jornada_detalle',
                                jornada_id=jornada_id))
    flash('Jornada optimizada. Revise las propuestas por ruta.', 'success')
    return redirect(url_for('recoleccion_blueprint.planificacion',
                            jornada_id=jornada_id))


@blueprint.route('/recoleccion/planificacion')
@login_required
@despachador_required
def planificacion():
    jornada_id = request.args.get('jornada_id', type=int)
    jornada = Jornada.query.get_or_404(jornada_id)
    metricas = metricas_jornada(jornada)
    versiones = {}
    for ruta in jornada.rutas:
        versiones[ruta.id] = {
            'linea_base': next((v for v in ruta.versiones if v.tipo == 'linea_base'), None),
            'propuesta': next((v for v in reversed(ruta.versiones) if v.tipo == 'propuesta'), None),
            'publicada': next((v for v in reversed(ruta.versiones) if v.tipo == 'publicada'), None),
        }
    return render_template('recoleccion/planificacion.html', jornada=jornada,
                           metricas=metricas, versiones=versiones,
                           segment='recoleccion_planificacion')


@blueprint.route('/recoleccion/rutas/<int:ruta_id>/mapa')
@login_required
@despachador_required
def ruta_mapa(ruta_id):
    ruta = Ruta.query.get_or_404(ruta_id)
    version_id = request.args.get('version_id', type=int)
    version = (RutaVersion.query.get(version_id)
               if version_id else ruta.version_vigente)
    if not version:
        flash('Esta ruta aún no tiene versión publicada.', 'warning')
        return redirect(url_for('recoleccion_blueprint.planificacion',
                                jornada_id=ruta.jornada_id))
    datos = version_a_json(version)
    return render_template('recoleccion/mapa_ruta.html', ruta=ruta,
                           datos=datos, version=version,
                           segment='recoleccion_planificacion')


@blueprint.route('/recoleccion/rutas/<int:ruta_id>/publicar', methods=['POST'])
@login_required
@despachador_required
def ruta_publicar(ruta_id):
    version_id = request.form.get('version_id', type=int)
    if not version_id:
        flash('Debe seleccionar una versión a publicar.', 'warning')
        return redirect(url_for('recoleccion_blueprint.planificacion',
                                jornada_id=Ruta.query.get(ruta_id).jornada_id))
    resultado = publicar_version(ruta_id, version_id)
    flash('Ruta publicada.' if resultado.get('ok') else 'No se pudo publicar.',
          'success' if resultado.get('ok') else 'danger')
    return redirect(url_for('recoleccion_blueprint.planificacion',
                            jornada_id=Ruta.query.get(ruta_id).jornada_id))


@blueprint.route('/recoleccion/rutas/<int:ruta_id>/recalcular', methods=['POST'])
@login_required
@despachador_required
def ruta_recalcular(ruta_id):
    resultado = recalcular_ruta(ruta_id)
    ruta = Ruta.query.get(ruta_id)
    if not resultado.get('ok'):
        flash(resultado.get('error', 'No se pudo recalcular.'), 'danger')
    elif not resultado.get('cambio'):
        flash(resultado.get('mensaje', 'Sin cambios.'), 'info')
    else:
        flash('Ruta recalculada conservando las paradas completadas.', 'success')
    return redirect(url_for('recoleccion_blueprint.planificacion',
                            jornada_id=ruta.jornada_id))


# ---------------------------------------------------------------------------
# Vistas: conductor y antecedentes
# ---------------------------------------------------------------------------

@blueprint.route('/recoleccion/mi-ruta')
@login_required
@conductor_o_despachador
def mi_ruta():
    if current_user.rol == 'Conductor':
        ruta = (Ruta.query.filter_by(conductor_id=current_user.id)
                .filter(Ruta.jornada.has(Jornada.estado.in_(
                    ['publicada', 'en_ejecucion'])))
                .first())
        if not ruta:
            flash('No tiene una ruta publicada para la jornada vigente.', 'info')
            return render_template('recoleccion/conductor_ruta.html', ruta=None,
                                   datos=None, segment='recoleccion_conductor')
        datos = version_a_json(ruta.version_vigente)
        return render_template('recoleccion/conductor_ruta.html', ruta=ruta,
                               datos=datos, segment='recoleccion_conductor')
    rutas = (Ruta.query.filter(Ruta.jornada.has(Jornada.estado.in_(
        ['publicada', 'en_ejecucion'])))
        .order_by(Ruta.id.desc()).all())
    return render_template('recoleccion/conductor_ruta.html', ruta=None,
                           rutas=rutas, datos=None,
                           segment='recoleccion_conductor')


@blueprint.route('/recoleccion/historial')
@login_required
@despachador_required
def historial():
    from apps.recoleccion.models import EjecucionOptimizacion, EventoRuta
    eventos = (EventoRuta.query.order_by(EventoRuta.fecha_utc.desc()).limit(50).all())
    ejecuciones = (EjecucionOptimizacion.query
                   .order_by(EjecucionOptimizacion.id.desc()).limit(50).all())
    return render_template('recoleccion/historial.html', eventos=eventos,
                           ejecuciones=ejecuciones,
                           segment='recoleccion_historial')


@blueprint.route('/recoleccion')
@login_required
@conductor_o_despachador
def indice():
    estado = obtener_estado_proveedor()
    totales = {
        'solicitudes': SolicitudRecoleccion.query.count(),
        'vehiculos': Vehiculo.query.count(),
        'jornadas': Jornada.query.count(),
        'rutas': Ruta.query.count(),
    }
    return render_template('recoleccion/indice.html', estado=estado,
                           totales=totales, segment='recoleccion_indice')


# ---------------------------------------------------------------------------
# API JSON
# ---------------------------------------------------------------------------

@blueprint.route('/api/v1/recoleccion/estado-proveedor')
@login_required
def api_estado_proveedor():
    return jsonify({'ok': True, **obtener_estado_proveedor()})


@blueprint.route('/api/v1/recoleccion/geocodificar', methods=['POST'])
@login_required
@despachador_required
def api_geocodificar():
    datos = request.get_json(silent=True) or {}
    direccion = (datos.get('direccion') or '').strip()
    if not direccion:
        return jsonify({'ok': False, 'error': 'Debe indicar una dirección.'}), 400
    try:
        resultado = geocodificar_direccion(direccion)
    except MapProviderError as exc:
        return jsonify({'ok': False, 'error': exc.mensaje}), 422
    return jsonify({'ok': True, **resultado.to_dict()})


@blueprint.route('/api/v1/recoleccion/reversa', methods=['POST'])
@login_required
@despachador_required
def api_reversa():
    datos = request.get_json(silent=True) or {}
    try:
        lat = float(datos.get('lat'))
        lon = float(datos.get('lon'))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Coordenadas inválidas.'}), 400
    try:
        resultado = geocodificar_reversa(lat, lon)
    except MapProviderError as exc:
        return jsonify({'ok': False, 'error': exc.mensaje}), 422
    return jsonify({'ok': True, **resultado.to_dict()})


@blueprint.route('/api/v1/recoleccion/rutas/<int:ruta_id>/version/<int:version_id>')
@login_required
def api_version(ruta_id, version_id):
    ruta = Ruta.query.get_or_404(ruta_id)
    version = RutaVersion.query.get_or_404(version_id)
    if version.ruta_id != ruta.id:
        abort(404)
    return jsonify({'ok': True, 'version': version_a_json(version)})


@blueprint.route('/api/v1/recoleccion/rutas/<int:ruta_id>/recalcular', methods=['POST'])
@login_required
@despachador_required
def api_recalcular(ruta_id):
    resultado = recalcular_ruta(ruta_id)
    if not resultado.get('ok'):
        return jsonify(resultado), 400
    return jsonify(resultado)


@blueprint.route('/api/v1/recoleccion/rutas/<int:ruta_id>/publicar', methods=['POST'])
@login_required
@despachador_required
def api_publicar(ruta_id):
    datos = request.get_json(silent=True) or {}
    version_id = datos.get('version_id')
    if not version_id:
        return jsonify({'ok': False, 'error': 'Falta version_id.'}), 400
    resultado = publicar_version(ruta_id, int(version_id))
    if not resultado.get('ok'):
        return jsonify(resultado), 400
    return jsonify(resultado)


def _ruta_conductor_actual():
    """Ruta publicada asignada al conductor autenticado (o verificable)."""
    if current_user.rol == 'Conductor':
        ruta = (Ruta.query.filter_by(conductor_id=current_user.id)
                .filter(Ruta.jornada.has(Jornada.estado.in_(
                    ['publicada', 'en_ejecucion']))).first())
        return ruta, None
    return None, 'Rol no autorizado para esta operación.'


@blueprint.route('/api/v1/recoleccion/paradas/<int:parada_id>/evento', methods=['POST'])
@login_required
@conductor_o_despachador
def api_evento_parada(parada_id):
    parada = ParadaRuta.query.get_or_404(parada_id)
    datos = request.get_json(silent=True) or {}
    tipo = datos.get('tipo')
    idempotencia_key = (datos.get('idempotencia_key') or '').strip()
    if tipo not in ('llegada', 'recoleccion_completada', 'punto_no_disponible',
                    'incidencia'):
        return jsonify({'ok': False, 'error': 'Tipo de evento inválido.'}), 400
    if not idempotencia_key:
        return jsonify({'ok': False, 'error': 'Falta idempotencia_key.'}), 400

    ruta = parada.version.ruta
    if current_user.rol == 'Conductor':
        if ruta.conductor_id != current_user.id:
            abort(403)
        if parada.version_id != (ruta.version_vigente_id or parada.version_id):
            abort(409, 'La parada no pertenece a la versión vigente.')

    from apps.recoleccion.models import EventoRuta
    existente = EventoRuta.query.filter_by(idempotencia_key=idempotencia_key).first()
    if existente:
        return jsonify({'ok': True, 'duplicado': True, 'evento_id': existente.id})

    try:
        lat = float(datos.get('lat')) if datos.get('lat') is not None else None
        lon = float(datos.get('lon')) if datos.get('lon') is not None else None
    except (TypeError, ValueError):
        lat = lon = None

    estado_anterior = parada.estado
    if tipo == 'llegada':
        parada.estado = 'en_atencion'
    elif tipo == 'recoleccion_completada':
        parada.estado = 'completada'
        parada.solicitud.estado_operacional = 'completada'
    elif tipo == 'punto_no_disponible':
        parada.estado = 'no_disponible'
        parada.solicitud.estado_disponibilidad = 'no_disponible'
    elif tipo == 'incidencia':
        parada.estado = 'incidencia'
    parada.actualizado_en = utcnow()

    evento = EventoRuta(
        ruta_id=ruta.id, parada_id=parada.id,
        version_id=ruta.version_vigente_id,
        actor_id=current_user.id, tipo=tipo,
        fecha_utc=utcnow(), idempotencia_key=idempotencia_key,
        latitud=lat, longitud=lon,
        observacion=datos.get('observacion') or '',
        datos_anteriores={'estado': estado_anterior},
        datos_nuevos={'estado': parada.estado})
    db.session.add(evento)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        existente2 = EventoRuta.query.filter_by(idempotencia_key=idempotencia_key).first()
        if existente2:
            return jsonify({'ok': True, 'duplicado': True, 'evento_id': existente2.id})
        raise
    return jsonify({'ok': True, 'evento_id': evento.id, 'parada': {
        'id': parada.id, 'estado': parada.estado}})
