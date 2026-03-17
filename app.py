import os
import tempfile
from datetime import datetime

import gspread
from fastapi import FastAPI, Request
from google.oauth2.service_account import Credentials

app = FastAPI()

# =========================
# 1. 환경변수 / Secrets
# =========================
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
SPREADSHEET_ID = "1zQ0rIZ3Kt-V16NfRvWQvdQvabjF36xCHE9mbWuNncGA"
WORKSHEET_INDEX = 0

# =========================
# 2. 서비스 계정 JSON 임시 파일 생성
# =========================
with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
    f.write(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds_path = f.name

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
client = gspread.authorize(creds)

spreadsheet = client.open_by_key(SPREADSHEET_ID)
worksheet = spreadsheet.get_worksheet(WORKSHEET_INDEX)

# =========================
# 3. 오늘 날짜 찾기
# =========================
def get_today_str():
    return datetime.now().strftime("%Y%m%d")

def get_today_row():
    today = get_today_str()
    all_values = worksheet.get_all_values()

    # 헤더 제외
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

@app.get("/")
def root():
    return {"status": "ok"}

# =========================
# 4. 카카오 챗봇 스킬 엔드포인트
# =========================
@app.post("/skill/today-dining")
async def today_dining(request: Request):
    body = await request.json()

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
