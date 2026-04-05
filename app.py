import os
import tempfile
import threading
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import gspread
from fastapi import FastAPI, Request
from google.oauth2.service_account import Credentials

app = FastAPI()

SPREADSHEET_ID = "1zQ0rIZ3Kt-V16NfRvWQvdQvabjF36xCHE9mbWuNncGA"

DINING_SHEET_NAME = "dining_menu"
SALAD_SHEET_NAME = "salad"
COMMAND_SHEET_NAME = "command"

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
worksheet_dining = spreadsheet.worksheet(DINING_SHEET_NAME)
worksheet_salad = spreadsheet.worksheet(SALAD_SHEET_NAME)
worksheet_command = spreadsheet.worksheet(COMMAND_SHEET_NAME)

# =========================
# 2. 캐시
# =========================
CACHE_LOCK = threading.Lock()

DINING_CACHE = {
    "date": None,
    "data": None,
    "fetched_at": None,
}

SALAD_CACHE = {
    "table": None,
    "fetched_at": None,
}

COMMAND_CACHE = {
    "rows": None,
    "fetched_at": None,
}

DINING_CACHE_SECONDS = 60
SALAD_CACHE_SECONDS = 300
COMMAND_CACHE_SECONDS = 300

DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]

DINING_MEAL_MAP = {
    "아침": ("breakfast", "breakfast_dessert"),
    "점심": ("lunch", "lunch_dessert"),
    "저녁": ("dinner", "dinner_dessert"),
}

SALAD_MEAL_MAP = {
    "아침": "조식",
    "점심": "중식",
    "저녁": "석식",
}

# =========================
# 3. 발화 alias
# =========================
NOW_DINING_ALIASES = {
    "밥", "학식", "ㅂ", "오늘학식", "학식메뉴", "학식 메뉴", "오늘 학식", "메뉴",
    "급식", "오늘 급식", "짬밥", "ㅉ"
}

BREAKFAST_DINING_ALIASES = {
    "조식", "아침", "아침메뉴", "아침 메뉴", "아침학식", "아침 학식", "ㅇㅊ", "아침 급식"
}

LUNCH_DINING_ALIASES = {
    "중식", "점심", "점심메뉴", "점심 메뉴", "점심학식", "점심 학식", "ㅈㅅ", "점심 급식"
}

DINNER_DINING_ALIASES = {
    "석식", "저녁", "저녁메뉴", "저녁 메뉴", "저녁학식", "저녁 학식", "ㅈㄴ", "저녁 급식"
}

NOW_SALAD_ALIASES = {
    "간편식"
}

BREAKFAST_SALAD_ALIASES = {
    "아침간편식", "아침 간편식", "ㅇㅊ ㄱ"
}

LUNCH_SALAD_ALIASES = {
    "점심간편식", "점심 간편식", "ㅈㅅ ㄱ"
}

DINNER_SALAD_ALIASES = {
    "저녁간편식", "저녁 간편식", "ㅈㄴ ㄱ"
}

COMMAND_ALIASES = {"/명령어"}
FEATURE_ALIASES = {"/기능"}

# =========================
# 4. 공통 함수
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

def format_aliases(words):
    cleaned = [clean_text(x) for x in words if clean_text(x)]
    return ", ".join([f'"{w}"' for w in cleaned])

# =========================
# 5. dining_menu 조회
# =========================
def is_dining_cache_valid():
    if DINING_CACHE["date"] != get_today_str():
        return False
    if DINING_CACHE["data"] is None:
        return False
    if DINING_CACHE["fetched_at"] is None:
        return False

    age = (get_now_kst() - DINING_CACHE["fetched_at"]).total_seconds()
    return age <= DINING_CACHE_SECONDS

def fetch_today_dining_row_from_sheet():
    today = get_today_str()
    all_values = worksheet_dining.get_all_values()

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

def get_today_dining_row():
    with CACHE_LOCK:
        if is_dining_cache_valid():
            return DINING_CACHE["data"]

        data = fetch_today_dining_row_from_sheet()
        DINING_CACHE["date"] = get_today_str()
        DINING_CACHE["data"] = data
        DINING_CACHE["fetched_at"] = get_now_kst()
        return data

def get_current_dining_meal_name():
    now_time = get_now_kst().time()

    # 00:00 ~ 03:59:59 => 업데이트 중
    if time(0, 0, 0) <= now_time < time(4, 0, 0):
        return None
    elif time(4, 0, 0) <= now_time < time(9, 0, 0):
        return "아침"
    elif time(9, 0, 0) <= now_time < time(14, 0, 0):
        return "점심"
    else:
        return "저녁"

def build_all_dining_text(data: dict) -> str:
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

def build_single_dining_text(data: dict, meal_name: str) -> str:
    if data is None:
        return "오늘 학식 정보가 아직 등록되지 않았습니다."

    if meal_name not in DINING_MEAL_MAP:
        return "잘못된 식사 종류입니다."

    menu_key, dessert_key = DINING_MEAL_MAP[meal_name]

    restaurant = clean_text(data.get("restaurant", "")) or "생활관 식당"
    menu = clean_text(data.get(menu_key, ""))
    dessert = clean_text(data.get(dessert_key, ""))

    if not menu:
        return f"오늘 {meal_name} 메뉴 데이터가 없습니다."

    text = f"[{restaurant} {meal_name} 메뉴]\n{menu}"

    if dessert:
        text += f"\n\n[후식]\n{dessert}"

    return text

def build_now_dining_text(data: dict) -> str:
    meal_name = get_current_dining_meal_name()

    if meal_name is None:
        return "현재는 학식 메뉴 업데이트 시간입니다.\n오전 4시 이후 다시 조회해주세요."

    return build_single_dining_text(data, meal_name)

def route_dining(block_name: str, utterance: str, data: dict) -> str:
    block_name = clean_text(block_name)
    utterance = clean_text(utterance)

    if block_name == "명령어 조회" or utterance in COMMAND_ALIASES:
        return build_command_text()

    if block_name == "기능 조회" or utterance in FEATURE_ALIASES:
        return build_feature_text()

    if block_name == "지금 밥" or utterance in NOW_DINING_ALIASES:
        return build_now_dining_text(data)

    if block_name == "아침" or utterance in BREAKFAST_DINING_ALIASES:
        return build_single_dining_text(data, "아침")

    if block_name == "점심" or utterance in LUNCH_DINING_ALIASES:
        return build_single_dining_text(data, "점심")

    if block_name == "저녁" or utterance in DINNER_DINING_ALIASES:
        return build_single_dining_text(data, "저녁")

    return build_all_dining_text(data)

# =========================
# 6. salad 시트 조회
# =========================
def is_salad_cache_valid():
    if SALAD_CACHE["table"] is None:
        return False
    if SALAD_CACHE["fetched_at"] is None:
        return False

    age = (get_now_kst() - SALAD_CACHE["fetched_at"]).total_seconds()
    return age <= SALAD_CACHE_SECONDS

def fetch_salad_table_from_sheet():
    values = worksheet_salad.get_all_values()

    if len(values) < 4:
        return {}

    day_headers = [clean_text(x) for x in values[0][1:8]]

    table = {}

    for row in values[1:4]:
        meal_label = clean_text(row[0])  # 조식 / 중식 / 석식
        menus = row[1:8]

        while len(menus) < len(day_headers):
            menus.append("")

        for day_name, menu in zip(day_headers, menus):
            table[(day_name, meal_label)] = clean_text(menu)

    return table

def get_salad_table():
    with CACHE_LOCK:
        if is_salad_cache_valid():
            return SALAD_CACHE["table"]

        table = fetch_salad_table_from_sheet()
        SALAD_CACHE["table"] = table
        SALAD_CACHE["fetched_at"] = get_now_kst()
        return table

def get_kor_day_name(target_dt: datetime):
    return DAY_NAMES[target_dt.weekday()]

def get_now_salad_target():
    now = get_now_kst()
    now_time = now.time()

    # 전날 20:00 ~ 다음날 09:00 -> 아침 간편식
    if now_time >= time(20, 0, 0):
        target_dt = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return get_kor_day_name(target_dt), "아침"

    if now_time < time(9, 0, 0):
        return get_kor_day_name(now), "아침"

    # 09:00 ~ 12:59:59 -> 점심 간편식
    if now_time < time(13, 0, 0):
        return get_kor_day_name(now), "점심"

    # 13:00 ~ 19:59:59 -> 저녁 간편식
    return get_kor_day_name(now), "저녁"

def get_fixed_salad_target(meal_name: str):
    now = get_now_kst()

    if meal_name == "아침":
        if now.time() >= time(20, 0, 0):
            target_dt = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return get_kor_day_name(target_dt), "아침"
        return get_kor_day_name(now), "아침"

    if meal_name == "점심":
        return get_kor_day_name(now), "점심"

    if meal_name == "저녁":
        return get_kor_day_name(now), "저녁"

    return get_kor_day_name(now), meal_name

def build_salad_text(day_name: str, meal_name: str) -> str:
    table = get_salad_table()
    sheet_meal_name = SALAD_MEAL_MAP[meal_name]
    menu = clean_text(table.get((day_name, sheet_meal_name), ""))

    if not menu or menu == "미운영":
        return f"[{day_name}요일 {meal_name} 간편식]\n미운영"

    return f"[{day_name}요일 {meal_name} 간편식]\n{menu}"

def route_salad(block_name: str, utterance: str) -> str:
    block_name = clean_text(block_name)
    utterance = clean_text(utterance)

    if block_name == "명령어 조회" or utterance in COMMAND_ALIASES:
        return build_command_text()

    if block_name == "기능 조회" or utterance in FEATURE_ALIASES:
        return build_feature_text()

    if block_name == "간편식" or utterance in NOW_SALAD_ALIASES:
        day_name, meal_name = get_now_salad_target()
        return build_salad_text(day_name, meal_name)

    if block_name == "아침 간편식" or utterance in BREAKFAST_SALAD_ALIASES:
        day_name, meal_name = get_fixed_salad_target("아침")
        return build_salad_text(day_name, meal_name)

    if block_name == "점심 간편식" or utterance in LUNCH_SALAD_ALIASES:
        day_name, meal_name = get_fixed_salad_target("점심")
        return build_salad_text(day_name, meal_name)

    if block_name == "저녁 간편식" or utterance in DINNER_SALAD_ALIASES:
        day_name, meal_name = get_fixed_salad_target("저녁")
        return build_salad_text(day_name, meal_name)

    return "간편식 관련 명령을 찾지 못했습니다. /명령어 를 입력해보세요."

# =========================
# 7. command 시트 조회
# =========================
def is_command_cache_valid():
    if COMMAND_CACHE["rows"] is None:
        return False
    if COMMAND_CACHE["fetched_at"] is None:
        return False

    age = (get_now_kst() - COMMAND_CACHE["fetched_at"]).total_seconds()
    return age <= COMMAND_CACHE_SECONDS

def fetch_command_rows_from_sheet():
    values = worksheet_command.get_all_values()
    return values

def get_command_rows():
    with CACHE_LOCK:
        if is_command_cache_valid():
            return COMMAND_CACHE["rows"]

        rows = fetch_command_rows_from_sheet()
        COMMAND_CACHE["rows"] = rows
        COMMAND_CACHE["fetched_at"] = get_now_kst()
        return rows

def build_command_text():
    rows = get_command_rows()

    if not rows or len(rows) < 2:
        return "명령어 정보가 아직 등록되지 않았습니다."

    lines = ["[사용 가능한 명령어]"]

    for row in rows[1:]:
        if not row:
            continue

        title_raw = clean_text(row[0]) if len(row) > 0 else ""
        aliases = [clean_text(x) for x in row[1:] if clean_text(x)]

        if not title_raw:
            continue

        title_lines = [x.strip() for x in title_raw.split("\n") if x.strip()]
        title = title_lines[0]
        notes = title_lines[1:]

        if aliases:
            lines.append(f"{title}: {format_aliases(aliases)}")
        else:
            lines.append(f"{title}")

        for note in notes:
            lines.append(f"- {note}")

    text = "\n".join(lines)

    if len(text) > 1000:
        text = text[:995] + "..."

    return text

def build_feature_text():
    return (
        "[기능 안내]\n"
        "학식 조회\n"
        "간편식 조회\n\n"
        "자세한 입력어는 /명령어 로 확인해주세요."
    )

# =========================
# 8. 핸들러
# =========================
async def dining_handler(request: Request):
    try:
        body = await request.json()
        block_name = body.get("userRequest", {}).get("block", {}).get("name", "")
        utterance = body.get("userRequest", {}).get("utterance", "")

        data = get_today_dining_row()
        text = route_dining(block_name, utterance, data)
    except Exception:
        text = "학식 메뉴를 불러오는 중 잠시 문제가 발생했습니다. 잠시 후 다시 시도해주세요."

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

async def salad_handler(request: Request):
    try:
        body = await request.json()
        block_name = body.get("userRequest", {}).get("block", {}).get("name", "")
        utterance = body.get("userRequest", {}).get("utterance", "")

        text = route_salad(block_name, utterance)
    except Exception:
        text = "간편식 메뉴를 불러오는 중 잠시 문제가 발생했습니다. 잠시 후 다시 시도해주세요."

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

async def command_handler(request: Request):
    try:
        body = await request.json()
        utterance = clean_text(body.get("userRequest", {}).get("utterance", ""))

        if utterance in FEATURE_ALIASES:
            text = build_feature_text()
        else:
            text = build_command_text()
    except Exception:
        text = "명령어 정보를 불러오는 중 잠시 문제가 발생했습니다. 잠시 후 다시 시도해주세요."

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

# =========================
# 9. 엔드포인트
# =========================
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

@app.post("/skill/salad")
async def salad(request: Request):
    return await salad_handler(request)

@app.post("/skill/command")
async def command(request: Request):
    return await command_handler(request)
