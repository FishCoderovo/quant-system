"""
技术指标计算
"""
import pandas as pd
import numpy as np

def calculate_ma(df: pd.DataFrame, periods: list = [5, 10, 20]) -> pd.DataFrame:
    """计算移动平均线"""
    for period in periods:
        df[f'ma{period}'] = df['close'].rolling(window=period).mean()
    return df

def calculate_ema(df: pd.DataFrame, periods: list = [5, 10, 20]) -> pd.DataFrame:
    """计算指数移动平均线"""
    for period in periods:
        df[f'ema{period}'] = df['close'].ewm(span=period, adjust=False).mean()
    return df

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """计算 RSI"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2) -> pd.DataFrame:
    """计算布林带"""
    df['bb_middle'] = df['close'].rolling(window=period).mean()
    df['bb_std'] = df['close'].rolling(window=period).std()
    df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * std_dev)
    df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * std_dev)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    return df

def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """计算 MACD"""
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd'] = ema_fast - ema_slow
    df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    return df

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """计算 ATR (平均真实波幅)"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['atr'] = true_range.rolling(period).mean()
    return df

def calculate_pivot_points(df: pd.DataFrame) -> pd.DataFrame:
    """计算枢轴点和支撑阻力位"""
    # 使用最新一根K线
    high = df['high'].iloc[-1]
    low = df['low'].iloc[-1]
    close = df['close'].iloc[-1]
    
    p = (high + low + close) / 3
    r1 = 2 * p - low
    s1 = 2 * p - high
    r2 = p + (high - low)
    s2 = p - (high - low)
    
    df['pivot'] = p
    df['r1'] = r1
    df['s1'] = s1
    df['r2'] = r2
    df['s2'] = s2
    return df

def calculate_volume_ma(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """计算成交量均线"""
    df['volume_ma'] = df['volume'].rolling(window=period).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']
    return df

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算所有指标"""
    df = calculate_ma(df)
    df = calculate_ema(df)
    df = calculate_rsi(df)
    df = calculate_bollinger_bands(df)
    df = calculate_macd(df)
    df = calculate_atr(df)
    df = calculate_pivot_points(df)
    df = calculate_volume_ma(df)
    return df
