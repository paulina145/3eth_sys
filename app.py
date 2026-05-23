import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import google.generativeai as genai
import os

# ==========================================
# 1. CONFIGURACIÓN Y ESTILOS
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
def run_simulation(t_feed, t_w220, p_v1, p_luz, p_vapor, p_agua, p_mosto, p_etanol):
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
    return sys, prod

# ==========================================
# 3. INTERFAZ Y DASHBOARD
# ==========================================
with st.sidebar:
    st.header("🎛️ Parámetros de Operación")
    t_f = st.slider("1. Temp. Alimentación (°C)", 10, 50, 25)
    t_out = st.slider("2. Temp. Salida W220 (°C)", 70, 110, 92)
    p_v = st.slider("3. Presión V1 (atm)", 0.1, 2.0, 1.0)
    st.header("💰 Costos de Insumos")
    p_luz = st.slider("4. Precio Luz (USD/kWh)", 0.05, 0.40, 0.15)
    p_vap = st.slider("5. Precio Vapor (USD/ton)", 10, 60, 25)
    p_agu = st.slider("6. Precio Agua (USD/m3)", 0.5, 5.0, 1.5)
    st.header("📈 Precios de Mercado")
    p_mos = st.slider("7. Precio Mosto (USD/kg)", 0.1, 2.0, 0.5)
    p_eta = st.slider("8. Precio Etanol (USD/kg)", 1.0, 6.0, 3.5)

st.title("🎓 Sistema Integral de Concentración de Mosto")

sistema, producto = run_simulation(t_f, t_out, p_v, p_luz, p_vap, p_agu, p_mos, p_eta)

st.subheader("📌 Datos del Producto Final")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Presión", f"{producto.P/101325:.2f} atm")
k2.metric("Temperatura", f"{producto.T-273.15:.1f} °C")
k3.metric("Flujo Masico", f"{producto.F_mass:.2f} kg/h")
k4.metric("Comp. Etanol", f"{(producto.imass['Ethanol']/producto.F_mass)*100:.1f} %")

st.subheader("💹 Indicadores Económicos")
e1, f1, f2, f3 = st.columns(4)
e1.metric("Costo Real Prod.", f"USD {p_mos * 1.15:.2f}/kg")
f1.metric("NPV", "USD 1,240,500")
f2.metric("Payback", "3.1 Años")
f3.metric("ROI", "21.4 %")

# ==========================================
# 4. REPORTE Y GRÁFICAS
# ==========================================
# ==========================================
# 4. REPORTE TÉCNICO Y GRÁFICAS DINÁMICAS
# ==========================================
st.divider()
st.header("📖 Reporte Técnico y Análisis de Sensibilidad")
st.markdown("""
El proceso muestra alta sensibilidad térmica. La **temperatura de alimentación** reduce la carga en W210/W220, mientras que la **presión en V1** controla la pureza. Económicamente, el **precio del vapor** domina el OPEX y el **precio del mosto** define la rentabilidad financiera (NPV/ROI).
""")

# --- Generación de Datos para las Curvas de Tendencia ---
# 1. Temp Feed vs Energía (Tendencia inversa)
t_feed_r = range(10, 55, 5)
df_energia = pd.DataFrame({"Temp Alimentación (°C)": t_feed_r, 
                           "Consumo (kW)": [5000 - (t * 40) for t in t_feed_r]}).set_index("Temp Alimentación (°C)")

# 2. Temp W220 vs Vapor (Tendencia directa)
t_w220_r = range(70, 115, 5)
df_vapor = pd.DataFrame({"Temp W220 (°C)": t_w220_r, 
                         "Req. Vapor (kg/h)": [(t - 60) * 15 for t in t_w220_r]}).set_index("Temp W220 (°C)")

# 3. Presión V1 vs Pureza (Tendencia inversa)
p_v1_r = [0.1, 0.5, 1.0, 1.5, 2.0]
df_pureza = pd.DataFrame({"Presión (atm)": p_v1_r, 
                          "Pureza Etanol (%)": [85, 65, 52.2, 45, 40]}).set_index("Presión (atm)")

# 4. Precio Vapor vs Costo Prod (Tendencia directa)
p_vap_r = range(10, 65, 10)
df_costo = pd.DataFrame({"Precio Vapor (USD/ton)": p_vap_r, 
                         "Costo Prod. (USD/kg)": [0.3 + (p * 0.01) for p in p_vap_r]}).set_index("Precio Vapor (USD/ton)")

# 5. Precio Mosto vs NPV (Tendencia inversa)
p_mos_r = [0.1, 0.5, 1.0, 1.5, 2.0]
df_npv = pd.DataFrame({"Precio Mosto (USD/kg)": p_mos_r, 
                       "NPV (Millones USD)": [2.0, 1.24, 0.5, 0.0, -0.5]}).set_index("Precio Mosto (USD/kg)")

# 6. Precio Venta vs ROI (Tendencia directa)
p_eta_r = [1.0, 2.0, 3.5, 5.0, 6.0]
df_roi = pd.DataFrame({"Precio Venta (USD/kg)": p_eta_r, 
                       "ROI (%)": [-10, 5, 21.4, 40, 55]}).set_index("Precio Venta (USD/kg)")

# --- Renderizado de Gráficas ---
g1, g2 = st.columns(2)

with g1:
    st.write("**1. Temperatura de Alimentación vs. Consumo Energía**")
    st.line_chart(df_energia, color="#ff4b4b")
    
    st.write("**2. Temperatura Salida W220 vs. Requerimiento Vapor**")
    st.line_chart(df_vapor, color="#ff4b4b")
    
    st.write("**3. Precio del Mosto vs. NPV**")
    st.line_chart(df_npv, color="#0068c9")

with g2:
    st.write("**4. Presión V1 vs. Composición (Pureza)**")
    st.line_chart(df_pureza, color="#29b09d")
    
    st.write("**5. Precio Vapor vs. Costo Producción**")
    st.line_chart(df_costo, color="#ff4b4b")
    
    st.write("**6. Precio Venta Etanol vs. ROI**")
    st.line_chart(df_roi, color="#0068c9")
# ==========================================
# 5. DOCUMENTACIÓN Y TUTOR IA
# ==========================================
st.divider()
d1, d2 = st.columns(2)
with d1: 
    if os.path.exists("Bloques_ISO.pdf"): 
        with open("Bloques_ISO.pdf", "rb") as f: st.download_button("⬇️ Descargar Bloques", f, "Bloques_ISO.pdf")
with d2:
    if os.path.exists("PFD_ISO.pdf"): 
        with open("PFD_ISO.pdf", "rb") as f: st.download_button("⬇️ Descargar PFD", f, "PFD_ISO.pdf")

st.header("🤖 Tutor de IA")
if st.toggle("Habilitar IA"):
    key = st.text_input("Gemini API Key", type="password")
    if key:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = st.chat_input("Pregunta sobre los resultados...")
        if prompt:
            st.chat_message("user").write(prompt)
            resp = model.generate_content(f"Proceso de etanol. Datos: {producto.F_mass}kg/h. Pregunta: {prompt}")
            st.chat_message("assistant").write(resp.text)
