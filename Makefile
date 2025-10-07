RENDER_API_BASE ?= https://cryptopulse-okqa.onrender.com
PORT ?= 8501

.PHONY: dash

dash:
	- kill -9 $$(lsof -t -i:$(PORT)) 2>/dev/null || true
	API_BASE=$(RENDER_API_BASE) streamlit run dashboard/streamlit_app.py --server.port $(PORT)
