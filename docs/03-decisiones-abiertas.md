# Decisiones abiertas

Cada decisión tiene una **recomendación** y un campo **Decisión** para el responsable de
arquitectura. Una vez decidida, se convierte en un ADR (`docs/adr/NNNN-titulo.md`).

---

### D-01 — Modo de despliegue en Android
- **Opciones:** (A) backend en Linux + Android como pantalla vía WiFi · (B) backend en Termux ·
  (C) app nativa con núcleo Python embebido (Chaquopy).
- **Recomendación:** A y B en la Fase 1 (no requieren código extra gracias a `Transport`);
  evaluar C después de la Fase 3.
- **Decisión:** ✅ Linux + Termux — ver [ADR-0001](adr/0001-despliegue-linux-termux.md)

### D-02 — Adaptador de referencia
- **Opciones:**
  - **OBDLink MX+** (STN, Bluetooth clásico): muy fiable, buen soporte multiprotocolo y CAN.
  - **vLinker MC+/FS** (Bluetooth / USB): más económico y compatible con ELM/STN.
  - **Adaptador WiFi ELM/STN**: necesario para el modo B (Termux).
  - **USB-CAN (CANable)**: acceso CAN crudo, útil en Linux; no cubre K-Line.
- **Recomendación:** un adaptador STN/ELM de calidad como referencia (cubre CAN y K-Line,
  frecuente en vehículos asiáticos y chinos más antiguos). USB-CAN como complemento opcional.
- **Decisión:** ⚠️ **Reabierta.** Se propuso el ThinkDiag 2, pero usa un protocolo propietario cifrado y está fuera de alcance (requisitos §1.3). La Fase 1 avanza con el **simulador**, que no necesita hardware; antes de las pruebas con vehículos reales hay que elegir un adaptador ELM327/STN (para Termux: versión **WiFi**).

### D-03 — Marcas prioritarias
- **Contexto Chile:** alta presencia de Chevrolet, Hyundai, Kia, Toyota, Nissan, Suzuki, Peugeot,
  Mitsubishi y de marcas chinas (MG, Chery, Changan, Great Wall/Haval, JAC, Maxus).
  Las chinas tienen poca documentación pública.
- **Recomendación:** elegir 3 marcas para la Fase 3 según el volumen real del taller.
- **Decisión:** _pendiente — ¿cuáles atiendes más?_

### D-04 — Framework de la UI
- **Opciones:** TypeScript sin framework + Vite · Svelte · Vue · React.
- **Recomendación:** **Svelte + TypeScript + Vite**: liviano (bueno para tablets), reactivo,
  poco código repetitivo; uPlot y Cytoscape se integran sin envoltorios pesados.
- **Decisión:** ✅ Svelte + TypeScript + Vite — ver [ADR-0002](adr/0002-ui-svelte-typescript.md)

### D-05 — Librería del mapa topológico
- **Opciones:** Cytoscape.js · D3 (a mano) · SVG propio.
- **Recomendación:** Cytoscape.js.
- **Decisión:** ✅ Cytoscape.js — ver [ADR-0002](adr/0002-ui-svelte-typescript.md)

### D-06 — Proveedor de IA
- **Opciones:** API en la nube (Claude u otro) · modelo local (Ollama) · ambos tras `AIProvider`.
- **Recomendación:** interfaz común; implementar primero un proveedor en la nube (calidad de
  razonamiento) y dejar el local como opción offline.
- **Decisión:** ✅ Nube primero, local opcional — ver [ADR-0003](adr/0003-ia-nube-primero.md)

### D-07 — Servicios con efecto (escritura, rutinas, pruebas activas)
- **Recomendación:** fuera de alcance. Si se incluyen en el futuro: lista blanca por ECU en la
  definición de marca, confirmación doble y bloqueo con el vehículo en movimiento.
- **Decisión:** _pendiente_

### D-08 — Fuentes de definiciones por marca
- **Opciones:** documentación pública/OEM · proyectos abiertos (p. ej. opendbc) · captura propia
  desde vehículos del taller (con un modo "aprendizaje" que registre las respuestas de ECUs).
- **Recomendación:** las tres, registrando el **origen** de cada definición en el YAML
  (`source:`) para saber su fiabilidad.
- **Decisión:** _pendiente_

### D-09 — Licencia del proyecto
- **Opciones:** privado · MIT/Apache-2.0 · GPL.
- **Decisión:** _pendiente_
