import os
import tempfile
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
# 1. GitHub Actions / 로컬 둘 다 대응
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
# 2. 헬스체크
# =========================
@app.get("/")
def root():
    return {"status": "ok"}

# =========================
# 3. 오늘 날짜 찾기 (한국 시간 기준)
# =========================
def get_today_str():
    return datetime.now(KST).strftime("%Y%m%d")

def clean_text(value):
    return (value or "").strip()

def get_today_row():
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

def build_meal_text(data: dict) -> str:
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

# =========================
# 4. 현재 시간 기준 식사 구분
# =========================
def get_current_meal_info():
    now_time = datetime.now(KST).time()

    if time(1, 0, 0) <= now_time <= time(8, 59, 59):
        return {
            "meal_name": "아침",
            "menu_key": "breakfast",
            "dessert_key": "breakfast_dessert",
        }
    elif time(9, 0, 0) <= now_time <= time(13, 59, 59):
        return {
            "meal_name": "점심",
            "menu_key": "lunch",
            "dessert_key": "lunch_dessert",
        }
    elif time(14, 0, 0) <= now_time <= time(23, 59, 59):
        return {
            "meal_name": "저녁",
            "menu_key": "dinner",
            "dessert_key": "dinner_dessert",
        }
    else:
        return None

def build_now_meal_text(data: dict) -> str:
    meal_info = get_current_meal_info()

    if meal_info is None:
        return "현재는 메뉴 갱신 시간입니다.\n오전 1시 이후 다시 조회해주세요."

    if data is None:
        return "오늘 학식 정보가 아직 등록되지 않았습니다."

    restaurant = clean_text(data.get("restaurant", "")) or "생활관 식당"
    meal_name = meal_info["meal_name"]
    menu = clean_text(data.get(meal_info["menu_key"], ""))
    dessert = clean_text(data.get(meal_info["dessert_key"], ""))

    if not menu:
        return f"오늘 {meal_name} 메뉴 데이터가 없습니다."

    text = f"[{restaurant} {meal_name} 메뉴]\n{menu}"

    if dessert:
        text += f"\n\n[후식]\n{dessert}"

    return text

# =========================
# 5. 카카오 챗봇 스킬 엔드포인트
# =========================
@app.post("/skill/today-dining")
async def today_dining(request: Request):
    _ = await request.json()

    data = get_today_row()

    if data is None:
        text = "오늘 학식 정보가 아직 등록되지 않았습니다."
    else:
        text = build_meal_text(data)

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

@app.post("/skill/now-dining")
async def now_dining(request: Request):
    _ = await request.json()

    data = get_today_row()
    text = build_now_meal_text(data)

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
