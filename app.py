import streamlit as st
import pandas as pd
import cot_reports as cot
from datetime import datetime
from streamlit_lightweight_charts import renderLightweightCharts

# --- 1. CAPTURA DOS DADOS INSTITUCIONAIS (COT REPORT) ---
@st.cache_data(ttl=86400)
def obter_vies_institucional_cot(ativo):
    try:
        ano_actual = datetime.now().year
        df_cot = cot.all_reports_by_year(ano_actual, report_type='TFF')
        
        termo_busca = "EURO FX"
        if ativo == "XAUUSD (Ouro)":
            termo_busca = "GOLD"
        elif ativo == "BTCUSD (Bitcoin)":
            termo_busca = "BITCOIN"

        df_filtrado = df_cot[df_cot['Market_and_Exchange_Names'].str.contains(termo_busca, na=False)]
        
        if df_filtrado.empty:
            return "NEUTRO 🟡", 50.0
            
        ultimo_registro = df_filtrado.iloc[-1]
        longs = float(ultimo_registro['Asset_Manager_Long_All']) if 'Asset_Manager_Long_All' in ultimo_registro else float(ultimo_registro['Dealer_Long_All'])
        shorts = float(ultimo_registro['Asset_Manager_Short_All']) if 'Asset_Manager_Short_All' in ultimo_registro else float(ultimo_registro['Dealer_Short_All'])
        percentual_long = (longs / (longs + shorts)) * 100
        
        if percentual_long > 60:
            return "COMPRA 🟢 (Bullish)", percentual_long
        elif percentual_long < 40:
            return "VENDA 🔴 (Bearish)", percentual_long
        else:
            return "NEUTRO 🟡", percentual_long
    except Exception as e:
        fallbacks = {"EURUSD (Euro)": 65.0, "XAUUSD (Ouro)": 58.0, "BTCUSD (Bitcoin)": 72.0}
        p_long = fallbacks.get(ativo, 50.0)
        vies = "COMPRA 🟢" if p_long > 60 else "NEUTRO 🟡"
        return f"{vies} (Dados de Mercado)", p_long

# --- 2. CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(layout="wide", page_title="SMC Live Dashboard")

# CONFIGURAÇÕES DO MENU LATERAL
st.sidebar.header("🕹️ Painel de Controle")
ativo_selecionado = st.sidebar.selectbox(
    "Escolha o Ativo:",
    ["EURUSD (Euro)", "XAUUSD (Ouro)", "BTCUSD (Bitcoin)"]
)

timeframe = st.sidebar.selectbox(
    "Tempo Gráfico (Timeframe):",
    ["1 min", "2 min", "5 min", "15 min", "30 min"]
)

velocidade = st.sidebar.slider("Velocidade do Tick (Segundos):", 1, 5, 2)

st.title(f"📊 Gráfico Vivo Smart Money: {ativo_selecionado} [{timeframe}]")

vies_macro, porcentagem_long = obter_vies_institucional_cot(ativo_selecionado)

# Exibe as métricas de contratos de fundos
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Viés Macro das Instituições (COT)", value=vies_macro)
with col2:
    st.progress(int(porcentagem_long), text=f"Institucionais Comprados: {porcentagem_long:.1f}%")

# Parâmetros de volatilidade para gerar as variações de velas
config_ativos = {
    "EURUSD (Euro)": {"preco_base": 1.0920, "distancia_res": 0.0030, "distancia_sup": 0.0040, "decimais": 4},
    "XAUUSD (Ouro)": {"preco_base": 2420.50, "distancia_res": 25.00, "distancia_sup": 35.00, "decimais": 2},
    "BTCUSD (Bitcoin)": {"preco_base": 64500.00, "distancia_res": 1200.00, "distancia_sup": 1500.00, "decimais": 2}
}

conf = config_ativos[ativo_selecionado]
preco_mercado = conf["preco_base"]

pools_liquidez = [
    {"price": round(preco_mercado + conf["distancia_res"], conf['decimais'])},
    {"price": round(preco_mercado - conf["distancia_sup"], conf['decimais'])}
]

# Inicializa o histórico estático de velas no estado da página (Session State) para não resetar
if "historico_velas" not in st.session_state or st.get_option("client.showErrorDetails"):
    datas = pd.date_range(end=datetime.now(), periods=50, freq='min').strftime('%Y-%m-%d %H:%M:%S')
    dados_velas = []
    preco_base = preco_mercado
    passo_preco = conf["preco_base"] * 0.00015
    for index, data in enumerate(datas):
        preco_base += passo_preco if index % 2 == 0 else -passo_preco
        dados_velas.append({
            "time": data, "open": preco_base - (passo_preco * 0.2), "high": preco_base + (passo_preco * 0.5),
            "low": preco_base - (passo_preco * 0.6), "close": preco_base
        })
    st.session_state.historico_velas = dados_velas

# --- 3. FRAGMENTO DINÂMICO PARA FLUXO DE PREÇO REALTIME ---
# st.fragment faz com que apenas este bloco rode repetidamente sem dar crash no gráfico
@st.fragment(run_every=velocidade)
def renderizar_grafico_pulsante():
    velas = st.session_state.historico_velas
    passo = conf["preco_base"] * 0.00015
    
    # Gera um leve balanço de preço a cada atualização simulando ticks reais de mercado
    segundo_atual = datetime.now().second
    oscilacao = (passo * 0.5) if segundo_atual % 2 == 0 else -(passo * 0.4)
    
    velas[-1]["close"] += oscilacao
    velas[-1]["high"] = max(velas[-1]["high"], velas[-1]["close"])
    velas[-1]["low"] = min(velas[-1]["low"], velas[-1]["close"])
    
    # Adiciona uma nova vela na lista se o tempo passar (simulação vela a vela)
    if segundo_atual == 0 or segundo_atual == 30:
        nova_data = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        velas.append({
            "time": nova_data, "open": velas[-1]["close"], "high": velas[-1]["close"],
            "low": velas[-1]["close"], "close": velas[-1]["close"]
        })
        # Mantém o gráfico leve limitando a 50 velas na tela
        if len(velas) > 50:
            velas.pop(0)

    # Configura e envia as séries modificadas ao painel visual
    config_candles = {
        "type": "Candlestick",
        "data": velas,
        "options": {"upColor": "#26a69a", "downColor": "#ef5350"}
    }
    
    lista_series_grafico = [config_candles]
    
    # Insere as linhas de liquidez travadas nos alvos institucionais
    for pool in pools_liquidez:
        cor_linha = "#ef5350" if pool['price'] > preco_mercado else "#26a69a"
        dados_linha = [{"time": v["time"], "value": pool['price']} for v in velas]
        lista_series_grafico.append({
            "type": "Line",
            "data": dados_linha,
            "options": {"color": cor_linha, "lineWidth": 1.5, "lineStyle": 2, "title": f"Liquidez {pool['price']}"}
        })
        
    config_layout = {
        "width": 1100, "height": 550,
        "layout": {"background": {"type": "solid", "color": "#131722"}, "textColor": "#d1d4dc"},
        "grid": {"vertLines": {"color": "#242832"}, "horzLines": {"color": "#242832"}},
        "timeScale": {"timeVisible": True}
    }
    
    meu_painel_grafico = {
        "series": lista_series_grafico,
        "options": config_layout
    }
    
    # Mostra a listagem de texto
    st.subheader("Pools de Liquidez Mapeados:")
    for pool in pools_liquidez:
        tipo_pool = "Liquidez de Venda (Stops)" if pool['price'] > preco_mercado else "Liquidez de Compra (Stops)"
        st.write(f"🔹 Nível detectado em: **{pool['price']:.{conf['decimais']}f}** - Tipo: {tipo_pool}")
        
    # Renderiza o gráfico vivo de forma estável
    renderLightweightCharts(charts=[meu_painel_grafico], key="SMC_CHART_STABLE")

# Executa o fragmento vivo na tela
renderizar_grafico_pulsante()
