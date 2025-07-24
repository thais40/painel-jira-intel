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
import plotly.graph_objects as go

# Calcular percentual e exibir gráfico com meta
sla_mes['fora'] = sla_mes['count'] - sla_mes['sum']
sla_mes['percentual'] = (sla_mes['sum'] / sla_mes['count']) * 100
meta_sla = 96  # meta ajustável por projeto
fig = go.Figure()
fig.add_trace(go.Bar(x=sla_mes['mes_str'], y=sla_mes['sum'], name='Dentro SLA', marker_color='green'))
fig.add_trace(go.Bar(x=sla_mes['mes_str'], y=sla_mes['fora'], name='Fora SLA', marker_color='red'))
fig.add_shape(type='line', x0=-0.5, x1=len(sla_mes['mes_str']) - 0.5, y0=meta_sla, y1=meta_sla,
              line=dict(color='orange', dash='dash'), xref='x', yref='y')
fig.update_layout(barmode='stack', title=f'SLA por Mês — Meta: {meta_sla}%',
                  xaxis_title='Mês', yaxis_title='Qtd. Chamados', legend_title='Status')
st.plotly_chart(fig, use_container_width=True)
