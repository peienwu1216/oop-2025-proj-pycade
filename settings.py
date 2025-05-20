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
PLAYER_SPRITE_FRAME_WIDTH = 32  # 玩家 Sprite Sheet 中單幀的寬度
PLAYER_SPRITE_FRAME_HEIGHT = 32 # 玩家 Sprite Sheet 中單幀的高度

# Initial game settings (可以從你的 C++ Globals.cpp 參考)
# 例如：
# DEFAULT_MAP_WIDTH = 21
# DEFAULT_MAP_HEIGHT = 21
# MAX_LIVES = 3
# INITIAL_BOMBS = 1
# INITIAL_BOMB_RANGE = 3

# Player settings
PLAYER_SPEED = 2         # 玩家移動速度 (像素/幀)
MAX_LIVES = 3
INITIAL_BOMBS = 2        # 初始可放置炸彈數
INITIAL_BOMB_RANGE = 1   # 炸彈初始範圍 (格子數) - 你C++是3，可以調整

# Player controls (for reference, actual input handled in Player class)
# P1_UP = pygame.K_w (Pygame key constants)
# P1_DOWN = pygame.K_s
# P1_LEFT = pygame.K_a
# P1_RIGHT = pygame.K_d
# P1_BOMB = pygame.K_f

import os # 為了處理路徑

# Asset paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # 專案根目錄
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
IMAGES_DIR = os.path.join(ASSETS_DIR, "images")
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds") # 預留
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")   # 預留
DATA_DIR = os.path.join(ASSETS_DIR, "data")     # 預留

# Image specific paths
WALL_SOLID_IMG = os.path.join(IMAGES_DIR, "walls", "wall_solid_placeholder.png")
WALL_DESTRUCTIBLE_IMG = os.path.join(IMAGES_DIR, "walls", "wall_destructible_placeholder.png")
PLAYER_IMG = os.path.join(IMAGES_DIR, "player", "player_placeholder.png")
BOMB_IMG = os.path.join(IMAGES_DIR, "bomb", "bomb_placeholder.png")
ITEM_SCORE_IMG = os.path.join(IMAGES_DIR, "items", "item_score_placeholder.png")
ITEM_LIFE_IMG = os.path.join(IMAGES_DIR, "items", "item_life_placeholder.png")
ITEM_BOMB_CAPACITY_IMG = os.path.join(IMAGES_DIR, "items", "item_bomb_capacity_placeholder.png")
ITEM_BOMB_RANGE_IMG = os.path.join(IMAGES_DIR, "items", "item_bomb_range_placeholder.png")

# Item Types (用字串來標識道具類型)
ITEM_TYPE_SCORE = "score"
ITEM_TYPE_LIFE = "life"
ITEM_TYPE_BOMB_CAPACITY = "bomb_capacity"
ITEM_TYPE_BOMB_RANGE = "bomb_range"

# Item settings
SCORE_ITEM_VALUE = 50 # 參考你的 C++ 報告，加分道具增加 50 分 [cite: 3]
# 其他道具增加 20 分 [cite: 3]
GENERIC_ITEM_SCORE_VALUE = 20

# --- 玩家 Sprite Sheet 設定 ---
# 假設 P1 和 AI 使用不同的 sprite sheet，如果相同，則路徑可以一樣
PLAYER1_SPRITESHEET_PATH = os.path.join(IMAGES_DIR, "player", "player.png") # !!! 你的 player1 sprite sheet 路徑 !!!
PLAYER2_AI_SPRITESHEET_PATH = os.path.join(IMAGES_DIR, "player", "player2.png") # !!! 你的 player2 sprite sheet 路徑 !!!

# 動畫參數
PLAYER_ANIMATION_SPEED = 0.1  # 秒/幀，值越小動畫越快 (例如 0.1 秒切換一幀)
PLAYER_NUM_WALK_FRAMES = 6    # !!! 每個方向的行走動畫有多少幀 !!!

# Sprite sheet 中各方向動畫行的索引 (從0開始)
# 根據你的 constant.py: DOWN=row3, RIGHT=row4, UP=row5
PLAYER_SPRITESHEET_ROW_MAP = {
    "DOWN": 3,
    "RIGHT": 4,
    "UP": 5,
    # "LEFT" is derived by flipping "RIGHT"
}

# 如果你有炸彈動畫幀，可以像這樣定義一個列表:
# BOMB_ANIM_FRAMES = [
#     os.path.join(IMAGES_DIR, "bomb", "bomb_tick_0.png"),
#     os.path.join(IMAGES_DIR, "bomb", "bomb_tick_1.png"),
# ]

# ... (之後會添加更多圖片路徑) ...

# Bomb settings
BOMB_TIMER = 3000  # 炸彈爆炸前的毫秒數 (3 秒)
EXPLOSION_DURATION = 500  # 爆炸效果持續的毫秒數 (0.5 秒)
EXPLOSION_COLOR = (255, 165, 0) # 橘色，用於繪製爆炸效果
# 如果使用圖片，可以在這裡定義路徑:
# EXPLOSION_CENTER_IMG = os.path.join(IMAGES_DIR, "explosion", "explosion_center.png")
# EXPLOSION_SEGMENT_IMG = os.path.join(IMAGES_DIR, "explosion", "explosion_segment.png") # 假設水平垂直用同一種

# AI Settings
AI_MOVE_DELAY = 200       # AI "思考"或主要決策的間隔毫秒數 (0.2秒)
                          # 你的 C++ 版本有 AI_MOVE_DELAY = 4 (easy) 或 2 (hard)
                          # 這可能是指遊戲幀而不是毫秒，需要確認。
                          # Pygame 中用毫秒更常見。
AI_PLAYER_SPEED_FACTOR = 0.8 # AI 玩家可以比人類玩家稍慢或一樣快