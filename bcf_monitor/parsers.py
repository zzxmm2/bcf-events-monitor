"""
HTML parsing modules for BCF Events Monitor.

This module contains all the HTML parsing logic for extracting event information,
participant data, and other details from the BCF website.
"""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup


class DateParser:
    """Parser for extracting and normalizing dates from various formats."""
    
    DATE_PATTERNS = [
        "%A, %B %d, %Y",
        "%B %d, %Y", 
        "%Y-%m-%d",
        "%m/%d/%Y",
    ]
    
    @staticmethod
    def parse_date(text: str) -> Optional[datetime]:
        """Parse a single date from text.
        
        Args:
            text: Text containing a date
            
        Returns:
            Parsed date object or None if parsing fails
        """
        if not text:
            return None
            
        cleaned = re.sub(r"\s+", " ", text.strip())
        
        # Try standard patterns first
        for pattern in DateParser.DATE_PATTERNS:
            try:
                return datetime.strptime(cleaned, pattern).date()
            except ValueError:
                continue
        
        # Try regex pattern for YYYY-MM-DD or MM/DD/YYYY
        match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", cleaned)
        if match:
            year, month, day = map(int, match.groups())
            return datetime(year, month, day).date()
        
        return None
    
    @staticmethod
    def parse_multiple_dates(text: str) -> List[datetime]:
        """Parse text that may contain multiple dates or date ranges.
        
        Args:
            text: Text containing dates
            
        Returns:
            List of parsed dates
        """
        if not text:
            return []
        
        cleaned = re.sub(r"\s+", " ", text.strip())
        dates = []
        
        # Extract month and year information first
        month_year_match = re.search(r"([A-Za-z]+).*?(\d{4})", cleaned)
        if not month_year_match:
            # Fallback to single date parsing
            single_date = DateParser.parse_date(cleaned)
            return [single_date] if single_date else []
        
        month_name = month_year_match.group(1)
        year = int(month_year_match.group(2))
        
        try:
            month_num = datetime.strptime(month_name, "%B").month
        except ValueError:
            # Fallback to single date parsing
            single_date = DateParser.parse_date(cleaned)
            return [single_date] if single_date else []
        
        # Handle date ranges (contains '-')
        if '-' in cleaned:
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
                
                # For end date, also add month if not present
                if month_name.lower() not in end_clean.lower():
                    end_clean = f"{month_name} {end_clean}"
                
                start_date = DateParser.parse_date(start_clean)
                end_date = DateParser.parse_date(end_clean)
                
                if start_date and end_date:
                    current = start_date
                    while current <= end_date:
                        dates.append(current)
                        current += timedelta(days=1)
                    return dates
        
        # Handle individual days (contains 'and' keyword)
        elif 'and' in cleaned:
            parts = re.split(r',\s*and\s*|,\s*', cleaned)
            day_numbers = []
            
            for part in parts:
                numbers = re.findall(r'\b(\d{1,2})\b', part)
                for num_str in numbers:
                    day = int(num_str)
                    if 1 <= day <= 31 and day != year:
                        day_numbers.append(day)
            
            for day in day_numbers:
                dates.append(datetime(year, month_num, day).date())
            
            if dates:
                return sorted(dates)
        
        # Handle comma-separated days without 'and' keyword
        elif ',' in cleaned:
            parts = cleaned.split(',')
            day_numbers = []
            
            for part in parts:
                numbers = re.findall(r'\b(\d{1,2})\b', part)
                for num_str in numbers:
                    day = int(num_str)
                    if 1 <= day <= 31 and day != year:
                        day_numbers.append(day)
            
            for day in day_numbers:
                dates.append(datetime(year, month_num, day).date())
            
            if dates:
                return sorted(dates)
        
        # Fallback to single date parsing
        single_date = DateParser.parse_date(cleaned)
        return [single_date] if single_date else []


class EventParser:
    """Parser for extracting event information from HTML pages."""
    
    def __init__(self, base_url: str = "https://boylstonchess.org"):
        """Initialize event parser.
        
        Args:
            base_url: Base URL for resolving relative links
        """
        self.base_url = base_url
    
    def find_nearest_heading_text(self, elem) -> Optional[str]:
        """Find the nearest meaningful heading text for an element.
        
        Args:
            elem: BeautifulSoup element
            
        Returns:
            Heading text or None
        """
        # First, try to find a more specific heading that's not generic
        for heading in elem.find_all_previous(["h1", "h2", "h3", "h4", "h5"]):
            heading_text = " ".join(heading.get_text(" ").split())
            # Skip generic headings
            if heading_text.lower() not in ["upcoming events", "events", "tournaments", "chess events"]:
                return heading_text
        
        # If no specific heading found, try to find the event name in the link text or nearby text
        parent = elem.find_parent(["div", "section", "article", "td", "li"])
        if parent:
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
    
    def find_event_dates(self, elem) -> List[datetime]:
        """Find event dates from an element.
        
        Args:
            elem: BeautifulSoup element
            
        Returns:
            List of parsed dates
        """
        block = elem.find_parent(["table", "div", "section", "article"]) or elem.parent
        if not block:
            return []
        
        # Look in table rows first
        for tr in block.find_all("tr"):
            cells = [td.get_text(" ").strip() for td in tr.find_all(["td", "th"])]
            if not cells:
                continue
            if re.search(r"^date$", cells[0], re.I) and len(cells) > 1:
                dates = DateParser.parse_multiple_dates(cells[1])
                if dates:
                    return dates
        
        # Look for date labels
        labels = block.find_all(string=re.compile(r"^\s*Date\s*$", re.I))
        for lab in labels:
            sib = lab.parent.find_next(string=True)
            if sib:
                dates = DateParser.parse_multiple_dates(sib)
                if dates:
                    return dates
        
        # Look for date patterns in the text
        txt = " ".join(block.get_text(" ").split())
        dates = DateParser.parse_multiple_dates(txt)
        if dates:
            return dates
        
        return []
    
    def parse_events_page(self, html: str) -> List[Dict[str, Any]]:
        """Parse the main events listing page.
        
        Args:
            html: HTML content of the events page
            
        Returns:
            List of event dictionaries
        """
        soup = BeautifulSoup(html, "html.parser")
        events = []
        
        container = soup.find("div", id="events") or soup.find(id="events")
        if not container:
            return events
        
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
                event_name = self.find_nearest_heading_text(block) or "Unknown Event"
            
            # Choose an anchor near the date (detail link or any link), fallback to the block itself
            anchor_for_date = detail_link or entry_link_tag or block
            date_values = self.find_event_dates(anchor_for_date)
            
            event_detail_url = urljoin(self.base_url, detail_link["href"]) if detail_link else None
            if entry_link_tag:
                entry_list_url = urljoin(self.base_url, entry_link_tag["href"])
            elif event_id:
                entry_list_url = urljoin(self.base_url, f"/tournament/entries/{event_id}")
            else:
                entry_list_url = None
            
            if event_id or entry_list_url:
                events.append({
                    "event_id": event_id or (re.search(r"/entries/(\d+)", entry_link_tag["href"]).group(1) if entry_link_tag else ""),
                    "name": event_name,
                    "dates": [d.isoformat() for d in date_values] if date_values else [],
                    "event_detail_url": event_detail_url,
                    "entry_list_url": entry_list_url,
                })
        
        # Treat each direct child of the container as an event block
        for child in container.find_all(recursive=False):
            if getattr(child, "name", None):
                extract_event_from_block(child)
        
        # Remove duplicates by event_id
        unique_by_id = {}
        for ev in events:
            unique_by_id.setdefault(ev["event_id"], ev)
        return list(unique_by_id.values())
    
    def parse_event_details(self, html: str) -> Dict[str, Any]:
        """Parse detailed event information from event detail page.
        
        Args:
            html: HTML content of the event detail page
            
        Returns:
            Dictionary of event details
        """
        soup = BeautifulSoup(html, "html.parser")
        details = {}
        
        # Try to extract event name from the page title or main heading
        event_name = None
        
        # Look for page title
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(" ").strip()
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
                    if key in ["name", "event name", "tournament name", "title"]:
                        event_name = value
        
        # Store the event name if found
        if event_name:
            details["event_name"] = event_name
        
        return details


class EntryListParser:
    """Parser for extracting participant information from entry list pages."""
    
    def parse_entry_list(self, html: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Parse entry list from tournament entries page.
        
        Args:
            html: HTML content of the entry list page
            
        Returns:
            Tuple of (participants_list, event_name)
        """
        soup = BeautifulSoup(html, "html.parser")
        participants = []
        
        # Extract event name from page title
        event_name = self._extract_event_name_from_title(soup)
        
        # First, try to find the specific "members" table (BCF format)
        members_table = soup.find("table", id="members")
        if members_table:
            participants = self._parse_members_table(members_table)
        
        # If no participants found in members table, try other approaches
        if not participants:
            participants = self._parse_generic_tables(soup)
        
        # Normalize names and remove duplicates
        participants = self._normalize_and_deduplicate(participants)
        
        return participants, event_name
    
    def _extract_event_name_from_title(self, soup) -> Optional[str]:
        """Extract event name from page title."""
        title_tag = soup.find("title")
        if not title_tag:
            return None
            
        title_text = title_tag.get_text(" ").strip()
        
        # Extract event name from title like "Registration List • Unrated Friday Night Blitz • Boylston Chess Foundation"
        if "•" in title_text:
            parts = [part.strip() for part in title_text.split("•")]
            if len(parts) >= 2:
                return parts[1]  # Second part should be the event name
        elif "Registration List" in title_text:
            # Fallback: try to extract from "Registration List &bull; Event Name &bull; Boylston Chess Foundation"
            match = re.search(r"Registration List[^•]*•\s*([^•]+)\s*•", title_text)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _parse_members_table(self, table) -> List[Dict[str, Any]]:
        """Parse the specific members table format."""
        participants = []
        rows = table.find_all("tr")
        
        if len(rows) > 1:  # Has header and data rows
            for tr in rows[1:]:  # Skip header row
                cells = [c.get_text(" ").strip() for c in tr.find_all(["td", "th"])]
                if len(cells) >= 6:  # Should have #, Name, Rating, USCF ID, Section, Byes
                    name = cells[1] if len(cells) > 1 else ""
                    rating = cells[2] if len(cells) > 2 else ""
                    uscf_id = cells[3] if len(cells) > 3 else ""
                    section = cells[4] if len(cells) > 4 else ""
                    byes = cells[5] if len(cells) > 5 else ""
                    
                    if name and name.strip():
                        participants.append({
                            "name": name.strip(),
                            "rating": rating.strip() if rating else None,
                            "uscf_id": uscf_id.strip() if uscf_id else None,
                            "section": section.strip() if section else None,
                            "byes": byes.strip() if byes else None,
                        })
        
        return participants
    
    def _parse_generic_tables(self, soup) -> List[Dict[str, Any]]:
        """Parse generic table formats for entry lists."""
        participants = []
        
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
        
        return participants
    
    def _normalize_and_deduplicate(self, participants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize participant names and remove duplicates."""
        def normalize_name(name: str) -> str:
            return re.sub(r"\s+", " ", (name or "").strip())
        
        # Normalize names
        for p in participants:
            p["name"] = normalize_name(p["name"])
        
        # Remove duplicates
        seen = set()
        unique_participants = []
        for p in participants:
            if p["name"] not in seen:
                seen.add(p["name"])
                unique_participants.append(p)
        
        return unique_participants
