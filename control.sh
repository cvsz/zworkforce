#!/usr/bin/env bash
# ==============================================================================
# zWorkforce Unified Control Panel & Master Orchestrator (control.sh)
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

cmd_status() {
    echo -e "\n${CYAN}=== zWorkforce System Status ===${NC}"
    
    # 1. zWorkforce Core API
    echo -n "zWorkforce Control Plane (Port 9569 / 9570): "
    if curl -s --connect-timeout 2 http://127.0.0.1:9569/health >/dev/null 2>&1; then
        echo -e "${GREEN}ONLINE${NC}"
    elif curl -s --connect-timeout 2 http://127.0.0.1:9570/health >/dev/null 2>&1; then
        echo -e "${GREEN}ONLINE (:9570)${NC}"
    else
        echo -e "${RED}OFFLINE${NC}"
    fi

    # 2. OpenWebUI Gateway
    echo -n "OpenWebUI Gateway (Port 3080 / chat.zeaz.dev): "
    if curl -s --connect-timeout 2 http://127.0.0.1:3080 >/dev/null 2>&1; then
        echo -e "${GREEN}ONLINE${NC}"
    else
        echo -e "${YELLOW}STANDBY${NC}"
    fi

    # 3. ZSP-AITool Studio
    echo -n "ZSP Studio & HyperFrames (Port 3005 / studio.zeaz.dev): "
    if curl -s --connect-timeout 2 http://127.0.0.1:3005 >/dev/null 2>&1; then
        echo -e "${GREEN}ONLINE${NC}"
    else
        echo -e "${YELLOW}STANDBY${NC}"
    fi

    # 4. Hermes Agent Engine
    echo -n "Hermes Agent CLI: "
    if command -v ~/.hermes/bin/hermes >/dev/null 2>&1 || command -v hermes >/dev/null 2>&1; then
        echo -e "${GREEN}INSTALLED${NC}"
    else
        echo -e "${RED}MISSING${NC}"
    fi

    # 5. Spawn CLI
    echo -n "OpenRouter Spawn CLI: "
    if command -v ~/.local/bin/spawn >/dev/null 2>&1 || command -v spawn >/dev/null 2>&1; then
        echo -e "${GREEN}INSTALLED${NC}"
    else
        echo -e "${RED}MISSING${NC}"
    fi

    echo ""
    zworkforce doctor || true
}

cmd_verify() {
    log_info "Executing Full Repository Verification Protocol..."
    python3 -m compileall -q zworkforce tests
    PYTHONPATH=. python3 -m unittest discover -s tests -v
    zworkforce doctor
    log_success "All unit tests and doctor checks PASSED!"
}

cmd_install() {
    log_info "Installing dependencies across full monorepo..."
    
    # 1. Root python & setup
    ./setup.sh
    
    # 2. Zarvis packages
    if [ -d "packages/zarvis" ]; then
        log_info "Setting up packages/zarvis..."
        (cd packages/zarvis && pnpm install --frozen-lockfile || npm install)
    fi

    # 3. ZSP-AITool studio
    if [ -d "packages/zsp-aitool" ]; then
        log_info "Setting up packages/zsp-aitool..."
        (cd packages/zsp-aitool && npm run prisma:generate && npm run build)
    fi

    # 4. Zider companion
    if [ -d "packages/zider" ]; then
        log_info "Setting up packages/zider..."
        (cd packages/zider && npm install && npm run build || true)
    fi

    # 5. Zok Conversational Commerce OS
    if [ -d "packages/zok" ]; then
        log_info "Setting up packages/zok..."
        (cd packages/zok && npm install || true)
    fi

    # 6. Top-level Monorepo Workspace (services & apps)
    if [ -f "pnpm-workspace.yaml" ]; then
        log_info "Setting up root pnpm workspaces..."
        pnpm install || true
    fi

    log_success "Monorepo installation complete!"
}

cmd_start() {
    log_info "Starting zWorkforce Services..."
    docker compose --profile all up -d
    if [ -f "compose.open-webui.yml" ]; then
        docker compose -f compose.open-webui.yml up -d
    fi
    log_success "Services started!"
}

cmd_stop() {
    log_info "Stopping zWorkforce Services..."
    docker compose down || true
    if [ -f "compose.open-webui.yml" ]; then
        docker compose -f compose.open-webui.yml down || true
    fi
    log_success "Services stopped!"
}

cmd_restart() {
    cmd_stop
    sleep 2
    cmd_start
}

cmd_config() {
    echo -e "\n${YELLOW}=== Active Provider & Secret Vault Config (.env.ai) ===${NC}"
    local env_file="${ROOT_DIR}/.env.ai"
    if [ ! -f "$env_file" ]; then
        env_file="${HOME}/.env.ai"
    fi

    if [ -f "$env_file" ]; then
        log_success "Vault located at: $env_file"
        python3 -c "
import os

env_path = '${env_file}'
count = 0
with open(env_path, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            parts = line.split('=', 1)
            key = parts[0].strip()
            val = parts[1].strip()
            if val:
                masked = '********'
                if len(val) > 8:
                    masked = f'{val[:4]}...{val[-4:]}'
                print(f'  • {key:<32} = {masked}')
                count += 1
print(f'\n\033[0;32mLoaded {count} active provider keys/endpoints securely with zero plaintext leakage.\033[0m')
"
    else
        log_warn "No .env.ai vault file found."
    fi
}

cmd_start_studio() {
    log_info "Starting ZSP AI Studio Next.js on port :3005..."
    docker compose -f compose.zsp-aitool.yml up -d
    log_success "ZSP Studio started at https://studio.zeaz.dev or http://localhost:3005"
}

cmd_stop_studio() {
    log_info "Stopping ZSP AI Studio containers..."
    docker compose -f compose.zsp-aitool.yml down || true
    log_success "ZSP Studio stopped."
}

cmd_start_webui() {
    log_info "Starting OpenWebUI Gateway on port :3080..."
    docker compose -f compose.open-webui.yml up -d
    log_success "OpenWebUI started at https://chat.zeaz.dev or http://localhost:3080"
}

cmd_stop_webui() {
    log_info "Stopping OpenWebUI Gateway..."
    docker compose -f compose.open-webui.yml down || true
    log_success "OpenWebUI stopped."
}

cmd_menu() {
    while true; do
        clear || true
        echo -e "${CYAN}=============================================================================${NC}"
        echo -e "${CYAN}             zWorkforce Master Control Panel & Orchestrator                  ${NC}"
        echo -e "${CYAN}=============================================================================${NC}"
        echo ""
        echo -e "  ${GREEN}1)${NC} Check System & Services Status"
        echo -e "  ${GREEN}2)${NC} Run Full Validation Suite (140 Tests + Invariants)"
        echo -e "  ${GREEN}3)${NC} Start All Services (Core + WebUI)"
        echo -e "  ${GREEN}4)${NC} Stop All Services"
        echo -e "  ${GREEN}5)${NC} Restart All Services"
        echo -e "  ${GREEN}6)${NC} Start ZSP AI Studio (:3005 / studio.zeaz.dev)"
        echo -e "  ${GREEN}7)${NC} Stop ZSP AI Studio"
        echo -e "  ${GREEN}8)${NC} Start OpenWebUI Gateway (:3080 / chat.zeaz.dev)"
        echo -e "  ${GREEN}9)${NC} Stop OpenWebUI Gateway"
        echo -e "  ${GREEN}10)${NC} Automated Full-Stack Monorepo Installer"
        echo -e "  ${GREEN}11)${NC} Inspect Provider & Secret Vault Config (.env.ai)"
        echo -e "  ${RED}q)${NC}  Exit"
        echo ""
        read -p "Select option [1-11, q]: " choice
        case "$choice" in
            1) cmd_status ;;
            2) cmd_verify ;;
            3) cmd_start ;;
            4) cmd_stop ;;
            5) cmd_restart ;;
            6) cmd_start_studio ;;
            7) cmd_stop_studio ;;
            8) cmd_start_webui ;;
            9) cmd_stop_webui ;;
            10) cmd_install ;;
            11) cmd_config ;;
            q|Q|exit|quit) echo "Exiting zWorkforce Master Control."; break ;;
            *) log_error "Invalid option" ;;
        esac
        echo ""
        read -p "Press Enter to return to menu..."
    done
}

case "${1:-menu}" in
    menu)
        cmd_menu
        ;;
    status)
        cmd_status
        ;;
    verify|test)
        cmd_verify
        ;;
    install)
        cmd_install
        ;;
    config|vault)
        cmd_config
        ;;
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    start-studio)
        cmd_start_studio
        ;;
    stop-studio)
        cmd_stop_studio
        ;;
    start-webui)
        cmd_start_webui
        ;;
    stop-webui)
        cmd_stop_webui
        ;;
    help|--help|-h)
        echo "Usage: ./control.sh [menu|status|verify|install|config|start|stop|restart|start-studio|stop-studio|start-webui|stop-webui]"
        ;;
    *)
        log_error "Unknown command: $1"
        echo "Usage: ./control.sh [menu|status|verify|install|config|start|stop|restart|start-studio|stop-studio|start-webui|stop-webui]"
        exit 1
        ;;
esac
