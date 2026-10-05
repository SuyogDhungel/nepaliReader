# Nepali Reader for NVDA

[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](LICENSE)
[![NVDA Compatibility](https://img.shields.io/badge/NVDA-2024.1%20to%202026.3-green.svg)](https://www.nvaccess.org/)
[![Release](https://img.shields.io/badge/Release-v1.0.0-orange.svg)](https://github.com/SuyogDhungel/nepaliReader/releases)

**Nepali Reader** is an open-source NVDA screen reader add-on designed to provide seamless, accurate, and completely offline Nepali reading support for blind and visually impaired users.

It automatically converts legacy Devanagari fonts (Preeti, Kantipur, Sagarmatha, Fontasy Himali, PCS Nepali, Kruti Dev) to Unicode, reconstructs corrupted Devanagari text layers in modern PDFs, speaks Devanagari numerals in Nepali with eSpeak, and provides offline OCR.

---

## 🌟 Key Features

* **Universal Legacy Font Reading**:
  * Reads **Preeti**, **Kantipur**, **Sagarmatha**, **Fontasy Himali**, and **PCS Nepali** as spoken Devanagari.
  * Reads Hindi **Kruti Dev** text accurately as Hindi.
  * Preserves English words and fonts (Calibri, Arial, Times New Roman, code snippets, URLs, email addresses) without false conversion.
  * Preserves punctuation, brackets, and bullet symbols (`•`, `●`, `■`, `✓`, `★`, `→`).

* **Advanced PDF Devanagari Reconstruction Engine**:
  * Fixes jumbled, broken, or split Devanagari words from Microsoft Word "Save as PDF", InDesign, Chrome PDFium/HarfBuzz, and LibreOffice.
  * Rebuilds text directly from TrueType glyph outlines and embedded font tables in the background.
  * **Syllable-Accurate Navigation**: Left/Right Arrow moves through exact syllables (e.g., `कि`, `र्मा`, `क्ष`, `ला`, `गू`), Ctrl+Left/Right Arrow moves by word, and Shift+Arrows selects clean Unicode text.
  * **Clipboard Copying (`Ctrl + C`)**: Always copies clean, properly formatted Unicode Devanagari to the clipboard.

* **eSpeak Devanagari Number Pronunciation**:
  * Automatically assigns Nepali language tagging to Devanagari text and numerals.
  * eSpeak pronounces dates, act numbers, and section identifiers aloud in Nepali (e.g., `२०७५` $\to$ *दुई हजार पचहत्तर*, `२३` $\to$ *तेइस*, `१.` $\to$ *एक*).

* **Offline OCR (NVDA + Alt + O)**:
  * Integrated offline OCR for Nepali, Hindi, and English using Tesseract to read scanned documents or inaccessible image PDFs.

* **Zero Configuration**:
  * Works out of the box upon installation. No internet connection or manual switching required.

---

## 📥 Download & Installation

1. Download the latest add-on package:
   - [**Download nepaliReader-1.0.0.nvda-addon**](https://github.com/SuyogDhungel/nepaliReader/releases/latest)
2. Press **Enter** on the downloaded `.nvda-addon` file, or open **NVDA Menu $\to$ Tools $\to$ Add-on Store $\to$ Install from external file...** and select the package.
3. Confirm installation and restart NVDA.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| **NVDA + Ctrl + Shift + Space** | Toggle Nepali Mode on / off |
| **Ctrl + C** | Copy text (in Nepali mode, copies clean Unicode Devanagari) |
| **NVDA + Alt + P** | Legacy font reading mode: Automatic (default), Always Convert, or Off |
| **NVDA + Alt + Shift + P** | Switch default legacy font family |
| **NVDA + Alt + U** | Convert selected text or clipboard to Unicode and read aloud |
| **NVDA + Alt + O** | Perform offline OCR on the current object / PDF page |

*All shortcuts can be customized under **NVDA Menu $\to$ Preferences $\to$ Input gestures $\to$ Nepali Reader**.*

---

## 🛠️ Building from Source

To package the add-on from the source code:

1. Clone the repository:
   ```bash
   git clone https://github.com/SuyogDhungel/nepaliReader.git
   cd nepaliReader
   ```
2. Run the build script using Python 3:
   ```bash
   python build.py
   ```
3. The installable `.nvda-addon` file and source zip will be generated in the root directory.

---

## 📂 Source Code Structure

```text
nepaliReader/
├── source/
│   ├── addon/
│   │   ├── manifest.ini              # NVDA add-on metadata
│   │   ├── doc/                      # User documentation & handoff notes
│   │   └── globalPlugins/
│   │       └── nepaliReader/         # Main add-on engine & hooks
│   │           ├── __init__.py       # NVDA integration & speech hooks
│   │           ├── legacyFonts.py    # Preeti / Kruti Dev conversion tables
│   │           ├── pdfText.py        # PDF Devanagari glyph reconstruction
│   │           ├── pdfReader.py      # Pure-Python PDF parser
│   │           ├── sfnt.py           # TrueType / OpenType font parser
│   │           └── devanagariRepair.py # Fallback Devanagari repair engine
│   ├── tests/                        # Automated unit & integration tests
│   └── tools/                        # Font analysis & training tools
├── build.py                          # Add-on packager
├── LICENSE                           # GNU General Public License v2.0
└── README.md                         # Documentation
```

---

## 📜 License

This project is licensed under the **GNU General Public License v2.0 (GPL-2.0)** - see the [LICENSE](LICENSE) file for details.

## 👤 Author & Support

* **Suyog Dhungel**
* Email: [dhungelsuyog13@gmail.com](mailto:dhungelsuyog13@gmail.com)
* GitHub: [@SuyogDhungel](https://github.com/SuyogDhungel)
