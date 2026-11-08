"""Plataforma abierta de diagnóstico automotriz multimarca.

Arquitectura hexagonal (ver ``docs/02-arquitectura.md``):

- ``diag.core``: dominio, puertos, protocolos y decodificación. Sin E/S ni dependencias de
  infraestructura.
- ``diag.infra``: implementaciones de los puertos (simulador, transportes, almacenamiento).
- ``diag.tools``: utilidades de línea de comandos.
"""
