#!/bin/bash
#===============================================================================
#  Alibaba Cloud Model Studio (DashScope) Client - Automated Installer
#  Region: ap-southeast-1 (International)
#===============================================================================

set -e

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
INSTALL_DIR="${HOME}/.dashscope"
VENV_DIR="${INSTALL_DIR}/venv"
CONFIG_FILE="${INSTALL_DIR}/config.env"
SAMPLE_SCRIPT="${INSTALL_DIR}/sample_client.py"
LOG_FILE="${INSTALL_DIR}/install.log"
PYTHON_MIN_VERSION="3.8"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────
log_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()    { echo -e "\n${BLUE}══════════════════════════════════════${NC}"; echo -e "${BLUE}  $1${NC}"; echo -e "${BLUE}══════════════════════════════════════${NC}"; }

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# ─────────────────────────────────────────────
# STEP 0: SYSTEM DETECTION
# ─────────────────────────────────────────────
log_step "Step 0: System Detection"

OS_TYPE="$(uname -s)"
case "${OS_TYPE}" in
    Linux*)     OS="linux";;
    Darwin*)    OS="macos";;
    MINGW*|MSYS*|CYGWIN*) OS="windows";;
    *)          OS="unknown";;
esac

log_info "Detected OS: ${OS}"
log_info "Architecture: $(uname -m)"

# ─────────────────────────────────────────────
# STEP 1: INSTALL PYTHON
# ─────────────────────────────────────────────
log_step "Step 1: Checking Python Installation"

PYTHON_CMD=""

if check_command python3; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
elif check_command python; then
    PYTHON_CMD="python"
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
else
    log_warn "Python not found. Installing..."

    case "${OS}" in
        linux)
            if check_command apt-get; then
                sudo apt-get update -qq
                sudo apt-get install -y python3 python3-pip python3-venv
            elif check_command yum; then
                sudo yum install -y python3 python3-pip
            elif check_command dnf; then
                sudo dnf install -y python3 python3-pip
            elif check_command apk; then
                sudo apk add python3 py3-pip
            else
                log_error "Unsupported package manager. Install Python ${PYTHON_MIN_VERSION}+ manually."
                exit 1
            fi
            ;;
        macos)
            if check_command brew; then
                brew install python@3.11
            else
                log_error "Install Homebrew first: https://brew.sh"
                exit 1
            fi
            ;;
        windows)
            log_error "Use: winget install Python.Python.3.11"
            exit 1
            ;;
    esac

    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
fi

log_info "Using: ${PYTHON_CMD} (version ${PYTHON_VERSION})"

# Validate version
if (( $(echo "$PYTHON_VERSION < $PYTHON_MIN_VERSION" | bc -l 2>/dev/null || echo "0") )); then
    log_error "Python ${PYTHON_MIN_VERSION}+ required. Found: ${PYTHON_VERSION}"
    exit 1
fi

# ─────────────────────────────────────────────
# STEP 2: CREATE PROJECT DIRECTORY
# ─────────────────────────────────────────────
log_step "Step 2: Creating Project Directory"

mkdir -p "${INSTALL_DIR}"
log_info "Created: ${INSTALL_DIR}"

# ─────────────────────────────────────────────
# STEP 3: CREATE VIRTUAL ENVIRONMENT
# ─────────────────────────────────────────────
log_step "Step 3: Creating Virtual Environment"

if [ ! -d "${VENV_DIR}" ]; then
    ${PYTHON_CMD} -m venv "${VENV_DIR}"
    log_info "Virtual environment created at: ${VENV_DIR}"
else
    log_info "Virtual environment already exists. Skipping."
fi

# Activate
source "${VENV_DIR}/bin/activate" 2>/dev/null || . "${VENV_DIR}/Scripts/activate"

# ─────────────────────────────────────────────
# STEP 4: INSTALL PACKAGES
# ─────────────────────────────────────────────
log_step "Step 4: Installing Required Packages"

pip install --upgrade pip --quiet

PACKAGES=(
    "dashscope>=1.20.0"
    "openai>=1.0.0"
    "requests>=2.31.0"
    "python-dotenv>=1.0.0"
    "rich>=13.0.0"
)

for pkg in "${PACKAGES[@]}"; do
    log_info "Installing: ${pkg}"
    pip install "${pkg}" --quiet
done

log_info "All packages installed successfully!"

# ─────────────────────────────────────────────
# STEP 5: CREATE CONFIGURATION FILE
# ─────────────────────────────────────────────
log_step "Step 5: Creating Configuration"

cat > "${CONFIG_FILE}" << 'EOF'
# ═══════════════════════════════════════════════
# Alibaba Cloud Model Studio - Configuration
# Region: ap-southeast-1 (Singapore)
# ═══════════════════════════════════════════════

# Your API Key (Get from: https://modelstudio.console.alibabacloud.com)
DASHSCOPE_API_KEY=sk-your-api-key-here

# Base URL for International Region
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1

# Default Model
DASHSCOPE_MODEL=qwen-plus

# Optional: Proxy settings
# HTTP_PROXY=http://proxy:port
# HTTPS_PROXY=http://proxy:port
EOF

log_info "Config file created: ${CONFIG_FILE}"

# ─────────────────────────────────────────────
# STEP 6: CREATE SAMPLE CLIENT SCRIPT
# ─────────────────────────────────────────────
log_step "Step 6: Creating Sample Client Script"

cat > "${SAMPLE_SCRIPT}" << 'PYTHON_EOF'
#!/usr/bin/env python3
"""
Alibaba Cloud Model Studio - Automated Client
Region: ap-southeast-1 (Singapore)
"""

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    from openai import OpenAI
    from rich.console import Console
    from rich.markdown import Markdown
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)

# ─── Configuration ───────────────────────────
CONFIG_PATH = Path(__file__).parent / "config.env"
load_dotenv(CONFIG_PATH)

API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
MODEL = os.getenv("DASHSCOPE_MODEL", "qwen-plus")

console = Console()

# ─── Client Setup ────────────────────────────
def get_client() -> OpenAI:
    if not API_KEY or API_KEY == "sk-your-api-key-here":
        console.print("[red]ERROR: Set your API key in config.env[/red]")
        sys.exit(1)
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)

# ─── Chat Function ───────────────────────────
def chat(messages: list, model: str = MODEL, stream: bool = False):
    client = get_client()

    if stream:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True
        )
        full_response = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                print(content, end="", flush=True)
        print()
        return full_response
    else:
        response = client.chat.completions.create(
            model=model,
            messages=messages
        )
        return response.choices[0].message.content

# ─── Interactive Mode ────────────────────────
def interactive_mode():
    console.print("\n[bold blue]═══ Alibaba Cloud Model Studio Client ═══[/bold blue]")
    console.print(f"Model: [green]{MODEL}[/green] | Region: [green]ap-southeast-1[/green]")
    console.print("Type 'quit' to exit, 'clear' to reset history\n")

    messages = [{"role": "system", "content": "You are a helpful assistant."}]

    while True:
        try:
            user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if user_input.lower() in ('quit', 'exit', 'q'):
            break
        elif user_input.lower() == 'clear':
            messages = [{"role": "system", "content": "You are a helpful assistant."}]
            console.print("[yellow]History cleared.[/yellow]")
            continue
        elif not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        console.print("[bold green]AI:[/bold green] ", end="")
        try:
            response = chat(messages, stream=True)
            messages.append({"role": "assistant", "content": response})
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            messages.pop()  # Remove failed user message

# ─── Single Query Mode ───────────────────────
def single_query(prompt: str):
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ]
    response = chat(messages)
    console.print(Markdown(response))

# ─── Main ────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        single_query(query)
    else:
        interactive_mode()
PYTHON_EOF

chmod +x "${SAMPLE_SCRIPT}"
log_info "Sample client created: ${SAMPLE_SCRIPT}"

# ─────────────────────────────────────────────
# STEP 7: CREATE REQUIREMENTS FILE
# ─────────────────────────────────────────────
log_step "Step 7: Creating requirements.txt"

cat > "${INSTALL_DIR}/requirements.txt" << 'EOF'
dashscope>=1.20.0
openai>=1.0.0
requests>=2.31.0
python-dotenv>=1.0.0
rich>=13.0.0
EOF

log_info "Created: ${INSTALL_DIR}/requirements.txt"

# ─────────────────────────────────────────────
# STEP 8: CREATE ACTIVATION HELPER
# ─────────────────────────────────────────────
log_step "Step 8: Creating Activation Helper"

cat > "${INSTALL_DIR}/activate.sh" << EOF
#!/bin/bash
source "${VENV_DIR}/bin/activate"
export DASHSCOPE_API_KEY=\$(grep DASHSCOPE_API_KEY "${CONFIG_FILE}" | cut -d'=' -f2)
echo "✅ DashScope environment activated"
echo "   Run: python ${SAMPLE_SCRIPT}"
EOF

chmod +x "${INSTALL_DIR}/activate.sh"

# Add to shell profile
SHELL_RC=""
if [ -f "${HOME}/.bashrc" ]; then
    SHELL_RC="${HOME}/.bashrc"
elif [ -f "${HOME}/.zshrc" ]; then
    SHELL_RC="${HOME}/.zshrc"
fi

if [ -n "${SHELL_RC}" ]; then
    if ! grep -q "dashscope" "${SHELL_RC}" 2>/dev/null; then
        echo "" >> "${SHELL_RC}"
        echo "# Alibaba Cloud DashScope" >> "${SHELL_RC}"
        echo "alias dashscope='source ${INSTALL_DIR}/activate.sh'" >> "${SHELL_RC}"
        log_info "Added alias 'dashscope' to ${SHELL_RC}"
    fi
fi

# ─────────────────────────────────────────────
# STEP 9: VERIFY INSTALLATION
# ─────────────────────────────────────────────
log_step "Step 9: Verification"

source "${VENV_DIR}/bin/activate"

echo ""
echo "Package versions:"
pip list 2>/dev/null | grep -E "(dashscope|openai|requests|python-dotenv|rich)" | while read line; do
    echo "  ✅ ${line}"
done

# ─────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────
log_step "✅ Installation Complete!"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  📁 Install Directory : ${INSTALL_DIR}${NC}"
echo -e "${GREEN}  ⚙️  Config File       : ${CONFIG_FILE}${NC}"
echo -e "${GREEN}  🐍 Client Script     : ${SAMPLE_SCRIPT}${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}NEXT STEPS:${NC}"
echo ""
echo "  1. Set your API Key:"
echo -e "     ${BLUE}nano ${CONFIG_FILE}${NC}"
echo ""
echo "  2. Activate environment:"
echo -e "     ${BLUE}source ${INSTALL_DIR}/activate.sh${NC}"
echo ""
echo "  3. Run the client:"
echo -e "     ${BLUE}python ${SAMPLE_SCRIPT}${NC}"
echo ""
echo "  4. Single query:"
echo -e "     ${BLUE}python ${SAMPLE_SCRIPT} \"What is AI?\"${NC}"
echo ""
echo -e "${YELLOW}Get your API Key at:${NC}"
echo -e "  https://modelstudio.console.alibabacloud.com/ap-southeast-1/?tab=dashboard#/api-key"
echo ""
