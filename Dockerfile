FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
RUN sentinel-eval run datasets/product_support.jsonl --mutations --min-pass-rate 0.8
EXPOSE 8000
CMD ["uvicorn", "agent_guardrails.evaluate.api:app", "--host", "0.0.0.0", "--port", "8000"]

