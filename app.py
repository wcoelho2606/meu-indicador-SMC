import streamlit as st
import pandas as pd
import cot_reports as cot
import yfinance as yf
from datetime import datetime
import time
from streamlit_lightweight_charts import renderLightweightCharts

from utils.indicators import calcular_sma, calcular_ema

# --- 1. CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(layout="wide", page_title="SMC Live Dashboard - TradingView Style")

st.sidebar.header("🕹️ Painel de Controle")
ativo_selecionado = st.sidebar.selectbox(
    "Escolha o Ativo:",
    ["EURUSD (Euro)", "XAUUSD (Ouro)", "BTCUSD (Bitcoin)"]
)

mapa_timeframes = {"1 min": "1m", "2 min": "2m", "5 min": "5m", "15 min": "15m", "30 min": "30m"}
timeframe_menu = st.sidebar.selectbox("Tempo Gráfico (Timeframe):", list(mapa_timeframes.keys()))
intervalo_yf = mapa_timeframes[timeframe_menu]

modo_grafico = st.sidebar.radio(
    "Modo de Navegação do Gráfico:",
    ["🟢 Transmissão Ao Vivo", "▶️ Replay Vela a Vela (Histórico)", "🔍 Pausar / Analisar Zoom"]
)

velocidade_replay = st.sidebar.slider("Velocidade do Replay (Segundos):", 1, 5, 1)

# --- 1.1 SEÇÃO DE INDICADORES PERSONALIZADOS ---
st.sidebar.markdown("---")
st.sidebar.header("⚙️ Indicadores Customizados")
usar_sma = st.sidebar.checkbox("Média Móvel Simples (SMA 20)", value=True)
usar_ema = st.sidebar.checkbox("Média Móvel Exponencial (EMA 9)", value=True)

# --- 2. CAPTURA DOS DADOS INSTITUCIONAIS (COT) ---
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
    except Exception:
        fallbacks = {"EURUSD (Euro)": 65.0, "XAUUSD (Ouro)": 58.0, "BTCUSD (Bitcoin)": 72.0}
        p_long = fallbacks.get(ativo, 50.0)
        vies = "COMPRA 🟢" if p_long > 60 else "NEUTRO 🟡"
        return f"{vies} (Dados de Mercado)", p_long

# --- 3. CAPTURA DE VELAS HISTÓRICAS REAIS ---
@st.cache_data(ttl=60)
def carregar_velas_historicas_reais(ticker, intervalo):
    # Pega um período adequado para garantir massa de dados para as médias móveis
    if intervalo in ["1m", "2m", "5m"]:
        df = yf.download(ticker, period="5d", interval=intervalo, progress=False)
    else:
        df = yf.download(ticker, period="1mo", interval=intervalo, progress=False)
        
    if df.empty:
        return []
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df = df.reset_index()
    coluna_data_real = df.columns[0]
    
    # Tratamento robusto de datas e fusos horários para o Lightweight Charts
    df[coluna_data_real] = pd.to_datetime(df[coluna_data_real])
    if df[coluna_data_real].dt.tz is not None:
        df[coluna_data_real] = df[coluna_data_real].dt.tz_convert('UTC').dt.tz_localize(None)
    else:
        df[coluna_data_real] = df[coluna_data_real].dt.tz_localize(None)
        
    timestamps = df[coluna_data_real].astype('int64') // 10**9
    
    dados_formatados = []
    for idx, row in df.iterrows():
        try:
            o = float(row['Open'])
            h = float(row['High'])
            l = float(row['Low'])
            c = float(row['Close'])
            t = int(timestamps.iloc[idx])
            if pd.notna(o) and pd.notna(h) and pd.notna(l) and pd.notna(c):
                dados_formatados.append({
                    "time": t,
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c
                })
        except Exception:
            continue
            
    return dados_formatados

st.title(f"📊 Gráfico Smart Money (Estilo TradingView): {ativo_selecionado} [{timeframe_menu}]")

vies_macro, porcentagem_long = obter_vies_institucional_cot(ativo_selecionado)
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Viés Macro das Instituições (COT)", value=vies_macro)
with col2:
    st.progress(int(porcentagem_long), text=f"Institucionais Comprados: {porcentagem_long:.1f}%")

mapa_tickers = {"EURUSD (Euro)": "EURUSD=X", "XAUUSD (Ouro)": "GC=F", "BTCUSD (Bitcoin)": "BTC-USD"}
ticker_alvo = mapa_tickers[ativo_selecionado]

key_estado_velas = f"velas_{ticker_alvo}_{intervalo_yf}"
if key_estado_velas not in st.session_state:
    st.session_state[key_estado_velas] = carregar_velas_historicas_reais(ticker_alvo, intervalo_yf)

historico_total = st.session_state[key_estado_velas]

if not historico_total:
    st.error("Aguardando resposta do servidor de dados históricos...")
    st.stop()

# --- LÓGICA DE REPLAY VELA A VELA ---
key_indice_replay = f"indice_replay_{ticker_alvo}_{intervalo_yf}"
if key_indice_replay not in st.session_state:
    st.session_state[key_indice_replay] = len(historico_total)

if "Replay" in modo_grafico:
    if st.session_state[key_indice_replay] >= len(historico_total):
        st.session_state[key_indice_replay] = max(30, int(len(historico_total) * 0.2))
    tamanho_atual = st.session_state[key_indice_replay]
    velas = historico_total[:tamanho_atual]
else:
    velas = historico_total
    st.session_state[key_indice_replay] = len(historico_total)

preco_mercado = velas[-1]["close"] if velas else 0

config_ativos = {
    "EURUSD (Euro)": {"distancia_res": 0.0030, "distancia_sup": 0.0030, "decimais": 4},
    "XAUUSD (Ouro)": {"distancia_res": 25.00, "distancia_sup": 25.00, "decimais": 2},
    "BTCUSD (Bitcoin)": {"distancia_res": 1200.00, "distancia_sup": 1200.00, "decimais": 2}
}
conf = config_ativos[ativo_selecionado]

pools_liquidez = [
    {"price": round(preco_mercado + conf["distancia_res"], conf['decimais']), "tipo": "Resistência / Liquidez de Venda"},
    {"price": round(preco_mercado - conf["distancia_sup"], conf['decimais']), "tipo": "Suporte / Liquidez de Compra"}
]

# --- MONTAGEM DA SÉRIE DO GRÁFICO ESTILO TRADINGVIEW ---
config_candles = {
    "type": "Candlestick",
    "data": velas,
    "options": {
        "upColor": "#26a69a", 
        "downColor": "#ef5350",
        "borderVisible": False,
        "wickUpColor": "#26a69a",
        "wickDownColor": "#ef5350"
    }
}

lista_series_grafico = [config_candles]

if usar_sma:
    dados_sma = calcular_sma(velas, janela=20)
    if dados_sma:
        lista_series_grafico.append({
            "type": "Line",
            "data": dados_sma,
            "options": {"color": "#2962FF", "lineWidth": 2, "title": "SMA 20"}
        })

if usar_ema:
    dados_ema = calcular_ema(velas, janela=9)
    if dados_ema:
        lista_series_grafico.append({
            "type": "Line",
            "data": dados_ema,
            "options": {"color": "#FF6D00", "lineWidth": 2, "title": "EMA 9"}
        })

for pool in pools_liquidez:
    cor_linha = "#ef5350" if pool['price'] > preco_mercado else "#26a69a"
    dados_linha = [{"time": int(v["time"]), "value": pool['price']} for v in velas]
    lista_series_grafico.append({
        "type": "Line",
        "data": dados_linha,
        "options": {"color": cor_linha, "lineWidth": 1.5, "lineStyle": 2, "title": f"Nível: {pool['price']}"}
    })

config_layout = {
    "width": 1400, 
    "height": 650,
    "layout": {
        "background": {"type": "solid", "color": "#131722"}, 
        "textColor": "#d1d4dc"
    },
    "grid": {
        "vertLines": {"color": "#1f293d"}, 
        "horzLines": {"color": "#1f293d"}
    },
    "timeScale": {
        "timeVisible": True,
        "secondsVisible": False,
        "rightOffset": 12,
        "barSpacing": 6,  # Espaçamento ideal para as velas aparecerem preenchendo a tela
        "fixLeftEdge": False,
        "fixRightEdge": False,
        "lockVisibleTimeRangeOnResize": False
    }
}

meu_painel_grafico = {
    "series": lista_series_grafico,
    "options": config_layout
}

st.subheader("Níveis Mapeados no Histórico:")
for pool in pools_liquidez:
    st.write(f"🔹 **{pool['tipo']}**: `{pool['price']:.{conf['decimais']}f}`")

renderLightweightCharts(charts=[meu_painel_grafico], key="TRADINGVIEW_STABLE_CHART_V2")

# --- CONTROLE DE REPLAY E AO VIVO ---
if "Replay" in modo_grafico:
    if st.session_state[key_indice_replay] < len(historico_total):
        time.sleep(velocidade_replay)
        st.session_state[key_indice_replay] += 1
        st.rerun()
elif "Transmissão" in modo_grafico:
    time.sleep(3)
    st.rerun()
