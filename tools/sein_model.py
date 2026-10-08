"""
sein_model.py — Modelo de despacho económico y congestión del SEIN (7 nodos).

Formulación: flujo de transporte (NTC) con optimización lineal (HiGHS vía scipy).
  min   Σ_t Σ_n Σ_k c_k · g[t,n,k]  +  C_falla · Σ_t Σ_n u[t,n]
  s.a.  Balance nodal:   Σ_k g[t,n,k] + u[t,n] + Σ_in f − Σ_out f = D[t,n]   (dual = precio nodal)
        Flujo acotado:  |f[t,l]| ≤ F̄_l · (1 + incremento_GET)
        Disponibilidad: 0 ≤ g[t,n,k] ≤ P̄[n,k] · perfil[t,k] · factor_ENSO(k)

Limitaciones (importantes para el estudio):
  · No modela flujo AC/DC ni pérdidas; sirve para identificar corredores congestionados
    y estimar el valor económico de incrementar capacidad (DLR / repotenciación / GET).
  · Los parámetros nodales son ESTIMADOS a partir de totales oficiales (ver data/reference/*.csv).
  · Para estudio de red completo use la red OSM depurada + PyPSA/pandapower (ver doc/METODOLOGIA.md).
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "data", "reference")

TECNOLOGIAS = ["hidro", "termo", "eolica", "solar"]
COSTO_FALLA = 1000.0  # USD/MWh — valor de falla (racionamiento)

# Factor de hidrología según escenario ENSO (aplicado a la energía hidráulica disponible)
FACTOR_ENSO = {"Niño fuerte": 0.70, "Niño moderado": 0.85, "Normal": 1.00, "Niña": 1.05}


def cargar_nodos() -> pd.DataFrame:
    return pd.read_csv(os.path.join(REF, "sein_nodos.csv"))


def cargar_enlaces() -> pd.DataFrame:
    return pd.read_csv(os.path.join(REF, "sein_enlaces.csv"))


def cargar_perfiles() -> pd.DataFrame:
    return pd.read_csv(os.path.join(REF, "sein_perfiles_horarios.csv"))


def run_dispatch(
    nodos: pd.DataFrame,
    enlaces: pd.DataFrame,
    perfiles: pd.DataFrame,
    crecimiento_demanda: float = 0.0,   # 0.05 = +5 %
    escenario_enso: str = "Normal",
    factor_solar: float = 1.0,          # multiplicador de capacidad solar (ej. 1.5 = +50 %)
    factor_eolica: float = 1.0,
    incremento_get: float = 0.0,        # 0.20 = +20 % de capacidad de líneas (DLR / repotenciación)
    demanda_total_mw: float | None = None,
    costo_falla: float = COSTO_FALLA,
) -> dict:
    """Resuelve el despacho horario de 24 h y devuelve precios, flujos y congestión."""
    n_nod = len(nodos)
    ids = nodos["id"].tolist()
    idx = {nid: i for i, nid in enumerate(ids)}
    T = len(perfiles)
    L = len(enlaces)

    # ── Demanda nodal (normalizada al pico coincidente oficial, si se indica) ──
    d_base = nodos["demanda_max_mw_est"].to_numpy(float)
    externo = nodos["externo"].to_numpy(int) if "externo" in nodos.columns else np.zeros(n_nod, int)
    interno = externo == 0
    if demanda_total_mw is None:
        demanda_total_mw = 7941.78  # máxima demanda SEIN 2025 (OSINERGMIN)
    # Los nodos internos se reescalan al pico oficial; los externos (p.ej. Ecuador) mantienen su valor
    d_base = np.where(interno, d_base / d_base[interno].sum() * demanda_total_mw * (1 + crecimiento_demanda), d_base)
    dem = np.outer(perfiles["demanda_pu"].to_numpy(float), d_base)  # T x N

    # ── Capacidades nodales por tecnología ──
    cap = {
        "hidro": nodos["hidro_mw"].to_numpy(float),
        "termo": nodos["termo_mw"].to_numpy(float),
        "eolica": nodos["eolica_mw"].to_numpy(float) * factor_eolica,
        "solar": nodos["solar_mw"].to_numpy(float) * factor_solar,
    }
    costo = {
        "hidro": nodos["costo_hidro_usd_mwh"].to_numpy(float),
        "termo": nodos["costo_termo_usd_mwh"].to_numpy(float),
        "eolica": np.zeros(n_nod),
        "solar": np.zeros(n_nod),
    }
    perfil = {
        "hidro": perfiles["hidro_pu"].to_numpy(float) * FACTOR_ENSO.get(escenario_enso, 1.0),
        "termo": np.ones(T),
        "eolica": perfiles["eolica_pu"].to_numpy(float),
        "solar": perfiles["solar_pu"].to_numpy(float),
    }

    # ── Variables: g[t,n,k] | f[t,l] | u[t,n] ──
    gen_pairs = [(n, k) for n in range(n_nod) for k in range(len(TECNOLOGIAS))
                 if cap[TECNOLOGIAS[k]][n] > 0]
    ng = T * len(gen_pairs)
    nf = T * L
    nu = T * n_nod
    nv = ng + nf + nu

    def gi(t, p):
        return t * len(gen_pairs) + p

    def fi(t, l):
        return ng + t * L + l

    def ui(t, n):
        return ng + nf + t * n_nod + n

    c = np.zeros(nv)
    bounds = [(0, None)] * nv
    for t in range(T):
        for p, (n, k) in enumerate(gen_pairs):
            tec = TECNOLOGIAS[k]
            c[gi(t, p)] = costo[tec][n]
            pmax = cap[tec][n] * perfil[tec][t]
            bounds[gi(t, p)] = (0, max(pmax, 0.0))
        for l in range(L):
            cap_l = enlaces["capacidad_mw_est"].iloc[l] * (1 + incremento_get)
            bounds[fi(t, l)] = (-cap_l, cap_l)
        for n in range(n_nod):
            c[ui(t, n)] = costo_falla
            bounds[ui(t, n)] = (0, None)

    # ── Restricciones de balance nodal (igualdad) ──
    A = lil_matrix((T * n_nod, nv))
    b = np.zeros(T * n_nod)
    desde = [idx[x] for x in enlaces["desde"]]
    hasta = [idx[x] for x in enlaces["hasta"]]
    for t in range(T):
        for n in range(n_nod):
            r = t * n_nod + n
            b[r] = dem[t, n]
            for p, (nn, k) in enumerate(gen_pairs):
                if nn == n:
                    A[r, gi(t, p)] = 1.0
            A[r, ui(t, n)] = 1.0
            for l in range(L):
                if hasta[l] == n:      # flujo entrante
                    A[r, fi(t, l)] = 1.0
                if desde[l] == n:      # flujo saliente
                    A[r, fi(t, l)] = -1.0

    res = linprog(c, A_eq=A.tocsr(), b_eq=b, bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError(f"Optimización no factible: {res.message}")

    # Precio nodal = dual de balance (sensibilidad del costo al consumo nodal)
    lmp = np.array(res.eqlin.marginals).reshape(T, n_nod)
    lmp = np.clip(lmp, 0, costo_falla)

    x = res.x
    flujos = np.array([[x[fi(t, l)] for l in range(L)] for t in range(T)])
    gen_tot = np.zeros((T, n_nod, len(TECNOLOGIAS)))
    for t in range(T):
        for p, (n, k) in enumerate(gen_pairs):
            gen_tot[t, n, k] = x[gi(t, p)]
    falla = np.array([[x[ui(t, n)] for n in range(n_nod)] for t in range(T)])

    # ── Congestión: líneas en límite (|f| ≥ 99.5 % de capacidad) ──
    cap_eff = enlaces["capacidad_mw_est"].to_numpy(float) * (1 + incremento_get)
    loading = np.abs(flujos) / cap_eff
    congestionada = loading >= 0.995
    horas_cong = congestionada.sum(axis=0)
    # Renta de congestión = Σ_t Σ_l f·(π_hasta − π_desde)
    renta_cong = 0.0
    for t in range(T):
        for l in range(L):
            renta_cong += flujos[t, l] * (lmp[t, hasta[l]] - lmp[t, desde[l]])

    resumen_lineas = pd.DataFrame({
        "id": enlaces["id"], "corredor": enlaces["corredor"],
        "tension_kv": enlaces["tension_kv"],
        "capacidad_MW": cap_eff.round(0),
        "flujo_max_MW": np.abs(flujos).max(axis=0).round(0),
        "utilizacion_media_%": (loading.mean(axis=0) * 100).round(1),
        "horas_congestionada": horas_cong,
        "diferencia_precio_media_USD": np.mean(
            lmp[:, [hasta[l] for l in range(L)]] - lmp[:, [desde[l] for l in range(L)]], axis=0
        ).round(2),
    })

    precios = pd.DataFrame(lmp, columns=ids)
    precios.insert(0, "hora", perfiles["hora"].to_numpy())

    gen_por_tec = pd.DataFrame({
        "hora": perfiles["hora"].to_numpy(),
        **{tec: gen_tot[:, :, k].sum(axis=1) for k, tec in enumerate(TECNOLOGIAS)},
        "falla_MW": falla.sum(axis=1),
        "demanda_MW": dem.sum(axis=1),
    })

    flujos_df = pd.DataFrame(flujos, columns=enlaces["id"].tolist())
    flujos_df.insert(0, "hora", perfiles["hora"].to_numpy())

    return {
        "estado": res.message,
        "precios": precios,
        "gen_tecnologia": gen_por_tec,
        "flujos": flujos_df,
        "lineas": resumen_lineas,
        "renta_congestion_MUSD": renta_cong / 1e6,
        "energia_falla_MWh": float(falla.sum()),
        "costo_total_MUSD": float(res.fun) / 1e6,
        "lmp_medio": pd.Series(lmp.mean(axis=0), index=ids),
        "demanda_nodal_MW": pd.Series(d_base, index=ids),
        "energia_no_servida_pct": float(falla.sum() / max(dem.sum(), 1) * 100),
    }
