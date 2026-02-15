#!/bin/bash
# macOS 应用修复工具 - 启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================"
echo "  macOS 应用修复工具"
echo "======================================"
echo ""

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3。"
    exit 1
fi

# 创建虚拟环境（如不存在）
if [ ! -d "venv" ]; then
    echo "📦 正在创建虚拟环境..."
    python3 -m venv venv
    echo "✅ 虚拟环境创建完成"
fi

# 激活虚拟环境
source "$SCRIPT_DIR/venv/bin/activate"

# 安装依赖
if ! python3 -c "import flask" &> /dev/null 2>&1; then
    echo "📦 正在安装 Flask..."
    pip install flask --quiet
    echo "✅ Flask 安装完成"
fi

echo ""

PORT=5555
URL="http://localhost:$PORT"

# 清理函数
cleanup() {
    echo ""
    echo "正在关闭服务..."
    if [ ! -z "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null
        wait $SERVER_PID 2>/dev/null
    fi
    echo "✅ 服务已关闭"
    exit 0
}
trap cleanup EXIT INT TERM

# 检查是否以 sudo 运行
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  需要管理员权限才能修复应用。"
    echo "   正在以 sudo 重新启动..."
    echo ""
    exec sudo "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/app.py"
else
    python3 "$SCRIPT_DIR/app.py" &
    SERVER_PID=$!
    sleep 2
    if curl -s "$URL" > /dev/null 2>&1; then
        echo "🌐 自动打开浏览器..."
        open "$URL"
    fi
    wait $SERVER_PID
fi
