# oop-2025-proj-pycade/sprites/item.py

import pygame
from .game_object import GameObject
import settings
import random # 我們將用它來隨機選擇道具類型

class Item(GameObject):
    """
    Base class for all collectible items.
    """
    def __init__(self, x_tile, y_tile, item_type, image_path, game_instance):
        super().__init__(
            x_tile * settings.TILE_SIZE,
            y_tile * settings.TILE_SIZE,
            settings.TILE_SIZE,
            settings.TILE_SIZE,
            image_path=image_path
        )
        self.type = item_type
        self.game = game_instance # 用於可能的音效等

    def apply_effect(self, player):
        """
        Applies the item's effect to the player.
        To be overridden by subclasses.
        Args:
            player (Player): The player who collected the item.
        """
        print(f"Item of type '{self.type}' collected by player, but apply_effect not implemented for base Item.")
        # 播放通用拾取音效
        # if self.game.sounds_enabled and settings.ITEM_COLLECT_SOUND:
        #     pygame.mixer.Sound(settings.ITEM_COLLECT_SOUND).play()
        self.kill() # 道具被拾取後消失

class ScoreItem(Item):
    """Increases player's score."""
    def __init__(self, x_tile, y_tile, game_instance):
        super().__init__(x_tile, y_tile, settings.ITEM_TYPE_SCORE, settings.ITEM_SCORE_IMG, game_instance)

    def apply_effect(self, player):
        player.score += settings.SCORE_ITEM_VALUE
        print(f"Player score +{settings.SCORE_ITEM_VALUE}! Total: {player.score}")
        super().apply_effect(player) # 播放音效和 self.kill()

class LifeItem(Item):
    """Increases player's lives."""
    def __init__(self, x_tile, y_tile, game_instance):
        super().__init__(x_tile, y_tile, settings.ITEM_TYPE_LIFE, settings.ITEM_LIFE_IMG, game_instance)

    def apply_effect(self, player):
        player.lives += 1
        player.score += settings.GENERIC_ITEM_SCORE_VALUE # 拾取功能性道具也加一點分 [cite: 3]
        print(f"Player lives +1! Total: {player.lives}. Score +{settings.GENERIC_ITEM_SCORE_VALUE}")
        super().apply_effect(player)

class BombCapacityItem(Item):
    """Increases player's maximum bomb capacity."""
    def __init__(self, x_tile, y_tile, game_instance):
        super().__init__(x_tile, y_tile, settings.ITEM_TYPE_BOMB_CAPACITY, settings.ITEM_BOMB_CAPACITY_IMG, game_instance)

    def apply_effect(self, player):
        player.max_bombs += 1
        player.score += settings.GENERIC_ITEM_SCORE_VALUE
        print(f"Player max bombs +1! Total: {player.max_bombs}. Score +{settings.GENERIC_ITEM_SCORE_VALUE}")
        super().apply_effect(player)

class BombRangeItem(Item):
    """Increases player's bomb explosion range."""
    def __init__(self, x_tile, y_tile, game_instance):
        super().__init__(x_tile, y_tile, settings.ITEM_TYPE_BOMB_RANGE, settings.ITEM_BOMB_RANGE_IMG, game_instance)

    def apply_effect(self, player):
        player.bomb_range += 1
        player.score += settings.GENERIC_ITEM_SCORE_VALUE
        print(f"Player bomb range +1! Total: {player.bomb_range}. Score +{settings.GENERIC_ITEM_SCORE_VALUE}")
        super().apply_effect(player)


# --- 函數：用於隨機創建一個道具 ---
def create_random_item(x_tile, y_tile, game_instance):
    """
    Randomly creates and returns an item instance based on defined probabilities.
    Returns None if no item is created (e.g., based on a general drop chance).
    """
    # 你的 C++ 報告中的道具生成機率:
    # 總掉落機率 80% (這個由 DestructibleWall 的 item_drop_chance 控制)
    # 在掉落的前提下，不同道具的機率:
    # 50% 加分 (SCORE_ITEM_VALUE)
    # 10% 加生命 (LIFE_ITEM)
    # 30% 加炸彈數 (BOMB_CAPACITY_ITEM)
    # 10% 加範圍 (BOMB_RANGE_ITEM)

    # 將百分比轉換為 0-1 之間的值
    prob_score = 0.50
    prob_life = 0.10
    prob_bomb_capacity = 0.30
    prob_bomb_range = 0.10 # 總和應為 1.0

    # 確保總和是 1 (或接近1，由於浮點數精度)
    # total_prob = prob_score + prob_life + prob_bomb_capacity + prob_bomb_range
    # assert 0.99 < total_prob < 1.01, f"Sum of item probabilities is not 1: {total_prob}"


    rand_val = random.random() # 生成一個 0.0 到 1.0 之間的隨機浮點數

    if rand_val < prob_score:
        return ScoreItem(x_tile, y_tile, game_instance)
    elif rand_val < prob_score + prob_life:
        return LifeItem(x_tile, y_tile, game_instance)
    elif rand_val < prob_score + prob_life + prob_bomb_capacity:
        return BombCapacityItem(x_tile, y_tile, game_instance)
    elif rand_val < prob_score + prob_life + prob_bomb_capacity + prob_bomb_range: # 或者直接 else
        return BombRangeItem(x_tile, y_tile, game_instance)
    
    return None # 理論上如果機率總和是1，不會到這裡，但作為保險