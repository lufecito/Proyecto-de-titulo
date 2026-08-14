# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os, random, string

class Config(object):

    basedir = os.path.abspath(os.path.dirname(__file__))

    # Assets Management
    ASSETS_ROOT = os.getenv('ASSETS_ROOT', '/static/assets')
    APP_NAME = os.getenv('APP_NAME', 'Ticket Kanban')

    # Google OAuth2
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', None)
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', None)
    GOOGLE_ALLOWED_DOMAIN = os.getenv('GOOGLE_ALLOWED_DOMAIN', '').strip().lower()
    GOOGLE_AUTO_PROVISION = os.getenv('GOOGLE_AUTO_PROVISION', 'False').lower() == 'true'

    # Set up the App SECRET_KEY
    SECRET_KEY  = os.getenv('SECRET_KEY', None)
    if not SECRET_KEY:
        SECRET_KEY = ''.join(random.choice( string.ascii_lowercase  ) for i in range( 32 ))

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DB_ENGINE   = os.getenv('DB_ENGINE'   , None)
    DB_USERNAME = os.getenv('DB_USERNAME' , None)
    DB_PASS     = os.getenv('DB_PASS'     , None)
    DB_HOST     = os.getenv('DB_HOST'     , None)
    DB_PORT     = os.getenv('DB_PORT'     , None)
    DB_NAME     = os.getenv('DB_NAME'     , None)

    USE_SQLITE  = True

    # try to set up a Relational DBMS
    if DB_ENGINE and DB_NAME and DB_USERNAME:

        try:

            # Relational DBMS: PSQL, MySql
            SQLALCHEMY_DATABASE_URI = '{}://{}:{}@{}:{}/{}'.format(
                DB_ENGINE,
                DB_USERNAME,
                DB_PASS,
                DB_HOST,
                DB_PORT,
                DB_NAME
            )

            USE_SQLITE  = False

        except Exception as e:

            print('> Error: DBMS Exception: ' + str(e) )
            print('> Fallback to SQLite ')

    if USE_SQLITE:
        sqlite_path = os.getenv('SQLITE_PATH', os.path.join(basedir, 'db.sqlite3'))
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.abspath(sqlite_path)

    # ------------------------------------------------------------------
    # Módulo de recolección: cartografía, optimización y caché
    # ------------------------------------------------------------------
    # MAP_PROVIDER: 'auto' (usa ORS si hay clave, si no FakeMapProvider),
    # 'ors' (openrouteservice) o 'fake' (modo demostración sin red).
    MAP_PROVIDER = os.getenv('MAP_PROVIDER', 'auto').strip().lower()

    # openrouteservice (las claves nunca salen del servidor).
    ORS_API_KEY = os.getenv('ORS_API_KEY', '').strip()
    ORS_BASE_URL = os.getenv('ORS_BASE_URL', 'https://api.openrouteservice.org').rstrip('/')
    ORS_GEOCODE_BASE_URL = os.getenv(
        'ORS_GEOCODE_BASE_URL', 'https://api.openrouteservice.org/geocode').rstrip('/')
    ORS_PROFILE = os.getenv('ORS_PROFILE', 'driving-hgv').strip() or 'driving-hgv'
    ORS_GEOCODE_COUNTRY = os.getenv('ORS_GEOCODE_COUNTRY', 'CHL').strip() or 'CHL'
    ORS_MAX_RESPONSE_BYTES = int(os.getenv('ORS_MAX_RESPONSE_BYTES', '2000000'))

    # Mapas web (Leaflet).
    MAP_TILE_URL = os.getenv(
        'MAP_TILE_URL', 'https://tile.openstreetmap.org/{z}/{x}/{y}.png')
    MAP_TILE_ATTRIBUTION = os.getenv(
        'MAP_TILE_ATTRIBUTION', '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors')
    CHILE_LIMITS_SERVICE_URL = os.getenv(
        'CHILE_LIMITS_SERVICE_URL',
        'https://rest-sit.mop.gob.cl/arcgis/rest/services/MAPA_BASE/LIMITES/MapServer')

    # Timeout y reintentos para llamadas externas.
    MAP_HTTP_TIMEOUT_SECONDS = float(os.getenv('MAP_HTTP_TIMEOUT_SECONDS', '15'))
    MAP_HTTP_RETRIES = int(os.getenv('MAP_HTTP_RETRIES', '2'))

    # Caché persistente de geocodificación y matrices.
    MAP_CACHE_DIR = os.getenv('MAP_CACHE_DIR', os.path.join(basedir, '..', 'map_cache'))
    GEOCODE_CACHE_TTL_SECONDS = int(os.getenv('GEOCODE_CACHE_TTL_SECONDS', '2592000'))
    MATRIX_CACHE_TTL_SECONDS = int(os.getenv('MATRIX_CACHE_TTL_SECONDS', '604800'))
    MAP_CACHE_MAX_ENTRIES = int(os.getenv('MAP_CACHE_MAX_ENTRIES', '2000'))

    # Optimización local.
    OPTIMIZER_TIME_LIMIT_SECONDS = int(os.getenv('OPTIMIZER_TIME_LIMIT_SECONDS', '30'))

    # Zona horaria operacional por defecto.
    OPERATIONAL_TIMEZONE = os.getenv('OPERATIONAL_TIMEZONE', 'America/Santiago')

class ProductionConfig(Config):
    DEBUG = False

    # Security
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 3600


class DebugConfig(Config):
    DEBUG = True


# Load all possible configurations
config_dict = {
    'Production': ProductionConfig,
    'Debug'     : DebugConfig
}
