# oop-2025-proj-pycade/sprites/player.py

import pygame
from .game_object import GameObject
import settings
from .bomb import Bomb

class Player(GameObject):
    def __init__(self, game, x_tile, y_tile, player_image_path=settings.PLAYER_IMG, is_ai=False, ai_controller=None):
        super().__init__(
            x_tile * settings.TILE_SIZE,
            y_tile * settings.TILE_SIZE,
            settings.TILE_SIZE,
            settings.TILE_SIZE,
            image_path=player_image_path
        )
        self.game = game
        # --- 新增 is_ai 和 ai_controller 屬性 ---
        self.is_ai = is_ai
        self.ai_controller = ai_controller # 如果是 AI，則持有對其控制器的引用
        # --- 新增結束 ---

        # 根據是否為 AI 調整速度 (可選)
        if self.is_ai and hasattr(settings, 'AI_PLAYER_SPEED_FACTOR'):
            self.speed = int((settings.PLAYER_SPEED if hasattr(settings, 'PLAYER_SPEED') else 4) * settings.AI_PLAYER_SPEED_FACTOR)
        else:
            self.speed = settings.PLAYER_SPEED if hasattr(settings, 'PLAYER_SPEED') else 4
        
        # ... (lives, max_bombs, bombs_placed_count, bomb_range, score, vx, vy, is_alive, etc. - 保持不變) ...
        self.lives = settings.MAX_LIVES if hasattr(settings, 'MAX_LIVES') else 3
        self.max_bombs = settings.INITIAL_BOMBS
        self.bombs_placed_count = 0
        self.bomb_range = settings.INITIAL_BOMB_RANGE
        self.score = 0
        # self.speed 已經在上面設定了
        self.vx = 0
        self.vy = 0
        self.is_alive = True
        self.last_hit_time = 0
        self.invincible_duration = 1000


    def get_input(self): # 這個方法只對人類玩家有效
        if self.is_ai:
            return # AI 不從鍵盤獲取輸入

        self.vx, self.vy = 0, 0
        keys = pygame.key.get_pressed()
        # ... (鍵盤輸入邏輯不變) ...
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vx = -self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vx = self.speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.vy = -self.speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.vy = self.speed
        if self.vx != 0 and self.vy != 0:
            self.vx *= 0.7071
            self.vy *= 0.7071
    
    # AI 控制器會調用這個方法來設置玩家的移動意圖
    def set_ai_movement_intent(self, dx_normalized, dy_normalized):
        """
        Called by AIController to set the player's desired movement direction.
        dx_normalized, dy_normalized should be -1, 0, or 1.
        """
        if not self.is_ai: return # Should only be called for AI players

        self.vx = dx_normalized * self.speed
        self.vy = dy_normalized * self.speed
        
        # Normalize diagonal movement if both are non-zero
        if self.vx != 0 and self.vy != 0:
            self.vx *= 0.7071
            self.vy *= 0.7071

    def collide_with_walls(self, dx, dy, walls_group):
        """
        Checks for collision with walls after a potential move.
        Adjusts player's rect if collision occurs.

        Args:
            dx (int): Change in x position.
            dy (int): Change in y position.
            walls_group (pygame.sprite.Group): Group of wall sprites.
        """
        # Move in x-direction
        self.rect.x += dx
        collided_walls_x = pygame.sprite.spritecollide(self, walls_group, False)
        for wall in collided_walls_x:
            if dx > 0: # Moving right
                self.rect.right = wall.rect.left
            elif dx < 0: # Moving left
                self.rect.left = wall.rect.right
        
        # Move in y-direction
        self.rect.y += dy
        collided_walls_y = pygame.sprite.spritecollide(self, walls_group, False)
        for wall in collided_walls_y:
            if dy > 0: # Moving down
                self.rect.bottom = wall.rect.top
            elif dy < 0: # Moving up
                self.rect.top = wall.rect.bottom

    def update(self, dt, solid_obstacles_group): # Renamed walls_group for clarity
        """
        Updates the player's state, including movement and collision.
        Handles differentiation between human and AI input for movement.
        """
        if not self.is_alive:
            self.vx = 0 # Stop movement if dead
            self.vy = 0
            # Consider also stopping animations or other updates for a dead player
            return

        # 1. 獲取移動意圖 (vx, vy)
        if not self.is_ai:
            self.get_input() # 人類玩家：從鍵盤讀取輸入並設定 self.vx, self.vy
        # else:
            # AI 玩家：self.vx 和 self.vy 應該已經由 AIController 
            # (例如在其 move_along_path 方法中) 設定好了。
            # Player.update 自身不需要再為 AI 設定 vx, vy，它只負責應用這些速度。
            pass

        # 2. 應用 X 軸移動並處理碰撞
        self.rect.x += self.vx
        hit_list_x = pygame.sprite.spritecollide(self, solid_obstacles_group, False)
        for obstacle in hit_list_x:
            if self.vx > 0:  # 向右移動撞到
                self.rect.right = obstacle.rect.left
            elif self.vx < 0:  # 向左移動撞到
                self.rect.left = obstacle.rect.right
        
        # 3. 應用 Y 軸移動並處理碰撞
        self.rect.y += self.vy
        hit_list_y = pygame.sprite.spritecollide(self, solid_obstacles_group, False)
        for obstacle in hit_list_y:
            if self.vy > 0:  # 向下移動撞到
                self.rect.bottom = obstacle.rect.top
            elif self.vy < 0:  # 向上移動撞到
                self.rect.top = obstacle.rect.bottom

        # 4. 地圖邊界限制 (對人類和 AI 都適用)
        map_pixel_width = self.game.map_manager.tile_width * settings.TILE_SIZE
        map_pixel_height = self.game.map_manager.tile_height * settings.TILE_SIZE

        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > map_pixel_width:
            self.rect.right = map_pixel_width
        if self.rect.top < 0:
            self.rect.top = 0
        if self.rect.bottom > map_pixel_height:
            self.rect.bottom = map_pixel_height

        # 5. (對於AI) 如果 AIController 不是每幀都更新 AI 的 vx, vy，
        #    並且希望 AI 在執行完一步移動後停下來，可以在這裡重置。
        #    但我們目前的 AIController.move_along_path 邏輯會在到達格子中心時重置 vx,vy。
        # if self.is_ai:
        #     # self.vx = 0 # 如果希望 AI 每“思考”一次才動一下，則在這裡重置
        #     # self.vy = 0
        #     pass

    def place_bomb(self):
        if not self.is_alive: return

        if self.bombs_placed_count < self.max_bombs:
            bomb_tile_x = self.rect.centerx // settings.TILE_SIZE
            bomb_tile_y = self.rect.centery // settings.TILE_SIZE
            can_place = True
            for bomb_sprite in self.game.bombs_group:
                if bomb_sprite.current_tile_x == bomb_tile_x and \
                   bomb_sprite.current_tile_y == bomb_tile_y:
                    can_place = False
                    if not self.is_ai: # 只對人類玩家打印，避免AI刷屏
                        print(f"Cannot place bomb at ({bomb_tile_x}, {bomb_tile_y}): Bomb already exists.")
                    break
            
            if can_place:
                new_bomb = Bomb(bomb_tile_x, bomb_tile_y, self, self.game)
                self.game.all_sprites.add(new_bomb)
                self.game.bombs_group.add(new_bomb)
                self.bombs_placed_count += 1
                # print(f"Player (ID: {id(self)}, AI: {self.is_ai}) placed bomb. Active: {self.bombs_placed_count}/{self.max_bombs}")
                
                if self.is_ai and self.ai_controller:
                    self.ai_controller.ai_placed_bomb_recently = True
                    self.ai_controller.last_bomb_placed_time = pygame.time.get_ticks()
                    # AIController 的 update_state_machine 會決定是否切換到 WAIT_EXPLOSION 或 ESCAPE
        # else:
        #     if not self.is_ai:
        #         print(f"Player (ID: {id(self)}) cannot place more bombs. Active: {self.bombs_placed_count}, Max: {self.max_bombs}")

    def bomb_exploded_feedback(self):
        self.bombs_placed_count = max(0, self.bombs_placed_count - 1)
        # print(f"Player (ID: {id(self)}, AI: {self.is_ai}) notified of bomb explosion. Active bombs: {self.bombs_placed_count}/{self.max_bombs}")
        if self.is_ai and self.ai_controller:
            self.ai_controller.ai_placed_bomb_recently = False

    def take_damage(self, amount=1):
        current_time = pygame.time.get_ticks()
        if self.is_alive and (current_time - self.last_hit_time > self.invincible_duration):
            self.lives -= amount
            self.last_hit_time = current_time
            print(f"Player (ID: {id(self)}, AI: {self.is_ai}) took damage! Lives left: {self.lives}")
            if self.lives <= 0:
                self.lives = 0
                self.die()

    def die(self):
        if self.is_alive:
            self.is_alive = False
            print(f"Player (ID: {id(self)}, AI: {self.is_ai}) has died!")
            self.kill()