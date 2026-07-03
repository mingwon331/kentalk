"""
학교 급식 '핵심 메뉴' 추출 알고리즘 v3

핵심 수정점
- 밥/국/김치/후식/일반 반찬을 먼저 제거하고, 실제 대표 메뉴 후보만 점수화
- 고기/생선/닭/불고기류 같은 메인 단백질 메뉴를 두부·달걀·어묵류 반찬보다 우선
- 비빔밥/덮밥/볶음밥/죽처럼 첫 번째로 나온 한그릇 메뉴는 대표 메뉴로 강하게 보정
- 찌개/탕/국은 단독일 때는 대표 메뉴가 될 수 있지만, 명확한 고기/한그릇 메뉴가 있으면 보조 메뉴로 감점
- A코너/B코너 구분과 반환 형식은 기존 app.py와 호환

사용법:
    extract_core_menu(menu_text, top_k=1)
"""

import re

# =========================================================
# 1) 텍스트 정제 & 코너 분리
# =========================================================

HEADER_PATTERNS = [
    r"^[AaBbCcDd]\s*코너$",
    r"^\[.*\]$",
    r"^간편식.*운영.*$",
    r"^\s*$",
]


def is_header(line: str) -> bool:
    s = (line or "").strip()
    return any(re.match(p, s) for p in HEADER_PATTERNS)


def split_corners(raw):
    if not isinstance(raw, str) or not raw.strip():
        return {}

    lines = [line.strip() for line in raw.split("\n")]

    # 주말/공휴일 조식처럼 간편식 대체 문구만 있는 경우 핵심 메뉴 없음
    if any("간편식" in line and "대체운영" in line for line in lines):
        return {}

    corners = {"MAIN": []}
    current = "MAIN"

    for line in lines:
        s = line.strip()
        if not s:
            continue

        m = re.match(r"^([AaBbCcDd])\s*코너$", s)
        if m:
            current = m.group(1).upper() + "코너"
            corners.setdefault(current, [])
            continue

        if is_header(s):
            continue

        corners[current].append(s)

    return {k: v for k, v in corners.items() if v}


def clean_menu_text(lines):
    items = []

    for raw_line in lines:
        text = raw_line or ""
        text = re.sub(r"<\s*br\s*/?\s*>", "|", text, flags=re.IGNORECASE)
        text = re.sub(r"\([\d\.\s,]+\)", "", text)
        text = re.sub(r"\d+\.?\d*\s*Kcal", "", text, flags=re.IGNORECASE)

        for piece in re.split(r"[|\r\n]+", text):
            s = piece.strip()
            if not s:
                continue

            # 쌀밥/누룽지, 시리얼/우유/주스 같은 결합 메뉴 분리
            for sub in s.split("/"):
                t = sub.strip()
                t = re.sub(r"^[\soO○●*\-•·]+", "", t)
                t = re.sub(r"[\s*]+$", "", t)
                t = re.sub(r"\s+", " ", t).strip()

                if t and not is_header(t):
                    items.append(t)

    return items


# =========================================================
# 2) 분류 사전
# =========================================================

RICE_PATTERNS = [
    r"^(쌀밥|잡곡밥|찹쌀밥|현미밥|흑미밥|기장밥|완두콩밥|검정콩밥|강낭콩밥|율무밥|백미밥|오곡밥|보리밥|팥밥|강황밥|미니밥)$",
    r"^(누룽지|죽)$",
    r"^당뇨식이밥$",
]

SOUP_PATTERNS = [r"국$", r"탕$", r"찌개$", r"전골$", r"스프$", r"수프$", r"^스프"]

# 단독으로 나오면 대표 메뉴가 될 수 있는 국/탕/찌개류.
# 다만 같은 식단에 명확한 고기/한그릇 메뉴가 있으면 점수에서 감점된다.
STRONG_SOUP_MAIN = [
    "부대찌개", "청국장찌개", "김치찌개", "순두부찌개", "바지락순두부찌개", "고기순두부짬뽕",
    "갈비탕", "설렁탕", "삼계탕", "육개장", "육계장", "닭개장", "감자탕", "추어탕", "해물탕", "미나리곰탕",
    "닭볶음탕", "닭도리탕", "꽃도리탕", "만두국", "떡국", "떡만두국", "수제비국",
]

KIMCHI_PATTERNS = [
    r"김치", r"깍두기", r"깍뚜기", r"석박지", r"섞박지", r"총각김치", r"갓김치",
    r"겉절이", r"장아찌", r"초절이", r"피클", r"단무지", r"락교",
    r"무말랭이", r"오이지", r"쌈무", r"치킨무",
    r"오복지", r"고추지", r"깻잎지", r"깐마늘지", r"양념고추지", r"간장고추지",
    r"할라피뇨",
]

SIDE_PATTERNS = [
    r"나물$", r"나물무침", r"무침$", r"겉절이$", r"생채$",
    r"^샐러드", r"샐러드$", r"드레싱", r"숙채$",
    r"^쌈$", r"쌈장$",
    r"도시락김$", r"구운김", r"조미김",
    r"초무침$", r"냉채$",
]

DESSERT_PATTERNS = [
    r"쥬스", r"주스", r"요거트", r"요구르트", r"우유$", r"두유$",
    r"라떼", r"쿨피스", r"아이스크림", r"셔벗", r"스무디",
    r"콜라", r"사이다", r"환타", r"에이드$", r"에이드\W",
    r"녹차$", r"매실차", r"복분자차", r"오미자차", r"체리에이드", r"아침햇살", r"옥수수차", r"보리차",
    r"케잌", r"케이크", r"쿠키", r"머핀", r"양갱", r"한과", r"약과",
    r"떡$", r"설기", r"인절미", r"푸딩", r"젤리", r"도넛", r"도너츠",
    r"초콜렛", r"초콜릿", r"꽈배기", r"츄러스", r"찐빵$",
    r"토스트", r"베이글", r"크로와상", r"크루아상", r"모닝빵", r"바게트",
    r"또띠아난", r"식빵", r"^난$",
    r"버터$", r"크림치즈", r"딸기잼", r"^잼$",
    r"시리얼",
    r"^딸기$", r"^사과$", r"^배$", r"^오렌지$", r"^귤$", r"^바나나$",
    r"^수박", r"^참외$", r"^포도$", r"^복숭아$", r"^키위$", r"^파인애플$",
    r"^방울토마토$", r"^자두$", r"^메론$", r"^멜론$",
    r"후식", r"^과일", r"삶은계란", r"삶은달걀", r"셀프후라이", r"^파이$",
    r"레모나", r"비타민", r"플리또", r"솜사탕",
]

# 대표 메뉴로 볼 가능성이 높은 단백질 키워드
PRIMARY_PROTEIN_KW = [
    "돼지", "돈육", "돈채", "돈갈비", "돈불", "돈까스", "돈가스", "제육", "삼겹", "목살", "폭찹", "두루치기", "불백",
    "소고기", "쇠고기", "한우", "차돌", "우삼겹", "규동", "불고기", "갈비", "떡갈비", "함박", "너비아니", "스테이크", "바베큐", "바비큐",
    "닭", "치킨", "닭갈비", "닭살", "닭찜", "찜닭", "닭볶음", "꽃도리", "오리", "훈제오리",
    "고등어", "갈치", "연어", "삼치", "임연수", "코다리", "명태", "동태", "생선", "가자미", "조기", "아귀", "장어",
    "오징어", "낙지", "문어", "쭈꾸미", "주꾸미", "새우", "꽃게", "게살", "조개", "홍합", "전복", "참치",
    "꿔바로우", "탕수육", "깐풍", "유린기", "까스", "커틀렛",
]

# 단백질이지만 보통 대표 메뉴보다는 반찬으로 쓰이는 키워드
WEAK_PROTEIN_KW = [
    "계란", "달걀", "메알", "메추리알", "두부", "순두부", "햄", "소시지", "스팸", "비엔나",
    "어묵", "오뎅", "가마보꼬", "김말이", "핫도그", "동그랑땡",
]

COOK_KW = [
    "구이", "볶음", "튀김", "찜", "조림", "전$", "부침",
    "스테이크", "바베큐", "바비큐", "강정", "데리야키", "오븐",
    "갈비찜", "숯불", "양념구이", "폭찹", "탕수", "꿔바로우",
    "제육", "두루치기", "불고기", "불백", "찜닭",
]

MEAL_MAIN_SUFFIX = [
    "볶음", "구이", "찜", "조림", "튀김", "전", "강정", "스테이크", "불고기", "불백", "두루치기", "갈비", "돈까스", "까스", "탕수육",
]

ONE_DISH_KW = [
    "비빔밥", "덮밥", "볶음밥", "김밥", "주먹밥", "솥밥", "영양밥",
    "필라프", "리조또", "라이스", "에비동", "규동",
    "카레", "커리", "하이라이스", "오므라이스", "밥버거",
    "파스타", "스파게티", "피자",
    "우동", "라면", "쌀국수", "짜장", "짬뽕", "칼국수", "국수",
    "비빔면", "냉면", "잔치국수", "볶음면", "막국수", "비빔국수",
    "누들면", "짜장면", "햄버거", "샌드위치", "퀘사디아", "랩",
    "떡볶이", "라볶이", "쫄면", "짜장떡볶이",
    "떡국", "만두국", "수제비", "닭갈비", "갈비찜", "갈비탕",
]

# 첫 번째 대표 후보로 나오면 강하게 보정할 한그릇 메뉴
PRIMARY_ONE_DISH_KW = [
    "비빔밥", "덮밥", "볶음밥", "김밥", "주먹밥", "솥밥", "영양밥", "필라프", "리조또", "라이스",
    "에비동", "규동", "카레", "커리", "하이라이스", "오므라이스", "밥버거", "죽",
]

# 고기 메인이 있을 때 대표 메뉴로 보기 애매한 면/분식류
LIGHT_ONE_DISH_KW = [
    "잔치국수", "국수", "우동", "면", "떡볶이", "쫄면", "막국수", "냉면", "파스타", "스파게티",
]


# =========================================================
# 3) 분류 & 점수
# =========================================================


def normalize_for_match(s: str) -> str:
    s2 = re.sub(r"^[가-힣A-Za-z]+-", "", s or "").strip()
    s2 = re.sub(r"\([^)]*\)", "", s2).strip()
    return s2 or (s or "")


def strip_sauce(s: str) -> str:
    """소스/고추장/케찹 등 표기 뒤쪽은 점수 계산에서 과도하게 보상하지 않음."""
    x = (s or "").strip()
    x = re.split(r"[*&]", x)[0].strip()
    x = re.sub(r"\([^)]*\)", "", x).strip()
    return x or (s or "")


def has_any(text: str, keywords) -> bool:
    return any(k in text for k in keywords)


def is_plain_staple(item: str) -> bool:
    body = strip_sauce(normalize_for_match(item))
    return any(re.search(p, body) for p in RICE_PATTERNS)


def is_primary_one_dish(body: str) -> bool:
    return has_any(body, PRIMARY_ONE_DISH_KW) or (body.endswith("죽") and body not in ("죽", "흰죽"))


def classify(item: str) -> str:
    body = strip_sauce(normalize_for_match(item))
    raw = item or ""

    if not body:
        return "OTHER"

    if is_plain_staple(body):
        return "RICE"

    for p in DESSERT_PATTERNS:
        if re.search(p, raw) or re.search(p, body):
            return "DESSERT"

    # 김치찌개, 묵은지찜닭처럼 김치 단어가 들어가도 메인일 수 있는 경우는 제외
    for p in KIMCHI_PATTERNS:
        if re.search(p, raw) or re.search(p, body):
            if not (has_any(body, PRIMARY_PROTEIN_KW) or body.endswith("찌개") or has_any(body, STRONG_SOUP_MAIN)):
                return "KIMCHI"
            break

    if has_any(body, STRONG_SOUP_MAIN):
        return "SOUP_MAIN"

    if body.endswith("죽") and body not in ("죽", "흰죽"):
        return "ONE_DISH"

    if has_any(body, ONE_DISH_KW):
        return "ONE_DISH"

    has_primary = has_any(body, PRIMARY_PROTEIN_KW)
    has_weak = has_any(body, WEAK_PROTEIN_KW)
    has_cook = any(re.search(k, body) for k in COOK_KW) or has_any(body, MEAL_MAIN_SUFFIX)

    if any(re.search(p, body) for p in SOUP_PATTERNS):
        if has_primary:
            return "SOUP_MAIN"
        return "SOUP"

    for p in SIDE_PATTERNS:
        if re.search(p, body):
            return "SIDE"

    if has_primary:
        return "MEAT_MAIN"

    if has_weak:
        return "WEAK_PROTEIN"

    if has_cook:
        return "SIDE"

    return "OTHER"


def score_main(item: str, category: str, idx: int = 0, context=None) -> float:
    body = strip_sauce(normalize_for_match(item))
    context = context or {}

    meat_exists = context.get("meat_exists", False)
    one_dish_exists = context.get("one_dish_exists", False)
    stronger_exists = context.get("stronger_exists", False)
    first_candidate_idx = context.get("first_candidate_idx")

    has_primary = has_any(body, PRIMARY_PROTEIN_KW)
    has_weak = has_any(body, WEAK_PROTEIN_KW)
    has_one = has_any(body, ONE_DISH_KW) or (body.endswith("죽") and body not in ("죽", "흰죽"))
    has_cook = any(re.search(k, body) for k in COOK_KW) or has_any(body, MEAL_MAIN_SUFFIX)

    score = {
        "MEAT_MAIN": 6.0,
        "ONE_DISH": 5.3,
        "SOUP_MAIN": 4.4,
        "WEAK_PROTEIN": 3.0,
        "SOUP": 2.0,
        "SIDE": 1.0,
        "OTHER": 0.8,
    }.get(category, 0.0)

    if has_primary:
        score += 1.0
    if has_cook:
        score += 0.6
    if has_one:
        score += 0.6

    if len(body) >= 5:
        score += 0.25
    if len(body) >= 8:
        score += 0.15

    # 메뉴판 순서 보정: 앞쪽 메뉴가 보통 대표 메뉴에 가까움.
    score += max(0.0, 0.45 - idx * 0.08)

    # 첫 대표 후보가 비빔밥/덮밥/죽류면 그 메뉴가 식단 제목일 가능성이 높음.
    if category == "ONE_DISH" and is_primary_one_dish(body):
        score += 0.9
        if first_candidate_idx == idx:
            score += 1.8

    # 고기/한그릇 메뉴가 있으면 국/탕/찌개는 보조 메뉴로 감점.
    if category in ("SOUP", "SOUP_MAIN") and (meat_exists or one_dish_exists):
        score -= 1.8 if category == "SOUP_MAIN" else 1.2

    # 두부/달걀/어묵/소시지류는 강한 메인 후보가 있으면 반찬으로 감점.
    if category == "WEAK_PROTEIN" and stronger_exists:
        score -= 1.8
    if has_weak and stronger_exists and not has_primary:
        score -= 0.7

    # 고기 메인이 있으면 잔치국수/떡볶이/쫄면류가 메인을 이기지 않도록 조정.
    if category == "ONE_DISH" and has_any(body, LIGHT_ONE_DISH_KW) and meat_exists:
        score -= 0.7
    if has_any(body, ["떡볶이", "라볶이", "쫄면", "맥앤치즈", "감자튀김", "고구마맛탕"]) and meat_exists:
        score -= 0.7

    # 소스 표기가 붙은 긴 이름이 길이 보너스를 과하게 받지 않도록 미세 조정.
    if "*" in (item or "") or "&" in (item or ""):
        score -= 0.05

    return round(score, 3)


# =========================================================
# 4) 핵심 메뉴 추출
# =========================================================


def extract_core_from_items(items, top_k=1):
    cats = [classify(item) for item in items]

    meat_exists = any(c == "MEAT_MAIN" for c in cats)
    one_dish_exists = any(c == "ONE_DISH" for c in cats)
    stronger_exists = any(c in ("MEAT_MAIN", "ONE_DISH") for c in cats)

    first_candidate_idx = None
    for idx, category in enumerate(cats):
        if category in ("MEAT_MAIN", "ONE_DISH", "SOUP_MAIN", "WEAK_PROTEIN"):
            first_candidate_idx = idx
            break

    context = {
        "meat_exists": meat_exists,
        "one_dish_exists": one_dish_exists,
        "stronger_exists": stronger_exists,
        "first_candidate_idx": first_candidate_idx,
    }

    candidates = []
    for idx, (item, category) in enumerate(zip(items, cats)):
        if category in ("MEAT_MAIN", "ONE_DISH", "SOUP_MAIN", "WEAK_PROTEIN"):
            candidates.append((item, category, score_main(item, category, idx, context)))

    # 명확한 메인 후보가 없으면 국/탕/찌개라도 반환
    if not candidates:
        for idx, (item, category) in enumerate(zip(items, cats)):
            if category == "SOUP":
                candidates.append((item, category, score_main(item, category, idx, context)))

    candidates.sort(key=lambda x: (-x[2], items.index(x[0])))

    return {
        "items": items,
        "categories": list(zip(items, cats)),
        "candidates": candidates,
        "core": [c[0] for c in candidates[:top_k]],
    }


def extract_core_menu(raw_text, top_k=1):
    """메인 함수: 메뉴 텍스트를 받아 코너별 핵심 메뉴를 dict로 반환"""
    corners = split_corners(raw_text)
    if not corners:
        return {}

    result = {}
    for corner_name, lines in corners.items():
        items = clean_menu_text(lines)
        result[corner_name] = extract_core_from_items(items, top_k=top_k)

    return result
