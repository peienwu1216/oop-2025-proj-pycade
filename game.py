# oop-2025-proj-pycade/game.py

import pygame
import settings
from core.map_manager import MapManager
from sprites.player import Player
from core.ai_controller import AIController

class Game:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock
        self.running = True
        self.game_state = "PLAYING" # 初始狀態，會被 setup_initial_state 再次設定

        self.all_sprites = pygame.sprite.Group()
        self.players_group = pygame.sprite.Group()
        self.bombs_group = pygame.sprite.Group()
        self.explosions_group = pygame.sprite.Group()
        self.items_group = pygame.sprite.Group() 

        self.solid_obstacles_group = pygame.sprite.Group() # 用於玩家碰撞

        self.map_manager = MapManager(self)
        self.player1 = None
        self.player2_ai = None
        self.ai_controller_p2 = None

        self.hud_font = None
        self.game_over_font = None
        self.restart_font = None
        try:
            self.hud_font = pygame.font.Font(None, 28)
            self.game_over_font = pygame.font.Font(None, 74)
            self.restart_font = pygame.font.Font(None, 30)
        except Exception as e:
            print(f"Error initializing fonts: {e}")
            self.hud_font = pygame.font.SysFont("arial", 28)
            self.game_over_font = pygame.font.SysFont('arial', 74)
            self.restart_font = pygame.font.SysFont('arial', 30)
        
        self.setup_initial_state() # 調用以設定初始狀態

    def setup_initial_state(self):
        print("[DEBUG] Game.setup_initial_state() called.")
        self.all_sprites.empty()
        self.players_group.empty()
        self.bombs_group.empty()
        self.explosions_group.empty()
        self.items_group.empty() # 確保 items_group 也被清空
        self.solid_obstacles_group.empty()

        # --- ！！！定義玩家出生點和地圖尺寸！！！ ---
        # 假設地圖寬高與你的 settings.GRID_SIZE (如果有的話) 或一個固定值相關
        # 我們使用 settings.py 中的 TILE_SIZE 和一個虛擬的 GRID_SIZE 來確定地圖大小
        # 如果 settings.py 中沒有 GRID_SIZE，可以先在這裡定義一個
        grid_width = settings.GRID_SIZE if hasattr(settings, 'GRID_SIZE') else 15 # 例如15格寬
        grid_height = settings.GRID_SIZE if hasattr(settings, 'GRID_SIZE') else 11 # 例如11格高
        
        # 玩家1出生在左上角附近，但不在邊緣
        p1_start_tile = (1, 1)
        # AI玩家出生在右下角附近
        p2_start_tile = (grid_width - 2, grid_height - 2)
        safe_radius = 1 # 出生點周圍1格內（3x3區域）是安全的

        # --- ！！！調用 MapManager 生成隨機地圖佈局！！！ ---
        print("[DEBUG] Generating randomized map layout...")
        random_map_layout = self.map_manager.get_randomized_map_layout(
            grid_width, grid_height,
            p1_start_tile, p2_start_tile,
            safe_radius
        )
        self.map_manager.load_map_from_data(random_map_layout) # 使用新生成的佈局加載地圖
        
        print(f"[DEBUG] Map loaded. Walls: {len(self.map_manager.walls_group)}, D_Walls: {len(self.map_manager.destructible_walls_group)}, Solid: {len(self.solid_obstacles_group)}")

        # --- 創建玩家1 (人類) ---
        print("[DEBUG] Recreating player 1 (Human)...")
        player1_sprite_config = {
            "ROW_MAP": settings.PLAYER_SPRITESHEET_ROW_MAP,
            "NUM_FRAMES": settings.PLAYER_NUM_WALK_FRAMES
        }
        # ！！確保 p1_start_tile 是可通行的，雖然 get_randomized_map_layout 應該已經保證了空格！！
        self.player1 = Player(self, p1_start_tile[0], p1_start_tile[1],
                              spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH,
                              sprite_config=player1_sprite_config,
                              is_ai=False)
        self.all_sprites.add(self.player1)
        self.players_group.add(self.player1)
        print(f"[DEBUG] Player 1 created at tile {p1_start_tile}. Lives: {self.player1.lives}")

        # --- 創建 AI 玩家 (Player 2) ---
        print("[DEBUG] Recreating player 2 (AI)...")
        ai_image_set_path = settings.PLAYER2_AI_SPRITESHEET_PATH \
            if hasattr(settings, 'PLAYER2_AI_SPRITESHEET_PATH') and settings.PLAYER2_AI_SPRITESHEET_PATH \
            else settings.PLAYER1_SPRITESHEET_PATH
        ai_sprite_config = {
            "ROW_MAP": settings.PLAYER_SPRITESHEET_ROW_MAP, # 假設AI動畫佈局與P1相同
            "NUM_FRAMES": settings.PLAYER_NUM_WALK_FRAMES
        }
        self.player2_ai = Player(self, p2_start_tile[0], p2_start_tile[1],
                                 spritesheet_path=ai_image_set_path,
                                 sprite_config=ai_sprite_config,
                                 is_ai=True)
        self.ai_controller_p2 = AIController(self.player2_ai, self)
        self.player2_ai.ai_controller = self.ai_controller_p2
        self.all_sprites.add(self.player2_ai)
        self.players_group.add(self.player2_ai)
        print(f"[DEBUG] Player 2 (AI) created at tile {p2_start_tile}. Lives: {self.player2_ai.lives}")
        if self.ai_controller_p2:
            self.ai_controller_p2.target_player = self.player1
        
        self.game_state = "PLAYING"
        print(f"[DEBUG] Total sprites in all_sprites after setup: {len(self.all_sprites)}")
        print("[DEBUG] Game.setup_initial_state() finished.")

    def run(self):
        while self.running:
            self.dt = self.clock.tick(settings.FPS) / 1000.0
            self.events()
            self.update()
            self.draw()

    def events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: self.running = False
                if self.game_state == "PLAYING":
                    if event.key == pygame.K_f:
                        if self.player1 and self.player1.is_alive: self.player1.place_bomb()
                elif self.game_state == "GAME_OVER":
                    if event.key == pygame.K_r:
                        print("[DEBUG] R key pressed in GAME_OVER state."); self.setup_initial_state()

    def update(self):
        if self.game_state == "PLAYING":
            self.all_sprites.update(self.dt, self.solid_obstacles_group)
            if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2:
                self.ai_controller_p2.update()
            for player in list(self.players_group):
                if player.is_alive:
                    hit_explosions = pygame.sprite.spritecollide(player, self.explosions_group, False)
                    if hit_explosions: player.take_damage()
            if hasattr(self.map_manager, 'destructible_walls_group'):
                for d_wall in list(self.map_manager.destructible_walls_group):
                    hit_explosions_for_d_wall = pygame.sprite.spritecollide(d_wall, self.explosions_group, False)
                    if hit_explosions_for_d_wall: d_wall.take_damage()
            for player in list(self.players_group):
                if player.is_alive:
                    items_collected = pygame.sprite.spritecollide(player, self.items_group, True)
                    for item in items_collected: item.apply_effect(player)
            
            human_player_alive = self.player1 and self.player1.is_alive
            ai_player_alive = self.player2_ai and self.player2_ai.is_alive
            if not human_player_alive and self.game_state != "GAME_OVER":
                print("Game Over! Player 1 (Human) has been defeated."); self.game_state = "GAME_OVER"
            elif not ai_player_alive and human_player_alive and self.game_state != "GAME_OVER":
                print("Victory! Player 2 (AI) has been defeated."); self.game_state = "GAME_OVER"
        elif self.game_state == "GAME_OVER": pass

    def draw(self):
        self.screen.fill(settings.WHITE)
        self.all_sprites.draw(self.screen)
        if self.game_state == "PLAYING":
            if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2:
                if hasattr(self.ai_controller_p2, 'debug_draw_path'):
                    self.ai_controller_p2.debug_draw_path(self.screen)
            if self.player1 and self.hud_font: # 檢查 self.hud_font 是否已初始化
                hud_texts = [f"P1 Lives: {self.player1.lives}",
                             f"P1 Bombs: {self.player1.max_bombs - self.player1.bombs_placed_count}/{self.player1.max_bombs}",
                             f"P1 Range: {self.player1.bomb_range}",
                             f"P1 Score: {self.player1.score}"]
                if self.player2_ai and self.player2_ai.is_alive:
                     hud_texts.append(f"AI Lives: {self.player2_ai.lives}")
                for i, text_line in enumerate(hud_texts):
                    text_surface = self.hud_font.render(text_line, True, settings.BLACK)
                    self.screen.blit(text_surface, (10, settings.SCREEN_HEIGHT - (len(hud_texts) - i) * 22 - 5 )) # 繪製在底部
        elif self.game_state == "GAME_OVER":
            if self.game_over_font and self.restart_font: # 檢查字型是否已初始化
                msg = "GAME OVER"; color = settings.RED
                if self.player1 and not self.player1.is_alive: msg = "GAME OVER - You Lost!"
                elif self.player2_ai and not self.player2_ai.is_alive and self.player1 and self.player1.is_alive :
                    msg = "VICTORY - AI Defeated!"; color = settings.GREEN # 勝利用綠色
                game_over_text = self.game_over_font.render(msg, True, color)
                text_rect = game_over_text.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 - 50))
                self.screen.blit(game_over_text, text_rect)
                restart_text = self.restart_font.render("Press 'R' to Restart", True, settings.BLACK)
                restart_rect = restart_text.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 + 20))
                self.screen.blit(restart_text, restart_rect)
        pygame.display.flip()