# 🚀 Pycade Bomber (瘋狂炸彈人 Pygame 複刻版)

[![Run Pygame Tests](https://github.com/peienwu1216/oop-2025-proj-pycade/actions/workflows/run-tests.yml/badge.svg)](https://github.com/peienwu1216/oop-2025-proj-pycade/actions/workflows/run-tests.yml)
[![Build and Deploy](https://github.com/peienwu1216/oop-2025-proj-pycade/actions/workflows/deploy-to-web.yml/badge.svg)](https://github.com/peienwu1216/oop-2025-proj-pycade/actions/workflows/deploy-to-web.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)


![遊戲截圖](https://github.com/user-attachments/assets/10f3a9b8-f6e1-4fa7-b980-8f0a47edc155)
![遊戲截圖2](https://github.com/user-attachments/assets/22ae902f-b236-4ef4-b3ba-3c1081ca4808)


本專案是物件導向程式設計 (OOP) 課程的期末成果，旨在使用 Python 與 Pygame 函式庫，複刻經典遊戲《瘋狂炸彈人》。我們不僅重現了核心的遊戲玩法，更將重點放在實踐優雅的軟體架構、智慧的 AI 設計，以及導入業界標準的開發流程。

---

## 🎮 線上試玩 (Live Demo)

您可以直接透過以下連結，在瀏覽器中體驗最新版本的遊戲，無需任何安裝！

**[➡️ 點擊這裡開始遊戲！](https://peienwu1216.github.io/oop-2025-proj-pycade/)**

---

## ✨ 專案亮點與實踐 (Key Features & Practices)

我們致力於讓這個專案不只是一個遊戲，更是一次完整的軟體工程實踐。其核心價值體現在：

* **實踐優雅的物件導向架構 (Elegant Architecture):**
    * 透過**繼承** (`GameObject` 作為基底)、**封裝** (`Manager` 類別) 與**策略模式** (`AIController`)，建立了清晰、可維護且易於擴充的程式碼基礎。

* **設計智慧的 AI 決策系統 (Intelligent AI):**
    * AI 對手並非隨機移動，而是結合了**有限狀態機 (FSM)** 來判斷當前局勢（追擊、逃跑、拾取道具），並使用 **A\* 演算法**來規劃出在複雜地圖中的最佳移動路徑。

* **採用專業的開發與協作流程 (Professional Workflow):**
    * 以 **GitHub Flow** 作為協作模型，利用 **Issue** 進行任務追蹤，並在 **Pull Request** 中進行嚴謹的 **Code Review**，確保了程式碼品質與團隊溝通效率。

* **建立完整的 CI/CD 自動化管線 (Automated CI/CD):**
    * 透過 **GitHub Actions**，我們建立了完整的自動化管線。當 Pull Request 被建立時，系統會自動執行 `flake8` 風格檢查與 `pytest` 單元測試。當程式碼成功合併到 `main` 分支後，會自動將遊戲打包並部署到 GitHub Pages。

* **複刻經典遊戲功能 (Classic Gameplay):**
    * 實現了包含多種 AI（攻擊型、保守型、道具優先型）、隨機地圖生成、道具系統與持久化本地排行榜等核心玩法。

---

## 📖 深入閱讀 (Further Reading)

這份 `README.md` 僅為專案摘要。如果您想深入了解我們的設計理念、開發歷程以及遇到的挑戰，我們強烈建議您閱讀我們發布在個人部落格上的完整文章：

* **[📄 專案開發全紀錄與技術剖析 (個人部落格)](https://peienwu-blog-next.vercel.app/pycade-bomber-ai-and-cicd)**

為了方便開發者，我們也將這份文件的副本歸檔在專案的 `docs/` 資料夾中，並提供了詳細的系統架構圖：

* **[📐 系統架構與 Class Diagram](ARCHITECTURE.md)**
* **[📝 文章歸檔 (於本倉庫)](docs/project-article.md)**
* 
---

## 📂 專案架構 (Project Structure)

```
.
├── .github/workflows/    # CI/CD 工作流設定
├── assets/               # 遊戲資源 (圖片, 音效, 數據)
├── core/                 # 核心邏輯 (AI, 場景, 系統管理)
├── docs/                 # 專案文件
├── sprites/              # 遊戲物件 (玩家, 炸彈等)
├── test/                 # 自動化單元測試
├── .gitignore
├── ARCHITECTURE.md       # 架構設計文件
├── CONTRIBUTING.md       # 貢獻指南
├── LICENSE
├── README.md             # 您正在閱讀的檔案
├── main.py               # 程式主進入點
└── requirements.txt      # Python 相依套件清單
```
---

## 🛠️ 安裝與執行 (Getting Started)

如果您想在自己的電腦上執行這個專案，請依照以下步驟操作。

### 必要條件

* Python 3.11+
* Git

### 安裝步驟

1.  **Clone 專案庫**
    ```bash
    git clone [https://github.com/peienwu1216/oop-2025-proj-pycade.git](https://github.com/peienwu1216/oop-2025-proj-pycade.git)
    cd oop-2025-proj-pycade
    ```

2.  **建立並啟用虛擬環境 (強烈建議)**
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate

    # macOS / Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **安裝相依套件**
    ```bash
    pip install -r requirements.txt
    ```

4.  **執行遊戲！**
    ```bash
    python main.py
    ```
---

## 🕹️ 如何遊玩 (How to Play)

* **移動:** `方向鍵` (↑ ↓ ← →) 或 `W`, `A`, `S`, `D` 鍵。
* **放置炸彈:** `F` 鍵。
* **退出/返回:** `ESC` 鍵。
* **重新開始:** 在遊戲結束畫面按下 `R` 鍵。

---

## 🧪 如何測試 (Testing)

本專案使用 `pytest` 進行單元測試。若要執行測試，請在專案根目錄下執行：

```bash
pytest
```
## 💻 使用的技術 (Tech Stack)

* **主要語言:** Python 3.11
* **遊戲引擎:** Pygame
* **測試框架:** Pytest, Pytest-mock
* **程式碼檢查:** Flake8
* **CI/CD:** GitHub Actions
* **網頁打包:** Pygbag

---

## 🤝 歡迎貢獻 (Contributing)

我們非常歡迎您為 Pycade Bomber 做出貢獻！無論是回報問題、提出新想法，還是直接貢獻程式碼。

請參考我們的 **[貢獻指南 (CONTRIBUTING.md)](CONTRIBUTING.md)** 來開始您的第一步。

---

## 📄 授權條款 (License)

本專案採用 [MIT License](LICENSE) 授權。