import streamlit as st
import pandas as pd

# Simulação de dataframe dfx já tratado
dfx = pd.DataFrame({
    'mes_str': ['Jan/2024', 'Feb/2024', 'Mar/2024', 'Jan/2024', 'Feb/2024'],
    'dentro_sla': [1, 1, 0, 1, 0]
})

sla_mes = dfx.groupby('mes_str')['dentro_sla'].agg(['sum', 'count']).reset_index()
sla_mes['fora'] = sla_mes['count'] - sla_mes['sum']
sla_mes['mes_str'] = pd.Categorical(
    sla_mes['mes_str'],
    categories=sorted(sla_mes['mes_str'].unique(), key=lambda x: pd.to_datetime(x, format='%b/%Y'))
)
sla_mes = sla_mes.sort_values('mes_str')

st.write('Resultado do agrupamento SLA por mês:')
st.dataframe(sla_mes)
