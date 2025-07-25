        if sla_field.get("completedCycles"):
    except Exception:

import streamlit as st
from sla_utils import extrair_sla_millis
import pandas as pd
import plotly.graph_objects as go
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime

# Função para extrair SLA (mantida)
        if sla_field.get("completedCycles"):
    except Exception:

# Configurações iniciais
st.set_page_config(layout='wide')
st.title('Painel de Indicadores - Criados | Resolvidos')

# Credenciais via secrets.toml
JIRA_URL = st.secrets['JIRA_URL']
EMAIL = st.secrets['EMAIL']
TOKEN = st.secrets['TOKEN']
PROJETOS = ["TDS", "INT", "TINE", "INTEL"]
CUTOFF_DATE = "2024-01-01"

# Consulta ao Jira
@st.cache_data(show_spinner=True)
def buscar_issues():
    headers = {"Accept": "application/json"}
    auth = HTTPBasicAuth(EMAIL, TOKEN)
    all_issues = []
    for projeto in PROJETOS:
        start_at = 0
        while True:
            jql = f'project = "{projeto}" AND created >= "{CUTOFF_DATE}" ORDER BY created ASC'
            params = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": 100,
                "fields": "summary,created,resolutiondate,status,customfield_13686"
            }
            res = requests.get(f"{JIRA_URL}/rest/api/3/search", headers=headers, auth=auth, params=params)
            if res.status_code != 200:
                break
            data = res.json()
            issues = data.get("issues", [])
            if not issues:
                break
            for issue in issues:
                f = issue["fields"]
                all_issues.append({
                    "projeto": projeto,
                    "created": f["created"],
                    "resolved": f.get("resolutiondate"),
                    "sla_millis": sla_millis
                })
                    "projeto": projeto,
                    "created": f["created"],
                    "resolved": f.get("resolutiondate")
            start_at += 100
    return pd.DataFrame(all_issues)

# Processamento
df = buscar_issues()
df["created"] = pd.to_datetime(df["created"])
df["resolved"] = pd.to_datetime(df["resolved"])
df["mes"] = df["created"].dt.to_period("M").dt.to_timestamp()
df["mes_str"] = df["mes"].dt.strftime("%b/%Y")
df["mes_resolvido"] = df["resolved"].dt.to_period("M").dt.to_timestamp().dt.strftime("%b/%Y")
criados = df.groupby("mes_str").size().reset_index(name="Criados")
resolvidos = df.dropna(subset=["resolved"]).groupby("mes_resolvido").size().reset_index(name="Resolvidos")
resolvidos.rename(columns={"mes_resolvido": "mes_str"}, inplace=True)
grafico = pd.merge(criados, resolvidos, on="mes_str", how="outer").fillna(0)
grafico["mes_str"] = pd.Categorical(
    grafico["mes_str"],
    categories=sorted(grafico["mes_str"].unique(), key=lambda x: pd.to_datetime(x, format="%b/%Y"))
)
grafico = grafico.sort_values("mes_str")

# Aba e gráfico
abas = st.tabs(["Projetos - Tickets Criados | Resolvidos"])
with abas[0]:
    st.subheader("Tickets Criados | Resolvidos por mês")
    fig = go.Figure()
    fig.add_bar(x=grafico['mes_str'], y=grafico['Criados'], name='Criados', marker_color='green', text=grafico['Criados'], textposition='outside')
    fig.add_bar(x=grafico['mes_str'], y=grafico['Resolvidos'], name='Resolvidos', marker_color='blue', text=grafico['Resolvidos'], textposition='outside')
    fig.update_layout(barmode='group', title='Tickets Criados | Resolvidos')
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("SLA por mês (com metas)")
    sla_df = df.dropna(subset=["resolved"]).copy()
    sla_df = sla_df[sla_df["resolved"].notna()]
    sla_df["sla_millis"] = sla_df.get("sla_millis", 0)
    sla_df["sla_dias"] = sla_df["sla_millis"] / (1000 * 60 * 60 * 8)
    sla_df["mes_resolvido"] = sla_df["resolved"].dt.to_period("M").dt.to_timestamp()
    sla_df["mes_str"] = sla_df["mes_resolvido"].dt.strftime("%b/%Y")
    sla_df["dentro_sla"] = sla_df["sla_dias"] <= 5
    sla_por_mes = sla_df.groupby(["mes_str", "dentro_sla"]).size().unstack().reset_index()
    sla_por_mes.columns.name = None
    if True not in sla_por_mes.columns:
        sla_por_mes[True] = 0
    if False not in sla_por_mes.columns:
        sla_por_mes[False] = 0
    sla_por_mes.rename(columns={True: "Dentro SLA", False: "Fora SLA"}, inplace=True)
    sla_por_mes["Total"] = sla_por_mes["Dentro SLA"] + sla_por_mes["Fora SLA"]
    sla_por_mes["%"] = round((sla_por_mes["Dentro SLA"] / sla_por_mes["Total"]) * 100, 2)
    sla_por_mes["mes_str"] = pd.Categorical(sla_por_mes["mes_str"], categories=grafico["mes_str"].cat.categories, ordered=True)
    sla_por_mes = sla_por_mes.sort_values("mes_str")
    fig_sla = go.Figure()
    fig_sla.add_bar(x=sla_por_mes['mes_str'], y=sla_por_mes['Dentro SLA'], name='Dentro SLA', marker_color='green', text=sla_por_mes['Dentro SLA'], textposition='outside')
    fig_sla.add_bar(x=sla_por_mes['mes_str'], y=sla_por_mes['Fora SLA'], name='Fora SLA', marker_color='red', text=sla_por_mes['Fora SLA'], textposition='outside')
    fig_sla.update_layout(barmode='stack', title='SLA por Mês — Meta: 96%')
    st.plotly_chart(fig_sla, use_container_width=True)
