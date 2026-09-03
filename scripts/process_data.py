#!/usr/bin/env python3
"""
process_data.py - _rawdata/page{1,2}.json (전국도시공원정보표준데이터)을
Jekyll 페이지 생성용 JSON으로 가공.

입력: _rawdata/page1.json, _rawdata/page2.json (data.go.kr standard.json 원본)
출력: _data_src/parks.json (개별 공원), _data_src/regions.json (시도/시군구 집계)

사용법:
  python scripts/process_data.py
"""
import json, re, hashlib, sys
from pathlib import Path
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
RAW_FILES = [ROOT / "_rawdata" / "page1.json", ROOT / "_rawdata" / "page2.json"]
PARKS_OUT = ROOT / "_data_src" / "parks.json"
REGIONS_OUT = ROOT / "_data_src" / "regions.json"
SEARCH_INDEX_OUT = ROOT / "search_index.json"

SIDO_FULL_TO_SHORT = {
    "서울특별시": "서울", "부산광역시": "부산", "인천광역시": "인천",
    "대구광역시": "대구", "광주광역시": "광주", "대전광역시": "대전",
    "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기",
    "강원특별자치도": "강원", "강원도": "강원",
    "충청북도": "충북", "충청남도": "충남",
    "전북특별자치도": "전북", "전라북도": "전북", "전라남도": "전남",
    "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주", "제주도": "제주",
}


def guess_sido_sggu(addr: str):
    """주소 문자열(도로명주소/지번주소)에서 시도/시군구 파싱."""
    text = (addr or "").strip()
    if not text:
        return "", ""
    if text.startswith("전남광주통합특별시"):
        rest = text[len("전남광주통합특별시"):].strip()
        sggu = rest.split()[0] if rest else ""
        short = "광주" if sggu.endswith("구") else "전남"
        return short, sggu
    tokens = text.split()
    if not tokens:
        return "", ""
    sido_full = tokens[0]
    short = SIDO_FULL_TO_SHORT.get(sido_full, "")
    sggu = tokens[1] if len(tokens) > 1 else ""
    return short, sggu


def make_slug(name: str, addr: str) -> str:
    slug = re.sub(r"[^\w가-힣\s-]", "", name).strip()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    h = hashlib.md5(f"{name}|{addr}".encode("utf-8")).hexdigest()[:6]
    return f"{slug}-{h}" if slug else h


def main():
    raw = []
    for f in RAW_FILES:
        if f.exists():
            raw.extend(json.loads(f.read_text(encoding="utf-8")))
    print(f"원본 레코드 수: {len(raw)}")

    items = []
    seen_slugs = Counter()
    no_region = 0
    for d in raw:
        park_name = (d.get("PARK_NM") or "").strip()
        rdnmadr = (d.get("RDNMADR") or "").strip()
        lnmadr = (d.get("LNMADR") or "").strip()
        addr = rdnmadr or lnmadr
        if not park_name or not addr:
            continue

        do_short, sigungu = guess_sido_sggu(addr)
        if not do_short:
            no_region += 1
            continue

        lat = (d.get("LATITUDE") or "").strip()
        lng = (d.get("LONGITUDE") or "").strip()

        slug = make_slug(park_name, addr)
        seen_slugs[slug] += 1
        if seen_slugs[slug] > 1:
            slug = f"{slug}-{seen_slugs[slug]}"

        # 시설 필드는 "A+B+C" 형태 -> 리스트로 분리, 빈 값 제거
        def split_fclty(key):
            raw_v = (d.get(key) or "").strip()
            if not raw_v:
                return []
            return [x.strip() for x in re.split(r"[+,/]", raw_v) if x.strip()]

        items.append({
            "parkName": park_name,
            "parkType": (d.get("PARK_SE") or "").strip(),
            "doShort": do_short,
            "sigungu": sigungu,
            "addr": addr,
            "area": (d.get("PARK_AR") or "").strip(),
            "lat": lat,
            "lng": lng,
            "sportFacility": split_fclty("MVM_FCLTY"),
            "playFacility": split_fclty("AMSMT_FCLTY"),
            "convFacility": split_fclty("CNVNNC_FCLTY"),
            "cultureFacility": split_fclty("CLTR_FCLTY"),
            "etcFacility": split_fclty("ETC_FCLTY"),
            "institution": (d.get("INSTITUTION_NM") or "").strip(),
            "tel": (d.get("PHONE_NUMBER") or "").strip(),
            "slug": slug,
        })

    PARKS_OUT.parent.mkdir(parents=True, exist_ok=True)
    PARKS_OUT.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    print(f"공원 {len(items)}개 저장 -> {PARKS_OUT}")
    print(f"지역 파싱 실패로 제외: {no_region}건")

    coord_count = sum(1 for i in items if i["lat"] and i["lng"])
    print(f"좌표 보유: {coord_count}개 / {len(items)}개")

    # 지역 집계 (시도 -> 시군구 -> 개수)
    region_map = defaultdict(lambda: defaultdict(int))
    for i in items:
        region_map[i["doShort"]][i["sigungu"]] += 1

    regions = []
    for do_short, sggu_map in sorted(region_map.items()):
        regions.append({
            "doShort": do_short,
            "count": sum(sggu_map.values()),
            "sigungus": [
                {"name": s, "count": c}
                for s, c in sorted(sggu_map.items(), key=lambda x: -x[1])
            ],
        })
    regions.sort(key=lambda x: -x["count"])
    REGIONS_OUT.write_text(json.dumps(regions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"지역 집계 저장 -> {REGIONS_OUT}")

    print("\n시도별 개수:")
    for r in regions:
        print(f"  {r['doShort']}: {r['count']}개 ({len(r['sigungus'])}개 시군구)")

    index = [
        {"n": i["parkName"], "slug": i["slug"], "doShort": i["doShort"], "sigungu": i["sigungu"]}
        for i in items
    ]
    SEARCH_INDEX_OUT.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_mb = SEARCH_INDEX_OUT.stat().st_size / 1024 / 1024
    print(f"\n검색 인덱스 {len(index)}건 저장 -> {SEARCH_INDEX_OUT} ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
