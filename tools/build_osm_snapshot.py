#!/usr/bin/env python3
"""
build_osm_snapshot.py — construye el snapshot geoespacial de la red eléctrica de
Perú a partir de OpenStreetMap (Overpass API) y lo deja en data/geo/.

Salidas:
    data/geo/lineas_osm.geojson        líneas (power=line con tag voltage)
    data/geo/subestaciones_osm.geojson subestaciones (nodo/way → centroide)
    data/geo/centrales_osm.geojson     centrales (power=plant → centroide)
    data/geo/kpis_osm.json             KPIs agregados y metadatos del corte

Uso:
    python3 tools/build_osm_snapshot.py            # descarga y reconstruye
    python3 tools/build_osm_snapshot.py --cache /tmp   # usa JSON ya descargados

Datos © colaboradores de OpenStreetMap, licencia ODbL.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.geo_utils import douglas_peucker, haversine_m, polyline_length_m  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "geo")
MIRRORS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]

Q_LINES = """[out:json][timeout:600];
area["ISO3166-1"="PE"][admin_level=2]->.co;
way["power"="line"]["voltage"](area.co);
out geom;"""

Q_SUBS = """[out:json][timeout:600];
area["ISO3166-1"="PE"][admin_level=2]->.co;
(node["power"="substation"](area.co);way["power"="substation"](area.co););
out center tags;"""

Q_PLANTS = """[out:json][timeout:600];
area["ISO3166-1"="PE"][admin_level=2]->.co;
(way["power"="plant"](area.co);relation["power"="plant"](area.co););
out center tags;"""

# Escalones de tensión del SEIN peruano (kV) → color del mapa/póster
TIERS = [(500, "500 kV", "#D62728"), (230, "220/230 kV", "#FF7F0E"),
         (110, "110/115 kV", "#FFD100"), (57.5, "57.5/66 kV", "#2CA02C"),
         (30, "34.5 kV", "#17A2B8"), (0, "≤ 13.8 kV", "#7F7F7F")]


def overpass(query: str, tries: int = 6) -> dict:
    last = None
    for i in range(tries):
        m = MIRRORS[i % len(MIRRORS)]
        try:
            req = urllib.request.Request(
                m, data=urllib.parse.urlencode({"data": query}).encode(),
                headers={"User-Agent": "peru-sein-dashboard/2.0"})
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  reintento {i} ({m.split('/')[2]}): {type(e).__name__}", file=sys.stderr)
            time.sleep(8)
    raise RuntimeError(f"Overpass falló: {last}")


def parse_kv(v) -> float:
    """'115000;34500' → 115.0 (kV). Devuelve 0 si no se puede interpretar."""
    if not v:
        return 0.0
    best = 0.0
    for tok in re.split(r"[;,|/]", str(v)):
        tok = tok.strip().replace(" ", "")
        if not tok:
            continue
        try:
            val = float(re.sub(r"[^0-9.]", "", tok) or 0)
        except ValueError:
            continue
        if val > 2000:      # viene en voltios
            val /= 1000.0
        best = max(best, val)
    return best


def parse_mw(tags: dict) -> float:
    for k in ("plant:output:electricity", "generator:output:electricity", "power_output"):
        v = tags.get(k)
        if not v:
            continue
        s = str(v).lower().replace(" ", "")
        try:
            if "gw" in s:
                return float(re.sub(r"[^0-9.]", "", s)) * 1000
            if "kw" in s:
                return float(re.sub(r"[^0-9.]", "", s)) / 1000
            return float(re.sub(r"[^0-9.]", "", s))
        except ValueError:
            continue
    return 0.0


def tier_of(kv: float):
    for umbral, etiqueta, color in TIERS:
        if kv >= umbral:
            return etiqueta, color
    return "≤ 13.8 kV", "#7F7F7F"


def build(cache: str | None = None, tol_deg: float = 3e-4):
    os.makedirs(OUT, exist_ok=True)

    def _load(name, query):
        if cache and os.path.exists(os.path.join(cache, name)):
            print(f"· cache {name}")
            return json.load(open(os.path.join(cache, name)))
        print(f"· Overpass {name}")
        return overpass(query)

    raw_l = _load("pe_lines.json", Q_LINES)
    raw_s = _load("pe_subs.json", Q_SUBS)
    raw_p = _load("pe_plants.json", Q_PLANTS)

    # ── líneas ──
    feats, tot_km, tot_vert = [], 0.0, 0
    por_tier: dict[str, dict] = {}
    operadores: dict[str, float] = {}
    for el in raw_l["elements"]:
        geom = el.get("geometry") or []
        if len(geom) < 2:
            continue
        coords = [(g["lon"], g["lat"]) for g in geom]
        t = el.get("tags", {})
        kv = parse_kv(t.get("voltage"))
        km = polyline_length_m(coords) / 1000.0
        etiqueta, color = tier_of(kv)
        try:
            cct = int(re.sub(r"[^0-9]", "", str(t.get("circuits", "1"))) or 1)
        except ValueError:
            cct = 1
        op = (t.get("operator") or "sin dato").strip()
        simp = douglas_peucker(coords, tol_deg)
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[round(x, 5), round(y, 5)] for x, y in simp]},
            "properties": {
                "id": el["id"], "nombre": t.get("name", ""), "kv": kv, "tier": etiqueta,
                "color": color, "operador": op, "circuitos": cct,
                "cables": t.get("cables", ""), "linea": t.get("line", ""),
                "km": round(km, 3), "km_circuito": round(km * cct, 3),
                "vertices": len(coords), "vertices_simp": len(simp),
                "lat_c": round(sum(y for _, y in coords) / len(coords), 5),
                "lon_c": round(sum(x for x, _ in coords) / len(coords), 5),
                "lat_ini": round(coords[0][1], 5), "lon_ini": round(coords[0][0], 5),
                "lat_fin": round(coords[-1][1], 5), "lon_fin": round(coords[-1][0], 5),
                "ubicacion": t.get("location", ""), "fuente": "OpenStreetMap (ODbL)",
            }})
        tot_km += km
        tot_vert += len(coords)
        d = por_tier.setdefault(etiqueta, {"color": color, "n": 0, "km": 0.0, "km_cto": 0.0, "vertices": 0})
        d["n"] += 1
        d["km"] += km
        d["km_cto"] += km * cct
        d["vertices"] += len(coords)
        operadores[op] = operadores.get(op, 0.0) + km

    json.dump({"type": "FeatureCollection", "features": feats},
              open(os.path.join(OUT, "lineas_osm.geojson"), "w", encoding="utf-8"), ensure_ascii=False)

    # ── subestaciones ──
    sf = []
    for el in raw_s["elements"]:
        c = el.get("center") or ({"lat": el.get("lat"), "lon": el.get("lon")} if el.get("lat") else None)
        if not c or c["lat"] is None:
            continue
        t = el.get("tags", {})
        kv = parse_kv(t.get("voltage"))
        sf.append({"type": "Feature",
                   "geometry": {"type": "Point", "coordinates": [round(c["lon"], 5), round(c["lat"], 5)]},
                   "properties": {"id": el["id"], "osm_type": el["type"],
                                  "nombre": t.get("name", "sin nombre"), "kv": kv,
                                  "tier": tier_of(kv)[0], "color": tier_of(kv)[1],
                                  "operador": (t.get("operator") or "sin dato").strip(),
                                  "subestacion": t.get("substation", ""),
                                  "lat": round(c["lat"], 5), "lon": round(c["lon"], 5)}})
    json.dump({"type": "FeatureCollection", "features": sf},
              open(os.path.join(OUT, "subestaciones_osm.geojson"), "w", encoding="utf-8"), ensure_ascii=False)

    # ── centrales ──
    pf = []
    for el in raw_p["elements"]:
        c = el.get("center") or ({"lat": el.get("lat"), "lon": el.get("lon")} if el.get("lat") else None)
        if not c or c["lat"] is None:
            continue
        t = el.get("tags", {})
        mw = parse_mw(t)
        pf.append({"type": "Feature",
                   "geometry": {"type": "Point", "coordinates": [round(c["lon"], 5), round(c["lat"], 5)]},
                   "properties": {"id": el["id"], "osm_type": el["type"],
                                  "nombre": t.get("name", "sin nombre"),
                                  "fuente_energia": t.get("plant:source", t.get("generator:source", "sin dato")),
                                  "metodo": t.get("plant:method", ""), "mw": round(mw, 2),
                                  "operador": (t.get("operator") or "sin dato").strip(),
                                  "lat": round(c["lat"], 5), "lon": round(c["lon"], 5)}})
    json.dump({"type": "FeatureCollection", "features": pf},
              open(os.path.join(OUT, "centrales_osm.geojson"), "w", encoding="utf-8"), ensure_ascii=False)

    # ── KPIs ──
    por_fuente: dict[str, dict] = {}
    for f in pf:
        s = f["properties"]["fuente_energia"] or "sin dato"
        d = por_fuente.setdefault(s, {"n": 0, "mw": 0.0})
        d["n"] += 1
        d["mw"] += f["properties"]["mw"]
    kpis = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fuente": "OpenStreetMap vía Overpass API — licencia ODbL",
        "consulta": "power=line[voltage] / power=substation / power=plant en area ISO3166-1=PE",
        "tolerancia_simplificacion_deg": tol_deg,
        "lineas": len(feats), "km_totales": round(tot_km, 1),
        "km_circuito": round(sum(v["km_cto"] for v in por_tier.values()), 1),
        "vertices": tot_vert, "subestaciones": len(sf), "centrales": len(pf),
        "mw_osm": round(sum(f["properties"]["mw"] for f in pf), 1),
        "operadores": len(operadores),
        "por_tier": {k: {"color": v["color"], "n": v["n"], "km": round(v["km"], 1),
                         "km_circuito": round(v["km_cto"], 1), "vertices": v["vertices"]}
                     for k, v in por_tier.items()},
        "top_operadores": sorted(({"operador": k, "km": round(v, 1)} for k, v in operadores.items()),
                                 key=lambda r: -r["km"])[:15],
        "por_fuente": {k: {"n": v["n"], "mw": round(v["mw"], 1)} for k, v in sorted(
            por_fuente.items(), key=lambda kv: -kv[1]["mw"])},
        "referencia_validacion": "Ver doc/VALIDACION_PERU.md (contrastar con COES/Osinergmin)",
    }
    json.dump(kpis, open(os.path.join(OUT, "kpis_osm.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in kpis.items() if k != "por_fuente"}, ensure_ascii=False, indent=2)[:1800])
    for n in ("lineas_osm.geojson", "subestaciones_osm.geojson", "centrales_osm.geojson"):
        print(f"  {n}: {os.path.getsize(os.path.join(OUT, n))/1e6:.2f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=None, help="carpeta con pe_lines.json/pe_subs.json/pe_plants.json")
    ap.add_argument("--tol", type=float, default=3e-4)
    a = ap.parse_args()
    build(a.cache, a.tol)
