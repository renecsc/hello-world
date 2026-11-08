# ADR-0002 — Interfaz: Svelte + TypeScript + Vite (D-04)

- **Estado:** Aceptada (2026-11-08)
- **Requisitos:** RU-10…24, RNF-01, RNF-02

## Decisión
Frontend en **Svelte + TypeScript**, empaquetado con **Vite**. Gráficas con **uPlot**, mapa topológico con **Cytoscape.js** (D-05, aceptada junto con esta).

## Consecuencias
- El backend sirve los archivos estáticos compilados: en Termux no hace falta Node.js en tiempo de ejecución, solo para compilar.
- Textos de la UI externalizados en `i18n/` (RNF-11).
