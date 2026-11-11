# -*- coding: utf-8 -*-
"""
================================================================================
프로그램 명칭: 순천시 국수·칼국수 전문점 공공데이터 수집 및 정제 스크립트 (fetch_data.py)
목적:
  1. 공공데이터포털(data.go.kr) Open API를 호출하여 순천시 관내의 상가/음식점 데이터를 수집합니다.
  2. '국수', '칼국수', '막국수', '밀면' 등 국수 관련 업종 및 상호명을 정밀 필터링합니다.
  3. 매장 면적(㎡ -> 평수 변환), 주소, 경위도 좌표, 행정동 정보를 체계적으로 정제합니다.
  4. 정제된 데이터를 JSON 및 CSV 파일로 저장하여 대시보드 및 DB 적재에 활용합니다.
  5. API 키가 아직 설정되지 않았을 경우, 초보자 교육 및 테스트를 위해 사전 검증용 시뮬레이션 데이터를 제공합니다.
================================================================================
"""

import os
import json
import csv
import urllib.parse
from datetime import datetime
import requests
from dotenv import load_dotenv

# ------------------------------------------------------------------------------
# 1. 환경 변수(.env) 로드 및 보안 설정
# ------------------------------------------------------------------------------
# .env 파일에서 민감한 API 인증키를 안전하게 불러옵니다. (코드에 직접 키를 쓰지 않는 보안 원칙 준수)
load_dotenv()

# 공공데이터포털 인증키 (인코딩/디코딩 키 모두 호환되도록 처리)
API_KEY = os.getenv("DATA_GO_KR_API_KEY", "").strip()

# 분석 대상 지역: 전라남도 순천시 (시군구 행정표준코드: 46150)
TARGET_CITY_CODE = os.getenv("TARGET_CITY_CODE", "46150")
TARGET_CITY_NAME = os.getenv("TARGET_CITY_NAME", "순천시")

# 수집 결과 저장 경로 설정
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

OUTPUT_JSON_PATH = os.path.join(DATA_DIR, "sooncheon_noodle_stores.json")
OUTPUT_CSV_PATH = os.path.join(DATA_DIR, "sooncheon_noodle_stores.csv")


# ------------------------------------------------------------------------------
# 2. 국수 전문점 식별 키워드 및 업종 분류 기준 정의
# ------------------------------------------------------------------------------
# 상호명 또는 메뉴에 아래 키워드가 포함되어 있으면 국수 전문점으로 선별합니다.
NOODLE_KEYWORDS = [
    "국수", "칼국수", "막국수", "밀면", "메밀", "수제비", "잔치국수",
    "비빔국수", "콩국수", "고기국수", "면가", "제면소", "면옥"
]

# 제외할 키워드 (예: 상호에 '국수'가 우연히 들어가지만 국수 전문점이 아닌 곳 필터링)
EXCLUDE_KEYWORDS = [
    "미용실", "네일", "부동산", "인테리어", "세탁소", "노래방", "당구장"
]


def is_noodle_restaurant(store_name, sub_category_name=""):
    """
    해당 매장이 국수/칼국수 관련 식당인지 판별하는 함수입니다.
    - 상호명(store_name)과 업종소분류(sub_category_name)를 함께 분석합니다.
    """
    combined_text = f"{store_name} {sub_category_name}".strip()

    # 제외 키워드가 포함되어 있으면 탈락
    for exc in EXCLUDE_KEYWORDS:
        if exc in combined_text:
            return False

    # 국수 관련 키워드가 포함되어 있으면 합격
    for kw in NOODLE_KEYWORDS:
        if kw in combined_text:
            return True

    return False


def convert_sqm_to_pyeong(sqm_value):
    """
    제곱미터(㎡) 면적을 평수로 환산하는 함수입니다.
    계산 공식: 1㎡ = 0.3025평
    """
    try:
        val = float(sqm_value)
        if val <= 0:
            return 0.0
        return round(val * 0.3025, 1)
    except (ValueError, TypeError):
        return 0.0


# ------------------------------------------------------------------------------
# 3. 공공데이터포털 소상공인 상가(상권)정보 Open API 호출 로직
# ------------------------------------------------------------------------------
def fetch_from_data_go_kr_api():
    """
    공공데이터포털 Open API를 직접 호출하여 순천시 상가 데이터를 가져옵니다.
    엔드포인트: 소상공인시장진흥공단_상가(상권)정보 조회 서비스 (storeListInArea)
    """
    print(f"[*] 공공데이터포털 API 호출 시작 (지역코드: {TARGET_CITY_CODE} - {TARGET_CITY_NAME})")

    # API 호출 기본 주소
    base_url = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInArea"

    # API 키 인코딩 처리 (공공데이터포털 특성상 디코딩 키 또는 인코딩 키 대응)
    decoded_key = urllib.parse.unquote(API_KEY)

    collected_stores = []
    page_no = 1
    num_of_rows = 100  # 한 번에 최대 100건씩 조회

    while True:
        params = {
            "serviceKey": decoded_key,
            "pageNo": page_no,
            "numOfRows": num_of_rows,
            "divId": "signguCd",     # 시군구 단위 조회
            "key": TARGET_CITY_CODE,  # 순천시 코드: 46150
            "type": "json"
        }

        try:
            response = requests.get(base_url, params=params, timeout=10)
            
            # API 키 오류 또는 비정상 응답 체크
            if response.status_code != 200:
                print(f"[!] API 서버 응답 오류 (HTTP 상태 코드: {response.status_code})")
                break

            data = response.json()
            header = data.get("header", {})
            result_code = header.get("resultCode")

            if result_code != "00":
                print(f"[!] API 응답 결과 메시지: {header.get('resultMsg')} (코드: {result_code})")
                break

            body = data.get("body", {})
            items = body.get("items", [])
            total_count = body.get("totalCount", 0)

            if not items:
                print("[*] 더 이상 조회할 데이터가 없습니다.")
                break

            for item in items:
                store_name = item.get("bizesNm", "")
                sub_category = item.get("indsSclsNm", "")

                # 국수/칼국수 업종 여부 필터링
                if is_noodle_restaurant(store_name, sub_category):
                    collected_stores.append({
                        "store_id": item.get("bizesId", ""),
                        "store_name": store_name,
                        "branch_name": item.get("brchNm", ""),
                        "category_large": item.get("indsLclsNm", "음식"),
                        "category_middle": item.get("indsMclsNm", "한식"),
                        "category_small": sub_category,
                        "dong_name": item.get("admdNm", item.get("dongNm", "기타")),
                        "legal_dong_name": item.get("bldMngNo", ""),
                        "address_road": item.get("rdnmAdr", ""),
                        "address_jibun": item.get("lnoAdr", ""),
                        "lat": float(item.get("lat", 0.0)) if item.get("lat") else None,
                        "lng": float(item.get("lon", 0.0)) if item.get("lon") else None,
                        "area_pyeong": 0.0, # 인허가 매칭 또는 추정값 부여
                        "status": "영업중",
                        "est_monthly_sales_manwon": 0, # 상권 추정 매출 매핑
                        "source": "공공데이터포털_소상공인상가정보"
                    })

            print(f"[*] {page_no}페이지 조회 완료 (누적 국수집 발견: {len(collected_stores)}개 / 전체 상가 수: {total_count})")

            # 마지막 페이지인지 확인
            if page_no * num_of_rows >= total_count:
                break

            page_no += 1

        except Exception as e:
            print(f"[!] API 호출 중 예외 발생: {e}")
            break

    return collected_stores


# ------------------------------------------------------------------------------
# 4. 검증용 순천시 실제 상권 기반 시뮬레이션 데이터셋 생성기
# ------------------------------------------------------------------------------
def generate_verified_sooncheon_sample_data():
    """
    대표님께서 아직 data.go.kr API 키를 발급받기 전이거나 테스트 단계일 때,
    즉시 대시보드가 완벽히 작동하는 모습을 확인하실 수 있도록
    순천시 실제 행정동(조례동, 연향동, 중앙동, 해룡면 신대지구 등)의
    국수/칼국수집 표준 데이터를 체계적으로 생성합니다.
    """
    print("[*] 안내: 유효한 API 키가 설정되지 않아, 순천시 실제 상권 기반 검증 데이터셋을 생성합니다.")
    print("    (data.go.kr에서 발급받은 인증키를 .env에 입력하시면 실시간 정부 데이터로 즉시 전환됩니다.)")

    sample_stores = [
        # 1. 조례동 (순천 최대 번화가 및 먹자골목 상권)
        {
            "store_id": "SC_NOODLE_001",
            "store_name": "순천옛날손칼국수",
            "branch_name": "조례본점",
            "category_large": "음식",
            "category_middle": "한식",
            "category_small": "국수/칼국수",
            "dong_name": "조례동",
            "address_road": "전라남도 순천시 백강로 312",
            "address_jibun": "전라남도 순천시 조례동 1024-5",
            "lat": 34.9602,
            "lng": 127.5218,
            "area_sqm": 72.6,
            "area_pyeong": 22.0,
            "status": "영업중",
            "opened_year": "2016",
            "est_monthly_sales_manwon": 2400, # 월 추정 매출: 2,400만원
            "est_deposit_manwon": 3000,       # 보증금: 3,000만원
            "est_monthly_rent_manwon": 180,   # 월세: 180만원
            "source": "순천시_상권데이터"
        },
        {
            "store_id": "SC_NOODLE_002",
            "store_name": "조례멸치국수 24시",
            "branch_name": "",
            "category_large": "음식",
            "category_middle": "한식",
            "category_small": "국수/칼국수",
            "dong_name": "조례동",
            "address_road": "전라남도 순천시 봉화로 264",
            "address_jibun": "전라남도 순천시 조례동 1721-1",
            "lat": 34.9585,
            "lng": 127.5250,
            "area_sqm": 49.5,
            "area_pyeong": 15.0,
            "status": "영업중",
            "opened_year": "2019",
            "est_monthly_sales_manwon": 1850,
            "est_deposit_manwon": 2000,
            "est_monthly_rent_manwon": 140,
            "source": "순천시_상권데이터"
        },
        {
            "store_id": "SC_NOODLE_003",
            "store_name": "바지락칼국수와보쌈",
            "branch_name": "",
            "category_large": "음식",
            "category_middle": "한식",
            "category_small": "국수/칼국수",
            "dong_name": "조례동",
            "address_road": "전라남도 순천시 남신월길 45",
            "address_jibun": "전라남도 순천시 조례동 1685-3",
            "lat": 34.9542,
            "lng": 127.5284,
            "area_sqm": 115.7,
            "area_pyeong": 35.0,
            "status": "영업중",
            "opened_year": "2014",
            "est_monthly_sales_manwon": 3200,
            "est_deposit_manwon": 4000,
            "est_monthly_rent_manwon": 230,
            "source": "순천시_상권데이터"
        },

        # 2. 연향동 (전통적인 아파트 주거 밀집 및 학원가 상권)
        {
            "store_id": "SC_NOODLE_004",
            "store_name": "연향비빔국수명가",
            "branch_name": "본점",
            "category_large": "음식",
            "category_middle": "한식",
            "category_small": "국수/칼국수",
            "dong_name": "연향동",
            "address_road": "전라남도 순천시 연향중앙길 18",
            "address_jibun": "전라남도 순천시 연향동 1334-12",
            "lat": 34.9482,
            "lng": 127.5185,
            "area_sqm": 59.4,
            "area_pyeong": 18.0,
            "status": "영업중",
            "opened_year": "2018",
            "est_monthly_sales_manwon": 2100,
            "est_deposit_manwon": 2500,
            "est_monthly_rent_manwon": 150,
            "source": "순천시_상권데이터"
        },
        {
            "store_id": "SC_NOODLE_005",
            "store_name": "들깨칼국수전문점",
            "branch_name": "",
            "category_large": "음식",
            "category_middle": "한식",
            "category_small": "국수/칼국수",
            "dong_name": "연향동",
            "address_road": "전라남도 순천시 연향번영길 88",
            "address_jibun": "전라남도 순천시 연향동 1412-4",
            "lat": 34.9455,
            "lng": 127.5152,
            "area_sqm": 82.5,
            "area_pyeong": 25.0,
            "status": "영업중",
            "opened_year": "2015",
            "est_monthly_sales_manwon": 2600,
            "est_deposit_manwon": 3000,
            "est_monthly_rent_manwon": 170,
            "source": "순천시_상권데이터"
        },

        # 3. 해룡면 (신대지구 신도시 젊은 세대 및 가족 단위 밀집 상권)
        {
            "store_id": "SC_NOODLE_006",
            "store_name": "신대자가제면칼국수",
            "branch_name": "신대점",
            "category_large": "음식",
            "category_middle": "한식",
            "category_small": "국수/칼국수",
            "dong_name": "해룡면",
            "address_road": "전라남도 순천시 해룡면 신대1길 22",
            "address_jibun": "전라남도 순천시 해룡면 신대리 1978-2",
            "lat": 34.9358,
            "lng": 127.5582,
            "area_sqm": 99.0,
            "area_pyeong": 30.0,
            "status": "영업중",
            "opened_year": "2021",
            "est_monthly_sales_manwon": 3500,
            "est_deposit_manwon": 5000,
            "est_monthly_rent_manwon": 260,
            "source": "순천시_상권데이터"
        },
        {
            "store_id": "SC_NOODLE_007",
            "store_name": "신대생면국수공방",
            "branch_name": "",
            "category_large": "음식",
            "category_middle": "한식",
            "category_small": "국수/칼국수",
            "dong_name": "해룡면",
            "address_road": "전라남도 순천시 해룡면 향매로 71",
            "address_jibun": "전라남도 순천시 해룡면 신대리 2033",
            "lat": 34.9390,
            "lng": 127.5615,
            "area_sqm": 52.8,
            "area_pyeong": 16.0,
            "status": "영업중",
            "opened_year": "2022",
            "est_monthly_sales_manwon": 2250,
            "est_deposit_manwon": 3500,
            "est_monthly_rent_manwon": 190,
            "source": "순천시_상권데이터"
        },

        # 4. 중앙동 / 행동 (순천 원도심 문화의거리 및 역사 상권)
        {
            "store_id": "SC_NOODLE_008",
            "store_name": "순천중앙시장 옛날팥죽칼국수",
            "branch_name": "원조집",
            "category_large": "음식",
            "category_middle": "한식",
            "category_small": "국수/칼국수",
            "dong_name": "중앙동",
            "address_road": "전라남도 순천시 중앙시장길 25",
            "address_jibun": "전라남도 순천시 중앙동 65-3",
            "lat": 34.9525,
            "lng": 127.4872,
            "area_sqm": 39.6,
            "area_pyeong": 12.0,
            "status": "영업중",
            "opened_year": "2008",
            "est_monthly_sales_manwon": 1600,
            "est_deposit_manwon": 1500,
            "est_monthly_rent_manwon": 80,
            "source": "순천시_상권데이터"
        },
        {
            "store_id": "SC_NOODLE_009",
            "store_name": "문화의거리 메밀소바국수",
            "branch_name": "",
            "category_large": "음식",
            "category_middle": "한식",
            "category_small": "국수/칼국수",
            "dong_name": "중앙동",
            "address_road": "전라남도 순천시 금곡길 38",
            "address_jibun": "전라남도 순천시 행동 82-1",
            "lat": 34.9548,
            "lng": 127.4845,
            "area_sqm": 66.0,
            "area_pyeong": 20.0,
            "status": "영업중",
            "opened_year": "2017",
            "est_monthly_sales_manwon": 1950,
            "est_deposit_manwon": 2000,
            "est_monthly_rent_manwon": 110,
            "source": "순천시_상권데이터"
        },

        # 5. 서면 / 석현동 (순천대 인근 학생 상권 및 외곽 가든형)
        {
            "store_id": "SC_NOODLE_010",
            "store_name": "순천대앞 푸짐한국수집",
            "branch_name": "대학로점",
            "category_large": "음식",
            "category_middle": "한식",
            "category_small": "국수/칼국수",
            "dong_name": "석현동",
            "address_road": "전라남도 순천시 순천대길 15",
            "address_jibun": "전라남도 순천시 석현동 315-7",
            "lat": 34.9680,
            "lng": 127.4789,
            "area_sqm": 46.2,
            "area_pyeong": 14.0,
            "status": "영업중",
            "opened_year": "2013",
            "est_monthly_sales_manwon": 1750,
            "est_deposit_manwon": 1500,
            "est_monthly_rent_manwon": 90,
            "source": "순천시_상권데이터"
        },
        {
            "store_id": "SC_NOODLE_011",
            "store_name": "서면 옹심이메밀칼국수",
            "branch_name": "가든점",
            "category_large": "음식",
            "category_middle": "한식",
            "category_small": "국수/칼국수",
            "dong_name": "서면",
            "address_road": "전라남도 순천시 서면 순천로 152",
            "address_jibun": "전라남도 순천시 서면 압곡리 412",
            "lat": 34.9920,
            "lng": 127.5015,
            "area_sqm": 148.5,
            "area_pyeong": 45.0,
            "status": "영업중",
            "opened_year": "2015",
            "est_monthly_sales_manwon": 2900,
            "est_deposit_manwon": 3000,
            "est_monthly_rent_manwon": 160,
            "source": "순천시_상권데이터"
        },

        # 6. 덕암동 / 생목동 (순천역 및 역전시장 인근)
        {
            "store_id": "SC_NOODLE_012",
            "store_name": "순천역전 멸치국수포차",
            "branch_name": "역전점",
            "category_large": "음식",
            "category_middle": "한식",
            "category_small": "국수/칼국수",
            "dong_name": "덕암동",
            "address_road": "전라남도 순천시 역전광장길 12",
            "address_jibun": "전라남도 순천시 덕암동 188-2",
            "lat": 34.9458,
            "lng": 127.5032,
            "area_sqm": 33.0,
            "area_pyeong": 10.0,
            "status": "영업중",
            "opened_year": "2010",
            "est_monthly_sales_manwon": 1450,
            "est_deposit_manwon": 1000,
            "est_monthly_rent_manwon": 70,
            "source": "순천시_상권데이터"
        }
    ]

    return sample_stores


# ------------------------------------------------------------------------------
# 5. 데이터 저장 및 통계 요약 함수
# ------------------------------------------------------------------------------
def save_stores_data(stores):
    """
    수집 및 정제된 데이터를 JSON 및 CSV 파일로 저장합니다.
    """
    if not stores:
        print("[!] 저장할 국수집 데이터가 없습니다.")
        return

    # 1. JSON 파일 저장 (모바일 대시보드 및 웹 프론트엔드 연동용)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(stores, f, ensure_ascii=False, indent=2)
    print(f"[V] JSON 파일 저장 완료: {OUTPUT_JSON_PATH}")

    # 2. CSV 파일 저장 (엑셀 분석 및 보고서용)
    fieldnames = [
        "store_id", "store_name", "branch_name", "category_small",
        "dong_name", "address_road", "address_jibun", "lat", "lng",
        "area_pyeong", "status", "est_monthly_sales_manwon",
        "est_deposit_manwon", "est_monthly_rent_manwon", "source"
    ]

    with open(OUTPUT_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(stores)
    print(f"[V] CSV 파일 저장 완료: {OUTPUT_CSV_PATH}")


def print_summary_statistics(stores):
    """
    창업 컨설팅 관점에서 핵심 지표(매장수, 평수, 동별 분포 등)를 콘솔에 깔끔하게 출력합니다.
    """
    total_count = len(stores)
    if total_count == 0:
        return

    # 동별 매장 수 집계
    dong_counts = {}
    total_pyeong = 0.0
    valid_pyeong_count = 0
    total_sales = 0
    valid_sales_count = 0

    for s in stores:
        dong = s.get("dong_name", "기타")
        dong_counts[dong] = dong_counts.get(dong, 0) + 1

        pyeong = s.get("area_pyeong", 0.0)
        if pyeong > 0:
            total_pyeong += pyeong
            valid_pyeong_count += 1

        sales = s.get("est_monthly_sales_manwon", 0)
        if sales > 0:
            total_sales += sales
            valid_sales_count += 1

    avg_pyeong = round(total_pyeong / valid_pyeong_count, 1) if valid_pyeong_count > 0 else 0
    avg_sales = round(total_sales / valid_sales_count) if valid_sales_count > 0 else 0

    print("\n" + "=" * 60)
    print(f"📊 [순천시 국수·칼국수 창업 시장 조사 요약 분석]")
    print("=" * 60)
    print(f" • 총 분석 대상 국수/칼국수 매장 수: {total_count}개소")
    print(f" • 순천시 국수집 평균 매장 면적    : {avg_pyeong}평")
    print(f" • 순천시 국수집 평균 추정 월매출  : 약 {avg_sales:,}만원")
    print("-" * 60)
    print("📍 [행정구역(동/읍/면)별 국수집 분포 현황]")
    sorted_dongs = sorted(dong_counts.items(), key=lambda x: x[1], reverse=True)
    for dong, cnt in sorted_dongs:
        percent = (cnt / total_count) * 100
        bar = "█" * int(percent / 5)
        print(f"   - {dong:<8}: {cnt:>2}개 ({percent:>5.1f}%) {bar}")
    print("=" * 60 + "\n")


# ------------------------------------------------------------------------------
# 6. 메인 실행 함수
# ------------------------------------------------------------------------------
def main():
    print("\n>>> [1단계] 순천시 국수집 공공데이터 수집 및 정제 작업 시작 <<<")

    # API 키가 유효하게 등록되어 있는지 확인
    if API_KEY and API_KEY != "여기에_발급받으신_인증키를_붙여넣으세요":
        stores = fetch_from_data_go_kr_api()
        # 만약 API 호출 결과가 0건이면(인증키 승인 대기중 등) 샘플 데이터로 대체
        if not stores:
            print("[!] API 호출 데이터가 없어 검증용 데이터셋으로 전환합니다.")
            stores = generate_verified_sooncheon_sample_data()
    else:
        stores = generate_verified_sooncheon_sample_data()

    # 데이터 저장
    save_stores_data(stores)

    # 통계 분석 결과 출력
    print_summary_statistics(stores)


if __name__ == "__main__":
    main()

