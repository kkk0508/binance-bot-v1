import os
import time
import pandas as pd
from datetime import datetime
from binance.client import Client
from dotenv import load_dotenv

# 1. 환경변수 로드
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

# 2. 바이낸스 클라이언트 초기화
client = Client(API_KEY, API_SECRET)

# 3. 기본 설정
symbol = "BTCUSDT"
interval = Client.KLINE_INTERVAL_1HOUR
leverage = 20

# 실전 계좌의 USDT 잔고를 조회하여 적용
def get_balance():
    balance_info = client.futures_account_balance()
    usdt = next(item for item in balance_info if item['asset'] == 'USDT')
    return float(usdt['balance'])

# 진입 조건 설정
def is_golden_cross(df):
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    return ema12.iloc[-2] < ema26.iloc[-2] and ema12.iloc[-1] > ema26.iloc[-1]

def is_range(df):
    rsi = compute_rsi(df['close'])
    return 35 <= rsi.iloc[-1] <= 65

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# 포지션 진입 함수 (실제 주문 체결 후만 출력)
def enter_position(entry_price, side, size):
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=Client.SIDE_BUY if side == 'LONG' else Client.SIDE_SELL,
            type=Client.ORDER_TYPE_MARKET,
            quantity=round(size, 3)
        )
        print(f"✅ 실전 주문 체결 완료 → 방향: {side}, 수량: {size}, 진입가: {entry_price}")
        return True
    except Exception as e:
        print("❌ 주문 실패:", e)
        return False

# 실시간 데이터 가져오기 (최근 100개 캔들)
def get_ohlcv(symbol, interval):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=100)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'num_trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['close'] = df['close'].astype(float)
    return df

# 메인 자동매매 루프
def run_bot():
    entry_count = 0
    print("\n[🟢 실전 자동매매 시작]")
    while True:
        balance = get_balance()
        df = get_ohlcv(symbol, interval)

        if is_golden_cross(df):
            side = 'LONG'
        elif is_range(df):
            side = 'GRID'
        else:
            print("신호 없음. 대기 중...")
            time.sleep(10)
            continue

        if entry_count >= 3:
            print("❗ 하루 진입 한도 초과. 다음 날까지 대기 중...")
            time.sleep(60 * 60)
            continue

        price = float(df['close'].iloc[-1])
        size = (balance * leverage) / price

        if enter_position(price, side, size):
            entry_count += 1

        time.sleep(60 * 60)

# 실행
run_bot()

