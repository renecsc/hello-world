# Avance de implementación

Leyenda: ✅ hecho · 🟡 parcial · ⬜ pendiente

## Fase 1 — MVP

### Iteración 1: núcleo y simulador (sin hardware)

| Requisito | Estado | Dónde | Notas |
|---|---|---|---|
| RS-02 puerto `Adapter` | ✅ | `core/ports/adapter.py` | |
| RS-03 OBD2 sobre CAN 11 bits | ✅ | `core/protocols/obd2.py`, `services/obd2_client.py` | 29 bits y K-Line: con el adaptador real |
| RS-05 configuración externa | ✅ | `config/`, `src/diag/config.py` | default < local < entorno |
| RS-06 simulador | ✅ | `infra/simulator/` | mismo puerto que un adaptador real |
| RS-10 PIDs en YAML | ✅ | `definitions/obd2/pids.yaml` | 24 PIDs, 26 señales |
| RS-12 validación con archivo y línea | ✅ | `core/definitions/loader.py` | errores de fórmula: línea del PID |
| RS-13 fórmulas seguras sin `eval` | ✅ | `core/decoding/formula.py` | AST con lista blanca |
| RS-15 conversión de unidades | 🟡 | `definitions/units.yaml`, `core/decoding/units.py` | falta persistir la preferencia (con la UI) |
| RS-21 marca de tiempo monotónica | ✅ | `services/obd2_client.py` | reloj inyectable |
| RU-02 identificación (VIN, ECUs) | ✅ | `Obd2Client.connect` | |
| RU-03 trabajar sin vehículo | 🟡 | simulador | falta reproducir grabaciones (RU-30) |
| RU-40 leer/borrar DTC genéricos | ✅ | `Obd2Client.read_all_dtcs`, `clear_dtcs` | confirmación del borrado: en la UI (RNF-04) |
| RU-41 freeze frame | ✅ | `Obd2Client.read_freeze_frames` | |
| RS-14 descripciones de DTC | ⬜ | | siguiente iteración |

### Próximas iteraciones
1. **Adquisición continua** (RS-20 planificador por prioridad) + **grabación SQLite** (RS-22, RU-30) + exportación CSV (RU-31).
2. **API** FastAPI + WebSocket (RS-23).
3. **UI** Svelte: tabla completa, gráficas uPlot sincronizadas, plantillas, unidades (RU-10…24).
4. **Adaptador real** ELM327/STN: transportes TCP (Termux) y Bluetooth/serie (Linux). Bloqueado por D-02.
