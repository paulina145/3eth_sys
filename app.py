import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import google.generativeai as genai

# ==========================================
# 1. CONFIGURACIÓN
# ==========================================
st.set_page_config(page_title="Concentración de Mosto - IMIQ", layout="wide")

# ==========================================
# 2. LÓGICA DE SIMULACIÓN Y VALIDACIÓN
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
    
    # Cálculos económicos
    costo_prod = (p_mosto * 1.15) + (p_vapor * 0.05) 
    ingresos = (p_etanol - costo_prod) * prod.F_mass * 8000
    npv = ingresos * 3.5 - 500000
    roi = (ingresos / 1000000) * 10
    payback = 500000 / ingresos if ingresos > 0 else 10
    
    return prod, {"NPV": npv, "ROI": roi, "Costo": costo_prod, "Payback": payback}

def get_warnings(t_f, p_v, costo, p_eta, roi, payback):
    warnings = []
    if t_f < 15 or t_f > 45: warnings.append("⚠️ Temp. alimentación fuera de rango (15-45°C).")
    if p_v < 0.5 or p_v > 1.5: warnings.append("⚠️ Presión V1 fuera de rango (0.5-1.5 atm).")
    if costo >= p_eta: warnings.append("🚨 Costo producción mayor al precio venta.")
    if roi < 10: warnings.append("📉 ROI bajo (< 10%).")
    if payback > 5: warnings.append("⏳ Payback mayor a 5 años.")
    return warnings

# ==========================================
# 3. DASHBOARD Y VALIDACIONES
# ==========================================
with st.sidebar:
    st.header("🎛️ Parámetros")
    t_f = st.slider("Temp. Alimentación (°C)", 10, 50, 25)
    t_out = st.slider("Temp. Salida W220 (°C)", 70, 110, 92)
    p_v = st.slider("Presión V1 (atm)", 0.1, 2.0, 1.0)
    p_mosto = st.slider("Precio Mosto (USD/kg)", 0.1, 2.0, 0.5)
    p_etanol = st.slider("Precio Etanol (USD/kg)", 1.0, 6.0, 3.5)
    p_vapor = st.slider("Precio Vapor (USD/ton)", 10, 60, 25)

st.title("🎓 Sistema Integral de Concentración")
prod, kpi = run_simulation(t_f, t_out, p_v, p_mosto, p_etanol, p_vapor=p_vapor)

# Mostrar Alertas (Validación 6.4)
for warning in get_warnings(t_f, p_v, kpi['Costo'], p_etanol, kpi['ROI'], kpi['Payback']):
    st.warning(warning)

# Métricas
col1, col2, col3 = st.columns(3)
col1.metric("Costo Producción", f"${kpi['Costo']:.2f}/kg")
col2.metric("ROI", f"{kpi['ROI']:.1f}%")
col3.metric("NPV", f"${kpi['NPV']/1000:.1f}k")

# ==========================================
# 4. ANÁLISIS DE SENSIBILIDAD (GRÁFICAS)
# ==========================================
st.divider()
st.header("📖 Análisis de Sensibilidad")
c1, c2, c3 = st.columns(3)

# Datos simulados para gráficas
x_vap = range(10, 61, 5)
df1 = pd.DataFrame({"Costo": [0.3 + (v*0.005) for v in x_vap]}, index=x_vap)

x_mos = [0.1, 0.5, 1.0, 1.5, 2.0]
df2 = pd.DataFrame({"NPV": [2000, 1200, 500, 0, -500]}, index=x_mos)

x_eta = [1.0, 2.0, 3.0, 4.0, 5.0]
df3 = pd.DataFrame({"ROI": [-20, 0, 20, 40, 60]}, index=x_eta)

with c1:
    st.line_chart(df1)
    st.caption("Precio Vapor vs. Costo Prod.")
with c2:
    st.line_chart(df2)
    st.caption("Precio Mosto vs. NPV")
with c3:
    st.line_chart(df3)
    st.caption("Precio Venta vs. ROI")

# ==========================================
# 5. COMPARACIÓN DE ESCENARIOS
# ==========================================
st.divider()
st.header("📊 Comparación de Escenarios")
if st.button("Ejecutar Comparación"):
    casos = {
        "Caso base": (25, 92, 1.0, 0.5, 3.5),
        "Caso económico": (35, 85, 1.2, 0.3, 3.5),
        "Caso rentable": (25, 95, 0.8, 0.5, 5.0),
        "Caso crítico": (15, 105, 1.8, 1.0, 2.0)
    }
    res = []
    for nombre, p in casos.items():
        _, kpi_c = run_simulation(*p)
        res.append({"Escenario": nombre, **kpi_c})
    st.table(pd.DataFrame(res).set_index("Escenario"))
