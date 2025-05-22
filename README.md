# Pycade Bomber (瘋狂炸彈人 Pygame 複刻版)

https://hackmd.io/@peienwu/SJr3Yhd-gl

本專案是物件導向程式設計 (OOP) 課程專案 (oop-2025-proj-pycade)，旨在使用 Pygame 函式庫複刻經典遊戲《瘋狂炸彈人》(Crazy Arcade/Bomberman)。目前的開發目標是完成一個功能相對完善、包含單人對戰 AI 的本地端可執行版本，並為未來可能的擴展（如更複雜的 AI 演算法、強化學習訓練、使用 Pygbag 進行網頁化部署）打下良好基礎。

## 目錄

- [Pycade Bomber (瘋狂炸彈人 Pygame 複刻版)](#pycade-bomber-瘋狂炸彈人-pygame-複刻版)
  - [目錄](#目錄)
  - [目前狀態與版本資訊](#目前狀態與版本資訊)
  - [環境設定與執行](#環境設定與執行)
    - [前置需求](#前置需求)
    - [安裝依賴](#安裝依賴)
    - [執行遊戲](#執行遊戲)
  - [遊戲控制](#遊戲控制)
  - [專案架構](#專案架構)
  - [後續優化與開發方向 (致組員)](#後續優化與開發方向-致組員)
    - [優先任務：提升 AI 智慧與遊戲性](#優先任務提升-ai-智慧與遊戲性)
    - [遊戲體驗與功能擴充](#遊戲體驗與功能擴充)
    - [程式碼與專案管理](#程式碼與專案管理)
    - [長期目標思考](#長期目標思考)

## 目前狀態與版本資訊

* **專案版本 (Tag 建議)**：`v0.3.1-ai-astar-bfs` (表示已實現瞬時格子移動，AI 採用 A* 和 BFS 進行路徑規劃與戰術決策)
* **核心功能實現**：
    * 玩家角色 (人類與AI) 採用**瞬時格子移動**系統，位置離散化 (`player.py` - `tile_x`, `tile_y`, `attempt_move_to_tile`)。
    * 人類玩家可透過鍵盤控制移動（按住方向鍵可持續移動，一格接一格，有動作動畫） (`player.py` - `get_input`, `_animate`)。
    * AI 玩家由 `AIController` 控制，基於 A* 演算法進行宏觀路徑規劃，BFS 演算法進行局部移動路徑搜索 (`core/ai_controller.py`)。
    * 基本的炸彈放置機制 (`player.py` - `place_bomb`, `sprites/bomb.py`)。 炸彈在玩家離開該格後變為固態障礙物 (`sprites/bomb.py` - `owner_has_left_tile`, `is_solidified`)。
    * 炸彈爆炸產生火焰，可摧毀可破壞的牆壁 (`sprites/bomb.py` - `explode`, `sprites/explosion.py`, `sprites/wall.py` - `DestructibleWall.take_damage`)。
    * 基本的道具系統 (分數、生命、炸彈容量、炸彈威力)，道具由牆壁被炸毀時根據設定機率隨機掉落 (`sprites/item.py`, `sprites/wall.py` - `try_drop_item`, `settings.py` - `ITEM_DROP_WEIGHTS`, `WALL_ITEM_DROP_CHANCE`)。
    * 隨機地圖生成，包含不可破壞的固定牆壁和可隨機分佈的可破壞牆壁，並設有玩家初始安全區 (`core/map_manager.py` - `get_randomized_map_layout`)。 `MapManager` 會在牆壁被炸毀時更新地圖數據 (`core/map_manager.py` - `update_tile_char_on_map`)。
    * AI 對手基於有限狀態機 (FSM) 進行決策，包括 `PLANNING_PATH_TO_PLAYER`, `EXECUTING_PATH_CLEARANCE` (炸牆開路), `TACTICAL_RETREAT_AND_WAIT`, `ENGAGING_PLAYER`, `EVADING_DANGER`, `CLOSE_QUARTERS_COMBAT` 等狀態 (`core/ai_controller.py`)。
    * AI 具備危險評估 (`is_tile_dangerous`) 和安全撤退邏輯 (`find_safe_tiles_nearby_for_retreat`, `can_place_bomb_and_retreat`)。
    * AI 包含卡住檢測 (單點停滯和振盪) 以嘗試觸發重新規劃 (`core/ai_controller.py` - `decision_cycle_stuck_counter`, `oscillation_stuck_counter`)。
    * 遊戲界面 HUD 可顯示玩家的基本狀態資訊（生命、炸彈、威力、分數、AI 當前狀態） (`game.py` - `draw` method)。
    * 基本的遊戲流程控制，包括遊戲結束判斷 (任一方玩家生命為零) 與重新開始功能 (`game.py` - `update`, `events`)。
    * 玩家和 AI 會受到爆炸傷害 (`game.py` - `update` collision checks, `player.py` - `take_damage`)。
    * 玩家（包括AI）無法直接穿過已放置且固化的炸彈，但允許剛放置炸彈的玩家離開該格 (`player.py` - `attempt_move_to_tile`)。

* **已知主要待辦事項 / 問題點**：
    * **AI 行為**：
        * AI 執行「放置炸彈開路」 (`EXECUTING_PATH_CLEARANCE` 狀態) 的策略時，儘管 `_find_optimal_bombing_and_retreat_spot` 和 `can_place_bomb_and_retreat` 可能成功找到計畫，實際放置炸彈的頻率和效率可能仍需根據遊戲體驗進行調優。 需要持續觀察 AI 在複雜地圖下清除障礙以達成目標（如追擊玩家或到達玩家初始點）的整體表現。
        * AI 的整體「智慧感」、情境感知 (situational awareness) 和行為多樣性有很大的提升空間。例如，更精細的道具價值判斷、對玩家行為的預測等。
        * AI 在複雜危險環境下的逃生路徑選擇 (`handle_evading_danger_state`) 及執行穩定性可能需要進一步測試和強化。
    * **人類玩家體驗**：
        * 持續按鍵移動的「手感」（例如，`HUMAN_GRID_MOVE_ACTION_DURATION` 的值）可能需要進一步微調以達到最佳體驗。
    * **遊戲內容**：
        * `sprites/item.py` 中的道具效果實現已更新，各子類有自己的 `apply_effect` 邏輯並調用基類的通用處理（如加分、銷毀自身）。 之前的關於基類日誌提示問題已透過重構解決。
    * **程式碼與資源**：
        * 部分資源檔案路徑在 `settings.py` 中仍使用預留位置 (placeholder) 命名 (e.g., `WALL_SOLID_IMG`, `BOMB_IMG`)。
        * 音效部分尚未整合 (`main.py` 中的 `pygame.mixer.init()` 被註解，`settings.py` 中有 `SOUNDS_DIR` 但尚無實際音效調用邏輯)。
        * AI 控制器中的 `ai_log` 函數為自定義的簡易日誌，未來可考慮替換為 Python `logging` 模組以獲得更強大的日誌管理功能。

## 環境設定與執行

### 前置需求

* Python 3.x (建議 3.8 或更高版本)
* pip (Python 套件安裝器)
* Git (用於版本控制與協作)

### 安裝依賴

1.  使用 Git 克隆 (Clone) 此專案到您的本地電腦：
    ```bash
    git clone <repository_url>
    cd oop-2025-proj-pycade
    ```
2.  (強烈建議) 在專案目錄下建立並啟用一個 Python 虛擬環境，以隔離專案依賴：
    ```bash
    python -m venv venv
    # Windows:
    # venv\Scripts\activate
    # Linux/macOS:
    # source venv/bin/activate
    ```
3.  安裝必要的 Python 套件 (主要為 Pygame):
    ```bash
    pip install -r requirements.txt
    ```

### 執行遊戲

在專案根目錄下，使用 Python 直譯器執行 `main.py`:
```bash
python3 main.py
```
## 遊戲控制

* **人類玩家 (Player 1)**：
    * **移動**：方向鍵 (上、下、左、右) 或 W、A、S、D 鍵。按住可持續一格格移動。
    * **放置炸彈**：F 鍵。
* **遊戲通用**：
    * **退出遊戲**：ESC 鍵。
    * **重新開始** (遊戲結束後)：R 鍵。

## 專案架構

本專案採用模組化的結構，主要包含以下幾個部分：

* **`main.py`**: 遊戲的入口點，初始化 Pygame、創建 `Game` 物件並開始遊戲主循環。
* **`settings.py`**: 存放遊戲的全域設定，如螢幕尺寸、幀率、顏色定義、圖片與資源路徑、遊戲機制參數（例如炸彈威力、玩家動作持續時間、AI決策間隔、道具掉落機率等）。
* **`game.py`**: 包含核心的 `Game` 類別。
    * 負責管理遊戲的主循環、處理遊戲事件（鍵盤輸入）、更新遊戲狀態（所有精靈更新、碰撞檢測、遊戲邏輯判斷）、繪製遊戲畫面。
    * 管理遊戲中的各類精靈群組 (`pygame.sprite.Group`)。
    * 初始化並管理 `MapManager` 和 `AIController`。
* **`core/` 目錄**: 包含遊戲的核心機制和管理器。
    * `ai_controller.py` (`AIController` 類別): 實現 AI 玩家的決策邏輯。
        * 基於有限狀態機 (FSM) 設計，包含多種狀態 (如 `PLANNING_PATH_TO_PLAYER`, `EXECUTING_PATH_CLEARANCE`, `ENGAGING_PLAYER`, `EVADING_DANGER`, `CLOSE_QUARTERS_COMBAT` 等)。
        * 使用 A* 演算法 (`astar_find_path`) 進行戰略路徑規劃，廣度優先搜索 (BFS) (`bfs_find_direct_movement_path`) 進行局部移動和安全路徑查找。
        * 包含複雜的危險評估 (`is_tile_dangerous`, `_is_tile_in_hypothetical_blast`) 和安全判斷邏輯 (`can_place_bomb_and_retreat`, `find_safe_tiles_nearby_for_retreat`)。
        * AI 的移動請求是向其控制的 `Player` 物件發出 `attempt_move_to_tile` 指令。
        * 包含針對卡死情況的檢測機制 (單點停滯 `decision_cycle_stuck_counter` 和振盪 `oscillation_stuck_counter`)。
    * `map_manager.py` (`MapManager` 類別): 負責地圖的載入、生成（包括隨機佈置可破壞牆壁，並考慮玩家初始安全區）、以及提供地圖資訊查詢（如某格子是否可走、是否為固定牆）和更新地圖狀態（如牆壁被摧毀）。
* **`sprites/` 目錄**: 包含遊戲中所有可見或可互動的物件（精靈）的類別定義。所有精靈都繼承自 `game_object.py` 中的 `GameObject` 基類。
    * `bomb.py` (`Bomb` 類別): 定義炸彈的行為，包括計時、爆炸 (`explode`)、火焰蔓延邏輯（基於格子和炸彈威力）。 其位置由格子座標決定。 包含 `owner_has_left_tile` 和 `is_solidified` 邏輯，影響其碰撞特性。
    * `explosion.py` (`Explosion` 類別): 代表炸彈爆炸時產生的單格火焰效果，有持續時間。 其位置由格子座標決定。
    * `game_object.py` (`GameObject` 類別): 提供所有遊戲物件共享的基礎屬性（如 `image`, `rect`）和方法。
    * `item.py` (`Item` 基類及各道具子類如 `ScoreItem`, `LifeItem` 等): 定義各種道具及其被玩家拾取時產生的效果 (`apply_effect`)。 道具的位置基於格子。 道具的生成由 `DestructibleWall` 中的 `try_drop_item` 方法調用 `create_random_item` 函數控制，後者根據 `settings.py` 中的權重隨機選擇道具類型。
    * `player.py` (`Player` 類別): 定義玩家角色（可為人類或AI）。
        * 核心位置由 `tile_x`, `tile_y` (格子座標) 表示。
        * 實現了瞬時格子移動邏輯 (`attempt_move_to_tile(dx, dy)`)，該方法會檢查目標格子的有效性（邊界、牆壁、其他炸彈、其他玩家）。
        * 移動後有短暫的 `action_timer` 控制 `is_moving` 狀態，用於播放行走動畫。 人類和 AI 的 `ACTION_ANIMATION_DURATION` 可以分別設定 (`settings.py`)。
        * 人類玩家的持續移動由 `get_input()` (在 `update` 中呼叫，基於 `pygame.key.get_pressed()`) 結合 `action_timer` 實現。
        * 動畫處理 (`_animate`)。
        * 生命與傷害管理 (`take_damage`, `die`)。
        * 炸彈放置 (`place_bomb`) 基於當前格子位置，並檢查該格是否已有其他炸彈或玩家。
    * `wall.py` (`Wall`, `DestructibleWall` 類別): 定義不可破壞的牆壁和可被炸彈摧毀的牆壁。 位置基於格子。 可破壞牆壁在被摧毀時有一定機率掉落道具，並會通知 `MapManager` 更新地圖數據。
* **`assets/` 目錄**: 存放所有遊戲資源檔案，如圖片、未來可能加入的音效和字型等。 建議按資源類型分子目錄管理 (e.g., `images/player/`, `images/bomb/`)。
* **`requirements.txt`**: 列出專案運行的 Python 依賴套件，主要為 `pygame`。
* **`README.md`**: 本檔案，提供專案的說明和指引。

這種結構使得不同功能的程式碼分離，易於理解、維護和擴展。

## 後續優化與開發方向 (致組員)

以下是針對本專案下一階段的開發建議和可優化方向。目前的版本已經實現了核心的格子移動和具備多種策略狀態的 AI 行為，但仍有很大的打磨和擴展空間。

### 優先任務：遊戲體驗與功能擴充
> [!CAUTION]
> 優先任務：完成UI優化（遊戲目錄、玩法種類如單人對戰、雙人對戰、地圖多樣性、隨機地圖、地圖大小、玩家造型等等）

1.  **遊戲選單與設置界面**：
    * 實現一個基本的開始畫面、遊戲模式選擇（目前是人對AI，未來可擴展為人對人、AI對AI）、難度選擇（可調整 AI 的 `AI_MOVE_DELAY`, `AI_GRID_MOVE_ACTION_DURATION` 或其他行為參數如 `AI_CLOSE_QUARTERS_BOMB_CHANCE`）。
    * 考慮加入簡單的遊戲說明或控制提示。

2.  **音效與視覺打磨**：
    * **整合音效**：逐步加入背景音樂、角色移動音效、炸彈放置/爆炸音效、道具拾取音效、受傷音效、遊戲勝利/失敗音效等。
    * **視覺效果優化**：
        * 優化角色動畫 (`player.py` - `_animate`)，使其行走、放置炸彈、受傷等動作更平滑自然。
        * 增強爆炸動畫效果 (`sprites/explosion.py`)，使其更具視覺衝擊力。
        * 道具出現和拾取的視覺提示。

3.  **遊戲內容豐富度**：
    * **多樣化地圖**：設計更多具有不同特色、障礙物佈局和策略記憶點的地圖。可以考慮加入一些特殊的地圖元素。目前的 `MapManager` 支持從字符佈局加載地圖。
    * **新道具類型**：引入更多種類的道具 (`sprites/item.py` 的擴展)，例如增加移動速度的鞋子、可以踢炸彈的道具、可以穿牆的幽靈藥水、遙控炸彈、穿透炸彈（可以炸毀一排可破壞物）等。

4.  **`Item.apply_effect` 日誌**：
    * 此問題在原 README 中被提及。目前 `sprites/item.py` 的結構是：基類 `Item` 的 `apply_effect` 負責通用邏輯 (如為非分數道具加分和 `self.kill()`)，各道具子類實現自己的特定效果和日誌輸出，然後選擇性調用 `super().apply_effect()`。 這種結構看起來是合理的。原先的「未為基類實現」的日誌問題已不存在。

### 提升 AI 智慧與遊戲性

5.  **[核心] 強化 AI 炸牆策略與執行力**：
    * **目標**：讓 AI 更智能、更可靠地透過放置炸彈來清除障礙 (`EXECUTING_PATH_CLEARANCE` 狀態)，以達成其目標（攻擊玩家、獲取道具、或自我解困）。
    * **目前情況**：AI 能夠規劃炸毀 A* 路徑上的可破壞牆壁，並能計算轟炸點和安全撤退點 (`_find_optimal_bombing_and_retreat_spot`, `can_place_bomb_and_retreat`)。
    * **建議行動**：
        * **觀察與調優**：大量測試 AI 在不同地圖和情境下炸牆的實際表現。如果 AI 在需要炸牆時猶豫不決或選擇不佳，需深入檢查 `ai_controller.py` 中 `handle_executing_path_clearance_state` 的決策條件、安全參數 (`AI_RETREAT_SPOT_OTHER_DANGER_FUTURE_SECONDS`) 和路徑成本計算。
        * **牆壁價值評估**：`_find_optimal_bombing_and_retreat_spot` 中的邏輯可以考慮更精細的牆壁價值，例如，優先炸掉那些能開闢通往高價值目標（玩家、強力道具）的路徑的牆壁，或者能一次炸開多個可破壞物的牆。
        * **"進退兩難時的決斷"**：考慮在 AI 被困很久或有極高價值目標被擋住時，是否能引入一種機制，讓 AI 在評估後可適度承擔更高風險來執行關鍵炸牆。

6.  **提升 AI 戰術多樣性與反應能力**：
    * **目標**：讓 AI 的行為更難預測，更能適應戰場變化。
    * **建議行動**：
        * **攻擊策略 (`ENGAGING_PLAYER`, `CLOSE_QUARTERS_COMBAT`)**：
            * 除了追擊和近身纏鬥，能否利用牆角進行伏擊？
            * 能否更精準預判玩家可能的移動方向來放置預置炸彈？
            * 當玩家被困時，AI 是否能更有效地利用炸彈封鎖玩家？目前的 `_is_tile_in_hypothetical_blast` 僅判斷是否在爆炸範圍。
        * **防禦策略 (`EVADING_DANGER`)**：
            * AI 目前會尋找安全點躲避 (`find_safe_tiles_nearby_for_retreat`)。 是否可以考慮更主動的防禦，如用自己的炸彈反制或引爆對手炸彈（高風險）？
        * **狀態切換優化**：持續檢視 `AIController` 中各狀態的轉換條件和優先級，避免 AI 在某些狀態間不必要地頻繁切換或長時間卡在某個無效的中間狀態。目前的卡死檢測 (`decision_cycle_stuck_counter`, `oscillation_stuck_counter`) 有助於跳出循環。

7.  **完善 AI 的環境感知與互動**：
    * **目標**：讓 AI 更好地理解地圖佈局和場上動態元素。
    * **建議行動**：
        * **火焰鏈反應**：AI 目前的危險評估 (`is_tile_dangerous`) 主要考慮單個炸彈的即將爆炸。 是否應讓 AI 預估連鎖爆炸的可能性？
        * **躲避預判**：AI 的 `is_tile_dangerous` 和 `_is_tile_in_hypothetical_blast` 提供了基礎。 可進一步優化 AI 選擇最佳躲避路線和時機的精準度。
        * **對其他 AI 的感知 (若未來有多AI)**：需要考慮 AI 之間的協同或競爭行為。

### 程式碼與專案管理

8.  **持續的程式碼註解與文檔化**：
    * 為所有重要模組、類別、方法和複雜邏輯段添加清晰的中文註解。
    * 保持 `README.md` 的更新。

9.  **日誌系統優化**：
    * 目前 `core/ai_controller.py` 中使用 `ai_log` 函數和 `AI_DEBUG_MODE` 進行調試輸出。 強烈建議逐步遷移到使用 Python 內建的 `logging` 模組，以便更好地控制日誌級別、格式和輸出目標。

10. **版本控制與協作**：
    * 熟練使用 Git 的基本操作。
    * 撰寫清晰、有意義的 commit message。
    * 對於較大的功能修改或重構，建議新建特性分支。
    * 定期與組員同步進度。

### 長期目標思考

11. **強化學習 AI 接口**：
    * 目前的格子化移動系統 (`player.py`) 和 AI 狀態機 (`core/ai_controller.py`) 為將來引入強化學習 AI 奠定了良好基礎。
    * 需要進一步思考：狀態表示、動作空間、獎勵函數的設計。

12. **Pygbag 網頁化部署**：
    * 在後續開發中，持續關注資源檔案的路徑管理 (`settings.py` 中已使用 `os.path.join`)，確保與 Pygbag 的打包方式兼容。
    * 避免使用 Pygame 中可能與網頁環境不兼容的特定模組或功能。
