"""
Dashboard SEIN Perú — Análisis de Congestión, Corredores y Capacidad de Transmisión
=================================================================================
Plataforma abierta para el estudio del Sistema Eléctrico Interconectado Nacional (SEIN)
del Perú: despacho económico nodal, precios, congestión de corredores y valor de
tecnologías de incremento de capacidad (DLR, repotenciación, GET).

Estructura y enfoque heredados de dashboard SIN Nodal (Colombia), del mismo autor.
Diseñado para colaboración: todos los parámetros de entrada están en CSV editables
(data/reference/) y la app admite cargar versiones propias de esos archivos.

Autor original del marco: Prof. Sergio Rivera — Universidad Nacional de Colombia
"""
import io
import os
import sys
import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from tools import sein_model as M  # noqa: E402
from tools import gis_data as GIS  # noqa: E402

st.set_page_config(page_title="SEIN Perú · Congestión", page_icon="🇵🇪", layout="wide")

st.markdown(
    """
    <style>
    .kpi {background:#f0f4f8;border-left:5px solid #D91023;border-radius:8px;padding:12px 14px;margin-bottom:8px}
    .kpi b {font-size:1.45rem;color:#1f2a44} .kpi span {display:block;color:#555;font-size:.85rem}
    .aviso {background:#fff8e1;border-left:4px solid #f5a623;padding:10px 14px;border-radius:6px;font-size:.9rem}
    </style>
    """,
    unsafe_allow_html=True,
)

COLORES_TEC = {"hidro": "#1f77b4", "termo": "#7f7f7f", "eolica": "#2ca02c", "solar": "#ffbf00"}
NOMBRES_TEC = {"hidro": "Hidroeléctrica", "termo": "Termoeléctrica", "eolica": "Eólica", "solar": "Solar"}
COLORES_KV = {500: "#D91023", 220: "#FF7F0E", 138: "#FFD100", 60: "#2CA02C"}


def kpi(valor, etiqueta):
    st.markdown(f'<div class="kpi"><b>{valor}</b><span>{etiqueta}</span></div>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def leer_csv(nombre: str) -> pd.DataFrame:
    return pd.read_csv(os.path.join(ROOT, "data", "reference", nombre))


@st.cache_data(show_spinner=False)
def correr(nodos_json: str, enlaces_json: str, crec: float, enso: str, f_sol: float,
           f_eol: float, get_inc: float):
    nodos = pd.read_json(io.StringIO(nodos_json))
    enlaces = pd.read_json(io.StringIO(enlaces_json))
    perfiles = leer_csv("sein_perfiles_horarios.csv")
    return M.run_dispatch(nodos, enlaces, perfiles, crecimiento_demanda=crec,
                          escenario_enso=enso, factor_solar=f_sol, factor_eolica=f_eol,
                          incremento_get=get_inc)


# ═══════════════════════════════════════════════════════════════════════
#  NAVEGACIÓN
# ═══════════════════════════════════════════════════════════════════════
PAGINAS = [
    "🏠 Inicio",
    "🗺️ Mapa del SEIN",
    "⚡ Arquitectura del SEIN",
    "🔴 Congestión y GET",
    "🔥 Congestión documentada",
    "🌎 Interconexiones internacionales",
    "🧩 DLR y GET",
    "🧭 Red OSM, MapYourGrid y póster",
    "🌊 ENSO e hidrología",
    "🌍 Perú en el mundo",
    "🗄️ Datos Perú",
    "📋 Política y regulación",
    "💼 Propuesta IDOM",
    "🤝 Colaboración",
]
with st.sidebar:
    st.markdown("### 🇵🇪 SEIN Perú")
    st.caption("Congestión, corredores y capacidad de transmisión")
    pagina = st.radio("Navegar:", PAGINAS, key="nav", label_visibility="collapsed")
    st.divider()
    st.caption("Datos de entrada: `data/reference/*.csv` (editables).")
    st.caption("Snapshot OSM: " + ("✅ disponible" if GIS.disponible() else "⚠️ no generado aún"))


# ═══════════════════════════════════════════════════════════════════════
#  🏠 INICIO
# ═══════════════════════════════════════════════════════════════════════
if pagina == "🏠 Inicio":
    st.title("🇵🇪 Sistema Eléctrico Interconectado Nacional (SEIN) — Perú")
    st.markdown(
        "Plataforma de análisis de **congestión de transmisión**, **precios nodales** y "
        "**valor de tecnologías de incremento de capacidad** (DLR, repotenciación de conductores y otras GET)."
    )
    ind = leer_csv("sein_indicadores.csv")
    cols = st.columns(4)
    valores = [
        ("61 244 GWh", "Energía producida SEIN 2025"),
        ("7 942 MW", "Máxima demanda SEIN 2025"),
        ("14 492 MW", "Capacidad instalada (jul-2026)"),
        ("25 400 MW", "Capacidad estimada 2030 (con EPO)"),
    ]
    for c, (v, e) in zip(cols, valores):
        with c:
            kpi(v, e)

    st.subheader("Matriz de capacidad instalada (jul-2026)")
    tec = leer_csv("sein_tecnologia_2026.csv")
    fig = go.Figure(go.Pie(
        labels=tec["tecnologia"], values=tec["potencia_instalada_mw"], hole=0.5,
        marker_colors=["#1f77b4", "#7f7f7f", "#2ca02c", "#ffbf00"], textinfo="label+percent",
    ))
    fig.update_layout(height=380, margin=dict(t=10, b=10), showlegend=False)
    c1, c2 = st.columns([1, 1])
    with c1:
        st.plotly_chart(fig, width="stretch")
        st.caption("Fuente: OSINERGMIN / COES (vía Energía Estratégica, jul-2026). Ver `data/reference/sein_tecnologia_2026.csv`.")
    with c2:
        st.markdown("#### Resultado rápido del modelo (escenario base)")
        r = correr(leer_csv("sein_nodos.csv").to_json(), leer_csv("sein_enlaces.csv").to_json(),
                   0.0, "Normal", 1.0, 1.0, 0.0)
        st.metric("Renta de congestión (día representativo)", f"{r['renta_congestion_MUSD']:.2f} MUSD")
        st.metric("Energía no servida", f"{r['energia_falla_MWh']:.0f} MWh")
        cong = r["lineas"]
        top = cong.sort_values("horas_congestionada", ascending=False).head(1).iloc[0]
        st.metric("Corredor más congestionado", f"{top['id']} · {top['horas_congestionada']} h",
                  help=top["corredor"])
        st.markdown(
            '<div class="aviso">Los parámetros nodales y de enlaces son <b>estimaciones</b> a partir de totales '
            'oficiales. Use la pestaña 🤝 Colaboración para proponer correcciones con fuente.</div>',
            unsafe_allow_html=True,
        )

    st.subheader("Preguntas que responde esta plataforma")
    st.markdown(
        "- ¿Qué corredores del SEIN se congestionan y en qué horas?\n"
        "- ¿Cuánto cuesta la congestión en precios y renta (y quién la paga)?\n"
        "- ¿Cuánto vale incrementar 10–30 % la capacidad de las líneas con DLR o repotenciación?\n"
        "- ¿Cómo cambian precios y congestión con El Niño / La Niña y con más solar en el sur?"
    )


# ═══════════════════════════════════════════════════════════════════════
#  🗺️ MAPA DEL SEIN
# ═══════════════════════════════════════════════════════════════════════
elif pagina == "🗺️ Mapa del SEIN":
    st.title("🗺️ Mapa del SEIN")
    dep = GIS.departamentos()
    nodos = leer_csv("sein_nodos.csv")
    enlaces = leer_csv("sein_enlaces.csv")

    fig = go.Figure()
    # Límites departamentales (dibujados como líneas, sin mapa base → funciona offline)
    if dep:
        for feat in dep["features"]:
            geom = feat["geometry"]
            polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
            for poly in polys:
                anillo = poly[0]
                xs = [p[0] for p in anillo] + [None]
                ys = [p[1] for p in anillo] + [None]
                fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#c9d3df", width=1),
                                         hoverinfo="skip", showlegend=False))

    if GIS.disponible():
        lineas = GIS.lineas_df()
        niveles = [t for t in ["500 kV", "220/230 kV", "110/115 kV", "57.5/66 kV", "34.5 kV", "≤ 13.8 kV"]
                   if t in set(lineas["tier"])]
        filtro = st.sidebar.multiselect("Niveles de tensión — OSM", niveles,
                                        default=[t for t in niveles if t in ("500 kV", "220/230 kV")])
        lineas = lineas[lineas["tier"].isin(filtro)] if filtro else lineas.iloc[0:0]
        subs = GIS.subestaciones_df()
        if not subs.empty and st.sidebar.checkbox("Mostrar subestaciones ≥ 138 kV (OSM)", value=True):
            subs = subs[subs["kv"] >= 138]
            fig.add_trace(go.Scatter(x=subs["lon"], y=subs["lat"], mode="markers", name="Subestaciones OSM",
                                     marker=dict(size=4, color="#333333", symbol="square"),
                                     hovertext=subs["nombre"] + " · " + subs["tier"], hoverinfo="text"))
        for _, row in lineas.iterrows():
            xs = [p[0] for p in row["geometry"]["coordinates"]]
            ys = [p[1] for p in row["geometry"]["coordinates"]]
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", showlegend=False,
                                     line=dict(color=row["color"], width=2 if row["kv"] >= 220 else 1),
                                     hovertext=f"{row['nombre'] or 'línea'} · {row['tier']} · {row['operador']}",
                                     hoverinfo="text"))
        st.caption(f"Red OSM: {len(lineas)} tramos mostrados. Fuente: OpenStreetMap (ODbL).")
    else:
        # Esquema nodal: enlaces del modelo
        for _, e in enlaces.iterrows():
            a = nodos.set_index("id").loc[e["desde"]]
            b = nodos.set_index("id").loc[e["hasta"]]
            fig.add_trace(go.Scatter(
                x=[a["lon"], b["lon"]], y=[a["lat"], b["lat"]], mode="lines",
                line=dict(color=COLORES_KV.get(int(e["tension_kv"]), "#888"),
                          width=max(2, e["capacidad_mw_est"] / 150)),
                hovertext=f"{e['id']} · {e['corredor']} · {e['capacidad_mw_est']:.0f} MW",
                hoverinfo="text", showlegend=False))
        st.caption("Red esquemática de 7 nodos (enlaces del modelo). Grosor ∝ capacidad estimada. "
                   "Para la red real, ejecute `python3 tools/build_osm_snapshot.py`.")

    fig.add_trace(go.Scatter(
        x=nodos["lon"], y=nodos["lat"], mode="markers+text", text=nodos["id"],
        textposition="top center",
        marker=dict(size=np.clip(nodos["demanda_max_mw_est"] / 60, 10, 60), color="#D91023",
                    opacity=0.85, line=dict(color="white", width=1)),
        hovertext=nodos["nodo"] + "<br>Demanda est.: " + nodos["demanda_max_mw_est"].astype(str) + " MW",
        hoverinfo="text", name="Nodos del modelo"))

    if GIS.disponible() and st.sidebar.checkbox("Mostrar centrales OSM", value=False):
        cen = GIS.centrales_df()
        if not cen.empty:
            fig.add_trace(go.Scatter(x=cen["lon"], y=cen["lat"], mode="markers", name="Centrales OSM",
                                     marker=dict(size=5, color="#1f77b4"),
                                     hovertext=cen["nombre"], hoverinfo="text"))

    fig.update_layout(height=680, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white",
                      xaxis=dict(range=[GIS.EXTENT["lon_min"], GIS.EXTENT["lon_max"]], title="Longitud",
                                 showgrid=False, scaleanchor="y", scaleratio=1.1),
                      yaxis=dict(range=[GIS.EXTENT["lat_min"], GIS.EXTENT["lat_max"]], title="Latitud",
                                 showgrid=False),
                      legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig, width="stretch")

    if GIS.disponible():
        from tools import geo_utils as GEO
        st.subheader("🛰️ Contraste con Google Maps / Earth y OSM")
        subs = GIS.subestaciones_df()
        if not subs.empty:
            subs = subs[subs["kv"] >= 220].dropna(subset=["lat", "lon"]).reset_index(drop=True)
            etiquetas = (subs["nombre"].fillna("sin nombre") + " · " + subs["tier"]).tolist()
            if etiquetas:
                i = st.selectbox("Subestación ≥ 220 kV", range(len(etiquetas)),
                                 format_func=lambda k: etiquetas[k])
                la, lo = float(subs.loc[i, "lat"]), float(subs.loc[i, "lon"])
                c1, c2, c3, c4 = st.columns(4)
                c1.link_button("🛰️ Google Satélite", GEO.google_maps_url(la, lo, 17, "satelite"))
                c2.link_button("🧍 Street View", GEO.google_streetview_url(la, lo))
                c3.link_button("🌍 Google Earth", GEO.google_earth_url(la, lo))
                c4.link_button("🗺️ OpenStreetMap", f"https://www.openstreetmap.org/?mlat={la}&mlon={lo}#map=17/{la}/{lo}")
                st.caption(f"Coordenadas: {la:.5f}, {lo:.5f}. Los enlaces abren Google Maps en una pestaña nueva. "
                           "El uso intensivo de teselas de Google requiere Google Maps Platform (ToS).")

    st.subheader("Nodos del modelo")
    st.dataframe(nodos[["id", "nodo", "region_zona", "lat", "lon", "demanda_max_mw_est", "hidro_mw",
                        "termo_mw", "eolica_mw", "solar_mw"]], width="stretch", hide_index=True)


# ═══════════════════════════════════════════════════════════════════════
#  ⚡ ARQUITECTURA DEL SEIN
# ═══════════════════════════════════════════════════════════════════════
elif pagina == "⚡ Arquitectura del SEIN":
    st.title("⚡ Arquitectura del SEIN")
    nodos = leer_csv("sein_nodos.csv")
    ind = leer_csv("sein_indicadores.csv")

    st.subheader("Capacidad instalada por nodo y tecnología (MW)")
    fig = go.Figure()
    for tec in ["hidro", "termo", "eolica", "solar"]:
        fig.add_trace(go.Bar(name=NOMBRES_TEC[tec], x=nodos["id"] + " " + nodos["nodo"].str.split(" ").str[0],
                             y=nodos[f"{tec}_mw"], marker_color=COLORES_TEC[tec]))
    fig.add_trace(go.Scatter(name="Demanda máx. est.", x=nodos["id"] + " " + nodos["nodo"].str.split(" ").str[0],
                             y=nodos["demanda_max_mw_est"], mode="markers",
                             marker=dict(symbol="diamond", size=12, color="black")))
    fig.update_layout(barmode="stack", height=460, margin=dict(t=20, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("Distribución nodal ESTIMADA: se reparten los totales oficiales por tecnología entre zonas. "
               "Corrija `data/reference/sein_nodos.csv` con datos de la tabla de centrales del COES.")

    st.subheader("Balance por zona")
    bal = nodos.groupby("region_zona")[["demanda_max_mw_est", "hidro_mw", "termo_mw", "eolica_mw", "solar_mw"]].sum()
    bal["generacion_total_mw"] = bal[["hidro_mw", "termo_mw", "eolica_mw", "solar_mw"]].sum(axis=1)
    bal["balance_mw (gen−dem)"] = bal["generacion_total_mw"] - bal["demanda_max_mw_est"]
    st.dataframe(bal.round(0), width="stretch")

    st.subheader("Cartera y pipeline de transmisión / generación")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Indicadores oficiales**")
        st.dataframe(ind, width="stretch", hide_index=True, height=420)
    with c2:
        st.markdown("**Cartera renovable en revisión (COES, 2025)**")
        cartera = pd.DataFrame({
            "Zona": ["Norte", "Centro", "Sur"],
            "Eólica (MW)": [5605, 3838, 348],
            "Solar (MW)": [650, 1743, 11908],
            "Hidro < 20 MW (MW)": [632, 913, 918],
        })
        st.dataframe(cartera, width="stretch", hide_index=True)
        st.caption("Fuente: COES, presentación en V Conferencia Expo Solar Perú 2025 (cifras de proyectos aprobados y en revisión).")
        fig2 = go.Figure(go.Bar(x=cartera["Zona"], y=cartera["Solar (MW)"], name="Solar", marker_color="#ffbf00"))
        fig2.add_trace(go.Bar(x=cartera["Zona"], y=cartera["Eólica (MW)"], name="Eólica", marker_color="#2ca02c"))
        fig2.update_layout(barmode="group", height=300, margin=dict(t=10, b=10))
        st.plotly_chart(fig2, width="stretch")


# ═══════════════════════════════════════════════════════════════════════
#  🔴 CONGESTIÓN Y GET
# ═══════════════════════════════════════════════════════════════════════
elif pagina == "🔴 Congestión y GET":
    st.title("🔴 Congestión de corredores y valor de GET / DLR")
    st.markdown(
        "Despacho económico horario (24 h, día representativo) con flujo de transporte entre los 7 nodos. "
        "Pruebe el efecto de **incrementar la capacidad térmica de las líneas** (DLR, repotenciación con "
        "conductores de alta temperatura u otras GET)."
    )

    with st.expander("📂 Usar datos propios (opcional)"):
        st.caption("Suba versiones editadas de los CSV con las mismas columnas que las plantillas.")
        up_n = st.file_uploader("sein_nodos.csv", type="csv", key="up_n")
        up_e = st.file_uploader("sein_enlaces.csv", type="csv", key="up_e")

    nodos = pd.read_csv(up_n) if up_n is not None else leer_csv("sein_nodos.csv")
    enlaces = pd.read_csv(up_e) if up_e is not None else leer_csv("sein_enlaces.csv")
    if up_n is not None or up_e is not None:
        st.info("Usando datos cargados por el usuario.")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        crec = st.slider("Crecimiento de demanda (%)", 0, 20, 0, 1) / 100
        enso = st.selectbox("Escenario hidrológico (ENSO)", list(M.FACTOR_ENSO.keys()), index=2)
    with c2:
        f_sol = st.slider("Capacidad solar (× actual)", 0.5, 3.0, 1.0, 0.1)
        f_eol = st.slider("Capacidad eólica (× actual)", 0.5, 3.0, 1.0, 0.1)
    with c3:
        get_inc = st.slider("Incremento de capacidad de líneas por GET/DLR (%)", 0, 50, 0, 5) / 100
        st.caption("Escenario de referencia: 0 %. Un DLR bien instrumentado suele dar mejoras del orden de 10–30 % "
                   "según clima y tipo de conductor (supuesto a validar).")
    with c4:
        dias = st.number_input("Días/año para anualizar", 1, 365, 365)

    nj = nodos.to_json()
    ej = enlaces.to_json()
    r = correr(nj, ej, crec, enso, f_sol, f_eol, get_inc)
    base = correr(nj, ej, crec, enso, f_sol, f_eol, 0.0)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi(f"{r['renta_congestion_MUSD']*1000:,.0f} kUSD", "Renta de congestión (día)")
    with k2:
        kpi(f"{r['lmp_medio'].mean():.1f} USD/MWh", "Precio nodal medio")
    with k3:
        ahorro = (base["costo_total_MUSD"] - r["costo_total_MUSD"]) * 1e3
        kpi(f"{ahorro:,.1f} kUSD/día", "Ahorro de despacho por GET vs. base")
    with k4:
        kpi(f"{ahorro*dias/1000:,.2f} MUSD/año", f"Valor anualizado ({dias} días) — orientativo")

    if r["energia_falla_MWh"] > 0:
        st.warning(f"⚠️ Hay energía no servida: {r['energia_falla_MWh']:,.0f} MWh en el día. "
                   "El sistema no alcanza a abastecer toda la demanda con los supuestos actuales.")

    tab1, tab2, tab3, tab4 = st.tabs(["📈 Precios nodales", "🔌 Corredores", "⚙️ Despacho", "ℹ️ Metodología"])

    with tab1:
        p = r["precios"]
        fig = go.Figure()
        for nid in nodos["id"]:
            fig.add_trace(go.Scatter(x=p["hora"], y=p[nid], mode="lines+markers", name=nid))
        fig.update_layout(height=430, xaxis_title="Hora", yaxis_title="USD/MWh", margin=dict(t=10, b=10),
                          legend=dict(orientation="h"))
        st.plotly_chart(fig, width="stretch")
        st.dataframe(pd.DataFrame({"Nodo": nodos["id"] + " · " + nodos["nodo"],
                                   "Precio medio (USD/MWh)": r["lmp_medio"].values.round(2),
                                   "Precio medio caso sin GET": base["lmp_medio"].values.round(2)}),
                     width="stretch", hide_index=True)
        st.caption("Precio nodal = dual del balance de energía en cada nodo y hora (LMP sin pérdidas).")

    with tab2:
        lin = r["lineas"].copy()
        lin_base = base["lineas"]
        lin["horas_congestionada_sin_GET"] = lin_base["horas_congestionada"].values
        st.dataframe(lin, width="stretch", hide_index=True)
        fig = go.Figure(go.Bar(x=lin["id"] + " " + lin["corredor"].str.slice(0, 28),
                               y=lin["horas_congestionada"], marker_color="#D91023", name="Con GET"))
        fig.add_trace(go.Bar(x=lin["id"] + " " + lin["corredor"].str.slice(0, 28),
                             y=lin["horas_congestionada_sin_GET"], marker_color="#bbbbbb", name="Sin GET"))
        fig.update_layout(barmode="group", height=380, yaxis_title="Horas congestionadas (de 24)",
                          margin=dict(t=10, b=120))
        st.plotly_chart(fig, width="stretch")
        st.caption("Congestión = flujo ≥ 99,5 % de la capacidad térmica (con GET si se aplica).")

    with tab3:
        g = r["gen_tecnologia"]
        fig = go.Figure()
        for tec in ["hidro", "termo", "eolica", "solar"]:
            fig.add_trace(go.Scatter(x=g["hora"], y=g[tec], stackgroup="one", name=NOMBRES_TEC[tec],
                                     line=dict(color=COLORES_TEC[tec])))
        fig.add_trace(go.Scatter(x=g["hora"], y=g["demanda_MW"], mode="lines", name="Demanda",
                                 line=dict(color="black", dash="dash")))
        fig.update_layout(height=420, yaxis_title="MW", xaxis_title="Hora", margin=dict(t=10, b=10),
                          legend=dict(orientation="h"))
        st.plotly_chart(fig, width="stretch")
        sel = st.selectbox("Enlace a graficar", r["flujos"].columns[1:].tolist(), index=4)
        fl = r["flujos"]
        cap = float(r["lineas"].set_index("id").loc[sel, "capacidad_MW"])
        fig2 = go.Figure(go.Scatter(x=fl["hora"], y=fl[sel], mode="lines+markers", name="Flujo (MW)"))
        fig2.add_hline(y=cap, line_dash="dot", line_color="red", annotation_text="+cap.")
        fig2.add_hline(y=-cap, line_dash="dot", line_color="red", annotation_text="-cap.")
        fig2.update_layout(height=320, yaxis_title="MW (+ desde → hasta)", margin=dict(t=10, b=10))
        st.plotly_chart(fig2, width="stretch")

    with tab4:
        st.markdown(
            f"""
- **Formulación:** optimización lineal (HiGHS) de costo mínimo con balance nodal, flujo de transporte y
  límites de capacidad por enlace.
- **Costo de falla:** {M.COSTO_FALLA:.0f} USD/MWh (energía no servida).
- **Hidrología:** factor sobre la hidroelectricidad disponible según ENSO: {M.FACTOR_ENSO}.
- **Demanda:** perfil horario y pico coincidente de {7941.78:,.0f} MW (OSINERGMIN 2025), repartido por nodo.
- **GET / DLR:** multiplica la capacidad de todos los enlaces por (1 + incremento). Es una prueba de *valor*
  de la tecnología, no un diseño de línea.
- **Límites:** no incluye flujo AC, pérdidas, contingencias N-1 ni restricciones de tensión. Para planificación
  use el snapshot OSM depurado con PyPSA o pandapower (ver `doc/METODOLOGIA.md`).
"""
        )


# ═══════════════════════════════════════════════════════════════════════
#  🌊 ENSO E HIDROLOGÍA
# ═══════════════════════════════════════════════════════════════════════
elif pagina == "🌊 ENSO e hidrología":
    st.title("🌊 ENSO e hidrología en el SEIN")
    st.markdown(
        "La hidroelectricidad aporta cerca de la mitad de la capacidad instalada del SEIN, por lo que la "
        "sequía (La Niña/El Niño costero) afecta precios y congestión, sobre todo en la zona centro y sur."
    )
    oni = leer_csv("oni_noaa.csv")
    oni["Fecha"] = pd.to_datetime(oni["Fecha"])
    desde = st.slider("Desde el año", 1950, 2026, 1990)
    o = oni[oni["Fecha"].dt.year >= desde]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=o["Fecha"], y=o["ONI"], marker_color=np.where(o["ONI"] >= 0.5, "#D91023",
                         np.where(o["ONI"] <= -0.5, "#1f77b4", "#bbbbbb"))))
    fig.add_hline(y=0.5, line_dash="dot", annotation_text="El Niño (≥0,5)")
    fig.add_hline(y=-0.5, line_dash="dot", annotation_text="La Niña (≤−0,5)")
    fig.update_layout(height=380, yaxis_title="ONI (°C)", margin=dict(t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("Índice ONI (NOAA/CPC) — región Niño 3.4. Ver `data/reference/oni_noaa.csv`.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Efecto simulado sobre precios y congestión")
        nodos = leer_csv("sein_nodos.csv")
        enlaces = leer_csv("sein_enlaces.csv")
        nj, ej = nodos.to_json(), enlaces.to_json()
        filas = []
        for esc in M.FACTOR_ENSO:
            rr = correr(nj, ej, 0.0, esc, 1.0, 1.0, 0.0)
            filas.append({"Escenario": esc, "Factor hidro": M.FACTOR_ENSO[esc],
                          "Precio medio (USD/MWh)": round(rr["lmp_medio"].mean(), 1),
                          "Renta congestión (kUSD/día)": round(rr["renta_congestion_MUSD"] * 1000, 1),
                          "Energía no servida (MWh)": round(rr["energia_falla_MWh"], 0)})
        st.dataframe(pd.DataFrame(filas), width="stretch", hide_index=True)
    with c2:
        st.markdown("#### Qué observar")
        st.markdown(
            "- En **El Niño fuerte** cae la hidro disponible del Centro y del Sur Oriente: aumenta la "
            "dependencia del gas de Camisea y sube el precio de la costa.\n"
            "- En **La Niña** la hidro abundante puede saturar los enlaces hacia la costa: la congestión se desplaza "
            "y aparecen diferencias de precio entre nodos.\n"
            "- El **Niño costero** (ENFEN, lluvias e inundaciones en el norte) no está en el índice ONI: "
            "pendiente incorporar su serie oficial."
        )
    st.info("Pendiente de datos: serie mensual de caudales de cuencas (ANA) y el índice de Niño costero (ENFEN). "
            "Son contribuciones bienvenidas (ver 🤝 Colaboración).")


# ═══════════════════════════════════════════════════════════════════════
#  🗄️ DATOS PERÚ
# ═══════════════════════════════════════════════════════════════════════
elif pagina == "🗄️ Datos Perú":
    st.title("🗄️ Catálogo de datos del sistema eléctrico peruano")
    st.markdown("Fuentes oficiales y abiertas. Filtre por categoría o busque por palabra clave.")
    catalogo = pd.DataFrame([
        ("Operación", "COES — Comité de Operación Económica del Sistema", "Demanda, generación, programación, planes de transmisión y EPO", "https://www.coes.org.pe"),
        ("Regulación", "OSINERGMIN — Supervisión y tarifas", "Fichas técnicas de líneas, compendios de proyectos, tarifas de transmisión", "https://www.osinergmin.gob.pe"),
        ("Política", "MINEM — Dirección General de Electricidad", "Informes técnicos, Balance Nacional de Energía, planes", "https://www.gob.pe/minem"),
        ("Datos abiertos", "Portal Nacional de Datos Abiertos (Perú)", "Conjuntos de datos del sector energía", "https://www.datosabiertos.gob.pe"),
        ("Clima", "SENAMHI", "Precipitación, temperatura, series climáticas", "https://www.senamhi.gob.pe"),
        ("ENSO", "ENFEN — Estudio Nacional del Fenómeno El Niño", "Comunicados sobre Niño costero", "https://www.enfen.gob.pe"),
        ("Hidrología", "ANA — Autoridad Nacional del Agua", "Caudales, cuencas, recursos hídricos", "https://www.ana.gob.pe"),
        ("ENSO global", "NOAA CPC — Índice ONI", "Índice oceánico de El Niño (región 3.4)", "https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php"),
        ("Red (geometría)", "OpenStreetMap / Overpass API", "Líneas, subestaciones y centrales (ODbL)", "https://www.openstreetmap.org"),
        ("Límites", "geoBoundaries", "Contornos administrativos (ADM0)", "https://www.geoboundaries.org"),
        ("Plantas globales", "Global Power Plant Database (WRI)", "Inventario de centrales con capacidad y combustible", "https://datasets.wri.org/dataset/globalpowerplantdatabase"),
        ("Plantas globales", "Global Energy Monitor (GEM)", "Trackers de centrales y transmisión (incluye Perú)", "https://globalenergymonitor.org"),
        ("Transmisión", "ISA / Transmantaro (proyectos)", "Información de la línea 500 kV Mantaro–Marcona–Socabaya–Montalvo", "https://www.isa.co"),
    ], columns=["Categoría", "Fuente", "Qué aporta", "Enlace"])
    q = st.text_input("Buscar", "")
    cat = st.multiselect("Categoría", sorted(catalogo["Categoría"].unique()))
    df = catalogo.copy()
    if q:
        df = df[df.apply(lambda r: q.lower() in " ".join(map(str, r.values)).lower(), axis=1)]
    if cat:
        df = df[df["Categoría"].isin(cat)]
    st.dataframe(df, width="stretch", hide_index=True,
                 column_config={"Enlace": st.column_config.LinkColumn("Enlace")})
    st.download_button("⬇️ Descargar catálogo (CSV)", df.to_csv(index=False).encode("utf-8"),
                       "catalogo_datos_peru.csv", "text/csv")
    st.caption("Las URLs se citan como referencia; verifique disponibilidad antes de automatizar descargas.")


# ═══════════════════════════════════════════════════════════════════════
#  📋 POLÍTICA Y REGULACIÓN
# ═══════════════════════════════════════════════════════════════════════
elif pagina == "📋 Política y regulación":
    st.title("📋 Política y regulación del sector eléctrico peruano")
    st.markdown(
        "Marco normativo relevante para la expansión de transmisión y la integración de renovables. "
        "**Verifique la versión vigente** del texto legal antes de citarlo en un informe formal."
    )
    st.dataframe(pd.DataFrame([
        ("Ley de Concesiones Eléctricas (DL 25844, 1997)", "Estructura del sector, concesiones de generación y transmisión, precios regulados."),
        ("Ley 28832 (2006)", "Desarrollo eficiente de la generación; mecanismos de expansión y planificación de la transmisión."),
        ("DL 1002 (2008)", "Promoción de la inversión en energías renovables no convencionales (RER)."),
        ("Plan de Transmisión (COES, vinculante)", "Proyectos de expansión de la red troncal aprobados por el Ministerio/Osinergmin; base para la licitación de obras."),
        ("Estudios de Pre Operatividad (EPO)", "Requisito técnico del COES para incorporar centrales nuevas al SEIN."),
        ("Ley 32249 (2025)", "Citada en prensa especializada como impulsora de la expansión solar en el sur. Verificar texto y alcance."),
    ], columns=["Norma / instrumento", "Relevancia para DLR / GET y transmisión"]),
        width="stretch", hide_index=True)
    st.subheader("Preguntas de política para el estudio")
    st.markdown(
        "- ¿Quién paga la congestión y cómo se asignan los costos de la expansión (peaje, licitación, mercado)?\n"
        "- ¿Pueden los DLR/GET reconocerse como alternativa a obras nuevas en el plan de transmisión?\n"
        "- ¿Qué incentivos hay para la repotenciación en líneas existentes?\n"
        "- ¿Cómo se reflejan la hidrología y el Niño costero en la planificación del sistema?"
    )


# ═══════════════════════════════════════════════════════════════════════
#  🤝 COLABORACIÓN
# ═══════════════════════════════════════════════════════════════════════
elif pagina == "🤝 Colaboración":
    st.title("🤝 Colabore con el dashboard SEIN Perú")
    st.markdown(
        "Esta plataforma está pensada para construirse entre varios investigadores y profesionales. "
        "Puede aportar **datos**, **correcciones**, **nuevos análisis** o **visualizaciones**."
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### ¿Cómo participar?")
        st.markdown(
            "1. **Descargue** una plantilla (abajo) y corrija o complete los valores con su **fuente**.\n"
            "2. **Pruébela** en la pestaña 🔴 Congestión y GET con el panel *Usar datos propios*.\n"
            "3. **Proponga el cambio** en el repositorio (issue o pull request) citando la fuente oficial.\n"
            "4. Si tiene una **serie de datos** (caudales, demanda, tablas de centrales), abra un issue con el enlace."
        )
        st.markdown("### Prioridades abiertas")
        st.dataframe(pd.DataFrame([
            ("Alta", "Tabla de centrales por nodo (COES) para reemplazar la distribución estimada", "sein_nodos.csv"),
            ("Alta", "Capacidades térmicas y longitudes reales de líneas 500/220 kV", "sein_enlaces.csv"),
            ("Alta", "Demanda horaria por nodo/región (COES)", "sein_perfiles_horarios.csv"),
            ("Media", "Serie mensual de caudales de cuencas (ANA)", "nuevo"),
            ("Media", "Índice de Niño costero (ENFEN)", "nuevo"),
            ("Media", "Parámetros DLR: temperatura de diseño, viento, clima local", "nuevo"),
        ], columns=["Prioridad", "Dato", "Archivo destino"]), width="stretch", hide_index=True)
    with c2:
        st.markdown("### Plantillas de datos")
        for nombre in ["sein_nodos.csv", "sein_enlaces.csv", "sein_perfiles_horarios.csv",
                       "sein_tecnologia_2026.csv", "sein_indicadores.csv"]:
            st.download_button(f"⬇️ {nombre}", leer_csv(nombre).to_csv(index=False).encode("utf-8"),
                               nombre, "text/csv", key=f"dl_{nombre}")
        st.markdown("### Autoría y licencia")
        st.markdown(
            "- Marco metodológico y dashboard base: **Prof. Sergio Rivera** (Universidad Nacional de Colombia), "
            "adaptado de *Dashboard SIN Nodal* (Colombia).\n"
            "- Datos de OpenStreetMap: © colaboradores de OSM, licencia **ODbL**.\n"
            "- Datos oficiales: citar COES, OSINERGMIN, MINEM, NOAA según corresponda.\n"
            "- Los parámetros marcados como *ESTIMADO* son supuestos de trabajo, no datos oficiales."
        )
    st.info("Consultas de colaboración o propuestas de consultoría: contacte al autor a través del repositorio.")


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS PARA LAS PÁGINAS NUEVAS
# ═══════════════════════════════════════════════════════════════════════
MODOS_EC = {
    "Sin interconexión con Ecuador": (None, 0),
    "Actual Zorritos–Machala 220 kV (≈332 MW)": ("220", 332),
    "Proyecto 500 kV (etapa 1, 650 MW)": ("500", 650),
    "Proyecto ampliado 500 kV (1 000 MW)": ("500", 1000),
}


def con_ecuador(nodos: pd.DataFrame, enlaces: pd.DataFrame, modo: str):
    """Devuelve (nodos, enlaces) con un nodo equivalente 'EC' y un enlace N1–EC según el modo."""
    n = nodos.copy()
    e = enlaces.copy()
    if "externo" not in n.columns:
        n["externo"] = 0
    tension, mw = MODOS_EC[modo]
    if tension is None:
        return n, e
    fila_ec = {
        "id": "EC", "nodo": "Ecuador (sistema equivalente, supuesto)", "region_zona": "Externo",
        "lat": -2.2, "lon": -79.9, "demanda_max_mw_est": 2800, "hidro_mw": 2500, "termo_mw": 1200,
        "eolica_mw": 0, "solar_mw": 0, "costo_termo_usd_mwh": 95, "costo_hidro_usd_mwh": 15,
        "fuente_nivel": "SUPUESTO para ilustrar intercambio; reemplazar con datos CENACE/CELEC", "externo": 1,
    }
    n = pd.concat([n, pd.DataFrame([fila_ec])], ignore_index=True)
    fila_l = {"id": "IE", "desde": "N1", "hasta": "EC", "tension_kv": int(tension),
              "capacidad_mw_est": mw, "corredor": f"Interconexión Perú–Ecuador ({modo})",
              "fuente_nivel": "Ver peru_interconexiones.csv"}
    e = pd.concat([e, pd.DataFrame([fila_l])], ignore_index=True)
    return n, e


def correr_con(nodos: pd.DataFrame, enlaces: pd.DataFrame, **kw):
    return correr(nodos.to_json(), enlaces.to_json(), kw.get("crec", 0.0), kw.get("enso", "Normal"),
                  kw.get("f_sol", 1.0), kw.get("f_eol", 1.0), kw.get("get_inc", 0.0))


# ═══════════════════════════════════════════════════════════════════════
#  🔥 CONGESTIÓN DOCUMENTADA
# ═══════════════════════════════════════════════════════════════════════
if pagina == "🔥 Congestión documentada":
    st.title("🔥 Congestiones documentadas en el SEIN")
    st.markdown(
        "Restricciones de transmisión reportadas en documentos oficiales del COES, observaciones de agentes "
        "y estudios de preoperatividad (EPO). Se cruzan con los **horas de congestión simuladas** por el modelo "
        "del caso base, para ver qué corredores el modelo reproduce y cuáles no."
    )
    cong = leer_csv("peru_congestiones_documentadas.csv")
    nodos = leer_csv("sein_nodos.csv")
    enlaces = leer_csv("sein_enlaces.csv")
    base = correr_con(nodos, enlaces)
    hc = base["lineas"].set_index("id")["horas_congestionada"].to_dict()
    cong["horas_simuladas_(modelo_base)"] = cong["modelo_id"].map(hc).fillna(0).astype(int)

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi(f"{len(cong)}", "Restricciones documentadas")
    with c2:
        kpi(f"{cong['zona'].nunique()}", "Zonas afectadas")
    with c3:
        kpi(f"{(cong['horas_simuladas_(modelo_base)'] > 0).sum()}", "Con congestión simulada en el modelo")

    t1, t2, t3 = st.tabs(["📋 Registro", "📊 Contraste modelo vs documentos", "🧭 Lectura técnica"])
    with t1:
        zonas = st.multiselect("Filtrar por zona", sorted(cong["zona"].unique()))
        df = cong[cong["zona"].isin(zonas)] if zonas else cong
        st.dataframe(df, width="stretch", hide_index=True)
        st.download_button("⬇️ Descargar registro (CSV)", df.to_csv(index=False).encode("utf-8"),
                           "congestiones_documentadas_peru.csv", "text/csv")
    with t2:
        fig = go.Figure(go.Bar(x=cong["id"] + " " + cong["corredor"].str.slice(0, 34),
                               y=cong["horas_simuladas_(modelo_base)"], marker_color="#D91023"))
        fig.update_layout(height=420, yaxis_title="Horas congestionadas simuladas (de 24)",
                          margin=dict(t=10, b=160))
        st.plotly_chart(fig, width="stretch")
        st.caption("Solo se muestran horas simuladas para los corredores asociados a un enlace del modelo "
                   "(columna modelo_id). Varias restricciones documentadas son de nivel de subestación o de "
                   "contingencia y el modelo de transporte no las captura.")
    with t3:
        st.markdown(
            """
**Patrones que se repiten en la documentación:**
1. **Sur (Ica–Arequipa–Moquegua):** concentración de solar y eólica con transformación 500/220 kV limitada
   (San José, Socabaya, Montalvo). Los estudios anticipan congestión Centro–Sur en horas sin sol desde 2027.
2. **Eje Poroma–Chilca:** el enlace existente (840 MVA) no alcanza para la generación renovable del sur medio;
   la solución vinculante es una segunda vía paralela.
3. **Lima sur (Alto Pradera, San Juan):** desbalances de flujo en líneas 220 kV paralelas que se resuelven con
   reconfiguraciones de topología.
4. **Esquemas de rechazo de generación (ERAG):** se usan hoy para contener sobrecargas mayores al 20 %;
   un GET (DLR o repotenciación) podría reducir su uso y el *curtailment*.

**Relevancia para DLR/GET:** en corredores con sobrecarga térmica en condiciones de viento frío (sur, altiplano),
el DLR puede liberar margen sin obra; en tramos con falta de capacidad estructural (p. ej. Poroma–Chilca),
la repotenciación con HTLS o un enlace nuevo son más pertinentes. Ver la pestaña 🧩 DLR y GET.
"""
        )
        st.caption("Fuentes: COES Carta ENG/446-2023 (comentarios al diagnóstico 2025-2034); COES EPO COES/D/DP-229-2023 "
                   "y COES/D/DP-677-2023; informe COES/DP-02-2022; comentarios ISA al diagnóstico PT 2025-2034.")


# ═══════════════════════════════════════════════════════════════════════
#  🌎 INTERCONEXIONES INTERNACIONALES
# ═══════════════════════════════════════════════════════════════════════
elif pagina == "🌎 Interconexiones internacionales":
    st.title("🌎 Interconexiones internacionales del Perú")
    st.markdown(
        "El Perú tiene hoy un único enlace internacional operativo, con Ecuador, de capacidad limitada. "
        "Chile y Bolivia tienen propuestas de estudio; Colombia solo cuenta con estudios regionales. "
        "El caso de Ecuador se simula en el modelo para medir su efecto sobre precios y congestión."
    )
    inter = leer_csv("peru_interconexiones.csv")
    nodos = leer_csv("sein_nodos.csv")
    enlaces = leer_csv("sein_enlaces.csv")

    t1, t2, t3 = st.tabs(["🗺️ Mapa y registro", "⚡ Simulación con Ecuador", "🧭 Lectura regional"])
    with t1:
        fig = go.Figure()
        if GIS.departamentos():
            for feat in GIS.departamentos()["features"]:
                geom = feat["geometry"]
                polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
                for poly in polys:
                    anillo = poly[0]
                    fig.add_trace(go.Scatter(x=[p[0] for p in anillo], y=[p[1] for p in anillo], mode="lines",
                                             line=dict(color="#c9d3df", width=1), hoverinfo="skip", showlegend=False))
        vecinos = [
            ("Ecuador (Machala)", -3.26, -79.96, "#D91023", "Ecuador"),
            ("Ecuador (Zorritos, PE)", -3.67, -80.66, "#D91023", "Ecuador"),
            ("Chile (Parinacota)", -18.15, -69.25, "#1f77b4", "Chile (propuesta)"),
            ("Bolivia (Desaguadero, aprox.)", -16.56, -69.04, "#2ca02c", "Bolivia (propuesta)"),
            ("Colombia (Leticia, aprox.)", -4.21, -69.94, "#7f7f7f", "Colombia (sin enlace)"),
        ]
        for nombre, la, lo, col, _ in vecinos:
            fig.add_trace(go.Scatter(x=[lo], y=[la], mode="markers+text", text=[nombre], textposition="top center",
                                     marker=dict(size=12, color=col), name=nombre))
        n1 = nodos.set_index("id").loc["N1"]
        for nombre, la, lo, col, _ in vecinos:
            fig.add_trace(go.Scatter(x=[n1["lon"], lo], y=[n1["lat"], la], mode="lines",
                                     line=dict(color=col, width=1, dash="dot"), showlegend=False, hoverinfo="skip"))
        fig.update_layout(height=600, margin=dict(t=10, b=0), plot_bgcolor="white",
                          xaxis=dict(range=[-82, -67], title="Longitud", showgrid=False),
                          yaxis=dict(range=[-19.5, 0.5], title="Latitud", showgrid=False, scaleanchor="x"),
                          legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig, width="stretch")
        st.caption("Coordenadas de los puntos de frontera aproximadas. Las líneas punteadas esquematizan la conexión "
                   "lógica desde el nodo Norte (N1), no el trazado real.")
        st.dataframe(inter, width="stretch", hide_index=True)
    with t2:
        st.markdown("Compare el efecto de incorporar el enlace con Ecuador manteniendo los demás supuestos.")
        c1, c2, c3 = st.columns(3)
        with c1:
            crec = st.slider("Crecimiento de demanda (%)", 0, 20, 0, 1, key="ie_crec") / 100
        with c2:
            enso = st.selectbox("Escenario ENSO", list(M.FACTOR_ENSO.keys()), index=2, key="ie_enso")
        with c3:
            modo_a = st.selectbox("Escenario A", list(MODOS_EC.keys()), index=0, key="ie_a")
            modo_b = st.selectbox("Escenario B", list(MODOS_EC.keys()), index=2, key="ie_b")
        ra = correr_con(*con_ecuador(nodos, enlaces, modo_a), crec=crec, enso=enso)
        rb = correr_con(*con_ecuador(nodos, enlaces, modo_b), crec=crec, enso=enso)
        comp = pd.DataFrame({
            "Indicador": ["Precio medio Perú (USD/MWh)", "Renta de congestión (kUSD/día)",
                          "Energía no servida (MWh/día)", "Costo total de despacho (MUSD/día)"],
            "A": [round(ra["lmp_medio"][[n for n in nodos['id']]].mean(), 2),
                  round(ra["renta_congestion_MUSD"] * 1000, 1), round(ra["energia_falla_MWh"], 1),
                  round(ra["costo_total_MUSD"], 3)],
            "B": [round(rb["lmp_medio"][[n for n in nodos['id']]].mean(), 2),
                  round(rb["renta_congestion_MUSD"] * 1000, 1), round(rb["energia_falla_MWh"], 1),
                  round(rb["costo_total_MUSD"], 3)],
        })
        comp["Δ (B − A)"] = (comp["B"] - comp["A"]).round(3)
        st.dataframe(comp, width="stretch", hide_index=True)
        flujo = rb["flujos"]["IE"] if "IE" in rb["flujos"].columns else None
        if flujo is not None:
            fig = go.Figure(go.Scatter(x=rb["flujos"]["hora"], y=flujo, mode="lines+markers",
                                       name="Flujo Perú→Ecuador (MW)"))
            fig.add_hline(y=0, line_color="gray")
            fig.update_layout(height=320, xaxis_title="Hora", yaxis_title="MW (+ exporta Perú)",
                              margin=dict(t=10, b=10))
            st.plotly_chart(fig, width="stretch")
        st.caption("Ecuador se modela como un nodo equivalente con supuestos de demanda y generación "
                   "(sein_nodos.csv, fila EC, marcada como SUPUESTO). El resultado es ilustrativo del "
                   "mecanismo, no una proyección del intercambio real.")
        st.info("Con los supuestos actuales el flujo máximo Perú→Ecuador/Ecuador→Perú es ≈300 MW. Por eso los "
                "escenarios de 650 y 1 000 MW dan el mismo resultado: la capacidad adicional no se satura. "
                "El valor de la ampliación depende de la oferta excedentaria de Ecuador y de la hidrología de ambos "
                "países; es un resultado a validar con datos de CENACE y COES.")
    with t3:
        st.markdown(
            """
- **Ecuador (único enlace activo):** la línea Zorritos–Machala 220 kV opera de forma limitada. La transferencia
  Perú→Ecuador de la interconexión 500 kV proyectada se estima en 500–650 MW por salidas de 500 kV del norte del SEIN
  (estabilidad transitoria). Ecuador licita una línea de 500 kV de 600 MW ampliable a 1 500 MW.
- **Chile:** propuesta de enlace 220 kV de 54 km con convertidor HVDC (50 Hz / 60 Hz). El estudio concluye que es técnicamente
  viable; falta el marco regulatorio para el intercambio.
- **Bolivia:** propuesta de línea de ~230 km con convertidor HVDC, relación beneficio-costo 1,3 en el estudio citado.
- **Colombia:** sin enlace físico; la integración andina aparece en estudios de prefactibilidad (CAN).
- **Implicación para DLR/GET:** el norte peruano concentra la transferencia hacia Ecuador. Cualquier aumento de
  capacidad térmica en 500/220 kV del norte tiene valor directo para la capacidad de exportación/importación.
"""
        )


# ═══════════════════════════════════════════════════════════════════════
#  🧩 DLR Y GET
# ═══════════════════════════════════════════════════════════════════════
elif pagina == "🧩 DLR y GET":
    st.title("🧩 DLR y otras tecnologías de incremento de capacidad (GET)")
    st.markdown(
        "Comparación de costos y ganancias de capacidad reportados para cada tecnología, y una calculadora "
        "simple de **valor económico y periodo de recuperación** para un corredor. Los rangos son de divulgación "
        "técnica y deben validarse con estudios de caso de la red peruana."
    )
    tec = leer_csv("dlr_get_tecnologias.csv")
    t1, t2, t3 = st.tabs(["📊 Comparativo", "🧮 Calculadora de corredor", "🧠 Estrategia para el Perú"])
    with t1:
        st.dataframe(tec, width="stretch", hide_index=True)
        dat = tec.dropna(subset=["costo_usd_por_milla_min"]).copy()
        dat = dat[dat["costo_usd_por_milla_max"] > 0]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=dat["tecnologia"], y=dat["costo_usd_por_milla_min"], name="Mín. USD/milla",
                             marker_color="#1f77b4"))
        fig.add_trace(go.Bar(x=dat["tecnologia"], y=dat["costo_usd_por_milla_max"], name="Máx. USD/milla",
                             marker_color="#9ecae1"))
        fig.update_layout(barmode="group", yaxis_type="log", height=420, yaxis_title="USD por milla (escala log)",
                          margin=dict(t=10, b=160))
        st.plotly_chart(fig, width="stretch")
        st.caption("Escala logarítmica. Fuentes de divulgación: Harbinger Land, CleanTechnica, Forbes, Energy Solutions, Green Fuel Journal.")
    with t2:
        c1, c2, c3 = st.columns(3)
        with c1:
            km = st.number_input("Longitud del corredor (km)", 10.0, 800.0, 150.0, 10.0)
            mw = st.number_input("Capacidad térmica actual (MW)", 50.0, 3000.0, 840.0, 10.0)
        with c2:
            uplift = st.slider("Ganancia de capacidad DLR (%)", 5, 40, 15, 1) / 100
            horas = st.slider("Horas/año con congestión en el corredor", 0, 8760, 1200, 50)
        with c3:
            spread = st.number_input("Diferencia de precio en congestión (USD/MWh)", 0.0, 200.0, 25.0, 1.0)
            tec_sel = st.selectbox("Alternativa de comparación",
                                   ["HTLS reconductoring", "Línea nueva 500 kV"])
        millas = km / 1.609344
        costo_dlr = millas * 47500
        cost_map = {"HTLS reconductoring": 650000, "Línea nueva 500 kV": 3800000}
        costo_alt = millas * cost_map[tec_sel]
        delta_mw = mw * uplift
        valor_anual = delta_mw * horas * spread  # USD/año (orientativo)
        pb_dlr = costo_dlr / valor_anual if valor_anual > 0 else float("inf")
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            kpi(f"{costo_dlr/1e6:,.2f} MUSD", f"Costo DLR ({millas:,.0f} millas)")
        with k2:
            kpi(f"+{delta_mw:,.0f} MW", "Capacidad liberada por DLR")
        with k3:
            kpi(f"{valor_anual/1e6:,.2f} MUSD/año", "Valor de congestión evitada (orientativo)")
        with k4:
            kpi(f"{pb_dlr:,.1f} años" if pb_dlr != float("inf") else "n. a.", "Recuperación simple con DLR")
        st.markdown(f"**Alternativa {tec_sel}:** costo ≈ **{costo_alt/1e6:,.1f} MUSD**; "
                    f"recuperación con el mismo valor anual ≈ **{(costo_alt/valor_anual if valor_anual>0 else float('inf')):,.1f} años**.")
        st.caption("Supuestos: costo DLR 47 500 USD/milla (punto medio de divulgación); HTLS 650 000 USD/milla; "
                   "línea nueva 500 kV 3,8 MUSD/milla. El valor usa la capacidad liberada por hora congestionada × "
                   "diferencia de precio; no incluye O&M, degradación del conductor ni riesgo de intermitencia.")
    with t3:
        st.markdown(
            """
**Secuencia propuesta para el estudio en el Perú**
1. **Identificar corredores con sobrecarga térmica y congestión recurrente** (pestaña 🔥 Congestión documentada).
2. **Medir la capacidad dinámica** en líneas piloto de 220 kV del sur y del norte (DLR o ampacidad ajustada ambiental).
   La ampacidad ajustada ambiental (AAR) es el primer paso de bajo costo.
3. **Clasificar la solución**:
   - *Congestión por condiciones ambientales frías y viento* → DLR (bajo costo, meses).
   - *Falta de capacidad estructural del conductor* → HTLS reconductoring en torres existentes (18–36 meses).
   - *Reparto desigual entre rutas paralelas* → control de flujo (compensación serie/FACTS) o topología.
   - *Falta de corredor* → obra nueva (7–15 años, con permisos).
4. **Incorporar el valor en la planificación:** el COES y OSINERGMIN evalúan proyectos de transmisión; los
   GET deben poder presentarse como alternativa en el Plan de Transmisión.
5. **Marco regulatorio:** reconocimiento de costos, incentivos a la repotenciación y responsabilidad por los
   sobrecostos de congestión (ver 📋 Política y regulación).
"""
        )


# ═══════════════════════════════════════════════════════════════════════
#  🧭 RED OSM, MAPYOURGRID Y PÓSTER
# ═══════════════════════════════════════════════════════════════════════
elif pagina == "🧭 Red OSM, MapYourGrid y póster":
    st.title("🧭 Calidad de la red OSM, MapYourGrid y póster Grid2Poster")
    st.markdown(
        "La geometría del dashboard proviene de **OpenStreetMap**. Esta página evalúa su cobertura frente a "
        "referencias y muestra el póster generado con **Grid2Poster** (Open Energy Transition, MIT)."
    )
    t1, t2, t3 = st.tabs(["📏 Cobertura OSM", "🖼️ Póster Grid2Poster", "🤝 Cómo mapear (MapYourGrid)"])
    with t1:
        if not GIS.disponible():
            st.warning("No hay snapshot OSM. Ejecute `python3 tools/build_osm_snapshot.py`.")
        else:
            k = GIS.kpis()
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                kpi(f"{k['lineas']:,}", "Tramos de línea (OSM)")
            with c2:
                kpi(f"{k['km_totales']:,.0f} km", "Longitud de ruta")
            with c3:
                kpi(f"{k['km_circuito']:,.0f} km-circ.", "Longitud por circuito")
            with c4:
                kpi(f"{k['subestaciones']:,}", "Subestaciones")
            ref = 30457  # ckm 2023 (Power Technology)
            cob = k["km_circuito"] / ref * 100
            st.metric("Cobertura frente a la referencia de longitud de transmisión (2023)",
                      f"{cob:,.0f} %", help=f"{k['km_circuito']:,.0f} km-circuito OSM vs {ref:,} ckm de referencia")
            st.progress(min(cob / 100, 1.0))
            tiers = pd.DataFrame([{"Nivel": t, "Tramos": v["n"], "km ruta": v["km"], "km-circuito": v["km_circuito"]}
                                  for t, v in k["por_tier"].items()])
            st.dataframe(tiers.sort_values("km ruta", ascending=False), width="stretch", hide_index=True)
            ops = pd.DataFrame(k["top_operadores"])
            sin = next((r["km"] for r in k["top_operadores"] if r["operador"] == "sin dato"), 0)
            st.metric("Km sin atributo de operador en OSM", f"{sin / max(k['km_totales'], 1) * 100:,.0f} %")
            st.dataframe(ops, width="stretch", hide_index=True)
            st.caption("Lectura: el snapshot tiene cobertura parcial de circuitos y casi todas las líneas carecen de "
                       "operador. Corregir esto es una tarea directa de MapYourGrid y de la comunidad OSM.")
    with t2:
        import os as _os
        for nombre, titulo in [("peru_grid_poster_midnight.png", "Tema Electric Midnight"),
                               ("peru_grid_poster_paper.png", "Tema Paper Grid")]:
            ruta = _os.path.join(ROOT, "data", "posters", nombre)
            if _os.path.exists(ruta):
                st.subheader(titulo)
                st.image(ruta, width=520)
                with open(ruta, "rb") as fh:
                    st.download_button(f"⬇️ Descargar {nombre}", fh.read(), nombre, "image/png", key=f"dl_{nombre}")
        st.caption("Generado con tools/grid2poster_peru.py (A3 a 110 dpi). Use dpi=300 para impresión.")
        st.markdown("Para regenerar: `python3 tools/grid2poster_peru.py`.")
    with t3:
        st.markdown(
            """
**MapYourGrid** es una iniciativa comunitaria que mapea redes eléctricas en OpenStreetMap, con foco en países
en desarrollo. Recursos:
- Guía de inicio: https://mapyourgrid.org/starter-kit/
- Mapear por país: https://mapyourgrid.org/map-it/
- Visor de infraestructura: https://openinframap.org

**Prioridades para el Perú**
1. Completar la tensión (`voltage`) y el operador en líneas de 220 y 500 kV.
2. Verificar trazados de los proyectos listados en 🧩 / 🌎 (p. ej. Mantaro–Nueva Yanango–Carapongo, Chilca–Bicentenario).
3. Mapear subestaciones y transformadores 500/220 kV del sur (San José, Montalvo, Poroma, Ocoña).
4. Registrar los enlaces internacionales (Zorritos–Machala) con sus tensiones reales.

Cuando se corrija OSM, basta con regenerar el snapshot (`tools/build_osm_snapshot.py`) y el póster.
"""
        )
        st.link_button("Abrir guía de MapYourGrid", "https://mapyourgrid.org/starter-kit/")


# ═══════════════════════════════════════════════════════════════════════
#  🌍 PERÚ EN EL MUNDO
# ═══════════════════════════════════════════════════════════════════════
elif pagina == "🌍 Perú en el mundo":
    st.title("🌍 Perú en el contexto internacional")
    ctx = leer_csv("peru_contexto_mundial.csv")
    st.dataframe(ctx, width="stretch", hide_index=True)
    st.subheader("Mix de generación reciente (may-2025 a abr-2026)")
    mix = pd.DataFrame({"Fuente": ["Hidro", "Gas natural", "Eólica + solar (aprox.)", "Otras"],
                        "%": [53, 35, 10, 2]})
    fig = go.Figure(go.Pie(labels=mix["Fuente"], values=mix["%"], hole=0.5,
                           marker_colors=["#1f77b4", "#7f7f7f", "#ffbf00", "#bbbbbb"]))
    fig.update_layout(height=340, margin=dict(t=10, b=10))
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.markdown(
            """
- **Dependencia del gas de Camisea** en la costa: la congestión en el norte y el sur es menos importante cuando la
  hidro del centro está disponible, pero el gas define el precio en Lima.
- **Sensibilidad a la hidrología:** un año de sequía en el centro reduce la oferta barata y reaparecen congestiones
  de evacuación hacia Lima y el sur.
- **Potencial renovable declarado** (MINEM, 2026): 937 GW solar, 20 GW eólica, 69 GW hidro (potencial técnico).
  La brecha entre potencial y capacidad es la razón de la planificación de transmisión.
- **Red de transmisión:** 30 457 ckm (2023) con proyección de 35 100 ckm en 2028, frente a 5,77 millones de ckm
  mundiales (2023).
"""
        )
    st.caption("Fuentes: lowcarbonpower.org; Enerdata; Power Technology (2024); IndustrialInfo (sept-2026). "
               "Las cifras deben citarse con fecha de consulta.")


# ═══════════════════════════════════════════════════════════════════════
#  💼 PROPUESTA IDOM
# ═══════════════════════════════════════════════════════════════════════
elif pagina == "💼 Propuesta IDOM":
    st.title("💼 Propuesta: evaluación de DLR y GET en el SEIN")
    st.markdown(
        "Marco de trabajo para la propuesta de **IDOM Advisory** (Public Sector PMO / Multilateral Development Projects) "
        "sobre el potencial técnico, económico y regulatorio de incremento de capacidad en transmisión del Perú. "
        "Esta plataforma sirve como **base de análisis preliminar** y demuestra la metodología propuesta."
    )
    st.markdown("### Alcance y paquetes de trabajo")
    wp = pd.DataFrame([
        ("WP1 · Diagnóstico de corredores", "Identificar corredores 220/500 kV congestionados o con restricción de evacuación",
         "Pestañas 🔥 Congestión documentada y 🔴 Congestión y GET", "Mapa de congestión y priorización"),
        ("WP2 · Potencial técnico DLR/GET", "Capacidad dinámica, AAR, HTLS, control de flujo y topología por corredor",
         "🧩 DLR y GET; datos de clima y conductor (pendientes)", "Matriz técnica por línea y ganancia estimada"),
        ("WP3 · Valor económico", "Costo de congestión evitado, ahorro de despacho, recuperación por tecnología",
         "🔴 Congestión y GET; calculadora 🧩", "Análisis costo-beneficio (VPN, TIR, payback) por corredor"),
        ("WP4 · Regulatorio e institucional", "Reconocimiento en planificación, incentivos y reparto de costos",
         "📋 Política y regulación", "Recomendaciones de marco regulatorio"),
        ("WP5 · Interconexiones y contexto", "Efecto de la interconexión con Ecuador y de proyectos Chile/Bolivia",
         "🌎 Interconexiones; 🌍 Perú en el mundo", "Escenarios de intercambio internacional"),
        ("WP6 · Datos y transparencia", "Red OSM depurada, MapYourGrid y datos abiertos",
         "🧭 Red OSM, MapYourGrid y póster; 🗄️ Datos Perú", "Base de datos abierta y reproducible"),
    ], columns=["Paquete", "Objetivo", "Dónde se ve en la plataforma", "Entregable"])
    st.dataframe(wp, width="stretch", hide_index=True)

    st.markdown("### Perfil del experto propuesto")
    st.markdown(
        "- Planificación y operación de sistemas de potencia en el SEIN (congestión, despacho y precios nodales).\n"
        "- Modelado de transmisión (flujo de potencia DC/AC, optimización) y uso de datos abiertos (OSM, MapYourGrid).\n"
        "- Evaluación económica de inversiones en transmisión y regulación del sector eléctrico latinoamericano.\n"
        "- Trabajo en proyectos de desarrollo multilateral: contexto, metodología y entregables para equipos de consultoría."
    )

    st.markdown("### Preguntas para la reunión de arranque")
    st.markdown(
        "1. ¿Qué corredores prioriza el cliente (p. ej. Poroma–Chilca, Centro–Sur, norte hacia Ecuador)?\n"
        "2. ¿Se dispone de datos de la operación (PRONÓSTICOS, restricciones, ERAG) del COES?\n"
        "3. ¿Hay líneas piloto disponibles para medición de DLR?\n"
        "4. ¿Qué horizonte temporal y escenarios de referencia (PT 2025-2034 o actualizado)?\n"
        "5. ¿Qué formato de entregables requiere IDOM (informes, modelos, tableros)?"
    )
    st.info("Contacto para la propuesta: Alejandro Gaviria — alejandro.gaviria@idom.com")
    st.caption("Esta página resume la propuesta; no constituye oferta comercial. Los datos de la plataforma son de "
               "trabajo y están marcados según su nivel de verificación.")


# ═══════════════════════════════════════════════════════════════════════
#  (Colaboración se mantiene en el bloque anterior)
# ═══════════════════════════════════════════════════════════════════════
