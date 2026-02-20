#!/bin/bash
# Phoenix Guardian V5 — Demo Startup Checklist
# Run this 10 minutes before presenting
# Usage: bash scripts/demo_start.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}🛡️  Phoenix Guardian V5 — Demo Startup${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

ALL_OK=true

# 1. Check backend is running
echo -n "Backend running... "
if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
  echo -e "${GREEN}✅${NC}"
else
  echo -e "${RED}❌ Start with: uvicorn phoenix_guardian.api.main:app --reload${NC}"
  ALL_OK=false
fi

# 2. Check frontend is running
echo -n "Frontend running... "
if curl -s http://localhost:3000 > /dev/null 2>&1; then
  echo -e "${GREEN}✅${NC}"
else
  echo -e "${YELLOW}⚠️  Not running (cd phoenix-ui && npm start)${NC}"
fi

# 3. Check Redis
echo -n "Redis running... "
if redis-cli ping > /dev/null 2>&1; then
  echo -e "${GREEN}✅${NC}"
else
  echo -e "${YELLOW}⚠️  Redis not running — Ghost Protocol uses in-memory fallback${NC}"
fi

# 4. Re-seed ghost protocol
echo -n "Seeding Ghost Protocol... "
if python scripts/seed_ghost_protocol.py > /dev/null 2>&1; then
  echo -e "${GREEN}✅${NC}"
else
  echo -e "${YELLOW}⚠️  Seed script error${NC}"
fi

# 5. Check all 3 agent health endpoints
for agent in treatment-shadow silent-voice zebra-hunter; do
  echo -n "Agent $agent... "
  STATUS=$(curl -s http://localhost:8000/api/v1/$agent/health | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null)
  if [ "$STATUS" = "healthy" ]; then
    echo -e "${GREEN}✅${NC}"
  else
    echo -e "${RED}❌ Not healthy: $STATUS${NC}"
    ALL_OK=false
  fi
done

# 6. Pre-warm caches
echo ""
echo -n "Pre-warming caches... "
if python scripts/demo_warmup.py > /dev/null 2>&1; then
  echo -e "${GREEN}✅ Done${NC}"
else
  echo -e "${YELLOW}⚠️  Warmup script failed${NC}"
fi

# 7. Summary
echo ""
if [ "$ALL_OK" = true ]; then
  echo -e "${GREEN}🚀 All checks passed. Opening demo...${NC}"
else
  echo -e "${YELLOW}⚠️  Some checks failed. Fix issues before presenting.${NC}"
fi

echo ""
echo "Demo URL: http://localhost:3000/v5-dashboard"
echo ""
echo -e "${CYAN}Demo order:${NC}"
echo "  1. Dashboard overview (30 sec)"
echo "  2. Treatment Shadow — Rajesh Kumar (45 sec)"
echo "  3. Silent Voice — Lakshmi Devi + toggle (45 sec)"
echo "  4. Zebra Hunter — Priya Sharma + timeline (45 sec)"
echo "  5. Zebra Hunter — Arjun Nair + Ghost Protocol (30 sec)"
echo "  6. Closing line (15 sec)"
echo ""
echo -e "${CYAN}TOTAL: 3 minutes 30 seconds${NC}"
echo ""
