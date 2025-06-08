# core/thank_you_scene.py

import pygame
import settings # 用於取得顏色和螢幕尺寸等設定
# from core.menu import Menu # 如果要加「返回選單」按鈕才需要

class ThankYouScene:
    def __init__(self, screen, audio_manager):
        self.screen = screen
        self.audio_manager = audio_manager
        self.font_color = settings.THANK_YOU_FONT_COLOR
        self.background_color = settings.THANK_YOU_BG_COLOR # 您可以選擇一個不同的背景色

        self.audio_manager.play_music(settings.THANKS_YOU_PATH)
        try:
            # 嘗試使用您在 settings.py 中定義的字體路徑
            # 您可以選擇一個適合的字體，例如主選單的 option_font 或 description_font
            font_path = settings.SUB_TITLE_FONT_PATH # 或者使用其他字體路徑
            self.title_font_size = 48
            self.subtitle_font_size = 28
            self.title_font = pygame.font.Font(font_path, self.title_font_size)
            self.subtitle_font = pygame.font.Font(font_path, self.subtitle_font_size)
        except Exception as e:
            print(f"ThankYouScene Font Error: {e}. Falling back to default.")
            self.title_font = pygame.font.Font(None, 60) # 備用字體
            self.subtitle_font = pygame.font.Font(None, 30)

        self.message_text = "Thank you for playing!"
        self.instruction_text = "Please close this browser tab to exit."

        # 計算文字位置 (只計算一次，以提升效能)
        self.title_surf = self.title_font.render(self.message_text, True, self.font_color)
        self.title_rect = self.title_surf.get_rect(center=(settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2 - 40))

        self.subtitle_surf = self.subtitle_font.render(self.instruction_text, True, settings.GREY) # 副標題用灰色
        self.subtitle_rect = self.subtitle_surf.get_rect(center=(settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2 + 20))

        # 【新增】一個旗標，用來告訴 main.py 是否要真正結束應用程式
        self.request_app_quit = False

    def update(self, events, dt):
        """
        處理感謝場景的事件。
        目前只監聽是否有任何按鍵或點擊，以觸發退出。
        """
        for event in events:
            # 偵測到任何按鍵或滑鼠點擊，就設定退出旗標
            if event.type == pygame.QUIT or \
               event.type == pygame.KEYDOWN or \
               event.type == pygame.MOUSEBUTTONDOWN:
                self.request_app_quit = True
                break # 找到一個就夠了

        # 返回 self 表示繼續停留在這個場景
        # main.py 的主迴圈會檢查 request_app_quit 旗標
        return self

    def draw(self):
        """繪製此場景。"""
        self.screen.fill(self.background_color)
        self.screen.blit(self.title_surf, self.title_rect)
        self.screen.blit(self.subtitle_surf, self.subtitle_rect)
        # pygame.display.flip() 由主迴圈 (main.py) 處理