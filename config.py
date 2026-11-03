import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# LLM
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# FastAPI service
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# MCP server ports
APPLICANT_DB_PORT = int(os.getenv("APPLICANT_DB_PORT", "8001"))
RISK_RULES_PORT = int(os.getenv("RISK_RULES_PORT", "8002"))
DECISION_SYNTHESIS_PORT = int(os.getenv("DECISION_SYNTHESIS_PORT", "8003"))
NOTIFICATION_PORT = int(os.getenv("NOTIFICATION_PORT", "8004"))

# MCP server scripts (for stdio transport)
MCP_SERVERS_DIR = BASE_DIR / "mcp_servers"
APPLICANT_DB_SERVER = str(MCP_SERVERS_DIR / "applicant_db_server.py")
RISK_RULES_SERVER = str(MCP_SERVERS_DIR / "risk_rules_server.py")
DECISION_SYNTHESIS_SERVER = str(MCP_SERVERS_DIR / "decision_synthesis_server.py")
NOTIFICATION_SERVER = str(MCP_SERVERS_DIR / "notification_server.py")

# Streamlit
STREAMLIT_API_URL = os.getenv("STREAMLIT_API_URL", f"http://localhost:{API_PORT}")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
