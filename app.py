import os
import tempfile
from datetime import datetime, time
from zoneinfo import ZoneInfo

import gspread
from fastapi import FastAPI, Request
from google.oauth2.service_account import Credentials

from core_menu import extract_core_menu
from name_compatibility import (
    is_name_compatibility_query,
    route_name_compatibility_by_utterance,
)

app = FastAPI()

SPREADSHEET_ID = "1zQ0rIZ3Kt-V16NfRvWQvdQvabjF36xCHE9mbWuNncGA"

WORKSHEET_NAME = "dining_menu"
SALAD_WORKSHEET_NAME = "salad"
COMMAND_WORKSHEET_NAME = "command"
TODAY_WORKSHEET_NAME = "today"
DELIVERY_WORKSHEET_NAME = "delivery"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

KST = ZoneInfo("Asia/Seoul")

DESSERT_BLACKLIST = ["셀프후라이"]


# =========================================================
# 1. Google Sheets 연결
# =========================================================
def get_google_credentials_path() -> str:
    if "GOOGLE_SERVICE_ACCOUNT_JSON" in os.environ:
        service_account_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(service_account_json)
            return f.name

    return r"C:\Users\Kim\Desktop\KENTECH\KENTALK\kentalk-490316-d7c1fe0f6909.json"


creds_path = get_google_credentials_path()
creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(SPREADSHEET_ID)

worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
salad_worksheet = spreadsheet.worksheet(SALAD_WORKSHEET_NAME)
command_worksheet = spreadsheet.worksheet(COMMAND_WORKSHEET_NAME)
today_worksheet = spreadsheet.worksheet(TODAY_WORKSHEET_NAME)
delivery_worksheet = spreadsheet.worksheet(DELIVERY_WORKSHEET_NAME)


# =========================================================
# 2. 헬스체크
# =========================================================
@app.get("/")
def root():
    return {"status": "ok"}


# =========================================================
# 3. 공통 유틸
# =========================================================
def kakao_response(text: str):
    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {"simpleText": {"text": text}}
            ]
        },
    }


def get_utterance(body: dict) -> str:
    try:
        return body.get("userRequest", {}).get("utterance", "") or ""
    except Exception:
        return ""


def get_today_str() -> str:
    return datetime.now(KST).strftime("%Y%m%d")


def clean_text(value) -> str:
    return (value or "").strip()


def format_date_md(date_str: str) -> str:
    if not date_str or len(date_str) < 8:
        return ""
    return f"{date_str[4:6]}.{date_str[6:8]}"


def format_core_label(core_list) -> str:
    if not core_list:
        return "<정보 없음>"
    cleaned = [c.split("*")[0].strip() for c in core_list]
    return f"<{', '.join(cleaned)}>"


def filter_dessert(dessert_raw: str) -> str:
    if not dessert_raw:
        return ""

    items = [d.strip() for d in dessert_raw.split("/") if d.strip()]
    filtered = [
        d for d in items
        if not any(black in d for black in DESSERT_BLACKLIST)
    ]

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


# =========================================================
# 4. 현재 시간 기준 식사 구분
# =========================================================
def get_current_meal_info():
    now_time = datetime.now(KST).time()

    if time(1, 0, 0) <= now_time <= time(8, 59, 59):
        return {"meal_name": "아침", "meal_type": "breakfast"}

    if time(9, 0, 0) <= now_time <= time(13, 59, 59):
        return {"meal_name": "점심", "meal_type": "lunch"}

    if time(14, 0, 0) <= now_time <= time(23, 59, 59):
        return {"meal_name": "저녁", "meal_type": "dinner"}

    return None


# =========================================================
# 5. 학식 응답
# =========================================================
def build_single_meal_text(data: dict, meal_type: str) -> str:
    if data is None:
        return "오늘 학식 정보가 아직 등록되지 않았습니다."

    restaurant = clean_text(data.get("restaurant", "")) or "에디슨생활관식당"
    date_md = format_date_md(data.get("date", ""))

    meal_map = {
        "breakfast": ("아침", "breakfast", "breakfast_dessert"),
        "lunch": ("점심", "lunch", "lunch_dessert"),
        "dinner": ("저녁", "dinner", "dinner_dessert"),
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
            body_parts.append(
                f"[{corner_name}] - 핵심 메뉴: {core_label}\n{items_text}"
            )

    body = "\n\n".join(body_parts)

    dessert_text = ""
    dessert_filtered = filter_dessert(dessert_raw)
    if dessert_filtered:
        dessert_text = f"\n\n[후식]\n{dessert_filtered}"

    return f"{header}\n{body}{dessert_text}"


def build_meal_text(data: dict) -> str:
    if data is None:
        return "오늘 학식 정보가 아직 등록되지 않았습니다."

    parts = []

    for meal_type in ("breakfast", "lunch", "dinner"):
        parts.append(build_single_meal_text(data, meal_type))

    return "\n\n━━━━━━━━━━━━━━\n\n".join(parts)


def build_now_meal_text(data: dict) -> str:
    meal_info = get_current_meal_info()

    if meal_info is None:
        return "현재는 메뉴 갱신 시간입니다.\n오전 1시 이후 다시 조회해주세요."

    if data is None:
        return "오늘 학식 정보가 아직 등록되지 않았습니다."

    return build_single_meal_text(data, meal_info["meal_type"])


# =========================================================
# 6. 간편식/샐러드 응답
# =========================================================
SALAD_MEAL_ROW = {
    "breakfast": 1,
    "lunch": 2,
    "dinner": 3,
}

SALAD_MEAL_NAME = {
    "breakfast": "조식",
    "lunch": "중식",
    "dinner": "석식",
}


def get_today_weekday_col_idx() -> int:
    return datetime.now(KST).weekday() + 1


def get_salad_cell(meal_type: str) -> str:
    if meal_type not in SALAD_MEAL_ROW:
        return ""

    all_values = salad_worksheet.get_all_values()
    row_idx = SALAD_MEAL_ROW[meal_type]
    col_idx = get_today_weekday_col_idx()

    if row_idx >= len(all_values):
        return ""

    row = all_values[row_idx]

    if col_idx >= len(row):
        return ""

    return row[col_idx].strip()


def build_single_salad_text(meal_type: str) -> str:
    if meal_type not in SALAD_MEAL_ROW:
        return "잘못된 식사 종류입니다."

    meal_name = SALAD_MEAL_NAME[meal_type]
    date_md = format_date_md(get_today_str())
    cell = get_salad_cell(meal_type)
    header = f"🥗 {date_md} 간편식 {meal_name}"

    if not cell or "미운영" in cell:
        return f"{header}\n오늘은 미운영입니다."

    return f"{header}\n\n{cell}"


def build_salad_all_text() -> str:
    date_md = format_date_md(get_today_str())
    parts = [f"🥗 {date_md} 간편식"]

    for meal_type in ("breakfast", "lunch", "dinner"):
        meal_name = SALAD_MEAL_NAME[meal_type]
        cell = get_salad_cell(meal_type)

        if not cell or "미운영" in cell:
            parts.append(f"[{meal_name}]\n미운영")
        else:
            parts.append(f"[{meal_name}]\n{cell}")

    return "\n\n".join(parts)


def build_now_salad_text() -> str:
    meal_info = get_current_meal_info()

    if meal_info is None:
        return "현재는 메뉴 갱신 시간입니다.\n오전 1시 이후 다시 조회해주세요."

    return build_single_salad_text(meal_info["meal_type"])


def route_salad_by_utterance(utterance: str) -> str:
    u = (utterance or "").lower().replace(" ", "")

    if any(kw in u for kw in ["전체", "오늘", "하루", "all", "전부", "모든"]):
        return build_salad_all_text()

    if any(kw in u for kw in ["조식", "아침", "breakfast"]):
        return build_single_salad_text("breakfast")

    if any(kw in u for kw in ["중식", "점심", "lunch"]):
        return build_single_salad_text("lunch")

    if any(kw in u for kw in ["석식", "저녁", "dinner"]):
        return build_single_salad_text("dinner")

    return build_now_salad_text()


# =========================================================
# 7. 명령어 목록 응답
# =========================================================
def build_command_text() -> str:
    rows = command_worksheet.get_all_values()

    if not rows or len(rows) < 2:
        return "명령어 정보를 불러올 수 없습니다."

    lines = ["📌 KENTALK 명령어 목록\n"]

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


# =========================================================
# 8. 오늘의 추천곡 응답
# =========================================================
def build_song_text() -> str:
    today = get_today_str()
    all_values = today_worksheet.get_all_values()

    for row in all_values[1:]:
        date_cell = row[0].strip() if len(row) > 0 else ""
        song_cell = row[1].strip() if len(row) > 1 else ""

        if date_cell == today:
            if not song_cell:
                return "오늘의 추천곡이 아직 등록되지 않았습니다."

            date_md = format_date_md(today)
            return f"🎧 {date_md} 오늘의 추천곡\n\n{song_cell}"

    return "오늘의 추천곡 정보를 찾을 수 없습니다."


# =========================================================
# 9. 오늘의 배달 추천 응답
# =========================================================
def build_delivery_text() -> str:
    rows = delivery_worksheet.get_all_values()

    if not rows or len(rows) < 2:
        return "배달음식 추천 목록이 아직 등록되지 않았습니다."

    foods = []

    for row in rows[1:]:
        if len(row) > 0 and row[0].strip():
            foods.append(row[0].strip())

    if not foods:
        return "배달음식 추천 목록이 비어 있습니다."

    today = datetime.now(KST)

    # 매일 다른 메뉴가 나오도록 날짜 기준으로 하나 선택
    index = (today.timetuple().tm_yday - 1) % len(foods)
    food = foods[index]

    return f"🍽️ 오늘의 배달 추천\n\n{food}"


# =========================================================
# 10. 폴백/전체 라우터
# =========================================================
def route_unknown_utterance(utterance: str) -> str:
    u = (utterance or "").strip()
    compact = u.replace(" ", "").lower()

    # 이름 궁합
    if is_name_compatibility_query(u):
        return route_name_compatibility_by_utterance(u)

    # 오늘의 배달 추천
    if any(
        kw in compact
        for kw in [
            "배달",
            "배달음식",
            "배달추천",
            "야식",
            "야식추천",
            "시켜먹",
            "시켜먹지",
            "뭐시켜",
            "뭐먹지",
            "먹을거",
            "먹을것",
        ]
    ):
        return build_delivery_text()

    # 간편식/샐러드
    if any(kw in compact for kw in ["간편식", "샐러드", "샐러드식"]):
        return route_salad_by_utterance(u)

    # 학식
    if any(kw in compact for kw in ["학식", "메뉴", "식단", "밥"]):
        data = get_today_row()

        if any(kw in compact for kw in ["전체", "오늘", "하루", "전부", "모든"]):
            return build_meal_text(data)

        if any(kw in compact for kw in ["아침", "조식"]):
            return build_single_meal_text(data, "breakfast")

        if any(kw in compact for kw in ["점심", "중식"]):
            return build_single_meal_text(data, "lunch")

        if any(kw in compact for kw in ["저녁", "석식"]):
            return build_single_meal_text(data, "dinner")

        return build_now_meal_text(data)

    # 오늘의 추천곡
    if any(kw in compact for kw in ["추천곡", "노래", "음악"]):
        return build_song_text()

    # 명령어
    if any(kw in compact for kw in ["명령어", "도움말", "사용법", "기능"]):
        return build_command_text()

    return (
        "이해하기 어려워요 😅\n\n"
        "이렇게 입력해볼 수 있어요.\n"
        "- 오늘 학식\n"
        "- 점심 학식\n"
        "- 간편식\n"
        "- 오늘의 추천곡\n"
        "- 오늘의 배달 추천\n"
        "- 민수 민지 궁합"
    )


# =========================================================
# 11. 카카오 챗봇 스킬 엔드포인트
# =========================================================

# -------------------------
# 학식
# -------------------------
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


# -------------------------
# 간편식/샐러드
# -------------------------
@app.post("/skill/salad")
async def salad(request: Request):
    body = await request.json()
    utterance = get_utterance(body)
    return kakao_response(route_salad_by_utterance(utterance))


# -------------------------
# 오늘의 추천곡
# -------------------------
@app.post("/skill/song")
async def song(request: Request):
    _ = await request.json()
    return kakao_response(build_song_text())


# -------------------------
# 오늘의 배달 추천
# -------------------------
@app.post("/skill/delivery")
async def delivery(request: Request):
    _ = await request.json()
    return kakao_response(build_delivery_text())


# -------------------------
# 이름 궁합
# -------------------------
@app.post("/skill/name-compatibility")
async def name_compatibility(request: Request):
    body = await request.json()
    utterance = get_utterance(body)
    return kakao_response(route_name_compatibility_by_utterance(utterance))


# -------------------------
# 명령어
# -------------------------
@app.post("/skill/command")
async def command(request: Request):
    _ = await request.json()
    return kakao_response(build_command_text())


# -------------------------
# 폴백/전체 라우터
# -------------------------
@app.post("/skill/router")
async def skill_router(request: Request):
    body = await request.json()
    utterance = get_utterance(body)
    return kakao_response(route_unknown_utterance(utterance))
