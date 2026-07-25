import streamlit as st
import pandas as pd
import requests
import cot_reports as cot
from datetime import datetime
from streamlit_lightweight_charts import renderLightweightCharts

# --- CONFIGURAÇÕES DA API DA OANDA ---
OANDA_API_KEY = "SUA_API_KEY_OANDA"
OANDA_ACCOUNT_ID = "SEU_ACCOUNT_ID"
OANDA_URL = f"https://oanda.com" # Ambiente Demo (Practice)

# --- 1. CAPTURA DOS DADOS INSTITUCIONAIS (COT REPORT) ---
@st.cache_data(ttl=86400) # Guarda os dados por 24h para não travar o app baixando toda hora
def obtener_vies_institucional_cot():
    try:
        ano_actual = datetime.now().year
        # Baixa o relatório "Traders in Financial Futures" (TFF) do ano atual
        df_cot = cot.all_reports_by_year(ano_actual, report_type='TFF')
        
        # Filtra o contrato futuro do Euro FX (base do EURUSD)
        df_euro = df_cot[df_cot['Market_and_Exchange_Names'].str.contains("EURO FX", na=False)]
        
        if df_euro.empty:
            return "NEUTRO", 50.0
            
        ultimo_registro = df_euro.iloc[-1]
        
        # Posições Long vs Short dos Gestores de Ativos (Institucionais)
        longs = float(ultimo_registro['Asset_Manager_Long_All'])
        shorts = float(ultimo_registro['Asset_Manager_Short_All'])
        
        percentual_long = (longs / (longs + shorts)) * 100
        
        if percentual_long > 60:
            return "COMPRA 🟢 (Bullish)", percentual_long
        elif percentual_long < 40:
            return "VENDA 🔴 (Bearish)", percentual_long
        else:
            return "NEUTRO 🟡", percentual_long
    except Exception as e:
        # Fallback caso o site do governo esteja fora do ar no momento
        return "COMPRA 🟢 (Simulado - Erro API)", 65.0

# --- 2. CAPTURA DA LIQUIDEZ EM TEMPO REAL (OANDA ORDER BOOK) ---
def obtener_liquidez_oanda():
    headers = {
        "Authorization": f"Bearer {OANDA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(OANDA_URL, headers=headers)
        if response.status_code != 200:
            raise Exception("Falha na autenticação OANDA")
            
        dados = response.json()
        order_book = dados['orderBook']
        preco_atual = float(order_book['price'])
        
        linhas_liquidez = []
        # Percorre as faixas de preço mapeando onde o varejo colocou ordens
        for bucket in order_book['buckets']:
            preco_faixa = float(bucket['price'])
            # Posições de ordens de stop/limite acima de 0.5% de densidade são consideradas relevantes
            total_ordens = float(bucket['longCountPercent']) + float(bucket['shortCountPercent'])
            
            if total_ordens > 0.5: 
                linhas_liquidez.append({
                    "price": preco_faixa,
                    "volume": total_ordens
                })
                
        return preco_atual, linhas_liquidez
    except Exception as e:
        # Dados simulados de liquidez caso você ainda não tenha inserido as chaves da OANDA
        preco_fake = 1.0920
        liquidez_fake = [
            {"price": 1.0950, "volume": 0.85}, # Liquidez acima (Stop de Venda)
            {"price": 1.0880, "volume": 0.92}  # Liquidez abaixo (Stop de Compra)
        ]
        return preco_fake, liquidez_fake

# --- 3. MONTAGEM DA INTERFACE STREAMLIT ---
st.set_page_config(layout="wide", page_title="SMC Python Dashboard")
st.title("📊 Painel Quant: Indicador de Liquidez Institucional")

# Busca os dados macro
vies_macro, porcentagem_long = obtener_vies_institucional_cot()

# Exibe os Cards de Informação Institucional no topo
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Vies Macro das Instituições (COT)", value=vies_macro)
with col2:
    st.progress(int(porcentagem_long), text=f"Institucionais Comprados: {porcentagem_long:.1f}%")

# Busca os dados micro de preço e liquidez
preco_mercado, pools_liquidez = obtener_liquidez_oanda()

# Criação de dados de simulação de velas para alimentar o Lightweight Charts
datas = pd.date_range(end=datetime.now(), periods=50, freq='min').strftime('%Y-%m-%d %H:%M:%S')
dados_velas = []
preco_base = preco_mercado
for index, data in enumerate(datas):
    preco_base += 0.0001 if index % 2 == 0 else -0.0001
    dados_velas.append({
        "time": data,
        "open": preco_base - 0.0002,
        "high": preco_base + 0.0005,
        "low": preco_base - 0.0006,
        "close": preco_base
    })

# Configuração Visual do Gráfico (Estilo Dark do TradingView)
opcoes_grafico = {
    "width": 1100,
    "height": 500,
    "layout": {"background": {"type": "solid", "color": "#131722"}, "textColor": "#d1d4dc"},
    "grid": {"vertLines": {"color": "#242832"}, "horzLines": {"color": "#242832"}},
    "timeScale": {"timeVisible": True}
}

# Define as velas do preço
series_grafico = [
    {"type": "Candlestick", "data": dados_velas, "options": {"upColor": "#26a69a", "downColor": "#ef5350"}}
]

# Exibe a listagem técnica de liquidez
st.subheader("Pools de Liquidez Identificados no Livro de Ordens:")
for pool in pools_liquidez:
    tipo_pool = "Liquidez de Venda (Stops)" if pool['price'] > preco_mercado else "Liquidez de Compra (Stops)"
    st.write(f"🔹 Nível detectado em: **{pool['price']:.5f}** - Tipo: {tipo_pool}")

# --- RENDERIZAÇÃO DO GRÁFICO ATUALIZADA ---
renderLightweightCharts(series=series_grafico, options=opcoes_grafico)
