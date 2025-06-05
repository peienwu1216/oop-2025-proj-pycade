# oop-2025-proj-pycade/sprites/bomb.py

import pygame
from .game_object import GameObject # 從同一個 sprites 套件中匯入 GameObject
import settings
from .explosion import Explosion

class Bomb(GameObject):
    """
    Represents a bomb placed by a player.
    """
    def __init__(self, x_tile, y_tile, placed_by_player, game_instance): # 添加 game_instance
        """
        Initializes a Bomb object.

        Args:
            x_tile (int): The x-coordinate (in tile units) where the bomb is placed.
                          [SPS_BOMB_NO_CHANGE_NEEDED] 這與 Player.place_bomb() 中傳入的 player.tile_x 一致。
            y_tile (int): The y-coordinate (in tile units) where the bomb is placed.
                          [SPS_BOMB_NO_CHANGE_NEEDED] 這與 Player.place_bomb() 中傳入的 player.tile_y 一致。
            placed_by_player (Player): The player instance that placed this bomb.
            game_instance (Game): The main game instance.
        """
        # 判斷是否是 player1 放的炸彈
        if placed_by_player.is_player1:
            toggle_index = game_instance.player1_bomb_toggle
            bomb_img = settings.PLAYER1_BOMB_IMAGES[toggle_index]
            game_instance.player1_bomb_toggle = (toggle_index + 1) % len(settings.PLAYER1_BOMB_IMAGES)
        else:
            bomb_img = settings.BOMB_IMG  # 預設圖

        super().__init__(
            x_tile * settings.TILE_SIZE+6, # 視覺位置基於格子座標
            y_tile * settings.TILE_SIZE, # 視覺位置基於格子座標
            width=None, # 寬度基於圖片比例
            height=settings.TILE_SIZE,
            image_path=bomb_img
        )
        self.placed_by_player = placed_by_player
        self.game = game_instance # 儲存 Game 實例，以便訪問 Sprite Group 等
        self.spawn_time = pygame.time.get_ticks() # 記錄放置時間
        self.timer = settings.BOMB_TIMER # 毫秒
        self.exploded = False
        self.current_tile_x = x_tile # [SPS_BOMB_NO_CHANGE_NEEDED] 記錄炸彈所在的格子座標，這很好。
        self.current_tile_y = y_tile # [SPS_BOMB_NO_CHANGE_NEEDED] 記錄炸彈所在的格子座標，這很好。

        self.is_solidified = False # 炸彈初始不是固態的，允許放置者離開
        self.owner_has_left_tile = False # 標記擁有者是否已離開此格
        
        # Bomb animation
        self.animation_images = [
            pygame.transform.smoothscale(
                pygame.image.load(img).convert_alpha(),
                (settings.TILE_SIZE, settings.TILE_SIZE)
            )
            for img in settings.PLAYER1_BOMB_IMAGES
        ]
        self.animation_index = 0
        self.last_animation_time = pygame.time.get_ticks()
        self.animation_interval = 300  # 毫秒，調整為你想要的動畫速度


        # For visual countdown (optional)
        try:
            self.font = pygame.font.Font(None, 20) 
        except pygame.error: 
            self.font = pygame.font.SysFont("arial", 20)
        self.text_color = settings.RED

        # [SPS_BOMB_NO_CHANGE_NEEDED] 這個 print 仍然有效。
        # print(f"Bomb placed at tile ({x_tile}, {y_tile}) by Player object ID: {id(self.placed_by_player)}")


    def update(self, dt, *args): # dt is not used yet for timer logic, but good practice
        """
        Updates the bomb's state (timer, visual countdown).
        """
        # [SPS_BOMB_NO_CHANGE_NEEDED] 倒數計時和爆炸邏輯與玩家移動方式無直接關聯。
        current_time = pygame.time.get_ticks()
        time_elapsed = current_time - self.spawn_time

        if not self.owner_has_left_tile and self.placed_by_player:
            if self.placed_by_player.tile_x != self.current_tile_x or \
               self.placed_by_player.tile_y != self.current_tile_y:
                self.owner_has_left_tile = True
                self.is_solidified = True 
        
        # if not self.exploded and time_elapsed >= self.timer:
        #     self.explode() # 觸發爆炸
            
        if not self.exploded:
            # 動畫切換邏輯
            if current_time - self.last_animation_time >= self.animation_interval:
                self.animation_index = (self.animation_index + 1) % len(self.animation_images)
                self.original_image = self.animation_images[self.animation_index]
                self.last_animation_time = current_time

            # 更新圖像（先清除，再加倒數字）
            self.image = self.original_image.copy()
            time_left_sec = max(0, (self.timer - time_elapsed) / 1000)
            countdown_text = f"{time_left_sec:.1f}"
            text_surface = self.font.render(countdown_text, True, self.text_color)
            text_rect = text_surface.get_rect(center=(self.image.get_width() / 2, self.image.get_height() / 2))
            self.image.blit(text_surface, text_rect)

            # 判斷是否該爆炸
            if time_elapsed >= self.timer:
                self.explode()
        
        if not self.exploded:
            time_left_sec = max(0, (self.timer - time_elapsed) / 1000)
            self.image = self.original_image.copy() 
            countdown_text = f"{time_left_sec:.1f}" 
            text_surface = self.font.render(countdown_text, True, self.text_color)
            text_rect = text_surface.get_rect(center=(self.image.get_width() / 2, self.image.get_height() / 2))
            self.image.blit(text_surface, text_rect)

    def explode(self):
        # [SPS_BOMB_NO_CHANGE_NEEDED] 爆炸邏輯完全基於炸彈自身的 current_tile_x, current_tile_y 和放置者的 bomb_range。
        # 這些都不受玩家移動方式從像素級變為格子級的影響。
        if not self.exploded:
            # print(f"Bomb at ({self.current_tile_x}, {self.current_tile_y}) EXPLOADED by player with range {self.placed_by_player.bomb_range}!") # DEBUG
            self.exploded = True
            if self.placed_by_player:
                 self.placed_by_player.bomb_exploded_feedback()

            bomb_range = self.placed_by_player.bomb_range
            explosion_tiles = []
            explosion_tiles.append((self.current_tile_x, self.current_tile_y)) 

            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]: 
                for i in range(1, bomb_range + 1):
                    nx, ny = self.current_tile_x + dx * i, self.current_tile_y + dy * i
                    
                    if not (0 <= nx < self.game.map_manager.tile_width and \
                            0 <= ny < self.game.map_manager.tile_height):
                        break 

                    if self.game.map_manager.is_solid_wall_at(nx, ny):
                        break 
                    
                    explosion_tiles.append((nx, ny))
                    
                    is_destructible_here = False
                    # 需要確保 self.game.map_manager.destructible_walls_group 中的牆壁有 tile_x, tile_y 屬性
                    for d_wall in self.game.map_manager.destructible_walls_group:
                        if hasattr(d_wall, 'tile_x') and hasattr(d_wall, 'tile_y'): # 增加檢查
                            if d_wall.tile_x == nx and d_wall.tile_y == ny and not getattr(d_wall, 'is_destroyed', False): # 確保牆未被摧毀
                                is_destructible_here = True
                                break
                        # else:
                            # print(f"[BOMB EXPLODE WARN] Destructible wall object {d_wall} missing tile_x/tile_y attributes.") # DEBUG

                    if is_destructible_here:
                        break 

            for ex_tile_x, ex_tile_y in explosion_tiles:
                expl_sprite = Explosion(ex_tile_x, ex_tile_y, self.game)
                self.game.all_sprites.add(expl_sprite)
                self.game.explosions_group.add(expl_sprite)
            
            self.kill()