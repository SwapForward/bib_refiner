#!/usr/bin/env python3
"""
BibTeX Refiner - Refine LLM-generated BibTeX entries with academic databases

Motivation: Large Language Models (LLMs) often hallucinate when generating BibTeX entries,
creating incorrect metadata, DOIs, or publication details. This tool queries authoritative
academic databases (Semantic Scholar, DBLP, Crossref) to refine and validate BibTeX entries.

License: MIT
"""

import argparse
import os
import re
import sys
import time
import requests
import urllib.parse
from difflib import SequenceMatcher
from habanero import Crossref, cn
from lxml import etree


def calculate_similarity(str1, str2, debug=False):
    """
    计算两个字符串的相似度（0-1之间）
    基于单词匹配：统计查询结果中有多少单词在原标题中出现
    忽略大小写和标点符号
    """
    import string

    # 清理和统一大小写
    str1_lower = str1.lower().strip()
    str2_lower = str2.lower().strip()

    # 先将连字符、冒号等替换为空格，避免单词粘连
    # 例如 "Video-to-Audio" -> "Video to Audio"
    for char in ['-', ':', '/', '\\', '(', ')', '[', ']', '{', '}']:
        str1_lower = str1_lower.replace(char, ' ')
        str2_lower = str2_lower.replace(char, ' ')

    # 移除其他标点符号
    translator = str.maketrans('', '', string.punctuation)
    str1_clean = str1_lower.translate(translator)
    str2_clean = str2_lower.translate(translator)

    # 提取单词
    words1 = set(str1_clean.split())
    words2 = set(str2_clean.split())

    # 过滤掉常见停用词
    stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from'}
    words1 = words1 - stop_words
    words2 = words2 - stop_words

    # 移除空字符串
    words1 = {w for w in words1 if w}
    words2 = {w for w in words2 if w}

    if not words1 or not words2:
        return 0.0

    # 计算交集和并集
    intersection = words1 & words2
    union = words1 | words2

    # Jaccard 相似度 (交集/并集)
    jaccard_similarity = len(intersection) / len(union) if union else 0.0

    # 覆盖率（查询结果的单词有多少在原标题中）
    coverage = len(intersection) / len(words2) if words2 else 0.0

    # 调试模式：打印详细信息
    if debug:
        print(f"  [调试] 原标题单词: {sorted(words1)}")
        print(f"  [调试] 查询结果单词: {sorted(words2)}")
        print(f"  [调试] 交集单词: {sorted(intersection)}")
        print(f"  [调试] 交集数/原标题数/查询结果数: {len(intersection)}/{len(words1)}/{len(words2)}")
        print(f"  [调试] Jaccard={jaccard_similarity:.2%}, 覆盖率={coverage:.2%}")

    # 取两者的加权平均，覆盖率权重更高（更重要）
    # 如果查询结果的大部分单词都在原标题中，说明很可能是同一篇论文
    return 0.3 * jaccard_similarity + 0.7 * coverage


def extract_bibtex_entries(content):
    """
    从内容中提取 BibTeX 条目
    返回列表，每个元素为字典 {'citation_key', 'title', 'entry_type', 'full_entry'}
    """
    entries = []

    # 手动解析 BibTeX 条目，支持多层嵌套花括号
    # 找到所有 @entrytype{ 的位置
    entry_starts = []
    for match in re.finditer(r'@(\w+)\{', content):
        entry_starts.append((match.start(), match.group(1), match.end()))

    for i, (start_pos, entry_type, brace_start) in enumerate(entry_starts):
        # 找到对应的闭合花括号
        brace_count = 1
        pos = brace_start
        while pos < len(content) and brace_count > 0:
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
            pos += 1

        if brace_count != 0:
            # 花括号不匹配，跳过
            continue

        # 提取完整条目
        full_entry = content[start_pos:pos]

        # 提取 citation_key（在第一个逗号之前）
        inner_content = content[brace_start:pos-1]
        comma_pos = inner_content.find(',')
        if comma_pos == -1:
            continue

        citation_key = inner_content[:comma_pos].strip()
        entry_content = inner_content[comma_pos+1:].strip()

        # 提取 title（改进版：处理嵌套花括号）
        # 先找到 title = { 的位置
        title_start_match = re.search(r'title\s*=\s*\{', entry_content, re.IGNORECASE)
        if title_start_match:
            start_pos = title_start_match.end()
            # 从这个位置开始，匹配对应的闭合花括号
            brace_count = 1
            pos = start_pos
            while pos < len(entry_content) and brace_count > 0:
                if entry_content[pos] == '{':
                    brace_count += 1
                elif entry_content[pos] == '}':
                    brace_count -= 1
                pos += 1

            if brace_count == 0:
                title = entry_content[start_pos:pos-1].strip()

                # 清理 BibTeX 格式的花括号（如 {MMAudio} -> MMAudio）
                # 但保留实际内容中的花括号
                title_clean = re.sub(r'\{([^{}]+)\}', r'\1', title)

                entries.append({
                    'citation_key': citation_key,
                    'title': title_clean,
                    'entry_type': entry_type,
                    'full_entry': full_entry
                })
            else:
                print(f"⚠ 警告: 无法从条目 {citation_key} 中提取标题（花括号不匹配）")
        else:
            print(f"⚠ 警告: 无法从条目 {citation_key} 中找到 title 字段")

    return entries


def get_bib_from_crossref(title, citation_key, similarity_threshold=0.7):
    """使用 Crossref 获取 BibTeX，并验证标题相似度"""
    try:
        print(f"  [Crossref] 正在查询...")
        cr = Crossref()

        # 搜索标题，取第一个结果
        result = cr.works(query=title, limit=1)

        if not result['message']['items']:
            print(f"  [Crossref] ✗ 未找到结果")
            return None

        item = result['message']['items'][0]
        doi = item['DOI']
        found_title = item.get('title', [''])[0]
        found_author = item.get('author', [{}])[0].get('family', 'N/A')
        found_year = item.get('published', {}).get('date-parts', [[None]])[0][0] or \
                    item.get('created', {}).get('date-parts', [[None]])[0][0] or 'N/A'

        print(f"  [Crossref] ✓ 找到: {found_title}")
        print(f"             DOI: {doi}")
        print(f"             作者: {found_author} et al.")
        print(f"             年份: {found_year}")

        # 验证标题相似度（启用调试模式）
        similarity = calculate_similarity(title, found_title, debug=True)
        similarity_percent = similarity * 100

        print(f"             相似度: {similarity_percent:.1f}%", end="")

        # 判断相似度是否达标
        if similarity < similarity_threshold:
            print(f" ✗ (低于 {similarity_threshold*100:.0f}% 阈值)")
            print(f"  [Crossref] ⚠ 标题不匹配")
            return None
        else:
            print(f" ✓")

        # 通过 DOI 获取 BibTeX 格式
        bib_data = cn.content_negotiation(ids=doi, format='bibentry')

        # 替换引用键
        bib_data_updated = replace_citation_key_in_bibtex(bib_data, citation_key)

        return bib_data_updated

    except Exception as e:
        print(f"  [Crossref] ✗ 错误: {e}")
        return None


def get_bib_from_semantic_scholar(title, citation_key, api_key=None, similarity_threshold=0.70):
    """使用 Semantic Scholar API 获取 BibTeX，并验证标题相似度"""
    try:
        print(f"  [Semantic Scholar] 正在查询...")

        # 构建请求 URL
        query = urllib.parse.quote(title)
        search_url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=1&fields=paperId,title,authors,year,venue,citationStyles"

        # 设置请求头（如果有 API key）
        headers = {}
        if api_key:
            headers['x-api-key'] = api_key

        response = requests.get(search_url, headers=headers, timeout=10)

        # 检查速率限制
        if response.status_code == 429:
            print(f"  [Semantic Scholar] ⚠ 速率限制 (429)")
            return None

        response.raise_for_status()
        result = response.json()

        if not result.get('data'):
            print(f"  [Semantic Scholar] ✗ 未找到结果")
            return None

        paper = result['data'][0]
        found_title = paper.get('title', '')
        found_authors = paper.get('authors', [])
        found_year = paper.get('year', 'N/A')
        found_venue = paper.get('venue', 'N/A')

        # 显示作者（前3个）
        author_names = ', '.join([a.get('name', '') for a in found_authors[:3]])
        if len(found_authors) > 3:
            author_names += ' et al.'

        print(f"  [Semantic Scholar] ✓ 找到: {found_title}")
        print(f"                     作者: {author_names}")
        print(f"                     年份: {found_year}")
        print(f"                     会议/期刊: {found_venue}")

        # 验证标题相似度（启用调试模式）
        similarity = calculate_similarity(title, found_title, debug=True)
        similarity_percent = similarity * 100

        print(f"                     相似度: {similarity_percent:.1f}%", end="")

        # 判断相似度是否达标
        if similarity < similarity_threshold:
            print(f" ✗ (低于 {similarity_threshold*100:.0f}% 阈值)")
            print(f"  [Semantic Scholar] ⚠ 标题不匹配")
            return None
        else:
            print(f" ✓")

        # 获取 BibTeX
        bibtex = paper.get('citationStyles', {}).get('bibtex')
        if not bibtex:
            print(f"  [Semantic Scholar] ✗ 无法获取 BibTeX")
            return None

        # 替换引用键
        bibtex_updated = replace_citation_key_in_bibtex(bibtex, citation_key)

        return bibtex_updated

    except Exception as e:
        print(f"  [Semantic Scholar] ✗ 错误: {e}")
        return None


def get_bib_from_dblp(title, citation_key, similarity_threshold=0.7):
    """使用 DBLP 获取 BibTeX，并验证标题相似度"""
    try:
        print(f"  [DBLP] 正在查询...")

        # 构建搜索 URL
        query = urllib.parse.quote(title)
        search_url = f"https://dblp.org/search?q={query}"

        # 发送搜索请求
        response = requests.get(search_url, timeout=10)

        # 检查速率限制
        if response.status_code == 429:
            print(f"  [DBLP] ⚠ 速率限制 (429)")
            return None

        response.raise_for_status()

        # 解析 HTML，找到 BibTeX 链接
        html = etree.HTML(response.content)
        bibtex_links = html.xpath('//a[contains(@href, "?view=bibtex")]/@href')

        if not bibtex_links:
            print(f"  [DBLP] ✗ 未找到结果")
            return None

        # 取第一个结果，并转换为 .bib URL
        bibtex_link = bibtex_links[0]
        bib_url = bibtex_link.replace('.html?view=bibtex', '.bib')

        # 下载 BibTeX
        bib_response = requests.get(bib_url, timeout=10)

        # 再次检查速率限制
        if bib_response.status_code == 429:
            print(f"  [DBLP] ⚠ 速率限制 (429)")
            return None

        bib_response.raise_for_status()
        bibtex = bib_response.text.strip()

        # 从 BibTeX 中提取标题以验证相似度（处理嵌套花括号）
        title_start_match = re.search(r'title\s*=\s*\{', bibtex, re.IGNORECASE)
        if not title_start_match:
            print(f"  [DBLP] ✗ 无法从 BibTeX 提取标题")
            return None

        start_pos = title_start_match.end()
        # 从这个位置开始，匹配对应的闭合花括号
        brace_count = 1
        pos = start_pos
        while pos < len(bibtex) and brace_count > 0:
            if bibtex[pos] == '{':
                brace_count += 1
            elif bibtex[pos] == '}':
                brace_count -= 1
            pos += 1

        if brace_count != 0:
            print(f"  [DBLP] ✗ 无法从 BibTeX 提取标题（花括号不匹配）")
            return None

        found_title = bibtex[start_pos:pos-1].strip()
        # 清理 BibTeX 格式的花括号（如 {MMAudio} -> MMAudio）
        found_title = re.sub(r'\{([^{}]+)\}', r'\1', found_title)

        print(f"  [DBLP] ✓ 找到: {found_title[:60]}...")

        # 验证标题相似度（启用调试模式）
        similarity = calculate_similarity(title, found_title, debug=True)
        similarity_percent = similarity * 100

        print(f"         相似度: {similarity_percent:.1f}%", end="")

        # 判断相似度是否达标
        if similarity < similarity_threshold:
            print(f" ✗ (低于 {similarity_threshold*100:.0f}% 阈值)")
            print(f"  [DBLP] ⚠ 标题不匹配")
            return None
        else:
            print(f" ✓")

        # 替换引用键
        bibtex_updated = replace_citation_key_in_bibtex(bibtex, citation_key)

        # 清理 DBLP 特有的字段
        bibtex_cleaned = remove_dblp_fields(bibtex_updated)

        return bibtex_cleaned

    except Exception as e:
        print(f"  [DBLP] ✗ 错误: {e}")
        return None


def remove_dblp_fields(bibtex):
    """
    移除 DBLP 特有的字段（timestamp, biburl, bibsource）
    """
    lines = bibtex.split('\n')
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        # 跳过 DBLP 特有字段
        if any(stripped.startswith(field) for field in ['timestamp', 'biburl', 'bibsource']):
            continue
        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def replace_citation_key_in_bibtex(bibtex, new_key):
    """
    替换 BibTeX 中的引用键
    将 @entrytype{原键, 替换为 @entrytype{新键,
    """
    # 匹配 @entrytype{citation_key,
    pattern = r'(@\w+\{)([^,]+)(,)'
    replacement = r'\1' + new_key + r'\3'
    new_bibtex = re.sub(pattern, replacement, bibtex, count=1)
    return new_bibtex.strip()


def truncate_authors(author_field, max_authors=5):
    """
    截断作者列表，超过 max_authors 个作者时只保留前 max_authors 个并添加 'and others'
    """
    # 按 'and' 分割作者（注意前后要有空格或换行）
    import re
    # 先统一格式：将所有换行符和多余空格替换为单个空格
    author_clean = re.sub(r'\s+', ' ', author_field.strip())

    # 按 ' and ' 分割（注意两边有空格）
    authors = re.split(r'\s+and\s+', author_clean)

    if len(authors) > max_authors:
        # 只保留前 max_authors 个作者
        truncated = authors[:max_authors]
        # 添加 'and others'
        return ' and\n                  '.join(truncated) + ' and\n                  others'
    else:
        # 不超过限制，保持原样但格式化
        return ' and\n                  '.join(authors)


def format_bibtex(bibtex):
    """格式化 BibTeX，统一缩进，每个字段一行，并截断过长的作者列表"""
    # 检查是否是单行格式（没有换行符，或者所有内容在一行）
    if '\n' not in bibtex or bibtex.count('\n') <= 1:
        # 单行格式，需要拆分成多行
        # 匹配 @entrytype{key, field1={...}, field2={...}, ... }
        entry_match = re.match(r'(@\w+\{)([^,]+)(,\s*)(.*?)(\s*\})\s*$', bibtex.strip(), re.DOTALL)
        if not entry_match:
            # 无法解析，直接返回
            return bibtex

        entry_start = entry_match.group(1) + entry_match.group(2) + ','
        fields_str = entry_match.group(4).strip()

        # 解析字段
        fields = []
        pos = 0
        while pos < len(fields_str):
            # 跳过空白
            while pos < len(fields_str) and fields_str[pos].isspace():
                pos += 1
            if pos >= len(fields_str):
                break

            # 匹配字段名
            field_match = re.match(r'(\w+)\s*=\s*', fields_str[pos:])
            if not field_match:
                break

            field_name = field_match.group(1)
            pos += field_match.end()

            # 提取字段值
            if pos < len(fields_str) and fields_str[pos] == '{':
                # 值用花括号包围
                brace_count = 0
                value_start = pos
                while pos < len(fields_str):
                    if fields_str[pos] == '{':
                        brace_count += 1
                    elif fields_str[pos] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            pos += 1
                            break
                    pos += 1
                value = fields_str[value_start:pos].strip()
            else:
                # 值不用花括号，找到下一个逗号或结束
                value_start = pos
                while pos < len(fields_str) and fields_str[pos] not in ',}':
                    pos += 1
                value = fields_str[value_start:pos].strip()

            fields.append(f'{field_name} = {value}')

            # 跳过逗号
            if pos < len(fields_str) and fields_str[pos] == ',':
                pos += 1

        # 构建多行格式
        formatted = entry_start + '\n'
        for field in fields:
            formatted += '  ' + field + ',\n'
        # 移除最后一个逗号
        formatted = formatted.rstrip(',\n') + '\n'
        formatted += '}'

        # 截断作者列表
        formatted = apply_author_truncation(formatted)
        return formatted
    else:
        # 已经是多行格式，只需要调整缩进
        lines = bibtex.split('\n')
        formatted_lines = []

        for line in lines:
            stripped = line.strip()
            # 第一行和最后一行不缩进
            if stripped.startswith('@') or stripped == '}':
                formatted_lines.append(stripped)
            elif stripped:  # 跳过空行
                # 其他行缩进2空格
                formatted_lines.append('  ' + stripped)

        result = '\n'.join(formatted_lines)
        # 截断作者列表
        result = apply_author_truncation(result)
        return result


def apply_author_truncation(bibtex):
    """
    在完整的 BibTeX 条目中查找并截断 author 字段
    """
    # 查找 author 字段的起始位置
    author_match = re.search(r'(author\s*=\s*\{)', bibtex, re.IGNORECASE)
    if not author_match:
        return bibtex

    start_pos = author_match.end()
    # 找到对应的闭合花括号
    brace_count = 1
    pos = start_pos
    while pos < len(bibtex) and brace_count > 0:
        if bibtex[pos] == '{':
            brace_count += 1
        elif bibtex[pos] == '}':
            brace_count -= 1
        pos += 1

    if brace_count != 0:
        return bibtex

    # 提取作者字段内容
    author_content = bibtex[start_pos:pos-1]

    # 截断作者列表
    truncated_authors = truncate_authors(author_content)

    # 重新组装 BibTeX
    before = bibtex[:start_pos]
    after = bibtex[pos-1:]
    return before + truncated_authors + after


def main():
    parser = argparse.ArgumentParser(
        description='智能 BibTeX 更新：自动先用 Semantic Scholar（有API key），失败后切换到 DBLP，最后尝试 Crossref',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本使用（自动三层切换，推荐使用 API key）
  python update_bibtex.py --input title.txt -o ref.txt --semantic-key YOUR_KEY

  # 强制重新查询所有条目
  python update_bibtex.py --input title.txt -o ref.txt --semantic-key YOUR_KEY --force

  # 调整相似度阈值
  python update_bibtex.py --input title.txt -o ref.txt --semantic-key YOUR_KEY --similarity 0.85

  # 查询失败时保留原始条目
  python update_bibtex.py --input title.txt -o ref.txt --semantic-key YOUR_KEY --keep-original

工作流程:
  1. 先用 Semantic Scholar 查询（覆盖最全面：正式发表+arXiv预印本+新论文）
  2. 如果失败，自动切换到 DBLP（计算机科学论文数据库，速度快）
  3. 如果仍失败，最后尝试 Crossref（高质量、正式发表的论文）
  4. 相似度验证（默认 80%）避免找错论文
  5. 断点续传：已成功条目自动跳过（使用 --force 强制重新查询）

申请免费 Semantic Scholar API key（强烈推荐）:
  https://www.semanticscholar.org/product/api#api-key-form
  免费 API key 限额：10,000 次请求 / 5 分钟（vs 无 key 的 100 次）
        """
    )

    parser.add_argument('--input', default='title.txt', help='输入的 BibTeX 文件（如 title.txt）')
    parser.add_argument('-o', '--output', default='ref.txt',
                       help='输出文件（默认: ref.txt）')
    parser.add_argument('--semantic-key', '-k',
                       default=None,
                       help='Semantic Scholar API key (recommended for better rate limits)')
    parser.add_argument('--similarity', type=float, default=0.7,
                       help='标题相似度阈值，0-1之间（默认: 0.8，即 80%%）')
    parser.add_argument('--keep-original', action='store_true',
                       help='查询失败时保留原始条目')
    parser.add_argument('--delay', type=int, default=1,
                       help='每个查询之间的延迟秒数（默认: 1）')
    parser.add_argument('--force', action='store_true',
                       help='强制重新查询所有条目（忽略已有结果）')

    args = parser.parse_args()

    # 读取输入文件
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"✗ 错误: 文件 {args.input} 不存在", file=sys.stderr)
        sys.exit(1)

    # 提取 BibTeX 条目
    print(f"正在解析 {args.input}...\n")
    entries = extract_bibtex_entries(content)

    if not entries:
        print("✗ 未找到任何 BibTeX 条目", file=sys.stderr)
        sys.exit(1)

    # 读取已有的成功结果（断点续传）
    existing_entries = {}  # citation_key -> bibtex
    existing_keys = set()
    if not args.force and os.path.exists(args.output):
        print(f"发现已有结果文件: {args.output}")
        try:
            with open(args.output, 'r', encoding='utf-8') as f:
                existing_content = f.read()
            existing_list = extract_bibtex_entries(existing_content)
            for entry in existing_list:
                existing_keys.add(entry['citation_key'])
                existing_entries[entry['citation_key']] = entry['full_entry']
            print(f"已有 {len(existing_keys)} 个成功条目，将跳过重复查询\n")
        except Exception as e:
            print(f"⚠ 读取已有结果失败: {e}，将重新查询所有条目\n")
            existing_keys = set()
            existing_entries = {}

    print(f"找到 {len(entries)} 个 BibTeX 条目")
    if existing_keys:
        to_process = len(entries) - len(existing_keys)
        print(f"需要处理: {to_process} 个（{len(existing_keys)} 个已完成）")
    print("策略: Semantic Scholar (优先) → DBLP (次选) → Crossref (最后)")
    if args.semantic_key:
        print(f"Semantic Scholar API Key: {args.semantic_key[:8]}...")
    else:
        print("⚠ 警告: 未提供 Semantic Scholar API key，可能遇到速率限制")
    print("="*70)

    # 处理每个条目
    updated_entries = []
    failed_titles = []  # 收集失败的标题
    stats = {'crossref': 0, 'semantic': 0, 'dblp': 0, 'failed': 0, 'skipped': 0}

    for idx, entry in enumerate(entries, 1):
        print(f"\n[{idx}/{len(entries)}] 处理: {entry['citation_key']}")
        print(f"  标题: {entry['title']}")

        # 检查是否已经查询成功（断点续传）
        if entry['citation_key'] in existing_keys:
            print(f"  ⏭ 已存在，跳过")
            updated_entries.append(existing_entries[entry['citation_key']])
            stats['skipped'] += 1
            continue

        bibtex = None
        source = None

        # 步骤1: 先尝试 Semantic Scholar（覆盖最全面，有API key速度快）
        bibtex = get_bib_from_semantic_scholar(
            entry['title'],
            entry['citation_key'],
            api_key=args.semantic_key,
            similarity_threshold=args.similarity
        )

        if bibtex:
            source = 'semantic'
            stats['semantic'] += 1
        else:
            # 步骤2: Semantic Scholar 失败，切换到 DBLP
            print(f"  → 切换到 DBLP...")
            time.sleep(1)  # 避免请求过快

            bibtex = get_bib_from_dblp(
                entry['title'],
                entry['citation_key'],
                similarity_threshold=args.similarity
            )

            if bibtex:
                source = 'dblp'
                stats['dblp'] += 1
            else:
                # 步骤3: DBLP 也失败，最后尝试 Crossref
                print(f"  → 切换到 Crossref...")
                time.sleep(1)  # 避免请求过快

                bibtex = get_bib_from_crossref(
                    entry['title'],
                    entry['citation_key'],
                    similarity_threshold=args.similarity
                )

                if bibtex:
                    source = 'crossref'
                    stats['crossref'] += 1

        # 处理结果
        if bibtex:
            # 格式化
            bibtex = format_bibtex(bibtex)
            updated_entries.append(bibtex)
            print(f"  ✓ 已更新 (来源: {source.upper()})")

            # 立即写入文件（断点保护）
            output_text = "\n\n".join(updated_entries)
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_text)
        else:
            stats['failed'] += 1
            # 记录失败的标题
            failed_titles.append(entry['title'])

            # 立即更新 error.txt
            with open('error.txt', 'w', encoding='utf-8') as f:
                for title in failed_titles:
                    f.write(title + '\n')

            if args.keep_original:
                print(f"  ⚠ 查询失败，保留原始条目")
                updated_entries.append(entry['full_entry'])
                # 立即写入文件
                output_text = "\n\n".join(updated_entries)
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(output_text)
            else:
                print(f"  ✗ 查询失败，跳过")

        # 避免请求过快
        if idx < len(entries):
            time.sleep(args.delay)

    # 保存结果
    if updated_entries:
        output_text = "\n\n".join(updated_entries)

        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_text)

        print("\n" + "="*70)
        print(f"✓ 成功处理 {len(updated_entries)}/{len(entries)} 个条目")
        if stats['skipped'] > 0:
            print(f"  - 已跳过（已有结果）: {stats['skipped']} 个")
        print(f"  - DBLP: {stats['dblp']} 个")
        print(f"  - Crossref: {stats['crossref']} 个")
        print(f"  - Semantic Scholar: {stats['semantic']} 个")
        if stats['failed'] > 0:
            print(f"  - 失败: {stats['failed']} 个")
        print(f"✓ 已保存到: {args.output}")

        # 保存失败的标题到 error.txt
        if failed_titles:
            error_file = 'error.txt'
            with open(error_file, 'w', encoding='utf-8') as f:
                for title in failed_titles:
                    f.write(title + '\n')
            print(f"✗ 失败的标题已保存到: {error_file}")
    else:
        print("\n✗ 没有成功更新任何条目", file=sys.stderr)

        # 保存失败的标题
        if failed_titles:
            error_file = 'error.txt'
            with open(error_file, 'w', encoding='utf-8') as f:
                for title in failed_titles:
                    f.write(title + '\n')
            print(f"✗ 失败的标题已保存到: {error_file}")

        sys.exit(1)


if __name__ == '__main__':
    main()
