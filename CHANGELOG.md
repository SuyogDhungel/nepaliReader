# Changelog

All notable changes to the **Nepali Reader** NVDA add-on are documented here.

## [1.1.3] - 2026-10-06 (Stable Release)

### Added
- **Startup & Toggle Guidance**: Automatic announcement and settings panel tip recommending users keep Nepali mode OFF (`NVDA + Alt + N`) during English typing, programming, or menu navigation, and toggle it ON when reading Nepali text or PDFs.
- **Smart English Number & Symbol Protection**: Numbers like `8848.86`, `8516`, and standalone bullets (`*`, `•`, `-`) are protected from being misidentified as Preeti keys.
- **Ultra-Lightweight Distribution**: Completely removed user-facing OCR and heavy Tesseract data, shrinking package size from 27 MB to 2.99 MB.

## [1.1.2] - 2026-10-06

### Fixed
- **Selective Delta Announcements**: Fixed text selection so `Shift + Arrows` speaks only the newly selected/unselected delta chunk rather than repeating the entire selection from top to bottom.
- **Preeti Typewriter Typo Repairs**: Automatic restoration of `dxj` -> `महत्त्व`, `महवको` -> `महत्त्वको`.
- **Publisher Name**: Updated official publisher name to `Suyog Dhungel`.

## [1.0.0] - 2026-10-05 (Official Initial Release)

### Added
- **Universal Legacy Font Reading**:
  - Full offline support for Preeti, Kantipur, Sagarmatha, Fontasy Himali, and PCS Nepali fonts.
  - Full support for Hindi Kruti Dev fonts (`krutidev010`, `k010`, etc.) with Hindi synthesizer voice switching.
  - Automatic English word and font preservation (Calibri, Arial, Times New Roman, code blocks, URLs, and emails are never falsely converted).
  - Punctuation, parentheses, and bullet symbol preservation (`•`, `●`, `■`, `✓`, `★`, `→`, `–`, `—`).
- **Advanced Devanagari PDF Reconstruction Engine**:
  - Direct TrueType glyph outline and font table reconstruction for broken Devanagari text layers from Microsoft Word ("Save as PDF"), InDesign, Chrome PDFium/HarfBuzz, and LibreOffice.
  - Resolves misplaced short-i (`ि`), reph (`र्`), and split conjuncts in the background.
  - Syllable-accurate character navigation (`Left/Right Arrow`) with mathematical akshara partitioning.
  - Word navigation (`Ctrl + Left/Right Arrow`) through reconstructed Devanagari words.
  - Accurate multi-word text selection (`Shift + Arrows`).
- **eSpeak Devanagari Numeral Pronunciation**:
  - Automatic Nepali language tagging for Devanagari text and numerals.
  - eSpeak pronounces act numbers, section headers, and dates aloud in Nepali (e.g. `२०७५`, `२३`, `१.`).
- **Smart Unicode Clipboard Copy (`Ctrl + C`)**:
  - Copying in browse mode or focus mode converts selected legacy font text or repaired PDF text into clean, standard Unicode Devanagari on the clipboard.
- **Offline OCR (`NVDA + Alt + O`)**:
  - Integrated Tesseract OCR engine for Nepali, Hindi, and English to read scanned documents and image PDFs without internet access.
- **NVDA Menu & Gesture Customization**:
  - NVDA Menu (`NVDA + N`) -> Tools -> Nepali Reader submenu.
  - NVDA Menu (`NVDA + N`) -> Preferences -> Settings -> Nepali Reader panel.
  - NVDA Menu (`NVDA + N`) -> Preferences -> Input gestures -> Nepali Reader category for full shortcut customization.
