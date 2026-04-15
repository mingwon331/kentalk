import os
import tempfile
from datetime import datetime, time
from zoneinfo import ZoneInfo

import gspread
from fastapi import FastAPI, Request
from google.oauth2.service_account import Credentials

from core_menu import extract_core_menu

app = FastAPI()

SPREADSHEET_ID = "1zQ0rIZ3Kt-V16NfRvWQvdQvabjF36xCHE9mbWuNncGA"
WORKSHEET_NAME = "dining_menu"
COMMAND_WORKSHEET_NAME = "command"
TODAY_WORKSHEET_NAME = "today"
SALAD_WORKSHEET_NAME = "salad"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

KST = ZoneInfo("Asia/Seoul")

# 후식에서 제외할 키워드
DESSERT_BLACKLIST = ["셀프후라이"]

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
worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
command_worksheet = spreadsheet.worksheet(COMMAND_WORKSHEET_NAME)
today_worksheet = spreadsheet.worksheet(TODAY_WORKSHEET_NAME)
salad_worksheet = spreadsheet.worksheet(SALAD_WORKSHEET_NAME)

# =========================
# 2. 헬스체크
# =========================
@app.get("/")
def root():
    return {"status": "ok"}

# =========================
# 3. 공통 유틸
# =========================
def get_today_str():
    return datetime.now(KST).strftime("%Y%m%d")

def clean_text(value):
    return (value or "").strip()

def format_date_md(date_str: str) -> str:
    """20260415 -> 04.15"""
    if not date_str or len(date_str) < 8:
        return ""
    return f"{date_str[4:6]}.{date_str[6:8]}"

def format_core_label(core_list) -> str:
    if not core_list:
        return "<정보 없음>"
    cleaned = [c.split('*')[0].strip() for c in core_list]
    return f"<{'. '.join(cleaned)}>"

def filter_dessert(dessert_raw: str) -> str:
    if not dessert_raw:
        return ""
    items = [d.strip() for d in dessert_raw.split('/') if d.strip()]
    filtered = [d for d in items if not any(b in d for b in DESSERT_BLACKLIST)]
    return "/".join(filtered)

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

# =========================
# 4. salad 시트 읽기
# 구조:
#   B1:H1 = 월~일
#   A2:A4 = 조식, 중식, 석식
#   B2:H4 = 각 요일/식사 메뉴
# =========================
def get_weekday_col_index():
    """
    월요일=2(B), 화=3(C), ..., 일요일=8(H)
    datetime.weekday(): 월=0 ... 일=6
    """
    return 2 + datetime.now(KST).weekday()

def get_salad_menu(meal_type: str) -> str:
    """
    meal_type:
      breakfast -> 2행
      lunch     -> 3행
      dinner    -> 4행
    """
    meal_row_map = {
        "breakfast": 2,
        "lunch": 3,
        "dinner": 4,
    }

    row_idx = meal_row_map.get(meal_type)
    col_idx = get_weekday_col_index()

    if row_idx is None:
        return ""

    try:
        value = salad_worksheet.cell(row_idx, col_idx).value
        return clean_text(value)
    except Exception:
        return ""

def build_salad_section(meal_type: str) -> str:
    salad_menu = get_salad_menu(meal_type)

    if not salad_menu:
        return ""

    return f"\n\n[샐러드 코너]\n{salad_menu}"

# =========================
# 5. 현재 시간 기준 식사 구분
# =========================
def get_current_meal_info():
    now_time = datetime.now(KST).time()

    if time(1, 0, 0) <= now_time <= time(8, 59, 59):
        return {"meal_name": "아침", "meal_type": "breakfast"}
    elif time(9, 0, 0) <= now_time <= time(13, 59, 59):
        return {"meal_name": "점심", "meal_type": "lunch"}
    elif time(14, 0, 0) <= now_time <= time(23, 59, 59):
        return {"meal_name": "저녁", "meal_type": "dinner"}
    else:
        return None

# =========================
# 6. 응답 텍스트 빌더 (학식)
# =========================
def build_single_meal_text(data: dict, meal_type: str) -> str:
    if data is None:
        return "오늘 학식 정보가 아직 등록되지 않았습니다."

    restaurant = clean_text(data.get("restaurant", "")) or "에디슨생활관식당"
    date_md = format_date_md(data.get("date", ""))

    meal_map = {
        "breakfast": ("아침", "breakfast", "breakfast_dessert"),
        "lunch":     ("점심", "lunch",     "lunch_dessert"),
        "dinner":    ("저녁", "dinner",    "dinner_dessert"),
    }

    if meal_type not in meal_map:
        return "잘못된 식사 종류입니다."

    meal_name, menu_key, dessert_key = meal_map[meal_type]
    menu_raw = clean_text(data.get(menu_key, ""))
    dessert_raw = clean_text(data.get(dessert_key, ""))

    if not menu_raw:
        return f"오늘 {meal_name} 메뉴 데이터가 없습니다."

    header = f"🍽️ {date_md} {restaurant} {meal_name} 메뉴"

    core_result = extract_core_menu(menu_raw, top_k=1)

    body_parts = []
    if not core_result:
        body_parts.append(f"핵심 메뉴: <정보 없음>\n{menu_raw}")
    elif len(core_result) == 1 and "MAIN" in core_result:
        info = core_result["MAIN"]
        core_label = format_core_label(info["core"])
        items_text = "\n".join(info["items"])
        body_parts.append(f"핵심 메뉴: {core_label}\n{items_text}")
    else:
        for corner_name, info in core_result.items():
            if corner_name == "MAIN":
                continue
            core_label = format_core_label(info["core"])
            items_text = "\n".join(info["items"])
            body_parts.append(f"[{corner_name}] - 핵심 메뉴: {core_label}\n{items_text}")

    body = "\n\n".join(body_parts)

    salad_text = build_salad_section(meal_type)

    dessert_text = ""
    dessert_filtered = filter_dessert(dessert_raw)
    if dessert_filtered:
        dessert_text = f"\n\n[후식]\n{dessert_filtered}"

    return f"{header}\n{body}{salad_text}{dessert_text}"

def build_meal_text(data: dict) -> str:
    """전체 식단 (조식+중식+석식 모두)"""
    if data is None:
        return "오늘 학식 정보가 아직 등록되지 않았습니다."

    parts = []
    for mt in ("breakfast", "lunch", "dinner"):
        parts.append(build_single_meal_text(data, mt))

    return "\n\n━━━━━━━━━━━━━━\n\n".join(parts)

def build_now_meal_text(data: dict) -> str:
    meal_info = get_current_meal_info()

    if meal_info is None:
        return "현재는 메뉴 갱신 시간입니다.\n오전 1시 이후 다시 조회해주세요."

    if data is None:
        return "오늘 학식 정보가 아직 등록되지 않았습니다."

    return build_single_meal_text(data, meal_info["meal_type"])

# =========================
# 7. 명령어 목록 빌더
# =========================
def build_command_text() -> str:
    rows = command_worksheet.get_all_values()

    if not rows or len(rows) < 2:
        return "명령어 정보를 불러올 수 없습니다."

    lines = ["📋 KENTALK 명령어 목록\n"]

    for row in rows[1:]:
        if not row or not row[0].strip():
            continue

        cmd_name = row[0].strip()
        keywords = [k.strip() for k in row[1:] if k.strip()]

        if keywords:
            lines.append(f"• {cmd_name}\n  입력어: {', '.join(keywords)}")
        else:
            lines.append(f"• {cmd_name}")

    return "\n\n".join(lines)

# =========================
# 8. 오늘의 추천곡 빌더
# =========================
def build_song_text() -> str:
    """today 시트 B열에서 오늘 날짜에 해당하는 추천곡 읽기"""
    today = get_today_str()
    all_values = today_worksheet.get_all_values()

    for row in all_values[1:]:
        date_cell = row[0].strip() if len(row) > 0 else ""
        song_cell = row[1].strip() if len(row) > 1 else ""

        if date_cell == today:
            if not song_cell:
                return "오늘의 추천곡이 아직 등록되지 않았습니다. 🎵"

            date_md = format_date_md(today)
            return f"🎵 {date_md} 오늘의 추천곡\n\n{song_cell}"

    return "오늘의 추천곡 정보를 찾을 수 없습니다."

# =========================
# 9. 카카오 챗봇 응답 포맷
# =========================
def kakao_response(text: str):
    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {"simpleText": {"text": text}}
            ]
        }
    }

# =========================
# 10. 카카오 챗봇 스킬 엔드포인트
# =========================
@app.post("/skill/dining")
async def dining(request: Request):
    _ = await request.json()
    data = get_today_row()
    return kakao_response(build_now_meal_text(data))

@app.post("/skill/today-dining")
async def today_dining(request: Request):
    _ = await request.json()
    data = get_today_row()
    return kakao_response(build_meal_text(data))

@app.post("/skill/now-dining")
async def now_dining(request: Request):
    _ = await request.json()
    data = get_today_row()
    return kakao_response(build_now_meal_text(data))

@app.post("/skill/breakfast")
async def breakfast(request: Request):
    _ = await request.json()
    data = get_today_row()
    return kakao_response(build_single_meal_text(data, "breakfast"))

@app.post("/skill/lunch")
async def lunch(request: Request):
    _ = await request.json()
    data = get_today_row()
    return kakao_response(build_single_meal_text(data, "lunch"))

@app.post("/skill/dinner")
async def dinner(request: Request):
    _ = await request.json()
    data = get_today_row()
    return kakao_response(build_single_meal_text(data, "dinner"))

@app.post("/skill/command")
async def command(request: Request):
    _ = await request.json()
    return kakao_response(build_command_text())

@app.post("/skill/song")
async def song(request: Request):
    _ = await request.json()
    return kakao_response(build_song_text())
