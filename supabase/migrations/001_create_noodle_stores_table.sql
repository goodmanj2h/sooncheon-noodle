-- ==============================================================================
-- 마이그레이션 파일: 001_create_noodle_stores_table.sql
-- 설명: 전라남도 순천시 국수·칼국수 매장 정보 및 상권 분석 데이터를 저장하는 테이블 생성
-- 관리 규칙: supabase/migrations 디렉토리에 000_ 순서 번호로 관리
-- 보안 규칙: Row Level Security(RLS) 활성화로 안전한 데이터 보호
-- ==============================================================================

-- 1. 순천시 국수 매장 테이블 생성
CREATE TABLE IF NOT EXISTS public.sooncheon_noodle_stores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),            -- 고유 식별자 (UUID)
    store_id VARCHAR(50) UNIQUE NOT NULL,                     -- 상가 고유 코드
    store_name VARCHAR(100) NOT NULL,                         -- 상호명 (예: 순천옛날손칼국수)
    branch_name VARCHAR(50) DEFAULT '',                       -- 지점명 (예: 조례본점)
    category_large VARCHAR(50) DEFAULT '음식',                -- 업종 대분류
    category_middle VARCHAR(50) DEFAULT '한식',               -- 업종 중분류
    category_small VARCHAR(50) DEFAULT '국수/칼국수',         -- 업종 소분류
    dong_name VARCHAR(50) NOT NULL,                           -- 행정동/법정동명 (예: 조례동, 연향동)
    address_road VARCHAR(255) NOT NULL,                       -- 도로명 주소
    address_jibun VARCHAR(255) DEFAULT '',                    -- 지번 주소
    lat NUMERIC(10, 7) NOT NULL,                              -- 위도 (Latitude)
    lng NUMERIC(10, 7) NOT NULL,                              -- 경도 (Longitude)
    area_sqm NUMERIC(8, 2) DEFAULT 0.0,                       -- 매장 면적 (제곱미터 ㎡)
    area_pyeong NUMERIC(6, 1) DEFAULT 0.0,                    -- 매장 평수 (평)
    status VARCHAR(20) DEFAULT '영업중',                      -- 영업 상태 (영업중, 폐업 등)
    opened_year VARCHAR(10) DEFAULT '',                       -- 개업 년도
    est_monthly_sales_manwon INTEGER DEFAULT 0,               -- 상권 추정 월매출 (만원)
    est_deposit_manwon INTEGER DEFAULT 0,                     -- 상가 추정 보증금 (만원)
    est_monthly_rent_manwon INTEGER DEFAULT 0,                -- 상가 추정 월세 (만원)
    source VARCHAR(100) DEFAULT '공공데이터포털',             -- 데이터 출처
    created_at TIMESTAMPTZ DEFAULT NOW(),                     -- 등록 일시
    updated_at TIMESTAMPTZ DEFAULT NOW()                      -- 수정 일시
);

-- 2. 검색 속도 향상을 위한 인덱스(Index) 생성
-- 모바일에서 동별 필터링, 평수 정렬, 지도 좌표 검색이 0.01초 만에 실행되도록 인덱스를 설정합니다.
CREATE INDEX IF NOT EXISTS idx_noodle_dong_name ON public.sooncheon_noodle_stores (dong_name);
CREATE INDEX IF NOT EXISTS idx_noodle_area_pyeong ON public.sooncheon_noodle_stores (area_pyeong);
CREATE INDEX IF NOT EXISTS idx_noodle_lat_lng ON public.sooncheon_noodle_stores (lat, lng);

-- 3. 강력한 보안 설정 (Row Level Security - RLS 활성화)
-- 규칙 8 준수: 무단 수정 및 데이터 변조를 원천 차단합니다.
ALTER TABLE public.sooncheon_noodle_stores ENABLE ROW LEVEL SECURITY;

-- 4. 읽기 정책: 모바일 대시보드 사용자는 누구나(익명 포함) 안전하게 데이터를 조회할 수 있습니다.
CREATE POLICY "누구나 순천시 국수집 데이터를 조회할 수 있습니다"
ON public.sooncheon_noodle_stores
FOR SELECT
TO anon, authenticated
USING (true);

-- 5. 쓰기/수정/삭제 정책: 서비스 롤(관리자 키)을 가진 백엔드 데이터 파이프라인만 수정할 수 있습니다.
CREATE POLICY "관리자만 데이터를 등록 및 수정할 수 있습니다"
ON public.sooncheon_noodle_stores
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

