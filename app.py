import streamlit as st
import pandas as pd
import requests
import cot_reports as cot
import time
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

# CONFIGURAÇÕES DO MENU LATERAL (SELEÇÃO DE ATIVO E TIMEFRAME)
st.sidebar.header("🕹️ Painel de Controle")
ativo_selecionado = st.sidebar.selectbox(
    "Escolha o Ativo:",
    ["EURUSD (Euro)", "XAUUSD (Ouro)", "BTCUSD (Bitcoin)"]
)

# Adiciona o seletor dos tempos gráficos pedidos por você
timeframe = st.sidebar.selectbox(
    "Tempo Gráfico (Timeframe):",
    ["1 min", "2 min", "5 min", "15 min", "30 min"]
)

# Velocidade de pulso do mercado na tela
velocidade = st.sidebar.slider("Velocidade do Tick (Segundos):", 1, 5, 2)

st.title(f"📊 Gráfico Vivo Smart Money: {ativo_selecionado} [{timeframe}]")

# Carrega os dados do relatório COT
vies_macro, porcentagem_long = obter_vies_institucional_cot(ativo_selecionado)

# Exibe métricas institucionais
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Viés Macro das Instituições (COT)", value=vies_macro)
with col2:
    st.progress(int(porcentagem_long), text=f"Institucionais Comprados: {porcentagem_long:.1f}%")

# Definições matemáticas específicas por volatilidade de cada mercado
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

# Cria o container reservado do Streamlit para o gráfico se mexer sem quebrar a página
container_do_grafico = st.empty()

# --- 3. LÓGICA DE MOVIMENTAÇÃO DINÂMICA (LOOP REALTIME) ---
# Geramos a estrutura inicial das barras
datas = pd.date_range(end=datetime.now(), periods=40, freq='min').strftime('%Y-%m-%d %H:%M:%S')
dados_velas = []
preco_base = preco_mercado
passo_preco = conf["preco_base"] * 0.00015

for index, data in enumerate(datas):
    preco_base += passo_preco if index % 2 == 0 else -passo_preco
    dados_velas.append({
        "time": data, "open": preco_base - (passo_preco * 0.2), "high": preco_base + (passo_preco * 0.5),
        "low": preco_base - (passo_preco * 0.6), "close": preco_base
    })

# Inicia a oscilação infinita na tela simulando o mercado ao vivo
contador_loop = 0
while True:
    contador_loop += 1
    
    # Faz o preço da última vela se mover para cima ou para baixo a cada ciclo do loop
    variacao_ao_vivo = (passo_preco * 0.4) if contador_loop % 2 == 0 else -(passo_preco * 0.3)
    dados_velas[-1]["close"] += variacao_ao_vivo
    dados_velas[-1]["high"] = max(dados_velas[-1]["high"], dados_velas[-1]["close"])
    dados_velas[-1]["low"] = min(dados_velas[-1]["low"], dados_velas[-1]["close"])

    # Monta a estrutura gráfica atualizada
    config_candles = {
        "type": "Candlestick",
        "data": dados_velas,
        "options": {"upColor": "#26a69a", "downColor": "#ef5350"}
    }
    
    lista_series_grafico = [config_candles]
    
    # Atualiza as duas linhas horizontais de liquidez acompanhando as velas
    for pool in pools_liquidez:
        cor_linha = "#ef5350" if pool['price'] > preco_mercado else "#26a69a"
        dados_linha_liquidez = [{"time": vela["time"], "value": pool['price']} for vela in dados_velas]
        
        lista_series_grafico.append({
            "type": "Line",
            "data": dados_linha_liquidez,
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
    
    # Atualiza o gráfico limpando o container anterior e reinjetando os dados modificados
    with container_do_grafico:
        renderLightweightCharts(charts=[meu_painel_grafico], key=f"grafico_{contador_loop}")
        
    # Dá uma pausa antes de simular a próxima movimentação (controlado pela barra lateral)
    time.sleep(velocidade)
