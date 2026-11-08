# diag — Plataforma abierta de diagnóstico automotriz multimarca

Herramienta de análisis y diagnóstico que complementa a las herramientas comerciales:
datos en vivo completos, gráficas sincronizadas, asistente de IA con contexto real y mapa
topológico de ECUs.

- Requisitos: [`docs/01-requisitos.md`](docs/01-requisitos.md)
- Arquitectura: [`docs/02-arquitectura.md`](docs/02-arquitectura.md)
- Decisiones: [`docs/03-decisiones-abiertas.md`](docs/03-decisiones-abiertas.md) y [`docs/adr/`](docs/adr/)
- Avance: [`docs/04-avance.md`](docs/04-avance.md)

## Puesta en marcha (Linux o Termux)

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Prueba de extremo a extremo contra el vehículo simulado (sin hardware)
.venv/bin/diag-sim --duration 5
.venv/bin/diag-sim --signals engine_rpm,ltft_b1,o2_b1s1_voltage --unit o2_b1s1_voltage=mV
```

## Calidad

```bash
.venv/bin/pytest            # pruebas
.venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests
.venv/bin/mypy src          # tipado estricto
```

## Extender sin tocar código

| Quiero... | Edito... |
|---|---|
| Agregar una unidad de visualización | `definitions/units.yaml` |
| Agregar un PID OBD2 | `definitions/obd2/pids.yaml` |
| Crear un vehículo de práctica | un archivo nuevo en `definitions/vehicles/sim/` |
| Cambiar un parámetro (retardo, semilla, PIDs por petición) | `config/local.yaml` o `DIAG_<SECCIÓN>__<CLAVE>` |

Cada archivo se valida al cargarse. Un error indica **archivo, línea y causa**, por ejemplo:

```
definitions/obd2/pids.yaml:9: pids.0.signals.0.unit: unidad 'rev/s' no definida en units.yaml
```

## Estructura

```
config/         configuración (default.yaml versionado; local.yaml no)
definitions/    datos: unidades, PIDs, vehículos simulados (y luego marcas, reglas...)
src/diag/
  core/         dominio, puertos, protocolos y decodificación (sin E/S)
  services/     casos de uso (cliente OBD2)
  infra/        implementaciones de puertos (simulador; luego ELM327, SQLite, IA)
  tools/        utilidades de línea de comandos
tests/          pruebas unitarias e integración con el simulador
```
