"""
KENTALK 이름 궁합 기능

사용 예시:
    route_name_compatibility_by_utterance("홍길동-홍길순 궁합")
    route_name_compatibility_by_utterance("홍길동이랑 김민지 이름궁합")

알고리즘:
    1. 사용자 발화에서 이름 2개 추출
    2. 한글 음절을 초성/중성/종성으로 분해
    3. 각 자모의 획수를 더해 글자별 획수 계산
    4. 두 이름의 획수를 번갈아 배치
    5. 인접 숫자를 더한 뒤 10으로 나눈 나머지를 반복
    6. 마지막 두 자리 숫자를 궁합 점수로 사용

주의:
    과학적/사주적 판단이 아니라, 챗봇용 재미 콘텐츠입니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# =========================================================
# 1) 한글 획수 테이블
# =========================================================
# 서비스용 재미 알고리즘이므로, 한 가지 기준을 고정해서 사용한다.
# 초성/종성은 같은 자모라도 위치에 따라 시각적으로 다를 수 있지만 여기서는 동일 획수로 처리한다.
CHOSUNG_LIST = [
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
]
JUNGSUNG_LIST = [
    "ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ",
    "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ",
]
JONGSUNG_LIST = [
    "", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ",
    "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
]

STROKE_COUNT = {
    # 자음
    "ㄱ": 2, "ㄲ": 4, "ㄴ": 2, "ㄷ": 3, "ㄸ": 6,
    "ㄹ": 5, "ㅁ": 4, "ㅂ": 4, "ㅃ": 8, "ㅅ": 2,
    "ㅆ": 4, "ㅇ": 1, "ㅈ": 3, "ㅉ": 6, "ㅊ": 4,
    "ㅋ": 3, "ㅌ": 4, "ㅍ": 4, "ㅎ": 3,

    # 겹받침
    "ㄳ": 4, "ㄵ": 5, "ㄶ": 5, "ㄺ": 7, "ㄻ": 9,
    "ㄼ": 9, "ㄽ": 7, "ㄾ": 9, "ㄿ": 9, "ㅀ": 8,
    "ㅄ": 6,

    # 모음
    "ㅏ": 2, "ㅐ": 3, "ㅑ": 3, "ㅒ": 4, "ㅓ": 2,
    "ㅔ": 3, "ㅕ": 3, "ㅖ": 4, "ㅗ": 2, "ㅘ": 4,
    "ㅙ": 5, "ㅚ": 3, "ㅛ": 3, "ㅜ": 2, "ㅝ": 4,
    "ㅞ": 5, "ㅟ": 3, "ㅠ": 3, "ㅡ": 1, "ㅢ": 2,
    "ㅣ": 1,
}

COMMAND_WORDS = [
    "이름궁합", "이름", "궁합", "점수", "봐줘", "봐주라", "봐", "해줘", "해주라",
    "알려줘", "분석", "결과", "테스트", "랑", "이랑", "하고", "과", "와", "의",
    "님", "씨", "는", "은", "가", "이", "을", "를", "도", "좀", "제발",
]

QUERY_KEYWORDS = ["궁합", "이름궁합", "이름 궁합", "커플", "케미"]


@dataclass
class NameCompatibilityResult:
    name1: str
    name2: str
    score: int
    grade: str
    comment: str
    name1_strokes: List[int]
    name2_strokes: List[int]
    start_numbers: List[int]
    steps: List[List[int]]


# =========================================================
# 2) 입력 분석
# =========================================================
def is_name_compatibility_query(utterance: str) -> bool:
    """발화가 이름 궁합 요청인지 간단 판별."""
    u = normalize_utterance(utterance)
    return any(k.replace(" ", "") in u.replace(" ", "") for k in QUERY_KEYWORDS)


def normalize_utterance(utterance: str) -> str:
    return (utterance or "").strip()


def clean_name_token(token: str) -> str:
    """이름 후보 토큰에서 조사/불필요 단어 제거."""
    t = (token or "").strip()
    t = re.sub(r"[^가-힣A-Za-z]", "", t)

    # 긴 명령어부터 제거
    for word in sorted(COMMAND_WORDS, key=len, reverse=True):
        if t == word:
            return ""
        if t.endswith(word) and len(t) - len(word) >= 2:
            t = t[: -len(word)]

    return t.strip()


def is_valid_name(name: str) -> bool:
    """한국어 이름 위주. 2~5글자 한글 이름을 기본 지원."""
    if not name:
        return False
    if not re.fullmatch(r"[가-힣]{2,5}", name):
        return False
    if name in COMMAND_WORDS:
        return False
    if any(x in name for x in ["궁합", "이름", "분석", "결과"]):
        return False
    return True


def parse_two_names(utterance: str) -> Optional[Tuple[str, str]]:
    """
    사용자 발화에서 이름 2개 추출.

    지원 예시:
        홍길동-홍길순 궁합
        홍길동/홍길순 이름궁합
        홍길동, 홍길순 궁합
        홍길동이랑 김민지 궁합
        이름궁합 홍길동 홍길순
    """
    if not utterance:
        return None

    original = normalize_utterance(utterance)

    # 1순위: 구분자가 명확한 경우
    delimiter_pattern = r"\s*(?:-|–|—|/|,|\+|&|♡|♥|❤|💕|랑|이랑|하고|와|과|및)\s*"
    parts = re.split(delimiter_pattern, original)
    candidates = []
    for part in parts:
        # part 안에 붙은 명령어 제거
        for chunk in re.split(r"\s+", part):
            name = clean_name_token(chunk)
            if is_valid_name(name):
                candidates.append(name)

    if len(candidates) >= 2:
        return candidates[0], candidates[1]

    # 2순위: 전체 문장에서 한글 이름처럼 보이는 토큰 추출
    text = original
    for word in sorted(COMMAND_WORDS + QUERY_KEYWORDS, key=len, reverse=True):
        text = text.replace(word, " ")

    raw_tokens = re.findall(r"[가-힣]{2,5}", text)
    candidates = []
    for token in raw_tokens:
        name = clean_name_token(token)
        if is_valid_name(name) and name not in candidates:
            candidates.append(name)

    if len(candidates) >= 2:
        return candidates[0], candidates[1]

    return None


# =========================================================
# 3) 이름 궁합 계산
# =========================================================
def decompose_hangul_char(ch: str) -> Tuple[str, str, str]:
    """한글 완성형 음절을 초성/중성/종성으로 분해."""
    code = ord(ch)
    base = ord("가")
    end = ord("힣")
    if code < base or code > end:
        return ch, "", ""

    offset = code - base
    cho_idx = offset // 588
    jung_idx = (offset % 588) // 28
    jong_idx = offset % 28

    return CHOSUNG_LIST[cho_idx], JUNGSUNG_LIST[jung_idx], JONGSUNG_LIST[jong_idx]


def hangul_char_stroke_count(ch: str) -> int:
    cho, jung, jong = decompose_hangul_char(ch)
    return (
        STROKE_COUNT.get(cho, 0)
        + STROKE_COUNT.get(jung, 0)
        + STROKE_COUNT.get(jong, 0)
    )


def name_to_strokes(name: str) -> List[int]:
    return [hangul_char_stroke_count(ch) for ch in name]


def interleave_numbers(a: List[int], b: List[int]) -> List[int]:
    """두 이름 획수를 번갈아 배치. 길이가 다르면 남은 글자는 뒤에 붙인다."""
    result = []
    max_len = max(len(a), len(b))
    for i in range(max_len):
        if i < len(a):
            result.append(a[i])
        if i < len(b):
            result.append(b[i])
    return result


def reduce_to_score(numbers: List[int]) -> Tuple[int, List[List[int]]]:
    """인접 숫자를 더해 1의 자리만 남기는 과정을 반복하여 마지막 두 자리 점수 생성."""
    steps = [numbers[:]]
    current = numbers[:]

    while len(current) > 2:
        current = [(current[i] + current[i + 1]) % 10 for i in range(len(current) - 1)]
        steps.append(current[:])

    if len(current) == 1:
        score = current[0]
    else:
        score = current[0] * 10 + current[1]
    return score, steps


def grade_by_score(score: int) -> Tuple[str, str]:
    if score >= 90:
        return "S급 케미", "이 조합은 그냥 드라마 한 편이에요. 이름만 봐도 분위기가 꽤 잘 맞는 느낌입니다."
    if score >= 80:
        return "완전 좋은 궁합", "서로 다른 점이 있어도 은근히 잘 맞춰가는 조합이에요. 장난치다가도 분위기가 좋아질 타입입니다."
    if score >= 70:
        return "꽤 좋은 궁합", "처음엔 평범해 보여도 볼수록 편해지는 조합이에요. 천천히 가까워지는 케미가 있습니다."
    if score >= 60:
        return "무난한 궁합", "엄청 강렬하진 않아도 편하게 지낼 수 있는 조합이에요. 서로 배려하면 충분히 좋아질 수 있어요."
    if score >= 50:
        return "반반 궁합", "잘 맞는 부분과 살짝 엇갈리는 부분이 같이 있어요. 대화 스타일만 맞추면 분위기가 꽤 괜찮아질 수 있습니다."
    if score >= 30:
        return "티격태격 궁합", "서로 다른 점이 좀 보여요. 그래도 오히려 티격태격하면서 기억에 남는 조합일 수도 있습니다."
    return "예능형 궁합", "조용히 잘 맞는다기보다는 예상 못 한 웃긴 상황이 많이 생길 조합이에요. 재미는 확실합니다."


def calculate_name_compatibility(name1: str, name2: str) -> NameCompatibilityResult:
    n1 = clean_name_token(name1)
    n2 = clean_name_token(name2)

    if not is_valid_name(n1) or not is_valid_name(n2):
        raise ValueError("이름은 2~5글자의 한글 이름으로 입력해주세요.")

    n1_strokes = name_to_strokes(n1)
    n2_strokes = name_to_strokes(n2)
    start_numbers = interleave_numbers(n1_strokes, n2_strokes)
    score, steps = reduce_to_score(start_numbers)
    grade, comment = grade_by_score(score)

    return NameCompatibilityResult(
        name1=n1,
        name2=n2,
        score=score,
        grade=grade,
        comment=comment,
        name1_strokes=n1_strokes,
        name2_strokes=n2_strokes,
        start_numbers=start_numbers,
        steps=steps,
    )


# =========================================================
# 4) 응답 생성
# =========================================================
def format_steps_for_display(steps: List[List[int]], max_lines: int = 4) -> str:
    """계산 과정이 너무 길어지지 않게 앞부분과 마지막만 표시."""
    if not steps:
        return ""

    lines = []
    shown = steps[:max_lines]
    for step in shown:
        lines.append(" ".join(str(n) for n in step))

    if len(steps) > max_lines:
        lines.append("...")
        lines.append(" ".join(str(n) for n in steps[-1]))

    return "\n".join(lines)


def build_name_compatibility_text(name1: str, name2: str, show_steps: bool = True) -> str:
    result = calculate_name_compatibility(name1, name2)

    n1_stroke_text = " + ".join(map(str, result.name1_strokes))
    n2_stroke_text = " + ".join(map(str, result.name2_strokes))

    text = (
        f"💕 {result.name1} × {result.name2} 이름 궁합\n\n"
        f"궁합 점수: {result.score}점\n"
        f"결과: {result.grade}\n\n"
        f"{result.comment}\n\n"
        f"이름 획수\n"
        f"- {result.name1}: {n1_stroke_text}\n"
        f"- {result.name2}: {n2_stroke_text}"
    )

    if show_steps:
        text += "\n\n계산 흐름\n" + format_steps_for_display(result.steps)

    text += "\n\n※ 재미로 보는 이름 궁합이에요. 진짜 관계는 대화와 타이밍이 더 중요합니다 😄"
    return text


def route_name_compatibility_by_utterance(utterance: str) -> str:
    parsed = parse_two_names(utterance)
    if not parsed:
        return (
            "이름 궁합을 보려면 이름 2개를 같이 입력해주세요.\n\n"
            "예시\n"
            "홍길동-홍길순 궁합\n"
            "홍길동이랑 김민지 이름궁합\n"
            "이름궁합 홍길동 홍길순"
        )

    name1, name2 = parsed
    try:
        return build_name_compatibility_text(name1, name2)
    except ValueError:
        return (
            "이름을 제대로 인식하지 못했어요.\n"
            "2~5글자의 한글 이름 2개로 입력해주세요.\n\n"
            "예시: 홍길동-홍길순 궁합"
        )


if __name__ == "__main__":
    examples = [
        "홍길동-홍길순 궁합",
        "홍길동이랑 김민지 이름궁합",
        "이름궁합 홍길동 홍길순",
        "홍길동/홍길순",
        "궁합 봐줘",
    ]
    for ex in examples:
        print("=" * 40)
        print(ex)
        print(route_name_compatibility_by_utterance(ex))
