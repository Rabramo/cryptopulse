import os
import time
import requests
import pandas as pd
import plotly.express as px
import streamlit as st

# =========================
# Design (DS Gov)
# =========================
DS_AZUL_PRIM = "#1351B4"   # Azul 700
DS_AZUL_ESCU = "#0C326F"   # Azul escuro (títulos)
DS_AMARELO   = "#F7A600"   # Amarelo 500
DS_VERDE     = "#168821"   # Verde 700
DS_VERMELHO  = "#A80521"   # Vermelho 700
DS_CINZA_10  = "#F5F5F5"
DS_CINZA_80  = "#4D4D4D"
GRID         = "#E6E6E6"

ACCENT = DS_AZUL_PRIM
TEXT   = DS_CINZA_80
BG     = "#FFFFFF"

st.set_page_config(
    page_title="CryptoPulse – BTC Nowcasting",
    layout="wide",
   
)

# Font Awesome + tipografia + estilos
st.markdown(
    f"""
    <link rel="stylesheet"
          href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"
          crossorigin="anonymous" referrerpolicy="no-referrer" />
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
      html, body, [class*="css"]  {{ font-family: 'Roboto', Arial, sans-serif; color: {TEXT}; }}
      h1, h2, h3, h4 {{ color: {DS_AZUL_ESCU}; font-weight: 700; letter-spacing: .2px; }}
      .stAlert, .stMetric, .stDataFrame, .stPlotlyChart, .stMarkdown {{ border-radius: 14px !important; }}
      .stButton>button {{
        background: {DS_AZUL_PRIM}; color: #fff; border: 0; border-radius: 10px;
        padding: .6rem 1rem; font-weight: 600;
      }}
      .stButton>button:hover {{ filter: brightness(0.95); }}
      .stTextInput>div>div>input, .stNumberInput input {{
        border-radius: 10px; border: 1px solid #D9D9D9;
      }}
      section[data-testid="stSidebar"] {{ background: {DS_CINZA_10}; }}
      .fa-label {{ color: {DS_AZUL_ESCU}; font-weight: 600; margin-bottom: .35rem; }}
      .fa-muted {{ color:#6b7280; font-weight: 500; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ======================
# Helpers de API / Secrets
# ======================
def safe_has_secret(key: str) -> bool:
    try:
        return key in st.secrets
    except Exception:
        return False

def safe_get_secret(key: str, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

def get_default_api() -> str:
    if safe_has_secret("API_BASE"):
        return safe_get_secret("API_BASE").rstrip("/")
    return os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")

def call_json(method: str, url: str, **kwargs):
    try:
        timeout = kwargs.pop("timeout", 10)
        r = requests.request(method, url, timeout=timeout, **kwargs)
        ctype = r.headers.get("content-type", "").lower()
        if "application/json" in ctype:
            return r.status_code, r.json()
        return r.status_code, {"non_json": r.text[:800]}
    except Exception as e:
        return 0, {"exception": str(e)}

def api_call(path: str, method: str = "GET", **kwargs):
    base = st.session_state.get("api_base", get_default_api()).rstrip("/")
    return call_json(method, f"{base}{path}", **kwargs)

def render_status(label: str, status: int, body: dict):
    box = {"status": status, "body": body}
    if status == 200:
        st.success({label: box}, icon="✅")
    elif status == 0:
        st.error({label: box}, icon="🛑")
    else:
        st.warning({label: box}, icon="⚠️")

def is_api_up(base: str, timeout=1.8) -> bool:
    try:
        r = requests.get(base.rstrip("/") + "/", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False

# =================
# Sidebar (controles)
# =================
PROD = safe_has_secret("API_BASE")
if "api_base" not in st.session_state:
    st.session_state.api_base = get_default_api()

with st.sidebar:
    st.header("Config")
    if PROD:
        st.markdown('<div class="fa-label"><i class="fa-solid fa-plug"></i> API Base</div>', unsafe_allow_html=True)
        st.text_input("API Base", value=st.session_state.api_base, disabled=True, label_visibility="collapsed")
        st.caption("Definido em Secrets (Streamlit Cloud).")
        if ("localhost" in st.session_state.api_base) or ("127.0.0.1" in st.session_state.api_base):
            st.warning("API_BASE inválido para produção. Ajuste em Secrets para a URL do Render.", icon="⚠️")
    else:
        st.markdown('<div class="fa-label"><i class="fa-solid fa-plug"></i> API Base</div>', unsafe_allow_html=True)
        st.session_state.api_base = st.text_input(
            "API Base", value=st.session_state.api_base, label_visibility="collapsed",
            help="Ex.: http://127.0.0.1:8000 ou a URL pública do Render",
        )

    st.divider()
    st.subheader("Auto-refresh")
    auto = st.checkbox("Atualizar automaticamente", value=False, help="Recarrega a página para buscar dados novos.")
    secs = st.slider("Intervalo (segundos)", 3, 60, 10, disabled=not auto)

# =========================
# Readiness
# =========================
if not is_api_up(st.session_state.api_base):
    with st.container(border=True):
        st.warning("Conectando à API…", icon="⏳")
        st.write("Aguardando:", st.session_state.api_base)
    time.sleep(2)
    st.experimental_rerun()

# ===========
# Cabeçalho UI
# ===========
st.markdown('<h1><i class="fa-solid fa-chart-line"></i> CryptoPulse – BTC Nowcasting</h1>', unsafe_allow_html=True)

# =========
# Ações/API
# =========
colA, colB = st.columns([3, 2])

with colA:
    c1, c2 = st.columns(2)

    # Ações unitárias
    with c1:
        st.markdown('<div></div>', unsafe_allow_html=True)
        if st.button("Coletar preço agora", use_container_width=True, key="btn_ingest"):
            status, body = api_call("/ingest", method="POST", timeout=12)
            render_status("ingest", status, body)

    with c2:
        st.markdown('<div> </div>', unsafe_allow_html=True)
        if st.button("Treinar modelo", use_container_width=True, key="btn_train"):
            status, body = api_call("/train", method="POST", timeout=60)
            render_status("train", status, body)

    # --------- COLETA EM LOTE (server-side) ---------
    st.markdown('### <i class="fa-solid fa-layer-group"></i> Coletar em lote', unsafe_allow_html=True)
    qtty  = st.number_input("Quantidade de coletas", min_value=5, max_value=500, value=60, step=5)
    delay = st.number_input("Intervalo entre coletas (segundos)", min_value=5, max_value=120, value=12, step=1)
    st.markdown('<div class="fa-muted"><i class="fa-regular fa-circle-question"></i> Lote executa no servidor (API). A página acompanha o progresso.</div>', unsafe_allow_html=True)

    cols = st.columns([1, 1, 2])
    with cols[0]:
        st.markdown('<div> </div>', unsafe_allow_html=True)
        if st.button("Iniciar coleta em lote", use_container_width=True, key="btn_batch_start"):
            # warm-up explícito
            api_call("/", timeout=5)
            status, body = api_call(
                f"/ingest_batch?count={int(qtty)}&delay={float(delay)}",
                method="POST", timeout=10
            )
            render_status("ingest_batch", status, body)
            st.session_state.batch_poll = True  # liga polling local

    with cols[1]:
        st.markdown('<div> </div>', unsafe_allow_html=True)
        if st.button("Parar lote", use_container_width=True, key="btn_batch_stop"):
            status, body = api_call("/batch/stop", method="POST", timeout=6)
            render_status("batch_stop", status, body)
            st.session_state.batch_poll = True

    # polling de status: mostra progresso sempre
    status, info = api_call("/batch/status", timeout=6)
    if status == 200 and isinstance(info, dict):
        total   = max(1, int(info.get("target", 1)))
        done    = int(info.get("done", 0))
        fail    = int(info.get("fail", 0))
        running = bool(info.get("running", False))
        st.progress(done / total if total else 0.0,
                    text=f"Progresso do lote: {done}/{total} (falha={fail})")
        if running and not auto:
            # pequeno polling manual para atualizar a barra quando auto-refresh estiver desligado
            time.sleep(2)
            st.experimental_rerun()

with colB:
    st.markdown('<div> </div>', unsafe_allow_html=True)
    if st.button("Tendência de alta/baixa próx. 5 min", use_container_width=True, key="btn_predict"):
        status, body = api_call("/predict", timeout=12)
        if status == 200 and body.get("status") == "ok":
            st.metric("Probabilidade de Alta (5 min)", f"{body.get('proba_up_next_5', 0) * 100:.1f}%")
        render_status("predict", status, body)

# =================
# Série / Visualização
# =================
status, body = api_call("/data/last?n=300", timeout=12)
if status == 200 and isinstance(body, dict) and "data" in body:
    df = pd.DataFrame(body["data"])
    if not df.empty:
        if not pd.api.types.is_datetime64_any_dtype(df["ts_utc"]):
            df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True, errors="coerce")
        df = df.dropna(subset=["ts_utc", "price_usd"])

        last_row = df.iloc[-1]
        st.metric("Último preço BTC (USD)", f"{last_row['price_usd']:.2f}")

        fig = px.line(
            df, x="ts_utc", y="price_usd",
            title="Preço BTC (últimas leituras)",
            color_discrete_sequence=[ACCENT],
        )
        fig.update_traces(line=dict(width=3), hovertemplate="%{x}<br>USD %{y:.2f}<extra></extra>")
        fig.update_layout(
            paper_bgcolor=BG, plot_bgcolor=BG, font=dict(color=TEXT, size=14),
            xaxis=dict(showgrid=True, gridcolor=GRID, title=""),
            yaxis=dict(showgrid=True, gridcolor=GRID, title="USD"),
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Ver últimas linhas"):
            st.dataframe(
                df.tail(15).rename(columns={"ts_utc": "timestamp (UTC)", "price_usd": "preco_usd"}),
                use_container_width=True,
            )
    else:
        st.info("Sem dados ainda. Use “Coletar preço agora” ou “Coletar em lote”.")
else:
    render_status("data/last", status, body)

# =================
# Auto-refresh simples
# =================
if auto:
    time.sleep(int(secs))
    st.experimental_rerun()
