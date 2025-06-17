
import streamlit as st
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth

# --- Autenticação via Streamlit Secrets ---
JIRA_URL = st.secrets["JIRA_URL"]
EMAIL = st.secrets["EMAIL"]
TOKEN = st.secrets["TOKEN"]

# --- JQL corrigida ---
JQL = 'project in ("INT", "INTEL") AND created >= startOfYear() ORDER BY created ASC'

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
            "fields": "summary,created,resolutiondate,labels,components"
        }
        response = requests.get(f"{JIRA_URL}/rest/api/3/search", headers=headers, auth=auth, params=params)
        data = response.json()

        issues = data.get("issues", [])
        if not issues:
            break

        for issue in issues:
            f = issue["fields"]
            todas_issues.append({
                "key": issue["key"],
                "summary": f["summary"],
                "created": f["created"],
                "resolved": f["resolutiondate"],
                "labels": f["labels"],
                "components": [c["name"] for c in f["components"]]
            })

        start_at += 100

    return pd.DataFrame(todas_issues)

def processar(df):
    df["created"] = pd.to_datetime(df["created"])
    df["resolved"] = pd.to_datetime(df["resolved"])
    df["sla_dias"] = (df["resolved"] - df["created"]).dt.days
    df["mes_criacao"] = df["created"].dt.to_period("M").astype(str)
    df["mes_resolucao"] = df["resolved"].dt.to_period("M").astype(str)
    return df

# --- UI ---
st.title("📊 Painel de Indicadores - INT & INTEL")

df = buscar_issues()

if df.empty:
    st.warning("Nenhum dado retornado pela API.")
else:
    df = processar(df)

    criados = df.groupby("mes_criacao").size().reset_index(name="Criados")
    resolvidos = df.dropna(subset=["resolved"]).groupby("mes_resolucao").size().reset_index(name="Resolvidos")
    sla_mensal = df.dropna(subset=["resolved"]).groupby("mes_resolucao")["sla_dias"].mean().reset_index(name="SLA médio")

    col1, col2 = st.columns(2)
    col1.subheader("🗓️ Criados por mês")
    col1.bar_chart(criados.set_index("mes_criacao"))

    col2.subheader("✅ Resolvidos por mês")
    col2.bar_chart(resolvidos.set_index("mes_resolucao"))

    st.subheader("⏱️ SLA médio por mês (dias)")
    st.line_chart(sla_mensal.set_index("mes_resolucao"))

    st.subheader("🏷️ Assuntos (labels)")
    st.bar_chart(df.explode("labels")["labels"].value_counts())

    st.subheader("🏢 Áreas (componentes)")
    st.bar_chart(df.explode("components")["components"].value_counts())

    st.subheader("🚨 Chamados fora do SLA (> 7 dias)")
    fora_sla = df[df["sla_dias"] > 7]
    st.error(f"{len(fora_sla)} chamados fora do SLA")
    st.dataframe(fora_sla[["key", "summary", "created", "resolved", "sla_dias"]])
