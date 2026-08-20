# CRM Nova Uniao - Streamlit

Visualizacao dos leads da tabela `clientes_novauniao.prospecao_mkt`.

## Rodar localmente

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit/streamlit_app.py
```

O app le `SUPABASE_DATABASE_URL` de `streamlit/.env`, do `.env` na raiz local ou dos secrets do Streamlit.

## Deploy no Streamlit

Configure o secret:

```toml
SUPABASE_DATABASE_URL = "postgresql://usuario:senha@host:5432/postgres"
```

Arquivo principal:

```text
streamlit/streamlit_app.py
```
