# oop-2025-proj-pycade/sprites/item.py

import pygame
from .game_object import GameObject
import settings
import random # 我們將用它來隨機選擇道具類型

class Item(GameObject):
    """
    Base class for all collectible items.
    """
    # （1）！！！ 修改 Item 的 __init__ 以允許 image_path 為 None，並在子類中設定預設值 ！！！（1）
    # 或者，讓 create_random_item 傳遞正確的 image_path，但更常見的是子類知道自己的圖片
    def __init__(self, x_tile, y_tile, item_type, game_instance, image_path=None, score_value=0):
        # 如果 image_path 未提供，則嘗試從 settings 中根據 item_type 獲取
        # 這段邏輯更適合放在各個子類的 __init__ 中，或者由 create_random_item 決定
        if image_path is None:
            if item_type == settings.ITEM_TYPE_SCORE:
                image_path = settings.ITEM_SCORE_IMG
            elif item_type == settings.ITEM_TYPE_LIFE:
                image_path = settings.ITEM_LIFE_IMG
            elif item_type == settings.ITEM_TYPE_BOMB_CAPACITY:
                image_path = settings.ITEM_BOMB_CAPACITY_IMG
            elif item_type == settings.ITEM_TYPE_BOMB_RANGE:
                image_path = settings.ITEM_BOMB_RANGE_IMG
            else: # 如果類型未知或未設定圖片，提供一個備用圖片
                  # 為了安全，最好確保所有類型都有對應圖片路徑在 settings.py
                print(f"[Item Init Warning] No specific image_path for item_type '{item_type}'. Using a default or potentially erroring.")
                # Fallback, or raise error if image_path must be set
                image_path = settings.ITEM_SCORE_IMG # Example fallback

        super().__init__(
            x_tile * settings.TILE_SIZE,
            y_tile * settings.TILE_SIZE,
            settings.TILE_SIZE,
            settings.TILE_SIZE,
            image_path=image_path
        )
        self.type = item_type
        self.game = game_instance
        # （1）！！！ 修改結束 ！！！（1）

        # 拾取道具時給予的基礎分數，除非是純分數道具
        self.score_value = score_value if score_value > 0 else getattr(settings, "GENERIC_ITEM_SCORE_VALUE", 10)
        if self.type == settings.ITEM_TYPE_SCORE: # 純分數道具使用其特定值
             self.score_value = getattr(settings, "SCORE_ITEM_VALUE", 50)


    def apply_effect(self, player):
        """
        Applies the item's effect to the player.
        To be overridden by subclasses for specific effects,
        but base class handles scoring and removal.
        """
        # （2）！！！ 修改：將 print 移到子類，基類只處理通用邏輯 ！！！（2）
        # print(f"Item of type '{self.type}' collected by player, but apply_effect not implemented for base Item.")
        
        # 通用邏輯：拾取非純分數道具時，也增加一點分數
        if self.type != settings.ITEM_TYPE_SCORE:
            player.score += self.score_value 
            print(f"Player picked up {self.type}, score +{self.score_value}. Total score: {player.score}")
        
        # 播放通用拾取音效 (如果啟用了音效)
        # if hasattr(self.game, 'sounds_enabled') and self.game.sounds_enabled and \
        #    hasattr(settings, 'ITEM_COLLECT_SOUND') and settings.ITEM_COLLECT_SOUND:
        #     try:
        #        pygame.mixer.Sound(settings.ITEM_COLLECT_SOUND).play()
        #     except Exception as e:
        #        print(f"Error playing item collect sound: {e}")
        
        self.kill() # 道具被拾取後消失
        # （2）！！！ 修改結束 ！！！（2）

class ScoreItem(Item):
    """Increases player's score."""
    def __init__(self, x_tile, y_tile, game_instance):
        # （3）！！！ 修改：直接在子類中傳遞 image_path 和 item_type ！！！（3）
        super().__init__(x_tile, y_tile, settings.ITEM_TYPE_SCORE, game_instance, image_path=settings.ITEM_SCORE_IMG, score_value=settings.SCORE_ITEM_VALUE)
        # （3）！！！ 修改結束 ！！！（3）

    def apply_effect(self, player):
        # 分數增加邏輯已移至 Item 基類的 __init__ (self.score_value) 和 apply_effect (純分數道具的特殊處理)
        # 但純分數道具的分數增加應在此處明確處理，不依賴 GENERIC_ITEM_SCORE_VALUE
        player.score += self.score_value # self.score_value 在 __init__ 中已設為 SCORE_ITEM_VALUE
        print(f"Player score +{self.score_value}! Total: {player.score}")
        # 不再需要呼叫 super().apply_effect(player) 來增加 GENERIC_ITEM_SCORE_VALUE
        # 只需呼叫基類的 kill()
        self.kill() # 或 super().kill() 如果 GameObject 有 kill

class LifeItem(Item):
    """Increases player's lives."""
    def __init__(self, x_tile, y_tile, game_instance):
        super().__init__(x_tile, y_tile, settings.ITEM_TYPE_LIFE, game_instance, image_path=settings.ITEM_LIFE_IMG)

    def apply_effect(self, player):
        player.lives += 1
        print(f"Player lives +1! Total: {player.lives}.")
        super().apply_effect(player) # 基類處理通用分數增加和 kill

class BombCapacityItem(Item):
    """Increases player's maximum bomb capacity."""
    def __init__(self, x_tile, y_tile, game_instance):
        super().__init__(x_tile, y_tile, settings.ITEM_TYPE_BOMB_CAPACITY, game_instance, image_path=settings.ITEM_BOMB_CAPACITY_IMG)

    def apply_effect(self, player):
        player.max_bombs += 1
        print(f"Player max bombs +1! Total: {player.max_bombs}.")
        super().apply_effect(player) # 基類處理通用分數增加和 kill

class BombRangeItem(Item):
    """Increases player's bomb explosion range."""
    def __init__(self, x_tile, y_tile, game_instance):
        super().__init__(x_tile, y_tile, settings.ITEM_TYPE_BOMB_RANGE, game_instance, image_path=settings.ITEM_BOMB_RANGE_IMG)

    def apply_effect(self, player):
        player.bomb_range += 1
        print(f"Player bomb range +1! Total: {player.bomb_range}.")
        super().apply_effect(player) # 基類處理通用分數增加和 kill


# --- 函數：用於隨機創建一個道具 ---
def create_random_item(x_tile, y_tile, game_instance):
    item_types = list(settings.ITEM_DROP_WEIGHTS.keys())
    weights = list(settings.ITEM_DROP_WEIGHTS.values())

    if not item_types or not weights or sum(weights) == 0:
        print("[ItemCreation] Warning: ITEM_DROP_WEIGHTS in settings is empty or all weights are zero. No item will drop.")
        return None

    chosen_item_type = random.choices(item_types, weights=weights, k=1)[0]

    # （4）！！！ 修改：根據 chosen_item_type 實例化對應的道具子類 ！！！（4）
    if chosen_item_type == settings.ITEM_TYPE_SCORE:
        return ScoreItem(x_tile, y_tile, game_instance)
    elif chosen_item_type == settings.ITEM_TYPE_LIFE:
        return LifeItem(x_tile, y_tile, game_instance)
    elif chosen_item_type == settings.ITEM_TYPE_BOMB_CAPACITY:
        return BombCapacityItem(x_tile, y_tile, game_instance)
    elif chosen_item_type == settings.ITEM_TYPE_BOMB_RANGE:
        return BombRangeItem(x_tile, y_tile, game_instance)
    # 如果將來有更多道具類型，在這裡添加 elif 分支
    else:
        print(f"[ItemCreation] Warning: Unknown chosen_item_type '{chosen_item_type}'. Cannot create specific item. Returning None.")
        return None
    # （4）！！！ 修改結束 ！！！（4）