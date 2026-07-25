import pandas as pd

def calcular_sma(df_velas, janela=20):
    """Calcula a Média Móvel Simples (SMA)."""
    df = pd.DataFrame(df_velas)
    if "close" not in df.columns:
        return []

    df["sma"] = df["close"].rolling(window=janela).mean().bfill()
    return [{"time": int(row["time"]), "value": float(row["sma"])} for _, row in df.iterrows()]

def calcular_ema(df_velas, janela=9):
    """Calcula a Média Móvel Exponencial (EMA)."""
    df = pd.DataFrame(df_velas)
    if "close" not in df.columns:
        return []

    df["ema"] = df["close"].ewm(span=janela, adjust=False).mean()
    return [{"time": int(row["time"]), "value": float(row["ema"])} for _, row in df.iterrows()]
