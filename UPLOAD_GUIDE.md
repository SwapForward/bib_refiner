# 📤 GitHub 上传指南

## 快速上传步骤

### 1️⃣ 在 GitHub 上创建仓库

1. 访问 https://github.com/new
2. **Repository name**: `bib_refiner`
3. **Description**: `Refine LLM-generated BibTeX entries with authoritative academic databases`
4. 设置为 **Public**（开源项目）
5. **不要勾选** "Add a README file"（我们已经有了）
6. 点击 **Create repository**

### 2️⃣ 本地 Git 配置（首次使用需要）

```bash
# 配置你的 Git 用户信息（如果还没配置）
git config --global user.name "SwapForward"
git config --global user.email "your-email@example.com"
```

### 3️⃣ 上传到 GitHub

在当前文件夹 `/mnt/c/Users/11728/Desktop/cinedub/bib_refiner/` 运行：

```bash
# 1. 添加所有文件
git add .

# 2. 首次提交
git commit -m "Initial commit: BibTeX Refiner v1.0

- Refine LLM-generated BibTeX with Semantic Scholar, DBLP, and Crossref
- Smart similarity matching (70% threshold)
- Resume capability and real-time saving
- Clean output with author truncation
- MIT License"

# 3. 重命名分支为 main
git branch -M main

# 4. 关联远程仓库
git remote add origin https://github.com/SwapForward/bib_refiner.git

# 5. 推送到 GitHub
git push -u origin main
```

### 4️⃣ 验证上传成功

访问: https://github.com/SwapForward/bib_refiner

你应该能看到：
- ✅ README.md 自动显示在首页
- ✅ 所有文件已上传
- ✅ License 显示为 MIT

---

## 🎉 完成！

你的开源项目已经发布！现在可以：

1. **添加 Topics** (在仓库页面点击设置图标):
   - `bibtex`
   - `academic-writing`
   - `llm`
   - `citation`
   - `bibliography`
   - `python`

2. **分享给其他人**:
   - 直接发送仓库链接
   - 在论文/博客中引用

3. **持续更新**:
   ```bash
   # 修改代码后
   git add .
   git commit -m "描述你的修改"
   git push
   ```
