
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
                area_data = f.get("customfield_13719")
                area_valor = area_data["value"] if isinstance(area_data, dict) and "value" in area_data else "Não especificado"
                escalado_n3 = (f.get("customfield_13659") or {}).get("value") == "Sim"
                all_issues.append({
                    "key": issue["key"],
                    "projeto": projeto,
                    "created": f["created"],
                    "resolved": f["resolutiondate"],
                    "sla_millis": sla_millis,
                    "area": area_valor,
                    "encaminhado_produto": encaminhado_produto,
                    "encaminhado_n3": escalado_n3
                })
            start_at += 100
    return pd.DataFrame(all_issues)
