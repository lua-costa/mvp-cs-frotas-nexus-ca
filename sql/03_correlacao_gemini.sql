-- ====================================================================
-- Script: Correlacionar Peças/Produtos VETOR x SAP com Gemini (BigQuery ML)
-- Otimização: Desduplicação de catálogos para redução de custos e quotas
-- Projeto: your-gcp-project-id
-- Dataset: cs_frotas_data
-- ====================================================================

-- --------------------------------------------------------------------
-- ETAPA 1: Criar tabela de Descrições/Itens ÚNICOS do Vetor
-- --------------------------------------------------------------------
CREATE OR REPLACE TABLE `cs_frotas_data.tb_vetor_descricoes_unicas` AS
SELECT
  FARM_FINGERPRINT(TRIM(UPPER(`descrição`))) AS hash_descricao_vetor,
  TRIM(UPPER(`descrição`)) AS descricao_vetor_limpa,
  ANY_VALUE(`tipo_de_peça`) AS tipo_peca_exemplo,
  COUNT(*) AS total_ocorrencias
FROM `cs_frotas_data.relatorio_item_vetor`
WHERE `descrição` IS NOT NULL AND TRIM(`descrição`) != ''
GROUP BY 1, 2;

-- --------------------------------------------------------------------
-- ETAPA 2: Criar tabela de Materiais ÚNICOS do SAP MB52
-- --------------------------------------------------------------------
CREATE OR REPLACE TABLE `cs_frotas_data.tb_sap_materiais_unicos` AS
SELECT
  TRIM(material) AS codigo_sap,
  TRIM(UPPER(`texto_breve_de_material`)) AS descricao_sap_limpa,
  COUNT(*) AS total_registros_estoque
FROM `cs_frotas_data.relatorio_estoque_sap_mb52`
WHERE `texto_breve_de_material` IS NOT NULL AND TRIM(`texto_breve_de_material`) != ''
GROUP BY 1, 2;

-- --------------------------------------------------------------------
-- ETAPA 3: Inferência Gemini APENAS sobre o Catálogo Desduplicado (De-Para)
-- --------------------------------------------------------------------
CREATE OR REPLACE TABLE `cs_frotas_data.tb_depara_vetor_sap_gemini` AS
SELECT
  vetor.hash_descricao_vetor,
  vetor.descricao_vetor_limpa,
  ml_generate_text_result AS analise_correlacao_gemini
FROM
  ML.GENERATE_TEXT(
    MODEL `cs_frotas_data.gemini_flash_model`,
    (
      SELECT
        CONCAT(
          'Você é um especialista em catálogo de peças automotivas e manutenção de frotas.\n',
          'Sua tarefa é analisar a descrição de um item do sistema VETOR e encontrar o melhor correspondente no catálogo SAP MB52.\n\n',
          'ITEM DO VETOR:\n',
          '- Descrição: ', IFNULL(descricao_vetor_limpa, ''), '\n\n',
          'Amostra de Materiais do SAP para Comparação:\n',
          (
            SELECT STRING_AGG(CONCAT('[Código SAP: ', codigo_sap, ' | Descrição: ', descricao_sap_limpa, ']'), '\n')
            FROM `cs_frotas_data.tb_sap_materiais_unicos`
            LIMIT 50
          ),
          '\n\nResponda estritamente em formato JSON com os campos:\n',
          '{\n',
          '  "codigo_sap_correspondente": "código SAP ou NENHUM",\n',
          '  "grau_confianca": "ALTO/MEDIO/BAIXO/NENHUM",\n',
          '  "justificativa": "motivo da correspondência técnica"\n',
          '}'
        ) AS prompt,
        hash_descricao_vetor,
        descricao_vetor_limpa
      FROM `cs_frotas_data.tb_vetor_descricoes_unicas`
    ),
    STRUCT(
      0.1 AS temperature,
      300 AS max_output_tokens
    )
  );

-- --------------------------------------------------------------------
-- ETAPA 4: JOIN Tradicional SQL para Reassentar o De-Para nos Fatos Brutos
-- --------------------------------------------------------------------
CREATE OR REPLACE TABLE `cs_frotas_data.tb_cruzamento_vetor_sap_consolidado` AS
SELECT
  v.*,
  depara.analise_correlacao_gemini,
  JSON_VALUE(depara.analise_correlacao_gemini, '$.codigo_sap_correspondente') AS codigo_sap_mapeado,
  JSON_VALUE(depara.analise_correlacao_gemini, '$.grau_confianca') AS grau_confianca_gemini
FROM `cs_frotas_data.relatorio_item_vetor` v
LEFT JOIN `cs_frotas_data.tb_vetor_descricoes_unicas` u
  ON FARM_FINGERPRINT(TRIM(UPPER(v.`descrição`))) = u.hash_descricao_vetor
LEFT JOIN `cs_frotas_data.tb_depara_vetor_sap_gemini` depara
  ON u.hash_descricao_vetor = depara.hash_descricao_vetor;

