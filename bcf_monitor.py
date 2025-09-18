import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://boylstonchess.org"
EVENTS_URL = "https://boylstonchess.org/events"
USER_AGENT = "bcf-monitor/0.1 (+https://boylstonchess.org/events)"
HTTP_TIMEOUT_SECONDS = 20


def http_get(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def parse_date(text: str):
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    patterns = [
        "%A, %B %d, %Y",
        "%B %d, %Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ]
    for fmt in patterns:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", cleaned)
    if m:
        y, mo, d = map(int, m.groups())
        return datetime(y, mo, d).date()
    return None


def nearest_heading_text(elem) -> str | None:
    heading = elem.find_previous(["h1", "h2", "h3", "h4", "h5"])
    if heading:
        return " ".join(heading.get_text(" ").split())
    strong = elem.find_previous(["strong"])
    if strong:
        return " ".join(strong.get_text(" ").split())
    return None


def find_event_date(elem):
    block = elem.find_parent(["table", "div", "section", "article"]) or elem.parent
    if not block:
        return None
    for tr in block.find_all("tr"):
        cells = [td.get_text(" ").strip() for td in tr.find_all(["td", "th"])]
        if not cells:
            continue
        if re.search(r"^date$", cells[0], re.I) and len(cells) > 1:
            parsed = parse_date(cells[1])
            if parsed:
                return parsed
    labels = block.find_all(string=re.compile(r"^\s*Date\s*$", re.I))
    for lab in labels:
        sib = lab.parent.find_next(string=True)
        if sib:
            parsed = parse_date(sib)
            if parsed:
                return parsed
    txt = " ".join(block.get_text(" ").split())
    m = re.search(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}", txt)
    if m:
        parsed = parse_date(m.group(0))
        if parsed:
            return parsed
    return None


def parse_events_page(html: str):
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for a in soup.find_all("a", href=True):
        if re.match(r"^/tournament/entries/\d+$", a["href"]):
            entry_url = urljoin(BASE_URL, a["href"])
            name = nearest_heading_text(a) or "Unknown Event"
            date_value = find_event_date(a)
            event_id = re.search(r"/entries/(\d+)", a["href"]).group(1)
            events.append(
                {
                    "event_id": event_id,
                    "name": name,
                    "date": date_value.isoformat() if date_value else None,
                    "entry_list_url": entry_url,
                }
            )
    unique_by_id = {}
    for ev in events:
        unique_by_id.setdefault(ev["event_id"], ev)
    return list(unique_by_id.values())


def parse_entry_list(html: str):
    soup = BeautifulSoup(html, "html.parser")
    participants = set()

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ").strip() for c in tr.find_all(["td", "th"])]
            if not cells or len(cells) < 1:
                continue
            if cells[0].lower() in ["name", "player", "entrant", "entry"]:
                continue
            candidate = cells[0]
            if candidate and len(candidate) > 1:
                participants.add(candidate)

    if not participants:
        for li in soup.find_all("li"):
            text = " ".join(li.get_text(" ").split())
            if 1 < len(text) < 80 and not re.search(r":\s*$", text):
                participants.add(text)

    def normalize(name: str) -> str:
        return re.sub(r"\s+", " ", (name or "").strip())

    return sorted({normalize(p) for p in participants})


def load_snapshot(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def diff_lists(old_list, new_list):
    old = set(old_list or [])
    new = set(new_list or [])
    added = sorted(new - old)
    removed = sorted(old - new)
    return added, removed


def within_days(event_date_iso: str | None, days_before: int) -> bool:
    if not event_date_iso:
        return False
    try:
        event_date = datetime.fromisoformat(event_date_iso).date()
    except Exception:
        return False
    today = datetime.now(timezone.utc).astimezone().date()
    if event_date < today:
        return False
    return (event_date - today).days <= days_before


def expired(event_date_iso: str | None) -> bool:
    if not event_date_iso:
        return False
    try:
        event_date = datetime.fromisoformat(event_date_iso).date()
    except Exception:
        return False
    today = datetime.now(timezone.utc).astimezone().date()
    return event_date < today


def cleanup_expired(data_dir: str):
    if not os.path.isdir(data_dir):
        return
    for fn in os.listdir(data_dir):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(data_dir, fn)
        try:
            snap = load_snapshot(path)
            if not snap:
                continue
            if expired(snap.get("event_date")):
                os.remove(path)
                print(f"[INFO] removed expired snapshot {fn}")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="./data")
    parser.add_argument("--days-before", type=int, default=7)
    parser.add_argument("--include", default="", help="comma-separated keywords in title")
    parser.add_argument("--exclude", default="", help="comma-separated keywords in title")
    args = parser.parse_args()

    include = [s.strip().lower() for s in args.include.split(",") if s.strip()]
    exclude = [s.strip().lower() for s in args.exclude.split(",") if s.strip()]

    def match_rules(name: str) -> bool:
        lower = (name or "").lower()
        if include and not any(k in lower for k in include):
            return False
        if exclude and any(k in lower for k in exclude):
            return False
        return True

    try:
        events_html = http_get(EVENTS_URL)
    except Exception as e:
        print(f"[ERR] fetch events page failed: {e}", file=sys.stderr)
        sys.exit(2)

    events = [e for e in parse_events_page(events_html) if match_rules(e["name"]) and within_days(e["date"], args.days_before)]

    if not events:
        print("[INFO] No events within window matching rules.")
        cleanup_expired(args.data_dir)
        return

    reports = []
    for e in events:
        try:
            entry_html = http_get(e["entry_list_url"])
            participants = parse_entry_list(entry_html)
        except Exception as ex:
            print(f"[WARN] fetch/parse entry list failed for {e['event_id']}: {ex}", file=sys.stderr)
            continue

        snap_path = os.path.join(args.data_dir, f"{e['event_id']}.json")
        previous = load_snapshot(snap_path) or {}
        prev_participants = previous.get("participants", [])
        added, removed = diff_lists(prev_participants, participants)

        snapshot = {
            "event_id": e["event_id"],
            "event_name": e["name"],
            "event_date": e["date"],
            "entry_list_url": e["entry_list_url"],
            "last_checked": datetime.now().isoformat(timespec="seconds"),
            "participants": participants,
            "count": len(participants),
        }
        save_snapshot(snap_path, snapshot)

        reports.append(
            {
                "name": e["name"],
                "date": e["date"],
                "url": e["entry_list_url"],
                "count": len(participants),
                "added": added,
                "removed": removed,
            }
        )

    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"BCF event updates ({today_str})")
    for r in reports:
        delta = f"(+{len(r['added'])} -{len(r['removed'])})" if (r["added"] or r["removed"]) else "(no changes)"
        print(f"- {r['name']} – {r['date']}  {delta}")
        if r["added"]:
            print(f"  New: {', '.join(r['added'])}")
        if r["removed"]:
            print(f"  Withdrawn: {', '.join(r['removed'])}")
        print(f"  Entry List: {r['url']}")

    cleanup_expired(args.data_dir)


if __name__ == "__main__":
    main()


