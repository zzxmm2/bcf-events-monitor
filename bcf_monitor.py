import argparse
import json
import os
import re
import sys
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urljoin

import requests
import certifi
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any


BASE_URL = "https://boylstonchess.org"
EVENTS_URL = "https://boylstonchess.org/events"
USER_AGENT = "bcf-monitor/0.1 (+https://boylstonchess.org/events)"
HTTP_TIMEOUT_SECONDS = 20

# Email configuration - can be overridden by environment variables
EMAIL_SMTP_SERVER = os.getenv("BCF_EMAIL_SMTP_SERVER", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("BCF_EMAIL_SMTP_PORT", "587"))
EMAIL_USERNAME = os.getenv("BCF_EMAIL_USERNAME", "")
EMAIL_PASSWORD = os.getenv("BCF_EMAIL_PASSWORD", "")
EMAIL_FROM = os.getenv("BCF_EMAIL_FROM", "")
EMAIL_TO = os.getenv("BCF_EMAIL_TO", "")

# Configuration file path
DEFAULT_CONFIG_FILE = "bcf_monitor_config.json"


def http_get(url: str, insecure: bool = False) -> str:
    verify_val = False if insecure else certifi.where()
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT_SECONDS,
        verify=verify_val,
    )
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


def parse_multiple_dates(text: str):
    """Parse text that may contain multiple dates or date ranges."""
    if not text:
        return []
    
    # Clean up the text
    cleaned = re.sub(r"\s+", " ", text.strip())
    dates = []
    
    # Extract month and year information first
    # Look for month followed by year, but allow other text in between
    month_year_match = re.search(r"([A-Za-z]+).*?(\d{4})", cleaned)
    if not month_year_match:
        # Fallback to single date parsing
        single_date = parse_date(cleaned)
        if single_date:
            return [single_date]
        return []
    
    month_name = month_year_match.group(1)
    year = int(month_year_match.group(2))
    
    try:
        month_num = datetime.strptime(month_name, "%B").month
    except ValueError:
        # Fallback to single date parsing
        single_date = parse_date(cleaned)
        if single_date:
            return [single_date]
        return []
    
    # Check if it's a range pattern (contains '-')
    if '-' in cleaned:
        # Split by '-' and parse start and end dates
        parts = cleaned.split('-')
        if len(parts) == 2:
            start_text = parts[0].strip()
            end_text = parts[1].strip()
            
            # Remove day of week from start and end
            start_clean = re.sub(r"^[A-Za-z]+,\s*", "", start_text)
            end_clean = re.sub(r"^[A-Za-z]+,\s*", "", end_text)
            
            # Add year to both dates if not present
            if str(year) not in start_clean:
                start_clean = f"{start_clean}, {year}"
            if str(year) not in end_clean:
                end_clean = f"{end_clean}, {year}"
            
            start_date = parse_date(start_clean)
            end_date = parse_date(end_clean)
            
            if start_date and end_date:
                current = start_date
                while current <= end_date:
                    dates.append(current)
                    current += timedelta(days=1)
                return dates
    
    # Handle individual days (contains 'and' keyword)
    elif 'and' in cleaned:
        # Extract all day numbers from the text
        day_numbers = []
        
        # Split by comma and 'and' to get individual day numbers
        parts = re.split(r',\s*and\s*|,\s*', cleaned)
        for part in parts:
            # Extract day numbers from each part
            numbers = re.findall(r'\b(\d{1,2})\b', part)
            for num_str in numbers:
                day = int(num_str)
                if 1 <= day <= 31 and day != year:  # Exclude year
                    day_numbers.append(day)
        
        # Create dates from day numbers
        for day in day_numbers:
            dates.append(datetime(year, month_num, day).date())
        
        if dates:
            return sorted(dates)
    
    # Handle comma-separated days without 'and' keyword
    elif ',' in cleaned:
        # Extract all day numbers from the text
        day_numbers = []
        
        # Split by comma to get individual day numbers
        parts = cleaned.split(',')
        for part in parts:
            # Extract day numbers from each part
            numbers = re.findall(r'\b(\d{1,2})\b', part)
            for num_str in numbers:
                day = int(num_str)
                if 1 <= day <= 31 and day != year:  # Exclude year
                    day_numbers.append(day)
        
        # Create dates from day numbers
        for day in day_numbers:
            dates.append(datetime(year, month_num, day).date())
        
        if dates:
            return sorted(dates)
    
    # Fallback to single date parsing
    single_date = parse_date(cleaned)
    if single_date:
        return [single_date]
    
    return []


def nearest_heading_text(elem) -> Optional[str]:
    # First, try to find a more specific heading that's not generic
    for heading in elem.find_all_previous(["h1", "h2", "h3", "h4", "h5"]):
        heading_text = " ".join(heading.get_text(" ").split())
        # Skip generic headings
        if heading_text.lower() not in ["upcoming events", "events", "tournaments", "chess events"]:
            return heading_text
    
    # If no specific heading found, try to find the event name in the link text or nearby text
    # Look for text that might be the event name in the same container
    parent = elem.find_parent(["div", "section", "article", "td", "li"])
    if parent:
        # Look for text that's not generic and seems like an event name
        for text_elem in parent.find_all(["span", "div", "p", "strong", "b"]):
            text = " ".join(text_elem.get_text(" ").split())
            if (text and len(text) > 5 and 
                text.lower() not in ["register online now", "upcoming events", "events", "tournaments", "chess events", "date", "time", "location"] and
                not text.startswith("http") and
                not re.match(r"^\d+$", text)):
                return text
    
    # Fallback to original logic
    heading = elem.find_previous(["h1", "h2", "h3", "h4", "h5"])
    if heading:
        return " ".join(heading.get_text(" ").split())
    strong = elem.find_previous(["strong"])
    if strong:
        return " ".join(strong.get_text(" ").split())
    return None


def find_event_dates(elem):
    """Find event dates, handling both single dates and multiple dates/ranges."""
    block = elem.find_parent(["table", "div", "section", "article"]) or elem.parent
    if not block:
        return []
    
    # Look in table rows first
    for tr in block.find_all("tr"):
        cells = [td.get_text(" ").strip() for td in tr.find_all(["td", "th"])]
        if not cells:
            continue
        if re.search(r"^date$", cells[0], re.I) and len(cells) > 1:
            dates = parse_multiple_dates(cells[1])
            if dates:
                return dates
    
    # Look for date labels
    labels = block.find_all(string=re.compile(r"^\s*Date\s*$", re.I))
    for lab in labels:
        sib = lab.parent.find_next(string=True)
        if sib:
            dates = parse_multiple_dates(sib)
            if dates:
                return dates
    
    # Look for date patterns in the text
    txt = " ".join(block.get_text(" ").split())
    dates = parse_multiple_dates(txt)
    if dates:
        return dates
    
    return []


def parse_events_page(html: str):
    soup = BeautifulSoup(html, "html.parser")
    events = []

    container = soup.find("div", id="events") or soup.find(id="events")

    def extract_event_from_block(block):
        detail_link = None
        event_name = None
        entry_link_tag = None
        event_id = None

        title_block = block.find("div", class_="title")
        if title_block:
            # Prefer an event detail link inside the title
            for tlink in title_block.find_all("a", href=True):
                if re.search(r"^/events/\d+", tlink.get("href", "")):
                    detail_link = tlink
                    event_name = " ".join(tlink.get_text(" ").split())
                    break
            # Fallback to first link text for name
            if not event_name:
                any_link = title_block.find("a", href=True)
                if any_link:
                    event_name = " ".join(any_link.get_text(" ").split())

        # Scan all links in the block to find event id and entry list link
        for a in block.find_all("a", href=True):
            href = a.get("href", "")
            if not event_id:
                m = (re.search(r"/events/(\d+)", href)
                     or re.search(r"/tournament/register/(\d+)", href)
                     or re.search(r"/tournament/entries/(\d+)", href))
                if m:
                    event_id = m.group(1)
            if not entry_link_tag and re.match(r"^/tournament/entries/\d+$", href):
                entry_link_tag = a

        if not event_name:
            event_name = nearest_heading_text(block) or "Unknown Event"

        # Choose an anchor near the date (detail link or any link), fallback to the block itself
        anchor_for_date = detail_link or entry_link_tag or block
        date_values = find_event_dates(anchor_for_date)

        event_detail_url = urljoin(BASE_URL, detail_link["href"]) if detail_link else None
        if entry_link_tag:
            entry_list_url = urljoin(BASE_URL, entry_link_tag["href"])
        elif event_id:
            entry_list_url = urljoin(BASE_URL, f"/tournament/entries/{event_id}")
        else:
            entry_list_url = None

        if event_id or entry_list_url:
            events.append(
                {
                    "event_id": event_id or (re.search(r"/entries/(\d+)", entry_link_tag["href"]).group(1) if entry_link_tag else ""),
                    "name": event_name,
                    "dates": [d.isoformat() for d in date_values] if date_values else [],
                    "event_detail_url": event_detail_url,
                    "entry_list_url": entry_list_url,
                }
            )

    if container:
        # Treat each direct child of the container as an event block
        for child in container.find_all(recursive=False):
            if getattr(child, "name", None):
                extract_event_from_block(child)

    unique_by_id = {}
    for ev in events:
        unique_by_id.setdefault(ev["event_id"], ev)
    return list(unique_by_id.values())


def parse_event_details(html: str):
    """Parse detailed event information from event detail page."""
    soup = BeautifulSoup(html, "html.parser")
    details = {}
    
    # Try to extract event name from the page title or main heading
    event_name = None
    
    # Look for page title
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text(" ").strip()
        # Clean up title to get event name
        if title_text and "boylston" not in title_text.lower():
            event_name = title_text
    
    # Look for main heading (h1)
    h1_tag = soup.find("h1")
    if h1_tag:
        h1_text = h1_tag.get_text(" ").strip()
        if h1_text and h1_text.lower() not in ["upcoming events", "events", "tournaments"]:
            event_name = h1_text
    
    # Look for event name in tables
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ").strip() for c in tr.find_all(["td", "th"])]
            if len(cells) >= 2:
                key = cells[0].lower().strip()
                value = cells[1].strip()
                if key and value:
                    details[key] = value
                    # If we find a name field, use it
                    if key in ["name", "event name", "tournament name", "title"]:
                        event_name = value
    
    # Also look for details in definition lists or other structures
    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            key = dt.get_text(" ").strip().lower()
            value = dd.get_text(" ").strip()
            if key and value:
                details[key] = value
                # If we find a name field, use it
                if key in ["name", "event name", "tournament name", "title"]:
                    event_name = value
    
    # Store the event name if found
    if event_name:
        details["event_name"] = event_name
    
    return details


def parse_entry_list(html: str):
    """Parse entry list from tournament entries page."""
    soup = BeautifulSoup(html, "html.parser")
    participants = []
    
    # Extract event name from page title
    event_name = None
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text(" ").strip()
        # Extract event name from title like "Registration List • Unrated Friday Night Blitz • Boylston Chess Foundation"
        if "•" in title_text:
            parts = [part.strip() for part in title_text.split("•")]
            if len(parts) >= 2:
                event_name = parts[1]  # Second part should be the event name
        elif "Registration List" in title_text:
            # Fallback: try to extract from "Registration List &bull; Event Name &bull; Boylston Chess Foundation"
            match = re.search(r"Registration List[^•]*•\s*([^•]+)\s*•", title_text)
            if match:
                event_name = match.group(1).strip()

    # First, try to find the specific "members" table (BCF format)
    members_table = soup.find("table", id="members")
    if members_table:
        rows = members_table.find_all("tr")
        if len(rows) > 1:  # Has header and data rows
            for tr in rows[1:]:  # Skip header row
                cells = [c.get_text(" ").strip() for c in tr.find_all(["td", "th"])]
                if len(cells) >= 6:  # Should have #, Name, Rating, USCF ID, Section, Byes
                    # Skip the first cell (row number)
                    name = cells[1] if len(cells) > 1 else ""
                    rating = cells[2] if len(cells) > 2 else ""
                    uscf_id = cells[3] if len(cells) > 3 else ""
                    section = cells[4] if len(cells) > 4 else ""
                    byes = cells[5] if len(cells) > 5 else ""
                    
                    if name and name.strip():
                        participant_info = {
                            "name": name.strip(),
                            "rating": rating.strip() if rating else None,
                            "uscf_id": uscf_id.strip() if uscf_id else None,
                            "section": section.strip() if section else None,
                            "byes": byes.strip() if byes else None,
                        }
                        participants.append(participant_info)

    # If no participants found in members table, try other approaches
    if not participants:
        # Look for any table with entry list structure
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if not rows:
                continue
                
            # Check if this looks like an entry list table
            header_row = rows[0]
            header_cells = [c.get_text(" ").strip().lower() for c in header_row.find_all(["td", "th"])]
            
            # More specific check for entry list headers
            if any(keyword in " ".join(header_cells) for keyword in ["name", "player", "entrant", "entry", "participant"]):
                # This is likely the entry list table
                for tr in rows[1:]:  # Skip header row
                    cells = [c.get_text(" ").strip() for c in tr.find_all(["td", "th"])]
                    if len(cells) >= 2:
                        name = cells[1] if len(cells) > 1 else cells[0]  # Try second cell first, then first
                        # More strict filtering to avoid navigation items
                        if (name and len(name) > 1 and 
                            name.lower() not in ["name", "player", "entrant", "entry", "#", "no", "yes"] and
                            not re.search(r"^\d+$", name) and  # Not just a number
                            len(name.split()) <= 4 and  # Reasonable name length
                            not any(nav_word in name.lower() for nav_word in ["home", "about", "contact", "login", "register", "search", "menu", "navigation"])):
                            
                            # Extract additional info if available
                            participant_info = {
                                "name": name,
                                "rating": cells[2] if len(cells) > 2 else None,
                                "uscf_id": cells[3] if len(cells) > 3 else None,
                                "section": cells[4] if len(cells) > 4 else None,
                                "byes": cells[5] if len(cells) > 5 else None,
                            }
                            participants.append(participant_info)

    def normalize_name(name: str) -> str:
        return re.sub(r"\s+", " ", (name or "").strip())

    # Normalize names and return
    for p in participants:
        p["name"] = normalize_name(p["name"])
    
    # Remove duplicates
    seen = set()
    unique_participants = []
    for p in participants:
        if p["name"] not in seen:
            seen.add(p["name"])
            unique_participants.append(p)
    
    return unique_participants, event_name


def load_snapshot(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(path: str, data: dict):
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def diff_lists(old_list, new_list):
    """Compare old and new participant lists and return added/removed participants."""
    # Convert to sets of names for comparison
    old_names = set()
    new_names = set()
    
    if old_list:
        for p in old_list:
            if isinstance(p, dict):
                old_names.add(p["name"])
            else:
                old_names.add(p)
    
    if new_list:
        for p in new_list:
            if isinstance(p, dict):
                new_names.add(p["name"])
            else:
                new_names.add(p)
    
    added_names = sorted(new_names - old_names)
    removed_names = sorted(old_names - new_names)
    
    # Convert back to full participant info
    added = []
    removed = []
    
    if new_list:
        for p in new_list:
            name = p["name"] if isinstance(p, dict) else p
            if name in added_names:
                added.append(p)
    
    if old_list:
        for p in old_list:
            name = p["name"] if isinstance(p, dict) else p
            if name in removed_names:
                removed.append(p)
    
    return added, removed


def within_days(event_dates: list, days_before: int) -> bool:
    """Check if any of the event dates are within the monitoring window."""
    if not event_dates:
        return False
    
    today = datetime.now(timezone.utc).astimezone().date()
    
    for date_str in event_dates:
        try:
            # Parse ISO date string (YYYY-MM-DD format)
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if event_date >= today and (event_date - today).days <= days_before:
                return True
        except Exception:
            continue
    return False


def expired(event_dates: list) -> bool:
    """Check if all event dates have passed."""
    if not event_dates:
        return True
    
    today = datetime.now(timezone.utc).astimezone().date()
    
    for date_str in event_dates:
        try:
            # Parse ISO date string (YYYY-MM-DD format)
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if event_date >= today:
                return False  # At least one date is in the future
        except Exception:
            continue
    return True  # All dates are in the past or invalid


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
            if expired(snap.get("event_dates", [])):
                os.remove(path)
                print(f"[INFO] removed expired snapshot {fn}")
        except Exception:
            pass


def send_email_notification(reports: list, email_config: dict):
    """Send email notification with event updates."""
    if not email_config.get("enabled") or not email_config.get("to"):
        return False
    
    try:
        # Create message with plain text and HTML alternatives
        msg = MIMEMultipart('alternative')
        msg['From'] = email_config.get("from", EMAIL_FROM)
        msg['To'] = email_config.get("to")
        msg['Subject'] = f"BCF Events Update - {datetime.now().strftime('%Y-%m-%d')}"
        
        # Create plain text body
        text_body = f"BCF Events Monitor Update\n"
        text_body += f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        text_body += "=" * 50 + "\n\n"

        # Create HTML body
        html_body = []
        html_body.append("<html><body>")
        html_body.append(f"<p><strong>BCF Events Monitor Update</strong><br/>Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")
        html_body.append("<hr/>")
        
        if not reports:
            text_body += "No events found within the monitoring window.\n"
            html_body.append("<p>No events found within the monitoring window.</p>")
        else:
            for r in reports:
                # Title line with link in HTML; plain text shows URL inline
                if r.get("detail_url"):
                    text_body += f"📅 {r['name']} - {r['detail_url']}\n"
                    html_body.append(f"<p>📅 <a href=\"{r['detail_url']}\">{r['name']}</a></p>")
                else:
                    text_body += f"📅 {r['name']}\n"
                    html_body.append(f"<p>📅 {r['name']}</p>")

                # Format dates - single date or list
                dates = r.get("dates", [])
                if len(dates) == 1:
                    date_display = dates[0]
                elif len(dates) > 1:
                    date_display = f"[{', '.join(dates)}]"
                else:
                    date_display = "TBD"
                
                text_body += f"   Date: {date_display}\n"
                text_body += f"   Participants: {r['count']}\n"
                html_body.append(f"<div>Date: {date_display}</div>")
                html_body.append(f"<div>Participants: {r['count']}</div>")
                
                # Show key event details if available (but no explicit Event Details URL line)
                # Note: Entry Fee, Time Control, and Sections fields removed per user request
                
                # Show changes
                if r["added"]:
                    text_body += f"   ✅ New participants:\n"
                    html_body.append("<div>✅ New participants:</div><ul>")
                    for p in r["added"]:
                        if isinstance(p, dict):
                            rating_info = f" ({p['rating']})" if p.get("rating") else ""
                            section_info = f" [{p['section']}]" if p.get("section") else ""
                            text_body += f"      • {p['name']}{rating_info}{section_info}\n"
                            html_body.append(f"<li>{p['name']}{rating_info}{section_info}</li>")
                        else:
                            text_body += f"      • {p}\n"
                            html_body.append(f"<li>{p}</li>")
                    html_body.append("</ul>")
                
                if r["removed"]:
                    text_body += f"   ❌ Withdrawn participants:\n"
                    html_body.append("<div>❌ Withdrawn participants:</div><ul>")
                    for p in r["removed"]:
                        if isinstance(p, dict):
                            rating_info = f" ({p['rating']})" if p.get("rating") else ""
                            section_info = f" [{p['section']}]" if p.get("section") else ""
                            text_body += f"      • {p['name']}{rating_info}{section_info}\n"
                            html_body.append(f"<li>{p['name']}{rating_info}{section_info}</li>")
                        else:
                            text_body += f"      • {p}\n"
                            html_body.append(f"<li>{p}</li>")
                    html_body.append("</ul>")

                # Only show Entry List if there are participants
                if r['count'] > 0:
                    text_body += f"   📝 Entry List: {r['entry_url']}\n\n"
                    html_body.append(f"<div>📝 Entry List: <a href=\"{r['entry_url']}\">{r['entry_url']}</a></div>")
                else:
                    text_body += "\n"

        html_body.append("<hr/>")
        html_body.append("<div>This is an automated message from BCF Events Monitor.</div>")
        html_body.append("</body></html>")
        
        text_body += "\n" + "=" * 50 + "\n"
        text_body += "This is an automated message from BCF Events Monitor.\n"
        
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText("\n".join(html_body), 'html'))
        
        # Send email
        server = smtplib.SMTP(email_config.get("smtp_server", EMAIL_SMTP_SERVER), 
                              email_config.get("smtp_port", EMAIL_SMTP_PORT))
        server.starttls()
        server.login(email_config.get("username", EMAIL_USERNAME), 
                     email_config.get("password", EMAIL_PASSWORD))
        text = msg.as_string()
        server.sendmail(msg['From'], msg['To'], text)
        server.quit()
        
        print(f"[INFO] Email notification sent to {email_config.get('to')}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to send email notification: {e}", file=sys.stderr)
        return False


def has_significant_changes(reports: list) -> bool:
    """Check if there are any significant changes worth notifying about."""
    for r in reports:
        if r["added"] or r["removed"]:
            return True
    return False


def load_config(config_file: str = DEFAULT_CONFIG_FILE) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    default_config = {
        "data_dir": "./data",
        "days_before": 7,
        "include": "",
        "exclude": "",
        "debug": False,
        "email": {
            "enabled": False,
            "to": "",
            "from": "",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "",
            "password": "",
            "only_changes": True
        }
    }
    
    if not os.path.exists(config_file):
        return default_config
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Merge with defaults to ensure all keys exist
        merged_config = default_config.copy()
        merged_config.update(config)
        
        # Ensure email config is properly merged
        if "email" in config:
            merged_config["email"].update(config["email"])
        
        return merged_config
    except Exception as e:
        print(f"[WARN] Failed to load config file {config_file}: {e}", file=sys.stderr)
        return default_config


def save_config(config: Dict[str, Any], config_file: str = DEFAULT_CONFIG_FILE) -> bool:
    """Save configuration to JSON file."""
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save config file {config_file}: {e}", file=sys.stderr)
        return False


def create_default_config(config_file: str = DEFAULT_CONFIG_FILE) -> bool:
    """Create a default configuration file with comments."""
    default_config = {
        "_comment": "BCF Events Monitor Configuration File",
        "_instructions": [
            "Modify the values below to set your default preferences.",
            "You can still override these settings using command line arguments.",
            "Remove the _comment and _instructions fields when you're done configuring."
        ],
        "data_dir": "./data",
        "days_before": 7,
        "include": "",
        "exclude": "",
        "debug": False,
        "email": {
            "enabled": False,
            "to": "your-email@example.com",
            "from": "your-gmail@gmail.com",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "your-gmail@gmail.com",
            "password": "your-app-password-here",
            "only_changes": True
        }
    }
    
    return save_config(default_config, config_file)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE, help="configuration file path")
    parser.add_argument("--create-config", action="store_true", help="create a default configuration file")
    parser.add_argument("--data-dir", help="directory to store snapshots")
    parser.add_argument("--days-before", type=int, help="number of days before event to start monitoring")
    parser.add_argument("--include", help="comma-separated keywords in title")
    parser.add_argument("--exclude", help="comma-separated keywords in title")
    parser.add_argument("--debug", action="store_true", help="enable debug output")
    
    # Email notification options
    parser.add_argument("--email", action="store_true", help="enable email notifications")
    parser.add_argument("--email-to", help="email address to send notifications to")
    parser.add_argument("--email-from", help="email address to send notifications from")
    parser.add_argument("--email-smtp-server", help="SMTP server for email")
    parser.add_argument("--email-smtp-port", type=int, help="SMTP port for email")
    parser.add_argument("--email-username", help="SMTP username")
    parser.add_argument("--email-password", help="SMTP password")
    parser.add_argument("--email-only-changes", action="store_true", help="only send email when there are changes")
    
    args = parser.parse_args()
    
    # Handle config file creation
    if args.create_config:
        if create_default_config(args.config):
            print(f"Default configuration file created: {args.config}")
            print("Please edit the file with your settings and remove the _comment and _instructions fields.")
        else:
            print(f"Failed to create configuration file: {args.config}")
        return
    
    # Load configuration from file
    config = load_config(args.config)
    
    # Override config with command line arguments
    data_dir = args.data_dir or config.get("data_dir", "./data")
    days_before = args.days_before or config.get("days_before", 7)
    include_str = args.include or config.get("include", "")
    exclude_str = args.exclude or config.get("exclude", "")
    debug = args.debug or config.get("debug", False)
    
    include = [s.strip().lower() for s in include_str.split(",") if s.strip()]
    exclude = [s.strip().lower() for s in exclude_str.split(",") if s.strip()]

    def match_rules(name: str) -> bool:
        lower = (name or "").lower()
        if include and not any(k in lower for k in include):
            return False
        if exclude and any(k in lower for k in exclude):
            return False
        return True

    # Setup email configuration (command line args override config file)
    email_config_from_file = config.get("email", {})
    email_config = {
        "enabled": args.email or email_config_from_file.get("enabled", False),
        "to": args.email_to or email_config_from_file.get("to", "") or EMAIL_TO,
        "from": args.email_from or email_config_from_file.get("from", "") or EMAIL_FROM,
        "smtp_server": args.email_smtp_server or email_config_from_file.get("smtp_server", "smtp.gmail.com"),
        "smtp_port": args.email_smtp_port or email_config_from_file.get("smtp_port", 587),
        "username": args.email_username or email_config_from_file.get("username", "") or EMAIL_USERNAME,
        "password": args.email_password or email_config_from_file.get("password", "") or EMAIL_PASSWORD,
        "only_changes": args.email_only_changes or email_config_from_file.get("only_changes", True),
    }
    
    # Validate email configuration if enabled
    if email_config["enabled"]:
        if not email_config["to"]:
            print("[ERROR] Email notifications enabled but no recipient email specified. Use --email-to or set BCF_EMAIL_TO environment variable.", file=sys.stderr)
            sys.exit(1)
        if not email_config["username"] or not email_config["password"]:
            print("[ERROR] Email notifications enabled but SMTP credentials not specified. Use --email-username/--email-password or set BCF_EMAIL_USERNAME/BCF_EMAIL_PASSWORD environment variables.", file=sys.stderr)
            sys.exit(1)

    try:
        events_html = http_get(EVENTS_URL, insecure=True)
    except Exception as e:
        print(f"[ERR] fetch events page failed: {e}", file=sys.stderr)
        sys.exit(2)

    # Parse events from listing page without filtering by date yet.
    # We'll enrich event names and dates from details/entry pages first.
    events = parse_events_page(events_html)
    if not events:
        print("[INFO] No events discovered on events listing page.")
        cleanup_expired(data_dir)
        return

    reports = []
    for e in events:
        event_details = {}
        
        # Fetch event details if URL is available
        if e.get("event_detail_url"):
            try:
                detail_html = http_get(e["event_detail_url"], insecure=True)
                event_details = parse_event_details(detail_html)
                # Use event name from details if available and better than the one from events page
                if event_details.get("event_name") and event_details["event_name"].lower() not in ["upcoming events", "events", "tournaments"]:
                    e["name"] = event_details["event_name"]
                # Try to extract/normalize event dates from details if missing
                if not e.get("dates"):
                    for k in ["date", "event date", "tournament date"]:
                        if k in event_details and event_details[k]:
                            parsed_dates = parse_multiple_dates(event_details[k])
                            if parsed_dates:
                                e["dates"] = [d.isoformat() for d in parsed_dates]
                                break
            except Exception as ex:
                print(f"[WARN] fetch event details failed for {e['event_id']}: {ex}", file=sys.stderr)
        
        # Fetch entry list
        try:
            entry_html = http_get(e["entry_list_url"], insecure=True)
            participants, entry_event_name = parse_entry_list(entry_html)
            
            # Use event name from entry list if available and better than current name
            if entry_event_name and entry_event_name.lower() not in ["upcoming events", "events", "tournaments"]:
                e["name"] = entry_event_name
            
            # Apply filtering rules now that we have the proper event name
            if not match_rules(e["name"]):
                print(f"[INFO] Event '{e['name']}' filtered out by include/exclude rules")
                continue

            # Now that we've attempted to populate dates, apply the date window filter
            if not within_days(e.get("dates", []), days_before):
                # Skip events outside the monitoring window
                continue
            
            if not participants:
                print(f"[DEBUG] No participants found for event {e['event_id']}. Entry list URL: {e['entry_list_url']}", file=sys.stderr)
                if debug:
                    # Save HTML for debugging
                    debug_file = f"debug_entry_{e['event_id']}.html"
                    with open(debug_file, "w", encoding="utf-8") as f:
                        f.write(entry_html)
                    print(f"[DEBUG] Saved HTML to {debug_file}", file=sys.stderr)
        except Exception as ex:
            print(f"[WARN] fetch/parse entry list failed for {e['event_id']}: {ex}", file=sys.stderr)
            continue

        snap_path = os.path.join(data_dir, f"{e['event_id']}.json")
        previous = load_snapshot(snap_path) or {}
        prev_participants = previous.get("participants", [])
        added, removed = diff_lists(prev_participants, participants)

        snapshot = {
            "event_id": e["event_id"],
            "event_name": e["name"],
            "event_dates": e.get("dates", []),
            "event_detail_url": e.get("event_detail_url"),
            "entry_list_url": e["entry_list_url"],
            "event_details": event_details,
            "last_checked": datetime.now().isoformat(timespec="seconds"),
            "participants": participants,
            "count": len(participants),
        }
        save_snapshot(snap_path, snapshot)

        reports.append(
            {
                "name": e["name"],
                "dates": e.get("dates", []),
                "detail_url": e.get("event_detail_url"),
                "entry_url": e["entry_list_url"],
                "count": len(participants),
                "added": added,
                "removed": removed,
                "event_details": event_details,
            }
        )

    if not reports:
        print("[INFO] No events within window matching rules.")
        cleanup_expired(data_dir)
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"BCF event updates ({today_str})")
    print("=" * 50)
    
    for r in reports:
        delta = f"(+{len(r['added'])} -{len(r['removed'])})" if (r["added"] or r["removed"]) else "(no changes)"
        # Make title clickable if detail_url exists by printing URL on same line
        if r.get("detail_url"):
            print(f"\n📅 {r['name']} - {r['detail_url']}")
        else:
            print(f"\n📅 {r['name']}")
        
        # Format dates - single date or list
        dates = r.get("dates", [])
        if len(dates) == 1:
            date_display = dates[0]
        elif len(dates) > 1:
            date_display = f"{dates[0]} to {dates[-1]}" if len(dates) > 2 else ", ".join(dates)
        else:
            date_display = "TBD"
        
        print(f"   Date: {date_display}")
        print(f"   Participants: {r['count']} {delta}")
        
        # Show key event details if available
        # Note: Entry Fee, Time Control, and Sections fields removed per user request
        
        if r["added"]:
            print(f"   ✅ New participants:")
            for p in r["added"]:
                if isinstance(p, dict):
                    rating_info = f" ({p['rating']})" if p.get("rating") else ""
                    section_info = f" [{p['section']}]" if p.get("section") else ""
                    print(f"      • {p['name']}{rating_info}{section_info}")
                else:
                    print(f"      • {p}")
        
        if r["removed"]:
            print(f"   ❌ Withdrawn participants:")
            for p in r["removed"]:
                if isinstance(p, dict):
                    rating_info = f" ({p['rating']})" if p.get("rating") else ""
                    section_info = f" [{p['section']}]" if p.get("section") else ""
                    print(f"      • {p['name']}{rating_info}{section_info}")
                else:
                    print(f"      • {p}")
        
        # Only show Entry List if there are participants
        if r['count'] > 0:
            print(f"   📝 Entry List: {r['entry_url']}")
    
    print("\n" + "=" * 50)

    # Send email notification if enabled
    if email_config["enabled"]:
        should_send = True
        if email_config.get("only_changes", True) and not has_significant_changes(reports):
            should_send = False
            print("[INFO] Email notifications enabled but no changes detected, skipping email.")
        
        if should_send:
            send_email_notification(reports, email_config)

    cleanup_expired(data_dir)


if __name__ == "__main__":
    main()


