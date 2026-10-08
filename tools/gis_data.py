"""
gis_data.py — acceso a la capa geoespacial del SEIN peruano.

Fuentes (todas en data/geo/ y data/reference/):
  · lineas_osm.geojson, subestaciones_osm.geojson, centrales_osm.geojson, kpis_osm.json
    → generados por tools/build_osm_snapshot.py (OpenStreetMap, ODbL)
  · peru_departamentos.geojson → límites departamentales (INEI/datos públicos, simplificados)
  · peru_boundary.geojson      → contorno nacional (geoBoundaries ADM0, CC BY 4.0 / dominio público)

Si el snapshot OSM no existe, disponible() devuelve False y la app usa la red nodal de sein_enlaces.csv.
"""
from __future__ import annotations

import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO = os.path.join(ROOT, "data", "geo")
REF = os.path.join(ROOT, "data", "reference")

# Límites del territorio peruano (continental + insular), para encuadre de mapas
EXTENT = dict(lat_min=-18.4, lat_max=0.1, lon_min=-81.4, lon_max=-68.6)


def _read(nombre: str):
    ruta = os.path.join(GEO, nombre)
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def disponible() -> bool:
    return os.path.exists(os.path.join(GEO, "lineas_osm.geojson"))


def kpis() -> dict:
    return _read("kpis_osm.json") or {}


def _df(nombre: str) -> pd.DataFrame:
    gj = _read(nombre)
    if not gj:
        return pd.DataFrame()
    return pd.DataFrame([f["properties"] | {"geometry": f["geometry"]} for f in gj["features"]])


def lineas_df() -> pd.DataFrame:
    df = _df("lineas_osm.geojson")
    if not df.empty:
        df["_coords"] = df["geometry"].map(lambda g: [tuple(p) for p in g["coordinates"]])
    return df


def subestaciones_df() -> pd.DataFrame:
    df = _df("subestaciones_osm.geojson")
    if not df.empty:
        df["lon"] = df["geometry"].map(lambda g: g["coordinates"][0])
        df["lat"] = df["geometry"].map(lambda g: g["coordinates"][1])
    return df


def centrales_df() -> pd.DataFrame:
    df = _df("centrales_osm.geojson")
    if not df.empty:
        df["lon"] = df["geometry"].map(lambda g: g["coordinates"][0])
        df["lat"] = df["geometry"].map(lambda g: g["coordinates"][1])
    return df


def departamentos() -> dict | None:
    return _leer_ref("peru_departamentos.geojson")


def _leer_ref(nombre: str):
    ruta = os.path.join(REF, nombre)
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def filtrar_lineas(df: pd.DataFrame, tiers=None, kv_min: float = 0.0, kv_max: float = 1e6,
                   texto: str = "", operador: str = "") -> pd.DataFrame:
    if df.empty:
        return df
    m = (df["kv"] >= kv_min) & (df["kv"] <= kv_max)
    if tiers:
        m &= df["tier"].isin(tiers)
    if texto:
        t = texto.lower()
        m &= df["nombre"].str.lower().str.contains(t, na=False) | \
             df["operador"].str.lower().str.contains(t, na=False)
    if operador and operador != "Todos":
        m &= df["operador"] == operador
    return df[m]
