"""주간 베스트셀러 수집기.

분야(자기계발·아동·경제)별 상위 10권을 사이트마다 모아 docs/data.json, docs/data.js 로 저장한다.
- 어떤 사이트가 실패하면 지난번 데이터를 그대로 두고 status 를 'stale' 로 표시한다.
- 아직 수집기를 만들지 않은 사이트는 공식 베스트셀러 페이지 링크만 보여준다.

실행:  py collect.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
KST = timezone(timedelta(hours=9))
TOP_N = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

CATEGORIES = [
    {"id": "self_help", "name": "자기계발"},
    {"id": "kids", "name": "아동"},
    {"id": "economy", "name": "경제"},
]

# status: ready = 수집기 있음 / pending = 준비 중(링크만) / blocked = 자동 수집 불가(링크만)
SOURCES = [
    {
        "id": "yes24", "name": "예스24", "country": "KR", "status": "ready",
        "urls": {
            "self_help": "https://www.yes24.com/Product/Category/BestSeller?categoryNumber=001001026",
            "kids": "https://www.yes24.com/Product/Category/BestSeller?categoryNumber=001001016",
            "economy": "https://www.yes24.com/Product/Category/BestSeller?categoryNumber=001001025",
        },
    },
    {
        "id": "kyobo", "name": "교보문고", "country": "KR", "status": "ready",
        "urls": {
            "self_help": "https://store.kyobobook.co.kr/bestseller/online/weekly/domestic/15",
            "kids": "https://store.kyobobook.co.kr/bestseller/online/weekly/domestic/42",
            "economy": "https://store.kyobobook.co.kr/bestseller/online/weekly/domestic/13",
        },
    },
    {
        "id": "aladin", "name": "알라딘", "country": "KR", "status": "blocked",
        "note": "온라인 신간과 중고서점으로 유명한 서점",
        "urls": {
            "self_help": "https://www.aladin.co.kr/shop/common/wbest.aspx?BestType=Bestseller&BranchType=1&CID=336",
            "kids": "https://www.aladin.co.kr/shop/common/wbest.aspx?BestType=Bestseller&BranchType=1&CID=1108",
            "economy": "https://www.aladin.co.kr/shop/common/wbest.aspx?BestType=Bestseller&BranchType=1&CID=170",
        },
    },
    {
        "id": "ypbooks", "name": "영풍문고", "country": "KR", "status": "ready",
        # 영풍문고는 분야를 바꿔도 주소가 같아서, 페이지의 분야 버튼을 눌러 목록을 바꾼다
        "urls": {k: "https://www.ypbooks.co.kr/bestseller/week" for k in ("self_help", "kids", "economy")},
        "buttons": {"self_help": "자기계발", "kids": "어린이", "economy": "경제경영"},
    },
    {
        "id": "interpark", "name": "인터파크 도서", "country": "KR", "status": "closed",
        "note": "도서 서비스가 종료되었어요",
        "urls": {},
    },
    {
        "id": "nyt", "name": "NYT 베스트셀러", "country": "US", "status": "blocked",
        "note": "미국에서 가장 권위 있는 베스트셀러 목록",
        "urls": {
            "self_help": "https://www.nytimes.com/books/best-sellers/advice-how-to-and-miscellaneous/",
            "kids": "https://www.nytimes.com/books/best-sellers/childrens-middle-grade-hardcover/",
            "economy": "https://www.nytimes.com/books/best-sellers/business-books/",
        },
    },
    {
        "id": "amazon", "name": "Amazon", "country": "US", "status": "blocked",
        "note": "세계 최대 온라인 서점",
        "urls": {
            "self_help": "https://www.amazon.com/gp/bestsellers/books/4736",
            "kids": "https://www.amazon.com/gp/bestsellers/books/4",
            "economy": "https://www.amazon.com/gp/bestsellers/books/3",
        },
    },
    {
        "id": "bn", "name": "Barnes & Noble", "country": "US", "status": "blocked",
        "note": "미국 최대 오프라인 서점 체인",
        "urls": {k: "https://www.barnesandnoble.com/collections/books/bestselling-books" for k in ("self_help", "kids", "economy")},
    },
    {
        "id": "bookshop", "name": "Bookshop.org", "country": "US", "status": "blocked",
        "note": "판매 수익을 독립서점과 나누는 온라인 서점",
        "urls": {k: "https://bookshop.org/" for k in ("self_help", "kids", "economy")},
    },
    {
        "id": "bam", "name": "Books-A-Million", "country": "US", "status": "blocked",
        "note": "미국 남동부 중심의 대형 서점 체인",
        "urls": {k: "https://www.booksamillion.com/" for k in ("self_help", "kids", "economy")},
    },
    {
        "id": "thriftbooks", "name": "ThriftBooks", "country": "US", "status": "blocked",
        "note": "미국 최대 중고서적 온라인 서점",
        "urls": {k: "https://www.thriftbooks.com/" for k in ("self_help", "kids", "economy")},
    },
]


# ---------------------------------------------------------------- 수집기들

def _text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _authors(li, limit: int = 3) -> str:
    names: list[str] = []
    for a in li.select(".info_auth a"):
        n = _text(a)
        if n and "더 보기" not in n and "감추기" not in n and n not in names:
            names.append(n)
    if not names:
        return _text(li.select_one(".info_auth"))
    return ", ".join(names[:limit]) + (f" 외 {len(names) - limit}명" if len(names) > limit else "")


def _shorten_names(s: str, limit: int = 3) -> str:
    names = [n.strip() for n in s.split(",") if n.strip()]
    return ", ".join(names[:limit]) + (f" 외 {len(names) - limit}명" if len(names) > limit else "")


def collect_yes24(url: str, **_) -> list[dict]:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    for li in soup.select("#yesBestList > li[data-goods-no]"):
        goods_no = li["data-goods-no"]
        name = li.select_one("a.gd_name")
        if not name:
            continue
        rank_el = li.select_one("em.ico.rank")
        img = li.select_one("img[data-original]") or li.select_one(".item_img img")
        price = li.select_one(".info_price .yes_b")
        rating = li.select_one(".rating_grade .yes_b")
        items.append({
            "rank": int(_text(rank_el)) if rank_el and _text(rank_el).isdigit() else len(items) + 1,
            "title": _text(name),
            "subtitle": _text(li.select_one(".gd_nameE")),
            "author": _authors(li),
            "publisher": _text(li.select_one(".info_pub")),
            "pub_date": _text(li.select_one(".info_date")),
            "price": f"{_text(price)}원" if price else "",
            "rating": _text(rating),
            "rating_max": 10,
            "image": (img.get("data-original") or img.get("src")) if img else "",
            "link": f"https://www.yes24.com/product/goods/{goods_no}",
        })
        if len(items) >= TOP_N:
            break
    if not items:
        raise RuntimeError("목록을 찾지 못했어요 (페이지 구조가 바뀌었을 수 있음)")
    return items


class Browser:
    """자바스크립트로 목록을 그리는 사이트용. 처음 필요할 때 한 번만 띄우고 끝에 닫는다."""

    def __init__(self):
        self._pw = self._browser = self._page = None

    def page(self):
        if self._page is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch()
            self._page = self._browser.new_page(
                locale="ko-KR", user_agent=HEADERS["User-Agent"], viewport={"width": 1440, "height": 2000})
        return self._page

    def close(self):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()


BROWSER = Browser()


def collect_kyobo(url: str, **_) -> list[dict]:
    pg = BROWSER.page()
    pg.goto(url, wait_until="networkidle", timeout=60000)
    pg.wait_for_selector("span.date", state="attached", timeout=30000)
    soup = BeautifulSoup(pg.content(), "html.parser")
    items, seen = [], set()
    for li in soup.select("li"):
        img = li.select_one("img[src*='/pdt/']")
        date = li.select_one("span.date")
        if not (img and date):
            continue
        title_a = next((a for a in li.select("a.prod_link[href*='/detail/S']")
                        if not a.find("img") and _text(a) and "새창보기" not in _text(a)), None)
        if not title_a or title_a["href"] in seen:
            continue
        seen.add(title_a["href"])
        parts = [p for p in date.parent.get_text("|", strip=True).split("|") if p != "·"]
        flat = li.get_text("|", strip=True)
        price = re.search(r"\|(\d[\d,]*)\|원", flat)
        rating = li.select_one("span.font-bold.text-black")
        items.append({
            "rank": len(items) + 1,
            "title": _text(title_a),
            "subtitle": "",
            "author": parts[0] if len(parts) > 2 else "",
            "publisher": parts[1] if len(parts) > 2 else "",
            "pub_date": parts[-1] if parts else "",
            "price": f"{price.group(1)}원" if price else "",
            "rating": _text(rating),
            "rating_max": 10,
            "image": img.get("src", ""),
            "link": title_a["href"],
        })
        if len(items) >= TOP_N:
            break
    if not items:
        raise RuntimeError("목록을 찾지 못했어요 (페이지 구조가 바뀌었을 수 있음)")
    return items


def collect_ypbooks(url: str, button: str = "", **_) -> list[dict]:
    pg = BROWSER.page()
    if not pg.url.startswith(url):
        pg.goto(url, wait_until="networkidle", timeout=60000)
    pg.wait_for_selector("li.book .book__title-text", timeout=20000)
    if button:
        before = pg.locator("li.book .book__title-text").first.inner_text()
        pg.get_by_role("button", name=button, exact=True).first.click()
        pg.wait_for_load_state("networkidle")
        try:  # 목록이 새로 그려질 때까지 기다림
            pg.wait_for_function(
                "b => { const e = document.querySelector('li.book .book__title-text'); return e && e.innerText !== b; }",
                arg=before, timeout=8000)
        except Exception:
            pass
        pg.wait_for_timeout(500)
    soup = BeautifulSoup(pg.content(), "html.parser")
    items = []
    for li in soup.select("li.book"):
        t = li.select_one(".book__title-text")
        a = li.select_one("a.book__title")
        if not (t and a):
            continue
        title, _, subtitle = _text(t).partition(" - ")
        info = [_text(x) for x in li.select(".list-info__text")]
        rank = re.sub(r"\D", "", _text(li.select_one(".book__rank")))
        price = li.select_one(".book__price")
        img = li.select_one(".book__thumb img")
        rating = _text(li.select_one(".book__votes-point"))
        items.append({
            "rank": int(rank) if rank else len(items) + 1,
            "title": title.strip(),
            "subtitle": subtitle.strip(),
            "author": _shorten_names(_text(li.select_one(".book__writer"))),
            "publisher": info[0] if info else "",
            "pub_date": info[1] if len(info) > 1 else "",
            "price": f"{_text(price)}원" if price else "",
            "rating": rating if rating not in ("", "0", "0.0") else "",
            "rating_max": 5,
            "image": img.get("src", "") if img else "",
            "link": "https://www.ypbooks.co.kr" + a["href"] if a["href"].startswith("/") else a["href"],
        })
        if len(items) >= TOP_N:
            break
    if not items:
        raise RuntimeError("목록을 찾지 못했어요 (페이지 구조가 바뀌었을 수 있음)")
    return items


COLLECTORS = {
    "yes24": collect_yes24,
    "kyobo": collect_kyobo,
    "ypbooks": collect_ypbooks,
}


# ---------------------------------------------------------------- 실행

def with_retry(fn, url: str, attempts: int = 2, **kw) -> list[dict]:
    """일시적인 지연·오류에 대비해 실패하면 잠시 쉬었다가 다시 시도한다."""
    for i in range(attempts):
        try:
            return fn(url, **kw)
        except Exception as e:
            if i == attempts - 1:
                raise
            print(f"  재시도 ({e.__class__.__name__})")
            time.sleep(5)
    return []


def load_previous() -> dict:
    p = DOCS / "data.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def main() -> int:
    now = datetime.now(KST).isoformat(timespec="seconds")
    prev = {s["id"]: s for s in load_previous().get("sources", [])}
    out_sources = []
    failures = 0

    for src in SOURCES:
        entry = {k: src.get(k, "") for k in ("id", "name", "country", "status", "note")}
        entry["lists"] = {}
        collector = COLLECTORS.get(src["id"])

        for cat in CATEGORIES:
            cid = cat["id"]
            url = src["urls"].get(cid, "")
            lst = {"url": url, "items": [], "updated_at": None, "error": None}
            if collector and url:
                try:
                    lst["items"] = with_retry(collector, url, button=src.get("buttons", {}).get(cid, ""))
                    lst["updated_at"] = now
                    print(f"  OK   {src['name']} / {cat['name']}: {len(lst['items'])}권")
                except Exception as e:  # 실패하면 지난 데이터 유지
                    failures += 1
                    old = prev.get(src["id"], {}).get("lists", {}).get(cid, {})
                    lst["items"] = old.get("items", [])
                    lst["updated_at"] = old.get("updated_at")
                    lst["error"] = str(e)[:200]
                    print(f"  FAIL {src['name']} / {cat['name']}: {e}")
                time.sleep(2)  # 사이트에 부담을 주지 않도록 요청 간격 두기
            entry["lists"][cid] = lst

        if collector:
            errs = [l for l in entry["lists"].values() if l["error"]]
            entry["status"] = "ok" if not errs else ("stale" if any(l["items"] for l in errs) else "error")
        out_sources.append(entry)

    BROWSER.close()
    data = {"updated_at": now, "categories": CATEGORIES, "sources": out_sources}
    DOCS.mkdir(exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    (DOCS / "data.json").write_text(text, encoding="utf-8")
    # data.js: 파일을 더블클릭해서 열어도(file://) 화면이 보이도록 스크립트 형태로도 저장
    (DOCS / "data.js").write_text(f"window.BESTSELLER_DATA = {text};\n", encoding="utf-8")
    print(f"저장 완료: {DOCS / 'data.json'} (실패 {failures}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
