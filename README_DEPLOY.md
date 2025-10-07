# Deploy – CryptoPulse (Render + Neon + Streamlit Cloud)

Este guia publica:
- **API FastAPI** no **Render** (runtime Python)
- **Banco**: **Neon Postgres** (via `DB_URL`)
- **Dashboard**: **Streamlit Community Cloud**

---

## 1) Pré-requisitos
- Repo atualizado (branch `main`).
- `requirements.txt` inclui `psycopg[binary]`.
- Banco no Neon criado e testado.

---

## 2) Variáveis de ambiente
- **DB_URL (obrigatória)** – formato psycopg3: postgresql+psycopg://neondb_owner:SENHA@ep-XXXXX.sa-east-1.aws.neon.tech/neondb?sslmode=require

- Opcionais:
- `MIN_TRAIN_ROWS=120`
- `PYTHONUNBUFFERED=1`

## 3) Deploy da API no Render (Git Provider)

1. **New → Web Service** → selecione o repositório e a branch **`main`**.
2. Campos:
 - **Root Directory**: *(vazio)*
 - **Build Command**:
   ```bash
   pip install --upgrade pip && pip install -r requirements.txt "psycopg[binary]"
   ```
 - **Start Command**:
   ```bash
   uvicorn app.api:app --host 0.0.0.0 --port $PORT
   ```
 - **Health Check Path**: `/`
3. Em **Environment → Environment Variables**, crie:
 - `DB_URL = postgresql+psycopg://...neon.tech/neondb?sslmode=require`
 - `PYTHONUNBUFFERED = 1`
 - `MIN_TRAIN_ROWS = 120` *(opcional)*
4. **Create Web Service**. Após deploy:
 - Teste `https://cryptopulse-okqa.onrender.com`
 - Docs: `https://cryptopulse-okqa.onrender.com/docs`

**Redeploy manual quando precisar**
- **Manual Deploy → Clear build cache & deploy**
- Garanta **Auto-Deploy = Yes** (cada push na `main` redeploya).

---

## 4) Dashboard no Streamlit Cloud

1. Acesse **streamlit.io/cloud → New app**.
2. App file: `dashboard/streamlit_app.py`.
3. Em **Settings → Secrets**, adicione:
 ```toml
 API_BASE = "https://cryptopulse-okqa.onrender.com"