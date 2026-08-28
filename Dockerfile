FROM python:3.11-slim

WORKDIR /app

# Instalar dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY web_app/ ./web_app/

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Executar com uvicorn
CMD exec uvicorn web_app.app:app --host 0.0.0.0 --port ${PORT}
