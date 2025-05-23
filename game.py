# oop-2025-proj-pycade/game.py

import pygame
import settings
from core.map_manager import MapManager
from sprites.player import Player # Player 類別現在使用新的移動系統

# AI 控制器匯入
from core.ai_controller import AIController as OriginalAIController # 您目前的 AI，作為 "original" 或 "balanced"
from core.ai_conservative import ConservativeAIController # 未來階段會建立
# from core.ai_controller_aggressive import AggressiveAIController   # 未來階段會建立
# from core.ai_controller_item_focused import ItemFocusedAIController # 未來階段會建立


class Game:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock
        self.running = True
        self.game_state = "PLAYING"
        # 從 settings.py 讀取 AI 原型，預設為 "original"
        self.ai_archetype = getattr(settings, "AI_OPPONENT_ARCHETYPE", "original")
        print(f"[Game Init] Selected AI Archetype: {self.ai_archetype}")

        self.all_sprites = pygame.sprite.Group()
        self.players_group = pygame.sprite.Group()
        self.bombs_group = pygame.sprite.Group()
        self.explosions_group = pygame.sprite.Group()
        self.items_group = pygame.sprite.Group()
        self.solid_obstacles_group = pygame.sprite.Group()

        self.map_manager = MapManager(self)
        self.player1 = None
        self.player2_ai = None
        self.ai_controller_p2 = None # AI 控制器實例

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

        grid_width = getattr(settings, 'GRID_WIDTH', 15)
        grid_height = getattr(settings, 'GRID_HEIGHT', 11)
        
        p1_start_tile = (1, 1)
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
        
        # 根據選擇的 AI 原型實例化 AI 控制器
        ai_controller_class = None
        if self.ai_archetype == "original":
            ai_controller_class = OriginalAIController
            print("[Game Setup] Initializing OriginalAIController.")
        # --- 未來擴展點 ---
        elif self.ai_archetype == "conservative":
            from core.ai_conservative import ConservativeAIController # 假設您已創建此文件
            ai_controller_class = ConservativeAIController
            print("[Game Setup] Initializing ConservativeAIController.")
        elif self.ai_archetype == "aggressive":
            from core.ai_aggressive import AggressiveAIController # 假設您已創建此文件
            ai_controller_class = AggressiveAIController
            print("[Game Setup] Initializing AggressiveAIController.")
        elif self.ai_archetype == "item_focused":
            from core.ai_item_focused import ItemFocusedAIController # 假設您已創建此文件
            ai_controller_class = ItemFocusedAIController
            print("[Game Setup] Initializing ItemFocusedAIController.")
        else:
            print(f"[Game Setup] Unknown AI Archetype '{self.ai_archetype}'. Defaulting to OriginalAIController.")
            ai_controller_class = OriginalAIController

        if self.ai_controller_p2 is None or not isinstance(self.ai_controller_p2, ai_controller_class):
            # 只有在控制器不存在，或控制器類型與期望類型不符時，才重新創建
            self.ai_controller_p2 = ai_controller_class(self.player2_ai, self)
            print(f"[Game Setup] AI Controller (re)created as {ai_controller_class.__name__}.")
        else:
            # 如果控制器已存在且類型正確，則只需更新其內部參考並重置狀態
            self.ai_controller_p2.ai_player = self.player2_ai
            print(f"[Game Setup] AI Controller instance of {ai_controller_class.__name__} already exists. Updating player reference.")

        # 重置 AI 控制器的狀態
        if hasattr(self.ai_controller_p2, 'reset_state') and callable(getattr(self.ai_controller_p2, 'reset_state')):
            # 優先呼叫子類別（例如 ItemFocusedAIController）自己定義的 reset_state
            self.ai_controller_p2.reset_state()
            print(f"[Game Setup] Called reset_state() on {self.ai_controller_p2.__class__.__name__}.")
        elif hasattr(self.ai_controller_p2, 'reset_state_base') and callable(getattr(self.ai_controller_p2, 'reset_state_base')):
            # 如果子類別沒有 reset_state，但基礎類別有 reset_state_base (我們的設計是子類reset_state會調用super().reset_state_base())
            # 這裡主要是為了向前兼容或處理未完全按新模式設計的AI
            self.ai_controller_p2.reset_state_base()
            print(f"[Game Setup] Called reset_state_base() on {self.ai_controller_p2.__class__.__name__} (fallback).")
        else:
            print(f"[Game Setup] AI Controller {self.ai_controller_p2.__class__.__name__} has no callable reset_state or reset_state_base method.")


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
                    if event.key == pygame.K_f:
                        if self.player1 and self.player1.is_alive:
                            self.player1.place_bomb()
                
                elif self.game_state == "GAME_OVER":
                    if event.key == pygame.K_r:
                        self.setup_initial_state() # 重置遊戲

    def update(self):
        if self.game_state == "PLAYING":
            if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2:
                self.ai_controller_p2.update()
            
            self.all_sprites.update(self.dt, self.solid_obstacles_group)

            for player in list(self.players_group):
                if player.is_alive:
                    hit_explosions = pygame.sprite.spritecollide(player, self.explosions_group, False, pygame.sprite.collide_rect)
                    if hit_explosions:
                        player.take_damage()
            
            if hasattr(self.map_manager, 'destructible_walls_group'):
                for d_wall in list(self.map_manager.destructible_walls_group):
                    if d_wall.alive(): # 確保牆壁還存在
                        hit_explosions_for_d_wall = pygame.sprite.spritecollide(d_wall, self.explosions_group, False)
                        if hit_explosions_for_d_wall:
                            d_wall.take_damage()
            
            for player in list(self.players_group):
                if player.is_alive:
                    collected_items_this_frame = []
                    for item in list(self.items_group):
                        item_tile_x = item.rect.centerx // settings.TILE_SIZE
                        item_tile_y = item.rect.centery // settings.TILE_SIZE
                        if player.tile_x == item_tile_x and player.tile_y == item_tile_y:
                            collected_items_this_frame.append(item)
                    
                    for item_to_collect in collected_items_this_frame:
                        item_to_collect.apply_effect(player)
            
            human_player_alive = self.player1 and self.player1.is_alive
            ai_player_alive = self.player2_ai and self.player2_ai.is_alive

            if not human_player_alive and not ai_player_alive and self.game_state != "GAME_OVER":
                self.game_state = "GAME_OVER"
            elif not human_player_alive and self.game_state != "GAME_OVER":
                self.game_state = "GAME_OVER"
            elif not ai_player_alive and human_player_alive and self.game_state != "GAME_OVER":
                self.game_state = "GAME_OVER"

        elif self.game_state == "GAME_OVER":
            pass

    def draw(self):
        self.screen.fill(settings.WHITE)
        self.all_sprites.draw(self.screen)

        if self.game_state == "PLAYING":
            if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2:
                if hasattr(self.ai_controller_p2, 'debug_draw_path'):
                    self.ai_controller_p2.debug_draw_path(self.screen)
            
            hud_texts = []
            if self.player1 and self.hud_font:
                hud_texts.extend([
                    f"P1 Lives: {self.player1.lives}",
                    f"P1 Bombs: {self.player1.max_bombs - self.player1.bombs_placed_count}/{self.player1.max_bombs}",
                    f"P1 Range: {self.player1.bomb_range}",
                    f"P1 Score: {self.player1.score}"
                ])
            if self.player2_ai and self.hud_font:
                 if self.player2_ai.is_alive:
                    hud_texts.append(f"AI Lives: {self.player2_ai.lives}")
                 else:
                    hud_texts.append("AI Defeated")
                 
                 if self.ai_controller_p2 and self.ai_status_font and hasattr(self.ai_controller_p2, 'current_state'):
                    ai_state_text = f"AI State: {self.ai_controller_p2.current_state}"
                    hud_texts.append(ai_state_text)
                 elif self.ai_controller_p2 and self.ai_status_font: # Fallback if current_state is missing for some reason
                    hud_texts.append(f"AI Controller: {self.ai_controller_p2.__class__.__name__}")


            line_height = 22
            start_y_offset = 10
            for i, text_line in enumerate(reversed(hud_texts)):
                font_to_use = self.hud_font
                if "AI State:" in text_line and self.ai_status_font:
                    font_to_use = self.ai_status_font
                elif "AI Controller:" in text_line and self.ai_status_font:
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