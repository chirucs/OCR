#!/bin/bash
apt-get update
apt-get install -y tesseract-ocr poppler-utils
streamlit run app.py --server.port 8000 --server.enableCORS false
