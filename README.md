# Nepali Reader for NVDA

[![Download Add-on](https://img.shields.io/badge/Download-nepaliReader--1.0.0.nvda--addon-brightgreen?style=for-the-badge&logo=nvda)](https://github.com/SuyogDhungel/nepaliReader/releases/download/v1.0.0/nepaliReader-1.0.0.nvda-addon)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](LICENSE)
[![NVDA Compatibility](https://img.shields.io/badge/NVDA-2024.1%20to%202026.3-purple.svg)](https://www.nvaccess.org/)

**Nepali Reader** is a free, open-source NVDA screen reader add-on created to solve the long-standing Devanagari reading issues faced by blind and visually impaired computer users in Nepal.

---

## 📌 Why This Add-on Was Created

Screen reader users in Nepal regularly encounter two major barriers when reading documents:

1. **Legacy Devanagari Fonts**: Official government acts, gazettes, legal notices, newspapers, and school materials are frequently typed in legacy fonts like **Preeti**, **Kantipur**, **Sagarmatha**, **Fontasy Himali**, and **PCS Nepali** (or Hindi **Kruti Dev**). Screen readers see these fonts as plain English characters, reading meaningless gibberish (such as reading `"g]kfn"` instead of `"नेपाल"`).
2. **Damaged PDF Text Layers**: When government offices and organizations export documents to PDF from Microsoft Word ("Save as PDF"), InDesign, or web print tools, the underlying Devanagari Unicode text layer becomes heavily jumbled. Matras appear out of order, letters are missing, and conjuncts are broken.
3. **Silent Numbers in eSpeak**: Screen reader synthesizers like eSpeak often skip or remain silent on Devanagari numerals (`०, १, २, ३, ४, ५, ६, ७, ८, ९`), making section numbers, act years, and dates unreadable.

**Nepali Reader** solves all of these problems automatically and completely **offline**. It reconstructs the text directly from the font shapes and tables inside the document so NVDA speaks natural, accurate Devanagari without any internet connection.

---

## 📥 How to Download and Install

1. Download the add-on file:
   👉 [**Click here to download nepaliReader-1.0.0.nvda-addon**](https://github.com/SuyogDhungel/nepaliReader/releases/download/v1.0.0/nepaliReader-1.0.0.nvda-addon)
2. Once downloaded, open your **Downloads** folder and press **Enter** on `nepaliReader-1.0.0.nvda-addon`.
3. NVDA will ask: *"Are you sure you want to install this add-on?"* — Press **Yes** (`Alt + Y`).
4. When prompted to restart NVDA, select **Yes**.
5. That is all! Nepali Reader activates automatically upon startup.

*Alternative installation method*: Open the **NVDA Menu (`NVDA + N`) $\to$ Tools $\to$ Add-on Store**, switch to the **Installed add-ons** tab, choose **Install from external file...**, select the downloaded file, and restart NVDA.

---

## 🧭 How to Use This Tool

### 1. Using via the NVDA Menu

You can control all features directly through the NVDA menu using your keyboard:

* **Toggle Nepali Mode on / off**:
  1. Press **`NVDA + N`** to open the NVDA Menu.
  2. Press **`T`** to open the **Tools** submenu.
  3. Navigate to **Nepali Reader** and press **Enter**.
  4. Check or uncheck **Nepali mode** to turn the add-on on or off.

* **Convert Highlighted Text or Clipboard**:
  1. If you are in an application where text is not reading, select the text (or copy it to your clipboard).
  2. Press **`NVDA + N` $\to$ Tools $\to$ Nepali Reader $\to$ Convert selected text or clipboard**.
  3. NVDA will convert the text to Unicode, copy the clean text to your clipboard, and read it aloud immediately.

* **Add-on Settings**:
  1. Press **`NVDA + N` $\to$ Preferences $\to$ Settings**.
  2. In the categories list, press **`N`** until you reach **Nepali Reader**.
  3. Here you can configure legacy font detection, switch languages automatically, or adjust repair settings.

---

### 2. Default Keyboard Shortcuts

| Shortcut | What It Does |
|---|---|
| **`NVDA + Ctrl + Shift + Space`** | **Toggle Nepali Mode**: Quickly turns reading conversion on or off. NVDA will announce *"Nepali mode on"* or *"Nepali mode off"*. |
| **`Ctrl + C`** | **Smart Copy**: While Nepali mode is active, copying selected text automatically places clean, standard Unicode Devanagari onto your clipboard (ready to paste into Word, Facebook, or messaging apps). |
| **`NVDA + Alt + U`** | **Convert and Read**: Converts whatever text is currently selected (or on the clipboard) to Unicode and speaks it aloud. |
| **`NVDA + Alt + P`** | **Legacy Font Mode**: Cycles font conversion between *Automatic* (default), *Always Convert*, and *Off*. |
| **`NVDA + Alt + Shift + P`** | **Default Font Family**: Switches the default legacy font between Preeti, Kantipur, Sagarmatha, Himali, PCS, and Kruti Dev. |
| **`NVDA + Alt + O`** | **Offline OCR**: Performs optical character recognition on scanned PDFs or images in Nepali, Hindi, and English. Use arrow keys to review the text and `Escape` to close. |

---

### 3. How to Create or Customize Your Own Shortcuts

If any shortcut conflicts with another add-on or if you prefer different keys, you can assign your own:

1. Press **`NVDA + N`** to open the NVDA Menu.
2. Go to **Preferences** and press Enter on **Input gestures...**.
3. In the tree view, press **`N`** until you find the **Nepali Reader** category, then press **Right Arrow** to expand it.
4. You will see a list of actions:
   * *Toggle Nepali mode*
   * *Convert the selected text or the clipboard to Unicode*
   * *OCR the current object in Nepali, Hindi and English*
   * *Legacy font reading: automatic, always convert, off*
   * *Default legacy font family*
5. Select the action you wish to change.
6. Press **`Alt + A`** (or Tab to the **Add** button and press Enter).
7. Press the exact key combination you want to use on your keyboard (for example, `NVDA + Shift + N`).
8. Select whether to use this shortcut for `all layouts` or your current keyboard layout and press **Enter**.
9. Tab to the **OK** button and press Enter to save your new shortcut.

---

## 📑 Reading PDFs and Documents

* **Up / Down Arrow**: Reads line by line. Scrambled government PDFs are rebuilt into clear Nepali sentences.
* **Left / Right Arrow**: Moves character by character. Speaks full syllables accurately (e.g. `कि`, `र्मा`, `क्ष`, `ला`, `गू`).
* **Ctrl + Left / Right Arrow**: Moves word by word through real Devanagari words.
* **Shift + Arrows**: Selects text accurately without broken characters.
* **Numbers & Dates**: Dates like `२०७५` and numbers like `१.`, `(१)`, `२३` are announced in spoken Nepali via eSpeak.

---

## 🌐 Hindi Support Confirmation

Yes, **Nepali Reader also supports Hindi**:
* **Kruti Dev Fonts**: Text written in Kruti Dev (the standard Hindi typewriter font) is converted to Hindi Devanagari and spoken using a Hindi voice.
* **Offline OCR**: The built-in offline OCR includes complete Hindi recognition data (`hin.traineddata`).

---

## 📜 Changelog

### Version 1.0.0 (Official Initial Release)
* Universal automatic conversion for Preeti, Kantipur, Sagarmatha, Fontasy Himali, PCS Nepali, and Kruti Dev.
* Deep TrueType glyph reconstruction for broken Devanagari PDFs from Word, InDesign, Chrome, and LibreOffice.
* Syllable-accurate character navigation (`Left/Right Arrow`) with exact akshara boundaries.
* Automatic Nepali language tagging for eSpeak Devanagari numeral pronunciation.
* Smart clipboard copy (`Ctrl + C`) that converts legacy and PDF text directly to standard Unicode.
* Built-in offline OCR for Nepali, Hindi, and English (`NVDA + Alt + O`).
* Full NVDA menu and custom input gesture integration.

---

## ⚖️ License

Distributed under the **GNU General Public License v2.0 (GPL-2.0)**. See [LICENSE](LICENSE) for details.

## 👤 Author & Feedback

* **Author**: Suyog Dhungel
* **Email**: [dhungelsuyog13@gmail.com](mailto:dhungelsuyog13@gmail.com)
* **GitHub Repository**: [https://github.com/SuyogDhungel/nepaliReader](https://github.com/SuyogDhungel/nepaliReader)

If you encounter any inaccessible Nepali document or have suggestions, please open an Issue on GitHub or send an email.
