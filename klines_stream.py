import websockets

async def stream_klines():
    uri = "wss://fapi.asterdex.com/ws/btcusdt@kline_1m"
    async with websockets.connect(uri) as websocket:
        while True:
            msg = await websocket.recv()
            print("Kline:", msg)

# asyncio.run(stream_klines())  # Commented for manual start
