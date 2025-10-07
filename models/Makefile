.PHONY: api dash ingest train predict
init:
\tpython -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
api:
\tuvicorn app.api:app --reload --port 8000
dash:
\tstreamlit run dashboard/streamlit_app.py
ingest:
\tcurl -X POST http://localhost:8000/ingest
train:
\tcurl -X POST http://localhost:8000/train
predict:
\tcurl http://localhost:8000/predict
