#!/bin/bash
# ============================================================
#  macOS 应用修复工具 — 双击即可启动
#  在 Finder 中双击此文件，一切自动完成
# ============================================================

# 定位到脚本所在目录（兼容从任何位置启动）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # 无颜色

clear
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}    🛠️  ${GREEN}macOS 应用修复工具${NC}                    ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    自动修复 \"应用已损坏\" 问题              ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ---- 1. 检查 Python3 ----
echo -e "${BLUE}[1/4]${NC} 检查 Python3..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 未找到 python3！${NC}"
    echo -e "   请先安装 Python 3: ${YELLOW}https://www.python.org/downloads/${NC}"
    echo ""
    echo "按任意键关闭..."
    read -n 1
    exit 1
fi
PYTHON_VER=$(python3 --version 2>&1)
echo -e "   ${GREEN}✅ $PYTHON_VER${NC}"

# ---- 2. 配置虚拟环境和依赖 ----
echo -e "${BLUE}[2/4]${NC} 配置运行环境..."
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo -e "   📦 正在创建虚拟环境..."
    python3 -m venv "$SCRIPT_DIR/venv"
    echo -e "   ${GREEN}✅ 虚拟环境就绪${NC}"
else
    echo -e "   ${GREEN}✅ 虚拟环境已存在${NC}"
fi

# 安装 Flask
if ! "$SCRIPT_DIR/venv/bin/python3" -c "import flask" &> /dev/null 2>&1; then
    echo -e "   📦 正在安装 Flask..."
    "$SCRIPT_DIR/venv/bin/pip" install flask --quiet
    echo -e "   ${GREEN}✅ Flask 安装完成${NC}"
else
    echo -e "   ${GREEN}✅ Flask 已就绪${NC}"
fi

# ---- 3. 获取管理员权限 ----
echo -e "${BLUE}[3/4]${NC} 获取管理员权限..."

if sudo -n true 2>/dev/null; then
    # 已有 sudo 权限（例如最近输入过密码）
    echo -e "   ${GREEN}✅ 管理员权限就绪${NC}"
    USE_SUDO=true
else
    echo -e "   ${YELLOW}请在下方输入您的开机密码（输入时不会显示字符，输完回车即可）：${NC}"
    echo ""
    if sudo -v 2>/dev/null; then
        echo ""
        echo -e "   ${GREEN}✅ 管理员权限就绪${NC}"
        USE_SUDO=true
    else
        echo ""
        echo -e "   ${YELLOW}⚠️  未获取管理员权限，部分修复功能可能受限${NC}"
        USE_SUDO=false
    fi
fi

# ---- 4. 启动服务 ----
echo -e "${BLUE}[4/4]${NC} 启动修复工具..."
echo ""

PORT=5555
URL="http://localhost:$PORT"

# 检查端口是否被占用
if lsof -i:$PORT -sTCP:LISTEN &> /dev/null; then
    echo -e "   ${YELLOW}⚠️  端口 $PORT 已被占用，正在释放...${NC}"
    lsof -ti:$PORT | xargs kill -9 2>/dev/null
    sleep 1
fi

# 清理函数 — 关闭终端时自动停止服务
cleanup() {
    echo ""
    echo -e "${YELLOW}正在关闭服务...${NC}"
    if [ ! -z "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null
        wait $SERVER_PID 2>/dev/null
    fi
    echo -e "${GREEN}✅ 服务已关闭，再见！${NC}"
    exit 0
}
trap cleanup EXIT INT TERM

# 启动 Flask 服务
if [ "$USE_SUDO" = true ]; then
    sudo "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/app.py" &
else
    "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/app.py" &
fi
SERVER_PID=$!

# 等待服务启动
echo -e "   等待服务启动..."
for i in $(seq 1 15); do
    if curl -s "$URL" > /dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

# 检查服务是否成功启动
if curl -s "$URL" > /dev/null 2>&1; then
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ 服务启动成功！${NC}"
    echo -e "${GREEN}  🌐 浏览器将自动打开: ${URL}${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}  💡 提示：关闭此终端窗口即可停止服务${NC}"
    echo ""

    # 自动打开浏览器
    open "$URL"
else
    echo -e "${RED}❌ 服务启动失败！${NC}"
    echo -e "   请检查上方的错误信息。"
    echo ""
    echo "按任意键关闭..."
    read -n 1
    exit 1
fi

# 保持终端窗口打开，显示服务日志
wait $SERVER_PID
