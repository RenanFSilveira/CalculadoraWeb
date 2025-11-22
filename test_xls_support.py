import pandas as pd
from calculadora_com_pedaladas import CalculadoraMargemLucroComPedalada
import os

def test_xls_compatibility():
    print("🧪 Iniciando teste de compatibilidade .xls vs .xlsx...")
    
    file_xlsx = "Outubro.xlsx"
    file_xls = "Outubro.xls"
    
    if not os.path.exists(file_xlsx) or not os.path.exists(file_xls):
        print("❌ Arquivos de teste não encontrados (Outubro.xlsx ou Outubro.xls)")
        return

    calc = CalculadoraMargemLucroComPedalada("Variaveis.csv", "Fixos.csv")
    
    print(f"🔄 Processando {file_xlsx}...")
    resumo_xlsx, _ = calc.processar_relatorio_mensal(file_xlsx, valor_pedaladas=0, salvar_resultado=False)
    
    print(f"🔄 Processando {file_xls}...")
    resumo_xls, _ = calc.processar_relatorio_mensal(file_xls, valor_pedaladas=0, salvar_resultado=False)
    
    # Comparar métricas chave
    keys_to_compare = ['receita_bruta_real', 'lucro_liquido', 'custo_insumos_total', 'valor_pedalada_auto']
    
    all_match = True
    print("\n📊 Comparativo de Resultados:")
    for key in keys_to_compare:
        val_xlsx = resumo_xlsx.get(key, 0)
        val_xls = resumo_xls.get(key, 0)
        
        match = abs(val_xlsx - val_xls) < 0.01 # Tolerância de 1 centavo
        status = "✅ IGUAL" if match else "❌ DIFERENTE"
        if not match: all_match = False
        
        print(f"   {key}: XLSX={val_xlsx:.2f} | XLS={val_xls:.2f} -> {status}")
        
    if all_match:
        print("\n✅ TESTE PASSOU! Os resultados são idênticos.")
    else:
        print("\n❌ TESTE FALHOU! Há divergências nos cálculos.")

if __name__ == "__main__":
    test_xls_compatibility()
