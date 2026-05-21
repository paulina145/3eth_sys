import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import google.generativeai as genai
import os

# ==========================================
# 1. CONFIGURACIÓN VISUAL Y ESTILOS (CSS)
# ==========================================
st.set_page_config(page_title="Concentración de Mosto - IMIQ", layout="wide")

st.markdown("""
    <style>
    [data-testid="stMetric"] { background-color: #ffffff !important; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid #d1d5db; }
    [data-testid="stMetricLabel"] > div { color: #4b5563 !important; font-weight: bold; }
    [data-testid="stMetricValue"] > div { color: #111827 !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. FUNCIÓN DE SIMULACIÓN
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

# [Aquí iría el resto de tu código original: Sidebar y Dashboard hasta el final...]

# ==========================================
# 3. NUEVA SECCIÓN: REPORTE TÉCNICO Y GRÁFICAS
# ==========================================
st.divider()
st.header("📖 Reporte Técnico: Análisis de Sensibilidad")

st.markdown("""
### Análisis de Operación
El proceso demuestra una alta sensibilidad a las variables térmicas. Un aumento en la **temperatura de alimentación** reduce el consumo energético, mientras que la **temperatura en W220** debe optimizarse para equilibrar la pureza frente al costo de vapor. La **presión en V1** es el factor determinante para la calidad de separación.

### Indicadores Económicos
El **precio del vapor** es el insumo más crítico para el costo operativo, mientras que el **precio del mosto** define la viabilidad financiera (NPV y ROI).
""")

# Gráficas integradas
st.subheader("📈 Análisis de Sensibilidad (Gráficas)")
g1, g2 = st.columns(2)
with g1:
    st.write("Temp. Alimentación vs. Consumo Energía")
    st.image("grafica1.png", use_container_width=True) # Sustituye con tus archivos
    st.write("Temp. Salida W220 vs. Vapor")
    st.image("grafica2.png", use_container_width=True)
with g2:
    st.write("Presión V1 vs. Composición")
    st.image("grafica3.png", use_container_width=True)
    st.write("Precio Vapor vs. Costo Prod.")
    st.image("grafica4.png", use_container_width=True)

g3, g4 = st.columns(2)
with g3:
    st.write("Precio Mosto vs. NPV")
    st.image("grafica5.png", use_container_width=True)
with g4:
    st.write("Precio Venta vs. ROI")
    st.image("grafica6.png", use_container_width=True)

# [Aquí cierras con el Modo Tutor IA...]
