import streamlit as st
import pandas as pd
import os
import tempfile
import time
import re
from datetime import datetime
import altair as alt

# Importação da classe de cálculo
from calculadora_com_pedaladas import CalculadoraMargemLucroComPedalada

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Financeira Delivery", layout="wide", page_icon="📊")

# Função de verificação de senha
def check_password():
    """Retorna `True` se o usuário tiver a senha correta."""

    def password_entered():
        """Checa se a senha inserida bate com a senha nos segredos."""
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Não armazena a senha
        else:
            st.session_state["password_correct"] = False

    # Verifica se a senha já foi validada
    if "password_correct" not in st.session_state:
        # Primeira execução, mostra input
        st.text_input(
            "Digite a senha de acesso:", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Senha incorreta, pede novamente
        st.text_input(
            "Senha incorreta. Tente novamente:", type="password", on_change=password_entered, key="password"
        )
        return False
    else:
        # Senha correta
        return True

# --- BLOQUEIO DA APLICAÇÃO ---
if not check_password():
    st.stop()  # Para a execução do app aqui se não estiver logado

st.title("📊 Painel de Gestão & Margem")

# --- FUNÇÕES AUXILIARES ---
def carregar_dados_csv(arquivo, colunas_padrao):
    if arquivo not in st.session_state:
        try:
            st.session_state[arquivo] = pd.read_csv(arquivo)
        except FileNotFoundError:
            st.session_state[arquivo] = pd.DataFrame(columns=colunas_padrao)
    return st.session_state[arquivo]

# NOVA FUNÇÃO ROBUSTA DE DATA
def converter_mes_para_data(texto_mes_ano):
    meses = {
        'janeiro': 1, 'jan': 1, 'fevereiro': 2, 'fev': 2, 'março': 3, 'marco': 3, 'mar': 3,
        'abril': 4, 'abr': 4, 'maio': 5, 'mai': 5, 'junho': 6, 'jun': 6,
        'julho': 7, 'jul': 7, 'agosto': 8, 'ago': 8, 'setembro': 9, 'set': 9,
        'outubro': 10, 'out': 10, 'novembro': 11, 'nov': 11, 'dezembro': 12, 'dez': 12
    }
    
    try:
        texto_limpo = str(texto_mes_ano).strip().lower()
        texto_limpo = texto_limpo.replace('/', ' ').replace('-', ' ')
        partes = texto_limpo.split()
        
        nome_mes = partes[0]
        ano_str = partes[1] if len(partes) > 1 else "2024"
        
        if len(ano_str) == 2:
            ano_num = int(ano_str) + 2000
        else:
            ano_num = int(ano_str)
            
        mes_num = meses.get(nome_mes, 1)
        
        return datetime(ano_num, mes_num, 1)
    except:
        return datetime(2099, 1, 1)

# ==============================================================================
# 1. CONFIGURAÇÃO DE CUSTOS
# ==============================================================================
with st.expander("⚙️ Configurações de Custos (Clique para expandir)", expanded=False):
    
    st.subheader("1. Custos Fixos")
    df_fixos = carregar_dados_csv("Fixos.csv", ["Custo", "Valor"])
    
    df_fixos_editado = st.data_editor(
        df_fixos, 
        num_rows="dynamic", 
        key="editor_fixos", 
        height=250,
        use_container_width=True,
        column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f")}
    )
    
    if st.button("💾 Salvar Fixos", key="btn_save_fixos"):
        df_fixos_editado.to_csv("Fixos.csv", index=False)
        st.session_state["Fixos.csv"] = df_fixos_editado
        st.toast("Custos fixos atualizados!", icon="✅")

    st.divider()

    st.subheader("2. Ficha Técnica (Insumos)")
    termo_busca = st.text_input("🔍 Buscar Produto", placeholder="Ex: Panqueca...")
    
    df_variaveis = carregar_dados_csv("Variaveis.csv", ["Produto", "Custo_Insumo_Unitario"])
    
    if termo_busca:
        df_show = df_variaveis[df_variaveis['Produto'].str.contains(termo_busca, case=False, na=False)]
    else:
        df_show = df_variaveis

    df_variaveis_editado_view = st.data_editor(
        df_show, 
        num_rows="dynamic", 
        key="editor_variaveis",
        height=300, 
        use_container_width=True,
        column_config={
            "Custo_Insumo_Unitario": st.column_config.NumberColumn("Custo (R$)", format="R$ %.2f"),
            "Produto": st.column_config.TextColumn("Nome do Produto", width="large")
        }
    )
    
    if st.button("💾 Salvar Variáveis", key="btn_save_vars"):
        st.session_state["Variaveis.csv"].update(df_variaveis_editado_view)
        novos = df_variaveis_editado_view.index.difference(st.session_state["Variaveis.csv"].index)
        if not novos.empty:
            st.session_state["Variaveis.csv"] = pd.concat([st.session_state["Variaveis.csv"], df_variaveis_editado_view.loc[novos]])
        st.session_state["Variaveis.csv"].to_csv("Variaveis.csv", index=False)
        st.toast("Ficha técnica atualizada!", icon="✅")

# ==============================================================================
# 2. DASHBOARD MENSAL
# ==============================================================================
st.divider()
st.header("🚀 Novo Relatório Mensal")

col_up1, col_up2, col_up3 = st.columns([2, 1, 1])

with col_up1:
    arquivo_vendas = st.file_uploader("Arquivo de Vendas (Sistema)", type=["xlsx", "csv", "xls"])

with col_up2:
    mes_ref = st.text_input("Mês de Referência", value="Outubro/2024", help="Ex: Outubro/2024")

with col_up3:
    valor_pedaladas = st.number_input("Valor Pedaladas (R$)", min_value=0.0, value=0.0, step=100.0)

if 'ultimo_resultado' not in st.session_state:
    st.session_state['ultimo_resultado'] = None

if st.button("Calcular Resultados", type="primary", use_container_width=True):
    if arquivo_vendas:
        with st.spinner('Processando...'):
            try:
                suffix = ".xlsx" if arquivo_vendas.name.endswith(".xlsx") else ".csv"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(arquivo_vendas.getvalue())
                    path_vendas_temp = tmp.name
                
                calc = CalculadoraMargemLucroComPedalada("Variaveis.csv", "Fixos.csv")
                resumo, df_resultado = calc.processar_relatorio_mensal(
                    path_vendas_temp, mes_ref, valor_pedaladas, salvar_resultado=False
                )
                
                st.session_state['ultimo_resultado'] = {"resumo": resumo, "df": df_resultado, "mes": mes_ref}
                os.remove(path_vendas_temp)
            except Exception as e:
                st.error(f"Erro: {e}")
    else:
        st.warning("Anexe o arquivo.")

if st.session_state['ultimo_resultado']:
    dados = st.session_state['ultimo_resultado']
    resumo = dados['resumo']
    df_resultado = dados['df']
    
    st.markdown("### 🏁 Resultados do Mês")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Faturamento Real", f"R$ {resumo['receita_bruta_real']:,.2f}")
    k2.metric("Lucro Líquido", f"R$ {resumo['lucro_liquido_estimado']:,.2f}", f"{resumo['margem_liquida_percentual']:.1f}%")
    k3.metric("Custos Variáveis", f"R$ {resumo['custos_variaveis_totais']:,.2f}")
    k4.metric("Custos Fixos", f"R$ {resumo['custos_fixos_totais']:,.2f}")
    
    if valor_pedaladas > 0:
         st.info(f"ℹ️ Ajuste de pedaladas: R$ {valor_pedaladas:,.2f}")

    tab_detalhe, tab_graficos, tab_save = st.tabs(["📋 Tabela", "🥞 Top Panquecas", "💾 Salvar Histórico"])
    
    with tab_detalhe:
        st.dataframe(df_resultado, use_container_width=True, height=400)
        csv = df_resultado.to_csv(index=False).encode('utf-8')
        st.download_button("Baixar CSV", csv, f"Relatorio_{dados['mes']}.csv", "text/csv")

    with tab_graficos:
        mask_panqueca = df_resultado['Produto'].str.contains("PANQUECA", case=False, na=False)
        df_panquecas = df_resultado[mask_panqueca].copy()
        if not df_panquecas.empty:
            st.caption("Ranking Panquecas (Margem Contribuição)")
            df_panquecas = df_panquecas.sort_values(by="Receita_Liquida_Produto", ascending=False).head(10)
            st.bar_chart(df_panquecas, x="Produto", y="Receita_Liquida_Produto", color="Margem_Unitaria")
        else:
            st.info("Sem panquecas.")

    with tab_save:
        st.write("Salvar este mês no banco de dados?")
        if st.button("Confirmar Gravação"):
            arquivo_hist = "historico_financeiro.csv"
            novo_registro = {
                "Mes_Referencia": dados['mes'],
                "Receita_Real": resumo['receita_bruta_real'],
                "Lucro_Liquido": resumo['lucro_liquido_estimado'],
                "Margem_Percentual": resumo['margem_liquida_percentual'],
            }
            df_novo = pd.DataFrame([novo_registro])
            
            if not os.path.exists(arquivo_hist):
                df_novo.to_csv(arquivo_hist, index=False)
            else:
                df_antigo = pd.read_csv(arquivo_hist)
                df_antigo = df_antigo[df_antigo['Mes_Referencia'] != dados['mes']]
                df_final = pd.concat([df_antigo, df_novo], ignore_index=True)
                df_final.to_csv(arquivo_hist, index=False)
                st.success("Salvo!")
                time.sleep(0.5)
                st.rerun()

# ==============================================================================
# 3. DASHBOARD EVOLUTIVO (CORRIGIDO COM ALTAIR)
# ==============================================================================
st.markdown("---")
st.header("📈 Evolução Histórica")

if os.path.exists("historico_financeiro.csv"):
    df_hist = pd.read_csv("historico_financeiro.csv")
    
    if not df_hist.empty:
        df_hist['Data_Ordenacao'] = df_hist['Mes_Referencia'].apply(converter_mes_para_data)
        df_hist = df_hist.sort_values("Data_Ordenacao")

        # Formatação do label
        df_hist["Label"] = df_hist["Data_Ordenacao"].dt.strftime("%b/%Y")

        # =============================
        # GRÁFICO 1 — Evolução Receita e Lucro
        # =============================
        st.subheader("Evolução Histórica (Receita x Lucro)")

        chart1 = (
            alt.Chart(df_hist)
            .mark_line(point=True)
            .encode(
                x=alt.X("Data_Ordenacao:T", axis=alt.Axis(title="Mês", labelAngle=-45, format="%b/%Y")),
                y=alt.Y("value:Q", title="Valores (R$)"),
                color="variable:N"
            )
            .transform_fold(
                ["Receita_Real", "Lucro_Liquido"],
                as_=["variable", "value"]
            )
            .properties(height=350)
        )

        st.altair_chart(chart1, use_container_width=True)

        # =============================
        # GRÁFICO 2 — Faturamento x Lucro (Separado)
        # =============================
        col_h1, col_h2 = st.columns(2)
        
        with col_h1:
            st.subheader("Faturamento x Lucro")
            chart2 = (
                alt.Chart(df_hist)
                .mark_line(point=True)
                .encode(
                    x=alt.X("Data_Ordenacao:T", axis=alt.Axis(labelAngle=-45, format="%b/%Y")),
                    y="Receita_Real:Q",
                    color=alt.value("#3498db")
                )
                .properties(height=300)
            ) + (
                alt.Chart(df_hist)
                .mark_line(point=True)
                .encode(
                    x=alt.X("Data_Ordenacao:T"),
                    y="Lucro_Liquido:Q",
                    color=alt.value("#2ecc71")
                )
            )

            st.altair_chart(chart2, use_container_width=True)
            
        # =============================
        # GRÁFICO 3 — Margem Líquida (%)
        # =============================
        with col_h2:
            st.subheader("Margem Líquida (%)")
            chart3 = (
                alt.Chart(df_hist)
                .mark_bar()
                .encode(
                    x=alt.X("Data_Ordenacao:T", axis=alt.Axis(labelAngle=-45, format="%b/%Y")),
                    y="Margem_Percentual:Q",
                    color=alt.value("#f1c40f")
                )
                .properties(height=300)
            )
            st.altair_chart(chart3, use_container_width=True)

        # =============================
        # Tabela
        # =============================
        with st.expander("Ver Tabela"):
            st.dataframe(df_hist.drop(columns=['Data_Ordenacao', 'Label']), use_container_width=True)
            if st.button("Limpar Histórico"):
                os.remove("historico_financeiro.csv")
                st.rerun()

    else:
        st.info("Histórico vazio.")
