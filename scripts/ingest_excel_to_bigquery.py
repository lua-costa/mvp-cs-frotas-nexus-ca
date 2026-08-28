import os
import re
import pandas as pd
import openpyxl
from google.cloud import bigquery

# Configurações do Projeto
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "cs-demo-2026")
DATASET_ID = os.getenv("BQ_DATASET_ID", "cs_frotas_data")

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

def load_vetor_data(file_path):
    print(f"📖 Lendo arquivo VETOR: {file_path}...")
    df = pd.read_excel(file_path, sheet_name="Relatorio_de_Item", dtype=str)
    print(f"Linhas carregadas do VETOR: {len(df)}, Colunas originais: {len(df.columns)}")
    
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
        if any(k in col for k in ["valor", "preco", "desconto", "variacao", "variacao_pct", "pct_desconto", "reducao", "orçamento", "orcamento"]):
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")
        elif any(k in col for k in ["quantidade", "idade", "km", "dia", "semana", "mes", "ano"]):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- REGRAS DE NEGÓCIO E SANITIZAÇÃO DE DADOS ---
    # 1. Filtro de exclusão oculto: desconsiderar ordens reprovadas ou sem item
    status_col = [c for c in df.columns if "status" in c]
    if status_col:
        df = df[~df[status_col[0]].astype(str).str.upper().str.contains("REPROVAD", na=False)].copy()
    
    # 2. Correção de sinais invertidos: Redução de Orçamento deve ser positiva
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
    
    print(f"🚀 Enviando {len(df)} registros SANITIZADOS do VETOR para o BigQuery: {table_ref}...")
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True
    )
    job = bq_client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()
    print("✅ Tabela `relatorio_item_vetor` criada e populada com regras de sanitização aplicadas!")

def load_sap_data(file_path):
    print(f"📖 Lendo arquivo SAP: {file_path}...")
    df = pd.read_excel(file_path, sheet_name="MB52", dtype=str)
    print(f"Linhas carregadas do SAP: {len(df)}, Colunas originais: {len(df.columns)}")
    
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
            df[col] = pd.to_numeric(df[col].str.replace(",", "."), errors="coerce")

    bq_client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.relatorio_estoque_sap_mb52"
    
    print(f"🚀 Enviando {len(df)} registros do SAP para o BigQuery: {table_ref}...")
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True
    )
    job = bq_client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()
    print("✅ Tabela `relatorio_estoque_sap_mb52` criada e populada com sucesso!")

def load_dicionarios(file_vetor, file_sap):
    bq_client = bigquery.Client(project=PROJECT_ID)
    
    # Dicionário VETOR
    df_dic_vetor = pd.read_excel(file_vetor, sheet_name="Dicionario_de_Dados", dtype=str)
    df_dic_vetor.columns = [sanitize_column_name(c, idx) for idx, c in enumerate(df_dic_vetor.columns)]
    tvetor = f"{PROJECT_ID}.{DATASET_ID}.dicionario_dados_vetor"
    job1 = bq_client.load_table_from_dataframe(
        df_dic_vetor, tvetor, 
        job_config=bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE, autodetect=True)
    )
    job1.result()
    print("✅ Tabela `dicionario_dados_vetor` criada e populada!")

    # Dicionário SAP
    df_dic_sap = pd.read_excel(file_sap, sheet_name="Dicionario_de_Dados", dtype=str)
    df_dic_sap.columns = [sanitize_column_name(c, idx) for idx, c in enumerate(df_dic_sap.columns)]
    tsap = f"{PROJECT_ID}.{DATASET_ID}.dicionario_dados_sap"
    job2 = bq_client.load_table_from_dataframe(
        df_dic_sap, tsap, 
        job_config=bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE, autodetect=True)
    )
    job2.result()
    print("✅ Tabela `dicionario_dados_sap` criada e populada!")

if __name__ == "__main__":
    file_vetor = os.getenv("FILE_VETOR", "data/Manutenção - Relatório de Item VETOR.xlsx")
    file_sap = os.getenv("FILE_SAP", "data/Manutenção - Relatório de Estoque SAP.xlsx")
    
    load_vetor_data(file_vetor)
    load_sap_data(file_sap)
    load_dicionarios(file_vetor, file_sap)
    print("🎉 Processo concluído! Todas as tabelas foram carregadas no BigQuery.")
