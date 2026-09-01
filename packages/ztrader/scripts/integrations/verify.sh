#!/usr/bin/env bash
# // ZeaZDev [Verification Script] //
# // Project: Auto Bot Trader i18n //
# // Version: 1.0.0 (Omega Scaffolding) //
# // Author: ZeaZDev Meta-Intelligence (Generated) //
# // --- DO NOT EDIT HEADER --- //

set -e

echo "=== ZeaZDev-ABTPi18n Scaffolding Verification ==="
echo ""

# Check file structure
echo "[1/5] Checking file structure..."
required_files=(
    ".env.example"
    "docker-compose.yml"
    "package.json"
    "install.sh"
    "apps/backend/Dockerfile"
    "apps/backend/main.py"
    "apps/backend/requirements.txt"
    "apps/backend/worker.py"
    "apps/backend/prisma/schema.prisma"
    "apps/frontend/Dockerfile"
    "apps/frontend/package.json"
    "apps/frontend/next.config.js"
    "apps/frontend/tsconfig.json"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "  ❌ Missing: $file"
        exit 1
    fi
done
echo "  ✅ All required files present"

# Check Python syntax
echo "[2/5] Checking Python syntax..."
python_files=(
    "apps/backend/main.py"
    "apps/backend/worker.py"
    "apps/backend/src/security/crypto_service.py"
    "apps/backend/src/trading/strategy_interface.py"
    "apps/backend/src/trading/bot_runner.py"
)
for file in "${python_files[@]}"; do
    python3 -m py_compile "$file" || { echo "  ❌ Syntax error in $file"; exit 1; }
done
echo "  ✅ Python syntax valid"

# Check headers
echo "[3/5] Checking required headers..."
header_pattern="// ZeaZDev"
for file in apps/backend/main.py apps/frontend/next.config.js; do
    if ! grep -q "$header_pattern" "$file"; then
        echo "  ❌ Missing header in $file"
        exit 1
    fi
done
echo "  ✅ Headers present"

# Check .env.example content
echo "[4/5] Checking .env.example variables..."
required_vars=(
    "POSTGRES_USER"
    "POSTGRES_PASS"
    "POSTGRES_DB"
    "DATABASE_URL"
    "REDIS_URL"
    "ENCRYPTION_KEY"
    "FRONTEND_URL"
    "NEXT_PUBLIC_BACKEND_URL"
)
for var in "${required_vars[@]}"; do
    if ! grep -q "^$var=" ".env.example"; then
        echo "  ❌ Missing variable: $var"
        exit 1
    fi
done
echo "  ✅ All environment variables defined"

# Check Prisma models
echo "[5/5] Checking Prisma schema models..."
required_models=(
    "model User"
    "model ExchangeKey"
    "model Strategy"
    "model BotRun"
    "model TradeLog"
    "model RentalContract"
    "model PromptPayTopup"
    "model ModuleRegistration"
    "model TelegramLink"
)
for model in "${required_models[@]}"; do
    if ! grep -q "$model" "apps/backend/prisma/schema.prisma"; then
        echo "  ❌ Missing: $model"
        exit 1
    fi
done
echo "  ✅ All Prisma models defined"

echo ""
echo "=== ✅ Verification Complete ==="
echo "All scaffolding components are properly configured!"
echo ""
echo "Next steps:"
echo "  1. Run ./install.sh to set up the environment"
echo "  2. Access Frontend: http://localhost:3000/en/dashboard"
echo "  3. Access Backend API docs: http://localhost:8000/docs"
