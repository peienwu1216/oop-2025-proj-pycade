# oop-2025-proj-pycade/game.py

import pygame
import settings
from core.map_manager import MapManager
from sprites.player import Player # Player 類別現在使用新的移動系統
from core.ai_controller import AIController # AIController 也會調整為使用 Player 的新移動方法

class Game:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock
        self.running = True
        self.game_state = "PLAYING" 

        self.all_sprites = pygame.sprite.Group()
        self.players_group = pygame.sprite.Group()
        self.bombs_group = pygame.sprite.Group()
        self.explosions_group = pygame.sprite.Group()
        self.items_group = pygame.sprite.Group() 
        self.solid_obstacles_group = pygame.sprite.Group() # 這個 group 仍然重要，用於 Player.attempt_move_to_tile 的障礙物檢查

        self.map_manager = MapManager(self)
        self.player1 = None
        self.player2_ai = None
        self.ai_controller_p2 = None

        self.hud_font = None
        self.game_over_font = None
        self.restart_font = None
        self.ai_status_font = None
        try:
            self.hud_font = pygame.font.Font(None, 28)
            self.game_over_font = pygame.font.Font(None, 74)
            self.restart_font = pygame.font.Font(None, 30)
            self.ai_status_font = pygame.font.Font(None, 24)
        except Exception as e:
            print(f"Error initializing fonts: {e}")
            self.hud_font = pygame.font.SysFont("arial", 28) # Fallback
            self.game_over_font = pygame.font.SysFont('arial', 74) # Fallback
            self.restart_font = pygame.font.SysFont('arial', 30) # Fallback
            self.ai_status_font = pygame.font.SysFont("arial", 24) # Fallback
        
        self.setup_initial_state()

    def setup_initial_state(self):
        self.all_sprites.empty()
        self.players_group.empty()
        self.bombs_group.empty()
        self.explosions_group.empty()
        self.items_group.empty() 
        self.solid_obstacles_group.empty()

        # 地圖和玩家生成邏輯不變，Player 的 __init__ 已更新為使用 tile_x, tile_y
        grid_width = getattr(settings, 'GRID_WIDTH', 15) # 使用 getattr 提供預設值
        grid_height = getattr(settings, 'GRID_HEIGHT', 11) # 使用 getattr 提供預設值
        
        p1_start_tile = (1, 1)
        # 確保 p2_start_tile 在邊界內
        p2_start_tile_x = grid_width - 2 if grid_width > 2 else 1
        p2_start_tile_y = grid_height - 2 if grid_height > 2 else 1
        p2_start_tile = (p2_start_tile_x, p2_start_tile_y)

        safe_radius = 2

        random_map_layout = self.map_manager.get_randomized_map_layout(
            grid_width, grid_height,
            p1_start_tile, p2_start_tile,
            safe_radius
        )
        self.map_manager.load_map_from_data(random_map_layout)
        
        player1_sprite_config = {
            "ROW_MAP": settings.PLAYER_SPRITESHEET_ROW_MAP, 
            "NUM_FRAMES": settings.PLAYER_NUM_WALK_FRAMES 
        }
        self.player1 = Player(self, p1_start_tile[0], p1_start_tile[1],
                              spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH, 
                              sprite_config=player1_sprite_config,
                              is_ai=False)
        self.all_sprites.add(self.player1)
        self.players_group.add(self.player1)

        ai_image_set_path = getattr(settings, 'PLAYER2_AI_SPRITESHEET_PATH', settings.PLAYER1_SPRITESHEET_PATH)
        ai_sprite_config = {
            "ROW_MAP": settings.PLAYER_SPRITESHEET_ROW_MAP, 
            "NUM_FRAMES": settings.PLAYER_NUM_WALK_FRAMES 
        }
        self.player2_ai = Player(self, p2_start_tile[0], p2_start_tile[1],
                                 spritesheet_path=ai_image_set_path,
                                 sprite_config=ai_sprite_config,
                                 is_ai=True)
        self.all_sprites.add(self.player2_ai)
        self.players_group.add(self.player2_ai)
        
        if self.ai_controller_p2 is None: # 只有在第一次 setup 時創建 AIController
            self.ai_controller_p2 = AIController(self.player2_ai, self)
        else: # 後續 reset 時，更新 AIController 內部參考的 AI player 物件 (如果需要)
            self.ai_controller_p2.ai_player = self.player2_ai 
            # 可能還需要重置 AIController 的內部狀態，例如呼叫一個 reset 方法
            if hasattr(self.ai_controller_p2, 'reset_state'):
                self.ai_controller_p2.reset_state()


        self.player2_ai.ai_controller = self.ai_controller_p2 
        if self.ai_controller_p2:
            self.ai_controller_p2.human_player_sprite = self.player1 
        
        self.game_state = "PLAYING"

    def run(self):
        while self.running:
            self.dt = self.clock.tick(settings.FPS) / 1000.0 
            self.events()
            self.update()
            self.draw()

    def events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN: 
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                
                if self.game_state == "PLAYING":
                    # 只處理一次性動作，如放炸彈
                    if event.key == pygame.K_f: 
                        if self.player1 and self.player1.is_alive:
                            self.player1.place_bomb()
                
                elif self.game_state == "GAME_OVER":
                    if event.key == pygame.K_r:
                        self.setup_initial_state()
        # 方向移動的 KEYDOWN 處理已移除，改由 Player.get_input() 配合 get_pressed() 處理

    def update(self):
        if self.game_state == "PLAYING":
            # AI 控制器更新 (AIController.update 會呼叫 ai_player.attempt_move_to_tile)
            if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2:
                self.ai_controller_p2.update()
            
            # 更新所有精靈 (Player.update 現在主要處理動畫和 action_timer)
            self.all_sprites.update(self.dt, self.solid_obstacles_group) 

            # --- 碰撞檢測 ---
            # 玩家與爆炸的碰撞 (基於 rect/hitbox，這部分不變，因為爆炸是區域效果)
            for player in list(self.players_group):
                if player.is_alive:
                    # 確保 player.hitbox 更新到最新位置 (Player.update 會處理)
                    # 使用 player.hitbox 進行碰撞檢測會更精確
                    hit_explosions = pygame.sprite.spritecollide(player, self.explosions_group, False, pygame.sprite.collide_rect) # 或者使用 player.hitbox 如果它更小:
                    # collided_hitbox = lambda s1, s2: s1.hitbox.colliderect(s2.rect)
                    # hit_explosions = pygame.sprite.spritecollide(player, self.explosions_group, False, collided_hitbox)
                    if hit_explosions:
                        player.take_damage()
            
            # 可破壞牆壁與爆炸的碰撞 (不變)
            if hasattr(self.map_manager, 'destructible_walls_group'):
                for d_wall in list(self.map_manager.destructible_walls_group):
                    if d_wall.alive():
                        hit_explosions_for_d_wall = pygame.sprite.spritecollide(d_wall, self.explosions_group, False)
                        if hit_explosions_for_d_wall: 
                            d_wall.take_damage()
            
            # ！！！修改開始：玩家與道具的碰撞 (基於格子座標)！！！
            for player in list(self.players_group):
                if player.is_alive:
                    collected_items_this_frame = []
                    for item in list(self.items_group): # 使用 list() 以允許在迭代中修改
                        # 假設 Item 精靈也有 tile_x, tile_y 屬性，或者從 rect 推算
                        # 我們在 Player.py 中已經將玩家位置改為 self.tile_x, self.tile_y
                        # 需要確保 Item 也有類似的格子座標屬性，或能方便地獲取
                        item_tile_x = item.rect.centerx // settings.TILE_SIZE # 從 Item rect 的中心計算格子座標
                        item_tile_y = item.rect.centery // settings.TILE_SIZE

                        if player.tile_x == item_tile_x and player.tile_y == item_tile_y:
                            collected_items_this_frame.append(item)
                    
                    for item_to_collect in collected_items_this_frame:
                        # print(f"Player at ({player.tile_x},{player.tile_y}) collected item {item_to_collect.type} at ({item_tile_x},{item_tile_y})") # DEBUG
                        item_to_collect.apply_effect(player) # apply_effect 應該包含 item.kill()
                        # Item.kill() 會將其從 all_sprites 和它所屬的其他 group (例如 items_group) 中移除
                        # 如果 Item.kill() 沒有將其從 self.items_group 中移除，則需要手動移除：
                        # if item_to_collect in self.items_group: # Double check
                        #    self.items_group.remove(item_to_collect)
            # ！！！修改結束！！！
            
            # --- 遊戲結束判斷 (不變) ---
            human_player_alive = self.player1 and self.player1.is_alive
            ai_player_alive = self.player2_ai and self.player2_ai.is_alive

            if not human_player_alive and not ai_player_alive and self.game_state != "GAME_OVER":
                self.game_state = "GAME_OVER"
                # print("Draw! Both players are defeated.") # DEBUG
            elif not human_player_alive and self.game_state != "GAME_OVER":
                self.game_state = "GAME_OVER"
                # print("Game Over! Player 1 (Human) has been defeated.") # DEBUG
            elif not ai_player_alive and human_player_alive and self.game_state != "GAME_OVER":
                self.game_state = "GAME_OVER"
                # print("Victory! Player 2 (AI) has been defeated.") # DEBUG

        elif self.game_state == "GAME_OVER": 
            pass

    def draw(self):
        self.screen.fill(settings.WHITE)
        # self.map_manager.draw_grid(self.screen) # 可選的調試繪圖

        self.all_sprites.draw(self.screen) # Player.rect 的位置由 Player.update 更新

        if self.game_state == "PLAYING":
            if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2:
                if hasattr(self.ai_controller_p2, 'debug_draw_path'):
                    self.ai_controller_p2.debug_draw_path(self.screen)
            
            hud_texts = []
            if self.player1 and self.hud_font:
                # 顯示 P1 格子座標 (調試用)
                # hud_texts.append(f"P1 Tile: ({self.player1.tile_x}, {self.player1.tile_y})")
                hud_texts.extend([
                    f"P1 Lives: {self.player1.lives}",
                    f"P1 Bombs: {self.player1.max_bombs - self.player1.bombs_placed_count}/{self.player1.max_bombs}",
                    f"P1 Range: {self.player1.bomb_range}",
                    f"P1 Score: {self.player1.score}"
                ])
            if self.player2_ai and self.hud_font:
                 if self.player2_ai.is_alive:
                    # 顯示 AI 格子座標 (調試用)
                    # hud_texts.append(f"AI Tile: ({self.player2_ai.tile_x}, {self.player2_ai.tile_y})")
                    hud_texts.append(f"AI Lives: {self.player2_ai.lives}")
                 else:
                    hud_texts.append("AI Defeated")
                 
                 if self.ai_controller_p2 and self.ai_status_font:
                    ai_state_text = f"AI State: {self.ai_controller_p2.current_state}"
                    hud_texts.append(ai_state_text)

            line_height = 22
            start_y_offset = 10
            for i, text_line in enumerate(reversed(hud_texts)):
                font_to_use = self.hud_font
                if "AI State:" in text_line and self.ai_status_font:
                    font_to_use = self.ai_status_font
                
                text_surface = font_to_use.render(text_line, True, settings.BLACK)
                text_pos_y = settings.SCREEN_HEIGHT - start_y_offset - (i + 1) * line_height
                self.screen.blit(text_surface, (10, text_pos_y))

        elif self.game_state == "GAME_OVER":
            if self.game_over_font and self.restart_font:
                msg = "GAME OVER"; color = settings.RED
                p1_alive = self.player1 and self.player1.is_alive
                ai_alive = self.player2_ai and self.player2_ai.is_alive

                if not p1_alive and not ai_alive:
                    msg = "DRAW!"
                    color = settings.GREY
                elif not p1_alive:
                    msg = "GAME OVER - You Lost!"
                elif not ai_alive:
                    msg = "VICTORY - AI Defeated!"
                    color = settings.GREEN
                
                game_over_text = self.game_over_font.render(msg, True, color)
                text_rect = game_over_text.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 - 50))
                self.screen.blit(game_over_text, text_rect)
                restart_text = self.restart_font.render("Press 'R' to Restart", True, settings.BLACK)
                restart_rect = restart_text.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 + 20))
                self.screen.blit(restart_text, restart_rect)
        
        pygame.display.flip()