
import streamlit as st
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth

# --- Autenticação via Streamlit Secrets ---
JIRA_URL = st.secrets["JIRA_URL"]
EMAIL = st.secrets["EMAIL"]
TOKEN = st.secrets["TOKEN"]

# --- JQL com aspas em torno dos nomes de projeto reservados ---
JQL = 'project in ("INT", "INTEL") ORDER BY created DESC'

def buscar_issues():
    headers = {"Accept": "application/json"}
    auth = HTTPBasicAuth(EMAIL, TOKEN)
    start_at = 0
    todas_issues = []

    while True:
        params = {
            "jql": JQL,
            "startAt": start_at,
            "maxResults": 50,
            "fields": "summary,created,resolutiondate,labels,components"
        }
        response = requests.get(f"{JIRA_URL}/rest/api/3/search", headers=headers, auth=auth, params=params)

        # Exibe conteúdo bruto da resposta para diagnóstico
        st.subheader("🧪 Retorno bruto da API (debug)")
        st.code(response.text, language="json")

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

        start_at += 50

    return pd.DataFrame(todas_issues)

def processar(df):
    df["created"] = pd.to_datetime(df["created"])
    df["resolved"] = pd.to_datetime(df["resolved"])
    df["sla_dias"] = (df["resolved"] - df["created"]).dt.days
    df["mes_criacao"] = df["created"].dt.to_period("M").astype(str)
    df["mes_resolucao"] = df["resolved"].dt.to_period("M").astype(str)
    return df

# --- UI ---
st.title("📊 Painel de Indicadores - INT & INTEL (Modo Diagnóstico)")

df = buscar_issues()

if df.empty:
    st.warning("Nenhum dado retornado pela API.")
else:
    df = processar(df)

    st.subheader("🔍 Visualização de dados extraídos")
    st.dataframe(df[["key", "summary", "created", "resolved", "labels", "components", "sla_dias"]])
