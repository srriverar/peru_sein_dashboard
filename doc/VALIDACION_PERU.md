# Validación cruzada de datos — SEIN Perú

| Indicador | Valor de la app | Fuente de contraste | Estado |
|---|---|---|---|
| Energía producida 2025 | 61 244 GWh | OSINERGMIN, compendio CGENC/EPO | Oficial |
| Máxima demanda 2025 | 7 941,78 MW | OSINERGMIN, compendio CGENC/EPO | Oficial |
| Capacidad instalada jul-2026 | 14 492 MW (hidro 5 343; termo 7 032; eólica 1 021; solar 1 095) | OSINERGMIN vía Energía Estratégica | Oficial (prensa) |
| Suma nodal de termo | 7 050 MW | Diferencia 0,3 % vs 7 032 MW | Cuadra |
| Suma nodal de demanda | 7 950 MW | Se reescala al pico oficial | Cuadra |
| Línea 500 kV Mantaro–Marcona–Socabaya–Montalvo | 918 km | ISA (Transmantaro) | Oficial |
| Líneas 500 kV Ocoña–Montalvo / Poroma–Marcona / Montalvo–Moquegua | 357 / 272 / 255 km | Fichas OSINERGMIN | Oficial |
| Capacidades de enlaces | Valores ESTIMADOS | Pendiente COES | **Pendiente** |
| Distribución nodal de capacidad | ESTIMADO | Pendiente tabla de centrales COES | **Pendiente** |
| Red OSM 500 kV | 22 tramos, 2 938 km de ruta (snapshot 2026-10-08) | COES: infografía PT 2017-2026 reporta 3 371 km de 500 kV (incl. proyectos) | Parcial: el OSM no incluye todo el trazado; revisar tramos faltantes |
| Red OSM total | 551 tramos, 16 288 km de ruta, 7 241 subestaciones, 208 centrales (OSM) | Sin cifra oficial directa de referencia | Snapshot generado; calidad de atributos (operador, tensión) incompleta |

Para cerrar la validación: (1) generar el snapshot OSM, (2) reemplazar los valores ESTIMADO con tablas COES,
(3) registrar aquí la fecha y la fuente de cada cambio.
