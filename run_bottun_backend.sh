#!/bin/bash
cd backend
export OPENAI_API_BASE_URLS="https://api.openai.com/v1;http://localhost:8081/bottun/v1"
export OPENAI_API_KEYS="sk-placeholder;any"
# Use the uvicorn from the open-webui conda environment
/Users/sophia/anaconda3/envs/open-webui/bin/uvicorn open_webui.main:app --host 0.0.0.0 --port 8081 --forwarded-allow-ips '*'
