import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# ── LLM ────────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# ANTHROPIC_BASE_URL is read automatically by the Anthropic SDK from the env var
# Set it in .env only if using a custom gateway (e.g. LLM proxy)
LLM_MODEL = os.getenv("LLM_MODEL", "global.anthropic.claude-sonnet-4-6")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# ── FastAPI service ────────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ── MCP server scripts (stdio transport) ──────────────────────────────────────
MCP_SERVERS_DIR = BASE_DIR / "mcp_servers"
APPLICANT_DB_SERVER = str(MCP_SERVERS_DIR / "applicant_db_server.py")
RISK_RULES_SERVER = str(MCP_SERVERS_DIR / "risk_rules_server.py")
DECISION_SYNTHESIS_SERVER = str(MCP_SERVERS_DIR / "decision_synthesis_server.py")
NOTIFICATION_SERVER = str(MCP_SERVERS_DIR / "notification_server.py")

# ── Streamlit ──────────────────────────────────────────────────────────────────
STREAMLIT_API_URL = os.getenv("STREAMLIT_API_URL", f"http://localhost:{API_PORT}")

# ── Logging — uvicorn requires lowercase level names ──────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").lower()
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
