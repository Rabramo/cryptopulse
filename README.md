CryptoPulse — Tech Challenge (Fase 3)
Agora-casting de direção do Bitcoin em ~5 minutos usando FastAPI, SQLite e um modelo de classificação (scikit-learn), com visualização em Streamlit.
Sumário
1. Contexto e objetivo
2. Arquitetura
3. Fonte de dados
4. Requisitos de ambiente
5. Instalação
6. Como executar
7. Endpoints da API
8. Fluxo sugerido (passo a passo)
9. Modelagem de ML
10. Métricas e validação
11. Dashboard (Streamlit)
12. Testes

1. Contexto e objetivo
Este repositório implementa um tech challenge de Data/ML com as seguintes entregas: 
API que coleta dados (quase em tempo real) e persiste em banco.
Modelo de ML treinado a partir dessa base.
Código + documentação no GitHub.
Storytelling em vídeo explicando do problema à entrega final.
Aplicação produtiva: um dashboard que consome os dados e o modelo.
Tudo conforme o enunciado da Fase 3 do Tech Challenge.
Problema proposto: prever a direção de preço do BTC nos próximos ~5 minutos (sobe/↓ desce), com atualizações rápidas de dados, para demonstrar um ciclo completo de dados → features → modelo → API → UI.
2. Arquitetura
           +--------------------+
           |  CoinGecko API     |  (Preço BTC em USD)
           +---------+----------+
                     |
               (requests)
                     v
+--------------------+-------------------+
|                FastAPI                 |
|  /ingest  /train  /predict  /data/last |
+---------+--------------+---------------+
          |              |
          | SQLAlchemy   | joblib
          v              v
   +-------------+    +----------------+
   |  SQLite     |    |  Modelo ML     |
   | prices.db   |    | model.pkl      |
   +-------------+    +----------------+
          ^                         |
          |                         |
          +-----------+-------------+
                      |
                 (HTTP/JSON)
                      v
            +----------------------+
            |  Streamlit Dashboard |
            +----------------------+
Coleta: endpoint /ingest busca o preço atual do BTC (CoinGecko) e grava uma linha com timestamp.
Treino: /train calcula features, treina uma Logistic Regression e salva models/model.pkl.
Predição: /predict retorna a probabilidade de alta nos próximos 5 “passos” (janelas consecutivas).
Dashboard: consulta a API, plota a série e exibe a última predição.
3. Fonte de dados
CoinGecko — endpoint público /simple/price para bitcoin em USD (sem API key).
Frequência de coleta: 
a) manual (botão no dashboard ou POST /ingest). 
b) coletar em lote: ideal para juntar rapidamente 60–100 amostras e treinar. Mostro progresso, sucesso/falha e tempo total.
Observação: “tempo real” aqui significa near-real-time por simplicidade (coletas frequentes via chamadas à API).
Opção de Auto-refresh, controle na sidebar; quando ativo, a página se atualiza no intervalo escolhido e o gráfico/último preço se renovam.
4. Requisitos de ambiente
Python: 3.13 (macOS arm64 suportado).
SO: macOS 12+ / Linux / WSL2 (testado em macOS).
Bibliotecas principais: FastAPI, SQLAlchemy, requests, pandas, numpy, scikit-learn, Streamlit, plotly.
Banco: SQLite (arquivo data/prices.db).
requirements.txt (compatível com Python 3.13)
fastapi==0.112.0
uvicorn==0.30.0
requests==2.32.3

# Científico (Py 3.13)
numpy>=2.1.0,<3
pandas==2.2.3
scipy>=1.14.1,<1.16
scikit-learn==1.6.1
joblib==1.4.2
threadpoolctl>=3.5.0

SQLAlchemy==2.0.31
pydantic>=2.8,<3
python-multipart==0.0.9

streamlit==1.36.0
plotly==5.22.0
Se preferir, pode usar Python 3.12 e versões “mais antigas” (ex.: scikit-learn==1.4.2, numpy==1.26.4, pydantic==2.7.x). Este README assume 3.13.
5. Instalação
# 1) criar e ativar venv
python -m venv .venv
source .venv/bin/activate   # (Linux/macOS)  |  .venv\Scripts\activate (Windows)

# 2) instalar dependências
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt
6. Como executar
6.1 Subir a API
uvicorn app.api:app --reload --port 8000
A API cria/usa data/prices.db.
Endereço padrão: http://localhost:8000.
6.2 Rodar o Dashboard
Em outro terminal:
streamlit run dashboard/streamlit_app.py
O dashboard usa API_BASE=http://localhost:8000 por padrão (pode sobrescrever via variável de ambiente).
7. Endpoints da API
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
8. Fluxo sugerido (passo a passo)
Suba a API (seção 6.1).
Colete dados: rode POST /ingest algumas vezes (ideal: ~1x/min por 10–20 min).
Treine: POST /train e verifique acc_test no retorno.
Predição: GET /predict para a probabilidade de alta.
Abra o dashboard e use os botões para coletar/treinar/predizer e visualizar a série.
Dica: se quiser automatizar a coleta, use um cron local ou inclua APScheduler (ver Roadmap).
9. Modelagem de ML
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
Atenção: é um baseline didático; não utilizar para trading real.
10. Métricas e validação
Métrica exibida: accuracy no conjunto de teste (hold-out temporal).
Melhorias possíveis (Roadmap): curva ROC/AUC, matriz de confusão, validação walk-forward, backtest de estratégia simples (ex.: threshold de probabilidade), métricas de lucro/perda simulada.
11. Dashboard (Streamlit)
Botões: “Coletar preço agora”, "Coletar em Lote", "Auto-Refresh",“Treinar modelo”, “Predizer próxima direção (5 min)”,.
Gráfico: série de preço das últimas leituras (Plotly).
Métrica: “Probabilidade de Alta (5 min)” (exibe proba_up_next_5).
Variáveis de ambiente:
# opcional
export API_BASE="http://localhost:8000"
12. Testes
Teste simples de fumaça:
pytest -q
# ou
python -m pytest -q
(Arquivo: tests/test_smoke.py).