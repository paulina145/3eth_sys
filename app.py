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
# Se añadieron valores por defecto a los costos para evitar el error de argumentos faltantes
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
    
    # Cálculo de indicadores para la tabla
    costo_prod = (p_mosto * 1.15)
    ingresos = (p_etanol - costo_prod) * prod.F_mass * 8000
    npv = ingresos * 3.5 - 500000
    roi = (ingresos / 1000000) * 10
    
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

producto, _ = run_simulation(t_f, t_out, p_v, p_mos, p_eta, p_luz, p_vap, p_agu)

st.subheader("📌 Datos del Producto Final")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Presión", f"{producto.P/101325:.2f} atm")
k2.metric("Temperatura", f"{producto.T-273.15:.1f} °C")
k3.metric("Flujo Masico", f"{producto.F_mass:.2f} kg/h")
k4.metric("Comp. Etanol", f"{(producto.imass['Ethanol']/producto.F_mass)*100:.1f} %")

# ==========================================
# 4. COMPARACIÓN DE ESCENARIOS
# ==========================================
st.divider()
st.header("📊 Comparación de Escenarios")

if st.button("Ejecutar Comparación de Escenarios"):
    escenarios = {
        "Caso base": {"params": (25, 92, 1.0, 0.5, 3.5), "desc": "Condiciones normales"},
        "Caso económico": {"params": (35, 85, 1.2, 0.3, 3.5), "desc": "Reducción costo producción"},
        "Caso rentable": {"params": (25, 95, 0.8, 0.5, 5.0), "desc": "Optimización ROI"},
        "Caso crítico": {"params": (15, 105, 1.8, 1.0, 2.0), "desc": "Condiciones desfavorables"}
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
# 5. TUTOR IA
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
            
