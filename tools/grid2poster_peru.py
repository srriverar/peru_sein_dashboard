"""
grid2poster_col.py — Implementación de Grid2Poster para Perú (SEIN).

Grid2Poster (Open Energy Transition, licencia MIT) genera pósters listos para
imprimir de la infraestructura eléctrica a partir de OpenStreetMap:
    galería : https://open-energy-transition.github.io/grid2poster/
    código  : https://github.com/open-energy-transition/grid2poster

Esta es una adaptación **offline y sin geopandas** del renderizador para el caso
peruano. Conserva del proyecto original: el esquema de temas JSON
(`tools/themes/`, copiados del repositorio upstream MIT), la clasificación en 5
escalones de voltaje (`unknown/low/mid/high/extra`), los anchos y alfas por
escalón, el halo (*glow*), los degradados superior e inferior, el bloque
tipográfico con km por nivel de tensión y GW por fuente, y los formatos de papel
ISO a 300 dpi.

Particularidades de Perú
----------------------------
* Escalones propios del SIN: **34,5 / 110-115 / 220-230 / 500 kV**
  (`DEFAULT_VOLTAGE_TIERS_COL = (34.5, 110.0, 220.0, 500.0)`).
* **Recuadro (inset) del Archipiélago de San Andrés, Providencia y Santa
  Catalina**: está a ~700 km del continente y es una ZNI (Zona No
  Interconectada), por lo que se dibuja aparte — igual que el inset de Galápagos
  en el dashboard de Ecuador — para no encoger el continente.
* Geometría desde el snapshot OSM del repositorio (`data/geo/*.geojson`), sin
  llamadas de red en tiempo de render.

Créditos: Grid2Poster © Open Energy Transition (MIT). Adaptación Perú para
el SEIN Perú · Congestión y GET (Prof. Sergio Rivera, UNAL).
"""
from __future__ import annotations

import io
import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
GEO_DIR = os.path.join(BASE_DIR, "data", "geo")
REF_DIR = os.path.join(BASE_DIR, "data", "reference")
BOUNDARY_GEOJSON = os.path.join(REF_DIR, "peru_boundary.geojson")
SAI_BOUNDARY_GEOJSON = os.path.join(REF_DIR, "san_andres_boundary.geojson")
SAI_POWER_GEOJSON = os.path.join(REF_DIR, "san_andres_power.geojson")
POSTER_DIR = os.path.join(BASE_DIR, "data", "posters")

MM_PER_INCH = 25.4
THIN_SPACE = "\u2009"
TEXT_ZORDER = 20

UPSTREAM_GALLERY = "https://open-energy-transition.github.io/grid2poster/"
UPSTREAM_REPO = "https://github.com/open-energy-transition/grid2poster"
MAPYOURGRID = "https://mapyourgrid.org/"
AWESOME_REPO = "https://github.com/open-energy-transition/Awesome-Electrical-Grid-Mapping"

PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "a5": (148.0, 210.0), "a4": (210.0, 297.0), "a3": (297.0, 420.0),
    "a2": (420.0, 594.0), "a1": (594.0, 841.0), "a0": (841.0, 1189.0),
    "letter": (215.9, 279.4), "square_30": (300.0, 300.0),
}

# Escalones del SEIN peruano (kV). Upstream usa (60, 150, 300, 500) global.
DEFAULT_VOLTAGE_TIERS_COL: tuple[float, float, float, float] = (34.5, 110.0, 220.0, 500.0)
DEFAULT_VOLTAGE_TIERS_OSM: tuple[float, float, float, float] = (60.0, 150.0, 300.0, 500.0)

# Longitud al oeste de la cual un elemento se considera insular (archipiélago)
LON_INSULAR = -999.0  # Perú no tiene ZNI separada: todo el territorio se dibuja junto
# Encuadres del archipiélago (lon0, lat0, lon1, lat1)
SAI_BBOX_SAN_ANDRES = (-81.765, 12.470, -81.665, 12.610)
SAI_BBOX_PROVIDENCIA = (-81.415, 13.305, -81.325, 13.410)
SAI_BBOX = SAI_BBOX_SAN_ANDRES  # compatibilidad

PLANT_SOURCE_BUCKETS = ["solar", "wind", "hydro", "nuclear", "coal", "gas",
                        "oil", "biomass", "other"]


# ---------------------------------------------------------------------------
# TEMAS (formato JSON upstream)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    description: str
    bg: str
    text: str
    subtext: str
    boundary: str
    line_unknown: str
    line_low: str
    line_mid: str
    line_high: str
    line_extra: str
    fade: str
    lw_unknown: float = 0.30
    lw_low: float = 0.48
    lw_mid: float = 0.72
    lw_high: float = 1.05
    lw_extra: float = 1.35
    plant_edge: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def tier_colors(self) -> dict[str, str]:
        return {"unknown": self.line_unknown, "low": self.line_low, "mid": self.line_mid,
                "high": self.line_high, "extra": self.line_extra}

    @property
    def tier_widths(self) -> dict[str, float]:
        return {"unknown": self.lw_unknown, "low": self.lw_low, "mid": self.lw_mid,
                "high": self.lw_high, "extra": self.lw_extra}


_FALLBACK_THEME = {
    "name": "Electric Midnight", "description": "Fondo azul noche con red luminosa.",
    "bg": "#06111F", "text": "#EAF4FF", "subtext": "#8FB7D8", "boundary": "#1D3C5A",
    "line_unknown": "#355B7C", "line_low": "#6FA4C8", "line_mid": "#A7D8FF",
    "line_high": "#F6E7A7", "line_extra": "#FFFFFF", "fade": "#06111F",
}


def _theme_from_dict(key: str, raw: dict) -> Theme:
    kwargs = {k: raw[k] for k in ("name", "description", "bg", "text", "subtext", "boundary",
                                  "line_unknown", "line_low", "line_mid", "line_high",
                                  "line_extra", "fade") if k in raw}
    for k in ("lw_unknown", "lw_low", "lw_mid", "lw_high", "lw_extra"):
        if k in raw:
            kwargs[k] = float(raw[k])
    if "plant_edge" in raw:
        kwargs["plant_edge"] = raw["plant_edge"]
    base = dict(_FALLBACK_THEME)
    base.update(kwargs)
    base["extra"] = {k: v for k, v in raw.items() if k.startswith("plant_")}
    return Theme(key=key, **base)  # type: ignore[arg-type]


def available_themes() -> dict[str, Theme]:
    themes: dict[str, Theme] = {}
    if os.path.isdir(THEMES_DIR):
        for fn in sorted(os.listdir(THEMES_DIR)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(THEMES_DIR, fn), encoding="utf-8") as fh:
                    themes[fn[:-5]] = _theme_from_dict(fn[:-5], json.load(fh))
            except Exception:
                continue
    if not themes:
        themes["electric_midnight"] = _theme_from_dict("electric_midnight", _FALLBACK_THEME)
    return themes


def get_theme(key: str) -> Theme:
    th = available_themes()
    return th.get(key) or next(iter(th.values()))


def derive_plant_colors(theme: Theme) -> dict[str, str]:
    import colorsys
    import matplotlib.colors as mcolors
    anchors = [theme.line_extra, theme.line_high, theme.line_mid,
               theme.line_low, theme.line_unknown, theme.text]
    out: dict[str, str] = {}
    for i, bucket in enumerate(PLANT_SOURCE_BUCKETS):
        pinned = theme.extra.get(f"plant_{bucket}")
        if pinned:
            out[bucket] = pinned
            continue
        h, l, s = colorsys.rgb_to_hls(*mcolors.to_rgb(anchors[i % len(anchors)]))
        h = (h + 0.11 * i) % 1.0
        l = min(0.86, max(0.34, l * (1.05 if i % 2 else 0.92)))
        s = min(1.0, max(0.45, s * 1.15))
        out[bucket] = mcolors.to_hex(colorsys.hls_to_rgb(h, l, s))
    return out


# ---------------------------------------------------------------------------
# DATOS
# ---------------------------------------------------------------------------
def tier_of(kv: float, tiers: tuple[float, float, float, float]) -> str:
    low, mid, high, extra = tiers
    kv = float(kv or 0.0)
    if kv >= extra:
        return "extra"
    if kv >= high:
        return "high"
    if kv >= mid:
        return "mid"
    if kv >= low:
        return "low"
    return "unknown"


def _bucket_osm(src: str) -> str:
    s = (src or "").lower()
    for b in ("solar", "wind", "hydro", "nuclear", "coal", "gas", "oil", "biomass"):
        if b in s:
            return b
    if "diesel" in s:
        return "oil"
    return "other"


def osm_snapshot_dataset(kv_min: float = 0.0, incluir_insular: bool = True,
                         solo_transmision: bool = False) -> dict:
    """Lee `data/geo/*.geojson` (snapshot Overpass) al formato común del render."""
    from tools import gis_data as G

    lin = G.lineas_df()
    if solo_transmision:
        lin = lin[lin["kv"] >= 110.0]
    if kv_min > 0:
        lin = lin[lin["kv"] >= kv_min]

    segs = [{"coords": [(y, x) for x, y in r["_coords"]], "kv": float(r["kv"]),
             "km": float(r["km"]), "nombre": r["nombre"]}
            for _, r in lin.iterrows()]

    cen = G.centrales_df()
    plants = [{"lat": float(r["lat"]), "lon": float(r["lon"]), "mw": float(r["mw"]),
               "bucket": _bucket_osm(str(r["fuente_energia"])), "nombre": r["nombre"]}
              for _, r in cen.iterrows()]

    sub = G.subestaciones_df()
    subs = [{"lat": float(r["lat"]), "lon": float(r["lon"]), "kv": float(r["kv"]),
             "nombre": r["nombre"]} for _, r in sub.iterrows()]

    if incluir_insular:
        plants += _san_andres_plants()

    return {"segments": segs, "plants": plants, "substations": subs,
            "fuente": "OpenStreetMap (Overpass, ODbL) · MapYourGrid"}


def _san_andres_plants() -> list[dict]:
    if not os.path.exists(SAI_POWER_GEOJSON):
        return []
    with open(SAI_POWER_GEOJSON, encoding="utf-8") as fh:
        gj = json.load(fh)
    out = []
    for f in gj.get("features", []):
        p = f["properties"]
        if p.get("power") not in ("plant", "generator"):
            continue
        out.append({"lat": float(p["lat"]), "lon": float(p["lon"]),
                    "mw": float(p.get("mw") or 0.0),
                    "bucket": _bucket_osm(str(p.get("fuente_energia", "diesel"))),
                    "nombre": p.get("nombre", "")})
    return out


def _rings_from_geojson(path: str) -> list[list[tuple[float, float]]]:
    """Devuelve anillos [(lat, lon), …] de un GeoJSON (Polygon/MultiPolygon/LineString)."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        gj = json.load(fh)
    rings: list[list[tuple[float, float]]] = []
    for feat in gj.get("features", []):
        geom = feat.get("geometry") or {}
        t, c = geom.get("type"), geom.get("coordinates")
        if t == "Polygon":
            polys = [c]
        elif t == "MultiPolygon":
            polys = c
        elif t == "LineString":
            rings.append([(float(y), float(x)) for x, y in c])
            continue
        elif t == "MultiLineString":
            for ln in c:
                rings.append([(float(y), float(x)) for x, y in ln])
            continue
        else:
            continue
        for poly in polys:
            for ring in poly:
                rings.append([(float(y), float(x)) for x, y in ring])
    return rings


def load_boundary() -> list[list[tuple[float, float]]]:
    """Contorno continental de Colombia (geoBoundaries ADM0, CC BY)."""
    return _rings_from_geojson(BOUNDARY_GEOJSON)


def load_san_andres() -> list[list[tuple[float, float]]]:
    """Costas del Archipiélago de San Andrés, Providencia y Santa Catalina (OSM)."""
    return _rings_from_geojson(SAI_BOUNDARY_GEOJSON)


# ---------------------------------------------------------------------------
# RENDER
# ---------------------------------------------------------------------------
def render_poster(
    dataset: dict,
    theme: Theme | str = "electric_midnight",
    *,
    titulo: str = "PERÚ",
    subtitulo: str | None = None,
    creditos: str | None = None,
    paper: str = "a3",
    landscape: bool = False,
    dpi: int = 200,
    voltage_tiers: tuple[float, float, float, float] = DEFAULT_VOLTAGE_TIERS_COL,
    mostrar_centrales: bool = True,
    mostrar_subestaciones: bool = False,
    min_mw: float = 0.0,
    plant_marker_scale: float = 1.0,
    mostrar_frontera: bool = True,
    mostrar_metadatos: bool = True,
    incluir_san_andres: bool = False,
    padding: float = 0.08,
    fade_top: float = 0.26,
    fade_bottom: float = 0.30,
    glow: bool = True,
    ancho_extra: float = 1.0,
    fondo_transparente: bool = False,
):
    """Genera el póster (figura matplotlib) al estilo Grid2Poster para Perú (SEIN)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.font_manager import FontProperties
    from matplotlib.offsetbox import AnchoredOffsetbox, HPacker, TextArea

    th = theme if isinstance(theme, Theme) else get_theme(theme)
    w_mm, h_mm = PAPER_SIZES_MM.get(paper, PAPER_SIZES_MM["a3"])
    if landscape:
        w_mm, h_mm = h_mm, w_mm
    width, height = w_mm / MM_PER_INCH, h_mm / MM_PER_INCH

    todos_segs = list(dataset.get("segments", []))
    todas_plants = list(dataset.get("plants", []))
    if min_mw > 0:
        todas_plants = [p for p in todas_plants if p["mw"] >= min_mw]

    # Separación continente / archipiélago (ZNI de San Andrés a ~700 km).
    segs = [s for s in todos_segs if s["coords"][0][1] > LON_INSULAR]
    plants = [p for p in todas_plants if p["lon"] > LON_INSULAR]
    segs_sai = [s for s in todos_segs if s["coords"][0][1] <= LON_INSULAR]
    plants_sai = [p for p in todas_plants if p["lon"] <= LON_INSULAR]

    bg = "none" if fondo_transparente else th.bg
    fig, ax = plt.subplots(figsize=(width, height), facecolor=bg)
    ax.set_facecolor(bg)
    ax.set_position((0, 0, 1, 1))
    ax.axis("off")

    if mostrar_frontera:
        for ring in load_boundary():
            ax.plot([p[1] for p in ring], [p[0] for p in ring],
                    color=th.boundary, lw=0.7, alpha=0.9, zorder=1)

    tier_alpha = {"unknown": 0.55, "low": 0.75, "mid": 0.86, "high": 0.92, "extra": 0.95}
    tier_z = {"unknown": 2, "low": 3, "mid": 4, "high": 5, "extra": 6}
    km_por_tier: dict[str, float] = {k: 0.0 for k in tier_alpha}
    n_por_tier: dict[str, int] = {k: 0 for k in tier_alpha}
    grupos: dict[str, list] = {k: [] for k in tier_alpha}
    for s in segs:
        t = tier_of(s["kv"], voltage_tiers)
        grupos[t].append([(p[1], p[0]) for p in s["coords"]])
        km_por_tier[t] += s.get("km", 0.0)
        n_por_tier[t] += 1

    for t, paths in grupos.items():
        if not paths:
            continue
        color = th.tier_colors[t]
        lw = th.tier_widths[t] * ancho_extra
        if glow and t in ("high", "extra", "mid"):
            ax.add_collection(LineCollection(paths, colors=color, linewidths=lw * 4.5,
                                             alpha=0.10, zorder=tier_z[t] - 0.5, capstyle="round"))
        ax.add_collection(LineCollection(paths, colors=color, linewidths=lw,
                                         alpha=tier_alpha[t], zorder=tier_z[t], capstyle="round"))

    if mostrar_subestaciones and dataset.get("substations"):
        ss = dataset["substations"]
        ax.scatter([s["lon"] for s in ss], [s["lat"] for s in ss],
                   s=[max(0.8, 0.6 + (s.get("kv") or 0) / 90.0) for s in ss],
                   c=th.line_mid, alpha=0.45, linewidths=0, zorder=7)

    plant_colors = derive_plant_colors(th)
    gw_por_fuente: dict[str, float] = {}
    if mostrar_centrales and plants:
        edge = th.plant_edge or (th.bg if not fondo_transparente else "none")
        por_bucket: dict[str, list] = {}
        for p in plants:
            por_bucket.setdefault(p["bucket"], []).append(p)
            gw_por_fuente[p["bucket"]] = gw_por_fuente.get(p["bucket"], 0.0) + p["mw"] / 1000.0
        for bucket, items in por_bucket.items():
            sizes = [max(3.0, 5.5 * math.sqrt(max(p["mw"], 0.4)) * plant_marker_scale) for p in items]
            ax.scatter([p["lon"] for p in items], [p["lat"] for p in items], s=sizes,
                       c=plant_colors.get(bucket, th.text), edgecolors=edge,
                       linewidths=0.35, alpha=0.85, zorder=9)

    # --- encuadre proporcional al papel ---
    lats = [p[0] for s in segs for p in s["coords"]] or [-4.2, 12.4]
    lons = [p[1] for s in segs for p in s["coords"]] or [-79.0, -67.0]
    lat0, lat1, lon0, lon1 = min(lats), max(lats), min(lons), max(lons)
    k = max(math.cos(math.radians((lat0 + lat1) / 2)), 1e-6)
    ax.set_aspect("auto")
    target = width / height
    dlon, dlat = (lon1 - lon0), (lat1 - lat0)
    if (dlon * k) / max(dlat, 1e-9) < target:
        need = dlat * target / k
        pad = (need - dlon) / 2
        lon0, lon1 = lon0 - pad, lon1 + pad
    else:
        need = dlon * k / target
        pad = (need - dlat) / 2
        lat0, lat1 = lat0 - pad, lat1 + pad
    mx = (lon1 - lon0) * padding
    my = mx * k / target
    ax.set_xlim(lon0 - mx, lon1 + mx)
    ax.set_ylim(lat0 - my * 3.0, lat1 + my)

    # --- recuadros del Archipiélago de San Andrés, Providencia y Santa Catalina (ZNI) ---
    if incluir_san_andres:
        costas = load_san_andres()
        if costas or segs_sai or plants_sai:
            def _panel(rect, bbox, etiqueta, fs=4.4):
                axi = fig.add_axes(rect)
                axi.set_facecolor("none" if fondo_transparente else th.bg)
                axi.patch.set_alpha(0.0 if fondo_transparente else 1.0)
                for sp in axi.spines.values():
                    sp.set_color(th.boundary)
                    sp.set_linewidth(0.6)
                axi.set_xticks([]); axi.set_yticks([])
                lon0_i, lat0_i, lon1_i, lat1_i = bbox
                for ring in costas:
                    xs = [p[1] for p in ring]; ys = [p[0] for p in ring]
                    if max(xs) < lon0_i or min(xs) > lon1_i or max(ys) < lat0_i or min(ys) > lat1_i:
                        continue
                    axi.plot(xs, ys, color=th.subtext, lw=0.7, alpha=0.70)
                dentro_s = [s_ for s_ in segs_sai
                            if lon0_i <= s_["coords"][0][1] <= lon1_i and lat0_i <= s_["coords"][0][0] <= lat1_i]
                for s_ in dentro_s:
                    t_ = tier_of(s_["kv"], voltage_tiers)
                    axi.plot([p[1] for p in s_["coords"]], [p[0] for p in s_["coords"]],
                             color=th.tier_colors[t_], lw=th.tier_widths[t_] * ancho_extra * 1.6,
                             alpha=tier_alpha[t_])
                dentro_p = [p_ for p_ in plants_sai
                            if lon0_i <= p_["lon"] <= lon1_i and lat0_i <= p_["lat"] <= lat1_i]
                if mostrar_centrales and dentro_p:
                    axi.scatter([p["lon"] for p in dentro_p], [p["lat"] for p in dentro_p],
                                s=[max(9.0, 5.5 * math.sqrt(max(p["mw"], 0.9)) * plant_marker_scale)
                                   for p in dentro_p],
                                c=[plant_colors.get(p["bucket"], th.text) for p in dentro_p],
                                edgecolors=th.bg if not fondo_transparente else "none",
                                linewidths=0.3, alpha=0.95, zorder=5)
                axi.set_xlim(lon0_i, lon1_i)
                axi.set_ylim(lat0_i, lat1_i)
                axi.set_aspect("equal", adjustable="box")
                axi.text(0.05, 0.045, etiqueta, transform=axi.transAxes, color=th.subtext,
                         fontsize=fs, alpha=0.92, linespacing=1.3)
                return dentro_s, dentro_p

            s1, p1 = _panel((0.035, 0.180, 0.150, 0.150), SAI_BBOX_SAN_ANDRES,
                            "SAN ANDRÉS\n(ZNI)")
            s2, p2 = _panel((0.195, 0.180, 0.105, 0.150), SAI_BBOX_PROVIDENCIA,
                            "PROVIDENCIA Y\nSANTA CATALINA", fs=3.9)
            for s_ in (s1 + s2):
                t_ = tier_of(s_["kv"], voltage_tiers)
                km_por_tier[t_] += s_.get("km", 0.0)
                n_por_tier[t_] += 1
            for p_ in (p1 + p2):
                gw_por_fuente[p_["bucket"]] = gw_por_fuente.get(p_["bucket"], 0.0) + p_["mw"] / 1000.0

    _fade(ax, th.fade, "bottom", fade_bottom)
    _fade(ax, th.fade, "top", fade_top)

    # --- tipografía ---
    scale = min(width, height) / 12
    title_pt = (48 if height >= width else 36) * scale
    f_main = FontProperties(family="DejaVu Sans", weight="bold", size=title_pt)
    f_sub = FontProperties(family="DejaVu Sans", size=15 * scale)
    f_meta = FontProperties(family="DejaVu Sans Mono", size=8.0 * scale)

    if subtitulo is None:
        subtitulo = "SISTEMA INTERCONECTADO NACIONAL"
    ax.text(0.5, 0.128, " ".join(titulo.upper()), transform=ax.transAxes, ha="center",
            va="center", color=th.text, fontproperties=f_main, zorder=TEXT_ZORDER)
    ax.text(0.5, 0.088, subtitulo, transform=ax.transAxes, ha="center", va="center",
            color=th.subtext, fontproperties=f_sub, zorder=TEXT_ZORDER)

    def _seg(txt, color, alpha):
        return TextArea(txt, textprops=dict(fontproperties=f_meta, color=color, alpha=alpha))

    def _row(children, y):
        packed = HPacker(children=children, align="center", sep=4.0 * scale, pad=0)
        box = AnchoredOffsetbox(loc="center", child=packed, bbox_to_anchor=(0.5, y),
                                bbox_transform=ax.transAxes, frameon=False, pad=0, borderpad=0)
        box.set_zorder(TEXT_ZORDER)
        ax.add_artist(box)

    low, mid, high, extra = voltage_tiers
    etiquetas = [("low", f"{low:g}–{mid:g}{THIN_SPACE}kV"),
                 ("mid", f"{mid:g}–{high:g}{THIN_SPACE}kV"),
                 ("high", f"{high:g}–{extra:g}{THIN_SPACE}kV"),
                 ("extra", f"≥{extra:g}{THIN_SPACE}kV")]
    if mostrar_metadatos:
        hijos = [_seg(str(datetime.now().year), th.subtext, 0.85)]
        for t, lab in etiquetas:
            if km_por_tier.get(t, 0) <= 0:
                continue
            hijos += [_seg("·", th.subtext, 0.8), _seg(lab, th.tier_colors[t], 0.95),
                      _seg(f"{km_por_tier[t]:,.0f}{THIN_SPACE}km", th.subtext, 0.85)]
        _row(hijos, 0.062)
        if mostrar_centrales and gw_por_fuente:
            hijos = []
            for i, b in enumerate([b for b in PLANT_SOURCE_BUCKETS if b in gw_por_fuente]):
                if i:
                    hijos.append(_seg("·", th.subtext, 0.8))
                hijos += [_seg(b.upper(), plant_colors[b], 0.95),
                          _seg(f"{gw_por_fuente[b]:,.2f}{THIN_SPACE}GW", th.subtext, 0.85)]
            _row(hijos, 0.040)

    if creditos is None:
        creditos = (f"{dataset.get('fuente', '')} · Grid2Poster (Open Energy Transition, MIT) · "
                    f"SEIN Perú · Congestión y GET")
    ax.text(0.5, 0.018, creditos, transform=ax.transAxes, ha="center", va="center",
            color=th.subtext, alpha=0.7,
            fontproperties=FontProperties(family="DejaVu Sans", size=6.0 * scale),
            zorder=TEXT_ZORDER)

    fig.set_dpi(dpi)
    stats = {
        "segmentos": len(segs) + len(segs_sai),
        "segmentos_continente": len(segs),
        "segmentos_insulares": len(segs_sai),
        "km_total": float(sum(km_por_tier.values())),
        "km_por_tier": km_por_tier,
        "n_por_tier": n_por_tier,
        "centrales": len(plants) + len(plants_sai),
        "gw_por_fuente": gw_por_fuente,
        "tema": th.name,
        "papel": f"{paper.upper()} {'apaisado' if landscape else 'retrato'} "
                 f"({w_mm:.0f}×{h_mm:.0f} mm @ {dpi} dpi)",
        "tiers": voltage_tiers,
    }
    return fig, stats


def _fade(ax, color: str, side: str, height: float, max_alpha: float = 1.0):
    import matplotlib.colors as mcolors
    import numpy as np
    if height <= 0:
        return
    rgb = mcolors.to_rgb(color)
    n = 256
    alpha = np.linspace(0, max_alpha, n) if side == "bottom" else np.linspace(max_alpha, 0, n)
    img = np.zeros((n, 1, 4))
    img[:, 0, :3] = rgb
    img[:, 0, 3] = alpha[::-1] if side == "bottom" else alpha
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    span = (y1 - y0) * height
    extent = (x0, x1, y0, y0 + span) if side == "bottom" else (x0, x1, y1 - span, y1)
    ax.imshow(img, extent=extent, aspect="auto", origin="lower", zorder=10, interpolation="bilinear")


def poster_bytes(fig, fmt: str = "png", dpi: int = 200) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, facecolor=fig.get_facecolor(),
                bbox_inches=None, pad_inches=0)
    buf.seek(0)
    return buf.read()


def save_poster(fig, nombre: str = "peru_grid_poster", fmt: str = "png", dpi: int = 200) -> str:
    os.makedirs(POSTER_DIR, exist_ok=True)
    path = os.path.join(POSTER_DIR, f"{nombre}.{fmt}")
    fig.savefig(path, dpi=dpi, facecolor=fig.get_facecolor(), pad_inches=0)
    return path


if __name__ == "__main__":
    import sys
    sys.path.insert(0, BASE_DIR)
    ds = osm_snapshot_dataset()
    for tema, nombre in (("neon_cyberpunk", "peru_grid_poster_neon"),
                         ("paper_grid", "peru_grid_poster_paper")):
        fig, stats = render_poster(ds, tema, titulo="PERÚ", dpi=120)
        print(save_poster(fig, nombre, dpi=120))
        print({k: v for k, v in stats.items() if k != "km_por_tier"})
        print("  km por tier:", {k: round(v, 1) for k, v in stats["km_por_tier"].items()})
