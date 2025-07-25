import streamlit as st
import pandas as pd
import plotly.graph_objects as go

def extrair_sla_millis(sla_field):
    try:
        if sla_field.get("completedCycles"):
            cycles = sla_field["completedCycles"]
            if isinstance(cycles, list) and cycles:
                return cycles[0].get("elapsedTime", {}).get("millis")
        if sla_field.get("ongoingCycle"):
            return sla_field["ongoingCycle"].get("elapsedTime", {}).get("millis")
    except Exception:
        return None
    return None

# Streamlit layout mínimo
st.set_page_config(layout='wide')
st.title('Painel de Indicadores - Mínimo')

abas = st.tabs(["Projeto A"])
with abas[0]:
    st.subheader("Exemplo: Tickets por mês")
    df = pd.DataFrame({
        'mes': ['Jan/2024', 'Feb/2024', 'Mar/2024'],
        'Criados': [120, 95, 110],
        'Resolvidos': [100, 90, 105]
    })
    fig = go.Figure()
    fig.add_bar(x=df['mes'], y=df['Criados'], name='Criados', marker_color='green')
    fig.add_bar(x=df['mes'], y=df['Resolvidos'], name='Resolvidos', marker_color='blue')
    fig.update_layout(barmode='group', title='Criados vs Resolvidos')
    st.plotly_chart(fig, use_container_width=True)
