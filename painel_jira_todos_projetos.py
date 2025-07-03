
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from requests.auth import HTTPBasicAuth
from datetime import datetime

# Configuração da API do Jira
JIRA_URL = st.secrets["JIRA_URL"]
EMAIL = st.secrets["EMAIL"]
TOKEN = st.secrets["TOKEN"]
SLA_ALVO_HORAS = 40
SLA_ALVO_DIAS = SLA_ALVO_HORAS / 8
SLA_META = 96
PROJETOS = ["TDS", "INT", "TINE", "INTEL"]
CUTOFF_DATE = "2024-12-01"

def extrair_sla_millis(sla_field):
    try:
        if sla_field.get("completedCycles"):
            return sla_field["completedCycles"][0]["elapsedTime"]["millis"]
        elif sla_field.get("ongoingCycle", {}).get("elapsedTime"):
            return sla_field["ongoingCycle"]["elapsedTime"]["millis"]
    except:
        return None
    return None

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
                "fields": "summary,created,resolutiondate,status,customfield_13686,customfield_13719,customfield_13659"
            }
            res = requests.get(f"{JIRA_URL}/rest/api/3/search", headers=headers, auth=auth, params=params)
            data = res.json()
            issues = data.get("issues", [])
            if not issues:
                break

            for issue in issues:
                f = issue["fields"]
                sla_millis = extrair_sla_millis(f.get("customfield_13686", {}))
                status = f.get("status", {}).get("name", "").lower()
                encaminhado_produto = "priorizar com produto" in status or "priorizado com produto" in status
                escalado_n3 = (f.get("customfield_13659") or {}).get("value") == "Sim"
                all_issues.append({
                    "key": issue["key"],
                    "projeto": projeto,
                    "created": f["created"],
                    "resolved": f["resolutiondate"],
                    "sla_millis": sla_millis,
                    "area": f.get("customfield_13719", {}).get("value") or "Não especificado",
                    "encaminhado_produto": encaminhado_produto,
                    "encaminhado_n3": escalado_n3
                })
            start_at += 100
    return pd.DataFrame(all_issues)

def processar(df):
    df["created"] = pd.to_datetime(df["created"])
    df["resolved"] = pd.to_datetime(df["resolved"])
    df["sla_dias"] = df["sla_millis"] / (1000 * 60 * 60 * 24)
    df["dentro_sla"] = df["sla_dias"] <= SLA_ALVO_DIAS
    df["mes"] = df["created"].dt.to_period("M").dt.to_timestamp()
    df["mes_str"] = df["mes"].dt.strftime("%b/%Y")
    return df

# Streamlit layout
st.set_page_config(layout="wide")
st.title("📊 Painel de Indicadores - Projeto INT")

df = buscar_issues()
if df.empty:
    st.warning("Nenhum dado encontrado.")
else:
    df = processar(df)

    projetos = df["projeto"].unique().tolist()
    projeto_filtro = st.multiselect("Filtrar por projeto", projetos, default=projetos)
    df = df[df["projeto"].isin(projeto_filtro)]

    meses_disponiveis = sorted(df["mes"].dropna().unique())
    meses_selecionados = st.multiselect("Filtrar por mês", meses_disponiveis, default=meses_disponiveis)
    df = df[df["mes"].isin(meses_selecionados)]

    st.metric("Total de Tickets", len(df))
    st.metric("Tickets dentro do SLA", df["dentro_sla"].sum())

    criados = df.groupby("mes_str").size().reset_index(name="Criados")
    resolvidos = df.dropna(subset=["resolved"]).groupby(df["resolved"].dt.to_period("M").dt.to_timestamp().dt.strftime("%b/%Y")).size().reset_index(name="Resolvidos")
    grafico = pd.merge(criados, resolvidos, on="mes_str", how="outer").fillna(0)

    fig = go.Figure([
        go.Bar(name="Criados", x=grafico["mes_str"], y=grafico["Criados"]),
        go.Bar(name="Resolvidos", x=grafico["mes_str"], y=grafico["Resolvidos"])
    ])
    fig.update_layout(barmode="group", title="Chamados Criados vs Resolvidos")
    st.plotly_chart(fig, use_container_width=True)

    sla_mes = df.groupby("mes_str")["dentro_sla"].agg(["sum", "count"]).reset_index()
    sla_mes["percentual"] = (sla_mes["sum"] / sla_mes["count"]) * 100
    sla_mes["cor"] = sla_mes["percentual"].apply(lambda x: "green" if x >= SLA_META else "red")

    fig_sla = go.Figure([
        go.Bar(x=sla_mes["mes_str"], y=sla_mes["percentual"], marker_color=sla_mes["cor"], name="% SLA"),
        go.Scatter(x=sla_mes["mes_str"], y=[SLA_META]*len(sla_mes), name="Meta SLA 96%", mode="lines", line=dict(color="black", dash="dash"))
    ])
    fig_sla.update_layout(title="% de Chamados dentro do SLA", yaxis_title="%", xaxis_title="Mês")
    st.plotly_chart(fig_sla, use_container_width=True)

    st.markdown("### Área Solicitante por Mês")
    area_mes = df.groupby(["mes_str", "area"]).size().reset_index(name="Chamados")
    tabela = area_mes.pivot(index="mes_str", columns="area", values="Chamados").fillna(0).astype(int)
    st.dataframe(tabela)
