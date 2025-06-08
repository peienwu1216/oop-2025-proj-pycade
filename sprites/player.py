# oop-2025-proj-pycade/sprites/player.py

import pygame
from .game_object import GameObject
import settings
from sprites.draw_text import FloatingText
# from .bomb import Bomb # Bomb 在 Player 中放置炸彈時才需要

class Player(GameObject):
    def __init__(self, game, x_tile, y_tile, spritesheet_path, sprite_config, is_ai=False, ai_controller=None, is_player1=False):
        pygame.sprite.Sprite.__init__(self) 

        self.game = game
        self.is_ai = is_ai
        self.ai_controller = ai_controller 
        self.is_player1 = is_player1

        self.tile_x = x_tile
        self.tile_y = y_tile

        self.animations = {}
        self.spritesheet = None
        try:
            self.spritesheet = pygame.image.load(spritesheet_path).convert_alpha()
        except pygame.error as e:
            print(f"Error loading spritesheet {spritesheet_path}: {e}")

        if self.spritesheet:
            # （1）！！！ 修改：從 settings.py 或 sprite_config 中獲取動畫幀的詳細資訊 ！！！（1）
            # 確保 sprite_config 字典中包含 "NUM_FRAMES"
            # settings.py 中有 PLAYER_NUM_WALK_FRAMES, PLAYER_SPRITE_FRAME_WIDTH, PLAYER_SPRITE_FRAME_HEIGHT
            num_frames = sprite_config.get("NUM_FRAMES", getattr(settings, "PLAYER_NUM_WALK_FRAMES", 1))
            # PLAYER_SPRITE_FRAME_WIDTH 和 PLAYER_SPRITE_FRAME_HEIGHT 已在 settings.py 中定義
            frame_w = settings.PLAYER_SPRITE_FRAME_WIDTH 
            frame_h = settings.PLAYER_SPRITE_FRAME_HEIGHT
            # （1）！！！ 修改結束 ！！！（1）

            for direction, row_index in sprite_config["ROW_MAP"].items(): 
                frames = []
                for i in range(num_frames): 
                    frame_x = i * frame_w 
                    frame_y = row_index * frame_h 
                    frame_surface = self.spritesheet.subsurface(
                        pygame.Rect(frame_x, frame_y, frame_w, frame_h) 
                    )
                    frames.append(frame_surface)
                self.animations[direction] = frames
            
            if "RIGHT" in self.animations and "LEFT" not in self.animations: 
                self.animations["LEFT"] = [pygame.transform.flip(frame, True, False) for frame in self.animations["RIGHT"]] 

        self.current_direction = "DOWN"
        self.current_frame_index = 0
        self.last_animation_update_time = pygame.time.get_ticks()
        
        # （2）！！！ 修改：PLAYER_ANIMATION_SPEED 已在 settings.py 中定義 ！！！（2）
        self.animation_frame_duration = settings.PLAYER_ANIMATION_SPEED * 1000 
        # （2）！！！ 修改結束 ！！！（2）

        # （3）！！！ 修改：PLAYER_VISUAL_SCALE_FACTOR 已在 settings.py 中定義 ！！！（3）
        self.visual_scale_factor = settings.PLAYER_VISUAL_SCALE_FACTOR 
        # （3）！！！ 修改結束 ！！！（3）
        if self.visual_scale_factor != 1.0 and self.animations: 
            scaled_animations = {}
            for direction, frames in self.animations.items():
                scaled_frames = []
                for frame in frames:
                    original_width = frame.get_width()
                    original_height = frame.get_height()
                    new_width = int(original_width * self.visual_scale_factor) 
                    new_height = int(original_height * self.visual_scale_factor) 
                    scaled_frames.append(pygame.transform.smoothscale(frame, (new_width, new_height))) 
                scaled_animations[direction] = scaled_frames
            self.animations = scaled_animations

        if self.animations and self.current_direction in self.animations and self.animations[self.current_direction]: 
            self.image = self.animations[self.current_direction][self.current_frame_index] 
        else:
            # （4）！！！ 修改：使用 settings.py 中的 PLAYER_SPRITE_FRAME_WIDTH/HEIGHT 設定 fallback image 大小 ！！！（4）
            base_fallback_w = settings.PLAYER_SPRITE_FRAME_WIDTH
            base_fallback_h = settings.PLAYER_SPRITE_FRAME_HEIGHT
            fallback_width = int(base_fallback_w * self.visual_scale_factor) 
            fallback_height = int(base_fallback_h * self.visual_scale_factor)
            # （4）！！！ 修改結束 ！！！（4）
            self.image = pygame.Surface((fallback_width, fallback_height)) 
            self.image.fill(settings.RED if not self.is_ai else settings.BLUE) 
            if not self.animations: 
                print(f"Warning: Player animations not loaded for {spritesheet_path}. Using fallback image.") 

        self.rect = self.image.get_rect()
        self.rect.center = (self.tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2,
                             self.tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2)

        # --- Hitbox ---
        # （5）！！！ 修改：使用 settings.py 中的 PLAYER_HITBOX_WIDTH_REDUCTION 和 PLAYER_HITBOX_HEIGHT_REDUCTION ！！！（5）
        # PLAYER_SPRITE_FRAME_WIDTH 和 PLAYER_SPRITE_FRAME_HEIGHT 已在 settings.py 中定義
        base_width_for_hitbox = settings.PLAYER_SPRITE_FRAME_WIDTH
        base_height_for_hitbox = settings.PLAYER_SPRITE_FRAME_HEIGHT

        hitbox_width_reduction = getattr(settings, "PLAYER_HITBOX_WIDTH_REDUCTION", int(base_width_for_hitbox * 0.3))
        hitbox_height_reduction = getattr(settings, "PLAYER_HITBOX_HEIGHT_REDUCTION", int(base_height_for_hitbox * 0.3))
        
        self.hitbox_width = base_width_for_hitbox - hitbox_width_reduction 
        self.hitbox_height = base_height_for_hitbox - hitbox_height_reduction 
        # （5）！！！ 修改結束 ！！！（5）
        self.hitbox = pygame.Rect(0, 0, self.hitbox_width, self.hitbox_height) 
        self.hitbox.center = self.rect.center 

        self.lives = settings.MAX_LIVES 
        self.max_bombs = settings.INITIAL_BOMBS 
        self.bombs_placed_count = 0 
        self.bomb_range = settings.INITIAL_BOMB_RANGE 
        self.score = 0 
        
        self.is_alive = True 
        self.last_hit_time = 0 
        # （6）！！！ 修改：使用 settings.py 中的 PLAYER_INVINCIBLE_DURATION ！！！（6）
        self.invincible_duration = settings.PLAYER_INVINCIBLE_DURATION 
        # （6）！！！ 修改結束 ！！！（6）

        self.is_moving = False 
        self.action_timer = 0 
        
        if self.is_ai:
            # （7）！！！ 修改：使用 settings.py 中的 AI_GRID_MOVE_ACTION_DURATION ！！！（7）
            self.ACTION_ANIMATION_DURATION = settings.AI_GRID_MOVE_ACTION_DURATION 
            # （7）！！！ 修改結束 ！！！（7）
        else:
            # （8）！！！ 修改：使用 settings.py 中的 HUMAN_GRID_MOVE_ACTION_DURATION ！！！（8）
            self.ACTION_ANIMATION_DURATION = settings.HUMAN_GRID_MOVE_ACTION_DURATION 
            # （8）！！！ 修改結束 ！！！（8）
            

    def attempt_move_to_tile(self, dx, dy):
        print(f"[DEBUG_ATTEMPT_MOVE] AI at ({self.tile_x},{self.tile_y}), trying dx={dx}, dy={dy}. IsAlive: {self.is_alive}, ActionTimer: {self.action_timer}")
        if not self.is_alive or self.action_timer > 0:
            # 新增: 打印具體失敗原因
            print(f"[DEBUG_ATTEMPT_MOVE_FAIL] Reason: Not alive or action_timer > 0. IsAlive: {self.is_alive}, ActionTimer: {self.action_timer}")
            return False
        if dx == 0 and dy == 0:
            # 新增: 打印具體失敗原因
            print(f"[DEBUG_ATTEMPT_MOVE_FAIL] Reason: dx=0 and dy=0 (no actual move)")
            return False
        # 假設不允許斜向移動 (如果允許，請調整此邏輯)
        if dx != 0 and dy != 0:
            # 新增: 打印具體失敗原因
            print(f"[DEBUG_ATTEMPT_MOVE_FAIL] Reason: Diagonal move attempted (dx={dx}, dy={dy})")
            return False

        target_tile_x = self.tile_x + dx
        target_tile_y = self.tile_y + dy

        # 1. Check map boundaries
        if not (0 <= target_tile_x < self.game.map_manager.tile_width and \
                0 <= target_tile_y < self.game.map_manager.tile_height):
            print(f"[DEBUG_ATTEMPT_MOVE_FAIL] Reason: Target out of bounds. Target: ({target_tile_x},{target_tile_y})")
            return False

        target_check_rect = pygame.Rect(target_tile_x * settings.TILE_SIZE,
                                        target_tile_y * settings.TILE_SIZE,
                                        settings.TILE_SIZE,
                                        settings.TILE_SIZE)
        
        # 2. Check solid obstacles (walls, destructible walls)
        if hasattr(self.game, 'solid_obstacles_group'):
            for obstacle in self.game.solid_obstacles_group:
                # 確保只檢查實際的碰撞體，並且未被摧毀的牆壁
                if hasattr(obstacle, 'is_destroyed') and obstacle.is_destroyed: 
                    continue 
                if obstacle.rect.colliderect(target_check_rect):
                    print(f"[DEBUG_MOVE_FAIL] Player at ({self.tile_x}, {self.tile_y}) trying to move to ({target_tile_x}, {target_tile_y}).")
                    print(f"    Blocked by: {type(obstacle)} sprite.")
                    print(f"    Obstacle rect: {obstacle.rect}, its map coords should be: ({obstacle.rect.x // settings.TILE_SIZE}, {obstacle.rect.y // settings.TILE_SIZE})")
                    print(f"    Target check rect: {target_check_rect}")
                    return False
        
        # 3. Check other players
        if hasattr(self.game, 'players_group'):
            for other_player in self.game.players_group:
                if other_player is self: 
                    continue 
                if other_player.is_alive and \
                   other_player.tile_x == target_tile_x and \
                   other_player.tile_y == target_tile_y:
                    print(f"[DEBUG_ATTEMPT_MOVE_FAIL] Reason: Blocked by other player {id(other_player)} at target ({target_tile_x},{target_tile_y})")
                    return False
        
        # 4. Check bombs (核心修改處)
        if hasattr(self.game, 'bombs_group'):
            for bomb in self.game.bombs_group:
                if not bomb.exploded and \
                   bomb.current_tile_x == target_tile_x and \
                   bomb.current_tile_y == target_tile_y:
                    # 如果目標格子上的炸彈是【當前玩家自己】放置的
                    if bomb.placed_by_player is self:
                        # 並且當前玩家【還沒有離開過】這個炸彈所在的格子
                        if not bomb.owner_has_left_tile:
                            print(f"[DEBUG_ATTEMPT_MOVE_FAIL] Reason: Trying to re-enter own bomb tile at ({target_tile_x},{target_tile_y}) after leaving.")
                            # 允許玩家離開自己剛放的、尚未固化的炸彈
                            pass 
                        # 如果玩家已經離開過，然後又想回到這個有自己未爆炸炸彈的格子
                        # （無論炸彈是否已固化，通常不允許再次進入，除非遊戲有特殊規則）
                        else:
                            # ai_log(f"Player {id(self)} trying to re-enter own bomb tile at ({target_tile_x},{target_tile_y}) after leaving. Blocked.")
                            return False # 不允許重新進入自己已離開的炸彈格
                    # 如果目標格子上的炸彈是【其他玩家】放置的
                    else:
                        print(f"[DEBUG_ATTEMPT_MOVE_FAIL] Reason: Blocked by opponent's bomb at ({target_tile_x},{target_tile_y})")
                        # 【關鍵新增】無論對方炸彈是否固化，都不允許通過
                        # ai_log(f"Player {id(self)} blocked by opponent's bomb at ({target_tile_x},{target_tile_y}) (Owner: {id(bomb.placed_by_player)}).")
                        return False
        
        # 如果以上檢查都通過，則允許移動
        self.tile_x = target_tile_x
        self.tile_y = target_tile_y
        # 更新 sprite 的 rect 位置，使其中心對齊新的格子中心
        self.rect.center = (self.tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2,
                             self.tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2)
        if hasattr(self, 'hitbox'): # 同時更新 hitbox 位置
            self.hitbox.center = self.rect.center

        # 更新面向和移動動畫相關狀態
        if dx > 0: self.current_direction = "RIGHT"
        elif dx < 0: self.current_direction = "LEFT"
        if dy > 0: self.current_direction = "DOWN"
        elif dy < 0: self.current_direction = "UP"
        
        self.is_moving = True
        self.action_timer = self.ACTION_ANIMATION_DURATION # ACTION_ANIMATION_DURATION 應在 __init__ 中設定
        return True
    
    def move(self, dx, dy):
        return self.attempt_move_to_tile(dx, dy)
    
    def get_input(self):
        if self.is_ai or not self.is_alive: return
        if self.action_timer > 0: return 
        keys = pygame.key.get_pressed()
        dx, dy = 0, 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]: dx = -1
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx = 1
        elif keys[pygame.K_UP] or keys[pygame.K_w]: dy = -1
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]: dy = 1
        if dx != 0 or dy != 0: self.attempt_move_to_tile(dx, dy)

    def _animate(self):
        if not self.animations or self.current_direction not in self.animations or not self.animations[self.current_direction]: return
        animation_frames = self.animations[self.current_direction]
        if not self.is_moving: self.current_frame_index = 0
        else:
            now = pygame.time.get_ticks()
            if now - self.last_animation_update_time > self.animation_frame_duration:
                self.last_animation_update_time = now
                self.current_frame_index = (self.current_frame_index + 1) % len(animation_frames)
        new_image = animation_frames[self.current_frame_index]
        if self.image != new_image:
            old_center = self.rect.center
            self.image = new_image
            self.rect = self.image.get_rect(center=old_center)
    
    def update(self, dt, solid_obstacles_group): 
        if not self.is_alive:
            self.is_moving = False
            return

        if self.action_timer > 0:
            self.action_timer -= dt
            if self.action_timer <= 0:
                self.is_moving = False 
                self.action_timer = 0 
        
        if not self.is_ai:
            self.get_input() 
        
        if not self.is_moving and self.action_timer <=0 :
            expected_center_x = self.tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2
            expected_center_y = self.tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2
            if self.rect.centerx != expected_center_x or self.rect.centery != expected_center_y:
                self.rect.center = (expected_center_x, expected_center_y)
            if hasattr(self, 'hitbox'):
                self.hitbox.center = self.rect.center

        self._animate()

    def place_bomb(self):
        if not self.is_alive: return 
        if self.bombs_placed_count < self.max_bombs:
            bomb_tile_x = self.tile_x; bomb_tile_y = self.tile_y
            can_place = True
            
            if hasattr(self.game, 'players_group'):
                for other_player in self.game.players_group:
                    if other_player is not self and other_player.is_alive and \
                       other_player.tile_x == bomb_tile_x and other_player.tile_y == bomb_tile_y:
                        can_place = False; break

            # （10）！！！ 修改：放置炸彈前，除了檢查是否已有炸彈，也應檢查是否已有其他玩家 ！！！（10）
            # （這是一個保險措施，因為 attempt_move_to_tile 應該已經阻止了玩家重疊）
            if hasattr(self.game, 'players_group'):
                for other_player in self.game.players_group:
                    if other_player is not self and other_player.is_alive and \
                       other_player.tile_x == bomb_tile_x and other_player.tile_y == bomb_tile_y:
                        # print(f"Player {id(self)} cannot place bomb: tile ({bomb_tile_x},{bomb_tile_y}) occupied by another player.")
                        can_place = False; break
            
            if can_place: # 只有在沒有其他玩家時才繼續檢查炸彈
                for bomb_sprite in self.game.bombs_group: 
                    if bomb_sprite.current_tile_x == bomb_tile_x and \
                       bomb_sprite.current_tile_y == bomb_tile_y:
                        # print(f"Player {id(self)} cannot place bomb: tile ({bomb_tile_x},{bomb_tile_y}) already has a bomb.")
                        can_place = False; break 
            # （10）！！！ 修改結束 ！！！（10）
            
            if can_place:
                from .bomb import Bomb 
                new_bomb = Bomb(bomb_tile_x, bomb_tile_y, self, self.game) 
                # self.game.all_sprites.add(new_bomb) 
                self.game.bombs_group.add(new_bomb) 
                self.bombs_placed_count += 1 
                
                if self.is_ai and self.ai_controller: 
                    self.ai_controller.ai_just_placed_bomb = True 
                    self.ai_controller.last_bomb_placed_time = pygame.time.get_ticks() 
    
    def bomb_exploded_feedback(self): 
        self.bombs_placed_count = max(0, self.bombs_placed_count - 1) 

    def take_damage(self, amount=1): 
        current_time = pygame.time.get_ticks() 
        if self.is_alive and (current_time - self.last_hit_time > self.invincible_duration): 
            self.lives -= amount 
            self.last_hit_time = current_time 
            hurt = pygame.mixer.Sound(settings.HURT_PATH)
            hurt.play()
            print(f"Player (ID: {id(self)}, AI: {self.is_ai}) took damage! Lives left: {self.lives}") 
            if hasattr(self.game, "floating_texts_group"):
                fx = self.rect.centerx
                fy = self.rect.top
                text = FloatingText(fx, fy, "-1 LIFE", color=(255, 50, 50))
                self.game.floating_texts_group.add(text)
            if self.lives <= 0: 
                self.lives = 0 
                self.die() 

    def die(self): 
        if self.is_alive: 
            self.is_alive = False 
            print(f"Player (ID: {id(self)}, AI: {self.is_ai}) has died!") 
            if not self.is_ai and hasattr(self.game, 'check_game_over_conditions'):
                 self.game.check_game_over_conditions()
            self.kill()