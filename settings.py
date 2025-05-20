# oop-2025-proj-pycade/settings.py

# Screen dimensions
SCREEN_WIDTH = 800  # 寬度 (像素) - 你可以根據你的 C++ 版本調整或先用一個常用值
SCREEN_HEIGHT = 600 # 高度 (像素)
FPS = 60             # Frames Per Second - 遊戲的目標幀率

# Colors (R, G, B)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
GREY = (128, 128, 128)

# Game Title
TITLE = "Pycade Bomber"

# Map settings (之後會更詳細)
TILE_SIZE = 32 # 每個格子的像素大小，可以根據你的喜好調整

# Initial game settings (可以從你的 C++ Globals.cpp 參考)
# 例如：
# DEFAULT_MAP_WIDTH = 21
# DEFAULT_MAP_HEIGHT = 21
# MAX_LIVES = 3
# INITIAL_BOMBS = 1
# INITIAL_BOMB_RANGE = 3

# Player settings
# PLAYER_SPEED = 5 # 像素/幀

# (更多設定會在這裡添加)