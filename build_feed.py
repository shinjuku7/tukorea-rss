#!/usr/bin/env python3
import os, re, sys
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

BASE_URL = "https://www.tukorea.ac.kr/tukorea/7607/subview.do"
OUTPUT_PATH = "docs/feed.xml"
SELF_FEED_URL = "https://shinjuku7.github.io/shinjuku7/feed.xml"  
MAX_ITEMS = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TU-Korea-RSS/1.0; +https://github.com/)"
}

def parse_kr_date(text):
    if not text:
        return None
    s = re.sub(r"\s+", "", text)
    m = re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", s)
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    try:
        tz = ZoneInfo("Asia/Seoul") if ZoneInfo else None
        return datetime(y, mo, d, 9, 0, 0, tzinfo=tz)
    except Exception:
        return None

def extract_items(soup):
    items = []

    # 1) 표 형태 추정: table > tbody > tr
    rows = soup.select("table tbody tr")
    if rows:
        for tr in rows:
            a = tr.select_one("a[href]")
            if not a:
                continue
            title = a.get_text(strip=True)
            link = urljoin(BASE_URL, a.get("href", ""))

            # tr 안에서 날짜 비슷한 텍스트 찾기
            pub_dt = None
            tds = tr.find_all("td")
            for td in reversed(tds):
                txt = td.get_text(strip=True)
                if re.search(r"\d{4}[./-]\d{1,2}[./-]\d{1,2}", txt):
                    pub_dt = parse_kr_date(txt)
                    break

            items.append({"title": title, "link": link, "pub_dt": pub_dt})

    # 2) 리스트 형태 추정: ul/li
    if not items:
        lis = soup.select("ul li, .post-list li, .board-list li")
        for li in lis:
            a = li.select_one("a[href]")
            if not a:
                continue
            title = a.get_text(strip=True)
            link = urljoin(BASE_URL, a.get("href", ""))

            date_text = ""
            date_el = li.find(attrs={"class": re.compile(r"(date|time)", re.I)})
            if date_el:
                date_text = date_el.get_text(strip=True)
            pub_dt = parse_kr_date(date_text)
            items.append({"title": title, "link": link, "pub_dt": pub_dt})

    # 정렬(날짜가 있으면 최신순)
    items_with_date = [x for x in items if x["pub_dt"]]
    items_no_date = [x for x in items if not x["pub_dt"]]
    items_with_date.sort(key=lambda x: x["pub_dt"], reverse=True)
    combined = items_with_date + items_no_date
    return combined[:MAX_ITEMS]

def build_feed(items):
    fg = FeedGenerator()
    fg.id(SELF_FEED_URL)
    fg.title("한국공학대 공지사항")
    fg.link(href=BASE_URL, rel="alternate")
    fg.link(href=SELF_FEED_URL, rel="self")
    fg.description("한국공학대 공지사항 비공식 RSS")
    fg.language("ko-kr")

    for it in items:
        fe = fg.add_entry()
        fe.id(it["link"])
        fe.title(it["title"])
        fe.link(href=it["link"])
        if it["pub_dt"]:
            fe.pubDate(it["pub_dt"])

    return fg.rss_str(pretty=True)

def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    resp = requests.get(BASE_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    # 인코딩 보정
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"

    soup = BeautifulSoup(resp.text, "lxml")
    items = extract_items(soup)
    if not items:
        print("경고: 공지 항목을 찾지 못했습니다. 선택자 점검 필요.", file=sys.stderr)

    rss_bytes = build_feed(items)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(rss_bytes)

    print(f"생성 완료: {OUTPUT_PATH} ({len(items)}건)")

if __name__ == "__main__":
    main()
