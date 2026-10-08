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
    "🌊 ENSO e hidrología",
    "🗄️ Datos Perú",
    "📋 Política y regulación",
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
