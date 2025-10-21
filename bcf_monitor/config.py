"""
Configuration management for BCF Events Monitor.

This module handles loading, saving, and validating configuration settings
from JSON files and environment variables.
"""

import json
import os
import sys
from typing import Dict, Any, Optional, Tuple


class Config:
    """Configuration manager for BCF Events Monitor."""
    
    # Default configuration values
    DEFAULT_CONFIG = {
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
    
    # Environment variable mappings
    ENV_MAPPINGS = {
        "BCF_EMAIL_SMTP_SERVER": ("email", "smtp_server"),
        "BCF_EMAIL_SMTP_PORT": ("email", "smtp_port"),
        "BCF_EMAIL_USERNAME": ("email", "username"),
        "BCF_EMAIL_PASSWORD": ("email", "password"),
        "BCF_EMAIL_FROM": ("email", "from"),
        "BCF_EMAIL_TO": ("email", "to"),
    }
    
    def __init__(self, config_file: str = "bcf_monitor_config.json"):
        """Initialize configuration manager.
        
        Args:
            config_file: Path to the configuration file
        """
        self.config_file = config_file
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file and environment variables."""
        config = self.DEFAULT_CONFIG.copy()
        
        # Load from file if it exists
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    file_config = json.load(f)
                
                # Merge file config with defaults
                config.update(file_config)
                
                # Ensure email config is properly merged
                if "email" in file_config:
                    config["email"].update(file_config["email"])
                    
            except Exception as e:
                print(f"[WARN] Failed to load config file {self.config_file}: {e}", file=sys.stderr)
        
        # Override with environment variables
        for env_var, (section, key) in self.ENV_MAPPINGS.items():
            value = os.getenv(env_var)
            if value is not None:
                if section == "email":
                    config["email"][key] = value
                else:
                    config[section] = value
        
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.
        
        Args:
            key: Configuration key (supports dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.
        
        Args:
            key: Configuration key (supports dot notation for nested keys)
            value: Value to set
        """
        keys = key.split(".")
        config = self._config
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the final value
        config[keys[-1]] = value
    
    def save(self) -> bool:
        """Save current configuration to file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save config file {self.config_file}: {e}", file=sys.stderr)
            return False
    
    def create_default_config(self) -> bool:
        """Create a default configuration file with comments.
        
        Returns:
            True if successful, False otherwise
        """
        default_config = {
            "_comment": "BCF Events Monitor Configuration File",
            "_instructions": [
                "Modify the values below to set your default preferences.",
                "You can still override these settings using command line arguments.",
                "Remove the _comment and _instructions fields when you're done configuring."
            ],
            **self.DEFAULT_CONFIG
        }
        
        # Update email config with example values
        default_config["email"].update({
            "to": "your-email@example.com",
            "from": "your-gmail@gmail.com",
            "username": "your-gmail@gmail.com",
            "password": "your-app-password-here",
        })
        
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to create config file {self.config_file}: {e}", file=sys.stderr)
            return False
    
    def validate_email_config(self) -> Tuple[bool, Optional[str]]:
        """Validate email configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.get("email.enabled", False):
            return True, None
        
        if not self.get("email.to"):
            return False, "Email notifications enabled but no recipient email specified"
        
        if not self.get("email.username") or not self.get("email.password"):
            return False, "Email notifications enabled but SMTP credentials not specified"
        
        return True, None
    
    def to_dict(self) -> Dict[str, Any]:
        """Get the complete configuration as a dictionary.
        
        Returns:
            Configuration dictionary
        """
        return self._config.copy()
