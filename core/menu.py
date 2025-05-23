# core/menu.py

import pygame
import settings

class Menu:
    """
    遊戲主選單，允許玩家選擇對戰的 AI 類型。
    """
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.is_running = True
        self.selected_ai_archetype = None

        # --- 字體設定 (增強錯誤處理) ---
        try:
            # 嘗試載入指定的中文字體
            self.title_font = pygame.font.Font(settings.CHINESE_FONT_PATH, 70)
            self.option_font = pygame.font.Font(settings.CHINESE_FONT_PATH, 45)
            self.description_font = pygame.font.Font(settings.CHINESE_FONT_PATH, 26)
            
            # 檢查字體是否成功載入 (沒有返回 None)
            if not self.title_font or not self.option_font or not self.description_font:
                # 如果有任何一個字體是 None，手動觸發一個錯誤以便進入 except 區塊
                raise pygame.error("Failed to load font, returned None.")

            print(f"成功載入中文字體: {settings.CHINESE_FONT_PATH}")

        except (pygame.error, FileNotFoundError) as e:
            print(f"警告：無法載入指定的中文字體 '{settings.CHINESE_FONT_PATH}': {e}")
            print("將退回使用系統預設字體，中文可能無法顯示。")
            # 如果找不到指定字體，退回到系統字體作為備案
            # 再次使用 try-except 以防系統字體也不存在
            try:
                self.title_font = pygame.font.SysFont('arial', 80)
                self.option_font = pygame.font.SysFont('arial', 50)
                self.description_font = pygame.font.SysFont('arial', 26)
            except pygame.error as e2:
                print(f"警告：連系統字體 'arial' 也無法載入: {e2}")
                # 絕對備案：使用 Pygame 預設字體
                self.title_font = pygame.font.Font(None, 80)
                self.option_font = pygame.font.Font(None, 50)
                self.description_font = pygame.font.Font(None, 26)

        # 從 settings.py 讀取 AI 選項
        self.ai_options = settings.AVAILABLE_AI_ARCHETYPES
        self.buttons = []
        self._create_buttons()

    def _create_buttons(self):
        """根據設定檔中的 AI 選項創建按鈕。"""
        start_y = 200
        button_spacing = 70
        
        for i, (display_name, archetype_key) in enumerate(self.ai_options.items()):
            y_pos = start_y + i * button_spacing
            button_rect = pygame.Rect(
                (settings.SCREEN_WIDTH - 350) // 2,
                y_pos,
                350,
                50
            )
            self.buttons.append({
                "rect": button_rect,
                "text": display_name,
                "archetype": archetype_key,
                "color": settings.GREY,
                "hover_color": (150, 150, 150)
            })

    def run(self):
        """運行選單主迴圈，返回玩家選擇的 AI 原型。"""
        while self.is_running:
            self.events()
            self.draw()
            self.clock.tick(settings.FPS)
        
        return self.selected_ai_archetype

    def events(self):
        """處理選單中的事件，如按鍵和滑鼠點擊。"""
        mouse_pos = pygame.mouse.get_pos()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
                self.selected_ai_archetype = None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.is_running = False
                    self.selected_ai_archetype = None
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    for button in self.buttons:
                        if button["rect"].collidepoint(mouse_pos):
                            self.selected_ai_archetype = button["archetype"]
                            self.is_running = False

    def draw(self):
        """繪製選單介面。"""
        self.screen.fill(settings.WHITE)
        
        # 繪製標題
        title_text = self.title_font.render(settings.TITLE, True, settings.BLACK)
        title_rect = title_text.get_rect(center=(settings.SCREEN_WIDTH / 2, 100))
        self.screen.blit(title_text, title_rect)
        
        description_text = self.description_font.render("Select AI Opponent", True, settings.GREY)
        description_rect = description_text.get_rect(center=(settings.SCREEN_WIDTH / 2, 150))
        self.screen.blit(description_text, description_rect)

        # 繪製按鈕
        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            is_hovering = button["rect"].collidepoint(mouse_pos)
            color = button["hover_color"] if is_hovering else button["color"]
            
            pygame.draw.rect(self.screen, color, button["rect"], border_radius=10)
            
            text_surface = self.option_font.render(button["text"], True, settings.BLACK)
            text_rect = text_surface.get_rect(center=button["rect"].center)
            self.screen.blit(text_surface, text_rect)
            
        pygame.display.flip()