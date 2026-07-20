#!/usr/bin/env bash
set -e
uv run streamlit run app/ui/app.py --server.port 8501
