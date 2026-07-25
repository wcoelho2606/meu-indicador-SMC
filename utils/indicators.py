import pandas as pd

def calcular_sma(df_velas, janela=20):
    """Calcula a Média Móvel Simples (SMA) compatível com Lightweight Charts."""
    df = pd.DataFrame(df_velas)
    if "close" not in df.columns or len(df) == 0:
        return []
    
    df["sma"] = df["close"].rolling(window=janela).mean()
    df = df.dropna(subset=["sma"]) # Remove valores nulos para evitar bugs de plotagem
    
    return [{"time": int(row["time"]), "value": float(row["sma"])} for _, row in df.iterrows()]

def calcular_ema(df_velas, janela=9):
    """Calcula a Média Móvel Exponencial (EMA) compatível com Lightweight Charts."""
    df = pd.DataFrame(df_velas)
    if "close" not in df.columns or len(df) == 0:
        return []
        
    df["ema"] = df["close"].ewm(span=janela, adjust=False).mean()
    df = df.dropna(subset=["ema"])
    
    return [{"time": int(row["time"]), "value": float(row["ema"])} for _, row in df.iterrows()]
