import streamlit as st
import pandas as pd
import os
import tempfile
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# Importação da classe de cálculo
from calculadora_com_pedaladas import CalculadoraMargemLucroComPedalada

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gestão Financeira Premium",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded"
)

# ==========================================
# 🔒 SISTEMA DE LOGIN (ADICIONE ISSO AQUI)
# ==========================================
def check_password():
    """Retorna `True` se o usuário tiver a senha correta."""

    def password_entered():
        """Verifica se a senha inserida bate com a do secrets."""
        if st.session_state["password"] == st.secrets["passwords"]["acesso_gestor"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Não armazena a senha na sessão
        else:
            st.session_state["password_correct"] = False

    # 1. Se já validou, retorna True
    if st.session_state.get("password_correct", False):
        return True

    # 2. Interface de Login
    st.markdown("""
    <style>
        .stTextInput > label { display: none; }
        .block-container { padding-top: 5rem; }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Acesso Restrito")
        st.write("Sistema de Gestão Financeira - Pankeca's")
        st.text_input(
            "Digite a senha de acesso", 
            type="password", 
            on_change=password_entered, 
            key="password",
            placeholder="Senha do Administrador"
        )
        
        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("❌ Senha incorreta. Tente novamente.")

    return False

# Se a senha não estiver correta, para a execução do script aqui.
if not check_password():
    st.stop()

# --- CSS CUSTOMIZADO (PREMIUM) ---
st.markdown("""
<style>
    /* Fundo Geral */
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    
    /* Cards de KPI */
    .kpi-card {
        background: linear-gradient(145deg, #1e2329, #161b22);
        border-radius: 15px;
        padding: 20px;
        box-shadow: 5px 5px 10px #0b0d10, -5px -5px 10px #292f38;
        text-align: center;
        border: 1px solid #30363d;
        transition: transform 0.2s;
    }
    .kpi-card:hover {
        transform: translateY(-5px);
        border-color: #58a6ff;
    }
    .kpi-value {
        font-size: 24px;
        font-weight: bold;
        color: #58a6ff;
        margin: 10px 0;
    }
    .kpi-label {
        font-size: 14px;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .kpi-delta {
        font-size: 12px;
        font-weight: 600;
    }
    .delta-pos { color: #2ea043; }
    .delta-neg { color: #da3633; }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    
    /* Botões */
    .stButton button {
        background-color: #238636;
        color: white;
        border-radius: 8px;
        font-weight: 600;
        border: none;
        transition: all 0.3s ease;
    }
    .stButton button:hover {
        background-color: #2ea043;
        box-shadow: 0 4px 12px rgba(46, 160, 67, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES AUXILIARES ---
def carregar_dados_csv(arquivo, colunas_padrao):
    if arquivo not in st.session_state:
        try:
            st.session_state[arquivo] = pd.read_csv(arquivo)
        except FileNotFoundError:
            st.session_state[arquivo] = pd.DataFrame(columns=colunas_padrao)
    return st.session_state[arquivo]

def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def kpi_card(label, valor, delta=None, prefix="R$ ", suffix=""):
    delta_html = ""
    if delta is not None:
        cor = "delta-pos" if delta >= 0 else "delta-neg"
        sinal = "+" if delta > 0 else ""
        delta_html = f"<div class='kpi-delta {cor}'>{sinal}{delta:.1f}% vs mês anterior</div>"
    
    val_fmt = f"{prefix}{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(valor, (int, float)) else valor
    
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{val_fmt}{suffix}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)

# --- SIDEBAR & NAVEGAÇÃO ---
with st.sidebar:
    st.title("💎 Gestão Premium")
    st.markdown("---")
    
    menu = st.radio("Navegação", ["📊 Dashboard Mensal", "📈 Analytics & Evolução", "⚙️ Configurações"], index=0)
    
    st.markdown("---")
    st.caption("Configurações da Sessão")
    
    # Controle de Data Inteligente
    meses = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
        7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    
    col_mes, col_ano = st.columns(2)
    with col_mes:
        mes_selecionado = st.selectbox("Mês", list(meses.values()), index=datetime.now().month - 1)
    with col_ano:
        ano_selecionado = st.number_input("Ano", min_value=2020, max_value=2030, value=datetime.now().year)
        
    mes_ref_formatado = f"{mes_selecionado}/{ano_selecionado}"
    
    st.markdown("### 📥 Upload de Vendas")
    arquivo_vendas = st.file_uploader("Arquivo do Sistema", type=["xlsx", "xls", "csv"], help="Arraste o arquivo de vendas aqui.")
    
    valor_pedaladas = st.number_input("Valor Pedaladas (R$)", min_value=0.0, value=0.0, step=100.0, help="Valor total descontado por antecipações ou taxas extras.")

# --- LÓGICA PRINCIPAL ---

if menu == "📊 Dashboard Mensal":
    st.title(f"Dashboard Financeiro - {mes_ref_formatado}")
    
    if 'ultimo_resultado' not in st.session_state:
        st.session_state['ultimo_resultado'] = None

    # Botão de Processamento Principal
    if st.sidebar.button("🚀 Processar Dados", type="primary", use_container_width=True):
        if arquivo_vendas:
            with st.spinner('Processando inteligência de dados...'):
                try:
                    if arquivo_vendas.name.endswith(".xlsx"):
                        suffix = ".xlsx"
                    elif arquivo_vendas.name.endswith(".xls"):
                        suffix = ".xls"
                    else:
                        suffix = ".csv"
                        
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(arquivo_vendas.getvalue())
                        path_vendas_temp = tmp.name
                    
                    calc = CalculadoraMargemLucroComPedalada("Variaveis.csv", "Fixos.csv")
                    resumo, df_resultado = calc.processar_relatorio_mensal(
                        path_vendas_temp, mes_ref_formatado, valor_pedaladas, salvar_resultado=False
                    )
                    
                    st.session_state['ultimo_resultado'] = {"resumo": resumo, "df": df_resultado, "mes": mes_ref_formatado}
                    os.remove(path_vendas_temp)
                    st.toast("Dados processados com sucesso!", icon="✅")
                except Exception as e:
                    st.error(f"Erro crítico: {e}")
        else:
            st.warning("Por favor, faça o upload do arquivo de vendas na barra lateral.")

    # Exibição dos Resultados
    if st.session_state['ultimo_resultado']:
        dados = st.session_state['ultimo_resultado']
        resumo = dados['resumo']
        df_resultado = dados['df']
        
        # 1. KPIs Principais (Cards Premium)
        st.markdown("### 🎯 Performance Financeira")

        # Alerta de Pedalada Automática
        valor_auto = resumo.get('valor_pedalada_auto', 0)
        if valor_auto > 0:
            st.warning(f"⚠️ Atenção: Foi detectado 'Produção Cozinha Industrial' no valor de R$ {valor_auto:,.2f}. Este valor foi automaticamente convertido para Pedalada e removido da análise de produtos.")

        c1, c2, c3, c4 = st.columns(4)
        with c1: kpi_card("Faturamento Real", resumo['receita_bruta_real'])
        with c2: kpi_card("Lucro Líquido", resumo['lucro_liquido_estimado'])
        with c3: kpi_card("Margem Líquida", resumo['margem_liquida_percentual'], prefix="", suffix="%")
        with c4: kpi_card("Break-even Point", resumo.get('kpi_break_even', 0))

        st.markdown("---")

        # 2. Gráficos Interativos (Plotly)
        col_g1, col_g2 = st.columns([2, 1])
        
        with col_g1:
            st.subheader("📊 Composição de Custos vs Lucro")
            # Dados para o Donut Chart
            labels = ['Custos Variáveis', 'Custos Fixos', 'Taxas', 'Lucro Líquido']
            values = [
                resumo['custos_variaveis_totais'],
                resumo['custos_fixos_total'],
                resumo['taxa_total_geral'],
                resumo['lucro_liquido_estimado']
            ]
            colors = ['#e74c3c', '#f39c12', '#95a5a6', '#2ecc71']
            
            fig_donut = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, marker_colors=colors)])
            fig_donut.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
            st.plotly_chart(fig_donut, use_container_width=True)
            
        with col_g2:
            st.subheader("🏆 Top 5 Produtos (Receita)")
            top_prod = df_resultado.nlargest(5, 'Receita_Liquida_Produto')
            fig_bar = px.bar(top_prod, x='Receita_Liquida_Produto', y='Produto', orientation='h', text_auto='.2s')
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
            fig_bar.update_traces(marker_color='#58a6ff')
            st.plotly_chart(fig_bar, use_container_width=True)

        # 3. Tabela Detalhada
        with st.expander("📋 Ver Detalhamento Completo dos Dados"):
            st.dataframe(df_resultado, use_container_width=True)
            
        # 4. Salvar Histórico
        if st.button("💾 Salvar no Histórico", use_container_width=True):
            arquivo_hist = "historico_financeiro.csv"
            novo_registro = {
                "Mes_Referencia": dados['mes'],
                "Receita_Real": resumo['receita_bruta_real'],
                "Lucro_Liquido": resumo['lucro_liquido_estimado'],
                "Margem_Percentual": resumo['margem_liquida_percentual'],
                "Custos_Fixos": resumo['custos_fixos_total'],
                "Ticket_Medio": resumo.get('ticket_medio_real', 0)
            }
            df_novo = pd.DataFrame([novo_registro])
            
            if not os.path.exists(arquivo_hist):
                df_novo.to_csv(arquivo_hist, index=False)
            else:
                df_antigo = pd.read_csv(arquivo_hist)
                # Remove duplicatas do mesmo mês
                df_antigo = df_antigo[df_antigo['Mes_Referencia'] != dados['mes']]
                df_final = pd.concat([df_antigo, df_novo], ignore_index=True)
                df_final.to_csv(arquivo_hist, index=False)
            
            st.success("Histórico atualizado com sucesso!")
            time.sleep(1)
            st.rerun()

elif menu == "📈 Analytics & Evolução":
    st.title("📈 Inteligência Histórica")
    
    if os.path.exists("historico_financeiro.csv"):
        df_hist = pd.read_csv("historico_financeiro.csv")
        
        if not df_hist.empty:
            # Tratamento de Data
            def converter_data(x):
                try:
                    return datetime.strptime(x, "%B/%Y") # Tenta formato completo
                except:
                    try:
                        # Tenta nosso parser customizado se falhar
                        from app import converter_mes_para_data # Fallback
                        return converter_mes_para_data(x)
                    except:
                        return datetime.now()

            # Simples parser local para garantir
            meses_map = {'Janeiro': 1, 'Fevereiro': 2, 'Março': 3, 'Abril': 4, 'Maio': 5, 'Junho': 6,
                        'Julho': 7, 'Agosto': 8, 'Setembro': 9, 'Outubro': 10, 'Novembro': 11, 'Dezembro': 12}
            
            def parse_mes_ano(texto):
                try:
                    mes_nome, ano = texto.split('/')
                    return datetime(int(ano), meses_map.get(mes_nome, 1), 1)
                except:
                    return datetime.now()

            df_hist['Data_Ordenacao'] = df_hist['Mes_Referencia'].apply(parse_mes_ano)
            df_hist = df_hist.sort_values("Data_Ordenacao")
            
            # Gráfico de Evolução (Linha Dupla)
            st.subheader("Evolução: Receita vs Lucro")
            fig_evol = go.Figure()
            fig_evol.add_trace(go.Scatter(x=df_hist['Mes_Referencia'], y=df_hist['Receita_Real'], mode='lines+markers', name='Receita', line=dict(color='#3498db', width=3)))
            fig_evol.add_trace(go.Scatter(x=df_hist['Mes_Referencia'], y=df_hist['Lucro_Liquido'], mode='lines+markers', name='Lucro', line=dict(color='#2ecc71', width=3)))
            fig_evol.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white", hovermode="x unified")
            st.plotly_chart(fig_evol, use_container_width=True)
            
            # Comparativo MoM (Mês a Mês)
            st.subheader("Variação Mensal (%)")
            if len(df_hist) > 1:
                df_hist['Var_Receita'] = df_hist['Receita_Real'].pct_change() * 100
                fig_mom = px.bar(df_hist, x='Mes_Referencia', y='Var_Receita', color='Var_Receita', color_continuous_scale='RdBu')
                fig_mom.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
                st.plotly_chart(fig_mom, use_container_width=True)
            else:
                st.info("Precisa de pelo menos 2 meses de histórico para calcular variação.")

            # --- GESTÃO DO HISTÓRICO ---
            st.markdown("---")
            st.subheader("🗑️ Gerenciar Histórico")
            
            with st.expander("Opções de Exclusão"):
                c_del1, c_del2 = st.columns(2)
                
                with c_del1:
                    st.markdown("##### Excluir Mês Específico")
                    mes_para_excluir = st.selectbox("Selecione o mês para remover:", df_hist['Mes_Referencia'].unique())
                    if st.button(f"🗑️ Excluir {mes_para_excluir}"):
                        df_hist = df_hist[df_hist['Mes_Referencia'] != mes_para_excluir]
                        df_hist.to_csv("historico_financeiro.csv", index=False)
                        st.success(f"Registro de {mes_para_excluir} removido!")
                        time.sleep(1)
                        st.rerun()
                
                with c_del2:
                    st.markdown("##### ⚠️ Zona de Perigo")
                    if st.button("🔥 Apagar TODO o Histórico", type="primary"):
                        if os.path.exists("historico_financeiro.csv"):
                            os.remove("historico_financeiro.csv")
                            st.warning("Todo o histórico foi apagado.")
                            time.sleep(1)
                            st.rerun()

        else:
            st.info("Histórico vazio.")
    else:
        st.warning("Nenhum histórico encontrado. Salve o primeiro fechamento mensal no Dashboard.")

elif menu == "⚙️ Configurações":
    st.title("⚙️ Gestão de Custos")
    
    tab1, tab2 = st.tabs(["🏢 Custos Fixos", "🍔 Ficha Técnica (Insumos)"])
    
    with tab1:
        st.subheader("Custos Fixos Mensais")
        df_fixos = carregar_dados_csv("Fixos.csv", ["Custo", "Valor"])
        df_fixos_editado = st.data_editor(df_fixos, num_rows="dynamic", use_container_width=True, height=400)
        
        if st.button("💾 Salvar Custos Fixos"):
            df_fixos_editado.to_csv("Fixos.csv", index=False)
            st.session_state["Fixos.csv"] = df_fixos_editado
            st.success("Custos fixos salvos!")

    with tab2:
        st.subheader("Custos Variáveis (Produtos)")
        termo = st.text_input("🔍 Buscar Produto", placeholder="Digite para filtrar...")
        df_variaveis = carregar_dados_csv("Variaveis.csv", ["Produto", "Custo_Insumo_Unitario"])
        
        if termo:
            df_show = df_variaveis[df_variaveis['Produto'].str.contains(termo, case=False, na=False)]
        else:
            df_show = df_variaveis
            
        df_variaveis_editado = st.data_editor(df_show, num_rows="dynamic", use_container_width=True, height=500)
        
        if st.button("💾 Salvar Ficha Técnica"):
            # Lógica de merge para salvar apenas o editado sem perder o resto se estiver filtrado
            if termo:
                # Atualiza apenas as linhas alteradas no dataframe original
                st.session_state["Variaveis.csv"].update(df_variaveis_editado)
                # Adiciona novos se houver
                novos = df_variaveis_editado.index.difference(st.session_state["Variaveis.csv"].index)
                if not novos.empty:
                    st.session_state["Variaveis.csv"] = pd.concat([st.session_state["Variaveis.csv"], df_variaveis_editado.loc[novos]])
            else:
                st.session_state["Variaveis.csv"] = df_variaveis_editado
                
            st.session_state["Variaveis.csv"].to_csv("Variaveis.csv", index=False)
            st.success("Ficha técnica salva!")
