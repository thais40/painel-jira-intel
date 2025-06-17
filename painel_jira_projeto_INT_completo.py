
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from requests.auth import HTTPBasicAuth
from io import BytesIO

# --- Autenticação via Streamlit Secrets ---
JIRA_URL = st.secrets["JIRA_URL"]
EMAIL = st.secrets["EMAIL"]
TOKEN = st.secrets["TOKEN"]

# --- JQL para os últimos 4 meses ---
from datetime import datetime, timedelta
cutoff_date = (datetime.today() - timedelta(days=120)).strftime("%Y-%m-%d")
JQL = f'project = "INT" AND created >= "{cutoff_date}" ORDER BY created ASC'

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
            "fields": "summary,created,resolutiondate,status,customfield_13686,customfield_13747,customfield_13719,customfield_13659"
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
            assunto_raw = f.get("customfield_13747") or []
            assuntos = [item["value"] for item in assunto_raw] if isinstance(assunto_raw, list) else []
            todas_issues.append({
                "key": issue["key"],
                "summary": f["summary"],
                "created": f["created"],
                "resolved": f["resolutiondate"],
                "sla_millis": f.get("customfield_13686", {}).get("ongoingCycle", {}).get("elapsedTime", {}).get("millis"),
                "assunto": assuntos,
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
    df["mes"] = df["created"].dt.to_period("M").astype(str)
    df["mes_resolucao"] = df["resolved"].dt.to_period("M").astype(str)
    return df

# --- UI ---
st.set_page_config(layout="wide")
st.title("📊 Painel de Indicadores - Projeto INT")

df = buscar_issues()

if df.empty:
    st.warning("Nenhum dado retornado pela API.")
else:
    df = processar(df)

    # Filtros interativos
    colf1, colf2, colf3 = st.columns(3)
    with colf1:
        meses_disponiveis = sorted(df["mes"].dropna().unique())
        meses_selecionados = st.multiselect("📆 Filtrar por mês de criação", meses_disponiveis, default=meses_disponiveis)
    with colf2:
        areas_disponiveis = sorted(df["area"].dropna().unique())
        areas_selecionadas = st.multiselect("🏢 Filtrar por Área", areas_disponiveis, default=areas_disponiveis)
    with colf3:
        assuntos_explodidos = df.explode("assunto")
        assuntos_disponiveis = sorted(assuntos_explodidos["assunto"].dropna().unique())
        assuntos_selecionados = st.multiselect("🏷️ Filtrar por Assunto", assuntos_disponiveis, default=assuntos_disponiveis)

    df = df[df["mes"].isin(meses_selecionados)]
    df = df[df["area"].isin(areas_selecionadas)]
    df = df[df["assunto"].apply(lambda x: any(i in assuntos_selecionados for i in x))]

    # KPIs
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

    fig = go.Figure(data=[
        go.Bar(name="Criados", x=grafico["mes"], y=grafico["Criados"]),
        go.Bar(name="Resolvidos", x=grafico["mes"], y=grafico["Resolvidos"])
    ])
    fig.update_layout(barmode='group')
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### ✅ Chamados dentro do SLA (40h úteis) por mês")
    sla_group = df.groupby("mes")[["dentro_sla"]].sum().reset_index()
    sla_group.rename(columns={"dentro_sla": "Chamados dentro SLA"}, inplace=True)
    st.bar_chart(sla_group.set_index("mes"))

    st.markdown("### 🏷️ Assuntos relacionados (selecionados)")
    assuntos_foco = [
        "Nova integração - Outros",
        "Nova integração - Cliente novo",
        "Dúvida sobre integração",
        "Nova integração - Conta filho",
        "Nova integração - Alteração de plataforma"
    ]
    assuntos_filtrados = assuntos_explodidos[assuntos_explodidos["assunto"].isin(assuntos_foco)]
    st.bar_chart(assuntos_filtrados["assunto"].value_counts())

    st.markdown("### 🏢 Áreas solicitantes")
    st.bar_chart(df["area"].value_counts())

    # Exportação
    st.markdown("### 📥 Exportar dados filtrados")
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Tickets')
    st.download_button(
        label="📁 Baixar Excel",
        data=output.getvalue(),
        file_name="tickets_INT_filtrados.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
