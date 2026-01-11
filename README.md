# BibTeX Refiner

> **Refine LLM-generated BibTeX entries with authoritative academic databases**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![GitHub stars](https://img.shields.io/github/stars/SwapForward/bib_refiner?style=social)](https://github.com/SwapForward/bib_refiner/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/SwapForward/bib_refiner)](https://github.com/SwapForward/bib_refiner/issues)

## 🎯 Motivation

Large Language Models (LLMs) like ChatGPT, Claude, and others are incredibly useful for generating BibTeX entries. However, they often **hallucinate** when creating bibliographic metadata:

- ❌ **Incorrect DOIs** - fabricated or wrong digital object identifiers
- ❌ **Wrong publication venues** - mismatched conference/journal names
- ❌ **Inaccurate dates** - incorrect publication years
- ❌ **Missing metadata** - incomplete author lists, page numbers, etc.
- ❌ **Inconsistent formatting** - non-standard BibTeX styles

**BibTeX Refiner** solves this by querying authoritative academic databases to validate and refine your BibTeX entries automatically.

### Before vs After

**Before** (LLM-generated with hallucinations):
```bibtex
@article{author2024paper,
  title = {Some Amazing Research Paper},
  author = {John Doe},
  year = {2024},
  doi = {10.1234/fake.doi}  # ❌ Fabricated DOI
}
```

**After** (refined with real data):
```bibtex
@inproceedings{author2024paper,
  author       = {John Doe and
                  Jane Smith and
                  Bob Chen and
                  Alice Wang and
                  Carol Lee and
                  others},
  title        = {Some Amazing Research Paper},
  booktitle    = {Proceedings of CVPR 2024},
  pages        = {12345--12356},
  year         = {2024},
  doi          = {10.1109/CVPR.2024.12345},  # ✅ Real DOI
  url          = {https://doi.org/10.1109/CVPR.2024.12345}
}
```

## ✨ Features

- 🔍 **Multi-source validation**: Queries Semantic Scholar → DBLP → Crossref in sequence
- 🎯 **Smart similarity matching**: Ensures returned entries match your titles (70% threshold)
- ⚡ **Resume capability**: Automatically skips already-processed entries
- 💾 **Real-time saving**: Writes results immediately to prevent data loss
- 🧹 **Clean output**: Removes redundant fields (timestamp, biburl, bibsource)
- 👥 **Author truncation**: Limits to first 5 authors + "others" for long author lists
- 📝 **Error tracking**: Failed queries saved to `error.txt`

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/SwapForward/bib_refiner.git
cd bib_refiner

# Install dependencies
pip install -r requirements.txt
```

## 🚀 Quick Start

### 1. Get a Semantic Scholar API Key (Recommended)

**Free API key with 10,000 requests / 5 minutes** (vs 100 requests without key)

1. Visit: https://www.semanticscholar.org/product/api#api-key-form
2. Fill in your details (name, email, affiliation)
3. Submit the form
4. **Wait ~10 minutes** - API key will be sent to your email

### 2. Prepare Your Input

Create a `title.txt` file with BibTeX entries (even if they have hallucinated data):

```bibtex
@inproceedings{author2024paper,
  title = {Some Amazing Research Paper},
  author = {John Doe and Jane Smith},
  year = {2024}
}

@article{researcher2023work,
  title = {Another Great Paper on AI},
  author = {Alice Johnson},
  year = {2023}
}
```

### 3. Run the Refiner

```bash
# Basic usage (without API key - limited rate)
python bib_refiner.py

# Recommended: with API key for better performance
python bib_refiner.py --semantic-key YOUR_API_KEY_HERE

# Custom input/output files
python bib_refiner.py --input my_refs.bib --output refined_refs.bib --semantic-key YOUR_KEY
```

### 4. Check the Output

The refined BibTeX entries will be saved to `ref.txt` (default) or your specified output file:

```bibtex
@inproceedings{author2024paper,
  author       = {John Doe and
                  Jane Smith and
                  Bob Chen and
                  Alice Wang and
                  Carol Lee and
                  others},
  title        = {Some Amazing Research Paper},
  booktitle    = {Proceedings of CVPR 2024},
  year         = {2024},
  doi          = {10.1109/CVPR.2024.12345},
  url          = {https://doi.org/10.1109/CVPR.2024.12345}
}
```

## 📖 Usage

```bash
python bib_refiner.py [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--input` | `title.txt` | Input BibTeX file to refine |
| `-o, --output` | `ref.txt` | Output file for refined entries |
| `-k, --semantic-key` | `None` | Semantic Scholar API key (highly recommended) |
| `--similarity` | `0.7` | Title similarity threshold (0-1) for matching |
| `--delay` | `1` | Delay in seconds between queries |
| `--keep-original` | `False` | Keep original entry if refinement fails |
| `--force` | `False` | Force re-query all entries (ignore cache) |

### Examples

```bash
# Resume from previous run (automatically skips completed entries)
python bib_refiner.py --semantic-key YOUR_KEY

# Force re-query everything
python bib_refiner.py --semantic-key YOUR_KEY --force

# Lower similarity threshold for fuzzy matching
python bib_refiner.py --semantic-key YOUR_KEY --similarity 0.6

# Keep original entries when refinement fails
python bib_refiner.py --semantic-key YOUR_KEY --keep-original
```

## 🗄️ Data Sources & Priority

The tool queries three academic databases in a specific order to maximize accuracy and coverage:

### 1️⃣ Semantic Scholar (Priority 1)
- **Coverage**: 📚 Most comprehensive - includes published papers, preprints (arXiv), and recent work
- **Fields**: 🌐 All academic fields (CS, physics, biology, medicine, etc.)
- **Speed**: ⚡ Fast with API key (10,000 requests/5min)
- **Data Quality**: ⭐⭐⭐⭐⭐ Excellent - includes venue, DOI, authors, citations
- **Why First?**: Best overall coverage for both published and preprint papers

### 2️⃣ DBLP (Priority 2)
- **Coverage**: 💻 Computer science and related fields only
- **Fields**: 🖥️ CS, AI, ML, software engineering
- **Speed**: ⚡ Fast - no API key required
- **Data Quality**: ⭐⭐⭐⭐⭐ Excellent for CS - highly curated, consistent formatting
- **Why Second?**: Extremely reliable for CS papers, but limited to CS domain

### 3️⃣ Crossref (Priority 3)
- **Coverage**: 📖 Formal publications with DOIs (journals, conferences)
- **Fields**: 🌐 All fields - anything with a DOI
- **Speed**: ⚡ Fast - no API key required
- **Data Quality**: ⭐⭐⭐⭐ Good - but may miss preprints and very recent papers
- **Why Last?**: Reliable fallback for papers with DOIs, but doesn't cover preprints

### Query Strategy

```
Paper Title
    ↓
┌─────────────────────────┐
│  Semantic Scholar       │ ✓ Found & Validated → Return
│  (Try first)            │ ✗ Not found/low similarity ↓
└─────────────────────────┘
    ↓
┌─────────────────────────┐
│  DBLP                   │ ✓ Found & Validated → Return
│  (Try second)           │ ✗ Not found/low similarity ↓
└─────────────────────────┘
    ↓
┌─────────────────────────┐
│  Crossref               │ ✓ Found & Validated → Return
│  (Try last)             │ ✗ Failed → Save to error.txt
└─────────────────────────┘
```

**Note**: Each source is validated with 70% title similarity threshold to prevent wrong matches.

## 🔄 How It Works

```
┌─────────────────┐
│  Input BibTeX   │
│   (title.txt)   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  1. Extract title from each entry   │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  2. Query Semantic Scholar API      │
│     ├─ Found? → Validate similarity │
│     └─ Not found? ↓                 │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  3. Query DBLP (CS papers)          │
│     ├─ Found? → Validate similarity │
│     └─ Not found? ↓                 │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  4. Query Crossref (all papers)     │
│     ├─ Found? → Validate similarity │
│     └─ Not found? → Mark as failed  │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  5. Clean & format BibTeX           │
│     ├─ Remove DBLP metadata fields  │
│     ├─ Truncate long author lists   │
│     └─ Apply consistent formatting  │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Output refined BibTeX (ref.txt)    │
│  + error.txt (failed queries)       │
└─────────────────────────────────────┘
```

## 📊 Output

### Success Case
- Refined BibTeX written to `ref.txt`
- Real-time updates (no data loss on interruption)
- Progress shown in console

### Failed Queries
- Failed titles saved to `error.txt`
- Can retry later or manually verify

### Statistics
```
======================================================================
✓ Successfully processed 75/78 entries
  - Semantic Scholar: 65 entries
  - DBLP: 8 entries
  - Crossref: 2 entries
  - Failed: 3 entries
✓ Saved to: ref.txt
✗ Failed titles saved to: error.txt
```

## 🛠️ Requirements

- Python 3.7+
- Dependencies (see `requirements.txt`):
  - `habanero` - Crossref API client
  - `requests` - HTTP library
  - `lxml` - HTML/XML parsing

## ❓ FAQ

<details>
<summary><b>Q: Do I need an API key?</b></summary>

Not required, but **highly recommended**. Without an API key, you're limited to 100 requests per 5 minutes. With a free API key, you get 10,000 requests per 5 minutes (100x increase).
</details>

<details>
<summary><b>Q: What if the tool can't find my paper?</b></summary>

The paper might be:
1. **Too new** - not yet indexed in the databases
2. **Non-CS field** - DBLP only covers computer science
3. **Title mismatch** - try adjusting `--similarity` threshold (e.g., `--similarity 0.6`)

Failed titles are saved to `error.txt` for manual processing.
</details>

<details>
<summary><b>Q: Can I interrupt the process?</b></summary>

Yes! The tool saves results in real-time. Just run it again and it will automatically resume from where it stopped.
</details>

<details>
<summary><b>Q: How accurate is the similarity matching?</b></summary>

The default 70% threshold works well for most cases. Lower it for fuzzy matching (`--similarity 0.6`) or raise it for stricter validation (`--similarity 0.85`).
</details>

<details>
<summary><b>Q: Why limit to 5 authors?</b></summary>

Many papers have 10+ authors. Listing them all makes BibTeX files bloated and harder to read. The first 5 authors + "others" is a common academic convention.
</details>

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Semantic Scholar API](https://www.semanticscholar.org/product/api) - Free academic search API
- [DBLP](https://dblp.org/) - Computer science bibliography
- [Crossref](https://www.crossref.org/) - DOI registration agency

## 📧 Contact

If you have any questions or suggestions, please open an issue on GitHub.

---

**Made with ❤️ to fight LLM hallucinations in academic writing**
