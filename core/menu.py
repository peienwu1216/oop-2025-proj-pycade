# core/menu.py

import pygame
import settings
from core.leaderboard_manager import LeaderboardManager # 匯入排行榜管理器

button_width = 200
button_height = 50

class Menu:
    """
    遊戲主選單，允許玩家選擇對戰的 AI 類型，並查看排行榜。
    """
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.is_running = True
        self.selected_ai_archetype = None # 用於返回給 main.py
        
        self.background_image = pygame.image.load(settings.MENU_BACKGROUND_IMG).convert()
        self.background_image = pygame.transform.scale(self.background_image, (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
        
        self.ai_light_button_image = pygame.image.load(settings.MENU_AI_LIGHT_BUTTON_IMG).convert_alpha()
        self.ai_light_button_image = pygame.transform.smoothscale(self.ai_light_button_image, (int(self.ai_light_button_image.get_size()[0] * (button_height / self.ai_light_button_image.get_size()[1])), button_height))
        self.ai_light_button_hover_image = pygame.image.load(settings.MENU_AI_LIGHT_BUTTON_HOVER_IMG).convert_alpha()
        self.ai_light_button_hover_image = pygame.transform.smoothscale(self.ai_light_button_hover_image, (int(self.ai_light_button_image.get_size()[0] * (button_height / self.ai_light_button_image.get_size()[1])), button_height))
        self.ai_blue_button_image = pygame.image.load(settings.MENU_AI_BLUE_BUTTON_IMG).convert_alpha()
        self.ai_blue_button_image = pygame.transform.smoothscale(self.ai_blue_button_image, (int(self.ai_blue_button_image.get_size()[0] * (button_height / self.ai_blue_button_image.get_size()[1])), button_height))
        self.ai_blue_button_hover_image = pygame.image.load(settings.MENU_AI_BLUE_BUTTON_HOVER_IMG).convert_alpha()
        self.ai_blue_button_hover_image = pygame.transform.smoothscale(self.ai_blue_button_hover_image, (int(self.ai_blue_button_image.get_size()[0] * (button_height / self.ai_blue_button_image.get_size()[1])), button_height))
        
        
        # --- 新增：選單狀態 ---
        self.menu_state = "MAIN"  # "MAIN" 或 "LEADERBOARD"

        # --- 新增：LeaderboardManager 實例 ---
        self.leaderboard_manager = LeaderboardManager()

        # 字體設定 (假設您已解決了字體問題，這裡沿用之前的設定)
        try:
            font_path = settings.CHINESE_FONT_PATH
            self.title_font = pygame.font.Font(settings.TITLE_FONT_PATH, 70)
            self.option_font = pygame.font.Font(font_path, 30)
            self.description_font = pygame.font.Font(settings.SUB_TITLE_FONT_PATH, 26)
            self.leaderboard_text_font = pygame.font.Font(font_path, 22) # 排行榜內容字體
            self.leaderboard_header_font = pygame.font.Font(font_path, 24) # 排行榜標頭字體
        except Exception as e:
            print(f"Menu Font Error: {e}. Falling back to default.")
            self.title_font = pygame.font.Font(None, 80)
            self.option_font = pygame.font.Font(None, 50)
            self.description_font = pygame.font.Font(None, 26)
            self.leaderboard_text_font = pygame.font.Font(None, 24)
            self.leaderboard_header_font = pygame.font.Font(None, 26)
            
        self.ai_options = settings.AVAILABLE_AI_ARCHETYPES
        self.buttons = []
        self._create_buttons()

    def _create_buttons(self):
        """根據設定檔中的 AI 選項和附加按鈕創建按鈕。"""
        self.buttons = [] # 清空按鈕，以便在狀態切換時重新創建（如果需要）
        
        
        start_y = 180
        button_spacing = 60
        
        

        # 1. AI 選擇按鈕
        for i, (display_name, archetype_key) in enumerate(self.ai_options.items()):
            y_pos = start_y + i * button_spacing
            button_rect = pygame.Rect(
                (settings.SCREEN_WIDTH - self.ai_light_button_image.get_size()[0]) // 2, y_pos, self.ai_light_button_image.get_size()[0], self.ai_light_button_image.get_size()[1]
            )
            # self.buttons.append({
            #     "rect": button_rect, "text": display_name, "action_type": "SELECT_AI",
            #     "archetype": archetype_key, "color": settings.GREY, "hover_color": (150, 150, 150)
            # })
            self.buttons.append({
                "rect": button_rect, "text": display_name, "action_type": "SELECT_AI",
                "archetype": archetype_key
            })

        # 2. 排行榜按鈕 (加在 AI 選項下方)
        leaderboard_y_pos = start_y + len(self.ai_options) * button_spacing + button_spacing // 2 # 留一些額外間距
        leaderboard_rect = pygame.Rect(
            (settings.SCREEN_WIDTH - self.ai_blue_button_image.get_size()[0]) // 2, leaderboard_y_pos, self.ai_blue_button_image.get_size()[0], self.ai_blue_button_image.get_size()[1]
        )
        self.buttons.append({
            "rect": leaderboard_rect, "text": "排行榜 (Leaderboard)", "action_type": "SHOW_LEADERBOARD",
            #"color": settings.BLUE, "hover_color": (100, 100, 255) # 給排行榜按鈕不同顏色
        })
        
        # 3. (可選) 退出遊戲按鈕
        quit_y_pos = leaderboard_y_pos + button_spacing
        quit_rect = pygame.Rect(
            (settings.SCREEN_WIDTH - self.ai_blue_button_hover_image.get_size()[0]) // 2, quit_y_pos, self.ai_blue_button_hover_image.get_size()[0], self.ai_blue_button_hover_image.get_size()[1]
        )
        self.buttons.append({
            "rect": quit_rect, "text": "退出遊戲 (Quit)", "action_type": "QUIT_GAME",
            #"color": settings.RED, "hover_color": (255, 100, 100)
        })


    def run(self):
        """運行選單主迴圈，返回玩家選擇的 AI 原型或 None (如果直接退出)。"""
        self.is_running = True # 確保每次運行選單都是 active 狀態
        self.selected_ai_archetype = None # 重置選擇
        
        # 當從排行榜返回主選單時，重新創建按鈕，確保它們是主選單的按鈕
        if self.menu_state != "MAIN":
            self.menu_state = "MAIN"
        self._create_buttons() # 確保主選單按鈕被創建

        while self.is_running:
            self.events()
            self.draw()
            self.clock.tick(settings.FPS)
        
        return self.selected_ai_archetype

    def events(self):
        """處理選單中的事件。"""
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
                self.selected_ai_archetype = None # 透過關閉視窗退出
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.menu_state == "LEADERBOARD":
                        self.menu_state = "MAIN" # 從排行榜返回主選單
                        self._create_buttons() # 重新創建主選單按鈕
                    elif self.menu_state == "MAIN":
                        self.is_running = False # 在主選單按 ESC 則退出
                        self.selected_ai_archetype = None
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # 左鍵點擊
                    if self.menu_state == "MAIN":
                        for button in self.buttons:
                            if button["rect"].collidepoint(mouse_pos):
                                action = button.get("action_type")
                                if action == "SELECT_AI":
                                    self.selected_ai_archetype = button["archetype"]
                                    self.is_running = False # 選擇 AI 後退出選單迴圈
                                elif action == "SHOW_LEADERBOARD":
                                    self.menu_state = "LEADERBOARD"
                                    # 不需要重新創建按鈕，因為排行榜畫面有自己的繪製邏輯
                                elif action == "QUIT_GAME":
                                    self.is_running = False
                                    self.selected_ai_archetype = None # 表示退出遊戲
                                break 
                    elif self.menu_state == "LEADERBOARD":
                        # 可以在排行榜畫面也加上可點擊的返回按鈕
                        # 為了簡化，目前只用 ESC 返回
                        pass

    def draw(self):
        """根據目前的選單狀態繪製對應的介面。"""
        # self.screen.fill(settings.WHITE)
        self.screen.blit(self.background_image, (0, 0))
        
        if self.menu_state == "MAIN":
            self.draw_main_menu_content()
        elif self.menu_state == "LEADERBOARD":
            self.draw_leaderboard_content()
            
        pygame.display.flip()

    def draw_main_menu_content(self):
        """繪製主選單的內容 (AI選擇、排行榜按鈕等)。"""
        # 繪製標題
        title_text = self.title_font.render(settings.TITLE, True, settings.WHITE)
        title_rect = title_text.get_rect(center=(settings.SCREEN_WIDTH / 2, 80)) # 稍微上移標題
        self.screen.blit(title_text, title_rect)
        
        description_text = self.description_font.render("Select AI Opponent or View Leaderboard", True, settings.GREY)
        description_rect = description_text.get_rect(center=(settings.SCREEN_WIDTH / 2, 140))
        self.screen.blit(description_text, description_rect)

        # 繪製按鈕
        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons[:-2]: # self.buttons 此時應包含 AI 選項和排行榜按鈕
            is_hovering = button["rect"].collidepoint(mouse_pos)
            # color = button["hover_color"] if is_hovering else button["color"]
            
            # pygame.draw.rect(self.screen, color, button["rect"], border_radius=10)
            button_image = self.ai_light_button_hover_image if is_hovering else self.ai_light_button_image
            self.screen.blit(button_image, button["rect"])
            
            text_surface = self.option_font.render(button["text"], True, settings.BLACK)
            text_rect = text_surface.get_rect(center=(button["rect"].centerx, button["rect"].centery-3))
            self.screen.blit(text_surface, text_rect)
        for button in self.buttons[-2:]: # self.buttons 此時應包含 AI 選項和排行榜按鈕
            is_hovering = button["rect"].collidepoint(mouse_pos)
            # color = button["hover_color"] if is_hovering else button["color"]
            
            # pygame.draw.rect(self.screen, color, button["rect"], border_radius=10)
            button_image = self.ai_blue_button_hover_image if is_hovering else self.ai_blue_button_image
            self.screen.blit(button_image, button["rect"])
            
            text_surface = self.option_font.render(button["text"], True, settings.BLACK)
            text_rect = text_surface.get_rect(center=(button["rect"].centerx, button["rect"].centery-3))
            self.screen.blit(text_surface, text_rect)

    def draw_leaderboard_content(self):
        """繪製排行榜介面。"""
        self.screen.fill((230, 230, 250)) # 給排行榜一個不同的背景色
        


        # 排行榜標題
        lb_title_surf = self.title_font.render("Leaderboard", True, settings.BLACK)
        lb_title_rect = lb_title_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, 70))
        self.screen.blit(lb_title_surf, lb_title_rect)

        scores = self.leaderboard_manager.get_scores()
        
        start_y = 150
        line_height = 30 # 排行榜行高
        column_paddings = [50, 200, 350, 500, 650] # 各列的起始X座標 (粗略)
        
        # 繪製表頭
        headers = ["Rank", "Name", "Score", "Defeated AI", "Date"]
        header_positions = [
            ("Rank", 100), ("Name", 200), ("Score", 320), 
            ("Defeated AI", 450), ("Date", 630)
        ]

        for i, header_text in enumerate(headers):
            header_surf = self.leaderboard_header_font.render(header_text, True, settings.BLACK)
            header_rect = header_surf.get_rect(centerx=header_positions[i][1], y=start_y)
            # 根據文字內容調整對齊，例如 Rank 可以靠左，Score 可以靠右
            if header_text == "Rank": header_rect.left = 50
            elif header_text == "Score": header_rect.centerx = 300
            elif header_text == "Name": header_rect.left = 120
            elif header_text == "Defeated AI": header_rect.centerx = 450
            elif header_text == "Date": header_rect.centerx = settings.SCREEN_WIDTH - 150

            self.screen.blit(header_surf, header_rect)
        
        current_y = start_y + line_height * 1.5 # 資料從表頭下方開始

        if not scores:
            no_scores_surf = self.option_font.render("No scores recorded yet!", True, settings.GREY)
            no_scores_rect = no_scores_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2))
            self.screen.blit(no_scores_surf, no_scores_rect)
        else:
            for i, entry in enumerate(scores):
                rank = str(i + 1)
                name = entry.get('name', 'N/A')
                score = str(entry.get('score', 0))
                
                # 將 AI archetype 轉換為顯示名稱 (如果 settings 中有定義)
                ai_archetype_key = entry.get('ai_defeated', 'N/A')
                ai_display_name = ai_archetype_key # 預設值
                if hasattr(settings, 'AVAILABLE_AI_ARCHETYPES'):
                    for display, key_in_settings in settings.AVAILABLE_AI_ARCHETYPES.items():
                        if key_in_settings == ai_archetype_key:
                            ai_display_name = display
                            break
                
                date = entry.get('date', 'N/A').split(" ")[0] # 只顯示日期部分

                entry_data = [rank, name, score, ai_display_name, date]
                for col, data_text in enumerate(entry_data):
                    data_surf = self.leaderboard_text_font.render(data_text, True, settings.BLACK)
                    data_rect = data_surf.get_rect(y=current_y)
                    # 根據表頭位置對齊
                    if col == 0: data_rect.left = 50 # Rank
                    elif col == 1: data_rect.left = 120 # Name
                    elif col == 2: data_rect.centerx = 300 # Score
                    elif col == 3: data_rect.centerx = 450 # AI Type
                    elif col == 4: data_rect.centerx = settings.SCREEN_WIDTH - 150 # Date
                    
                    self.screen.blit(data_surf, data_rect)
                current_y += line_height

        # 返回提示
        back_instructions_surf = self.description_font.render("Press ESC to return to Main Menu", True, settings.BLACK)
        back_instructions_rect = back_instructions_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT - 50))
        self.screen.blit(back_instructions_surf, back_instructions_rect)