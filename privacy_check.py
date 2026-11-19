#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前隐私扫描（通用规则，可公开）。

检查个人绝对路径、邮箱、手机号、内网 IP、常见凭据格式；命中则退出码 1。
CI 会把本脚本作为发布前硬门槛。

用法：
    python privacy_check.py            # 扫描当前目录
    python privacy_check.py --root .   # 指定目录

可选：在仓库根放 `.privacy-words`（每行一个词，已 gitignore），
用于补充项目特有的敏感词（课程名、学校名等），本脚本会自动读取。
"""
import argparse
import os
import re
import sys

EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "out", ".github"}
TEXT_EXT = {
    ".py", ".md", ".txt", ".json", ".js", ".mjs", ".yml", ".yaml",
    ".sh", ".html", ".css", ".toml", ".ini", ".cfg",
}
ALLOW_IPS = {
    "127.0.0.1", "0.0.0.0", "10.0.0.0", "172.16.0.0", "192.168.0.0",
}
SKIP_FILES = {".privacy-words"}

RULES = [
    ("个人绝对路径", re.compile(
        r"(?<![\w\]\)])(?:/home/[A-Za-z0-9_.-]+|/Users/[A-Za-z0-9_.-]+"
        r"|/data/storage/[^\s\"'`]+|/storage/Users/[A-Za-z0-9_.-]+)")),
    ("Windows 用户路径", re.compile(r"[A-Za-z]:\\\\Users\\\\[A-Za-z0-9_.-]+")),
    ("邮箱", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("内网 IP", re.compile(
        r"(?<![\d.])(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}(?![\d.])")),
    ("凭据格式", re.compile(
        r"(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
        r"|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})")),
]


def is_text(path):
    ext = os.path.splitext(path)[1].lower()
    return ext in TEXT_EXT or os.path.basename(path) in (".gitignore",)


def iter_files(root):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in EXCLUDE_DIRS]
        for f in fn:
            yield os.path.join(dp, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    self_path = os.path.abspath(__file__)
    hits = []

    for p in iter_files(root):
        if os.path.abspath(p) == self_path:
            continue
        if os.path.basename(p) in SKIP_FILES or not is_text(p):
            continue
        try:
            lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            for label, rx in RULES:
                for m in rx.finditer(line):
                    val = m.group(0)
                    if label == "内网 IP" and val in ALLOW_IPS:
                        continue
                    hits.append((os.path.relpath(p, root), i, label, val[:80]))

    words_file = os.path.join(root, ".privacy-words")
    if os.path.isfile(words_file):
        words = [w.strip() for w in open(words_file, encoding="utf-8")
                 if w.strip() and not w.startswith("#")]
        for p in iter_files(root):
            if os.path.abspath(p) == self_path:
                continue
            if os.path.basename(p) in SKIP_FILES or not is_text(p):
                continue
            try:
                lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines, 1):
                for w in words:
                    if w in line:
                        hits.append((os.path.relpath(p, root), i, "本地敏感词", w))

    if hits:
        print("隐私检查未通过：%d 处" % len(hits))
        for h in hits:
            print("  %s:%d [%s] %s" % h)
        return 1
    print("隐私检查通过：0 命中")
    return 0


if __name__ == "__main__":
    sys.exit(main())
