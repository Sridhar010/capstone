#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.pids"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

if [ ! -f "$PID_FILE" ]; then
    echo -e "${YELLOW}No services running (no .pids file found).${NC}"
    exit 0
fi

echo -e "${YELLOW}Stopping services...${NC}"
while IFS= read -r pid; do
    if kill "$pid" 2>/dev/null; then
        echo -e "${GREEN}  Stopped PID $pid${NC}"
    fi
done < "$PID_FILE"
rm -f "$PID_FILE"
echo -e "${GREEN}Done.${NC}"
