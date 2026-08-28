#!/bin/bash
set -e

# Configurações do Projeto
PROJECT_ID=${1:-"your-gcp-project-id"}
LOCATION=${2:-"US"}
DATASET_ID="cs_frotas_data"
BUCKET_NAME=${3:-"${PROJECT_ID}-cs-frotas-raw-data"}

echo "📌 Configurando projeto ativo..."
gcloud config set project $PROJECT_ID

echo "🔌 Habilitando APIs necessárias (BigQuery, Vertex AI, Cloud Storage, Compute, Notebooks)..."
gcloud services enable bigquery.googleapis.com aiplatform.googleapis.com storage.googleapis.com compute.googleapis.com notebooks.googleapis.com --project=$PROJECT_ID

echo "🗄️ Criando dataset BigQuery '$DATASET_ID' na localização $LOCATION..."
bq --location=$LOCATION mk --dataset $PROJECT_ID:$DATASET_ID || echo "Dataset já existe."

echo "🪣 Criando Bucket no Google Cloud Storage 'gs://$BUCKET_NAME'..."
gcloud storage buckets create gs://$BUCKET_NAME --location=$LOCATION --project=$PROJECT_ID || echo "Bucket já existe ou não foi possível criar."

echo "🌐 Criando Rede VPC e Sub-rede em us-central1 para Runtimes do BigQuery Studio..."
gcloud compute networks create bigquery-notebooks-vpc --subnet-mode=custom --project=$PROJECT_ID || echo "Rede VPC já existe."
gcloud compute networks subnets create bigquery-notebooks-subnet-us-central1 \
  --network=bigquery-notebooks-vpc \
  --region=us-central1 \
  --range=10.128.0.0/20 \
  --enable-private-ip-google-access \
  --project=$PROJECT_ID || echo "Sub-rede já existe."

gcloud compute firewall-rules create allow-internal-bigquery-notebooks \
  --network=bigquery-notebooks-vpc \
  --allow=tcp,udp,icmp \
  --source-ranges=10.128.0.0/20 \
  --project=$PROJECT_ID || echo "Regra de firewall já existe."

echo "✅ Setup do ambiente GCP concluído com sucesso!"
