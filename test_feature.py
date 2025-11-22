import pandas as pd
from calculadora_com_pedaladas import CalculadoraMargemLucroComPedalada
import os

def test_auto_detection():
    print("🧪 Iniciando teste de detecção automática...")
    
    # Criar dados fake
    data = {
        'Produto': ['Coca-Cola', 'Produção Cozinha Industrial', 'Hambúrguer', 'Produção Cozinha Industrial - Extra'],
        'Valor': [100.0, 500.0, 200.0, 100.0],
        'Quantidade': [10, 1, 5, 1],
        'Categoria': ['Bebida', 'Outros', 'Lanche', 'Outros'],
        'Dinheiro': [100, 0, 200, 0],
        'Crédito': [0, 500, 0, 100], # Pedaladas geralmente entram como crédito/outros
        'Débito': [0, 0, 0, 0],
        'Cashless': [0, 0, 0, 0],
        'Voucher': [0, 0, 0, 0],
        'Divisão': [0, 0, 0, 0],
        'Outros': [0, 0, 0, 0]
    }
    df = pd.DataFrame(data)
    
    # Salvar csv temporário
    df.to_csv("test_vendas.csv", index=False)
    
    # Instanciar calculadora
    # Usa os arquivos que sabemos que existem no diretório
    calc = CalculadoraMargemLucroComPedalada("Variaveis.csv", "Fixos.csv")
    
    # Processar
    # Valor manual de pedaladas = 0, esperamos que detecte 600 (500 + 100)
    resumo, resultado = calc.processar_relatorio_mensal("test_vendas.csv", valor_pedaladas=0)
    
    # Verificações
    valor_auto = resumo.get('valor_pedalada_auto', 0)
    valor_pedaladas_total = resumo.get('valor_pedaladas', 0)
    
    print(f"\n📊 Resultados:")
    print(f"   Valor Auto Detectado: R$ {valor_auto:.2f}")
    print(f"   Valor Total Pedaladas: R$ {valor_pedaladas_total:.2f}")
    print(f"   Receita Bruta Sistema: R$ {resumo['receita_bruta_sistema']:.2f}")
    print(f"   Receita Bruta Real: R$ {resumo['receita_bruta_real']:.2f}")
    
    # Verificar se removeu do dataframe de resultado
    tem_cozinha = resultado['Produto'].str.contains("Produção Cozinha Industrial").any()
    print(f"   'Produção Cozinha Industrial' presente no resultado? {'SIM' if tem_cozinha else 'NÃO'}")
    
    # Asserts
    # Receita Original: 100+500+200+100 = 900
    # Pedalada Auto: 500+100 = 600
    # Receita Real Esperada: 300
    
    if valor_auto == 600.0 and not tem_cozinha and resumo['receita_bruta_real'] == 300.0:
        print("\n✅ TESTE PASSOU! Lógica funcionando corretamente.")
    else:
        print(f"\n❌ TESTE FALHOU! Esperado Real=300, Obtido={resumo['receita_bruta_real']}")
        
    # Limpeza
    if os.path.exists("test_vendas.csv"):
        os.remove("test_vendas.csv")

if __name__ == "__main__":
    test_auto_detection()
