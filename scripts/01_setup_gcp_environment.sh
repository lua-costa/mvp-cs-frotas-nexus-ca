#!/bin/bash
set -e

# Configurações do Projeto
PROJECT_ID=${1:-"your-gcp-project-id"}
LOCATION=${2:-"US"}
DATASET_ID="cs_frotas_data"
BUCKET_NAME=${3:-"${PROJECT_ID}-cs-frotas-raw-data"}

echo "📌 Configurando projeto ativo..."
gcloud config set project $PROJECT_ID

echo "🔌 Habilitando APIs necessárias (BigQuery, Vertex AI, Cloud Storage)..."
gcloud services enable bigquery.googleapis.com aiplatform.googleapis.com storage.googleapis.com --project=$PROJECT_ID

echo "🗄️ Criando dataset BigQuery '$DATASET_ID' na localização $LOCATION..."
bq --location=$LOCATION mk --dataset $PROJECT_ID:$DATASET_ID || echo "Dataset já existe."

echo "🪣 Criando Bucket no Google Cloud Storage 'gs://$BUCKET_NAME'..."
gcloud storage buckets create gs://$BUCKET_NAME --location=$LOCATION --project=$PROJECT_ID || echo "Bucket já existe ou não foi possível criar."

echo "✅ Setup do ambiente GCP concluído com sucesso!"
