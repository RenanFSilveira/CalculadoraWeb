import pandas as pd
import numpy as np
from datetime import datetime
import os

class CalculadoraMargemLucroComPedalada:
    """
    Sistema de margem de lucro com tratamento de 'pedaladas' (falsas vendas no crédito)
    """

    def __init__(self, arquivo_custos_variaveis="Variaveis_completo.csv", arquivo_custos_fixos="Fixos.csv"):
        self.arquivo_custos_variaveis = arquivo_custos_variaveis
        self.arquivo_custos_fixos = arquivo_custos_fixos

    def processar_relatorio_mensal(self, arquivo_vendas, mes_referencia=None, 
                                 valor_pedaladas=0, salvar_resultado=True):
        """
        Processa um relatório mensal com tratamento de pedaladas

        Args:
            arquivo_vendas: Path para arquivo Excel/CSV de vendas
            mes_referencia: String identificando o mês (ex: "2024-09")
            valor_pedaladas: Valor total das pedaladas do mês (R$)
            salvar_resultado: Boolean para salvar CSV com resultado

        Returns:
            tuple: (resumo_financeiro, detalhamento_produtos)
        """

        print(f"📊 Processando relatório: {arquivo_vendas}")
        
        # 1. Carregar dados
        if arquivo_vendas.endswith('.xls'):
            try:
                vendas_df = pd.read_excel(arquivo_vendas, sheet_name=0, engine='xlrd')
            except Exception as e:
                print(f"⚠️ Erro ao ler .xls com xlrd: {e}. Tentando como HTML...")
                try:
                    # Tenta ler como HTML (comum em sistemas legados que exportam HTML com extensão .xls)
                    # read_html retorna uma lista de dataframes
                    dfs = pd.read_html(arquivo_vendas, decimal=',', thousands='.', header=0)
                    if dfs:
                        vendas_df = dfs[0] # Pega a primeira tabela
                    else:
                        raise ValueError("Nenhuma tabela encontrada no arquivo HTML/.xls")
                except Exception as e_html:
                     raise ValueError(f"Falha ao ler arquivo .xls (tanto como Excel quanto HTML): {e_html}")

        elif arquivo_vendas.endswith('.xlsx'):
            vendas_df = pd.read_excel(arquivo_vendas, sheet_name=0, engine='openpyxl')
        else:
            vendas_df = pd.read_csv(arquivo_vendas)

        custos_var_df = pd.read_csv(self.arquivo_custos_variaveis)
        custos_fix_df = pd.read_csv(self.arquivo_custos_fixos)

        # 2. Limpar e validar dados de vendas (MOVIDO PARA ANTES DA DETECÇÃO)
        vendas_clean = self._limpar_dados_vendas(vendas_df)

        # --- DETECÇÃO AUTOMÁTICA DE PEDALADA (Produção Cozinha Industrial) ---
        # Identifica itens que devem ser tratados como pedalada e removidos da análise de produtos
        mask_pedalada_auto = vendas_clean['Produto'].astype(str).str.contains("Produção Cozinha Industrial", case=False, na=False)
        
        # Calcular taxas sobre esses itens ANTES de remover
        # Taxas: Débito 2%, Crédito/Outros 3%, Dinheiro 0%
        df_pedalada = vendas_clean[mask_pedalada_auto].copy()
        taxa_variavel_pedalada_auto = 0.0
        
        if not df_pedalada.empty:
            taxa_debito = (df_pedalada['Débito'] * 0.02).sum()
            taxa_credito = (df_pedalada['Crédito'] * 0.03).sum()
            taxa_cashless = (df_pedalada['Cashless'] * 0.03).sum()
            taxa_voucher = (df_pedalada['Voucher'] * 0.03).sum()
            taxa_divisao = (df_pedalada['Divisão'] * 0.03).sum()
            taxa_outros = (df_pedalada['Outros'] * 0.03).sum()
            
            taxa_variavel_pedalada_auto = taxa_debito + taxa_credito + taxa_cashless + taxa_voucher + taxa_divisao + taxa_outros
            print(f"💳 Taxa variável sobre 'Produção Cozinha Industrial': R$ {taxa_variavel_pedalada_auto:.2f}")

        valor_pedalada_auto = vendas_clean.loc[mask_pedalada_auto, 'Valor'].sum()
        
        # Remove esses itens do dataframe principal para não sujar a análise de produtos
        if valor_pedalada_auto > 0:
            print(f"⚠️  Detectado 'Produção Cozinha Industrial': R$ {valor_pedalada_auto:.2f} (Convertido para Pedalada)")
            vendas_clean = vendas_clean[~mask_pedalada_auto].copy()
            
        # Soma ao valor informado manualmente pelo usuário
        valor_pedaladas_total = valor_pedaladas + valor_pedalada_auto

        if valor_pedaladas_total > 0:
            print(f"⚠️  Pedaladas totais (Manual + Auto): R$ {valor_pedaladas_total:,.2f}")

        # 3. Verificar produtos sem custo cadastrado
        self._verificar_produtos_sem_custo(vendas_clean, custos_var_df)

        # 4. Fazer merge com custos variáveis
        resultado = vendas_clean.merge(custos_var_df, on='Produto', how='left')
        resultado['Custo_Insumo_Unitario'] = resultado['Custo_Insumo_Unitario'].fillna(0)

        # 5. Calcular métricas por produto E taxas por forma de pagamento
        resultado = self._calcular_metricas_produto_e_taxas(resultado)

        # 6. Calcular totais e resumo financeiro (COM tratamento de pedaladas)
        resumo = self._calcular_resumo_financeiro_com_pedaladas(
            resultado, custos_fix_df, mes_referencia, valor_pedaladas_total, valor_pedalada_auto, taxa_variavel_pedalada_auto
        )
        
        # Adiciona info da detecção automática ao resumo para exibir no front
        resumo['valor_pedalada_auto'] = valor_pedalada_auto
        
        # 8. Novos KPIs (Break-even e Comparativos)
        self._calcular_kpis_avancados(
            resumo, 
            resumo.get('custos_fixos_total', 0), 
            resumo.get('margem_bruta', 0), 
            resumo.get('receita_bruta_real', 0)
        )

        # 7. Salvar resultado se solicitado
        if salvar_resultado:
            self._salvar_resultado(resultado, resumo, mes_referencia, valor_pedaladas_total)

        # 8. Exibir relatório
        self._exibir_relatorio(resumo, resultado, valor_pedaladas_total)

        return resumo, resultado

    def _limpar_dados_vendas(self, vendas_df):
        """Limpa e valida dados do arquivo de vendas"""

        # Remover linhas de totais e vazias
        vendas_clean = vendas_df[~vendas_df['Produto'].isna()].copy()
        vendas_clean = vendas_clean[vendas_clean['Categoria'] != 'Total Geral']
        vendas_clean = vendas_clean.dropna(subset=['Produto'])

        # Converter colunas numéricas (incluindo formas de pagamento)
        numeric_cols = ['Quantidade', 'Cashless', 'Débito', 'Crédito', 'Dinheiro', 
                       'Voucher', 'Divisão', 'Outros', 'Desconto', 'Valor']

        for col in numeric_cols:
            if col in vendas_clean.columns:
                vendas_clean[col] = pd.to_numeric(vendas_clean[col], errors='coerce')

        # Preencher NaN com 0 para cálculos
        for col in numeric_cols:
            if col in vendas_clean.columns:
                vendas_clean[col] = vendas_clean[col].fillna(0)

        print(f"✅ Dados limpos: {len(vendas_clean)} produtos processados")
        return vendas_clean

    def _verificar_produtos_sem_custo(self, vendas_clean, custos_var_df):
        """Verifica e alerta sobre produtos sem custo cadastrado"""

        produtos_vendas = set(vendas_clean['Produto'].unique())
        produtos_custos = set(custos_var_df['Produto'].unique())
        produtos_sem_custo = produtos_vendas - produtos_custos

        if produtos_sem_custo:
            print(f"\\n⚠️  ATENÇÃO: {len(produtos_sem_custo)} produto(s) sem custo cadastrado:")
            for produto in sorted(produtos_sem_custo):
                qtd = vendas_clean[vendas_clean['Produto'] == produto]['Quantidade'].sum()
                print(f"   - {produto} (Qtd vendida: {qtd})")
            print("   💡 Estes produtos terão custo = 0 no cálculo\\n")

    def _calcular_metricas_produto_e_taxas(self, resultado):
        """Calcula métricas financeiras por produto E taxas específicas por forma de pagamento"""

        # Calcular custos de insumos
        resultado['Custo_Total_Insumos'] = resultado['Quantidade'] * resultado['Custo_Insumo_Unitario']

        # Calcular taxas por forma de pagamento por produto
        # Dinheiro = 0% taxa
        # Débito = 2% taxa
        # Crédito = 3% taxa
        # Cashless, Voucher, Divisão, Outros = assumir como crédito (3%)

        resultado['Taxa_Debito'] = resultado['Débito'] * 0.02
        resultado['Taxa_Credito'] = resultado['Crédito'] * 0.03
        resultado['Taxa_Cashless'] = resultado['Cashless'] * 0.03
        resultado['Taxa_Voucher'] = resultado['Voucher'] * 0.03
        resultado['Taxa_Divisao'] = resultado['Divisão'] * 0.03
        resultado['Taxa_Outros'] = resultado['Outros'] * 0.03

        # Taxa total por produto
        resultado['Taxa_Total_Produto'] = (resultado['Taxa_Debito'] + 
                                         resultado['Taxa_Credito'] + 
                                         resultado['Taxa_Cashless'] + 
                                         resultado['Taxa_Voucher'] + 
                                         resultado['Taxa_Divisao'] + 
                                         resultado['Taxa_Outros'])

        # Receita líquida por produto (descontando insumos e taxas)
        resultado['Receita_Liquida_Produto'] = (resultado['Valor'] - 
                                              resultado['Custo_Total_Insumos'] - 
                                              resultado['Taxa_Total_Produto'])

        # Margem unitária
        # Se o Valor for 0, a Margem Unitária é zerada, senão calcula normalmente.
        resultado['Margem_Unitaria'] = np.where(
            resultado['Valor'] == 0,
            0,  # Valor se a condição for VERDADEIRA (Valor = 0)
            resultado['Receita_Liquida_Produto'] / resultado['Quantidade']  # Valor se a condição for FALSA (Valor > 0)
        )

        # Percentual de margem por produto
        # Se o Valor for 0, o Percentual de Margem é zerado, senão calcula normalmente.
        # Adicionalmente, verifica se o Valor é maior que zero para evitar divisão por zero.
        resultado['Percentual_Margem_Produto'] = np.where(
            resultado['Valor'] > 0,
            (resultado['Receita_Liquida_Produto'] / resultado['Valor']) * 100,
            0  # Valor se a condição for FALSA (Valor <= 0)
        )
        
        return resultado

    def _calcular_resumo_financeiro_com_pedaladas(self, resultado, custos_fix_df, mes_referencia, valor_pedaladas, valor_pedalada_auto=0, taxa_variavel_pedalada_auto=0):
        """Calcula o resumo financeiro completo COM tratamento de pedaladas"""

        # Totais básicos BRUTOS (antes de descontar pedaladas)
        # A receita bruta do sistema deve incluir o que foi removido (auto pedalada)
        receita_bruta_sistema = resultado['Valor'].sum() + valor_pedalada_auto
        custo_insumos_total = resultado['Custo_Total_Insumos'].sum()

        # Totais por forma de pagamento BRUTOS
        total_dinheiro = resultado['Dinheiro'].sum()
        total_debito = resultado['Débito'].sum()
        total_credito_bruto = resultado['Crédito'].sum()
        total_cashless = resultado['Cashless'].sum()
        total_voucher = resultado['Voucher'].sum()
        total_divisao = resultado['Divisão'].sum()
        total_outros = resultado['Outros'].sum()

        # AJUSTES PARA PEDALADAS
        # As pedaladas saem do crédito (pois foram passadas no cartão de crédito)
        total_credito_liquido = total_credito_bruto - valor_pedaladas
        receita_bruta_real = receita_bruta_sistema - valor_pedaladas

        # Calcular taxas (incluindo a taxa da pedalada que DEVE SER PAGA)
        taxa_pedalada = valor_pedaladas * 0.03  # 3% sobre o valor da pedalada
        taxa_total_debito = resultado['Taxa_Debito'].sum()
        taxa_total_credito_liquido = total_credito_liquido * 0.03
        taxa_total_credito_bruto = total_credito_bruto * 0.03  # Inclui taxa da pedalada
        taxa_total_cashless = resultado['Taxa_Cashless'].sum()
        taxa_total_voucher = resultado['Taxa_Voucher'].sum()
        taxa_total_divisao = resultado['Taxa_Divisao'].sum()
        taxa_total_outros = resultado['Taxa_Outros'].sum()

        # Taxa total (incluindo a taxa da pedalada)
        # ADICIONADO: taxa_variavel_pedalada_auto (calculada antes da remoção)
        taxa_total_geral = (taxa_total_debito + taxa_total_credito_bruto + 
                          taxa_total_cashless + taxa_total_voucher + 
                          taxa_total_divisao + taxa_total_outros + 
                          taxa_variavel_pedalada_auto)

        # Processar custos fixos
        custos_fixos_dict = dict(zip(custos_fix_df['Custo'], custos_fix_df['Valor']))
        custos_fixos_absolutos = {k: v for k, v in custos_fixos_dict.items() 
                                if not k.startswith('TAXA_MAQUINA_CARTAO_PERCENTUAL')}
        custos_fixos_total = sum(custos_fixos_absolutos.values())
        
        # --- CORREÇÃO DE CHAVES (BLINDAGEM) ---
        # Garante Custos Variáveis Totais
        if 'Custo_Total_Produto' in resultado.columns:
            custos_variaveis_totais = resultado['Custo_Total_Produto'].sum()
        else:
             # FALLBACK: Se a coluna não existe, calcula: Quantidade * Custo Unitário
            col_qtd = 'Quantidade' if 'Quantidade' in resultado.columns else None
            col_custo = 'Custo_Insumo_Unitario' if 'Custo_Insumo_Unitario' in resultado.columns else None
            if col_qtd and col_custo:
                 custos_variaveis_totais = (resultado[col_qtd] * resultado[col_custo]).sum()
            else:
                 custos_variaveis_totais = 0.0

        # Cálculos finais com receita REAL (descontada a pedalada)
        margem_bruta = receita_bruta_real - custo_insumos_total
        lucro_liquido = margem_bruta - custos_fixos_total - taxa_total_geral
        percentual_margem_liquida = (lucro_liquido / receita_bruta_real) * 100 if receita_bruta_real > 0 else 0

        return {
            'mes_referencia': mes_referencia or datetime.now().strftime("%Y-%m"),
            'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

            # Valores BRUTOS (do sistema)
            'receita_bruta_sistema': receita_bruta_sistema,
            'total_credito_bruto': total_credito_bruto,

            # Valores REAIS (descontadas as pedaladas)
            'receita_bruta_real': receita_bruta_real,
            'total_credito_liquido': total_credito_liquido,

            # Pedaladas
            'valor_pedaladas': valor_pedaladas,
            'taxa_pedalada': taxa_pedalada,
            'taxa_variavel_pedalada_auto': taxa_variavel_pedalada_auto,

            'custo_insumos_total': custo_insumos_total,
            'custos_variaveis_totais': custos_variaveis_totais, # Adicionado para compatibilidade
            'margem_bruta': margem_bruta,
            'percentual_margem_bruta': (margem_bruta / receita_bruta_real) * 100 if receita_bruta_real > 0 else 0,
            'custos_fixos_total': custos_fixos_total,

            # Detalhamento das formas de pagamento
            'total_dinheiro': total_dinheiro,
            'total_debito': total_debito,
            'total_cashless': total_cashless,
            'total_voucher': total_voucher,
            'total_divisao': total_divisao,
            'total_outros': total_outros,

            # Detalhamento das taxas
            'taxa_total_debito': taxa_total_debito,
            'taxa_total_credito_liquido': taxa_total_credito_liquido,
            'taxa_total_credito_bruto': taxa_total_credito_bruto,
            'taxa_total_cashless': taxa_total_cashless,
            'taxa_total_voucher': taxa_total_voucher,
            'taxa_total_divisao': taxa_total_divisao,
            'taxa_total_outros': taxa_total_outros,
            'taxa_total_geral': taxa_total_geral,

            'lucro_liquido': lucro_liquido,
            'lucro_liquido_estimado': lucro_liquido, # Alias para compatibilidade
            'percentual_margem_liquida': percentual_margem_liquida,
            'margem_liquida_percentual': percentual_margem_liquida, # Alias para compatibilidade
            'custos_fixos_detalhados': custos_fixos_absolutos,
            'produtos_processados': len(resultado),
            'ticket_medio_real': receita_bruta_real / resultado['Quantidade'].sum() if resultado['Quantidade'].sum() > 0 else 0
        }

    def _salvar_resultado(self, resultado, resumo, mes_referencia, valor_pedaladas):
        """Salva o resultado em CSV"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"margem_lucro_{mes_referencia or timestamp}.csv"

        # Preparar dados para salvar (incluindo detalhamento de taxas)
        resultado_salvar = resultado[['Categoria', 'Produto', 'Quantidade', 'Valor',
                                   'Dinheiro', 'Débito', 'Crédito', 'Cashless',
                                   'Custo_Insumo_Unitario', 'Custo_Total_Insumos',
                                   'Taxa_Debito', 'Taxa_Credito', 'Taxa_Cashless', 
                                   'Taxa_Total_Produto', 'Receita_Liquida_Produto', 
                                   'Margem_Unitaria', 'Percentual_Margem_Produto']].copy()

        resultado_salvar.to_csv(nome_arquivo, index=False, encoding='utf-8')
        print(f"💾 Resultado salvo em: {nome_arquivo}")

    def _exibir_relatorio(self, resumo, resultado, valor_pedaladas):
        """Exibe o relatório completo no console"""

        print("\\n" + "="*90)
        print("📈 RELATÓRIO DE MARGEM DE LUCRO - COM TRATAMENTO DE PEDALADAS")
        print("="*90)

        print(f"🗓️  Mês de referência: {resumo['mes_referencia']}")
        print(f"⏰ Processado em: {resumo['data_processamento']}")
        print(f"🍽️  Produtos analisados: {resumo['produtos_processados']}")

        if valor_pedaladas > 0:
            print("\\n💳 AJUSTES POR PEDALADAS:")
            print(f"   Receita bruta (sistema): R$ {resumo['receita_bruta_sistema']:>12,.2f}")
            print(f"   Pedaladas (desconto):    R$ {resumo['valor_pedaladas']:>12,.2f}")
            print(f"   Taxa da pedalada (3%):   R$ {resumo['taxa_pedalada']:>12,.2f}")
            if resumo.get('taxa_variavel_pedalada_auto', 0) > 0:
                print(f"   Taxa var. (Cozinha):     R$ {resumo['taxa_variavel_pedalada_auto']:>12,.2f}")
            print("-" * 90)
            print(f"   Receita bruta REAL:      R$ {resumo['receita_bruta_real']:>12,.2f}")

        print("\\n💰 RESUMO FINANCEIRO:")
        print(f"   Receita bruta real:  R$ {resumo['receita_bruta_real']:>12,.2f}")
        print(f"   Custo de insumos:    R$ {resumo['custo_insumos_total']:>12,.2f}")
        print(f"   Margem bruta:        R$ {resumo['margem_bruta']:>12,.2f} ({resumo['percentual_margem_bruta']:>5.1f}%)")
        print(f"   Custos fixos:        R$ {resumo['custos_fixos_total']:>12,.2f}")
        print(f"   Taxas totais:        R$ {resumo['taxa_total_geral']:>12,.2f}")
        print("-" * 90)
        print(f"   💎 LUCRO LÍQUIDO:     R$ {resumo['lucro_liquido']:>12,.2f} ({resumo['percentual_margem_liquida']:>5.1f}%)")

        print("\\n💳 DETALHAMENTO POR FORMA DE PAGAMENTO:")
        print(f"   Dinheiro (0% taxa):  R$ {resumo['total_dinheiro']:>10,.2f} | Taxa: R$ {0:>8,.2f}")
        print(f"   Débito (2% taxa):    R$ {resumo['total_debito']:>10,.2f} | Taxa: R$ {resumo['taxa_total_debito']:>8,.2f}")

        if valor_pedaladas > 0:
            print(f"   Crédito BRUTO:       R$ {resumo['total_credito_bruto']:>10,.2f} | Taxa: R$ {resumo['taxa_total_credito_bruto']:>8,.2f}")
            print(f"   Pedaladas:          -R$ {resumo['valor_pedaladas']:>10,.2f} | Taxa: R$ {resumo['taxa_pedalada']:>8,.2f}")
            print(f"   Crédito LÍQUIDO:     R$ {resumo['total_credito_liquido']:>10,.2f} | Taxa: R$ {resumo['taxa_total_credito_liquido']:>8,.2f}")
        else:
            print(f"   Crédito (3% taxa):   R$ {resumo['total_credito_bruto']:>10,.2f} | Taxa: R$ {resumo['taxa_total_credito_bruto']:>8,.2f}")

        print(f"   Cashless (3% taxa):  R$ {resumo['total_cashless']:>10,.2f} | Taxa: R$ {resumo['taxa_total_cashless']:>8,.2f}")

        if resumo['total_voucher'] > 0:
            print(f"   Voucher (3% taxa):   R$ {resumo['total_voucher']:>10,.2f} | Taxa: R$ {resumo['taxa_total_voucher']:>8,.2f}")
        if resumo['total_divisao'] > 0:
            print(f"   Divisão (3% taxa):   R$ {resumo['total_divisao']:>10,.2f} | Taxa: R$ {resumo['taxa_total_divisao']:>8,.2f}")
        if resumo['total_outros'] > 0:
            print(f"   Outros (3% taxa):    R$ {resumo['total_outros']:>10,.2f} | Taxa: R$ {resumo['taxa_total_outros']:>8,.2f}")

        print(f"\\n🎯 INDICADORES:")
        print(f"   Ticket médio real: R$ {resumo['ticket_medio_real']:.2f}")
        print(f"   % vendas em dinheiro: {(resumo['total_dinheiro']/resumo['receita_bruta_real']*100):.1f}%")
        print(f"   % vendas em cartão: {((resumo['receita_bruta_real']-resumo['total_dinheiro'])/resumo['receita_bruta_real']*100):.1f}%")

        if valor_pedaladas > 0:
            print(f"   % pedaladas do total: {(resumo['valor_pedaladas']/resumo['receita_bruta_sistema']*100):.1f}%")
            print(f"   Custo real das pedaladas: R$ {resumo['taxa_pedalada']:.2f}")

        # Top produtos por receita líquida
        print("\\n🏆 TOP 5 PRODUTOS POR RECEITA LÍQUIDA:")
        top_receita = resultado.nlargest(5, 'Receita_Liquida_Produto')[['Produto', 'Quantidade', 'Valor', 'Receita_Liquida_Produto', 'Margem_Unitaria']]
        for _, row in top_receita.iterrows():
            print(f"   {row['Produto'][:35]:<35} - Qtd: {row['Quantidade']:>3} - R$ {row['Valor']:>7.2f} | Líquida: R$ {row['Receita_Liquida_Produto']:>7.2f} (Margem: R$ {row['Margem_Unitaria']:>5.2f})")

        # Produtos problemáticos
        produtos_problema = resultado[resultado['Margem_Unitaria'] <= 0]
        if len(produtos_problema) > 0:
            print(f"\\n⚠️  PRODUTOS COM MARGEM NEGATIVA ({len(produtos_problema)}):")
            for _, row in produtos_problema.iterrows():
                print(f"   ❌ {row['Produto'][:35]:<35} - Margem: R$ {row['Margem_Unitaria']:>6.2f}")

        print("\\n" + "="*90)

    def _calcular_kpis_avancados(self, resumo, custos_fixos_total, margem_bruta, receita_bruta_real):
        """Calcula KPIs estratégicos para o gestor"""
        
        # 1. Break-even Point (Ponto de Equilíbrio)
        # Fórmula: Custos Fixos / Margem de Contribuição (%)
        margem_contrib_percentual = (margem_bruta / receita_bruta_real) if receita_bruta_real > 0 else 0
        
        if margem_contrib_percentual > 0:
            break_even = custos_fixos_total / margem_contrib_percentual
        else:
            break_even = 0
            
        resumo['kpi_break_even'] = break_even
        resumo['kpi_margem_contrib_percentual'] = margem_contrib_percentual * 100

        # 2. CMV (Custo da Mercadoria Vendida) %
        resumo['kpi_cmv_percentual'] = (resumo['custo_insumos_total'] / receita_bruta_real * 100) if receita_bruta_real > 0 else 0

    def comparar_mes_anterior(self, resumo_atual, resumo_anterior):
        """Gera dicionário com variações percentuais em relação ao mês anterior"""
        if not resumo_anterior:
            return None
            
        comparativo = {}
        metricas = ['receita_bruta_real', 'lucro_liquido', 'ticket_medio_real', 'custos_fixos_total']
        
        for metrica in metricas:
            valor_atual = resumo_atual.get(metrica, 0)
            valor_anterior = resumo_anterior.get(metrica, 0)
            
            if valor_anterior > 0:
                delta = ((valor_atual - valor_anterior) / valor_anterior) * 100
            else:
                delta = 0 if valor_atual == 0 else 100 # Se anterior era 0 e atual > 0, consideramos 100% de aumento simbólico
                
            comparativo[f'delta_{metrica}'] = delta
            
        return comparativo
