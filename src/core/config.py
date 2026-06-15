"""
Environment configuration management for multiple deployment environments
Supports local development, preview, and production environments
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

class Config:
    """Configuration manager for environment-specific settings"""
    
    def __init__(self):
        self.environment = os.getenv("APP_ENV", "local")
        self.postgres_url: Optional[str] = None
        self.openai_api_key: Optional[str] = None
        self.openai_model: str = "gpt-5-nano"  # Default model
        self.cors_origins: list = []
        self._load_environment()
    
    def _load_environment(self):
        """Load environment variables based on APP_ENV setting"""
        # First check if we're running in a deployed environment (Render sets these directly)
        self.postgres_url = os.environ.get("POSTGRES_URL")
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.openai_model = os.environ.get("OPENAI_MODEL", "gpt-5-nano")  # Default to gpt-5-nano if not set
        
        # Always load .env file to pick up all vars (SMTP, etc.)
        env_file_map = {
            "local": ".env.local",
            "preview": ".env.preview",
            "production": ".env.prod",
            "prod": ".env.prod"
        }

        # Get the project root directory (3 levels up from this file)
        project_root = Path(__file__).parent.parent.parent

        # Try to load the specific environment file
        env_file = env_file_map.get(self.environment, ".env")
        env_path = project_root / env_file

        if env_path.exists():
            print(f"[Config] Loading environment from: {env_file}")
            load_dotenv(env_path, override=False)  # Don't override existing env vars
        else:
            # Fallback to .env if specific file doesn't exist
            default_env_path = project_root / ".env"
            if default_env_path.exists():
                print(f"[Config] {env_file} not found, loading default .env")
                load_dotenv(default_env_path, override=False)
            else:
                print(f"[Config] No environment file found, using system environment variables only")

        # Reload core vars after dotenv
        if not self.postgres_url:
            self.postgres_url = os.environ.get("POSTGRES_URL")
            self.openai_api_key = os.environ.get("OPENAI_API_KEY")
            self.openai_model = os.environ.get("OPENAI_MODEL", "gpt-5-nano")
        
        # Validate required configuration
        if not self.postgres_url:
            raise ValueError(f"POSTGRES_URL is required for environment: {self.environment}")
        
        # Set CORS origins based on environment
        if self.environment == "local":
            self.cors_origins = [
                "http://localhost:3000",      # Next.js frontend (typical port)
                "http://localhost:3001",      # Next.js frontend (alternate port)
                "http://localhost:8000",      # Local frontend (your requested port)
                "http://127.0.0.1:3000",     # Alternative localhost
                "http://127.0.0.1:8000",     # Alternative localhost (your port)
            ]
        elif self.environment == "preview":
            self.cors_origins = [
                "*",  # Allow all origins for preview environment
                # Or be more specific if you prefer:
                # "https://mag-nextjs-fastapi-git-preview-gpt-socials-projects.vercel.app",
                # "https://*.vercel.app",  # All Vercel preview deployments
            ]
        else:  # production
            allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
            if allowed_origins_env and allowed_origins_env != "*":
                self.cors_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
            else:
                self.cors_origins = [
                    "https://vibelevel.ai",
                    "https://www.vibelevel.ai",
                ]
        
        # Log configuration (without sensitive data)
        print(f"[Config] Environment: {self.environment}")
        print(f"[Config] Database URL: {self.postgres_url[:50]}..." if self.postgres_url else "[Config] No database URL")
        print(f"[Config] CORS origins: {self.cors_origins}")
    
    def get_database_url(self) -> str:
        """Get the database URL for the current environment"""
        if not self.postgres_url:
            raise ValueError("Database URL not configured")
        return self.postgres_url
    
    def get_openai_api_key(self) -> Optional[str]:
        """Get the OpenAI API key"""
        return self.openai_api_key
    
    def get_openai_model(self) -> str:
        """Get the OpenAI model name"""
        return self.openai_model
    
    def get_cors_origins(self) -> list:
        """Get CORS origins for the current environment"""
        return self.cors_origins

# Create a singleton instance
config = Config()