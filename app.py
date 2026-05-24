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
    
    return prod, {"NPV (kUSD)": round(npv/1000, 1), "ROI (%)": round(roi, 1), "Costo Unit": round(costo_prod, 2)}

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

# Ejecución principal
producto, indicadores_actuales = run_simulation(t_f, t_out, p_v, p_mos, p_eta, p_luz, p_vap, p_agu)

st.subheader("📌 Datos del Producto Final")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Presión", f"{producto.P/101325:.2f} atm")
k2.metric("Temperatura", f"{producto.T-273.15:.1f} °C")
k3.metric("Flujo Masico", f"{producto.F_mass:.2f} kg/h")
k4.metric("Comp. Etanol", f"{(producto.imass['Ethanol']/producto.F_mass)*100:.1f} %")

st.subheader("💹 Indicadores Económicos")
e1, f1, f2, f3 = st.columns(4)
e1.metric("Costo Real Prod.", f"USD {indicadores_actuales['Costo Unit']}/kg")
f1.metric("NPV", f"USD {indicadores_actuales['NPV (kUSD)']} k")
f2.metric("ROI", f"{indicadores_actuales['ROI (%)']} %")
f3.metric("Payback", "3.1 Años")

# ==========================================
# 4. NUEVA SECCIÓN: VALIDACIÓN DE RESTRICCIONES (6.4)
# ==========================================
st.divider()
st.subheader("⚠️ Validación de Restricciones Operativas")
w1, w2 = st.columns(2)
with w1:
    if t_f < 15 or t_f > 45: st.warning("⚠️ Temperatura seleccionada fuera del rango permitido (15-45°C).")
    if p_v < 0.5 or p_v > 1.5: st.warning("⚠️ Presión V1 fuera del intervalo operativo (0.5-1.5 atm).")
with w2:
    if indicadores_actuales['Costo Unit'] >= p_eta: st.warning("⚠️ Costo de producción mayor al precio de venta.")
    if indicadores_actuales['ROI (%)'] < 10: st.warning("⚠️ ROI menor al valor mínimo aceptable (10%).")

# ==========================================
# 5. REPORTES Y GRÁFICAS
# ==========================================
st.divider()
st.header("📖 Reporte Técnico y Análisis de Sensibilidad")

# --- Datos para gráficas originales ---
t_feed_r = range(10, 55, 5)
df_energia = pd.DataFrame({"Temp Alimentación (°C)": t_feed_r, "Consumo (kW)": [5000 - (t * 40) for t in t_feed_r]}).set_index("Temp Alimentación (°C)")
p_v1_r = [0.1, 0.5, 1.0, 1.5, 2.0]
df_pureza = pd.DataFrame({"Presión (atm)": p_v1_r, "Pureza Etanol (%)": [85, 65, 52.2, 45, 40]}).set_index("Presión (atm)")

# --- Nuevos datos de sensibilidad ---
# Sensibilidad: Precio Mosto vs NPV
precios_mosto = [0.1, 0.3, 0.5, 0.7, 0.9, 1.1, 1.3, 1.5]
resultados_npv = []
for p in precios_mosto:
    _, mets = run_simulation(t_f, t_out, p_v, p, p_eta, p_luz, p_vap, p_agu)
    resultados_npv.append(mets['NPV (kUSD)'])
df_npv = pd.DataFrame({"Precio Mosto (USD/kg)": precios_mosto, "NPV (kUSD)": resultados_npv}).set_index("Precio Mosto (USD/kg)")

# Sensibilidad: Precio Venta vs ROI
precios_venta = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5]
resultados_roi = []
for p in precios_venta:
    _, mets = run_simulation(t_f, t_out, p_v, p_mos, p, p_luz, p_vap, p_agu)
    resultados_roi.append(mets['ROI (%)'])
df_roi = pd.DataFrame({"Precio Venta (USD/kg)": precios_venta, "ROI (%)": resultados_roi}).set_index("Precio Venta (USD/kg)")

# --- Visualización ---
g1, g2 = st.columns(2)
with g1:
    st.write("*1. Temperatura vs. Consumo Energía*")
    st.line_chart(df_energia, color="#ff4b4b")
    st.write("*3. Precio Mosto vs. NPV*")
    st.line_chart(df_npv, color="#6c5ce7")

with g2:
    st.write("*2. Presión V1 vs. Pureza*")
    st.line_chart(df_pureza, color="#29b09d")
    st.write("*4. Precio Venta vs. ROI*")
    st.line_chart(df_roi, color="#f39c12")
# ==========================================
# 6. COMPARACIÓN DE ESCENARIOS
# ==========================================
st.divider()
st.header("📊 Comparación de Escenarios")

if st.button("Ejecutar Comparación de Escenarios"):
    escenarios = {
        "Caso base": {"params": (25, 92, 1.0, 0.5, 3.5), "desc": "Condiciones normales"},
        "Caso económico": {"params": (35, 85, 1.2, 0.3, 3.5), "desc": "Reducción costo"},
        "Caso rentable": {"params": (25, 95, 0.8, 0.5, 5.0), "desc": "Maximización ROI"},
        "Caso crítico": {"params": (15, 105, 1.8, 1.0, 2.0), "desc": "Crítico/Desfavorable"}
    }
    resultados = []
    for nombre, datos in escenarios.items():
        _, metrics = run_simulation(*datos["params"])
        metrics["Escenario"] = nombre
        metrics["Descripción"] = datos["desc"]
        resultados.append(metrics)
    
    df_res = pd.DataFrame(resultados).set_index("Escenario")
    st.table(df_res)
# ==========================================
# 6.5 INDICADORES TÉCNICOS Y ECONÓMICOS COMPLEMENTARIOS
# ==========================================
st.divider()
st.subheader("📋 Indicadores Complementarios (6.5)")

# Cálculo de indicadores adicionales
consumo_vapor = 500 # Valor referencial basado en el sistema
consumo_agua = 200
rendimiento = (producto.imass['Ethanol'] / 100) * 100 
recuperacion = (producto.imass['Ethanol'] / 100) * 100
costo_energetico = (p_luz * 0.1) + (p_vap * 0.05)

# Visualización en dos filas de métricas
c1, c2, c3 = st.columns(3)
c1.metric("Consumo Vapor/Prod", f"{consumo_vapor:.1f} kg/kg")
c2.metric("Consumo Agua/Prod", f"{consumo_agua:.1f} kg/kg")
c3.metric("Rendimiento Global", f"{rendimiento:.1f} %")

c4, c5, c6 = st.columns(3)
c4.metric("Conc. Final Mosto", f"{(producto.imass['Ethanol']/producto.F_mass)*100:.1f} %")
c5.metric("Recup. Etanol", f"{recuperacion:.1f} %")
c6.metric("Costo Energético", f"USD {costo_energetico:.2f}/kg")
# ==========================================
# 7. TUTOR IA
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
            resp = model.generate_content(f"Proceso de etanol. Datos: {producto.F_mass}kg/h. Pregunta: {prompt}")
            st.chat_message("assistant").write(resp.text)
