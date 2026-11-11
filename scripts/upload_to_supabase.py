# -*- coding: utf-8 -*-
"""
================================================================================
프로그램 명칭: Supabase 클라우드 데이터베이스 자동 동기화 스크립트 (upload_to_supabase.py)
목적:
  1. data/sooncheon_noodle_stores.json에 정제된 순천시 국수집 데이터를
     클라우드 DB(Supabase PostgreSQL)에 안전하게 일괄 업로드(Upsert)합니다.
  2. 컴퓨터가 꺼져 있어도 스마트폰이 Supabase REST API를 통해 24시간 언제든
     최신 순천시 국수집 현황을 실시간으로 불러올 수 있도록 지원합니다.
  3. 보안 규칙 준수: 민감한 DB 접속 키는 .env 파일에서만 읽어옵니다.
================================================================================
"""

import os
import json
import requests
from dotenv import load_dotenv

# ------------------------------------------------------------------------------
# 1. 환경 변수(.env) 로드 및 보안 설정
# ------------------------------------------------------------------------------
# .env 파일에서 Supabase 프로젝트 접속 정보를 불러옵니다.
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
# 데이터를 DB에 직접 쓰고 수정하려면 Service Role Key 또는 적절한 권한을 가진 키가 필요합니다.
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.getenv("SUPABASE_ANON_KEY", "").strip()

# 업로드할 데이터 파일 경로
DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sooncheon_noodle_stores.json")


def upload_stores_to_supabase():
    """
    정제된 순천시 국수집 JSON 데이터를 Supabase 테이블에 업로드하는 메인 함수
    """
    print("\n>>> [2단계] Supabase 클라우드 데이터베이스 업로드 시작 <<<")

    # 1. 파일 존재 여부 확인
    if not os.path.exists(DATA_PATH):
        print(f"[!] 업로드할 데이터 파일이 존재하지 않습니다: {DATA_PATH}")
        print("    먼저 'python3 scripts/fetch_data.py'를 실행하여 데이터를 수집하세요.")
        return False

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        stores = json.load(f)

    if not stores:
        print("[!] 업로드할 데이터 항목이 0건입니다.")
        return False

    print(f"[*] 업로드 대상 데이터: 총 {len(stores)}개 매장")

    # 2. Supabase 환경변수 설정 여부 검증
    if not SUPABASE_URL or not SUPABASE_KEY or "여기에" in SUPABASE_URL:
        print("\n" + "=" * 65)
        print("💡 [안내] 아직 .env 파일에 Supabase 접속 정보가 설정되지 않았습니다.")
        print("=" * 65)
        print("  1) https://supabase.com 무료 가입 후 새 프로젝트를 생성합니다.")
        print("  2) Settings > API 메뉴에서 Project URL과 anon/service_role 키를 복사합니다.")
        print("  3) .env 파일에 아래와 같이 붙여넣으신 후 다시 실행하시면 됩니다:")
        print("     SUPABASE_URL=https://your-project-id.supabase.co")
        print("     SUPABASE_SERVICE_ROLE_KEY=your-secret-service-role-key")
        print("=" * 65 + "\n")
        return False

    # 3. Supabase REST API 엔드포인트 설정
    # 테이블명: sooncheon_noodle_stores
    endpoint = f"{SUPABASE_URL}/rest/v1/sooncheon_noodle_stores"

    # HTTP 요청 헤더 (Supabase 인증 및 Upsert 설정)
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        # on_conflict=store_id: 이미 등록된 매장이면 중복 생성하지 않고 최신 정보로 덮어쓰기(Upsert)
        "Prefer": "resolution=merge-duplicates"
    }

    # 4. 데이터 업로드 요청 (POST / Upsert)
    try:
        print(f"[*] Supabase 서버로 전송 중... ({endpoint})")
        response = requests.post(endpoint, headers=headers, json=stores, timeout=15)

        if response.status_code in [200, 201]:
            print(f"[V] 축하합니다! 순천시 국수집 {len(stores)}개 데이터가 클라우드 DB에 성공적으로 저장되었습니다.")
            print("    이제 컴퓨터를 꺼도 스마트폰에서 클라우드 DB를 통해 언제든 데이터를 조회할 수 있습니다.")
            return True
        else:
            print(f"[!] 업로드 실패 (HTTP 상태 코드: {response.status_code})")
            print(f"    서버 응답 내용: {response.text}")
            print("    * 팁: Supabase SQL Editor에서 001_create_noodle_stores_table.sql 테이블을 먼저 생성했는지 확인하세요.")
            return False

    except Exception as e:
        print(f"[!] 네트워크 통신 오류 발생: {e}")
        return False


if __name__ == "__main__":
    upload_stores_to_supabase()

