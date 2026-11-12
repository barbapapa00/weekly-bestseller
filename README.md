# 주간 베스트셀러

한국·미국 주요 서점의 **자기계발 · 아동 · 경제** 분야 베스트셀러 TOP 10을 모아 보여주는 사이트입니다.
매주 월요일 오전 9시(한국 시간)에 GitHub Actions가 자동으로 수집해 갱신합니다.

- 사이트: https://weekly-bestseller.vercel.app (Vercel)
- 데이터: Supabase 프로젝트 `weekly-bestseller` (서울 리전)

## 동작 방식

```
[매주 월 09:00] GitHub Actions → collect.py 실행
      ├─ 3개 서점에서 분야별 TOP10 수집
      ├─ Supabase에 저장 (snapshots: 주차별 전체 / bestseller_items: 책 한 권씩)
      └─ docs/data.json, data.js 갱신 (예비 데이터)

[방문자] Vercel 사이트 → Supabase에서 최신 주차 읽기 (실패하면 data.js 사용)
```

## 폴더 구성

| 파일 | 역할 |
|---|---|
| `collect.py` | 수집기. 사이트 목록(`SOURCES`)과 사이트별 수집 함수, Supabase 저장 |
| `docs/index.html` | 사이트 화면 (Vercel이 `docs` 폴더를 공개) |
| `docs/config.js` | Supabase 주소와 **공개용(publishable)** 키. 읽기 전용이라 공개돼도 안전 |
| `docs/data.json`, `docs/data.js` | 예비 데이터 (Supabase에 접속이 안 될 때 사용) |
| `supabase/migrations/` | 데이터베이스 테이블·보안 규칙 정의 |
| `vercel.json` | Vercel 배포 설정 |
| `.github/workflows/weekly-update.yml` | 매주 월요일 자동 실행 설정 |

## 비밀 정보 보관 위치

| 항목 | 위치 |
|---|---|
| Supabase secret 키, 주소 | GitHub 저장소 → Settings → Secrets (`SUPABASE_SECRET_KEY`, `SUPABASE_URL`) |
| Supabase DB 비밀번호 | 내 PC `%USERPROFILE%\.supabase\weekly-bestseller-db-password.txt` (Supabase 대시보드에서 재설정 가능) |

## 사이트 화면을 고친 뒤 다시 배포하기 (PowerShell)

```powershell
# docs 폴더를 Vercel 운영 주소로 배포
vercel deploy --prod --yes
```

## 내 PC에서 실행해 보기 (PowerShell)

```powershell
# 필요한 라이브러리 설치 (처음 한 번만)
py -m pip install -r requirements.txt
# 교보문고·영풍문고 수집용 브라우저 설치 (처음 한 번만)
py -m playwright install chromium

# 베스트셀러 수집 → docs/data.json, docs/data.js 갱신
py collect.py

# 결과 화면 열기
start docs\index.html
```

## 수집 현황

| 사이트 | 상태 |
|---|---|
| 예스24 | ✅ 수집 중 (일반 HTML) |
| 교보문고, 영풍문고 | ✅ 수집 중 (Playwright로 브라우저 렌더링) |
| 알라딘 | robots.txt가 자동 수집 비허용 → 링크만 제공 (공식 Open API TTB키가 있으면 추가 가능) |
| NYT 베스트셀러, Barnes & Noble | 링크만 제공 (NYT는 공식 API 키가 있으면 추가 가능) |
| Amazon | 약관상 자동 수집 금지 → 링크만 제공 |
| Bookshop.org, Books-A-Million, ThriftBooks | 봇 차단 → 링크만 제공 |
| 인터파크 도서 | 서비스 종료 |

수집에 실패한 주에는 지난 데이터를 그대로 보여주고, 카드에 "지난 데이터"로 표시합니다.
