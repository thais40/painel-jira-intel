
import streamlit as st
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

st.set_page_config(layout="wide")
st.title("📊 Painel de Indicadores")

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
                status = f.get("status", {}).get("name", "").lower()
                encaminhado_produto = "priorizar com produto" in status or "priorizado com produto" in status
                area_data = f.get("customfield_13719")
                area_valor = area_data["value"] if isinstance(area_data, dict) and "value" in area_data else "Não especificado"
                assunto_data = f.get("customfield_13747", [])
                assuntos = [item["value"] for item in assunto_data] if isinstance(assunto_data, list) else []
                escalado_n3 = (f.get("customfield_13659") or {}).get("value") == "Sim"
                all_issues.append({
                    "key": issue["key"],
                    "projeto": projeto,
                    "created": f["created"],
                    "resolved": f["resolutiondate"],
                    "sla_millis": sla_millis,
                    "area": area_valor,
                    "assunto": assuntos,
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

df = buscar_issues()
if df.empty:
    st.warning("Nenhum dado retornado da API do Jira.")
else:
    df = processar(df)
    abas = st.tabs(PROJETOS)

    for i, projeto in enumerate(PROJETOS):
        with abas[i]:
            st.subheader(f"📁 Projeto: {projeto}")
            dfx = df[df["projeto"] == projeto]

            meses_disponiveis = sorted(dfx["mes"].dropna().unique())
            meses_selecionados = st.multiselect(f"Mês - {projeto}", meses_disponiveis, default=meses_disponiveis, key=f"meses_{projeto}")
            dfx = dfx[dfx["mes"].isin(meses_selecionados)]

            st.metric("Total de Tickets", len(dfx))
            st.metric("Tickets dentro do SLA", int(dfx["dentro_sla"].sum()))

            criados = dfx.groupby("mes_str").size().reset_index(name="Criados")
            resolvidos = dfx.dropna(subset=["resolved"]).groupby(dfx["resolved"].dt.to_period("M").dt.to_timestamp().dt.strftime("%b/%Y")).size().reset_index(name="Resolvidos")
            resolvidos.columns = ["mes_str", "Resolvidos"]
            grafico = pd.merge(criados, resolvidos, on="mes_str", how="outer").fillna(0)
            grafico["mes_obj"] = pd.to_datetime(grafico["mes_str"], format="%b/%Y")
            grafico = grafico.sort_values("mes_obj")

            fig = go.Figure([
                go.Bar(name="Criados", x=grafico["mes_str"], y=grafico["Criados"]),
                go.Bar(name="Resolvidos", x=grafico["mes_str"], y=grafico["Resolvidos"])
            ])
            fig.update_layout(barmode="group", title=f"Criados vs Resolvidos - {projeto}")
            st.plotly_chart(fig, use_container_width=True)

            sla_mes = dfx.groupby("mes_str")["dentro_sla"].agg(["sum", "count"]).reset_index()
            sla_mes["fora_sla"] = sla_mes["count"] - sla_mes["sum"]
            sla_mes["percentual"] = (sla_mes["sum"] / sla_mes["count"]) * 100
            sla_meta = SLA_METAS.get(projeto, 96)
            sla_mes = sla_mes.sort_values("mes_str")
            sla_meta = SLA_METAS.get(projeto, 96)
            sla_mes["cor"] = sla_mes["percentual"].apply(lambda x: "green" if x >= sla_meta else "red")
            mes_gauge = st.selectbox("🗓️ Selecione o mês para o indicador de SLA:", options=sla_mes["mes_str"].tolist(), index=len(sla_mes)-1, key=f"mes_gauge_{projeto}")

            fig_sla = go.Figure([
                go.Bar(x=sla_mes["mes_str"], y=sla_mes["percentual"], marker_color=sla_mes["cor"], name="% SLA"),
                go.Scatter(x=sla_mes["mes_str"], y=[sla_meta]*len(sla_mes), name="Meta SLA 96%", mode="lines", line=dict(color="black", dash="dash"))
            ])
            fig_sla.update_layout(title="% de Chamados dentro do SLA", yaxis_title="%", xaxis_title="Mês",
                annotations=[dict(x=0.95, y=1.05, xref="paper", yref="paper",
                text=f"🎯 Meta SLA {sla_meta:.0f}%", showarrow=False,
                font=dict(size=14, color="green"))])
            fig_sla.add_trace(go.Bar(x=sla_mes["mes_str"], y=sla_mes["fora_sla"], name="Fora SLA", marker_color="red", text=sla_mes["fora_sla"], textposition="outside"))
            
            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.plotly_chart(fig_sla, use_container_width=True)
                with col2:
                    st.markdown("#### OKR - Meta SLA")
                    fig_gauge = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=float(sla_mes[sla_mes["mes_str"] == mes_gauge]["percentual"].values[0]),
                        domain={{'x': [0, 1], 'y': [0, 1]}},
                        gauge={{
                            'axis': {{'range': [0, 100]}},
                            'bar': {{'color': "darkgreen"}},
                            'steps': [
                                {{'range': [0, sla_meta], 'color': "lightgray"}},
                                {{'range': [sla_meta, 100], 'color': "lightgreen"}}
                            ],
                            'threshold': {{
                                'line': {{'color': "red", 'width': 4}},
                                'thickness': 0.75,
                                'value': sla_meta
                            }}
                        }},
                        title={"text": f"{sla_mes[sla_mes['mes_str'] == mes_gauge]['percentual'].values[0]:.1f}%"}))
                    st.plotly_chart(fig_gauge, use_container_width=True)


            area_mes = dfx.groupby(["mes_str", "area"]).size().reset_index(name="Chamados")
            tabela = area_mes.pivot(index="mes_str", columns="area", values="Chamados").fillna(0).astype(int)
            st.markdown("#### Área Solicitante por Mês")
            st.dataframe(tabela)

            st.download_button(
                label="📥 Exportar dados do projeto",
                data=dfx.to_csv(index=False).encode("utf-8"),
                file_name=f"{projeto}_dados.csv",
                mime="text/csv"
            )

            if projeto == "TDS":
                st.markdown("### 🔹 Chamados App NE / EN")
                df_app = dfx[dfx["assunto"].apply(lambda lst: any("App NE" in s or "App EN" in s for s in lst))]
                if df_app.empty:
                    st.info("Nenhum chamado de App NE/EN encontrado.")
                else:
                    col1, col2 = st.columns(2)
                    col1.metric("Total App NE/EN", len(df_app))
                    col2.metric("% dentro SLA", f"{(df_app['dentro_sla'].mean()*100):.1f}%")

                    sla_app = df_app.groupby("mes_str")["dentro_sla"].agg(["sum", "count"]).reset_index()
                    sla_app["percentual"] = (sla_app["sum"] / sla_app["count"]) * 100
                    sla_app = sla_app.sort_values("mes_str")
                    fig_app = go.Figure([
                        go.Bar(x=sla_app["mes_str"], y=sla_app["percentual"], name="% SLA App NE/EN", marker_color="blue"),
                        go.Scatter(x=sla_app["mes_str"], y=[SLA_META]*len(sla_app), name="Meta SLA", mode="lines", line=dict(dash="dash", color="black"))
                    ])
                    fig_app.update_layout(title="% SLA - App NE/EN", yaxis_title="%", xaxis_title="Mês")
                    st.plotly_chart(fig_app, use_container_width=True)

                    st.download_button(
                        label="⬇️ Exportar App NE/EN",
                        data=df_app.to_csv(index=False).encode("utf-8"),
                        file_name="app_ne_en.csv",
                        mime="text/csv"
                    )
