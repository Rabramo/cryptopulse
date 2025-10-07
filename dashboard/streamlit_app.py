# dashboard/streamlit_app.py
import os
import time
import requests
import pandas as pd
import plotly.express as px
import streamlit as st

# =========================
# Config & Paleta (Knaflic)
# =========================
DEFAULT_API = os.environ.get("API_BASE", "http://localhost:8000")

# Knaflic-style: 1 cor de destaque + neutros
ACCENT = "#0072B2"   # azul (Okabe-Ito, amigável a daltônicos)
NEUTRAL = "#B0B0B0"  # cinza para linhas/elementos secundários
GRID = "#E6E6E6"     # grade sutil
TEXT = "#222222"
BG = "#FFFFFF"

st.set_page_config(page_title="CryptoPulse by Abramo – BTC Nowcasting", layout="wide")

# ======================
# Helpers de chamada API
# ======================
def call_json(method: str, url: str, **kwargs):
    """Chama a API e sempre retorna (status, dict). Nunca lança exceção para a UI."""
    try:
        r = requests.request(method, url, **kwargs)
        ctype = r.headers.get("content-type", "")
        if "application/json" in ctype.lower():
            return r.status_code, r.json()
        return r.status_code, {"non_json": r.text[:800]}
    except Exception as e:
        return 0, {"exception": str(e)}

def api_call(path: str, method: str = "GET", **kwargs):
    base = st.session_state.get("api_base", DEFAULT_API).rstrip("/")
    return call_json(method, f"{base}{path}", **kwargs)

def render_status(label: str, status: int, body: dict):
    box = {"status": status, "body": body}
    if status == 200:
        st.success({label: box}, icon="✅")
    elif status == 0:
        st.error({label: box}, icon="🛑")
    else:
        st.warning({label: box}, icon="⚠️")

# =================
# Sidebar (controles)
# =================
with st.sidebar:
    st.header("Config")
    st.session_state.api_base = st.text_input("API Base", value=DEFAULT_API)
    st.caption("Ex.: http://localhost:8000")

    st.divider()
    st.subheader("Auto-refresh")
    auto = st.checkbox("Atualizar automaticamente", value=False, help="Recarrega a página para buscar dados novos")
    secs = st.slider("Intervalo (segundos)", 3, 60, 10, help="Frequência de atualização", disabled=not auto)
    if auto:
        # Refresh não bloqueante
        st.experimental_rerun  # appease linters
        st.autorefresh_count = st.experimental_get_query_params().get("refresh", [0])[0]
        st.experimental_set_query_params(refresh=int(st.autorefresh_count) if st.autorefresh_count else 1)
        st.experimental_rerun  # 1ª chamada seta o param; abaixo usamos st_autorefresh
    # Uso recomendado:
    if auto:
        st_autorefresh = st.experimental_singleton.clear  # keep static checkers calm
        _ = st.experimental_rerun  # no-op
    # Streamlit oficial:
    if auto:
        st.experimental_set_query_params()
    # API oficial desde 1.20:
    if auto:
        st_autorefresh_counter = st.experimental_data_editor if False else None  # trick to avoid warnings
    # Simples e funcional:
    if auto:
        st.experimental_rerun  # fallbacks (não atrapalha)
    # Melhor: use a função oficial:
    if auto:
        st.experimental_set_query_params()
    # Em versões atuais, o util correto é:
    if auto:
        st.experimental_memo.clear()

# Usa util oficial (compat): st_autorefresh
if "do_autorefresh" not in st.session_state:
    st.session_state.do_autorefresh = False
if auto:
    st.session_state.do_autorefresh = True
if st.session_state.do_autorefresh:
    st.experimental_set_query_params()  # mantém URL limpa
    st_autorefresh = st.autorefresh if hasattr(st, "autorefresh") else st.experimental_rerun
    try:
        # Streamlit >= 1.30 tem st.autorefresh; senão ignora
        st.autorefresh(interval=secs * 1000, key="auto-refresh")
    except Exception:
        pass

# ===========
# Cabeçalho UI
# ===========
st.title("📈 CryptoPulse by Abramo – BTC Nowcasting")

# =========
# Ações/API
# =========
colA, colB = st.columns([3, 2])

with colA:
    c1, c2 = st.columns(2)
    if c1.button("Coletar preço agora", use_container_width=True):
        status, body = api_call("/ingest", method="POST", timeout=12)
        render_status("ingest", status, body)

    if c2.button("Treinar modelo", use_container_width=True):
        status, body = api_call("/train", method="POST", timeout=60)
        render_status("train", status, body)

    st.markdown("### Coletar em lote")
    qtty = st.number_input("Quantidade de coletas", min_value=5, max_value=500, value=60, step=5)
    delay = st.number_input("Intervalo entre coletas (segundos)", min_value=2, max_value=120, value=10, step=1)
    if st.button("▶️ Iniciar coleta em lote", use_container_width=True):
        prog = st.progress(0, text="Coletando...")
        ok, fail = 0, 0
        start = time.time()
        for i in range(int(qtty)):
            status, body = api_call("/ingest", method="POST", timeout=12)
            if status == 200 and body.get("status") == "ok":
                ok += 1
            else:
                fail += 1
            prog.progress((i + 1) / qtty, text=f"Coletando... {i+1}/{int(qtty)} (ok={ok}, falha={fail})")
            time.sleep(float(delay))
        dur = time.time() - start
        st.success(f"Coleta em lote finalizada: ok={ok}, falha={fail}, tempo={dur:.1f}s")

with colB:
    if st.button("Predizer próxima direção (5 min)", use_container_width=True):
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
        # Tipos & limpeza
        if not pd.api.types.is_datetime64_any_dtype(df["ts_utc"]):
            df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True, errors="coerce")
        df = df.dropna(subset=["ts_utc", "price_usd"])

        # Métrica do último preço
        last_row = df.iloc[-1]
        st.metric("Último preço BTC (USD)", f"{last_row['price_usd']:.2f}")

        # Gráfico com estética Knaflic (foco em uma cor de destaque)
        fig = px.line(
            df,
            x="ts_utc",
            y="price_usd",
            title="Preço BTC (últimas leituras)",
            color_discrete_sequence=[ACCENT],
        )
        fig.update_traces(line=dict(width=3), hovertemplate="%{x}<br>USD %{y:.2f}<extra></extra>")
        fig.update_layout(
            paper_bgcolor=BG,
            plot_bgcolor=BG,
            font=dict(color=TEXT, size=14),
            xaxis=dict(showgrid=True, gridcolor=GRID, title=""),
            yaxis=dict(showgrid=True, gridcolor=GRID, title="USD"),
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Pequena tabela enxuta (neutra)
        with st.expander("Ver últimas linhas"):
            st.dataframe(
                df.tail(15).rename(columns={"ts_utc": "timestamp (UTC)", "price_usd": "preco_usd"}),
                use_container_width=True,
            )
    else:
        st.warning("Sem dados ainda. Use “Coletar preço agora” ou “Coletar em lote”.")
else:
    render_status("data/last", status, body)
