# -*- encoding: utf-8 -*-
"""
Blueprint del módulo de recolección.

Rutas de interfaz: /recoleccion/...
Rutas JSON: /api/v1/recoleccion/...
"""

from flask import Blueprint

blueprint = Blueprint(
    'recoleccion_blueprint',
    __name__,
    url_prefix=''
)
