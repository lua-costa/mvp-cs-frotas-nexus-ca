# 🚗 CS Frotas — Nexus CA (MVP de Inteligência de Frotas & Auditoria com Gemini)

O **Nexus CA** é uma plataforma analítica e agente inteligente desenvolvido para a **CS Frotas**, combinando a escalabilidade do **Google BigQuery**, a capacidade cognitiva dos modelos **Gemini (Vertex AI / BigQuery ML)** e uma interface interativa moderna para auditoria de manutenção, reconciliação de catálogos e gestão de **Cobrança de Avarias (CA)**.

---

## 📌 Contexto & Desafio de Negócio

A CS Frotas gerencia um volume massivo de manutenções preventivas e corretivas em sua frota de locação e terceirização. O desafio central envolve dois ecossistemas de dados heterogêneos:

1. **VETOR (Operação de Manutenção / OS)**: Registros detalhados de Ordens de Serviço, oficinas, itens substituídos, valores de orçamento, pareceres técnicos e cobranças de avarias de clientes.
2. **SAP MB52 (ERP / Gestão de Estoque & Suprimentos)**: Visão contábil e física de estoques, depósitos, plantas industriais e custos de materiais.

### Principais Dores Solucionadas:
- **Descasamento de Catálogos**: Ausência de chave primária direta entre a descrição livre no sistema Vetor e o código de material SAP.
- **Detecção de Sobrepreço e Anomalias**: Identificação de variações atípicas em orçamentos e discrepâncias de preços frente à tabela de referência.
- **Auditoria de Cobrança de Avaria (CA)**: Classificação automatizada dos pareceres textuais das OS para justificar cobranças ao cliente com base em regras contratuais.
- **Acesso Democrático aos Dados**: Interface conversacional via linguagem natural com geração instantânea de SQL, tabelas e gráficos dinâmicos.

---

## 📊 Estrutura dos Dados no BigQuery
 
Dataset: `cs_frotas_data` no seu projeto GCP (`PROJECT_ID`).

| Tabela / View | Descrição | Volume | Colunas Principais |
| :--- | :--- | :---: | :--- |
| **`relatorio_item_vetor`** | Itens de Ordens de Serviço do VETOR | **249.467** | `numero_os`, `placa`, `descricao`, `valor_total`, `valor_total_ca`, `parecer_tecnico`, `status_os` |
| **`relatorio_estoque_sap_mb52`** | Posição de estoque SAP MB52 | **2.097.150** | `material`, `texto_breve_de_material`, `centro`, `deposito`, `utilizacao_livre`, `valutilizlivre` |
| **`dicionario_dados_vetor`** | Metadados e catálogo do Vetor | **106** | `nome_coluna`, `tipo_dado`, `descricao_campo`, `classificacao_lgpd` |
| **`dicionario_dados_sap`** | Metadados de estoque SAP | **10** | `nome_coluna`, `tipo_dado`, `descricao_campo` |
| **`vw_cruzamento_vetor_sap`** | Visão comparativa de estoque/valores | *View* | `codigo_item_vetor`, `codigo_material_sap`, `dif_valor`, `status_divergencia` |
| **`tb_depara_vetor_sap_gemini`** | De-Para semântico IA com JSON | Catálogo | `hash_descricao_vetor`, `codigo_sap_correspondente`, `grau_confianca` |

---

## 💡 Recursos e Inovações Implementadas

### 1. Ingestão Inteligente com Regras de Negócio
- **Sanitização de Nomes**: Conversão de caracteres acentuados, símbolos e espaços para o padrão BigQuery.
- **Filtro de Descarte Oculto**: Exclusão automática de ordens reprovadas ou registros sem item válido.
- **Correção de Sinais**: Tratamento para métricas de "Redução de Orçamento" garantindo valor absoluto.
- **Deduplicação de Cobrança de Avaria**: Consolidação de `valor_total_ca` com fallback para `valor_cliente` para evitar dupla contagem.

### 2. De-Para Semântico Vetor $	imes$ SAP com Gemini
Para evitar estourar cotas e custos ao cruzar 249k linhas do Vetor com 2.09M do SAP:
- **Desduplicação por Hash**: Agrupamento por `FARM_FINGERPRINT(TRIM(UPPER(descricao)))`, reduzindo a volumetria de inferência em mais de **90%**.
- **Prompt Estruturado em JSON**: O Gemini analisa o item do Vetor contra o catálogo SAP e responde com `codigo_sap_correspondente`, `grau_confianca` e `justificativa`.
- **Reassentamento SQL**: Join tradicional para propagar a classificação da IA sobre toda a base histórica.

### 3. Agente Conversacional Nexus CA (Web App)
- **FastAPI + Jinja2**: Aplicação assíncrona leve e de alta performance.
- **Gemini Data Analytics API**: Tradução automática de perguntas em linguagem natural para consultas SQL no BigQuery.
- **Visualização Nativa Vega-Lite**: Renderização instantânea de gráficos interativos (barras, linhas, distribuição) gerados diretamente pelo agente.
- **Segurança & Proteção de Custo**: Modal de autenticação e rate limiting configurável por IP (ex: 3 requisições/minuto).

---

## 📂 Estrutura do Repositório

```text
├── README.md                           # Documentação completa do projeto
├── Dockerfile                          # Build da aplicação Web para Cloud Run
├── requirements.txt                    # Dependências principais
├── scripts/
│   ├── 01_setup_gcp_environment.sh     # Script Bash de ativação de APIs e Dataset
│   └── ingest_excel_to_bigquery.py     # Pipeline de ingestão, sanitização e carga BigQuery
│
├── sql/
│   ├── 01_cruzamento_vetor_sap.sql     # View analítica de divergências de valores
│   ├── 02_gemini_anomalias.sql         # Criação de modelo Gemini e auditoria de sobrepreço
│   └── 03_correlacao_gemini.sql         # Pipeline de De-Para semântico otimizado com IA
│
├── notebooks/
│   └── pipeline_cs_frotas_bigquery.ipynb # Notebook interativo de exploração e testes
│
└── web_app/
    ├── app.py                          # Servidor FastAPI e integração com Data Agent
    ├── requirements.txt                # Dependências do Web App
    ├── static/                         # Arquivos estáticos
    └── templates/
        └── index.html                  # Interface completa com tema CS Frotas e Vega-Lite
```

---

## 🚀 Guia de Execução Passo a Passo

### 1. Pré-requisitos
- Conta no **Google Cloud Platform** com permissões no **BigQuery** e **Vertex AI**.
- **Google Cloud SDK (`gcloud`)** instalado e autenticado:
  ```bash
  gcloud auth login
  gcloud auth application-default login
  ```
- **Python 3.10+** instalado.

---

### 2. Configurar o Ambiente no GCP (BigQuery, Vertex AI e Cloud Storage)
Execute o script de inicialização para habilitar as APIs, criar o dataset no BigQuery e o bucket no Google Cloud Storage:

```bash
chmod +x scripts/01_setup_gcp_environment.sh
./scripts/01_setup_gcp_environment.sh "SEU_PROJETO_GCP" "US" "SEU_BUCKET_GCS"
```

---

### 3. Ingestão e Sanitização das Bases (Via Google Cloud Storage ou Local)

#### Opção A: Ingestão Direta a partir do Google Cloud Storage (Recomendado)
Faça o upload das planilhas para o bucket criado no Cloud Storage:

```bash
# 1. Enviar os arquivos para o Cloud Storage
gcloud storage cp "caminho/para/Manutenção - Relatório de Item VETOR.xlsx" gs://SEU_BUCKET_GCS/
gcloud storage cp "caminho/para/Manutenção - Relatório de Estoque SAP.xlsx" gs://SEU_BUCKET_GCS/

# 2. Executar a ingestão apontando para o Cloud Storage
export GCP_PROJECT_ID="SEU_PROJETO_GCP"
export BQ_DATASET_ID="cs_frotas_data"
export GCS_BUCKET="SEU_BUCKET_GCS"

python3 scripts/ingest_excel_to_bigquery.py
```

*Também é possível passar URIs customizadas no GCS via variáveis de ambiente:*
```bash
export GCS_VETOR_URI="gs://SEU_BUCKET_GCS/pastas/Manutenção - Relatório de Item VETOR.xlsx"
export GCS_SAP_URI="gs://SEU_BUCKET_GCS/pastas/Manutenção - Relatório de Estoque SAP.xlsx"
```

#### Opção B: Ingestão Local
Se preferir executar a partir do disco local:

```bash
export GCP_PROJECT_ID="SEU_PROJETO_GCP"
export BQ_DATASET_ID="cs_frotas_data"
export FILE_VETOR="data/Manutenção - Relatório de Item VETOR.xlsx"
export FILE_SAP="data/Manutenção - Relatório de Estoque SAP.xlsx"

python3 scripts/ingest_excel_to_bigquery.py
```

### 4. Execução Interativa no BigQuery Studio / BigQuery Notebooks

Você pode executar todo o pipeline Python e SQL diretamente no **[BigQuery Studio (Notebooks no BigQuery)](https://docs.cloud.google.com/bigquery/docs/create-notebooks?hl=pt)**, integrado com o Colab Enterprise:

1. **Acesse o Console do BigQuery**:
   - No Google Cloud Console, navegue até **BigQuery** > **BigQuery Studio**.
2. **Criar ou Importar Notebook**:
   - Clique em **+ (Criar)** > **Notebook Python** ou faça o upload do arquivo `notebooks/pipeline_cs_frotas_bigquery.ipynb`.
   - Conecte a um runtime do BigQuery Studio / Colab Enterprise (as credenciais IAM do GCP são injetadas automaticamente na sessão).
3. **Execução das Células**:
   - O notebook realiza o download por streaming direto dos buckets no Google Cloud Storage (`gs://...`).
   - Aplica a sanitização e regras de negócio com Pandas.
   - Escreve as tabelas nativas no BigQuery.
   - Executa consultas SQL analíticas e inferências com o modelo **Gemini 3.7 Flash** via `%%bigquery`.

---

### 5. Criação dos Modelos de IA e Consultas SQL no BigQuery (Console ou CLI)
Se preferir executar os scripts SQL diretamente pelo BigQuery Console ou via CLI `bq`:

```bash
# 1. View de cruzamento inicial
bq query --use_legacy_sql=false < sql/01_cruzamento_vetor_sap.sql

# 2. Modelo remoto Gemini e análise de anomalias
bq query --use_legacy_sql=false < sql/02_gemini_anomalias.sql

# 3. De-Para Semântico e Catálogo Unificado
bq query --use_legacy_sql=false < sql/03_correlacao_gemini.sql
```

---

### 6. Executando o Web App Localmente

```bash
cd web_app
pip install -r requirements.txt

export GCP_PROJECT_ID="SEU_PROJETO_GCP"
export GCP_LOCATION="us"
export DATA_AGENT_ID="seu_agent_id_ou_padrao"
export APP_ACCESS_KEY="sua_chave_de_acesso"

uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

Acesse no navegador: `http://localhost:8080`

---

### 7. Deploy no Google Cloud Run (Serverless)

Para publicar a aplicação em produção no Cloud Run:

```bash
# Build e Deploy direto no Cloud Run
gcloud run deploy nexus-ca-app \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID="SEU_PROJETO_GCP",GCP_LOCATION="us",APP_ACCESS_KEY="mvpcskey"
```

---

## 🔒 Segurança e Governança

- **Adequação LGPD**: Dicionários de metadados identificam dados pessoais e sensíveis para tratamento adequado.
- **Controle de Custos**: Otimização por amostragem e desduplicação por hash previne execuções redundantes de LLM.
- **Isolamento de Credenciais**: Utilização de Application Default Credentials (ADC) e Service Accounts gerenciadas do GCP.

---

## 👥 Autoria & Créditos

Desenvolvido por **Luana Costa** no âmbito da iniciativa **CS Frotas — Inovação com Inteligência Artificial & Google Cloud**.
