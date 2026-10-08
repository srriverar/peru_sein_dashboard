#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arcgis_fetch.py — descarga genérica de capas ArcGIS REST (FeatureServer / MapServer)
a GeoJSON + CSV, sin geopandas ni arcpy. Pensado para alimentar el dashboard de
Colombia (y cualquier otro) con datos georreferenciados oficiales.

Uso rápido
----------
    # listar las capas de un servicio
    python3 arcgis_fetch.py --list https://services1.arcgis.com/lHSB5M3vxFT82S7P/ArcGIS/rest/services/P_Redes_Energia_GE3/FeatureServer

    # descargar una capa completa (paginada) a GeoJSON WGS84
    python3 arcgis_fetch.py --layer https://.../FeatureServer/17 --out data/epm_transmision

    # comprobar qué endpoints del registro están vivos
    python3 arcgis_fetch.py --check

    # descargar todas las capas del registro marcadas como "core"
    python3 arcgis_fetch.py --registry core --outdir data/colombia

API
---
    from arcgis_fetch import service_layers, fetch_layer, layer_count
    gj = fetch_layer("https://.../FeatureServer/17", where="TENSION_CONN>=110")

Licencia: MIT. Respete la licencia de cada fuente (ver CATALOGO_GEODATA_COLOMBIA.md).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (compatible; grid-dashboard/1.0; +https://github.com/srriverar)"
TIMEOUT = 120


# ─────────────────────────── registro de capas Colombia ───────────────────────────
# tier: "core" = infraestructura del SIN/STN; "or" = operadores de red (distribución);
#       "ref" = capas de referencia territorial/ambiental
REGISTRO: list[dict] = [
    # ---- UPME (autoridad de planeación) ----
    dict(id="upme_lineas_construidas", tier="core", fuente="UPME",
         nombre="Sistema de transmisión: líneas construidas (STN/STR)",
         url="https://geo.upme.gov.co/server/rest/services/Capas_EnergiaElectrica/"
             "Sistema_transmision_lineas_construidas/FeatureServer/17",
         licencia="CC BY 2.0", geom="polyline"),
    dict(id="upme_subestaciones", tier="core", fuente="UPME",
         nombre="Subestaciones construidas STN - STR",
         url="https://energia-upme.hub.arcgis.com/datasets/subestaciones-construidas-stn-str",
         licencia="CC BY", geom="point",
         nota="Hub de descarga: usar el botón Download (GeoJSON/SHP/CSV) o su FeatureServer asociado."),
    dict(id="upme_simec_subestaciones", tier="core", fuente="UPME/SIMEC",
         nombre="APP_SUBESTACIONES (ArcGIS Server heredado)",
         url="http://arcgis.simec.gov.co:6080/arcgis/rest/services/APP_SUBESTACIONES/MapServer",
         licencia="Uso público", geom="point"),
    # ---- EPM (Antioquia): red real de distribución + transmisión ----
    dict(id="epm_conductor_transmision", tier="or", fuente="EPM",
         nombre="Conductor de transmisión",
         url="https://services1.arcgis.com/lHSB5M3vxFT82S7P/ArcGIS/rest/services/"
             "P_Redes_Energia_GE3/FeatureServer/17", licencia="Datos abiertos EPM", geom="polyline"),
    dict(id="epm_conductor_primario", tier="or", fuente="EPM",
         nombre="Conductor primario (media tensión)",
         url="https://services1.arcgis.com/lHSB5M3vxFT82S7P/ArcGIS/rest/services/"
             "P_Redes_Energia_GE3/FeatureServer/13", licencia="Datos abiertos EPM", geom="polyline"),
    dict(id="epm_conductor_secundario", tier="or", fuente="EPM",
         nombre="Conductor secundario (baja tensión)",
         url="https://services1.arcgis.com/lHSB5M3vxFT82S7P/ArcGIS/rest/services/"
             "P_Redes_Energia_GE3/FeatureServer/12", licencia="Datos abiertos EPM", geom="polyline"),
    dict(id="epm_subestaciones", tier="or", fuente="EPM",
         nombre="Subestaciones (polígono)",
         url="https://services1.arcgis.com/lHSB5M3vxFT82S7P/ArcGIS/rest/services/"
             "P_Redes_Energia_GE3/FeatureServer/14", licencia="Datos abiertos EPM", geom="polygon"),
    dict(id="epm_transformadores", tier="or", fuente="EPM",
         nombre="Transformadores",
         url="https://services1.arcgis.com/lHSB5M3vxFT82S7P/ArcGIS/rest/services/"
             "P_Redes_Energia_GE3/FeatureServer/4", licencia="Datos abiertos EPM", geom="point"),
    dict(id="epm_torres", tier="or", fuente="EPM",
         nombre="Torres de transmisión",
         url="https://services1.arcgis.com/lHSB5M3vxFT82S7P/ArcGIS/rest/services/"
             "P_Redes_Energia_GE3/FeatureServer/16", licencia="Datos abiertos EPM", geom="point"),
    dict(id="epm_postes", tier="or", fuente="EPM",
         nombre="Postes",
         url="https://services1.arcgis.com/lHSB5M3vxFT82S7P/ArcGIS/rest/services/"
             "P_Redes_Energia_GE3/FeatureServer/7", licencia="Datos abiertos EPM", geom="point"),
    # ---- Referencia territorial ----
    dict(id="dane_mgn_departamentos", tier="ref", fuente="DANE",
         nombre="Marco Geoestadístico Nacional — departamentos/municipios",
         url="https://geoportal.dane.gov.co/servicios/descarga-y-metadatos/descarga-mgn-marco-geoestadistico-nacional/",
         licencia="Datos abiertos", geom="polygon",
         nota="Descarga directa de shapefile; no es servicio REST."),
]


# ───────────────────────────────── utilidades HTTP ─────────────────────────────────
def _get(url: str, params: dict | None = None, retries: int = 3) -> bytes:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"GET falló: {url} → {last}")


def _get_json(url: str, params: dict | None = None) -> dict:
    p = {"f": "json"}
    p.update(params or {})
    return json.loads(_get(url, p).decode("utf-8", "replace"))


# ───────────────────────────────── API principal ─────────────────────────────────
def service_layers(service_url: str) -> list[dict]:
    """Lista las capas/tablas de un FeatureServer o MapServer."""
    d = _get_json(service_url.rstrip("/"))
    out = []
    for lyr in (d.get("layers") or []) + (d.get("tables") or []):
        out.append({"id": lyr.get("id"), "name": lyr.get("name"),
                    "geometryType": lyr.get("geometryType")})
    return out


def layer_info(layer_url: str) -> dict:
    d = _get_json(layer_url.rstrip("/"))
    return {"name": d.get("name"), "geometryType": d.get("geometryType"),
            "maxRecordCount": d.get("maxRecordCount", 1000),
            "fields": [f["name"] for f in d.get("fields", [])],
            "wkid": (d.get("extent") or {}).get("spatialReference", {}).get("latestWkid")}


def layer_count(layer_url: str, where: str = "1=1") -> int:
    d = _get_json(layer_url.rstrip("/") + "/query",
                  {"where": where, "returnCountOnly": "true"})
    return int(d.get("count", 0))


def fetch_layer(layer_url: str, where: str = "1=1", out_sr: int = 4326,
                fields: str = "*", page: int | None = None,
                max_records: int | None = None, verbose: bool = True) -> dict:
    """Descarga una capa completa paginando por resultOffset. Devuelve un FeatureCollection."""
    layer_url = layer_url.rstrip("/")
    info = layer_info(layer_url)
    page = page or min(int(info["maxRecordCount"] or 1000), 2000)
    total = layer_count(layer_url, where)
    if verbose:
        print(f"  · {info['name']}: {total} registros (página {page})", file=sys.stderr)
    feats: list[dict] = []
    offset = 0
    while offset < total:
        d = _get_json(layer_url + "/query", {
            "where": where, "outFields": fields, "outSR": out_sr,
            "returnGeometry": "true", "f": "geojson",
            "resultOffset": offset, "resultRecordCount": page,
        })
        got = d.get("features", [])
        if not got:
            break
        feats.extend(got)
        offset += len(got)
        if verbose:
            print(f"    {offset}/{total}", file=sys.stderr)
        if max_records and len(feats) >= max_records:
            feats = feats[:max_records]
            break
    return {"type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": f"EPSG:{out_sr}"}},
            "metadata": {"source": layer_url, "layer": info["name"], "count": len(feats)},
            "features": feats}


def geojson_to_csv(gj: dict, path: str) -> int:
    """Vuelca los atributos + un centroide/primer vértice a CSV (para inspección rápida)."""
    rows = []
    for f in gj.get("features", []):
        p = dict(f.get("properties") or {})
        g = f.get("geometry") or {}
        c = _first_coord(g.get("coordinates"))
        p["_lon"], p["_lat"] = (c if c else (None, None))
        p["_geom_type"] = g.get("type")
        rows.append(p)
    if not rows:
        return 0
    cols = list({k for r in rows for k in r})
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def _first_coord(c):
    while isinstance(c, list) and c and isinstance(c[0], list):
        c = c[0]
    if isinstance(c, list) and len(c) >= 2 and all(isinstance(v, (int, float)) for v in c[:2]):
        return c[0], c[1]
    return None


def check_endpoint(url: str) -> str:
    try:
        d = _get_json(url.rstrip("/"))
        if "error" in d:
            return f"ERROR {d['error'].get('code')}"
        n = len(d.get("layers") or []) + len(d.get("tables") or [])
        return f"OK ({n} capas)" if n else f"OK ({d.get('name', 'capa')})"
    except Exception as e:  # noqa: BLE001
        return f"INACCESIBLE ({type(e).__name__})"


# ────────────────────────────────────── CLI ──────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", metavar="SERVICE_URL", help="lista las capas de un servicio")
    ap.add_argument("--layer", metavar="LAYER_URL", help="descarga una capa")
    ap.add_argument("--where", default="1=1")
    ap.add_argument("--max", type=int, default=None, help="límite de registros (pruebas)")
    ap.add_argument("--out", default=None, help="prefijo de salida (.geojson + .csv)")
    ap.add_argument("--check", action="store_true", help="prueba de vida del registro")
    ap.add_argument("--registry", choices=["core", "or", "ref", "all"], help="descarga por lote")
    ap.add_argument("--outdir", default="data/colombia")
    a = ap.parse_args()

    if a.list:
        for l in service_layers(a.list):
            print(f"{l['id']:>4} | {l['name']} | {l['geometryType']}")
        return 0

    if a.check:
        print(f"{'id':<28} {'fuente':<10} estado")
        for r in REGISTRO:
            if "/rest/services" not in r["url"]:
                print(f"{r['id']:<28} {r['fuente']:<10} (descarga directa, no REST)")
                continue
            print(f"{r['id']:<28} {r['fuente']:<10} {check_endpoint(r['url'])}")
        return 0

    if a.registry:
        os.makedirs(a.outdir, exist_ok=True)
        for r in REGISTRO:
            if a.registry != "all" and r["tier"] != a.registry:
                continue
            if "/rest/services" not in r["url"]:
                continue
            print(f"▶ {r['id']} — {r['nombre']}")
            try:
                gj = fetch_layer(r["url"], max_records=a.max)
                base = os.path.join(a.outdir, r["id"])
                json.dump(gj, open(base + ".geojson", "w", encoding="utf-8"), ensure_ascii=False)
                n = geojson_to_csv(gj, base + ".csv")
                print(f"  ✓ {n} registros → {base}.geojson / .csv")
            except Exception as e:  # noqa: BLE001
                print(f"  ✗ {e}")
        return 0

    if a.layer:
        gj = fetch_layer(a.layer, where=a.where, max_records=a.max)
        base = a.out or "capa"
        os.makedirs(os.path.dirname(base) or ".", exist_ok=True)
        json.dump(gj, open(base + ".geojson", "w", encoding="utf-8"), ensure_ascii=False)
        n = geojson_to_csv(gj, base + ".csv")
        print(f"✓ {n} registros → {base}.geojson / {base}.csv")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
