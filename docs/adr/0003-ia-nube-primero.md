# ADR-0003 — Proveedor de IA: nube primero, local opcional (D-06)

- **Estado:** Aceptada (2026-11-08)
- **Requisitos:** RU-60…64, RS-40…45, RNF-03, RNF-07

## Decisión
- El asistente usa el puerto `AIProvider`. Primera implementación: proveedor en la nube (API de Claude).
- Segunda implementación, opcional: modelo local (p. ej. Ollama) para trabajo sin internet.
- Proveedor, modelo y parámetros se eligen por configuración; la clave de API solo por variable de entorno.

## Consecuencias
- Se envía un resumen estadístico, no series crudas (RS-42), con anonimización configurable del VIN (RNF-03).
- Sin internet el resto de la plataforma funciona igual (RNF-07).
