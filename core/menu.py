# core/menu.py (REVISED FOR WEBGAME)

import pygame
import settings
from core.leaderboard_manager import LeaderboardManager

button_width = 200
button_height = 50

class Menu:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        
        # 【修改】不再需要 is_running 和 selected_ai_archetype
        # self.is_running = True
        # self.selected_ai_archetype = None
        
        self.background_image = pygame.image.load(settings.MENU_BACKGROUND_IMG).convert()
        self.background_image = pygame.transform.scale(self.background_image, (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
        
        # (圖片載入部分保持不變...)
        self.ai_light_button_image = pygame.image.load(settings.MENU_AI_LIGHT_BUTTON_IMG).convert_alpha()
        self.ai_light_button_image = pygame.transform.smoothscale(self.ai_light_button_image, (int(self.ai_light_button_image.get_size()[0] * (button_height / self.ai_light_button_image.get_size()[1])), button_height))
        self.ai_light_button_hover_image = pygame.image.load(settings.MENU_AI_LIGHT_BUTTON_HOVER_IMG).convert_alpha()
        self.ai_light_button_hover_image = pygame.transform.smoothscale(self.ai_light_button_hover_image, (int(self.ai_light_button_image.get_size()[0] * (button_height / self.ai_light_button_image.get_size()[1])), button_height))
        self.ai_blue_button_image = pygame.image.load(settings.MENU_AI_BLUE_BUTTON_IMG).convert_alpha()
        self.ai_blue_button_image = pygame.transform.smoothscale(self.ai_blue_button_image, (int(self.ai_blue_button_image.get_size()[0] * (button_height / self.ai_blue_button_image.get_size()[1])), button_height))
        self.ai_blue_button_hover_image = pygame.image.load(settings.MENU_AI_BLUE_BUTTON_HOVER_IMG).convert_alpha()
        self.ai_blue_button_hover_image = pygame.transform.smoothscale(self.ai_blue_button_hover_image, (int(self.ai_blue_button_image.get_size()[0] * (button_height / self.ai_blue_button_image.get_size()[1])), button_height))

        self.menu_state = "MAIN"
        self.leaderboard_manager = LeaderboardManager()

        # (字體設定部分保持不變...)
        try:
            font_path = settings.CHINESE_FONT_PATH
            self.title_font = pygame.font.Font(settings.TITLE_FONT_PATH, 70)
            self.option_font = pygame.font.Font(font_path, 30)
            self.description_font = pygame.font.Font(settings.SUB_TITLE_FONT_PATH, 24)
            self.leaderboard_text_font = pygame.font.Font(font_path, 22)
            self.leaderboard_header_font = pygame.font.Font(settings.SUB_TITLE_FONT_PATH, 24)
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
        # (此函式保持不變)
        self.buttons = []
        start_y = 180
        button_spacing = 60
        
        for i, (display_name, archetype_key) in enumerate(self.ai_options.items()):
            y_pos = start_y + i * button_spacing
            button_rect = pygame.Rect(
                (settings.SCREEN_WIDTH - self.ai_light_button_image.get_size()[0]) // 2, y_pos, self.ai_light_button_image.get_size()[0], self.ai_light_button_image.get_size()[1]
            )
            self.buttons.append({
                "rect": button_rect, "text": display_name, "action_type": "SELECT_AI",
                "archetype": archetype_key
            })

        leaderboard_y_pos = start_y + len(self.ai_options) * button_spacing + button_spacing // 2
        leaderboard_rect = pygame.Rect(
            (settings.SCREEN_WIDTH - self.ai_blue_button_image.get_size()[0]) // 2, leaderboard_y_pos, self.ai_blue_button_image.get_size()[0], self.ai_blue_button_image.get_size()[1]
        )
        self.buttons.append({
            "rect": leaderboard_rect, "text": "排行榜 (Leaderboard)", "action_type": "SHOW_LEADERBOARD",
        })
        
        quit_y_pos = leaderboard_y_pos + button_spacing
        quit_rect = pygame.Rect(
            (settings.SCREEN_WIDTH - self.ai_blue_button_hover_image.get_size()[0]) // 2, quit_y_pos, self.ai_blue_button_hover_image.get_size()[0], self.ai_blue_button_hover_image.get_size()[1]
        )
        self.buttons.append({
            "rect": quit_rect, "text": "退出遊戲 (Quit)", "action_type": "QUIT_GAME",
        })

    # 【修改】run() 方法被移除，改為 update() 和 draw()
    def update(self, events):
        """處理一幀的事件和邏輯，並返回下一個場景或指令。"""
        mouse_pos = pygame.mouse.get_pos()
        
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.menu_state == "LEADERBOARD":
                        self.menu_state = "MAIN"
                        self._create_buttons()
                    elif self.menu_state == "MAIN":
                        return "QUIT" # 返回一個指令來退出
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    click_position = event.pos # 使用事件提供的點擊位置
                    
                    if self.menu_state == "MAIN":
                        for button in self.buttons:
                            if button["rect"].collidepoint(click_position): # 使用 click_position 進行碰撞檢測
                                action = button.get("action_type")
                                if action == "SELECT_AI":
                                    # 返回一個新的 Game 物件作為下一個場景
                                    from game import Game
                                    game = Game(self.screen, self.clock, ai_archetype=button["archetype"])
                                    game.start_timer()
                                    return game
                                elif action == "SHOW_LEADERBOARD":
                                    self.menu_state = "LEADERBOARD"
                                elif action == "QUIT_GAME":
                                    return "QUIT" # 返回退出指令
                                break 
        
        return self # 預設情況下，返回自己，表示繼續留在這個場景

    def draw(self):
        """只負責繪製。"""
        self.screen.blit(self.background_image, (0, 0))
        
        if self.menu_state == "MAIN":
            self.draw_main_menu_content()
        elif self.menu_state == "LEADERBOARD":
            self.draw_leaderboard_content()
            
        # 注意：pygame.display.flip() 由主迴圈 (main.py) 呼叫

    def draw_main_menu_content(self):
        # (此函式保持不變...)
        title_text = self.title_font.render(settings.TITLE, True, settings.WHITE)
        title_rect = title_text.get_rect(center=(settings.SCREEN_WIDTH / 2, 80))
        self.screen.blit(title_text, title_rect)
        
        description_text = self.description_font.render("Select AI Opponent or View Leaderboard", True, settings.LIGHT_BROWN)
        description_rect = description_text.get_rect(center=(settings.SCREEN_WIDTH / 2, 140))
        self.screen.blit(description_text, description_rect)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons[:-2]:
            is_hovering = button["rect"].collidepoint(mouse_pos)
            button_image = self.ai_light_button_hover_image if is_hovering else self.ai_light_button_image
            self.screen.blit(button_image, button["rect"])
            
            text_surface = self.option_font.render(button["text"], True, settings.BLACK)
            text_rect = text_surface.get_rect(center=(button["rect"].centerx, button["rect"].centery-3))
            self.screen.blit(text_surface, text_rect)
        for button in self.buttons[-2:]:
            is_hovering = button["rect"].collidepoint(mouse_pos)
            button_image = self.ai_blue_button_hover_image if is_hovering else self.ai_blue_button_image
            self.screen.blit(button_image, button["rect"])
            
            text_surface = self.option_font.render(button["text"], True, settings.BLACK)
            text_rect = text_surface.get_rect(center=(button["rect"].centerx, button["rect"].centery-3))
            self.screen.blit(text_surface, text_rect)


    def draw_leaderboard_content(self):
        # (此函式保持不變...)
        # === 1. 背景圖片 ===
        bg_image = pygame.image.load(settings.MENU_BACKGROUND_IMG).convert()
        bg_image = pygame.transform.scale(bg_image, (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
        self.screen.blit(bg_image, (0, 0))

        # === 2. 半透明白色覆蓋層 ===
        overlay = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, 200))  # 半透明白色 (alpha = 200)
        self.screen.blit(overlay, (0, 0))
        lb_title_surf = self.title_font.render("Leaderboard", True, (16, 39, 54))
        lb_title_rect = lb_title_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, 70))
        self.screen.blit(lb_title_surf, lb_title_rect)

        scores = self.leaderboard_manager.get_scores()
        start_y = 150
        line_height = 30
        headers = ["Rank", "Name", "Score", "Defeated AI", "Date"]
        header_positions = [
            ("Rank", 100), ("Name", 200), ("Score", 320), 
            ("Defeated AI", 450), ("Date", 630)
        ]

        for i, header_text in enumerate(headers):
            header_surf = self.leaderboard_header_font.render(header_text, True, settings.BLACK)
            header_rect = header_surf.get_rect(centerx=header_positions[i][1], y=start_y)
            if header_text == "Rank": header_rect.left = 50
            elif header_text == "Score": header_rect.centerx = 240
            elif header_text == "Name": header_rect.left = 120
            elif header_text == "Defeated AI": header_rect.centerx = 550
            elif header_text == "Date": header_rect.centerx = settings.SCREEN_WIDTH - 100
            self.screen.blit(header_surf, header_rect)
        
        current_y = start_y + line_height * 1.5

        if not scores:
            no_scores_surf = self.option_font.render("No scores recorded yet!", True, settings.GREY)
            no_scores_rect = no_scores_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2))
            self.screen.blit(no_scores_surf, no_scores_rect)
        else:
            max_score = max(entry.get('score', 1) for entry in scores) or 1
            bar_max_width = 200
            bar_height = 20
            for i, entry in enumerate(scores):
                rank = str(i + 1)
                name = entry.get('name', 'N/A')
                score = str(entry.get('score', 0))
                score_val = entry.get('score', 0)
                ai_archetype_key = entry.get('ai_defeated', 'N/A')
                date = entry.get('date', 'N/A').split(" ")[0]
                ai_display_name = ai_archetype_key
                if hasattr(settings, 'AVAILABLE_AI_ARCHETYPES'):
                    for display, key_in_settings in settings.AVAILABLE_AI_ARCHETYPES.items():
                        if key_in_settings == ai_archetype_key:
                            ai_display_name = display
                            break
                bar_length = int((score_val / max_score) * bar_max_width)
                bar_rect = pygame.Rect(260+5, current_y+8, bar_length, bar_height)
                pygame.draw.rect(self.screen, (32, 80, 103), bar_rect)


                entry_data = [rank, name, score, ai_display_name, date]
                for col, data_text in enumerate(entry_data):
                    data_surf = self.leaderboard_text_font.render(data_text, True, settings.BLACK)
                    data_rect = data_surf.get_rect(y=current_y)
                    if col == 0: data_rect.left = 50
                    elif col == 1: data_rect.left = 120
                    elif col == 2: data_rect.centerx = 240
                    elif col == 3: data_rect.centerx = 550
                    elif col == 4: data_rect.centerx = settings.SCREEN_WIDTH - 100
                    self.screen.blit(data_surf, data_rect)
                current_y += line_height

        back_instructions_surf = self.description_font.render("Press ESC to return to Main Menu", True, settings.BLACK)
        back_instructions_rect = back_instructions_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT - 50))
        self.screen.blit(back_instructions_surf, back_instructions_rect)