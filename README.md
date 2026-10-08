# 🇵🇪 Dashboard SEIN Perú — Congestión, Corredores y Capacidad de Transmisión

Plataforma abierta para el análisis del **Sistema Eléctrico Interconectado Nacional (SEIN)** del Perú:
precios nodales, congestión de corredores y valor de tecnologías de incremento de capacidad
(**Dynamic Line Rating – DLR**, repotenciación de conductores y otras **Grid Enhancing Technologies – GET**).

Adaptado a partir del *Dashboard SIN Nodal* (Colombia), manteniendo su arquitectura:
`app.py` (interfaz y páginas) + `tools/` (modelo, GIS, snapshot OSM) + `data/` (insumos) + `doc/` (metodología).

## 🎯 Páginas

| # | Página | Contenido |
|---|---|---|
| 1 | 🏠 Inicio | Indicadores oficiales 2025-2026, matriz, resultado rápido del modelo |
| 2 | 🗺️ Mapa del SEIN | Red OSM (500/220 kV, subestaciones, centrales) o red nodal; límites departamentales |
| 3 | ⚡ Arquitectura | Capacidad por nodo y tecnología, balance por zona, cartera COES |
| 4 | 🔴 Congestión y GET | Despacho horario 24 h, LMP nodales, horas de congestión, valor de GET/DLR |
| 5 | 🌊 ENSO e hidrología | Índice ONI, efecto simulado de El Niño / La Niña sobre precios y congestión |
| 6 | 🗄️ Datos Perú | Catálogo de fuentes oficiales y abiertas, filtrable y descargable |
| 7 | 📋 Política y regulación | Marco normativo y preguntas de política para el estudio |
| 8 | 🤝 Colaboración | Plantillas de datos, prioridades abiertas, cómo contribuir, licencias |

## 🚀 Ejecución local

```bash
git clone <URL_DEL_REPOSITORIO>
cd peru_sein_dashboard
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Para regenerar la red desde OpenStreetMap (opcional, requiere conexión a Overpass):

```bash
python3 tools/build_osm_snapshot.py
```

## 🧭 Datos de entrada (editables)

| Archivo | Contenido | Estado |
|---|---|---|
| `data/reference/sein_nodos.csv` | 7 nodos: demanda, capacidad por tecnología, costos | **Estimado** a partir de totales oficiales |
| `data/reference/sein_enlaces.csv` | 8 corredores con capacidad térmica | **Estimado** (verificar con COES) |
| `data/reference/sein_perfiles_horarios.csv` | Perfiles horarios de demanda, solar, eólica, hidro | Supuesto representativo |
| `data/reference/sein_indicadores.csv` | Cifras oficiales: energía, demanda, capacidad, cartera, líneas | Oficial (con fuente en cada fila) |
| `data/reference/sein_tecnologia_2026.csv` | Capacidad instalada por tecnología (jul-2026) | Oficial (vía prensa especializada) |
| `data/reference/oni_noaa.csv` | Índice ONI mensual (NOAA/CPC) | Oficial |
| `data/geo/*.geojson` | Snapshot OpenStreetMap (ODbL) | Generado por `build_osm_snapshot.py` |

Todas las cifras con estado *Estimado* se marcan en la app. Consulte `doc/VALIDACION_PERU.md`.

## 📚 Fuentes principales

- COES — https://www.coes.org.pe (planes de transmisión, EPO, demanda)
- OSINERGMIN — https://www.osinergmin.gob.pe (fichas técnicas de líneas, compendios)
- MINEM — https://www.gob.pe/minem
- NOAA CPC — índice ONI
- OpenStreetMap (ODbL) · geoBoundaries (límites)

## ⚖️ Alcance y limitaciones

Es un instrumento de **estudio y prueba de concepto** con fines educativos y de investigación. El modelo es de
transporte (sin flujo AC ni pérdidas). Los resultados cuantitativos deben validarse con datos oficiales antes de
usarse en informes o decisiones de inversión. Ver `doc/METODOLOGIA.md`.

## 🤝 Colaboración

Lea [CONTRIBUTING.md](CONTRIBUTING.md). Las contribuciones de datos con fuente son bienvenidas.

## 👤 Autor

Marco metodológico y dashboard base: **Prof. Sergio Rivera** — Universidad Nacional de Colombia.
