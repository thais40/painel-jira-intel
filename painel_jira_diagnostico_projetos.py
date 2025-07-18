
import streamlit as st
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
from datetime import datetime

# Configurações iniciais
JIRA_URL = st.secrets.get("JIRA_URL", "")
EMAIL = st.secrets.get("EMAIL", "")
TOKEN = st.secrets.get("TOKEN", "")
PROJETOS = ["TDS", "INT", "TINE", "INTEL"]
CUTOFF_DATE = "2024-01-01"

st.set_page_config(layout="wide")
st.title("🧪 Diagnóstico de Carregamento - API Jira")

def extrair_sla_millis(sla_field):
    try:
        if sla_field.get("completedCycles"):
            return sla_field["completedCycles"][0]["elapsedTime"]["millis"]
        elif sla_field.get("ongoingCycle", {}).get("elapsedTime"):
            return sla_field["ongoingCycle"]["elapsedTime"]["millis"]
    except:
        return None
    return None

@st.cache_data(show_spinner=True)
def diagnosticar_projetos():
    headers = {"Accept": "application/json"}
    auth = HTTPBasicAuth(EMAIL, TOKEN)
    resultados = []

    for projeto in PROJETOS:
        chamados = []
        total = 0
        erro = None
        start_at = 0

        while True:
            jql = f'project = "{projeto}" AND created >= "{CUTOFF_DATE}" ORDER BY created ASC'
            params = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": 50,
                "fields": "summary,created,resolutiondate,status,customfield_13686"
            }
            res = requests.get(f"{JIRA_URL}/rest/api/3/search", headers=headers, auth=auth, params=params)

            if res.status_code != 200:
                erro = f"Erro {res.status_code} - {res.reason}"
                break

            data = res.json()
            issues = data.get("issues", [])
            total += len(issues)
            chamados.extend(issues)

            if not issues or len(issues) < 50:
                break
            start_at += 50

        resultados.append({
            "projeto": projeto,
            "total_chamados": total,
            "erro": erro,
            "exemplo": chamados[0]["key"] if chamados else "—"
        })

    return resultados

# Executar diagnóstico
resultados = diagnosticar_projetos()

# Exibir resultados
for r in resultados:
    if r["erro"]:
        st.error(f"❌ {r['projeto']}: {r['erro']}")
    elif r["total_chamados"] == 0:
        st.warning(f"⚠️ {r['projeto']}: nenhum chamado encontrado desde {CUTOFF_DATE}")
    else:
        st.success(f"✅ {r['projeto']}: {r['total_chamados']} chamados encontrados. Exemplo: {r['exemplo']}")
