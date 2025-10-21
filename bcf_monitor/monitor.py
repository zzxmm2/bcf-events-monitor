"""
Main monitoring orchestrator for BCF Events Monitor.

This module contains the core monitoring logic that coordinates
all the different components to monitor BCF events.
"""

import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from .config import Config
from .http_client import HTTPClient
from .parsers import EventParser, EntryListParser, DateParser
from .email_notifier import EmailNotifier


class BCFMonitor:
    """Main monitoring class for BCF Events Monitor."""
    
    # Constants
    BASE_URL = "https://boylstonchess.org"
    EVENTS_URL = "https://boylstonchess.org/events"
    
    def __init__(self, config: Config):
        """Initialize the BCF monitor.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.data_dir = config.get("data_dir", "./data")
        self.days_before = config.get("days_before", 7)
        self.debug = config.get("debug", False)
        
        # Initialize components
        self.http_client = HTTPClient()
        self.event_parser = EventParser(self.BASE_URL)
        self.entry_parser = EntryListParser()
        self.email_notifier = EmailNotifier(config.get("email", {}))
        
        # Setup filtering rules
        self._setup_filtering_rules()
    
    def _setup_filtering_rules(self):
        """Setup include/exclude filtering rules."""
        include_str = self.config.get("include", "")
        exclude_str = self.config.get("exclude", "")
        
        self.include_keywords = [s.strip().lower() for s in include_str.split(",") if s.strip()]
        self.exclude_keywords = [s.strip().lower() for s in exclude_str.split(",") if s.strip()]
    
    def _match_rules(self, name: str) -> bool:
        """Check if event name matches include/exclude rules.
        
        Args:
            name: Event name to check
            
        Returns:
            True if event should be included
        """
        lower_name = (name or "").lower()
        
        # Check include rules
        if self.include_keywords and not any(k in lower_name for k in self.include_keywords):
            return False
        
        # Check exclude rules
        if self.exclude_keywords and any(k in lower_name for k in self.exclude_keywords):
            return False
        
        return True
    
    def _within_days(self, event_dates: List[str], days_before: int) -> bool:
        """Check if any of the event dates are within the monitoring window.
        
        Args:
            event_dates: List of ISO date strings
            days_before: Number of days before event to start monitoring
            
        Returns:
            True if event is within monitoring window
        """
        if not event_dates:
            return False
        
        today = datetime.now(timezone.utc).astimezone().date()
        
        for date_str in event_dates:
            try:
                event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if event_date >= today and (event_date - today).days <= days_before:
                    return True
            except Exception:
                continue
        return False
    
    def _expired(self, event_dates: List[str]) -> bool:
        """Check if all event dates have passed.
        
        Args:
            event_dates: List of ISO date strings
            
        Returns:
            True if all dates are in the past
        """
        if not event_dates:
            return True
        
        today = datetime.now(timezone.utc).astimezone().date()
        
        for date_str in event_dates:
            try:
                event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if event_date >= today:
                    return False  # At least one date is in the future
            except Exception:
                continue
        return True  # All dates are in the past or invalid
    
    def _load_snapshot(self, path: str) -> Optional[Dict[str, Any]]:
        """Load a snapshot from file.
        
        Args:
            path: Path to snapshot file
            
        Returns:
            Snapshot data or None if file doesn't exist
        """
        if not os.path.exists(path):
            return None
        try:
            import json
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    
    def _save_snapshot(self, path: str, data: Dict[str, Any]) -> None:
        """Save a snapshot to file.
        
        Args:
            path: Path to save snapshot
            data: Snapshot data to save
        """
        dirname = os.path.dirname(path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        
        tmp = path + ".tmp"
        try:
            import json
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            print(f"[ERROR] Failed to save snapshot {path}: {e}", file=sys.stderr)
    
    def _diff_lists(self, old_list: List[Dict[str, Any]], new_list: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Compare old and new participant lists and return added/removed participants.
        
        Args:
            old_list: Previous participant list
            new_list: Current participant list
            
        Returns:
            Tuple of (added_participants, removed_participants)
        """
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
    
    def _cleanup_expired(self) -> None:
        """Remove expired event snapshots."""
        if not os.path.isdir(self.data_dir):
            return
        
        for filename in os.listdir(self.data_dir):
            if not filename.endswith(".json"):
                continue
            
            path = os.path.join(self.data_dir, filename)
            try:
                snapshot = self._load_snapshot(path)
                if not snapshot:
                    continue
                
                if self._expired(snapshot.get("event_dates", [])):
                    os.remove(path)
                    print(f"[INFO] removed expired snapshot {filename}")
            except Exception:
                pass
    
    def _fetch_events_page(self) -> str:
        """Fetch the main events page.
        
        Returns:
            HTML content of events page
            
        Raises:
            Exception: If fetching fails
        """
        try:
            return self.http_client.get(self.EVENTS_URL, insecure=True)
        except Exception as e:
            print(f"[ERR] fetch events page failed: {e}", file=sys.stderr)
            raise
    
    def _process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single event and return report.
        
        Args:
            event: Event dictionary from events page
            
        Returns:
            Event report dictionary or None if event should be skipped
        """
        event_id = event["event_id"]
        event_details = {}
        
        # Fetch event details if URL is available
        if event.get("event_detail_url"):
            try:
                detail_html = self.http_client.get(event["event_detail_url"], insecure=True)
                event_details = self.event_parser.parse_event_details(detail_html)
                
                # Use event name from details if available and better
                if (event_details.get("event_name") and 
                    event_details["event_name"].lower() not in ["upcoming events", "events", "tournaments"]):
                    event["name"] = event_details["event_name"]
                
                # Try to extract/normalize event dates from details if missing
                if not event.get("dates"):
                    for key in ["date", "event date", "tournament date"]:
                        if key in event_details and event_details[key]:
                            parsed_dates = DateParser.parse_multiple_dates(event_details[key])
                            if parsed_dates:
                                event["dates"] = [d.isoformat() for d in parsed_dates]
                                break
            except Exception as ex:
                print(f"[WARN] fetch event details failed for {event_id}: {ex}", file=sys.stderr)
        
        # Fetch entry list
        try:
            entry_html = self.http_client.get(event["entry_list_url"], insecure=True)
            participants, entry_event_name = self.entry_parser.parse_entry_list(entry_html)
            
            # Use event name from entry list if available and better
            if (entry_event_name and 
                entry_event_name.lower() not in ["upcoming events", "events", "tournaments"]):
                event["name"] = entry_event_name
            
            # Apply filtering rules now that we have the proper event name
            if not self._match_rules(event["name"]):
                print(f"[INFO] Event '{event['name']}' filtered out by include/exclude rules")
                return None
            
            # Apply the date window filter
            if not self._within_days(event.get("dates", []), self.days_before):
                return None
            
            if not participants:
                print(f"[DEBUG] No participants found for event {event_id}. Entry list URL: {event['entry_list_url']}", file=sys.stderr)
                if self.debug:
                    # Save HTML for debugging
                    debug_file = f"debug_entry_{event_id}.html"
                    with open(debug_file, "w", encoding="utf-8") as f:
                        f.write(entry_html)
                    print(f"[DEBUG] Saved HTML to {debug_file}", file=sys.stderr)
                return None
                
        except Exception as ex:
            print(f"[WARN] fetch/parse entry list failed for {event_id}: {ex}", file=sys.stderr)
            return None
        
        # Load previous snapshot and compare
        snap_path = os.path.join(self.data_dir, f"{event_id}.json")
        previous = self._load_snapshot(snap_path) or {}
        prev_participants = previous.get("participants", [])
        added, removed = self._diff_lists(prev_participants, participants)
        
        # Save new snapshot
        snapshot = {
            "event_id": event_id,
            "event_name": event["name"],
            "event_dates": event.get("dates", []),
            "event_detail_url": event.get("event_detail_url"),
            "entry_list_url": event["entry_list_url"],
            "event_details": event_details,
            "last_checked": datetime.now().isoformat(timespec="seconds"),
            "participants": participants,
            "count": len(participants),
        }
        self._save_snapshot(snap_path, snapshot)
        
        # Return report
        return {
            "name": event["name"],
            "dates": event.get("dates", []),
            "detail_url": event.get("event_detail_url"),
            "entry_url": event["entry_list_url"],
            "count": len(participants),
            "added": added,
            "removed": removed,
            "event_details": event_details,
        }
    
    def _print_reports(self, reports: List[Dict[str, Any]]) -> None:
        """Print event reports to console.
        
        Args:
            reports: List of event reports
        """
        if not reports:
            print("[INFO] No events within window matching rules.")
            return
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        print(f"BCF event updates ({today_str})")
        print("=" * 50)
        
        for report in reports:
            delta = f"(+{len(report['added'])} -{len(report['removed'])})" if (report["added"] or report["removed"]) else "(no changes)"
            
            # Print title with link if available
            if report.get("detail_url"):
                print(f"\n📅 {report['name']} - {report['detail_url']}")
            else:
                print(f"\n📅 {report['name']}")
            
            # Format dates
            dates = report.get("dates", [])
            if len(dates) == 1:
                date_display = dates[0]
            elif len(dates) > 1:
                date_display = f"{dates[0]} to {dates[-1]}" if len(dates) > 2 else ", ".join(dates)
            else:
                date_display = "TBD"
            
            print(f"   Date: {date_display}")
            print(f"   Participants: {report['count']} {delta}")
            
            # Show changes
            if report["added"]:
                print(f"   ✅ New participants:")
                for participant in report["added"]:
                    if isinstance(participant, dict):
                        rating_info = f" ({participant['rating']})" if participant.get("rating") else ""
                        section_info = f" [{participant['section']}]" if participant.get("section") else ""
                        print(f"      • {participant['name']}{rating_info}{section_info}")
                    else:
                        print(f"      • {participant}")
            
            if report["removed"]:
                print(f"   ❌ Withdrawn participants:")
                for participant in report["removed"]:
                    if isinstance(participant, dict):
                        rating_info = f" ({participant['rating']})" if participant.get("rating") else ""
                        section_info = f" [{participant['section']}]" if participant.get("section") else ""
                        print(f"      • {participant['name']}{rating_info}{section_info}")
                    else:
                        print(f"      • {participant}")
            
            print(f"   📝 Entry List: {report['entry_url']}")
        
        print("\n" + "=" * 50)
    
    def run(self) -> None:
        """Run the monitoring process."""
        try:
            # Fetch events page
            events_html = self._fetch_events_page()
            
            # Parse events from listing page
            events = self.event_parser.parse_events_page(events_html)
            if not events:
                print("[INFO] No events discovered on events listing page.")
                self._cleanup_expired()
                return
            
            # Process each event
            reports = []
            for event in events:
                report = self._process_event(event)
                if report:
                    reports.append(report)
            
            # Print reports
            self._print_reports(reports)
            
            # Send email notification if enabled
            if self.email_notifier.is_enabled():
                should_send = True
                if (self.email_notifier.only_changes and 
                    not self.email_notifier.has_significant_changes(reports)):
                    should_send = False
                    print("[INFO] Email notifications enabled but no changes detected, skipping email.")
                
                if should_send:
                    self.email_notifier.send_notification(reports)
            
            # Cleanup expired snapshots
            self._cleanup_expired()
            
        except Exception as e:
            print(f"[ERROR] Monitoring failed: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            self.http_client.close()
