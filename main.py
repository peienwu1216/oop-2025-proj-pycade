# oop-2025-proj-pycade/main.py

import pygame
from game import Game  # 我們很快會創建 game.py 和 Game 類
import settings

def main():
    """Main function to run the game."""
    pygame.init()  # 初始化 Pygame 的所有模組
    # pygame.mixer.init() # 如果要用音效，也初始化 mixer

    screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    pygame.display.set_caption(settings.TITLE)
    clock = pygame.time.Clock()

    game_instance = Game(screen, clock) # 創建 Game 物件的實例

    try:
        game_instance.run() # 運行遊戲主迴圈
    except Exception as e:
        print(f"An error occurred: {e}") # 簡單的錯誤處理
        # 在實際發布時，你可能需要更完善的錯誤日誌記錄
    finally:
        pygame.quit() # 結束遊戲時，反初始化 Pygame 模組
        # import sys # 如果需要確保完全退出
        # sys.exit()

if __name__ == '__main__':
    main()