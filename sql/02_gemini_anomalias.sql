-- ====================================================================
-- Script: Modelo Gemini no BigQuery ML para Análise de Sobrepreço/Anomalias
-- Projeto: cs-demo-2026
-- Dataset: cs_frotas_data
-- ====================================================================

-- 1. Criação do Modelo Gemini Remoto no BigQuery ML
CREATE OR REPLACE MODEL `cs-demo-2026.cs_frotas_data.gemini_flash_model`
REMOTE WITH CONNECTION DEFAULT
OPTIONS(endpoint = 'gemini-1.5-flash');

-- 2. Exemplo de Prompt para Identificação de Divergências de Peças/Valores com AI
SELECT
  ml_generate_text_result AS analise_gemini,
  codigo_item_vetor,
  descricao_vetor,
  valor_total_vetor,
  valor_total_sap
FROM
  ML.GENERATE_TEXT(
    MODEL `cs-demo-2026.cs_frotas_data.gemini_flash_model`,
    (
      SELECT
        CONCAT(
          'Atue como um auditor de frota e suprimentos. Analise o item abaixo e explique se a divergência entre o sistema VETOR e SAP representa risco de sobrepreço ou inconsistência de cadastro:\n',
          'Item Vetor: ', IFNULL(descricao_vetor, 'N/A'), ' | Valor Vetor: R$ ', CAST(IFNULL(valor_total_vetor, 0) AS STRING), '\n',
          'Item SAP: ', IFNULL(descricao_sap, 'N/A'), ' | Valor SAP: R$ ', CAST(IFNULL(valor_total_sap, 0) AS STRING), '\n',
          'Diferença de Valor: R$ ', CAST(IFNULL(dif_valor, 0) AS STRING), '\n',
          'Status: ', status_divergencia
        ) AS prompt,
        codigo_item_vetor,
        descricao_vetor,
        valor_total_vetor,
        valor_total_sap
      FROM `cs-demo-2026.cs_frotas_data.vw_cruzamento_vetor_sap`
      WHERE status_divergencia = 'Divergência Relevante'
      LIMIT 10
    ),
    STRUCT(0.2 AS temperature, 500 AS max_output_tokens)
  );
