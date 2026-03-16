import os
import json
import tempfile
from datetime import datetime

import gspread
import requests
from google.oauth2.service_account import Credentials


# =========================
# 1. 환경변수 / Secrets 읽기
# =========================
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
PTL_JSESSIONID = os.environ["PTL_JSESSIONID"]
ST_COOKIE = os.environ["ST_COOKIE"]

SPREADSHEET_ID = "1zQ0rIZ3Kt-V16NfRvWQvdQvabjF36xCHE9mbWuNncGA"
WORKSHEET_INDEX = 0

# =========================
# 2. 서비스 계정 JSON을 임시 파일로 저장
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
# 3. 포털 학식 API 설정
# =========================
DINING_URL = "https://my.kentech.ac.kr/portlet/Ptl014.eps"

HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://my.kentech.ac.kr",
    "Referer": "https://my.kentech.ac.kr/p/sMain/",
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
}

COOKIES = {
    "PTL_JSESSIONID": PTL_JSESSIONID,
    "_st": ST_COOKIE,
}

# =========================
# 4. 학식 데이터 가져오기
# =========================
def fetch_dining(lecture_date: str):
    response = requests.post(
        DINING_URL,
        headers=HEADERS,
        cookies=COOKIES,
        data={"lectureDate": lecture_date},
        timeout=15
    )
    response.raise_for_status()
    return response.json()

def clean_text(text):
    return (text or "").strip()

# =========================
# 5. 오늘 날짜 기준으로 저장
# =========================
today = datetime.now().strftime("%Y%m%d")
updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

data = fetch_dining(today)
dining = data["diningList"][0]

row_data = [
    data.get("lectureDate", today),
    data.get("dayOfWeek", ""),
    clean_text(dining.get("sikdang_nm", "")),
    clean_text(dining.get("josik_menu_contents", "")),
    clean_text(dining.get("josik_husik_contents", "")),
    clean_text(dining.get("jungsik_menu_contents", "")),
    clean_text(dining.get("jungsik_husik_contents", "")),
    clean_text(dining.get("seoksik_menu_contents", "")),
    clean_text(dining.get("seoksik_husik_contents", "")),
    updated_at
]

# =========================
# 6. 같은 날짜가 있으면 업데이트, 없으면 추가
# =========================
all_values = worksheet.get_all_values()

found_row = None
for idx, row in enumerate(all_values[1:], start=2):
    if len(row) > 0 and row[0] == today:
        found_row = idx
        break

if found_row:
    worksheet.update(f"A{found_row}:J{found_row}", [row_data])
    print(f"{today} 데이터 업데이트 완료")
else:
    worksheet.append_row(row_data)
    print(f"{today} 데이터 새로 추가 완료")
