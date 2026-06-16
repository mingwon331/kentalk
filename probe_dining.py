# probe_dining.py — 임시. 끝나면 버려.
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests

KST = ZoneInfo("Asia/Seoul")
URL = "https://my.kentech.ac.kr/portlet/Ptl014.eps"
HEADERS = {  # update_dining_sheet.py 그대로 복붙
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://my.kentech.ac.kr",
    "Referer": "https://my.kentech.ac.kr/p/sMain/",
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
}
COOKIES = {
    "PTL_JSESSIONID": "여기에 값 붙여넣기",
    "_st": "여기에 값 붙여넣기",
}

def probe(date_str, dump_full=False):
    r = requests.post(URL, headers=HEADERS, cookies=COOKIES,
                      data={"lectureDate": date_str}, timeout=20)
    ct = r.headers.get("content-type", "")
    print(f"\n=== lectureDate={date_str} | {r.status_code} | {ct}")
    if "json" not in ct:
        print("  JSON 아님(세션/리다이렉트 의심):", r.text[:200]); return
    data = r.json()
    print("  top keys:", list(data.keys()))
    print("  echoed date:", data.get("lectureDate"), "/ dow:", data.get("dayOfWeek"))
    dl = data.get("diningList", [])
    print("  diningList len:", len(dl))
    for i, e in enumerate(dl):
        date_fields = {k: v for k, v in e.items() if any(t in k.lower() for t in ("date","ymd","day"))}
        filled = [k for k in ("josik_menu_contents","jungsik_menu_contents","seoksik_menu_contents") if (e.get(k) or "").strip()]
        print(f"    [{i}] sikdang={e.get('sikdang_nm')} | {date_fields} | filled={filled}")
    if dump_full:
        print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])

base = datetime.now(KST)
for off in range(0, 8):
    probe((base + timedelta(days=off)).strftime("%Y%m%d"), dump_full=(off == 0))
