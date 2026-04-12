import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import google.generativeai as genai
import os

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILO
# ==========================================
st.set_page_config(page_title="BioSTEAM Process Dash", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. LÓGICA DE SIMULACIÓN (ENCAPSULADA)
# ==========================================
def run_simulation(flow_water, flow_eth, temp_feed, p_flash):
    # Limpieza de flowsheet para evitar IDs duplicados en Streamlit
    bst.main_flowsheet.clear()
    
    chemicals = tmo.Chemicals(["Water", "Ethanol"])
    bst.settings.set_thermo(chemicals)

    # Corrientes
    mosto = bst.Stream("MOSTO", Water=flow_water, Ethanol=flow_eth, 
                       units="kg/hr", T=temp_feed + 273.15)
    vinazas_retorno = bst.Stream("Vinazas_Retorno", Water=200, T=95+273.15)

    # Equipos
    P100 = bst.Pump("P100", ins=mosto, P=4*101325)
    W210 = bst.HXprocess("W210", ins=(P100-0, vinazas_retorno), 
                         outs=("Mosto_Pre", "Drenaje"), phase0="l", phase1="l")
    W210.outs[0].T = 85 + 273.15
    
    W220 = bst.HXutility("W220", ins=W210-0, outs="Mezcla", T=92+273.15)
    V100 = bst.IsenthalpicValve("V100", ins=W220-0, outs="Mezcla_Bif", P=101325)
    V1 = bst.Flash("V1", ins=V100-0, outs=("Vapor", "Vinazas"), P=p_flash*101325, Q=0)
    W310 = bst.HXutility("W310", ins=V1-0, outs="Producto", T=25+273.15)
    P200 = bst.Pump("P200", ins=V1-1, outs=vinazas_retorno, P=3*101325)

    sys = bst.System("eth_sys", path=(P100, W210, W220, V100, V1, W310, P200))
    sys.simulate()
    return sys, W310.outs[0]

# ==========================================
# 3. INTERFAZ DE USUARIO (SIDEBAR)
# ==========================================
st.sidebar.header("⚙️ Parámetros del Proceso")
f_water = st.sidebar.slider("Flujo Agua (kg/h)", 500, 1500, 900)
f_eth = st.sidebar.slider("Flujo Etanol (kg/h)", 50, 500, 100)
t_feed = st.sidebar.slider("Temp. Alimento (°C)", 15, 40, 25)
p_flash = st.sidebar.number_input("Presión Flash (atm)", 0.5, 2.0, 1.0)

# ==========================================
# 4. EJECUCIÓN Y LAYOUT PRINCIPAL
# ==========================================
st.title("🏭 Simulador Interactivo de Destilación Flash")

try:
    sistema, producto = run_simulation(f_water, f_eth, t_feed, p_flash)
    
    # --- FILA 1: KPIs ---
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    
    pureza = (producto.imass['Ethanol'] / producto.F_mass) * 100
    flujo_total = producto.F_mass
    energia_total = sum(u.duty for u in sistema.units if hasattr(u, 'duty')) / 3600 # kW

    col_kpi1.metric("Pureza Etanol", f"{pureza:.1f} %", delta=f"{pureza-10:.1f}% vs Ref")
    col_kpi2.metric("Producción", f"{flujo_total:.1f} kg/h")
    col_kpi3.metric("Carga Térmica Total", f"{abs(energia_total):.2f} kW")
    col_kpi4.metric("Temp. Salida", f"{producto.T - 273.15:.1f} °C")

    st.divider()

    # --- FILA 2: TABLAS (Lado a Lado) ---
    col_tab1, col_tab2 = st.columns(2)

    with col_tab1:
        st.subheader("📊 Balance de Materia")
        datos_materia = []
        for s in sistema.streams:
            if s.F_mass > 0:
                datos_materia.append({
                    "ID": s.ID,
                    "Flujo (kg/h)": round(s.F_mass, 2),
                    "% Etanol": f"{(s.imass['Ethanol']/s.F_mass)*100:.1f}%" if s.F_mass > 0 else "0%"
                })
        st.dataframe(pd.DataFrame(datos_materia), use_container_width=True)

    with col_tab2:
        st.subheader("⚡ Balance de Energía")
        datos_en = []
        for u in sistema.units:
            # Manejo de energía seguro para todas las unidades
            calor = sum(h.duty for h in u.heat_utilities) / 3600 if u.heat_utilities else 0
            if abs(calor) > 0.001:
                datos_en.append({"Equipo": u.ID, "Carga (kW)": round(calor, 2)})
        st.dataframe(pd.DataFrame(datos_en), use_container_width=True)

    # --- FILA 3: DIAGRAMA ---
    st.divider()
    st.subheader("🎨 Diagrama de Flujo del Proceso (PFD)")
    sistema.diagram(file="pfd", format="png")
    st.image("pfd.png")

except Exception as e:
    st.error(f"Error en la simulación: {e}")

# ==========================================
# 5. INTEGRACIÓN GEMINI AI
# ==========================================
st.divider()
api_key = st.secrets.get("GEMINI_API_KEY","")
ask_ai = st.checkbox("Habilitar Tutor IA")

if st.sidebar.button("🤖 Analizar con IA"):
    if not api_key:
        st.sidebar.warning("Por favor, ingresa tu API Key.")
    else:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-pro')
            prompt = f"Analiza estos resultados: Pureza {pureza:.1f}%, Energía {energia_total:.2f}kW. ¿Es eficiente?"
            response = model.generate_content(prompt)
            st.write("### 🧠 Sugerencia del Tutor IA")
            st.info(response.text)
        except Exception as e:
            st.error(f"Error con Gemini: {e}")
