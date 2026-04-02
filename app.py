import os
import tempfile
import threading
from datetime import datetime, time
from zoneinfo import ZoneInfo

import gspread
from fastapi import FastAPI, Request
from google.oauth2.service_account import Credentials

app = FastAPI()

SPREADSHEET_ID = "1zQ0rIZ3Kt-V16NfRvWQvdQvabjF36xCHE9mbWuNncGA"
WORKSHEET_INDEX = 0

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

KST = ZoneInfo("Asia/Seoul")

# =========================
# 1. 인증
# =========================
if "GOOGLE_SERVICE_ACCOUNT_JSON" in os.environ:
    service_account_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(service_account_json)
        creds_path = f.name
else:
    creds_path = r"C:\Users\Kim\Desktop\KENTECH\KENTALK\kentalk-490316-d7c1fe0f6909.json"

creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(SPREADSHEET_ID)
worksheet = spreadsheet.get_worksheet(WORKSHEET_INDEX)

# =========================
# 2. 캐시
# =========================
CACHE_LOCK = threading.Lock()
TODAY_CACHE = {
    "date": None,          # YYYYMMDD
    "data": None,          # 오늘 메뉴 dict
    "fetched_at": None,    # datetime
}
CACHE_SECONDS = 180

MEAL_MAP = {
    "아침": ("breakfast", "breakfast_dessert"),
    "점심": ("lunch", "lunch_dessert"),
    "저녁": ("dinner", "dinner_dessert"),
}

# =========================
# 3. 공통 함수
# =========================
@app.get("/")
def root():
    return {"status": "ok"}

def get_now_kst():
    return datetime.now(KST)

def get_today_str():
    return get_now_kst().strftime("%Y%m%d")

def clean_text(value):
    return (value or "").strip()

def is_cache_valid():
    if TODAY_CACHE["date"] != get_today_str():
        return False
    if TODAY_CACHE["data"] is None:
        return False
    if TODAY_CACHE["fetched_at"] is None:
        return False

    age = (get_now_kst() - TODAY_CACHE["fetched_at"]).total_seconds()
    return age <= CACHE_SECONDS

def fetch_today_row_from_sheet():
    today = get_today_str()
    all_values = worksheet.get_all_values()

    for row in all_values[1:]:
        if len(row) > 0 and row[0] == today:
            return {
                "date": row[0] if len(row) > 0 else "",
                "day": row[1] if len(row) > 1 else "",
                "restaurant": row[2] if len(row) > 2 else "",
                "breakfast": row[3] if len(row) > 3 else "",
                "breakfast_dessert": row[4] if len(row) > 4 else "",
                "lunch": row[5] if len(row) > 5 else "",
                "lunch_dessert": row[6] if len(row) > 6 else "",
                "dinner": row[7] if len(row) > 7 else "",
                "dinner_dessert": row[8] if len(row) > 8 else "",
                "updated_at": row[9] if len(row) > 9 else "",
            }
    return None

def get_today_row():
    with CACHE_LOCK:
        if is_cache_valid():
            return TODAY_CACHE["data"]

        try:
            data = fetch_today_row_from_sheet()
            TODAY_CACHE["date"] = get_today_str()
            TODAY_CACHE["data"] = data
            TODAY_CACHE["fetched_at"] = get_now_kst()
            return data
        except Exception:
            # 시트 읽기 실패 시, 오늘 캐시가 남아 있으면 그걸이라도 반환
            if TODAY_CACHE["date"] == get_today_str() and TODAY_CACHE["data"] is not None:
                return TODAY_CACHE["data"]
            raise

def get_current_meal_name():
    now_time = get_now_kst().time()

    if time(1, 0, 0) <= now_time <= time(8, 59, 59):
        return "아침"
    elif time(9, 0, 0) <= now_time <= time(13, 59, 59):
        return "점심"
    elif time(14, 0, 0) <= now_time <= time(23, 59, 59):
        return "저녁"
    else:
        return None

# =========================
# 4. 응답 텍스트 생성
# =========================
def build_all_meal_text(data: dict) -> str:
    if data is None:
        return "오늘 학식 정보가 아직 등록되지 않았습니다."

    return (
        f"{data['restaurant']}\n"
        f"{data['date']} ({data['day']})\n\n"
        f"[조식]\n{data['breakfast'] or '정보 없음'}\n\n"
        f"[조식 후식]\n{data['breakfast_dessert'] or '없음'}\n\n"
        f"[중식]\n{data['lunch'] or '정보 없음'}\n\n"
        f"[중식 후식]\n{data['lunch_dessert'] or '없음'}\n\n"
        f"[석식]\n{data['dinner'] or '정보 없음'}\n\n"
        f"[석식 후식]\n{data['dinner_dessert'] or '없음'}"
    )

def build_single_meal_text(data: dict, meal_name: str) -> str:
    if data is None:
        return "오늘 학식 정보가 아직 등록되지 않았습니다."

    if meal_name not in MEAL_MAP:
        return "잘못된 식사 종류입니다."

    menu_key, dessert_key = MEAL_MAP[meal_name]

    restaurant = clean_text(data.get("restaurant", "")) or "생활관 식당"
    menu = clean_text(data.get(menu_key, ""))
    dessert = clean_text(data.get(dessert_key, ""))

    if not menu:
        return f"오늘 {meal_name} 메뉴 데이터가 없습니다."

    text = f"[{restaurant} {meal_name} 메뉴]\n{menu}"

    if dessert:
        text += f"\n\n[후식]\n{dessert}"

    return text

def build_now_meal_text(data: dict) -> str:
    meal_name = get_current_meal_name()

    if meal_name is None:
        return "현재는 메뉴 갱신 시간입니다.\n오전 1시 이후 다시 조회해주세요."

    return build_single_meal_text(data, meal_name)

def route_by_block_name(block_name: str, utterance: str, data: dict) -> str:
    block_name = clean_text(block_name)
    utterance = clean_text(utterance)

    if block_name == "지금 밥" or utterance in ["지금 밥", "지금 메뉴"]:
        return build_now_meal_text(data)

    if block_name == "아침" or utterance == "아침":
        return build_single_meal_text(data, "아침")

    if block_name == "점심" or utterance == "점심":
        return build_single_meal_text(data, "점심")

    if block_name == "저녁" or utterance == "저녁":
        return build_single_meal_text(data, "저녁")

    return build_all_meal_text(data)

# =========================
# 5. 카카오 스킬 공통 처리
# =========================
async def dining_handler(request: Request):
    try:
        body = await request.json()

        block_name = body.get("userRequest", {}).get("block", {}).get("name", "")
        utterance = body.get("userRequest", {}).get("utterance", "")

        data = get_today_row()
        text = route_by_block_name(block_name, utterance, data)

    except Exception:
        text = "메뉴를 불러오는 중 잠시 문제가 발생했습니다. 잠시 후 다시 시도해주세요."

    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": text
                    }
                }
            ]
        }
    }

@app.post("/skill/dining")
async def dining(request: Request):
    return await dining_handler(request)

@app.post("/skill/today-dining")
async def today_dining(request: Request):
    return await dining_handler(request)

@app.post("/skill/now-dining")
async def now_dining(request: Request):
    return await dining_handler(request)

@app.post("/skill/breakfast")
async def breakfast(request: Request):
    return await dining_handler(request)

@app.post("/skill/lunch")
async def lunch(request: Request):
    return await dining_handler(request)

@app.post("/skill/dinner")
async def dinner(request: Request):
    return await dining_handler(request)
