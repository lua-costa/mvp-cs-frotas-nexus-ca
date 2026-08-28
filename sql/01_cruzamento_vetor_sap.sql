-- ====================================================================
-- Script: Cruzamento de Estoque e Valores VETOR x SAP (MB52)
-- Projeto: your-gcp-project-id
-- Dataset: cs_frotas_data
-- ====================================================================

-- Visão Consolidada de Peças e Valores entre Vetor e SAP MB52
CREATE OR REPLACE VIEW `cs_frotas_data.vw_cruzamento_vetor_sap` AS
SELECT
  v.`código_item_vetor` AS codigo_item_vetor,
  v.`código_item_sap` AS codigo_item_sap_ref,
  s.material AS codigo_material_sap,
  s.`texto_breve_de_material` AS descricao_sap,
  
  -- Valores e Quantidades
  SAFE_CAST(v.quantidade AS NUMERIC) AS qtd_vetor,
  SAFE_CAST(s.`utilização_livre` AS NUMERIC) AS qtd_sap_livre,
  SAFE_CAST(v.valor_total AS NUMERIC) AS valor_total_vetor,
  SAFE_CAST(s.valutilizlivre AS NUMERIC) AS valor_total_sap,
  
  -- Cálculo de Divergência de Valores
  (SAFE_CAST(v.valor_total AS NUMERIC) - SAFE_CAST(s.valutilizlivre AS NUMERIC)) AS dif_valor,
  
  -- Indicador de Consistência
  CASE 
    WHEN s.material IS NULL THEN 'Presente Apenas no Vetor'
    WHEN v.`código_item_vetor` IS NULL THEN 'Presente Apenas no SAP'
    WHEN ABS(SAFE_CAST(v.valor_total AS NUMERIC) - SAFE_CAST(s.valutilizlivre AS NUMERIC)) > 100 THEN 'Divergência Relevante'
    ELSE 'Consistente'
  END AS status_divergencia

FROM `cs_frotas_data.relatorio_item_vetor` v
FULL OUTER JOIN `cs_frotas_data.relatorio_estoque_sap_mb52` s
  ON v.`código_item_sap` = s.material;
