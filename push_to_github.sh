#!/bin/bash
set -e

echo "🚀 准备上传到 GitHub..."

# 添加所有文件
git add .

# 提交
git commit -m "Initial commit: BibTeX Refiner v1.0

- Refine LLM-generated BibTeX with Semantic Scholar, DBLP, and Crossref
- Smart similarity matching (70% threshold)
- Resume capability and real-time saving
- Clean output with author truncation
- MIT License"

# 重命名分支为 main
git branch -M main

# 关联远程仓库
git remote add origin https://github.com/SwapForward/bib_refiner.git 2>/dev/null || echo "Remote already exists"

# 推送到 GitHub
echo "📤 正在推送到 GitHub..."
git push -u origin main

echo "✅ 成功上传到 https://github.com/SwapForward/bib_refiner"
