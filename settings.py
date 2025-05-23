# oop-2025-proj-pycade/settings.py

# Screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Colors (R, G, B)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
GREY = (128, 128, 128)

# Game Title
TITLE = "Pycade Bomber"

# Map settings
TILE_SIZE = 32
# （1）！！！ 確認 Player Sprite Sheet 中的單幀寬高設定，這些在 Player class 中會被使用 ！！！（1）
PLAYER_SPRITE_FRAME_WIDTH = 32  # 玩家 Sprite Sheet 中單幀的寬度
PLAYER_SPRITE_FRAME_HEIGHT = 32 # 玩家 Sprite Sheet 中單幀的高度
# （1）！！！ 確認結束 ！！！（1）


# Player settings
MAX_LIVES = 3
INITIAL_BOMBS = 1
INITIAL_BOMB_RANGE = 1


PLAYER_ANIMATION_SPEED = 0.1  # 秒/幀，值越小動畫越快
PLAYER_NUM_WALK_FRAMES = 6    # 假設每個方向的行走動畫有6幀 (需要與你的 sprite sheet 匹配)
PLAYER_VISUAL_SCALE_FACTOR = 0.85 # 角色視覺縮放比例，1.0 為不縮放


# （3）！！！ 新增或確認 Player 移動與碰撞相關設定 ！！！（3）
# Hitbox 縮減量 (可以是絕對像素值，或相對於 PLAYER_SPRITE_FRAME_WIDTH/HEIGHT 的比例)
# 這裡使用絕對像素值作為例子，你可以根據需要調整
PLAYER_HITBOX_WIDTH_REDUCTION = 10 # Hitbox 寬度比 PLAYER_SPRITE_FRAME_WIDTH 小多少像素
PLAYER_HITBOX_HEIGHT_REDUCTION = 10 # Hitbox 高度比 PLAYER_SPRITE_FRAME_HEIGHT 小多少像素
# 或者，你也可以像 Player class 之前那樣，直接用比例來定義 hitbox 大小，例如：
# PLAYER_HITBOX_SCALE = 0.7 # Hitbox 是視覺大小的 70% (若使用此方式，Player class 中的 hitbox 計算需對應調整)

# 格子移動動畫持續時間 (秒)
HUMAN_GRID_MOVE_ACTION_DURATION = 0.2
AI_GRID_MOVE_ACTION_DURATION = 0.2   # AI 移動可以慢一點，方便觀察

# 受傷無敵時間 (毫秒)
PLAYER_INVINCIBLE_DURATION = 1000 
# （3）！！！ 新增或確認結束 ！！！（3）

DESTRUCTIBLE_WALL_CHANCE = 0.5


import os

# Asset paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
IMAGES_DIR = os.path.join(ASSETS_DIR, "images")
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds") 
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")   
DATA_DIR = os.path.join(ASSETS_DIR, "data")     

# Image specific paths
WALL_SOLID_IMG = os.path.join(IMAGES_DIR, "walls", "wall_solid_placeholder.png")
WALL_DESTRUCTIBLE_IMG = os.path.join(IMAGES_DIR, "walls", "wall_destructible_placeholder.png")
PLAYER_IMG = os.path.join(IMAGES_DIR, "player", "player_placeholder.png") # 備用圖片路徑
BOMB_IMG = os.path.join(IMAGES_DIR, "bomb", "bomb_placeholder.png")
ITEM_SCORE_IMG = os.path.join(IMAGES_DIR, "items", "item_score_placeholder.png")
ITEM_LIFE_IMG = os.path.join(IMAGES_DIR, "items", "item_life_placeholder.png")
ITEM_BOMB_CAPACITY_IMG = os.path.join(IMAGES_DIR, "items", "item_bomb_capacity_placeholder.png")
ITEM_BOMB_RANGE_IMG = os.path.join(IMAGES_DIR, "items", "item_bomb_range_placeholder.png")
# Explosion Image Path (新增或修改)
EXPLOSION_PARTICLE_IMG = os.path.join(IMAGES_DIR, "explosion", "explosion_particle.png") # 假設您的圖片名和路徑

# Item Types
ITEM_TYPE_SCORE = "score"
ITEM_TYPE_LIFE = "life"
ITEM_TYPE_BOMB_CAPACITY = "bomb_capacity"
ITEM_TYPE_BOMB_RANGE = "bomb_range"

ITEM_DROP_WEIGHTS = {
    ITEM_TYPE_LIFE: 30,            # 生命值道具的權重，例如從 10 增加到 30
    ITEM_TYPE_BOMB_CAPACITY: 20,   # 炸彈容量道具的權重 (保持或略微調整)
    ITEM_TYPE_BOMB_RANGE: 10,      # 爆炸範圍道具的權重，例如從 20 降低到 10
    ITEM_TYPE_SCORE: 40            # 分數道具的權重 (可以設為較常見)
    # 如果你還有其他道具類型，也應該在這裡加入它們的權重
}
# 牆壁被摧毀時掉落道具的總體機率 (0.0 到 1.0)
# 你可能已經在 DestructibleWall 中有一個 item_drop_chance，
# 如果要在 settings.py 中統一控制，可以新增這個，然後在 DestructibleWall 中使用它
WALL_ITEM_DROP_CHANCE = 0.8 # 例如，80% 的可破壞牆壁被炸後會掉落道具

# Item settings
SCORE_ITEM_VALUE = 50
GENERIC_ITEM_SCORE_VALUE = 20

# --- Player Sprite Sheet paths ---
PLAYER1_SPRITESHEET_PATH = os.path.join(IMAGES_DIR, "player", "player.png") 
PLAYER2_AI_SPRITESHEET_PATH = os.path.join(IMAGES_DIR, "player", "player2.png") 

# Sprite sheet row mapping for animations
PLAYER_SPRITESHEET_ROW_MAP = {
    "DOWN": 3,
    "RIGHT": 4,
    "UP": 5,
    # "LEFT" will be derived by flipping "RIGHT"
}

# Bomb settings
BOMB_TIMER = 3000  
EXPLOSION_DURATION = 300  
USE_EXPLOSION_IMAGES = True # 改為 False 則使用顏色方塊
EXPLOSION_COLOR = (255, 165, 0) 

# AI Settings
AI_MOVE_DELAY = 200       
AI_OPPONENT_ARCHETYPE = "aggressive" # 可以是 "original", "conservative", "aggressive", "item_focused"

AI_ENGAGE_MIN_DIST_TO_PLAYER_FOR_DIRECT_PATH = 2 # 在 ENGAGE 狀態下，如果與玩家距離小於此值，AI會重新考慮直接走向玩家的策略
AI_EVASION_SAFETY_CHECK_FUTURE_SECONDS = 0.3  # EVADING_DANGER 狀態下，判斷當前格子是否"真的"安全時的預判時間
AI_RETREAT_SPOT_OTHER_DANGER_FUTURE_SECONDS = 1.5 # 尋找撤退點時，評估該點是否受其他已存在威脅影響的預判時間
AI_CLOSE_QUARTERS_BOMB_CHANCE = 0.6 # 在近距離且無法移動時，AI 嘗試放置炸彈的機率 (0.0 至 1.0)
AI_ENGAGE_MIN_DIST_TO_PLAYER_FOR_DIRECT_PATH = 2
AI_EVASION_SAFETY_CHECK_FUTURE_SECONDS = 0.3
AI_RETREAT_SPOT_OTHER_DANGER_FUTURE_SECONDS = 1.5
AI_CLOSE_QUARTERS_BOMB_CHANCE = 0.6 # 近距離無法移動時，嘗試放置炸彈的機率
AI_OSCILLATION_STUCK_THRESHOLD = 3 # 振盪多少次後認為卡住

# AI Conservative State Settings
AI_CONSERVATIVE_RETREAT_DEPTH = 8
AI_CONSERVATIVE_MIN_RETREAT_OPTIONS = 3
AI_CONSERVATIVE_EVASION_URGENCY_MULTIPLIER = 1.5 # 用於 is_tile_dangerous 的 future_seconds

 # Aggressive 狀態下，AI 在巡邏時等待玩家的時間 (毫秒)