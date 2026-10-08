# Metodología — Congestión y valor de GET/DLR en el SEIN

## 1. Modelo de despacho (nivel 1, incluido en la app)
- **Nodos:** 7 nodos regionales (Norte, Centro-Norte, Lima-Callao, Centro, Sur, Sur Oriente, Selva Central).
- **Enlaces:** 8 corredores de transmisión con capacidad térmica de referencia (MW).
- **Formulación:** LOPF de transporte (sin pérdidas, sin AC) con HiGHS (vía `scipy.optimize.linprog`):
  min Σ c·g + C_falla·u  s.a. balance nodal (dual = precio nodal), |f| ≤ F̄·(1+GET), 0 ≤ g ≤ P̄·perfil.
- **Horizonte:** 24 h de un día representativo; perfiles de demanda, solar, eólica e hidro en `sein_perfiles_horarios.csv`.
- **Escenarios:** crecimiento de demanda, ENSO (factor hidro), multiplicadores solar/eólica, incremento de capacidad por GET/DLR.
- **Salidas:** LMP por nodo y hora, horas de congestión por enlace, renta de congestión, energía no servida, valor de la GET.

## 2. Valor de GET/DLR
Ahorro de despacho = Costo_total(base) − Costo_total(con GET). Se anualiza multiplicando por días/año
(supuesto de repetición del día representativo; **orientativo**).

## 3. Niveles previstos (no incluidos todavía)
- **Nivel 2 — Red real:** snapshot OSM depurado (`tools/build_osm_snapshot.py`) + enlace de nodos a subestaciones
  reales, con parámetros R/X y MVA por tensión; flujo DC/AC con PyPSA o pandapower.
- **Nivel 3 — Seguridad:** análisis N-1, flujo AC, tensiones, estabilidad (con datos del COES).
- **Nivel 4 — DLR:** series de temperatura ambiente, viento y carga por línea para estimar la capacidad dinámica
  (IEEE 738 / CIGRE) y su distribución horaria.

## 4. Limitaciones
Todos los parámetros marcados como ESTIMADO en `data/reference/*.csv` son supuestos de trabajo. Las
resultados cuantitativos deben validarse con datos oficiales del COES y OSINERGMIN antes de usarse en informes.
