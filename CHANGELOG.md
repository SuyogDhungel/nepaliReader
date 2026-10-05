# Changelog

All notable changes to the **Nepali Reader** NVDA add-on are documented here.

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
