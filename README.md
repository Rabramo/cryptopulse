## Turma de Machine Learning Engineering - 1º semestre 2025 - Pós-Tech FIAP+Alura - TC FASE 3

### Grupo 138 - Integrante: ROGÉRIO ABRAMO ALVES PRETTI - RM 363736

### DISCLAIMER 
É apenas um hands on de avalição acadêmcia, não utilizar para trading real. 

### DASHBOARD: https://rabramo-cryptopulse-dashboardstreamlit-app-fvrftu.streamlit.app
### API: https://cryptopulse-okqa.onrender.com
### API DOCS: https://cryptopulse-okqa.onrender.com/docs
### YOUTUBE: https://youtube.com/@rabramo2008?si=T_Y0Oy0xRUHvFl64

## CRYPTOPULSE – BTC Nowcasting (FastAPI + Render + Neon + Streamlit Cloud)

Nowcasting de direção do Bitcoin em ~5 minutos usando FastAPI no Render (Python runtime), PostgreSQL (Neon) como database e modelo de regressão linear(scikit-learn), com visualização em Streamlit.

ARQUITETURA DA SOLUÇÃO VER ARQUIVO ARCH.txt

ESTRUTURA DO PROJETO VER ARQUIVO STRUCT.txt

PASSOS

Coleta: endpoint /ingest busca o preço atual do BTC (CoinGecko) e grava uma linha com timestamp.

Treino: /train calcula features, treina uma Logistic Regression e salva models/model.pkl.

Predição: /predict retorna a probabilidade de alta nos próximos 5 “passos” (janelas consecutivas).

Dashboard: consulta a API, plota a série e exibe a última predição.

FONTES DE DADOS

CoinGecko — endpoint público /simple/price para bitcoin em USD (sem API key).

Frequência de coleta: 

a) manual (botão no dashboard ou POST /ingest). 

b) coletar em lote: ideal para juntar rapidamente 60–100 amostras e treinar. Mostro progresso, sucesso/falha e tempo total.

Observação: “tempo real” aqui significa near-real-time por simplicidade (coletas frequentes via chamadas à API).

Opção de Auto-refresh, controle na sidebar; quando ativo, a página se atualiza no intervalo escolhido e o gráfico/último preço se renovam.

Endpoints da API

GET / — Healthcheck:
{"ok": true, "service": "CryptoPulse"}

POST /ingest — Coleta o preço atual e grava no banco.

curl -X POST http://localhost:8000/ingest

POST /train — Treina o modelo (gera models/model.pkl).

curl -X POST http://localhost:8000/train

GET /predict — Probabilidade de alta nos próximos 5 passos.

curl http://localhost:8000/predict

GET /data/last?n=200 — Últimos n registros (p/ gráficos).

curl "http://localhost:8000/data/last?n=300"

Códigos de retorno/erros comuns:

{"status":"not_enough_data"} — colete mais leituras antes do treino/predição.
{"status":"no_model"} — treine o modelo antes de predizer.

MODELAGEM ML

Tarefa: classificação binária (sobe = 1, desce = 0) no horizonte de 5 passos.

Features (sobre a série de preço):

ret1: log-retorno 1 passo

ret3: log-retorno 3 passos

vol5: desvio padrão móvel de ret1 (5)

ma5, ma15: médias móveis

mom5: momentum (diferença de 5 passos)

Target: 1 se price(t+5) > price(t), senão 0.

Modelo: StandardScaler + LogisticRegression (rápido de treinar/explicar).

Split: hold-out temporal (shuffle=False, 75% treino / 25% teste).

