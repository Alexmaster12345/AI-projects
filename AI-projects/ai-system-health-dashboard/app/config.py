"""Configuration settings for the application."""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings."""
    
    def __init__(self):
        # Basic app settings
        self.app_version = os.getenv("APP_VERSION", "dev")
        self.help_url = os.getenv("HELP_URL", "")
        
        # Sampling settings
        self.sample_interval_seconds = float(os.getenv("SAMPLE_INTERVAL_SECONDS", "5"))
        self.history_seconds = int(os.getenv("HISTORY_SECONDS", "300"))
        
        # Anomaly detection settings
        self.anomaly_window_seconds = int(os.getenv("ANOMALY_WINDOW_SECONDS", "60"))
        self.anomaly_z_threshold = float(os.getenv("ANOMALY_Z_THRESHOLD", "2.0"))
        
        # Protocol checking settings
        self.protocol_check_interval_seconds = float(os.getenv("PROTOCOL_CHECK_INTERVAL_SECONDS", "15"))
        
        # NTP settings
        self.ntp_server = os.getenv("NTP_SERVER", "pool.ntp.org")
        self.ntp_timeout_seconds = float(os.getenv("NTP_TIMEOUT_SECONDS", "1.2"))
        
        # ICMP settings
        self.icmp_host = os.getenv("ICMP_HOST", "8.8.8.8")
        self.icmp_timeout_seconds = float(os.getenv("ICMP_TIMEOUT_SECONDS", "1.0"))
        
        # SNMP settings
        self.snmp_host = os.getenv("SNMP_HOST", "")
        self.snmp_port = int(os.getenv("SNMP_PORT", "161"))
        self.snmp_timeout_seconds = float(os.getenv("SNMP_TIMEOUT_SECONDS", "1.2"))
        self.snmp_community = os.getenv("SNMP_COMMUNITY", "")
        
        # NetFlow settings
        self.netflow_port = int(os.getenv("NETFLOW_PORT", "2055"))
        
        # Storage settings
        self.metrics_db_path = os.getenv("METRICS_DB_PATH", "data/metrics.db")
        self.auth_db_path = os.getenv("AUTH_DB_PATH", "data/auth.db")
        self.sqlite_retention_seconds = int(os.getenv("SQLITE_RETENTION_SECONDS", "86400"))
        
        # Authentication settings
        self.session_secret_key = os.getenv("SESSION_SECRET_KEY", "")
        self.session_cookie_name = os.getenv("SESSION_COOKIE_NAME", "system_trace_session")
        self.session_max_age_seconds = os.getenv("SESSION_MAX_AGE_SECONDS", "3600")
        self.session_cookie_samesite = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
        self.session_cookie_secure = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
        
        # Remember me settings
        self.remember_cookie_name = os.getenv("REMEMBER_COOKIE_NAME", "system_trace_remember")
        self.remember_max_age_seconds = os.getenv("REMEMBER_MAX_AGE_SECONDS", "604800")


settings = Settings()
