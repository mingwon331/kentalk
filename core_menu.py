"""
학교 급식 '핵심 메뉴' 추출 알고리즘 v2
- 머신러닝 X / 규칙 기반 (사전 + 점수)
- A코너 / B코너 구분 지원
- '쌀밥/누룽지' 같은 슬래시 결합 메뉴 분리
- 사용법: extract_core_menu(menu_text, top_k=1)
"""

import re

# =========================================================
# 1) 텍스트 정제 & 분리
# =========================================================

HEADER_PATTERNS = [
    r'^[AaBbCcDd]\s*코너$',
    r'^\[.*\]$',
    r'^간편식.*운영.*$',
    r'^\s*$',
]

def is_header(line):
    s = line.strip()
    return any(re.match(p, s) for p in HEADER_PATTERNS)


def split_corners(raw):
    if not isinstance(raw, str) or not raw.strip():
        return {}
    lines = [l.strip() for l in raw.split('\n')]
    if any('간편식' in l and '대체운영' in l for l in lines):
        return {}
    corners = {'MAIN': []}
    current = 'MAIN'
    for line in lines:
        s = line.strip()
        if not s:
            continue
        m = re.match(r'^([AaBbCcDd])\s*코너$', s)
        if m:
            current = m.group(1).upper() + '코너'
            corners.setdefault(current, [])
            continue
        if is_header(s):
            continue
        corners[current].append(s)
    return {k: v for k, v in corners.items() if v}


def clean_menu_text(lines):
    items = []
    for raw_line in lines:
        text = raw_line
        text = re.sub(r'<\s*br\s*/?\s*>', '|', text, flags=re.IGNORECASE)
        text = re.sub(r'\([\d\.\s,]+\)', '', text)
        text = re.sub(r'\d+\.?\d*\s*Kcal', '', text, flags=re.IGNORECASE)
        for piece in re.split(r'[|\r\n]+', text):
            s = piece.strip()
            if not s:
                continue
            for sub in s.split('/'):
                t = sub.strip()
                t = re.sub(r'^[\soO○●*\-•·]+', '', t)
                t = re.sub(r'[\s*]+$', '', t)
                t = re.sub(r'\s+', ' ', t).strip()
                if t and not is_header(t):
                    items.append(t)
    return items


# =========================================================
# 2) 카테고리 사전
# =========================================================

RICE_PATTERNS = [
    r'^쌀밥$', r'^누룽지$', r'^잡곡밥', r'^찹쌀밥', r'^현미밥', r'^흑미밥',
    r'^기장밥', r'^완두콩밥', r'^검정콩밥', r'^강낭콩밥', r'^율무밥', r'^미니밥',
    r'^백미밥', r'^오곡밥', r'^보리밥', r'^팥밥', r'^당뇨식이밥', r'^강황밥',
    r'^밥$', r'^죽$', r'죽-', r'^밥-',
]

SOUP_PATTERNS = [r'국$', r'탕$', r'찌개$', r'전골$', r'스프$', r'수프$', r'^스프']

STRONG_SOUP_MAIN = [
    '부대찌개', '청국장찌개', '순두부찌개',
    '갈비탕', '설렁탕', '도가니탕', '삼계탕', '육개장', '닭개장',
    '감자탕', '추어탕', '매운탕', '해물탕', '미나리곰탕',
    '닭도리탕', '닭볶음탕', '꽃도리탕',
    '옹심이국', '수제비국', '떡국', '만두국', '떡만두국',
]

KIMCHI_PATTERNS = [
    r'김치', r'깍두기', r'깍뚜기', r'석박지', r'섞박지', r'총각김치', r'갓김치',
    r'겉절이', r'장아찌', r'초절이', r'피클', r'단무지', r'락교',
    r'무말랭이', r'오이지', r'쌈무', r'치킨무',
    r'오복지', r'고추지', r'깻잎지', r'깐마늘지', r'양념고추지', r'간장고추지',
    r'할라피뇨',
]

SIDE_PATTERNS = [
    r'나물$', r'나물무침', r'무침$', r'겉절이$', r'생채$',
    r'^샐러드', r'샐러드$', r'드레싱', r'숙채$',
    r'^쌈$', r'쌈장$',
    r'도시락김$', r'구운김', r'조미김',
    r'초무침$', r'냉채$',
]

DESSERT_PATTERNS = [
    r'쥬스', r'주스', r'요거트', r'요구르트', r'우유$', r'두유$',
    r'라떼', r'쿨피스', r'아이스크림', r'셔벗', r'스무디',
    r'콜라', r'사이다', r'환타', r'에이드$', r'에이드\W',
    r'녹차$', r'매실차', r'복분자차', r'오미자차', r'체리에이드', r'아침햇살',
    r'케잌', r'케이크', r'쿠키', r'머핀', r'양갱', r'한과', r'약과',
    r'떡$', r'설기', r'인절미', r'푸딩', r'젤리', r'도넛', r'도너츠',
    r'초콜렛', r'초콜릿', r'꽈배기', r'츄러스', r'찐빵$',
    r'토스트', r'베이글', r'크로와상', r'크루아상', r'모닝빵', r'바게트',
    r'또띠아난', r'식빵', r'^난$',
    r'버터$', r'크림치즈', r'딸기잼', r'^잼$',
    r'시리얼',
    r'^딸기$', r'^사과$', r'^배$', r'^오렌지$', r'^귤$', r'^바나나$',
    r'^수박$', r'^참외$', r'^포도$', r'^복숭아$', r'^키위$', r'^파인애플$',
    r'^방울토마토$', r'^자두$', r'^메론$', r'^멜론$',
    r'후식', r'^과일', r'삶은계란', r'셀프후라이', r'^파이$',
    r'레모나', r'비타민', r'플리또', r'솜사탕',
]

# =========================================================
# 3) 메인 점수 키워드
# =========================================================

PROTEIN_KW = [
    '돼지', '돈육', '돈채', '돈갈비', '돈불', '돈까스', '돈가스',
    '제육', '삼겹', '목살', '폭찹', '두루치기', '불백',
    '소고기', '쇠고기', '한우', '차돌', '우삼겹', '규동', '불고기', '갈비', '떡갈비',
    '한박', '함박', '너비아니', '동그랑땡', '미트볼', '스테이크', '바베큐', '바비큐',
    '닭', '치킨', '꽃도리', '닭갈비', '닭살', '닭찜', '닭볶음',
    '오리', '훈제오리', '양갈비',
    '고등어', '갈치', '연어', '삼치', '임연수', '코다리', '명태', '동태',
    '가자미', '조기', '아귀', '장어', '뱀장어', '오징어', '낙지', '문어', '쭈꾸미', '주꾸미',
    '새우', '꽃게', '게살', '조개', '홍합', '전복', '북어',
    '참치', '꿔바로우', '탕수', '탕수육',
    '계란', '달걀', '두부', '순두부', '햄', '소시지', '스팸', '비엔나',
    '핫도그', '커틀렛', '까스', '가스', '어묵', '오뎅', '가마보꼬',
    '떡갈비', '떡불고기', '김말이', '오므라이스', '덮밥',
    '피자', '파스타', '함박',
    '깐풍', '라조', '난자완스', '유린기', '탕수',
]

COOK_KW = [
    '구이', '볶음', '튀김', '찜', '조림', '전$', '부침',
    '스테이크', '바베큐', '바비큐', '강정', '데리야키', '오븐',
    '갈비찜', '숯불', '양념구이', '폭찹', '탕수', '꿔바로우',
    '제육', '두루치기', '불고기', '불백', '찜닭',
]

ONE_DISH_KW = [
    '비빔밥', '덮밥', '볶음밥', '김밥', '주먹밥', '솥밥', '영양밥',
    '필라프', '리조또', '라이스', '에비동', '규동',
    '카레', '커리', '하이라이스', '오므라이스', '밥버거',
    '파스타', '스파게티', '피자',
    '우동', '라면', '쌀국수', '짜장', '짬뽕', '칼국수', '국수',
    '비빔면', '냉면', '잔치국수', '볶음면', '막국수', '비빔국수',
    '누들면', '짜장면',
    '햄버거', '샌드위치', '퀘사디아', '랩',
    '떡볶이', '라볶이', '쫄면', '짜장떡볶이',
    '떡국', '만두국', '수제비',
    '닭갈비', '갈비찜', '갈비탕',
]

# =========================================================
# 4) 분류 & 점수
# =========================================================

def normalize_for_match(s):
    s2 = re.sub(r'^[가-힣A-Za-z]+-', '', s).strip()
    s2 = re.sub(r'\([^)]*\)', '', s2).strip()
    return s2 or s


def classify(item):
    body = normalize_for_match(item)
    is_cooked = bool(re.search(r'(찌개|볶음|전|국$|탕$|죽|전병|국수|면)$', body))
    if not is_cooked:
        for p in KIMCHI_PATTERNS:
            if re.search(p, item) or re.search(p, body):
                return 'KIMCHI'
    if any(k in body for k in STRONG_SOUP_MAIN):
        return 'ONE_DISH'
    if re.search(r'(찌개|탕)$', body) and any(k in body for k in PROTEIN_KW):
        return 'ONE_DISH'
    for k in ONE_DISH_KW:
        if k in body:
            return 'ONE_DISH'
    for p in RICE_PATTERNS:
        if re.search(p, item) or re.search(p, body):
            return 'RICE'
    for p in DESSERT_PATTERNS:
        if re.search(p, item) or re.search(p, body):
            return 'DESSERT'
    for p in SOUP_PATTERNS:
        if re.search(p, body):
            return 'SOUP'
    for p in SIDE_PATTERNS:
        if re.search(p, body):
            return 'SIDE'
    has_protein = any(k in body for k in PROTEIN_KW)
    has_cook = any(re.search(k, body) for k in COOK_KW)
    if has_protein:
        return 'MAIN_CANDIDATE'
    if has_cook:
        return 'SIDE'
    return 'OTHER'


def score_main(item, category):
    body = normalize_for_match(item)
    score = 0.0
    if category == 'ONE_DISH':
        score += 2.5
    if any(k in body for k in ONE_DISH_KW):
        score += 0.5
    if any(k in body for k in STRONG_SOUP_MAIN):
        score += 0.5
    if any(k in body for k in PROTEIN_KW):
        score += 2.0
    if any(re.search(k, body) for k in COOK_KW):
        score += 1.0
    if len(body) >= 5:
        score += 0.5
    if len(body) >= 8:
        score += 0.3
    return score


# =========================================================
# 5) 핵심 메뉴 추출
# =========================================================

def extract_core_from_items(items, top_k=1):
    cats = [classify(i) for i in items]
    candidates = []
    for it, c in zip(items, cats):
        if c in ('ONE_DISH', 'MAIN_CANDIDATE'):
            candidates.append((it, c, score_main(it, c)))
    if not candidates:
        for it, c in zip(items, cats):
            if c == 'SOUP':
                candidates.append((it, c, score_main(it, c) + 0.3))
    candidates.sort(key=lambda x: -x[2])
    core = [c[0] for c in candidates[:top_k]]
    return {
        'items': items,
        'categories': list(zip(items, cats)),
        'candidates': candidates,
        'core': core,
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
