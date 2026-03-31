from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from line_handler import handle_callback
from admin_router import router as admin_router
from config import Config

app = FastAPI(title="Bus Quality Report System")

# Mount Static Files for Admin Dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include Admin Router
app.include_router(admin_router)

@app.get("/")
async def root():
    return {"status": "Bus Report System is running"}

@app.get("/health")
async def health():
    return {"status": "ok"}

print("==> Application initializing...")

@app.post("/webhook")
async def callback(request: Request, x_line_signature: str = Header(None)):
    if not x_line_signature:
        raise HTTPException(status_code=400, detail="Missing Signature")
    
    body = await request.body()
    try:
        await handle_callback(body.decode("utf-8"), x_line_signature)
    except Exception as e:
        import traceback
        print(f"--- Webhook Error Detailed ---")
        traceback.print_exc()
        print(f"------------------------------")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
    return "OK"

@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
