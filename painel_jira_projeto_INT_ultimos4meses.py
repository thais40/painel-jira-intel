
import streamlit as st
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth

# --- Autenticação via Streamlit Secrets ---
JIRA_URL = st.secrets["JIRA_URL"]
EMAIL = st.secrets["EMAIL"]
TOKEN = st.secrets["TOKEN"]

# --- JQL para os últimos 4 meses ---
JQL = 'project = "INT" AND created >= "2025-02-17" ORDER BY created ASC'

# SLA alvo em horas úteis
SLA_ALVO_HORAS = 40
SLA_ALVO_DIAS = SLA_ALVO_HORAS / 8

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
            "fields": "summary,created,resolutiondate,status,customfield_13686,customfield_13610,customfield_13719,customfield_13659"
        }
        response = requests.get(f"{JIRA_URL}/rest/api/3/search", headers=headers, auth=auth, params=params)
        data = response.json()
        issues = data.get("issues", [])
        if not issues:
            break

        for issue in issues:
            f = issue["fields"]
            status_nome = f.get("status", {}).get("name", "").lower()
            encaminhado_produto = any(s in status_nome for s in ["priorizar com produto", "priorizado com produto"])
            todas_issues.append({
                "key": issue["key"],
                "summary": f["summary"],
                "created": f["created"],
                "resolved": f["resolutiondate"],
                "sla_millis": f.get("customfield_13686", {}).get("ongoingCycle", {}).get("elapsedTime", {}).get("millis"),
                "assunto": [item["value"] for item in f.get("customfield_13610") or []],
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
    df["dentro_sla"] = df["sla_dias"] <= (SLA_ALVO_DIAS)
    df["mes"] = df["created"].dt.to_period("M").astype(str)
    df["mes_resolucao"] = df["resolved"].dt.to_period("M").astype(str)
    return df

# --- UI ---
st.set_page_config(layout="wide")
st.title("📊 Painel de Indicadores - Projeto INT (últimos 4 meses)")

df = buscar_issues()

if df.empty:
    st.warning("Nenhum dado retornado pela API.")
else:
    df = processar(df)

    total_criados = len(df)
    total_resolvidos = df["resolved"].notna().sum()
    total_enc_produto = df["encaminhado_produto"].sum()
    total_enc_n3 = df["encaminhado_n3"].sum()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("📥 Tickets criados", total_criados)
    kpi2.metric("✅ Tickets resolvidos", total_resolvidos)
    kpi3.metric("📦 Encaminhados produto", total_enc_produto)
    kpi4.metric("🚨 Escalados N3", total_enc_n3)

    st.markdown("### 📈 Criados vs Resolvidos por mês")
    criados = df.groupby("mes").size().reset_index(name="Criados")
    resolvidos = df.dropna(subset=["resolved"]).groupby("mes_resolucao").size().reset_index(name="Resolvidos")
    grafico = pd.merge(criados, resolvidos, how="outer", left_on="mes", right_on="mes_resolucao").fillna(0)
    grafico["mes"] = grafico["mes"].fillna(grafico["mes_resolucao"])
    st.bar_chart(grafico.set_index("mes")[["Criados", "Resolvidos"]])

    st.markdown("### ⏱️ SLA por mês com meta (96%)")
    sla_group = df.groupby("mes")[["dentro_sla"]].agg(["sum", "count"]).reset_index()
    sla_group.columns = ["mes", "dentro", "total"]
    sla_group["% dentro"] = (sla_group["dentro"] / sla_group["total"]) * 100
    st.bar_chart(sla_group.set_index("mes")["% dentro"])

    st.markdown("### 🏷️ Assuntos relacionados")
    st.bar_chart(df.explode("assunto")["assunto"].value_counts())

    st.markdown("### 🏢 Áreas solicitantes")
    st.bar_chart(df["area"].value_counts())
