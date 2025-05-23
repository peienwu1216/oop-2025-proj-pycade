# oop-2025-proj-pycade/main.py

import pygame
from game import Game
from core.menu import Menu
import settings

def main():
    """Main function to run the game."""
    pygame.init()
    # 正常情況下 pygame.init() 會處理好所有模組的初始化
    # 如果您遇到了特定的字體問題，可以取消註解下一行
    # pygame.font.init() 
    # pygame.mixer.init()

    screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    pygame.display.set_caption(settings.TITLE)
    clock = pygame.time.Clock()

    # --- 建立一個主應用程式迴圈 ---
    app_running = True
    while app_running:
        # 1. 創建並運行選單
        # 在迴圈內創建 Menu，確保每次都顯示一個新的選單
        menu = Menu(screen)
        selected_ai = menu.run()

        # 2. 檢查玩家是否在選單中途退出 (例如按 ESC 或關閉視窗)
        if selected_ai is None:
            app_running = False # 結束主應用程式迴圈
            continue # 進入下一次迴圈檢查，然後退出

        # 3. 如果玩家做了選擇，則創建並運行遊戲實例
        game_instance = Game(screen, clock, ai_archetype=selected_ai)
        
        # 4. game_instance.run() 現在會返回一個布林值
        #    True 表示玩家按 R 想回到選單
        #    False 表示玩家按 ESC 或關閉視窗想完全退出
        should_return_to_menu = game_instance.run()

        # 5. 如果 game_instance 返回 False，則結束主應用程式迴圈
        if not should_return_to_menu:
            app_running = False
    
    # --- 迴圈結束後，退出 Pygame ---
    pygame.quit()

if __name__ == '__main__':
    main()