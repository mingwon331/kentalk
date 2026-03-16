import gspread
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime

# =========================
# 1. Google Sheets 설정
# =========================
CREDS_FILE = r"C:\Users\Kim\Desktop\KENTECH\KENTALK\kentalk-490316-d7c1fe0f6909.json"
SPREADSHEET_ID = "1zQ0rIZ3Kt-V16NfRvWQvdQvabjF36xCHE9mbWuNncGA"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(SPREADSHEET_ID)
worksheet = spreadsheet.get_worksheet(0)   # 첫 번째 탭 사용

# =========================
# 2. 포털 학식 API 설정
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
    "PTL_JSESSIONID": "DC8D78E8029710FCDC3F8B8A553F6DBF",
    "_SSO_Global_Logout_url": "get^https://my.kentech.ac.kr/sso/logout.jsp?logout=1$",
    "_st": "1773590883S14400",
}

# =========================
# 3. 학식 데이터 가져오기
# =========================
def fetch_dining(lecture_date: str):
    response = requests.post(
        DINING_URL,
        headers=HEADERS,
        cookies=COOKIES,
        data={"lectureDate": lecture_date},
        timeout=10
    )
    response.raise_for_status()
    return response.json()

# =========================
# 4. 문자열 정리
# =========================
def clean_text(text):
    return (text or "").strip()

# =========================
# 5. 오늘 날짜 생성
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
# 6. 기존 날짜 있으면 업데이트, 없으면 추가
# =========================
all_values = worksheet.get_all_values()

found_row = None
for idx, row in enumerate(all_values[1:], start=2):  # 1행은 헤더라서 제외
    if len(row) > 0 and row[0] == today:
        found_row = idx
        break

if found_row:
    worksheet.update(f"A{found_row}:J{found_row}", [row_data])
    print(f"{today} 데이터 업데이트 완료")
else:
    worksheet.append_row(row_data)
    print(f"{today} 데이터 새로 추가 완료")