# Nepali Reader for NVDA

[![Download Add-on](https://img.shields.io/badge/Download-nepaliReader--2.0.nvda--addon-brightgreen?style=for-the-badge&logo=nvda)](https://github.com/SuyogDhungel/nepaliReader/releases/download/v2.0/nepaliReader-2.0.nvda-addon)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](LICENSE)
[![NVDA Compatibility](https://img.shields.io/badge/NVDA-2024.1%20to%202026.2-purple.svg)](https://www.nvaccess.org/)

**Nepali Reader** is a free, open-source NVDA screen reader add-on created to solve the long-standing Devanagari reading issues faced by blind and visually impaired computer users in Nepal.

> [!TIP]
> **Recommendation**: Keep Nepali Mode OFF (`NVDA + Ctrl + Shift + Space`) when working in English documents, browsing English websites, or programming. Toggle it ON when reading Nepali documents, gazettes, or PDFs.

---

## 📌 Why This Add-on Was Created

Screen reader users in Nepal regularly encounter two major barriers when reading documents:

1. **Legacy Devanagari Fonts**: Official government acts, gazettes, legal notices, newspapers, and school materials are frequently typed in legacy fonts like **Preeti**, **Kantipur**, **Sagarmatha**, **Fontasy Himali**, and **PCS Nepali**. Screen readers see these fonts as plain English characters, reading meaningless gibberish (such as reading `"g]kfn"` instead of `"नेपाल"`).
2. **Damaged PDF Text Layers**: When government offices and organizations export documents to PDF from Microsoft Word ("Save as PDF"), InDesign, or web print tools, the underlying Devanagari Unicode text layer becomes heavily jumbled. Matras appear out of order, letters are missing, and conjuncts are broken.
3. **Silent Numbers in eSpeak**: Screen reader synthesizers like eSpeak often skip or remain silent on Devanagari numerals (`०, १, २, ३, ४, ५, ६, ७, ८, ९`), making section numbers, act years, and dates unreadable.

**Nepali Reader** solves all of these problems automatically and completely **offline**. It reconstructs the text directly from the font shapes and tables inside the document so NVDA speaks natural, accurate Devanagari without any internet connection.

---

## 📥 How to Download and Install

1. Download the add-on file:
   👉 [**Click here to download nepaliReader-2.0.nvda-addon**](https://github.com/SuyogDhungel/nepaliReader/releases/download/v2.0/nepaliReader-2.0.nvda-addon)
2. Once downloaded, open your **Downloads** folder and press **Enter** on `nepaliReader-2.0.nvda-addon`.
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
| **`NVDA + Ctrl + Shift + Space`** | **Toggle Nepali Mode**: turns reading conversion on or off. NVDA announces *"Nepali mode on"* or *"Nepali mode off"*. |
| **`NVDA + Ctrl + L`** | **Open Settings**: directly opens the Nepali Reader settings dialog. |
| **`Ctrl + C`** | **Smart Copy**: while Nepali mode is on, copying selected text puts clean Unicode Devanagari on the clipboard. |

The other commands (convert selected text, legacy font mode, default font family) have no key by default. Use the NVDA menu, Tools, Nepali Reader, or assign a key yourself as described below.

---

### 3. How to Create or Customize Your Own Shortcuts

If any shortcut conflicts with another add-on or if you prefer different keys, you can assign your own:

1. Press **`NVDA + N`** to open the NVDA Menu.
2. Go to **Preferences** and press Enter on **Input gestures...**.
3. In the tree view, press **`N`** until you find the **Nepali Reader** category, then press **Right Arrow** to expand it.
4. You will see a list of actions:
   * *Toggle Nepali mode*
   * *Convert the selected text or the clipboard to Unicode*
   * *Legacy font reading: automatic, always convert, off*
   * *Default legacy font family*
5. Select the action you wish to change.
6. Press **`Alt + A`** (or Tab to the **Add** button and press Enter).
7. Press the exact key combination you want to use on your keyboard (any free combination).
8. Select whether to use this shortcut for `all layouts` or your current keyboard layout and press **Enter**.
9. Tab to the **OK** button and press Enter to save your new shortcut.

---

## 📑 Reading PDFs and Documents

* **Up / Down Arrow**: Reads line by line. Scrambled government PDFs are rebuilt into clear Nepali sentences.
* **Left / Right Arrow**: Moves character by character. Accurately speaks individual characters and vowel signs without repetition.
* **Ctrl + Left / Right Arrow**: Moves word by word through real Devanagari words.
* **Shift + Arrows**: Selects text accurately without broken characters.
* **Numbers & Dates**: Dates like `२०७५` and numbers like `१.`, `(१)`, `२३` are announced in spoken Nepali via eSpeak.
* **MultiLang & Multi-Voice TTS Support**: Seamlessly integrates with the **MultiLang** virtual synthesizer add-on. If MultiLang is active, Nepali Reader ensures Devanagari text is correctly recognized as Nepali (`ne`) rather than forced to Hindi (`hi`), and automatically routes speech to installed Nepali TTS voices (such as **Hear2Read Indic Voices** with Google Nepali voice or **eSpeak NG**) across Word documents, PDFs, and web browsers.

---

## 📜 Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full history of every version.

---

## ⚖️ License

Distributed under the **GNU General Public License v2.0 (GPL-2.0)**. See [LICENSE](LICENSE) for details.

## 🤝 Project & Support
* **Authors & Maintainers**: Suyog Dhungel (<dhungelsuyog13@gmail.com>), Roshan Gautam (<mr.pawittra@gmail.com>)
* **Project**: Nepali Reader for NVDA
* **GitHub Repository**: [https://github.com/SuyogDhungel/nepaliReader](https://github.com/SuyogDhungel/nepaliReader)
* **Feedback & Issues**: Please report issues or suggest improvements by opening an [Issue](https://github.com/SuyogDhungel/nepaliReader/issues) on GitHub.
* **Tags**: `nepali`, `nvda`, `nvda-addon`, `preeti-font`, `screen-reader`, `accessibility`, `devanagari`, `kantipur-font`
