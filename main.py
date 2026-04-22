from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from line_handler import handle_callback
from admin_router import router as admin_router
from config import Config
import bus_service

app = FastAPI(title="Bus Quality Report System")

# CORS — 允許 Vercel 前端跨域呼叫 /bus/* 端點
# 包含所有 HTTP Methods 以確保 LINE Webhook（POST）不受影響
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bus-map-smoky.vercel.app"],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 靜態檔案與 Admin 路由
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(admin_router)

print("==> Application initializing...")

# ─────────────────────────────────────────
# 基本路由
# ─────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "Bus Report System is running"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/webhook")
async def callback(request: Request, x_line_signature: str = Header(None)):
    if not x_line_signature:
        raise HTTPException(status_code=400, detail="Missing Signature")

    body = await request.body()
    try:
        await handle_callback(body.decode("utf-8"), x_line_signature)
    except Exception as e:
        import traceback
        print("--- Webhook Error Detailed ---")
        traceback.print_exc()
        print("------------------------------")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return "OK"

@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

# ─────────────────────────────────────────
# Bus Map API
# ─────────────────────────────────────────

@app.get("/bus/cities")
async def get_cities():
    """回傳所有啟用城市清單，供前端下拉選單使用。"""
    try:
        return bus_service.fetch_cities()
    except Exception as e:
        print(f"[/bus/cities] Error: {e}")
        raise HTTPException(status_code=500, detail="無法取得城市清單")


@app.get("/bus/status")
async def get_bus_status(city: str = "Tainan"):
    """
    取得指定城市所有受監控公車的整合狀態。
    Query param: ?city=Tainan | Kaohsiung | ...
    """
    try:
        return bus_service.fetch_bus_status(city)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"資料取得失敗: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
