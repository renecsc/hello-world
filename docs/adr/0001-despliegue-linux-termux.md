# ADR-0001 — Despliegue: Linux + Termux (D-01)

- **Estado:** Aceptada (2026-11-08)
- **Requisitos:** RU-01, RS-01, RNF-07

## Contexto
El técnico trabaja con Linux (portátil) y Android (tablet/teléfono).

## Decisión
- El backend es una aplicación Python que corre en **Linux** y en **Android vía Termux**, con el mismo código.
- La UI es web (PWA): se abre en el navegador del mismo equipo o desde una tablet en la misma red.
- En Termux el transporte soportado es **TCP (adaptadores WiFi)**: Termux no expone Bluetooth clásico (SPP) de forma fiable.
- La app nativa (Chaquopy + Bluetooth en Kotlin) se reevalúa después de la Fase 3.

## Consecuencias
- Solo dependencias Python puras o con ruedas disponibles en Termux (evitar extensiones C exóticas).
- Todos los transportes implementan el puerto `Transport`; agregar uno nuevo no toca el núcleo.
