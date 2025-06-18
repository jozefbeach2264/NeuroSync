from fastapi import Request, APIRouter

router = APIRouter()

@router.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    print("Webhook received:", data)
    return {"status": "received"}
