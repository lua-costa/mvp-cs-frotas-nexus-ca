#!/bin/bash
set -e

# Configurações do Projeto
PROJECT_ID=${1:-"cs-demo-2026"}
LOCATION=${2:-"US"}
DATASET_ID="cs_frotas_data"

echo "📌 Configurando projeto ativo..."
gcloud config set project $PROJECT_ID

echo "🔌 Habilitando APIs necessárias (BigQuery, Vertex AI / AI Platform)..."
gcloud services enable bigquery.googleapis.com aiplatform.googleapis.com --project=$PROJECT_ID

echo "🗄️ Criando dataset BigQuery '$DATASET_ID' na localização $LOCATION..."
bq --location=$LOCATION mk --dataset $PROJECT_ID:$DATASET_ID || echo "Dataset já existe."

echo "✅ Setup do ambiente GCP concluído com sucesso!"
