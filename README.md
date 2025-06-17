# Painel de Indicadores - Jira (Projetos INT & INTEL)

Este painel em Streamlit se conecta diretamente à API do Jira para exibir indicadores de produtividade e SLA dos projetos INT e INTEL.

## Funcionalidades
- Chamados criados e resolvidos por mês
- SLA médio
- Classificação por assunto (labels)
- Distribuição por área (componentes)
- Alerta de tickets acima do SLA (>7 dias)

## Como usar

1. Suba este repositório no GitHub.
2. Vá para https://streamlit.io/cloud e clique em "Deploy".
3. Selecione o repositório e o arquivo `painel_jira.py`.
4. Adicione suas credenciais no menu **Settings > Secrets**:

```toml
JIRA_URL = "https://seudominio.atlassian.net"
EMAIL = "seu.email@empresa.com"
TOKEN = "SEU_API_TOKEN"
```

5. Acesse o painel pela URL gerada.

---

