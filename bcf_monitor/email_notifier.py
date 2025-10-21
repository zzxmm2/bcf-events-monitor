"""
Email notification system for BCF Events Monitor.

This module handles sending email notifications about event updates
with both plain text and HTML formatting.
"""

import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Tuple


class EmailNotifier:
    """Email notification system for BCF Events Monitor."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize email notifier.
        
        Args:
            config: Email configuration dictionary
        """
        self.config = config
        self.enabled = config.get("enabled", False)
        self.to = config.get("to", "")
        self.from_addr = config.get("from", "")
        self.smtp_server = config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = config.get("smtp_port", 587)
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self.only_changes = config.get("only_changes", True)
    
    def is_enabled(self) -> bool:
        """Check if email notifications are enabled.
        
        Returns:
            True if enabled and properly configured
        """
        return (self.enabled and 
                bool(self.to) and 
                bool(self.username) and 
                bool(self.password))
    
    def has_significant_changes(self, reports: List[Dict[str, Any]]) -> bool:
        """Check if there are any significant changes worth notifying about.
        
        Args:
            reports: List of event reports
            
        Returns:
            True if there are significant changes
        """
        for report in reports:
            if report.get("added") or report.get("removed"):
                return True
        return False
    
    def should_send_notification(self, reports: List[Dict[str, Any]]) -> bool:
        """Determine if a notification should be sent.
        
        Args:
            reports: List of event reports
            
        Returns:
            True if notification should be sent
        """
        if not self.is_enabled():
            return False
        
        if self.only_changes and not self.has_significant_changes(reports):
            return False
        
        return True
    
    def send_notification(self, reports: List[Dict[str, Any]]) -> bool:
        """Send email notification with event updates.
        
        Args:
            reports: List of event reports to include in notification
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self.should_send_notification(reports):
            return False
        
        try:
            # Create message with plain text and HTML alternatives
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_addr
            msg['To'] = self.to
            msg['Subject'] = f"BCF Events Update - {datetime.now().strftime('%Y-%m-%d')}"
            
            # Create message body
            text_body, html_body = self._create_message_bodies(reports)
            
            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            text = msg.as_string()
            server.sendmail(self.from_addr, self.to, text)
            server.quit()
            
            print(f"[INFO] Email notification sent to {self.to}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to send email notification: {e}", file=sys.stderr)
            return False
    
    def _create_message_bodies(self, reports: List[Dict[str, Any]]) -> Tuple[str, str]:
        """Create both plain text and HTML message bodies.
        
        Args:
            reports: List of event reports
            
        Returns:
            Tuple of (text_body, html_body)
        """
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
            for report in reports:
                text_body += self._format_report_text(report)
                html_body.append(self._format_report_html(report))
        
        html_body.append("<hr/>")
        html_body.append("<div>This is an automated message from BCF Events Monitor.</div>")
        html_body.append("</body></html>")
        
        text_body += "\n" + "=" * 50 + "\n"
        text_body += "This is an automated message from BCF Events Monitor.\n"
        
        return text_body, "\n".join(html_body)
    
    def _format_report_text(self, report: Dict[str, Any]) -> str:
        """Format a single report for plain text.
        
        Args:
            report: Event report dictionary
            
        Returns:
            Formatted text string
        """
        text = ""
        
        # Title line with link
        if report.get("detail_url"):
            text += f"📅 {report['name']} - {report['detail_url']}\n"
        else:
            text += f"📅 {report['name']}\n"
        
        # Format dates
        dates = report.get("dates", [])
        if len(dates) == 1:
            date_display = dates[0]
        elif len(dates) > 1:
            date_display = f"[{', '.join(dates)}]"
        else:
            date_display = "TBD"
        
        text += f"   Date: {date_display}\n"
        text += f"   Participants: {report['count']}\n"
        
        # Show changes
        if report.get("added"):
            text += f"   ✅ New participants:\n"
            for participant in report["added"]:
                if isinstance(participant, dict):
                    rating_info = f" ({participant['rating']})" if participant.get("rating") else ""
                    section_info = f" [{participant['section']}]" if participant.get("section") else ""
                    text += f"      • {participant['name']}{rating_info}{section_info}\n"
                else:
                    text += f"      • {participant}\n"
        
        if report.get("removed"):
            text += f"   ❌ Withdrawn participants:\n"
            for participant in report["removed"]:
                if isinstance(participant, dict):
                    rating_info = f" ({participant['rating']})" if participant.get("rating") else ""
                    section_info = f" [{participant['section']}]" if participant.get("section") else ""
                    text += f"      • {participant['name']}{rating_info}{section_info}\n"
                else:
                    text += f"      • {participant}\n"
        
        text += f"   📝 Entry List: {report['entry_url']}\n\n"
        
        return text
    
    def _format_report_html(self, report: Dict[str, Any]) -> str:
        """Format a single report for HTML.
        
        Args:
            report: Event report dictionary
            
        Returns:
            Formatted HTML string
        """
        html_parts = []
        
        # Title line with link
        if report.get("detail_url"):
            html_parts.append(f"<p>📅 <a href=\"{report['detail_url']}\">{report['name']}</a></p>")
        else:
            html_parts.append(f"<p>📅 {report['name']}</p>")
        
        # Format dates
        dates = report.get("dates", [])
        if len(dates) == 1:
            date_display = dates[0]
        elif len(dates) > 1:
            date_display = f"[{', '.join(dates)}]"
        else:
            date_display = "TBD"
        
        html_parts.append(f"<div>Date: {date_display}</div>")
        html_parts.append(f"<div>Participants: {report['count']}</div>")
        
        # Show changes
        if report.get("added"):
            html_parts.append("<div>✅ New participants:</div><ul>")
            for participant in report["added"]:
                if isinstance(participant, dict):
                    rating_info = f" ({participant['rating']})" if participant.get("rating") else ""
                    section_info = f" [{participant['section']}]" if participant.get("section") else ""
                    html_parts.append(f"<li>{participant['name']}{rating_info}{section_info}</li>")
                else:
                    html_parts.append(f"<li>{participant}</li>")
            html_parts.append("</ul>")
        
        if report.get("removed"):
            html_parts.append("<div>❌ Withdrawn participants:</div><ul>")
            for participant in report["removed"]:
                if isinstance(participant, dict):
                    rating_info = f" ({participant['rating']})" if participant.get("rating") else ""
                    section_info = f" [{participant['section']}]" if participant.get("section") else ""
                    html_parts.append(f"<li>{participant['name']}{rating_info}{section_info}</li>")
                else:
                    html_parts.append(f"<li>{participant}</li>")
            html_parts.append("</ul>")
        
        html_parts.append(f"<div>📝 Entry List: <a href=\"{report['entry_url']}\">{report['entry_url']}</a></div>")
        
        return "".join(html_parts)
