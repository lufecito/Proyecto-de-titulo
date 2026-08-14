# -*- encoding: utf-8 -*-
"""
Caché persistente mínima para geocodificación y matrices cartográficas.

Las claves se derivan del proveedor, perfil, versión y entrada normalizada,
de modo que la misma consulta reutiliza el resultado dentro del TTL.
Persistencia en archivos JSON con escritura atómica (apto para SQLite de
desarrollo y PostgreSQL de producción).
"""

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path


def cache_key(*partes):
    """Clave estable a partir de partes normalizadas."""
    texto = '|'.join(str(p).strip().lower() for p in partes)
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


class MapCache:
    """Caché de archivos por clave, con expiración y límite de entradas."""

    def __init__(self, directorio, ttl_segundos, max_entradas=2000):
        self.directorio = Path(directorio)
        self.ttl_segundos = ttl_segundos
        self.max_entradas = max_entradas

    def _ruta(self, key):
        return self.directorio / f'{key}.json'

    def get(self, key):
        ruta = self._ruta(key)
        try:
            with open(ruta, 'r', encoding='utf-8') as fh:
                payload = json.load(fh)
        except (OSError, ValueError, KeyError):
            return None
        ahora = time.time()
        if payload.get('expires_at', 0) <= ahora:
            self._borrar(ruta)
            return None
        return payload.get('data')

    def set(self, key, data):
        try:
            self.directorio.mkdir(parents=True, exist_ok=True)
            self._podar()
            payload = {
                'stored_at': time.time(),
                'expires_at': time.time() + self.ttl_segundos,
                'data': data,
            }
            fd, tmp = tempfile.mkstemp(dir=str(self.directorio), suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                    json.dump(payload, fh, ensure_ascii=False)
                os.replace(tmp, self._ruta(key))
            except BaseException:
                if os.path.exists(tmp):
                    os.remove(tmp)
                raise
        except OSError:
            # Una caché no debe impedir el flujo principal.
            return

    def clear(self):
        if self.directorio.exists():
            for ruta in self.directorio.glob('*.json'):
                try:
                    ruta.unlink()
                except OSError:
                    pass
            for ruta in self.directorio.glob('*.tmp'):
                try:
                    ruta.unlink()
                except OSError:
                    pass

    def _podar(self):
        try:
            archivos = sorted(
                self.directorio.glob('*.json'),
                key=lambda p: p.stat().st_mtime,
            )
        except OSError:
            return
        while len(archivos) > self.max_entradas:
            self._borrar(archivos.pop(0))

    @staticmethod
    def _borrar(ruta):
        try:
            ruta.unlink()
        except OSError:
            pass
