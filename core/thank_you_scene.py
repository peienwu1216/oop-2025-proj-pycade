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

    def update(self, events):
        """處理此場景的事件。"""
        for event in events:
            # 在這個感謝畫面，我們可以讓任何按鍵或滑鼠點擊都觸發真正的退出
            # 或者，您可以選擇不處理任何事件，讓畫面一直顯示
            if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                # 為了確保在網頁上點擊不會立即關閉 (因為關閉由使用者手動進行)
                # 我們可以選擇在這裡不做任何事，或者您可以設定一個計時器自動退出
                # 此處我們簡單地讓它保持顯示，使用者手動關閉分頁
                pass 

        # 這個場景會一直返回自己，直到使用者關閉瀏覽器分頁
        # 如果想讓它在一段時間後或按鍵後也結束 main.py 的迴圈，可以在這裡返回 "REAL_QUIT"
        # 例如：
        # if some_condition:
        #    return "REAL_QUIT" 
        return self 

    def draw(self):
        """繪製此場景。"""
        self.screen.fill(self.background_color)
        self.screen.blit(self.title_surf, self.title_rect)
        self.screen.blit(self.subtitle_surf, self.subtitle_rect)
        # pygame.display.flip() 由主迴圈 (main.py) 處理