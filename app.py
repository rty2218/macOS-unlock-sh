#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
macOS 应用修复工具
自动扫描、检测并修复因安全隔离属性导致的 "应用已损坏" 问题。
"""

import os
import subprocess
import json
import glob
import re
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

APPLICATIONS_DIR = "/Applications"


def get_app_list():
    """获取 /Applications 下所有 .app 应用"""
    apps = []
    pattern = os.path.join(APPLICATIONS_DIR, "*.app")
    for app_path in sorted(glob.glob(pattern)):
        name = os.path.basename(app_path).replace(".app", "")
        apps.append({"name": name, "path": app_path})
    return apps


def check_quarantine(app_path):
    """检查应用是否有 com.apple.quarantine 隔离属性"""
    try:
        result = subprocess.run(
            ["xattr", "-l", app_path],
            capture_output=True, text=True, timeout=10
        )
        has_quarantine = "com.apple.quarantine" in result.stdout
        # 获取所有扩展属性
        attrs = []
        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                if ":" in line and not line.startswith(" "):
                    attr_name = line.split(":")[0].strip()
                    if attr_name:
                        attrs.append(attr_name)
        return {
            "has_quarantine": has_quarantine,
            "attributes": attrs,
            "raw_output": result.stdout.strip()
        }
    except Exception as e:
        return {
            "has_quarantine": False,
            "attributes": [],
            "error": str(e)
        }


def check_codesign(app_path):
    """检查应用的签名状态"""
    try:
        result = subprocess.run(
            ["codesign", "-v", "--verbose=2", app_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return {"valid": True, "detail": "签名有效"}
        else:
            error_msg = result.stderr.strip()
            return {"valid": False, "detail": error_msg}
    except Exception as e:
        return {"valid": False, "detail": str(e)}


def remove_quarantine(app_path):
    """移除应用的安全隔离属性"""
    try:
        result = subprocess.run(
            ["xattr", "-dr", "com.apple.quarantine", app_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return {"success": True, "message": f"已移除隔离属性: {app_path}"}
        else:
            return {"success": False, "message": result.stderr.strip()}
    except Exception as e:
        return {"success": False, "message": str(e)}


def resign_app(app_path):
    """重新签名应用"""
    try:
        result = subprocess.run(
            ["codesign", "--force", "--deep", "--sign", "-", app_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return {"success": True, "message": f"已重新签名: {app_path}"}
        else:
            return {"success": False, "message": result.stderr.strip()}
    except Exception as e:
        return {"success": False, "message": str(e)}


def check_xcode_cli():
    """检查是否安装了 Xcode Command Line Tools"""
    try:
        result = subprocess.run(
            ["xcode-select", "-p"],
            capture_output=True, text=True, timeout=10
        )
        return {
            "installed": result.returncode == 0,
            "path": result.stdout.strip() if result.returncode == 0 else None
        }
    except Exception as e:
        return {"installed": False, "error": str(e)}


# ============ Routes ============

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scan")
def api_scan():
    """扫描所有应用并返回状态"""
    apps = get_app_list()
    results = []
    for a in apps:
        quarantine_info = check_quarantine(a["path"])
        results.append({
            "name": a["name"],
            "path": a["path"],
            "has_quarantine": quarantine_info["has_quarantine"],
            "attributes": quarantine_info.get("attributes", []),
        })
    # 将有问题的应用排在前面
    results.sort(key=lambda x: (not x["has_quarantine"], x["name"]))
    problem_count = sum(1 for r in results if r["has_quarantine"])
    return jsonify({
        "apps": results,
        "total": len(results),
        "problem_count": problem_count
    })


@app.route("/api/fix", methods=["POST"])
def api_fix():
    """修复指定应用"""
    data = request.get_json()
    app_path = data.get("path")
    actions = data.get("actions", ["quarantine", "resign"])

    if not app_path or not os.path.exists(app_path):
        return jsonify({"success": False, "message": "应用路径无效"}), 400

    logs = []
    overall_success = True

    # 步骤1: 移除隔离属性
    if "quarantine" in actions:
        result = remove_quarantine(app_path)
        logs.append({
            "action": "移除隔离属性",
            "command": f"xattr -dr com.apple.quarantine {app_path}",
            "success": result["success"],
            "message": result["message"]
        })
        if not result["success"]:
            overall_success = False

    # 步骤2: 重新签名
    if "resign" in actions:
        result = resign_app(app_path)
        logs.append({
            "action": "重新签名",
            "command": f"codesign --force --deep --sign - {app_path}",
            "success": result["success"],
            "message": result["message"]
        })
        if not result["success"]:
            overall_success = False

    # 重新检查状态
    quarantine_info = check_quarantine(app_path)

    return jsonify({
        "success": overall_success,
        "app_name": os.path.basename(app_path).replace(".app", ""),
        "path": app_path,
        "logs": logs,
        "still_has_quarantine": quarantine_info["has_quarantine"]
    })


@app.route("/api/fix-all", methods=["POST"])
def api_fix_all():
    """一键修复所有有问题的应用"""
    data = request.get_json() or {}
    actions = data.get("actions", ["quarantine", "resign"])

    apps = get_app_list()
    results = []
    fixed = 0
    failed = 0

    for a in apps:
        quarantine_info = check_quarantine(a["path"])
        if not quarantine_info["has_quarantine"]:
            continue

        logs = []
        app_success = True

        if "quarantine" in actions:
            result = remove_quarantine(a["path"])
            logs.append({
                "action": "移除隔离属性",
                "command": f"xattr -dr com.apple.quarantine {a['path']}",
                "success": result["success"],
                "message": result["message"]
            })
            if not result["success"]:
                app_success = False

        if "resign" in actions:
            result = resign_app(a["path"])
            logs.append({
                "action": "重新签名",
                "command": f"codesign --force --deep --sign - {a['path']}",
                "success": result["success"],
                "message": result["message"]
            })
            if not result["success"]:
                app_success = False

        if app_success:
            fixed += 1
        else:
            failed += 1

        results.append({
            "name": a["name"],
            "path": a["path"],
            "success": app_success,
            "logs": logs
        })

    return jsonify({
        "results": results,
        "fixed": fixed,
        "failed": failed,
        "total_processed": len(results)
    })


@app.route("/api/check-xcode-cli")
def api_check_xcode():
    """检查 Xcode CLI Tools 安装状态"""
    return jsonify(check_xcode_cli())


@app.route("/api/app-detail")
def api_app_detail():
    """获取单个应用的详细信息"""
    app_path = request.args.get("path")
    if not app_path or not os.path.exists(app_path):
        return jsonify({"error": "应用路径无效"}), 400

    quarantine_info = check_quarantine(app_path)
    codesign_info = check_codesign(app_path)

    # 获取应用大小
    try:
        result = subprocess.run(
            ["du", "-sh", app_path],
            capture_output=True, text=True, timeout=10
        )
        size = result.stdout.split()[0] if result.returncode == 0 else "未知"
    except Exception:
        size = "未知"

    return jsonify({
        "name": os.path.basename(app_path).replace(".app", ""),
        "path": app_path,
        "size": size,
        "quarantine": quarantine_info,
        "codesign": codesign_info
    })


if __name__ == "__main__":
    # 检查是否以 root 权限运行
    if os.geteuid() != 0:
        print("\n⚠️  警告：未使用 sudo 运行，部分功能可能受限。")
        print("   建议使用: sudo python3 app.py\n")

    print("=" * 50)
    print("  macOS 应用修复工具")
    print("  访问地址: http://localhost:5555")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5555, debug=False)
