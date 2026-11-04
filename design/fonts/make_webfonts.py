"""원본 글꼴에서 웹용 woff2 서브셋을 만든다.

남기는 글자: KS X 1001 한글 2,350자 + 영문·숫자·기본 기호 + 한글 자모 + 자주 쓰는 기호.
가변 글꼴은 굵기 축을 그대로 남긴다.

    conda activate pro_1
    python design/fonts/make_webfonts.py
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

from fontTools import subset

ROOT = Path(__file__).resolve().parent
# 서비스에 쓰는 글꼴(11-01 결정: Noto Sans KR)만 프론트 public에 두고, 나머지 후보는 비교용으로 design/fonts/web에 둔다.
# public에 두면 배포 결과물(dist)에 그대로 복사되기 때문(리뷰 QA-17).
USED = {"noto-sans-kr"}
OUT = ROOT.parent.parent / "frontend" / "public" / "fonts"
OUT_SPARE = ROOT / "web"

# (출력 폴더, 원본 파일, 출력 파일 이름)
TARGETS = [
    (
        "noto-sans-kr",
        "noto-sans-kr/original/NotoSansKR[wght].ttf",
        "NotoSansKR-Variable.subset.woff2",
    ),
    ("pretendard", "pretendard/original/PretendardVariable.ttf", "PretendardVariable.subset.woff2"),
    ("freesentation", "freesentation/original/FreesentationVF.ttf", "FreesentationVF.subset.woff2"),
    ("suit", "suit/original/SUIT-Variable.ttf", "SUIT-Variable.subset.woff2"),
    (
        "spoqa-han-sans-neo",
        "spoqa-han-sans-neo/original/SpoqaHanSansNeo-Regular.ttf",
        "SpoqaHanSansNeo-Regular.subset.woff2",
    ),
    (
        "spoqa-han-sans-neo",
        "spoqa-han-sans-neo/original/SpoqaHanSansNeo-Medium.ttf",
        "SpoqaHanSansNeo-Medium.subset.woff2",
    ),
    (
        "spoqa-han-sans-neo",
        "spoqa-han-sans-neo/original/SpoqaHanSansNeo-Bold.ttf",
        "SpoqaHanSansNeo-Bold.subset.woff2",
    ),
]


def ks_x_1001_hangul() -> str:
    """EUC-KR 0xB0A1~0xC8FE 영역의 완성형 한글 2,350자."""
    chars = []
    for lead in range(0xB0, 0xC9):
        for trail in range(0xA1, 0xFF):
            with contextlib.suppress(UnicodeDecodeError):
                chars.append(bytes([lead, trail]).decode("euc-kr"))
    return "".join(chars)


def unicode_ranges() -> list[int]:
    ranges = [
        (0x0020, 0x007E),  # 영문·숫자·기본 기호
        (0x00A0, 0x00FF),  # 라틴-1 (·, ×, © 등)
        (0x2010, 0x2027),  # 대시·따옴표·말줄임
        (0x2030, 0x203A),
        (0x20A9, 0x20A9),  # ₩
        (0x2190, 0x2199),  # 화살표
        (0x2460, 0x2473),  # ①~⑳
        (0x25A0, 0x25CF),  # 도형
        (0x2605, 0x2606),  # ★☆
        (0x3000, 0x303F),  # CJK 기호
        (0x3131, 0x318E),  # 한글 자모
    ]
    codes = [c for start, end in ranges for c in range(start, end + 1)]
    codes += [ord(ch) for ch in ks_x_1001_hangul()]
    return codes


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    codes = unicode_ranges()
    for folder, src, name in TARGETS:
        out_dir = (OUT if folder in USED else OUT_SPARE) / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        options = subset.Options()
        options.flavor = "woff2"
        options.layout_features = ["*"]
        options.name_IDs = ["*"]
        options.notdef_outline = True
        font = subset.load_font(str(ROOT / src), options)
        subsetter = subset.Subsetter(options)
        subsetter.populate(unicodes=codes)
        subsetter.subset(font)
        out = out_dir / name
        subset.save_font(font, str(out), options)
        src_kb = (ROOT / src).stat().st_size // 1024
        print(f"{name}: {src_kb:,} KB → {out.stat().st_size // 1024:,} KB")


if __name__ == "__main__":
    main()
