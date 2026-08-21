# CRM Nova Uniao - Streamlit

Visualizacao dos leads da tabela `clientes_novauniao.prospecao_mkt`.

## Rodar localmente

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit/streamlit_app.py
```

O app le `SUPABASE_DATABASE_URL` de `streamlit/.env`, do `.env` na raiz local ou dos secrets do Streamlit.

## Deploy no EasyPanel

Este projeto esta pronto para rodar como container usando `streamlit/Dockerfile`.

No EasyPanel:

1. Crie um servico do tipo `App`.
2. Em `Source`, selecione `GitHub`.
3. Informe o repositorio e a branch.
4. Configure `Build Path` como `/streamlit`.
5. Em `Build`, selecione `Dockerfile` com path `Dockerfile`.
6. Em `Environment`, adicione:

```env
SUPABASE_DATABASE_URL=postgresql://usuario:senha@host:5432/postgres
TZ=America/Sao_Paulo
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
```

7. Em `Domains`, adicione o dominio/subdominio desejado e use:

```text
Internal protocol: HTTP
Target port: 8501
```

8. No DNS do dominio, aponte um registro `A` para o IP da VPS.

O container escuta em `0.0.0.0:8501` e possui healthcheck em `/_stcore/health`.

## Arquivo principal

```text
streamlit/streamlit_app.py
```
