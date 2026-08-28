import io
import os
import re
import pandas as pd
import openpyxl
from google.cloud import bigquery, storage

# ==============================================================================
# Configurações do Ambiente e Parâmetros
# ==============================================================================
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "your-gcp-project-id")
DATASET_ID = os.getenv("BQ_DATASET_ID", "cs_frotas_data")
GCS_BUCKET = os.getenv("GCS_BUCKET", "")

# Cache em memória para evitar múltiplos downloads do mesmo arquivo GCS
_FILE_BYTES_CACHE = {}

def get_file_source(uri_or_path: str):
    """Obtém o arquivo a partir do Google Cloud Storage (gs://) ou do disco local."""
    # 1. Se já está em cache
    if uri_or_path in _FILE_BYTES_CACHE:
        return io.BytesIO(_FILE_BYTES_CACHE[uri_or_path])

    # 2. Se for uma URI do Cloud Storage (gs://...)
    if uri_or_path.startswith("gs://"):
        print(f"📥 Baixando arquivo do Google Cloud Storage: {uri_or_path}...")
        path_without_prefix = uri_or_path[5:]
        bucket_name, blob_name = path_without_prefix.split("/", 1)
        
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        if not blob.exists():
            raise FileNotFoundError(f"Objeto não encontrado no GCS: {uri_or_path}")
            
        content = blob.download_as_bytes()
        _FILE_BYTES_CACHE[uri_or_path] = content
        print(f"✅ Download GCS concluído ({len(content) / (1024*1024):.2f} MB)")
        return io.BytesIO(content)

    # 3. Se for caminho local
    if not os.path.exists(uri_or_path):
        raise FileNotFoundError(f"Arquivo local não encontrado: {uri_or_path}")
    
    return uri_or_path

def sanitize_column_name(col, idx):
    """Sanitiza nomes de colunas para adequar às regras de nomeação do BigQuery."""
    if not col or str(col).strip() == "" or str(col) == "None":
        return f"coluna_{idx}"
    s = str(col).strip()
    s = s.replace("ª", "").replace("º", "").replace("%", "pct").replace("/", "_").replace(".", "")
    s = re.sub(r"[^\w\s]", "_", s)
    s = re.sub(r"\s+", "_", s).lower()
    if re.match(r"^\d", s):
        s = "c_" + s
    return s

def load_vetor_data(file_source):
    """Carrega e sanitiza os dados do relatório de itens do sistema VETOR."""
    print(f"📖 Lendo aba 'Relatorio_de_Item' do VETOR...")
    source = get_file_source(file_source)
    df = pd.read_excel(source, sheet_name="Relatorio_de_Item", dtype=str)
    print(f"Linhas carregadas do VETOR: {len(df):,}, Colunas originais: {len(df.columns)}")
    
    # Sanitização dos nomes de colunas
    new_cols = []
    seen = {}
    for idx, c in enumerate(df.columns):
        sc = sanitize_column_name(c, idx)
        if sc in seen:
            seen[sc] += 1
            sc = f"{sc}_{seen[sc]}"
        else:
            seen[sc] = 0
        new_cols.append(sc)
    df.columns = new_cols
    
    # Tipagem numérica para campos de valores, quantidades e datas
    for col in df.columns:
        if any(k in col for k in ["valor", "preco", "desconto", "variacao", "variacao_pct", "pct_desconto", "reducao", "orçamento", "orcamento"]):
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")
        elif any(k in col for k in ["quantidade", "idade", "km", "dia", "semana", "mes", "ano"]):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- REGRAS DE NEGÓCIO E SANITIZAÇÃO DE DADOS ---
    # 1. Filtro de exclusão oculto: desconsiderar ordens reprovadas ou sem item
    status_col = [c for c in df.columns if "status" in c]
    if status_col:
        df = df[~df[status_col[0]].astype(str).str.upper().str.contains("REPROVAD", na=False)].copy()
    
    # 2. Correção de sinais: Redução de Orçamento deve ser positiva
    reducao_cols = [c for c in df.columns if "reducao" in c or "orcamento" in c or "orçamento" in c]
    for rcol in reducao_cols:
        if rcol in df.columns and pd.api.types.is_numeric_dtype(df[rcol]):
            df[rcol] = df[rcol].abs()

    # 3. Tratamento de Variação % (ex: 0.07 -> 7%)
    pct_cols = [c for c in df.columns if "pct" in c or "variacao" in c or "variação" in c]
    for pcol in pct_cols:
        if pcol in df.columns and pd.api.types.is_numeric_dtype(df[pcol]):
            df[f"{pcol}_percentual"] = df[pcol] * 100.0

    # 4. Evitar duplicidade de cobrança de avaria (desconsiderar valor_cliente duplicado se existir valor_total_ca)
    v_ca = [c for c in df.columns if "valor_total_ca" in c]
    v_cli = [c for c in df.columns if "valor_cliente" in c]
    if v_ca and v_cli:
        df["valor_avaria_apurado"] = df[v_ca[0]].fillna(df[v_cli[0]])
    elif v_ca:
        df["valor_avaria_apurado"] = df[v_ca[0]]

    bq_client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.relatorio_item_vetor"
    
    print(f"🚀 Enviando {len(df):,} registros sanitizados do VETOR para o BigQuery: {table_ref}...")
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True
    )
    job = bq_client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()
    print("✅ Tabela `relatorio_item_vetor` criada e populada com sucesso!")

def load_sap_data(file_source):
    """Carrega e sanitiza os dados do estoque SAP MB52."""
    print(f"📖 Lendo aba 'MB52' do SAP...")
    source = get_file_source(file_source)
    df = pd.read_excel(source, sheet_name="MB52", dtype=str)
    print(f"Linhas carregadas do SAP: {len(df):,}, Colunas originais: {len(df.columns)}")
    
    new_cols = []
    seen = {}
    for idx, c in enumerate(df.columns):
        sc = sanitize_column_name(c, idx)
        if sc in seen:
            seen[sc] += 1
            sc = f"{sc}_{seen[sc]}"
        else:
            seen[sc] = 0
        new_cols.append(sc)
    df.columns = new_cols
    
    for col in df.columns:
        if any(k in col for k in ["val", "utilizacao", "transito"]):
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")

    bq_client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.relatorio_estoque_sap_mb52"
    
    print(f"🚀 Enviando {len(df):,} registros do SAP para o BigQuery: {table_ref}...")
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True
    )
    job = bq_client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()
    print("✅ Tabela `relatorio_estoque_sap_mb52` criada e populada com sucesso!")

def load_dicionarios(file_vetor, file_sap):
    """Carrega os dicionários de metadados do VETOR e do SAP."""
    bq_client = bigquery.Client(project=PROJECT_ID)
    
    # 1. Dicionário VETOR
    print("📖 Lendo dicionário de dados do VETOR...")
    source_vetor = get_file_source(file_vetor)
    df_dic_vetor = pd.read_excel(source_vetor, sheet_name="Dicionario_de_Dados", dtype=str)
    df_dic_vetor.columns = [sanitize_column_name(c, idx) for idx, c in enumerate(df_dic_vetor.columns)]
    
    tvetor = f"{PROJECT_ID}.{DATASET_ID}.dicionario_dados_vetor"
    job1 = bq_client.load_table_from_dataframe(
        df_dic_vetor, tvetor, 
        job_config=bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE, autodetect=True)
    )
    job1.result()
    print("✅ Tabela `dicionario_dados_vetor` criada e populada!")

    # 2. Dicionário SAP
    print("📖 Lendo dicionário de dados do SAP...")
    source_sap = get_file_source(file_sap)
    df_dic_sap = pd.read_excel(source_sap, sheet_name="Dicionario_de_Dados", dtype=str)
    df_dic_sap.columns = [sanitize_column_name(c, idx) for idx, c in enumerate(df_dic_sap.columns)]
    
    tsap = f"{PROJECT_ID}.{DATASET_ID}.dicionario_dados_sap"
    job2 = bq_client.load_table_from_dataframe(
        df_dic_sap, tsap, 
        job_config=bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE, autodetect=True)
    )
    job2.result()
    print("✅ Tabela `dicionario_dados_sap` criada e populada!")

if __name__ == "__main__":
    # Resolução dinâmica: aceita URIs diretas gs:// ou caminhos locais
    if GCS_BUCKET:
        default_vetor = f"gs://{GCS_BUCKET}/Manutenção - Relatório de Item VETOR.xlsx"
        default_sap = f"gs://{GCS_BUCKET}/Manutenção - Relatório de Estoque SAP.xlsx"
    else:
        default_vetor = "data/Manutenção - Relatório de Item VETOR.xlsx"
        default_sap = "data/Manutenção - Relatório de Estoque SAP.xlsx"

    file_vetor = os.getenv("FILE_VETOR", os.getenv("GCS_VETOR_URI", default_vetor))
    file_sap = os.getenv("FILE_SAP", os.getenv("GCS_SAP_URI", default_sap))
    
    print("=" * 70)
    print(f"🚀 INICIANDO INGESTÃO NO BIGQUERY ({PROJECT_ID}.{DATASET_ID})")
    print(f"📂 Origem VETOR: {file_vetor}")
    print(f"📂 Origem SAP:   {file_sap}")
    print("=" * 70)

    load_vetor_data(file_vetor)
    load_sap_data(file_sap)
    load_dicionarios(file_vetor, file_sap)
    
    print("=" * 70)
    print("🎉 Ingestão concluída com sucesso! Todas as tabelas estão prontas no BigQuery.")
    print("=" * 70)
