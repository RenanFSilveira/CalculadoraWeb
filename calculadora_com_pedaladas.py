
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
                                 valor_pedaladas=0, salvar_resultado=False):
        """
        Processa um relatório mensal com tratamento de pedaladas para o App Web.
        Versão: Blindada contra erros de chave (KeyError)
        """

        # 1. Carregar dados
        if arquivo_vendas.endswith('.xlsx'):
            vendas_df = pd.read_excel(arquivo_vendas, sheet_name=0)
        else:
            vendas_df = pd.read_csv(arquivo_vendas)

        custos_var_df = pd.read_csv(self.arquivo_custos_variaveis)
        custos_fix_df = pd.read_csv(self.arquivo_custos_fixos)

        # 2. Limpar e validar dados
        vendas_clean = self._limpar_dados_vendas(vendas_df)
        self._verificar_produtos_sem_custo(vendas_clean, custos_var_df)

        # 4. Merge com custos
        resultado = vendas_clean.merge(custos_var_df, on='Produto', how='left')
        resultado['Custo_Insumo_Unitario'] = resultado['Custo_Insumo_Unitario'].fillna(0)

        # 5. Métricas
        resultado = self._calcular_metricas_produto_e_taxas(resultado)

        # 6. Resumo Financeiro
        resumo = self._calcular_resumo_financeiro_com_pedaladas(
            resultado, custos_fix_df, mes_referencia, valor_pedaladas
        )

        # --- CORREÇÃO DE CHAVES (BLINDAGEM) ---
        
        # 1. Garante Custos Variáveis Totais
        # Se a função original não calculou, calculamos aqui.
        if 'custos_variaveis_totais' not in resumo:
            if 'Custo_Total_Produto' in resultado.columns:
                resumo['custos_variaveis_totais'] = resultado['Custo_Total_Produto'].sum()
            else:
                # FALLBACK: Se a coluna não existe, calcula: Quantidade * Custo Unitário
                # Verifica se as colunas base existem para evitar outro erro
                col_qtd = 'Quantidade' if 'Quantidade' in resultado.columns else None
                col_custo = 'Custo_Insumo_Unitario' if 'Custo_Insumo_Unitario' in resultado.columns else None
                
                if col_qtd and col_custo:
                    # Cria a coluna para uso futuro e soma
                    resultado['Custo_Total_Produto'] = resultado[col_qtd] * resultado[col_custo]
                    resumo['custos_variaveis_totais'] = resultado['Custo_Total_Produto'].sum()
                else:
                    resumo['custos_variaveis_totais'] = 0.0

        # 2. Garante Custos Fixos Totais
        if 'custos_fixos_totais' not in resumo:
            resumo['custos_fixos_totais'] = custos_fix_df['Valor'].sum() if 'Valor' in custos_fix_df else 0

        # 3. Garante Lucro Líquido
        if 'lucro_liquido_estimado' not in resumo:
            if 'lucro_liquido' in resumo:
                resumo['lucro_liquido_estimado'] = resumo['lucro_liquido']
            else:
                receita = resumo.get('receita_bruta_real', 0)
                custos = resumo.get('custos_variaveis_totais', 0) + resumo.get('custos_fixos_totais', 0)
                resumo['lucro_liquido_estimado'] = receita - custos

        # 4. Garante Margem %
        if 'margem_liquida_percentual' not in resumo:
            lucro = resumo.get('lucro_liquido_estimado', 0)
            receita = resumo.get('receita_bruta_real', 1) 
            if receita == 0: receita = 1 
            resumo['margem_liquida_percentual'] = (lucro / receita) * 100
            
        # 5. Garante Taxa Pedalada
        if 'taxa_pedalada' not in resumo:
            resumo['taxa_pedalada'] = valor_pedaladas * 0.03

        # 6. Garante Receita Bruta Real (caso falte)
        if 'receita_bruta_real' not in resumo:
             resumo['receita_bruta_real'] = resumo.get('receita_bruta_sistema', 0) - valor_pedaladas

        # 7. Salvar resultado (Ignora erros de permissão)
        if salvar_resultado:
            try:
                self._salvar_resultado(resultado, resumo, mes_referencia, valor_pedaladas)
            except Exception:
                pass

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
            print(f"\n⚠️  ATENÇÃO: {len(produtos_sem_custo)} produto(s) sem custo cadastrado:")
            for produto in sorted(produtos_sem_custo):
                qtd = vendas_clean[vendas_clean['Produto'] == produto]['Quantidade'].sum()
                print(f"   - {produto} (Qtd vendida: {qtd})")
            print("   💡 Estes produtos terão custo = 0 no cálculo\n")

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

    def _calcular_resumo_financeiro_com_pedaladas(self, resultado, custos_fix_df, mes_referencia, valor_pedaladas):
        """Calcula o resumo financeiro completo COM tratamento de pedaladas"""

        # Totais básicos BRUTOS (antes de descontar pedaladas)
        receita_bruta_sistema = resultado['Valor'].sum()
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
        taxa_total_geral = (taxa_total_debito + taxa_total_credito_bruto + 
                          taxa_total_cashless + taxa_total_voucher + 
                          taxa_total_divisao + taxa_total_outros)

        # Processar custos fixos
        custos_fixos_dict = dict(zip(custos_fix_df['Custo'], custos_fix_df['Valor']))
        custos_fixos_absolutos = {k: v for k, v in custos_fixos_dict.items() 
                                if not k.startswith('TAXA_MAQUINA_CARTAO_PERCENTUAL')}
        custos_fixos_total = sum(custos_fixos_absolutos.values())

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

            'custo_insumos_total': custo_insumos_total,
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
            'percentual_margem_liquida': percentual_margem_liquida,
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

        print("\n" + "="*90)
        print("📈 RELATÓRIO DE MARGEM DE LUCRO - COM TRATAMENTO DE PEDALADAS")
        print("="*90)

        print(f"🗓️  Mês de referência: {resumo['mes_referencia']}")
        print(f"⏰ Processado em: {resumo['data_processamento']}")
        print(f"🍽️  Produtos analisados: {resumo['produtos_processados']}")

        if valor_pedaladas > 0:
            print("\n💳 AJUSTES POR PEDALADAS:")
            print(f"   Receita bruta (sistema): R$ {resumo['receita_bruta_sistema']:>12,.2f}")
            print(f"   Pedaladas (desconto):    R$ {resumo['valor_pedaladas']:>12,.2f}")
            print(f"   Taxa da pedalada (3%):   R$ {resumo['taxa_pedalada']:>12,.2f}")
            print("-" * 90)
            print(f"   Receita bruta REAL:      R$ {resumo['receita_bruta_real']:>12,.2f}")

        print("\n💰 RESUMO FINANCEIRO:")
        print(f"   Receita bruta real:  R$ {resumo['receita_bruta_real']:>12,.2f}")
        print(f"   Custo de insumos:    R$ {resumo['custo_insumos_total']:>12,.2f}")
        print(f"   Margem bruta:        R$ {resumo['margem_bruta']:>12,.2f} ({resumo['percentual_margem_bruta']:>5.1f}%)")
        print(f"   Custos fixos:        R$ {resumo['custos_fixos_total']:>12,.2f}")
        print(f"   Taxas totais:        R$ {resumo['taxa_total_geral']:>12,.2f}")
        print("-" * 90)
        print(f"   💎 LUCRO LÍQUIDO:     R$ {resumo['lucro_liquido']:>12,.2f} ({resumo['percentual_margem_liquida']:>5.1f}%)")

        print("\n💳 DETALHAMENTO POR FORMA DE PAGAMENTO:")
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

        print(f"\n🎯 INDICADORES:")
        print(f"   Ticket médio real: R$ {resumo['ticket_medio_real']:.2f}")
        print(f"   % vendas em dinheiro: {(resumo['total_dinheiro']/resumo['receita_bruta_real']*100):.1f}%")
        print(f"   % vendas em cartão: {((resumo['receita_bruta_real']-resumo['total_dinheiro'])/resumo['receita_bruta_real']*100):.1f}%")

        if valor_pedaladas > 0:
            print(f"   % pedaladas do total: {(resumo['valor_pedaladas']/resumo['receita_bruta_sistema']*100):.1f}%")
            print(f"   Custo real das pedaladas: R$ {resumo['taxa_pedalada']:.2f}")

        # Top produtos por receita líquida
        print("\n🏆 TOP 5 PRODUTOS POR RECEITA LÍQUIDA:")
        top_receita = resultado.nlargest(5, 'Receita_Liquida_Produto')[['Produto', 'Quantidade', 'Valor', 'Receita_Liquida_Produto', 'Margem_Unitaria']]
        for _, row in top_receita.iterrows():
            print(f"   {row['Produto'][:35]:<35} - Qtd: {row['Quantidade']:>3} - R$ {row['Valor']:>7.2f} | Líquida: R$ {row['Receita_Liquida_Produto']:>7.2f} (Margem: R$ {row['Margem_Unitaria']:>5.2f})")

        # Produtos problemáticos
        produtos_problema = resultado[resultado['Margem_Unitaria'] <= 0]
        if len(produtos_problema) > 0:
            print(f"\n⚠️  PRODUTOS COM MARGEM NEGATIVA ({len(produtos_problema)}):")
            for _, row in produtos_problema.iterrows():
                print(f"   ❌ {row['Produto'][:35]:<35} - Margem: R$ {row['Margem_Unitaria']:>6.2f}")

        print("\n" + "="*90)

# Exemplo de uso
if __name__ == "__main__":
    # Criar instância da calculadora com pedaladas
    calc = CalculadoraMargemLucroComPedalada()

    # Processar relatório (exemplo: se houve R$ 54.310,00 de pedaladas no período)
    resumo, detalhamento = calc.processar_relatorio_mensal(
        "3Meses.xlsx", 
        "2024-Q3",
        valor_pedaladas=54310.00  # Valor das pedaladas do período
    )
