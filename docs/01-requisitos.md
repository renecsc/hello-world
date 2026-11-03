# Especificación de requisitos — Plataforma de diagnóstico automotriz multimarca

> **Estado:** v1.0 — requisitos aprobados por el responsable de arquitectura (2026-11-03).
> Ningún requisito se implementa hasta que esté marcado como **Aprobado**. Los cambios posteriores se proponen como nuevas filas o con estado `Propuesto`.

## 0. Cómo leer este documento

| Campo | Significado |
|---|---|
| **ID** | `RU-xx` = requisito de usuario · `RS-xx` = requisito de sistema · `RNF-xx` = no funcional |
| **Prioridad** | MoSCoW: **M** (Must), **S** (Should), **C** (Could), **W** (Won't, por ahora) |
| **Fase** | Fase del plan en que se entrega (ver §5) |
| **Estado** | `Propuesto` → `Aprobado` → `Implementado` → `Verificado` |

Cada requisito de sistema (`RS`) traza a uno o más requisitos de usuario (`RU`).

---

## 1. Contexto y alcance

### 1.1 Problema
La herramienta comercial actual (ThinkDiag 2) cubre bien las funciones especiales
(servicio, codificación), pero limita el **flujo de trabajo de diagnóstico**:

1. Datos en vivo paginados: no se puede ver la lista completa.
2. Gráficas pobres y pocas señales combinables a la vez.
3. Asistente de IA que solo explica códigos, sin razonar sobre datos reales.
4. Sin mapa topológico de la red de módulos (ECUs).

### 1.2 Objetivo
Una plataforma propia, abierta y extensible, orientada al **análisis y diagnóstico**,
que **complementa** (no reemplaza) a la herramienta comercial.

### 1.3 Fuera de alcance (explícito)
- Funciones especiales de servicio (EPB, DPF, SAS, codificación de inyectores…).
- Reprogramación / flasheo de ECUs.
- Codificación de módulos o escritura de datos (`WriteDataByIdentifier`, `RoutineControl`)
  — salvo decisión explícita futura (ver `03-decisiones-abiertas.md`, D-07).
- Comunicación con el hardware ThinkDiag (protocolo propietario).

### 1.4 Usuarios
| Perfil | Descripción |
|---|---|
| **Técnico** | Usuario principal. Diagnostica en el taller o en prueba de ruta. |
| **Desarrollador** | Mantiene definiciones de marcas, reglas y el propio software. |

### 1.5 Entorno operativo
- **Linux** (portátil de taller) y **Android** (tablet/teléfono).
- Parque vehicular de **Chile**, multimarca. Marcas prioritarias: ver D-03.

---

## 2. Requisitos de usuario

### 2.1 Conexión y vehículo
| ID | Requisito | Prior. | Fase | Estado |
|---|---|---|---|---|
| RU-01 | Como técnico, quiero conectarme al vehículo con un adaptador estándar desde Linux o Android. | M | 1 | Aprobado |
| RU-02 | Quiero que se identifique el vehículo (VIN, protocolo, ECUs presentes) automáticamente cuando sea posible. | M | 1 | Aprobado |
| RU-03 | Quiero poder trabajar **sin vehículo** (simulador / reproducción de grabaciones) para practicar, desarrollar y analizar. | M | 1 | Aprobado |

### 2.2 Datos en vivo
| ID | Requisito | Prior. | Fase | Estado |
|---|---|---|---|---|
| RU-10 | Quiero ver **todos** los parámetros disponibles en una sola lista, sin paginación. | M | 1 | Aprobado |
| RU-11 | Quiero buscar, filtrar y ordenar los parámetros. | M | 1 | Aprobado |
| RU-12 | Quiero ver mín./máx./media de cada parámetro durante la sesión. | S | 1 | Aprobado |
| RU-13 | Quiero que los valores fuera de rango esperado se resalten. | S | 2 | Aprobado |
| RU-14 | Quiero guardar **plantillas** de parámetros por tipo de avería (ej. "mezcla pobre"). | S | 1 | Aprobado |
| RU-15 | Quiero **cambiar la unidad de visualización** de cada parámetro (ej. V ↔ mV, °C ↔ °F, kPa ↔ psi ↔ bar), y que la elección se recuerde y se aplique también a gráficas, estadísticas y exportación. | S | 1 | Aprobado |

### 2.3 Gráficas
| ID | Requisito | Prior. | Fase | Estado |
|---|---|---|---|---|
| RU-20 | Quiero graficar **muchas señales simultáneamente** (objetivo ≥ 16, ver RNF-02). | M | 1 | Aprobado |
| RU-21 | Quiero paneles apilados con **eje de tiempo sincronizado** (zoom/desplazamiento comunes). | M | 1 | Aprobado |
| RU-22 | Quiero un **cursor común** que muestre el valor de todas las señales en un mismo instante. | M | 1 | Aprobado |
| RU-23 | Quiero superponer señales en un mismo panel con ejes Y independientes. | S | 1 | Aprobado |
| RU-24 | Quiero añadir **marcadores** durante la grabación (ej. "aquí tironea"). | S | 1 | Aprobado |

### 2.4 Grabación y análisis
| ID | Requisito | Prior. | Fase | Estado |
|---|---|---|---|---|
| RU-30 | Quiero grabar sesiones de datos en vivo y reproducirlas después. | M | 1 | Aprobado |
| RU-31 | Quiero exportar sesiones a CSV. | M | 1 | Aprobado |
| RU-32 | Quiero comparar dos sesiones (antes/después, o vs. vehículo sano). | C | 4 | Aprobado |

### 2.5 Códigos de avería
| ID | Requisito | Prior. | Fase | Estado |
|---|---|---|---|---|
| RU-40 | Quiero leer y borrar códigos OBD2 genéricos (modos 03/07/0A/04). | M | 1 | Aprobado |
| RU-41 | Quiero ver el **freeze frame** asociado a cada código. | M | 1 | Aprobado |
| RU-42 | Quiero leer códigos de **todos los módulos** (ABS, SRS, BCM, TCM…) vía UDS/KWP. | M | 3 | Aprobado |

### 2.6 Mapa topológico
| ID | Requisito | Prior. | Fase | Estado |
|---|---|---|---|---|
| RU-50 | Quiero ver un **mapa topológico** de los módulos del vehículo y los buses que los conectan. | M | 3 | Aprobado |
| RU-51 | Quiero ver el estado de cada módulo por color: sin fallas / con fallas / sin respuesta / no verificado. | M | 3 | Aprobado |
| RU-52 | Quiero hacer clic en un módulo para ver sus códigos, identificación y datos en vivo. | S | 3 | Aprobado |
| RU-53 | Quiero que módulos que responden pero no están en la definición de la marca aparezcan como "desconocidos". | S | 3 | Aprobado |

### 2.7 Asistente de diagnóstico con IA
| ID | Requisito | Prior. | Fase | Estado |
|---|---|---|---|---|
| RU-60 | Quiero que el asistente razone con **contexto completo**: vehículo, códigos, freeze frame, datos en vivo, síntomas e historial. | M | 2 | Aprobado |
| RU-61 | Quiero que proponga un **plan de pruebas** ordenado por probabilidad y costo de verificación. | M | 2 | Aprobado |
| RU-62 | Quiero que pueda **solicitar datos** adicionales (leer un parámetro, grabar una prueba). | S | 2 | Aprobado |
| RU-63 | Quiero ver en qué datos se basa cada conclusión (trazabilidad, sin "caja negra"). | M | 2 | Aprobado |
| RU-64 | Quiero que funcione en español. | M | 2 | Aprobado |

### 2.8 Historial
| ID | Requisito | Prior. | Fase | Estado |
|---|---|---|---|---|
| RU-70 | Quiero un historial por vehículo (VIN/patente) con sesiones, códigos y reparaciones. | S | 4 | Aprobado |
| RU-71 | Quiero generar un informe (PDF) para el cliente. | C | 4 | Aprobado |

---

## 3. Requisitos de sistema

### 3.1 Comunicación
| ID | Requisito | Traza | Prior. | Fase | Estado |
|---|---|---|---|---|---|
| RS-01 | El sistema abstraerá el medio físico tras una interfaz `Transport` (Bluetooth SPP, BLE, WiFi/TCP, USB serie, SocketCAN). | RU-01 | M | 1 | Aprobado |
| RS-02 | El sistema abstraerá el adaptador tras una interfaz `Adapter` (ELM327/STN, CAN nativo, J2534 en el futuro). | RU-01 | M | 1 | Aprobado |
| RS-03 | El sistema soportará OBD2 sobre ISO 15765-4 (CAN 11/29 bits). Otros protocolos (K-Line, J1850) según adaptador. | RU-01 | M | 1 | Aprobado |
| RS-04 | El sistema implementará UDS (ISO 14229) sobre ISO-TP: `0x10`, `0x19`, `0x14`, `0x22`, `0x3E`. Solo servicios de **lectura** + borrado de DTC. | RU-42 | M | 3 | Aprobado |
| RS-05 | Toda la configuración de conexión (puerto, MAC, velocidad, timeouts, reintentos) vendrá de configuración, **nunca del código**. | RNF-06 | M | 1 | Aprobado |
| RS-06 | El sistema incluirá un **simulador** que implementa `Adapter` y reproduce un vehículo definido por archivo. | RU-03 | M | 1 | Aprobado |

### 3.2 Definiciones de datos (cero hardcoding)
| ID | Requisito | Traza | Prior. | Fase | Estado |
|---|---|---|---|---|---|
| RS-10 | Los PIDs OBD2 estándar (SAE J1979) se definirán en archivos de datos (YAML), con fórmula, unidad y rango. | RU-10 | M | 1 | Aprobado |
| RS-11 | Cada marca/plataforma tendrá un archivo de definición: ECUs (direcciones), buses, DIDs, DTC propietarios. | RU-42, RU-50 | M | 3 | Aprobado |
| RS-12 | Las definiciones se validarán con un **esquema** al cargar; un error indica archivo, línea y causa. | RNF-06 | M | 1 | Aprobado |
| RS-13 | Las fórmulas de conversión se expresarán en un lenguaje restringido y seguro (sin `eval` arbitrario). | RNF-05 | M | 1 | Aprobado |
| RS-14 | Las descripciones de DTC se cargarán desde bases de datos de texto intercambiables (genérica + por marca). | RU-40 | M | 1 | Aprobado |
| RS-15 | Las conversiones de unidades se definirán en un archivo de datos (`definitions/units.yaml`) agrupadas por magnitud (tensión, temperatura, presión…). Internamente se almacena siempre la unidad base de la definición; la conversión se aplica solo en presentación y exportación (la exportación indica la unidad en la cabecera). La preferencia por señal se guarda en la configuración del usuario. | RU-12, RU-15 | S | 1 | Aprobado |

### 3.3 Adquisición y almacenamiento
| ID | Requisito | Traza | Prior. | Fase | Estado |
|---|---|---|---|---|---|
| RS-20 | Un planificador de sondeo (polling) priorizará las señales visibles/graficadas sobre el resto. | RU-10, RU-20 | M | 1 | Aprobado |
| RS-21 | Cada muestra llevará marca de tiempo **monotónica** de adquisición. | RU-22 | M | 1 | Aprobado |
| RS-22 | Las sesiones se guardarán en SQLite con formato documentado y versionado. | RU-30 | M | 1 | Aprobado |
| RS-23 | Los datos se publicarán a la interfaz mediante WebSocket. | RU-10 | M | 1 | Aprobado |

### 3.4 Topología
| ID | Requisito | Traza | Prior. | Fase | Estado |
|---|---|---|---|---|---|
| RS-30 | El escaneo de topología combinará (a) ECUs declaradas en la definición de marca y (b) descubrimiento activo opcional por barrido de direcciones con `TesterPresent`. | RU-50, RU-53 | M | 3 | Aprobado |
| RS-31 | El barrido activo será configurable (rango, timeout) y **desactivado por defecto**. | RNF-04 | M | 3 | Aprobado |
| RS-32 | La disposición del grafo (buses, gateway, posición) vendrá de la definición de marca; si no existe, se usa disposición automática. | RU-50 | M | 3 | Aprobado |

### 3.5 Asistente IA
| ID | Requisito | Traza | Prior. | Fase | Estado |
|---|---|---|---|---|---|
| RS-40 | El proveedor de IA estará tras una interfaz `AIProvider`; proveedor y modelo se eligen por configuración. | RU-60 | M | 2 | Aprobado |
| RS-41 | Un **motor de reglas** determinista (reglas en YAML) pre-analizará los datos y entregará hallazgos a la IA. | RU-60, RU-63 | M | 2 | Aprobado |
| RS-42 | Se enviará a la IA un **resumen estadístico** de la sesión, no la serie completa. | RNF-03 | M | 2 | Aprobado |
| RS-43 | La IA podrá invocar herramientas definidas (`leer_parametro`, `leer_dtc`, `iniciar_grabacion`…) que siempre requieren confirmación del técnico si interactúan con el vehículo. | RU-62, RNF-04 | S | 2 | Aprobado |
| RS-44 | Las plantillas de prompt estarán en archivos, no en el código. | RNF-06 | M | 2 | Aprobado |
| RS-45 | Las claves de API se leerán de variables de entorno o almacén seguro, nunca de archivos versionados. | RNF-05 | M | 2 | Aprobado |

---

## 4. Requisitos no funcionales

| ID | Requisito | Prior. | Estado |
|---|---|---|---|
| RNF-01 | **Latencia de interfaz:** un valor nuevo se muestra en < 200 ms desde su adquisición. | M | Aprobado |
| RNF-02 | **Gráficas:** ≥ 16 señales simultáneas a 30 fps en una tablet Android de gama media. | M | Aprobado |
| RNF-03 | **Privacidad:** el VIN y datos del cliente se pueden anonimizar antes de enviarse a la IA (configurable). | M | Aprobado |
| RNF-04 | **Seguridad del vehículo:** solo servicios de lectura por defecto; toda acción con efecto requiere confirmación explícita. Nunca se envían comandos con el vehículo en movimiento salvo lectura. | M | Aprobado |
| RNF-05 | **Seguridad del software:** sin `eval` de datos externos, secretos fuera del repositorio. | M | Aprobado |
| RNF-06 | **Cero hardcoding:** constantes de protocolo estándar viven en módulos de constantes con nombre y referencia a la norma; todo lo demás (configuración, definiciones, reglas, prompts, textos) en archivos de datos. | M | Aprobado |
| RNF-07 | **Funcionamiento offline:** todo excepto el asistente IA funciona sin internet. | M | Aprobado |
| RNF-08 | **Documentación:** cada módulo con docstring de propósito; cada función pública documentada (parámetros, retorno, errores); referencias a normas (ISO/SAE) en el código de protocolo. | M | Aprobado |
| RNF-09 | **Pruebas:** cobertura ≥ 80 % en capas de protocolo y decodificación, usando el simulador. | S | Aprobado |
| RNF-10 | **Extensibilidad:** añadir una marca nueva no requiere modificar código, solo agregar un archivo de definición. | M | Aprobado |
| RNF-11 | **Idioma:** interfaz y mensajes en español; textos externalizados (i18n). | S | Aprobado |

---

## 5. Plan de fases (resumen)

| Fase | Entregable | Requisitos clave |
|---|---|---|
| **1 — MVP** | Conexión OBD2 genérica, simulador, tabla completa, gráficas sincronizadas, grabación/CSV, DTC genéricos | RU-01…03, 10…14, 20…24, 30…31, 40…41 |
| **2 — IA** | Motor de reglas + asistente con contexto y herramientas | RU-13, 60…64 |
| **3 — Multimarca** | UDS, definiciones por marca, DTC de todos los módulos, **mapa topológico** | RU-42, 50…53 |
| **4 — Taller** | Historial por vehículo, comparación de sesiones, informes | RU-32, 70…71 |

## 6. Criterios de aceptación de la Fase 1 (propuesta)
1. Con el simulador, la interfaz muestra todos los PIDs soportados en una sola tabla filtrable.
2. Se grafican 16 señales sincronizadas con cursor común, a ≥ 30 fps en Android (Chrome).
3. Una sesión grabada se reproduce de forma idéntica y se exporta a CSV.
4. Con un adaptador real (ver D-02) sobre un vehículo CAN, se leen DTC y freeze frame.
5. `grep` sobre el código no encuentra direcciones, PIDs, puertos ni textos de UI fuera de constantes/definiciones.
