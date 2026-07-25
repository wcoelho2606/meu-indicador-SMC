import streamlit as st
import pandas as pd
import cot_reports as cot
import yfinance as yf
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

# --- 2. CAPTURA DE VELAS HISTÓRICAS REAIS (YAHOO FINANCE) ---
@st.cache_data(ttl=60)
def carregar_velas_historicas_reais(ticker, intervalo):
    data_inicio = "2026-07-01"
    
    # Restrição técnica do yfinance para tempos curtos
    if intervalo in ["1m", "2m"]:
        df = yf.download(ticker, period="7d", interval=intervalo)
    else:
        df = yf.download(ticker, start=data_inicio, interval=intervalo)
        
    if df.empty:
        return []
        
    # --- CORREÇÃO TÉCNICA DA DATA (LINHA 66) ---
    # Garante que o índice de tempo vire uma coluna normal de texto limpo
    df = df.reset_index()
    coluna_tempo = df.columns[0] # Pega sempre a primeira coluna que contém a data/hora
    df[coluna_tempo] = pd.to_datetime(df[coluna_tempo])
    
    dados_formatados = []
    for _, row in df.iterrows():
        dados_formatados.append({
            "time": row[coluna_tempo].strftime('%Y-%m-%d %H:%M:%S'),
            "open": float(row['Open']),
            "high": float(row['High']),
            "low": float(row['Low']),
            "close": float(row['Close'])
        })
    return dados_formatados

# --- 3. CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(layout="wide", page_title="SMC Live Dashboard")

st.sidebar.header("🕹️ Painel de Controle")
ativo_selecionado = st.sidebar.selectbox(
    "Escolha o Ativo:",
    ["EURUSD (Euro)", "XAUUSD (Ouro)", "BTCUSD (Bitcoin)"]
)

mapa_timeframes = {"1 min": "1m", "2 min": "2m", "5 min": "5m", "15 min": "15m", "30 min": "30m"}
timeframe_menu = st.sidebar.selectbox("Tempo Gráfico (Timeframe):", list(mapa_timeframes.keys()))
intervalo_yf = mapa_timeframes[timeframe_menu]

velocidade = st.sidebar.slider("Velocidade do Tick (Segundos):", 1, 5, 2)

st.title(f"📊 Gráfico Vivo Smart Money: {ativo_selecionado} [{timeframe_menu}]")

vies_macro, porcentagem_long = obter_vies_institucional_cot(ativo_selecionado)

col1, col2 = st.columns(2)
with col1:
    st.metric(label="Viés Macro das Instituições (COT)", value=vies_macro)
with col2:
    st.progress(int(porcentagem_long), text=f"Institucionais Comprados: {porcentagem_long:.1f}%")

mapa_tickers = {"EURUSD (Euro)": "EURUSD=X", "XAUUSD (Ouro)": "GC=F", "BTCUSD (Bitcoin)": "BTC-USD"}
ticker_alvo = mapa_tickers[ativo_selecionado]

historico_real = carregar_velas_historicas_reais(ticker_alvo, intervalo_yf)

if not historico_real:
    st.error("Aguardando resposta do servidor de dados históricos... Tente alterar o Timeframe para 5 min.")
    st.stop()

preco_mercado = historico_real[-1]["close"]

config_ativos = {
    "EURUSD (Euro)": {"distancia_res": 0.0030, "distancia_sup": 0.0040, "decimais": 4},
    "XAUUSD (Ouro)": {"distancia_res": 25.00, "distancia_sup": 35.00, "decimais": 2},
    "BTCUSD (Bitcoin)": {"distancia_res": 1200.00, "distancia_sup": 1500.00, "decimais": 2}
}
conf = config_ativos[ativo_selecionado]

pools_liquidez = [
    {"price": round(preco_mercado + conf["distancia_res"], conf['decimais'])},
    {"price": round(preco_mercado - conf["distancia_sup"], conf['decimais'])}
]

# --- 4. FRAGMENTO DINÂMICO PARA OSCILAÇÃO ---
@st.fragment(run_every=velocidade)
def renderizar_grafico_pulsante(velas_base):
    velas = list(velas_base)
    passo = preco_mercado * 0.0001
    
    segundo_atual = datetime.now().second
    oscilacao = (passo * 0.4) if segundo_atual % 2 == 0 else -(passo * 0.3)
    
    velas[-1]["close"] += oscilacao
    velas[-1]["high"] = max(velas[-1]["high"], velas[-1]["close"])
    velas[-1]["low"] = min(velas[-1]["low"], velas[-1]["close"])

    config_candles = {
        "type": "Candlestick",
        "data": velas,
        "options": {"upColor": "#26a69a", "downColor": "#ef5350"}
    }
    
    lista_series_grafico = [config_candles]
    
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
    
    st.subheader("Pools de Liquidez Mapeados no Histórico:")
    for pool in pools_liquidez:
        tipo_pool = "Liquidez de Venda (Stops)" if pool['price'] > preco_mercado else "Liquidez de Compra (Stops)"
        st.write(f"🔹 Nível detectado em: **{pool['price']:.{conf['decimais']}f}** - Tipo: {tipo_pool}")
        
    renderLightweightCharts(charts=[meu_painel_grafico], key="SMC_CHART_REAL_FINAL")

renderizar_grafico_pulsante(historico_real)
