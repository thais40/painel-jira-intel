
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from requests.auth import HTTPBasicAuth
from datetime import datetime

# --- Configurações iniciais ---
JIRA_URL = st.secrets["JIRA_URL"]
EMAIL = st.secrets["EMAIL"]
TOKEN = st.secrets["TOKEN"]
SLA_ALVO_HORAS = 40
SLA_ALVO_DIAS = SLA_ALVO_HORAS / 8
SLA_META_PERCENTUAL = 96
CUTOFF_DATE = "2024-06-01"

JQL = f'project = "INT" AND created >= "{CUTOFF_DATE}" ORDER BY created ASC'

def extrair_sla_millis(sla_field):
    try:
        if "completedCycles" in sla_field and sla_field["completedCycles"]:
            return sla_field["completedCycles"][0]["elapsedTime"]["millis"]
        elif "ongoingCycle" in sla_field and "elapsedTime" in sla_field["ongoingCycle"]:
            return sla_field["ongoingCycle"]["elapsedTime"]["millis"]
    except:
        return None
    return None

def buscar_issues():
    headers = {"Accept": "application/json"}
    auth = HTTPBasicAuth(EMAIL, TOKEN)
    start_at = 0
    todas_issues = []

    while True:
        params = {
            "jql": JQL,
            "startAt": start_at,
            "maxResults": 100,
            "fields": "summary,created,resolutiondate,status,customfield_13686,customfield_13719,customfield_13659"
        }
        response = requests.get(f"{JIRA_URL}/rest/api/3/search", headers=headers, auth=auth, params=params)
        data = response.json()
        issues = data.get("issues", [])
        if not issues:
            break

        for issue in issues:
            f = issue["fields"]
            sla_millis = extrair_sla_millis(f.get("customfield_13686", {}))
            status_nome = f.get("status", {}).get("name", "").lower()
            encaminhado_produto = any(s in status_nome for s in ["priorizar com produto", "priorizado com produto"])
            todas_issues.append({
                "key": issue["key"],
                "summary": f["summary"],
                "created": f["created"],
                "resolved": f["resolutiondate"],
                "sla_millis": sla_millis,
                "area": f.get("customfield_13719", {}).get("value") or "Não especificado",
                "encaminhado_produto": encaminhado_produto,
                "encaminhado_n3": f.get("customfield_13659", {}).get("value") == "Sim"
            })

        start_at += 100

    return pd.DataFrame(todas_issues)

def processar(df):
    df["created"] = pd.to_datetime(df["created"])
    df["resolved"] = pd.to_datetime(df["resolved"])
    df["sla_dias"] = df["sla_millis"] / (1000 * 60 * 60 * 24)
    df["dentro_sla"] = df["sla_dias"] <= SLA_ALVO_DIAS
    df["mes"] = df["created"].dt.strftime("%b/%Y")
    df["mes_resolucao"] = df["resolved"].dt.strftime("%b/%Y")
    return df

# --- UI ---
st.set_page_config(layout="wide")
st.title("📊 Painel de Indicadores - Projeto INT (com meta de SLA)")

df = buscar_issues()
if df.empty:
    st.warning("Nenhum dado retornado pela API.")
else:
    df = processar(df)

    meses_disponiveis = sorted(df["mes"].dropna().unique())
    meses_selecionados = st.multiselect("📆 Filtrar por mês de criação", meses_disponiveis, default=meses_disponiveis)
    df = df[df["mes"].isin(meses_selecionados)]

    total_criados = len(df)
    total_resolvidos = df["resolved"].notna().sum()
    total_enc_produto = df["encaminhado_produto"].sum()
    total_enc_n3 = df["encaminhado_n3"].sum()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("📥 Tickets criados", total_criados)
    kpi2.metric("✅ Tickets resolvidos", total_resolvidos)
    kpi3.metric("📦 Encaminhados produto", total_enc_produto)
    kpi4.metric("🚨 Escalados N3", total_enc_n3)

    st.markdown("### 📊 Criados vs Resolvidos por mês")
    criados = df.groupby("mes").size().reset_index(name="Criados")
    resolvidos = df.dropna(subset=["resolved"]).groupby("mes_resolucao").size().reset_index(name="Resolvidos")
    grafico = pd.merge(criados, resolvidos, how="outer", left_on="mes", right_on="mes_resolucao").fillna(0)
    grafico["mes"] = grafico["mes"].fillna(grafico["mes_resolucao"])

    fig = go.Figure([
        go.Bar(name="Criados", x=grafico["mes"], y=grafico["Criados"]),
        go.Bar(name="Resolvidos", x=grafico["mes"], y=grafico["Resolvidos"])
    ])
    fig.update_layout(barmode="group", xaxis_title="Mês", yaxis_title="Chamados")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### ✅ % de chamados dentro do SLA (meta: 96%)")

    sla_percent = df.groupby("mes")["dentro_sla"].agg(["sum", "count"]).reset_index()
    sla_percent["percentual"] = (sla_percent["sum"] / sla_percent["count"]) * 100
    sla_percent["color"] = sla_percent["percentual"].apply(lambda x: "green" if x >= SLA_META_PERCENTUAL else "red")

    fig_sla = go.Figure([
        go.Bar(
            name="% dentro SLA",
            x=sla_percent["mes"],
            y=sla_percent["percentual"],
            marker_color=sla_percent["color"]
        ),
        go.Scatter(
            name="Meta 96%",
            x=sla_percent["mes"],
            y=[SLA_META_PERCENTUAL] * len(sla_percent),
            mode="lines",
            line=dict(dash="dash", color="black")
        )
    ])
    fig_sla.update_layout(yaxis_title="% dentro SLA", xaxis_title="Mês")
    st.plotly_chart(fig_sla, use_container_width=True)

    st.markdown("### 🏢 Áreas solicitantes")
    st.bar_chart(df["area"].value_counts())
