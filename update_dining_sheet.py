import os
import tempfile
import time
from datetime import datetime
from zoneinfo import ZoneInfo

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
KST = ZoneInfo("Asia/Seoul")

# =========================
# 2. 서비스 계정 JSON을 임시 파일로 저장
# =========================
with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
    f.write(GOOGLE_SERVICE_ACCOUNT_JSON)
    CREDS_PATH = f.name

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

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


def clean_text(text):
    return (text or "").strip()


def retry_sleep(seconds: int):
    print(f"{seconds}초 후 재시도합니다...")
    time.sleep(seconds)


def get_worksheet_with_retry(max_attempts: int = 5):
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[Sheets 연결] 시도 {attempt}/{max_attempts}")
            creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
            worksheet = spreadsheet.get_worksheet(WORKSHEET_INDEX)
            print("[Sheets 연결] 성공")
            return worksheet

        except Exception as e:
            last_error = e
            print(f"[Sheets 연결] 실패: {repr(e)}")

            if attempt < max_attempts:
                retry_sleep(2 * attempt)

    raise last_error


def fetch_dining_with_retry(lecture_date: str, max_attempts: int = 5):
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[포털 요청] 시도 {attempt}/{max_attempts}")

            response = requests.post(
                DINING_URL,
                headers=HEADERS,
                cookies=COOKIES,
                data={"lectureDate": lecture_date},
                timeout=20
            )
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            print("Response content-type:", content_type)
            print("Response preview:", response.text[:300])

            data = response.json()

            if "diningList" not in data:
                raise ValueError(f"diningList가 응답에 없습니다: {data}")

            print("[포털 요청] 성공")
            return data

        except Exception as e:
            last_error = e
            print(f"[포털 요청] 실패: {repr(e)}")

            if attempt < max_attempts:
                retry_sleep(2 * attempt)

    raise last_error


def update_sheet_with_retry(worksheet, found_row, row_data, max_attempts: int = 5):
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[시트 쓰기] 시도 {attempt}/{max_attempts}")

            if found_row:
                worksheet.update(
                    range_name=f"A{found_row}:J{found_row}",
                    values=[row_data]
                )
            else:
                worksheet.append_row(row_data)

            print("[시트 쓰기] 성공")
            return

        except Exception as e:
            last_error = e
            print(f"[시트 쓰기] 실패: {repr(e)}")

            if attempt < max_attempts:
                retry_sleep(2 * attempt)

    raise last_error


def main():
    # 한국 시간 기준
    now_kst = datetime.now(KST)
    today = now_kst.strftime("%Y%m%d")
    updated_at = now_kst.strftime("%Y-%m-%d %H:%M:%S")

    print("KST now:", now_kst.strftime("%Y-%m-%d %H:%M:%S"))
    print("today used:", today)

    # 1) 시트 연결
    worksheet = get_worksheet_with_retry()

    # 2) 포털에서 메뉴 가져오기
    data = fetch_dining_with_retry(today)
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

    print("row_data date:", row_data[0])

    # 3) 기존 날짜 찾기
    all_values = worksheet.get_all_values()

    found_row = None
    for idx, row in enumerate(all_values[1:], start=2):
        if len(row) > 0 and row[0] == today:
            found_row = idx
            break

    # 4) 시트 쓰기
    update_sheet_with_retry(worksheet, found_row, row_data)

    if found_row:
        print(f"{today} 데이터 업데이트 완료")
    else:
        print(f"{today} 데이터 새로 추가 완료")


if __name__ == "__main__":
    main()
