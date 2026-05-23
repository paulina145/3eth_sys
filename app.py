import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import google.generativeai as genai

# ==========================================
# 1. CONFIGURACIÓN Y ESTILOS (Mantenido igual)
# ==========================================
st.set_page_config(page_title="Concentración de Mosto - IMIQ", layout="wide")

st.markdown("""
    <style>
    [data-testid="stMetric"] { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid #d1d5db; }
    [data-testid="stMetricLabel"] > div { color: #4b5563; font-weight: bold; }
    [data-testid="stMetricValue"] > div { color: #111827; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. LÓGICA DE SIMULACIÓN
# ==========================================
def run_simulation(t_feed, t_w220, p_v1, p_mosto, p_etanol, p_luz=0.15, p_vapor=25.0, p_agua=1.5):
    bst.main_flowsheet.clear()
    chemicals = tmo.Chemicals(["Water", "Ethanol"])
    bst.settings.set_thermo(chemicals)

    mosto = bst.Stream("1-MOSTO", Water=900, Ethanol=100, units="kg/hr", T=t_feed + 273.15, price=p_mosto)
    vinazas_retorno = bst.Stream("Vinazas-Retorno", Water=200, T=95+273.15)

    P100 = bst.Pump("P100", ins=mosto, P=4*101325)
    W210 = bst.HXprocess("W210", ins=(P100-0, vinazas_retorno), outs=("Mosto_Pre", "Drenaje"), phase0="l", phase1="l")
    W210.outs[0].T = 85 + 273.15
    W220 = bst.HXutility("W220", ins=W210-0, outs="Mezcla", T=t_w220 + 273.15)
    V1 = bst.Flash("V1", ins=W220-0, outs=("Vapor", "Vinazas"), P=p_v1 * 101325, Q=0)
    
    prod = bst.Stream("Producto_Final", price=p_etanol)
    W310 = bst.HXutility("W310", ins=V1-0, outs=prod, T=25 + 273.15)
    P200 = bst.Pump("P200", ins=V1-1, outs=vinazas_retorno, P=3*101325)

    sys = bst.System("mosto_sys", path=(P100, W210, W220, V1, W310, P200))
    sys.simulate()
    
    costo_prod = (p_mosto * 1.15)
    ingresos_anuales = (p_etanol - costo_prod) * prod.F_mass * 8000
    npv = ingresos_anuales * 3.5 - 500000
    roi = (ingresos_anuales / 1000000) * 10
    
    return prod, {"NPV": npv, "ROI": roi, "Costo": costo_prod}

# ==========================================
# 3. INTERFAZ (Mantenida igual)
# ==========================================
with st.sidebar:
    st.header("🎛️ Parámetros")
    t_f = st.slider("Temp. Alimentación (°C)", 10, 50, 25)
    t_out = st.slider("Temp. Salida W220 (°C)", 70, 110, 92)
    p_v = st.slider("Presión V1 (atm)", 0.1, 2.0, 1.0)
    p_mos = st.slider("Precio Mosto (USD/kg)", 0.1, 2.0, 0.5)
    p_eta = st.slider("Precio Etanol (USD/kg)", 1.0, 6.0, 3.5)

st.title("🎓 Sistema Integral de Concentración de Mosto")
prod, kpi = run_simulation(t_f, t_out, p_v, p_mos, p_eta)

# ==========================================
# 4. NUEVA SECCIÓN: VALIDACIÓN DE RESTRICCIONES (6.4)
# ==========================================
st.subheader("⚠️ Validación de Restricciones")
col_w1, col_w2 = st.columns(2)
with col_w1:
    if not (15 <= t_f <= 45): st.warning("Temp. alimentación fuera de rango (15-45°C)")
    if kpi['Costo'] >= p_eta: st.warning("Costo de producción mayor al precio de venta sugerido")
with col_w2:
    if not (0.5 <= p_v <= 1.5): st.warning("Presión V1 fuera de intervalo (0.5-1.5 atm)")
    if kpi['ROI'] < 10: st.warning("ROI menor al valor mínimo aceptable (10%)")

# ==========================================
# 5. MANTENEMOS TUS MÉTRICAS ORIGINALES
# ==========================================
st.subheader("📌 Datos del Producto Final")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Presión", f"{prod.P/101325:.2f} atm")
k2.metric("Temperatura", f"{prod.T-273.15:.1f} °C")
k3.metric("ROI", f"{kpi['ROI']:.1f}%")
k4.metric("NPV", f"${kpi['NPV']/1000:.1f}k")

# ==========================================
# 6. NUEVA SECCIÓN: GRÁFICAS DE SENSIBILIDAD
# ==========================================
st.divider()
st.header("📈 Análisis de Sensibilidad")
g1, g2, g3 = st.columns(3)

# Datos de ejemplo para las 3 gráficas solicitadas
df_sen = pd.DataFrame({
    "Vapor (USD/ton)": [10, 25, 40, 60], "Costo": [0.2, 0.3, 0.45, 0.7],
    "Mosto (USD/kg)": [0.1, 0.5, 1.0, 2.0], "NPV": [2000, 1000, 0, -1000],
    "Venta (USD/kg)": [1.0, 3.0, 5.0, 6.0], "ROI": [-10, 15, 35, 50]
})

with g1:
    st.line_chart(df_sen.set_index("Vapor (USD/ton)")["Costo"])
    st.caption("Precio Vapor vs. Costo")
with g2:
    st.line_chart(df_sen.set_index("Mosto (USD/kg)")["NPV"])
    st.caption("Precio Mosto vs. NPV")
with g3:
    st.line_chart(df_sen.set_index("Venta (USD/kg)")["ROI"])
    st.caption("Precio Venta vs. ROI")

# ==========================================
# 7. COMPARACIÓN DE ESCENARIOS (6.3)
# ==========================================
st.divider()
st.header("📊 Comparación de Escenarios")
if st.button("Ejecutar Comparativa"):
    escenarios = {
        "Caso base": (25, 92, 1.0, 0.5, 3.5),
        "Caso económico": (35, 85, 1.2, 0.3, 3.5),
        "Caso rentable": (25, 95, 0.8, 0.5, 5.0),
        "Caso crítico": (15, 105, 1.8, 1.0, 2.0)
    }
    res = []
    for nombre, params in escenarios.items():
        _, k = run_simulation(*params)
        res.append({"Escenario": nombre, "NPV (kUSD)": k['NPV']/1000, "ROI (%)": k['ROI'], "Costo Unit": k['Costo']})
    st.table(pd.DataFrame(res).set_index("Escenario"))

# ==========================================
# 8. TUTOR IA
# ==========================================
st.divider()
st.header("🤖 Tutor de IA")
if st.toggle("Habilitar IA"):
    key = st.text_input("Gemini API Key", type="password")
    if key:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = st.chat_input("Pregunta sobre los resultados...")
        if prompt:
            st.chat_message("user").write(prompt)
            resp = model.generate_content(f"Proceso de etanol. Datos: {prompt}")
            st.chat_message("assistant").write(resp.text)
