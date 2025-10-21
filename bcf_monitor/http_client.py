"""
HTTP client for BCF Events Monitor.

This module provides a clean interface for making HTTP requests
with proper error handling and configuration.
"""

import certifi
import requests
from typing import Optional


class HTTPClient:
    """HTTP client for making requests to BCF website."""
    
    def __init__(self, 
                 user_agent: str = "bcf-monitor/0.1 (+https://boylstonchess.org/events)",
                 timeout: int = 20,
                 verify_ssl: bool = True):
        """Initialize HTTP client.
        
        Args:
            user_agent: User agent string for requests
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
        """
        self.user_agent = user_agent
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
    
    def get(self, url: str, insecure: bool = False) -> str:
        """Make a GET request to the specified URL.
        
        Args:
            url: URL to request
            insecure: If True, disable SSL verification
            
        Returns:
            Response text content
            
        Raises:
            requests.RequestException: If the request fails
        """
        verify = False if insecure else (certifi.where() if self.verify_ssl else False)
        
        response = self.session.get(
            url,
            timeout=self.timeout,
            verify=verify
        )
        response.raise_for_status()
        return response.text
    
    def close(self):
        """Close the HTTP session."""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
