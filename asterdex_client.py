import asyncio
import websockets
import json

PAIR = "ethusdt"
URL = f"wss://fapi.asterdex.com/ws/{PAIR}@depth20@100ms"

# Core streaming logic (persistent + resilient)
async def asterdex_listener():
    while True:
        try:
            async with websockets.connect(URL, ping_interval=300, ping_timeout=600) as websocket:
                print(f"[CONNECTED] Listening to {PAIR} order book...")
                while True:
                    msg = await websocket.recv()
                    data = json.loads(msg)

                    bids = data.get("bids", [])
                    asks = data.get("asks", [])

                    if bids and asks:
                        print(f"[ASK] {asks[0]}  [BID] {bids[0]}")
                    else:
                        print("[WARNING] Empty bids or asks received")

        except Exception as e:
            print(f"[ERROR] {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

# Triggerable method for external startup (e.g. from main.py)
def start_asterdex_stream():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(asterdex_listener())
        else:
            loop.run_until_complete(asterdex_listener())
    except RuntimeError:
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        new_loop.run_until_complete(asterdex_listener())

# Standalone execution fallback
if __name__ == "__main__":
    asyncio.run(asterdex_listener())