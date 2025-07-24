
import streamlit as st
import plotly.express as px
import requests
import pandas as pd
import plotly.graph_objects as go
from requests.auth import HTTPBasicAuth
from datetime import datetime

JIRA_URL = st.secrets.get("JIRA_URL", "")
EMAIL = st.secrets.get("EMAIL", "")
TOKEN = st.secrets.get("TOKEN", "")
PROJETOS = ["TDS", "INT", "TINE", "INTEL"]
CUTOFF_DATE = "2024-01-01"
SLA_ALVO_DIAS = 40 / 8
SLA_METAS = {"TDS": 98, "INT": 96, "TINE": 96, "INTEL": 96}

# ========== CONFIGURAÇÃO STREAMLIT ==========
st.set_page_config(layout="wide")
st.title("📊 Painel de Indicadores")


# ========== FUNÇÕES AUXILIARES ==========
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



# ========== COLETA DE DADOS ==========
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
                "fields": "summary,created,resolutiondate,status,customfield_13686,customfield_13719,customfield_13659,customfield_13747"
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
                sla_millis = extrair_sla_millis(f.get("customfield_13686", {}))
                status = f.get("status", {})
                status = f.get("status", {}).get("name", "").lower()
                encaminhado_produto = "priorizar com produto" in status or "priorizado com produto" in status
                area_data = f.get("customfield_13719")
                area_valor = area_data.get("value") if isinstance(area_data, dict) else "Não especificado"
                assunto_data = f.get("customfield_13747") or []
                assuntos = [item["value"] for item in assunto_data] if isinstance(assunto_data, list) else []
                escalado_n3 = (f.get("customfield_13659") or {})
                custom_n3 = f.get("customfield_13659")
                escalado_n3 = isinstance(custom_n3, dict) and custom_n3.get("value") == "Sim"
                all_issues.append({
                    "key": issue["key"],
                    "projeto": projeto,
                    "created": f["created"],
                    "resolved": f["resolutiondate"],
                    "sla_millis": sla_millis,
                    "area": area_valor,
                    "assunto": assuntos,
                    "encaminhado_produto": encaminhado_produto,
                    "encaminhado_n3": escalado_n3,
                })
            start_at += 100
    return pd.DataFrame(all_issues)


# ========== PRÉ-PROCESSAMENTO ==========
def processar(df):
    df["created"] = pd.to_datetime(df["created"])
    df["resolved"] = pd.to_datetime(df["resolved"])
    df["sla_dias"] = df["sla_millis"] / (1000 * 60 * 60 * 24)
    df["dentro_sla"] = df["sla_dias"] <= SLA_ALVO_DIAS
    df["mes"] = df["created"].dt.to_period("M").dt.to_timestamp()
    df["mes_str"] = df["mes"].dt.strftime("%b/%Y")
    return df


# ========== EXECUÇÃO ==========
df = buscar_issues()
if df.empty:
    st.warning("Nenhum dado retornado da API do Jira.")
else:
    df = processar(df)
    abas = st.tabs(PROJETOS)

    
# ========== INTERFACE POR PROJETO ==========
    for i, projeto in enumerate(PROJETOS):
        with abas[i]:
            st.subheader(f"📁 Projeto: {projeto}")
            dfx = df[df["projeto"] == projeto]
    st.download_button(
        label="📥 Exportar dados do projeto",
        data=dfx.to_csv(index=False).encode("utf-8"),
        file_name=f"{projeto}_dados.csv",
        mime="text/csv"
    )
    dfx["mes_resolvido"] = dfx["resolved"].dt.to_period("M").dt.to_timestamp().dt.strftime("%b/%Y")

    dfx['mes_resolvido'] = dfx['resolved'].dt.to_period('M').dt.to_timestamp().dt.strftime('%b/%Y')
    resolvidos = dfx.dropna(subset=['resolved']).groupby('mes_resolvido').size().reset_index(name='Resolvidos')
    criados = dfx.groupby('mes_str').size().reset_index(name='Criados')
    grafico = pd.merge(criados, resolvidos.rename(columns={"mes_resolvido": "mes_str"}), on='mes_str', how='outer').fillna(0).sort_values('mes_str')
    fig = px.bar(
        grafico,
        x='mes_str',
        y=['Criados', 'Resolvidos'],
        barmode='group',
        title='Criados vs Resolvidos por mês'
    )
    st.plotly_chart(fig, use_container_width=True, key=f'grafico_{projeto}')
    fig_sla = go.Figure()
    fig_sla.add_trace(go.Bar(
        x=sla_mes['mes_str'],
        y=sla_mes['sum'],
        name='SLA Dentro',
        marker_color='green'
    ))
    fig_sla.add_trace(go.Bar(
        x=sla_mes['mes_str'],
        y=sla_mes['fora'],
        name='SLA Fora',
        marker_color='red'
    ))
    fig_sla.update_layout(
        barmode='stack',
        title='SLA Dentro | Fora',
        xaxis_title='Mês',
        yaxis_title='Chamados'
    )
    st.plotly_chart(fig_sla, use_container_width=True, key=f'sla_{projeto}')
with st.container():
    tabela = area_mes.pivot(index="mes_str", columns="area", values="Chamados").fillna(0).astype(int)
    st.markdown("#### Área Solicitante por Mês")
    st.dataframe(tabela)

    pass  # linha segura para encerrar bloco anterior
    st.download_button(
        file_name=f"{projeto}_dados.csv",
    )
