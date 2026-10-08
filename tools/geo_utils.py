"""
geo_utils.py — geodesia en Python puro (sin pyproj / GDAL / geopandas).

Portado del dashboard de Ecuador (ARCONEL/GEOSISDAT) y extendido con los
sistemas de referencia oficiales de Colombia:

    EPSG:4326  WGS 84                                  (salida web)
    EPSG:4686  MAGNA-SIRGAS geográficas                (datum oficial)
    EPSG:9377  MAGNA-SIRGAS / Origen-Nacional (CTM12)  λ0=-73°, φ0=4°,
                                                        FE 5 000 000, FN 2 000 000, k0=0.9992
    EPSG:3114-3118  orígenes antiguos (Oeste-Oeste, Oeste, Bogotá, Este-Central, Este)
    EPSG:32617/18/19  UTM 17N/18N/19N

Todas las funciones trabajan con floats y listas; no requieren dependencias
binarias, por lo que funcionan en Streamlit Community Cloud sin ruedas nativas.
"""
from __future__ import annotations

import math

# ───────────────────────── elipsoide GRS80 / WGS84 ─────────────────────────
A = 6378137.0
F = 1 / 298.257222101  # GRS80 (MAGNA-SIRGAS); WGS84 difiere en 1e-9
B = A * (1 - F)
E2 = F * (2 - F)

# Parámetros de las proyecciones transversas de Mercator usadas en Colombia
ORIGENES = {
    9377: dict(nombre="CTM12 (Origen Nacional)", lon0=-73.0, lat0=4.0,
               FE=5_000_000.0, FN=2_000_000.0, k0=0.9992),
    3114: dict(nombre="Colombia Oeste-Oeste", lon0=-80.0776564, lat0=4.5962320,
               FE=1_000_000.0, FN=1_000_000.0, k0=1.0),
    3115: dict(nombre="Colombia Oeste", lon0=-77.0776564, lat0=4.5962320,
               FE=1_000_000.0, FN=1_000_000.0, k0=1.0),
    3116: dict(nombre="Colombia Bogotá", lon0=-74.0776564, lat0=4.5962320,
               FE=1_000_000.0, FN=1_000_000.0, k0=1.0),
    3117: dict(nombre="Colombia Este-Central", lon0=-71.0776564, lat0=4.5962320,
               FE=1_000_000.0, FN=1_000_000.0, k0=1.0),
    3118: dict(nombre="Colombia Este", lon0=-68.0776564, lat0=4.5962320,
               FE=1_000_000.0, FN=1_000_000.0, k0=1.0),
    32617: dict(nombre="UTM 17N", lon0=-81.0, lat0=0.0, FE=500_000.0, FN=0.0, k0=0.9996),
    32618: dict(nombre="UTM 18N", lon0=-75.0, lat0=0.0, FE=500_000.0, FN=0.0, k0=0.9996),
    32619: dict(nombre="UTM 19N", lon0=-69.0, lat0=0.0, FE=500_000.0, FN=0.0, k0=0.9996),
}


# ───────────────────────────── distancias ─────────────────────────────
def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia esférica en metros (R media = 6 371 008.8 m). Rápida y estable."""
    r = 6_371_008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def vincenty_m(lat1: float, lon1: float, lat2: float, lon2: float,
               tol: float = 1e-12, itmax: int = 200) -> float:
    """Distancia geodésica elipsoidal (Vincenty inverso). Cae a haversine si no converge."""
    if (lat1, lon1) == (lat2, lon2):
        return 0.0
    L = math.radians(lon2 - lon1)
    U1 = math.atan((1 - F) * math.tan(math.radians(lat1)))
    U2 = math.atan((1 - F) * math.tan(math.radians(lat2)))
    sU1, cU1, sU2, cU2 = math.sin(U1), math.cos(U1), math.sin(U2), math.cos(U2)
    lam = L
    for _ in range(itmax):
        sl, cl = math.sin(lam), math.cos(lam)
        ss = math.sqrt((cU2 * sl) ** 2 + (cU1 * sU2 - sU1 * cU2 * cl) ** 2)
        if ss == 0:
            return 0.0
        cs = sU1 * sU2 + cU1 * cU2 * cl
        sigma = math.atan2(ss, cs)
        sa = cU1 * cU2 * sl / ss
        c2a = 1 - sa ** 2
        c2sm = cs - 2 * sU1 * sU2 / c2a if c2a != 0 else 0.0
        C = F / 16 * c2a * (4 + F * (4 - 3 * c2a))
        lam_p = lam
        lam = L + (1 - C) * F * sa * (sigma + C * ss * (c2sm + C * cs * (-1 + 2 * c2sm ** 2)))
        if abs(lam - lam_p) < tol:
            u2 = c2a * (A ** 2 - B ** 2) / B ** 2
            AA = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
            BB = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
            dS = BB * ss * (c2sm + BB / 4 * (cs * (-1 + 2 * c2sm ** 2)
                 - BB / 6 * c2sm * (-3 + 4 * ss ** 2) * (-3 + 4 * c2sm ** 2)))
            return B * AA * (sigma - dS)
    return haversine_m(lat1, lon1, lat2, lon2)


def polyline_length_m(coords, exact: bool = False) -> float:
    """Longitud de una polilínea [(lon, lat), …] en metros."""
    f = vincenty_m if exact else haversine_m
    tot = 0.0
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        tot += f(y1, x1, y2, x2)
    return tot


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Azimut inicial en grados (0 = norte)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


# ──────────────────── proyección transversa de Mercator (Krüger) ────────────────────
def _footpoint_lat(M: float, k0: float) -> float:
    mu = M / (A * (1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    return (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
            + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))


def _meridian_arc(lat: float) -> float:
    return A * ((1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256) * lat
                - (3 * E2 / 8 + 3 * E2 ** 2 / 32 + 45 * E2 ** 3 / 1024) * math.sin(2 * lat)
                + (15 * E2 ** 2 / 256 + 45 * E2 ** 3 / 1024) * math.sin(4 * lat)
                - (35 * E2 ** 3 / 3072) * math.sin(6 * lat))


def latlon_to_proj(lat: float, lon: float, epsg: int = 9377):
    """Geográficas → proyectadas (E, N) en metros para cualquier origen de ORIGENES."""
    p = ORIGENES[epsg]
    lat_r, lon_r = math.radians(lat), math.radians(lon)
    lon0, lat0, k0 = math.radians(p["lon0"]), math.radians(p["lat0"]), p["k0"]
    ep2 = E2 / (1 - E2)
    N = A / math.sqrt(1 - E2 * math.sin(lat_r) ** 2)
    T = math.tan(lat_r) ** 2
    C = ep2 * math.cos(lat_r) ** 2
    Aa = (lon_r - lon0) * math.cos(lat_r)
    M = _meridian_arc(lat_r)
    M0 = _meridian_arc(lat0)
    E = p["FE"] + k0 * N * (Aa + (1 - T + C) * Aa ** 3 / 6
                            + (5 - 18 * T + T ** 2 + 72 * C - 58 * ep2) * Aa ** 5 / 120)
    Nn = p["FN"] + k0 * (M - M0 + N * math.tan(lat_r) * (
        Aa ** 2 / 2 + (5 - T + 9 * C + 4 * C ** 2) * Aa ** 4 / 24
        + (61 - 58 * T + T ** 2 + 600 * C - 330 * ep2) * Aa ** 6 / 720))
    return E, Nn


def proj_to_latlon(E: float, N: float, epsg: int = 9377):
    """Proyectadas (E, N) → geográficas (lat, lon). Inversa de latlon_to_proj."""
    if not (math.isfinite(E) and math.isfinite(N)) or abs(E) > 1e12 or abs(N) > 1e12:
        return float("nan"), float("nan")
    p = ORIGENES[epsg]
    k0 = p["k0"]
    M = (N - p["FN"]) / k0 + _meridian_arc(math.radians(p["lat0"]))
    phi1 = _footpoint_lat(M, k0)
    ep2 = E2 / (1 - E2)
    C1 = ep2 * math.cos(phi1) ** 2
    T1 = math.tan(phi1) ** 2
    N1 = A / math.sqrt(1 - E2 * math.sin(phi1) ** 2)
    R1 = A * (1 - E2) / (1 - E2 * math.sin(phi1) ** 2) ** 1.5
    D = (E - p["FE"]) / (N1 * k0)
    lat = phi1 - (N1 * math.tan(phi1) / R1) * (
        D ** 2 / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * ep2) * D ** 4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 252 * ep2 - 3 * C1 ** 2) * D ** 6 / 720)
    lon = math.radians(p["lon0"]) + (
        D - (1 + 2 * T1 + C1) * D ** 3 / 6
        + (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * ep2 + 24 * T1 ** 2) * D ** 5 / 120) / math.cos(phi1)
    return math.degrees(lat), math.degrees(lon)


# ───────────────────────────── simplificación ─────────────────────────────
def _perp_dist(p, a, b) -> float:
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def douglas_peucker(coords, tol_deg: float = 1e-4):
    """Simplificación Douglas–Peucker sobre coordenadas [(lon, lat), …]."""
    if len(coords) < 3:
        return list(coords)
    dmax, idx = 0.0, 0
    for i in range(1, len(coords) - 1):
        d = _perp_dist(coords[i], coords[0], coords[-1])
        if d > dmax:
            dmax, idx = d, i
    if dmax > tol_deg:
        left = douglas_peucker(coords[:idx + 1], tol_deg)
        right = douglas_peucker(coords[idx:], tol_deg)
        return left[:-1] + right
    return [coords[0], coords[-1]]


# ───────────────────────────── utilidades varias ─────────────────────────────
def bbox_of(coords):
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return min(xs), min(ys), max(xs), max(ys)


def centroid_of(coords):
    n = len(coords)
    return sum(c[0] for c in coords) / n, sum(c[1] for c in coords) / n


def google_maps_url(lat: float, lon: float, zoom: int = 17, modo: str = "satelite") -> str:
    """Enlace profundo a Google Maps centrado en el punto."""
    base = f"https://www.google.com/maps/@{lat:.6f},{lon:.6f},{zoom}z"
    return base + ("/data=!3m1!1e3" if modo == "satelite" else "")


def google_streetview_url(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat:.6f},{lon:.6f}"


def google_earth_url(lat: float, lon: float, alt: int = 2000) -> str:
    return f"https://earth.google.com/web/@{lat:.6f},{lon:.6f},{alt}a,0d,35y,0h,45t,0r"


def openinframap_url(lat: float, lon: float, zoom: int = 13) -> str:
    return f"https://openinframap.org/#{zoom}/{lat:.5f}/{lon:.5f}"


def osm_object_url(osm_type: str, osm_id) -> str:
    return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"


if __name__ == "__main__":  # autotest
    lat, lon = 4.6097, -74.0817  # Bogotá
    for epsg in (9377, 3116, 32618):
        E, N = latlon_to_proj(lat, lon, epsg)
        la, lo = proj_to_latlon(E, N, epsg)
        err = haversine_m(lat, lon, la, lo)
        print(f"EPSG:{epsg} {ORIGENES[epsg]['nombre']:<28} E={E:12.3f} N={N:12.3f} "
              f"ida-vuelta={err:.2e} m")
    print("Bogotá–Medellín haversine:", round(haversine_m(4.6097, -74.0817, 6.2442, -75.5812) / 1000, 3), "km")
    print("Bogotá–Medellín vincenty :", round(vincenty_m(4.6097, -74.0817, 6.2442, -75.5812) / 1000, 3), "km")
