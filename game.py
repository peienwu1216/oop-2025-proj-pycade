# oop-2025-proj-pycade/game.py

import pygame
import settings
from core.map_manager import MapManager
from sprites.player import Player 

# AI 控制器匯入
from core.ai_controller import AIController as OriginalAIController
from core.ai_conservative import ConservativeAIController
from core.ai_aggressive import AggressiveAIController
from core.ai_item_focused import ItemFocusedAIController


class Game:
    def __init__(self, screen, clock, ai_archetype="original"):
        self.screen = screen
        self.clock = clock
        self.running = True
        self.restart_game = False
        self.game_state = "PLAYING"
        
        self.ai_archetype = ai_archetype
        # print(f"[Game Init] Selected AI Archetype: {self.ai_archetype}") # 可以註解掉，避免過多日誌

        self.all_sprites = pygame.sprite.Group()
        self.players_group = pygame.sprite.Group()
        self.bombs_group = pygame.sprite.Group()
        self.explosions_group = pygame.sprite.Group()
        self.items_group = pygame.sprite.Group()
        self.solid_obstacles_group = pygame.sprite.Group()

        self.map_manager = MapManager(self)
        self.player1 = None
        self.player2_ai = None
        self.ai_controller_p2 = None

        self.hud_font = None
        self.game_over_font = None
        self.restart_font = None
        self.ai_status_font = None
        try:
            # 統一使用較小的字體以便在左下角並排顯示
            font_size = 22
            font_status_size = 18
            self.hud_font = pygame.font.Font(None, font_size)
            self.ai_status_font = pygame.font.Font(None, font_status_size)
            
            # 嘗試載入中文字體 (如果您的 menu.py 和 settings.py 已經設定好 CHINESE_FONT_PATH)
            if hasattr(settings, 'CHINESE_FONT_PATH'):
                try:
                    self.hud_font = pygame.font.Font(settings.CHINESE_FONT_PATH, font_size)
                    self.ai_status_font = pygame.font.Font(settings.CHINESE_FONT_PATH, font_status_size)
                    print("HUD: 成功載入中文字體用於狀態顯示。")
                except pygame.error as e:
                    print(f"HUD: 載入中文字體失敗 ({e})，將使用預設字體。")
                    self.hud_font = pygame.font.Font(None, font_size) # Fallback
                    self.ai_status_font = pygame.font.Font(None, font_status_size) # Fallback
            
            self.game_over_font = pygame.font.Font(None, 74)
            self.restart_font = pygame.font.Font(None, 30)

        except Exception as e:
            print(f"Error initializing fonts: {e}")
            self.hud_font = pygame.font.SysFont("arial", 24) # Fallback
            self.game_over_font = pygame.font.SysFont('arial', 74)
            self.restart_font = pygame.font.SysFont('arial', 30)
            self.ai_status_font = pygame.font.SysFont("arial", 20) # Fallback
        
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
        
        ai_controller_class = None
        if self.ai_archetype == "original":
            ai_controller_class = OriginalAIController
        elif self.ai_archetype == "conservative":
            ai_controller_class = ConservativeAIController
        elif self.ai_archetype == "aggressive":
            ai_controller_class = AggressiveAIController
        elif self.ai_archetype == "item_focused":
            ai_controller_class = ItemFocusedAIController
        else:
            ai_controller_class = OriginalAIController
        
        self.ai_controller_p2 = ai_controller_class(self.player2_ai, self)

        if hasattr(self.ai_controller_p2, 'reset_state') and callable(getattr(self.ai_controller_p2, 'reset_state')):
            self.ai_controller_p2.reset_state()
        
        self.player2_ai.ai_controller = self.ai_controller_p2
        if self.ai_controller_p2: # 確保控制器存在
            self.ai_controller_p2.human_player_sprite = self.player1
        
        self.game_state = "PLAYING"

    def run(self):
        while self.running:
            self.dt = self.clock.tick(settings.FPS) / 1000.0
            self.events()
            self.update()
            self.draw()
        return self.restart_game

    def events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.restart_game = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    self.restart_game = False
                
                if self.game_state == "PLAYING":
                    if event.key == pygame.K_f:
                        if self.player1 and self.player1.is_alive:
                            self.player1.place_bomb()
                
                elif self.game_state == "GAME_OVER":
                    if event.key == pygame.K_r:
                        self.restart_game = True
                        self.running = False

    def update(self):
        if self.game_state == "PLAYING":
            if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2:
                self.ai_controller_p2.update()
            
            self.all_sprites.update(self.dt, self.solid_obstacles_group)

            for player in list(self.players_group):
                if player.is_alive:
                    if pygame.sprite.spritecollide(player, self.explosions_group, False, pygame.sprite.collide_rect):
                        player.take_damage()
            
            if hasattr(self.map_manager, 'destructible_walls_group'):
                for d_wall in list(self.map_manager.destructible_walls_group):
                    if d_wall.alive():
                        if pygame.sprite.spritecollide(d_wall, self.explosions_group, False):
                            d_wall.take_damage()
            
            for player in list(self.players_group):
                if player.is_alive:
                    items_collected = pygame.sprite.spritecollide(player, self.items_group, True, pygame.sprite.collide_rect)
                    for item in items_collected:
                        item.apply_effect(player)
            
            human_player_alive = self.player1 and self.player1.is_alive
            ai_player_alive = self.player2_ai and self.player2_ai.is_alive

            if not human_player_alive or not ai_player_alive:
                self.game_state = "GAME_OVER"

    def draw(self):
        self.screen.fill(settings.WHITE)
        self.all_sprites.draw(self.screen)

        if self.game_state == "PLAYING":
            if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2:
                if hasattr(self.ai_controller_p2, 'debug_draw_path'):
                    self.ai_controller_p2.debug_draw_path(self.screen)
            self.draw_hud() # 繪製 HUD
        elif self.game_state == "GAME_OVER":
            self.draw_game_over_screen()
        
        pygame.display.flip()

    # --- 修改後的 draw_hud 方法 ---
    def draw_hud(self):
        """在畫面左下角並排顯示 P1 和 AI 的狀態資訊。"""
        if not self.hud_font:
            return

        line_height = self.hud_font.get_linesize() 
        start_x_p1 = 10
        start_x_ai_offset = 200 # AI 資訊相對於 P1 資訊的水平偏移量
        start_y = settings.SCREEN_HEIGHT - (line_height * 6) # 預留足夠的行數空間，從底部往上算

        # --- P1 資訊 (左列) ---
        p1_texts = []
        if self.player1:
            p1_texts.append(f"P1 Lives: {self.player1.lives}")
            p1_texts.append(f"P1 Bombs: {self.player1.max_bombs - self.player1.bombs_placed_count}/{self.player1.max_bombs}")
            p1_texts.append(f"P1 Range: {self.player1.bomb_range}")
            p1_texts.append(f"P1 Score: {self.player1.score}")

        for i, text in enumerate(p1_texts):
            surf = self.hud_font.render(text, True, settings.BLACK)
            self.screen.blit(surf, (start_x_p1, start_y + i * line_height))

        # --- AI 資訊 (右列) ---
        ai_texts = []
        if self.player2_ai:
            if self.player2_ai.is_alive:
                ai_texts.append(f"AI Lives: {self.player2_ai.lives}")
            else:
                ai_texts.append("AI Defeated")
            
            # 新增 AI 的炸彈數量和分數
            ai_texts.append(f"AI Bombs: {self.player2_ai.max_bombs - self.player2_ai.bombs_placed_count}/{self.player2_ai.max_bombs}")
            ai_texts.append(f"AI Range: {self.player2_ai.bomb_range}")
            ai_texts.append(f"AI Score: {self.player2_ai.score}")
            
            if self.ai_controller_p2 and self.ai_status_font:
                ai_name = self.ai_controller_p2.__class__.__name__.replace("AIController", "")
                state = getattr(self.ai_controller_p2, 'current_state', 'N/A')
                ai_texts.append(f"AI ({ai_name}): {state}")

        for i, text in enumerate(ai_texts):
            font_to_use = self.hud_font
            if text.startswith("AI (") and self.ai_status_font: # AI 狀態使用小一點的字體
                font_to_use = self.ai_status_font
            
            surf = font_to_use.render(text, True, settings.BLACK)
            self.screen.blit(surf, (start_x_p1 + start_x_ai_offset, start_y + i * line_height))

    def draw_game_over_screen(self):
        if not self.game_over_font or not self.restart_font:
            return

        msg = "GAME OVER"; color = settings.RED
        p1_alive = self.player1 and self.player1.is_alive
        ai_alive = self.player2_ai and self.player2_ai.is_alive

        if not p1_alive and not ai_alive: msg = "DRAW!"; color = settings.GREY
        elif not p1_alive: msg = "GAME OVER - You Lost!"
        elif not ai_alive: msg = "VICTORY - AI Defeated!"; color = settings.GREEN
        
        game_over_text = self.game_over_font.render(msg, True, color)
        text_rect = game_over_text.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 - 50))
        self.screen.blit(game_over_text, text_rect)
        
        restart_text = self.restart_font.render("Press 'R' to return to Menu", True, settings.BLACK)
        restart_rect = restart_text.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 + 20))
        self.screen.blit(restart_text, restart_rect)