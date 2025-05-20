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

        self.setup_initial_state() # 調用以設定初始狀態

    def setup_initial_state(self):
        # ... (清空 sprite groups 的邏輯保持不變) ...
        print("[DEBUG] Game.setup_initial_state() called.")
        print("[DEBUG] Emptying sprite groups...")
        self.all_sprites.empty()
        self.players_group.empty()
        self.bombs_group.empty()
        self.explosions_group.empty()
        if hasattr(self, 'items_group'): self.items_group.empty()
        if hasattr(self, 'solid_obstacles_group'): self.solid_obstacles_group.empty()


        print("[DEBUG] Reloading map data...")
        self.map_manager.load_map_from_data(self.map_manager.get_simple_test_map())
        # ... (print map reloaded stats) ...
        print(f"[DEBUG] Map reloaded. Walls: {len(self.map_manager.walls_group)}, D_Walls: {len(self.map_manager.destructible_walls_group)}, Solid: {len(self.solid_obstacles_group)}")


        # --- 創建玩家1 (人類) ---
        print("[DEBUG] Recreating player 1 (Human)...")
        p1_start_x, p1_start_y = 1, 1
        # ！！！修改：準備 sprite_config 並傳遞給 Player！！！
        player1_sprite_config = {
            "ROW_MAP": settings.PLAYER_SPRITESHEET_ROW_MAP,
            "NUM_FRAMES": settings.PLAYER_NUM_WALK_FRAMES
        }
        if self.map_manager.is_walkable(p1_start_x, p1_start_y):
            self.player1 = Player(self, p1_start_x, p1_start_y,
                                  spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH,
                                  sprite_config=player1_sprite_config,
                                  is_ai=False)
        else:
            self.player1 = Player(self, 2, 1,
                                  spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH,
                                  sprite_config=player1_sprite_config,
                                  is_ai=False)
        self.all_sprites.add(self.player1)
        self.players_group.add(self.player1)
        print(f"[DEBUG] Player 1 created. Lives: {self.player1.lives}")

        # --- 創建 AI 玩家 (Player 2) ---
        print("[DEBUG] Recreating player 2 (AI)...")
        p2_start_x = self.map_manager.tile_width - 2
        p2_start_y = self.map_manager.tile_height - 2
        if not self.map_manager.is_walkable(p2_start_x, p2_start_y):
            p2_start_x, p2_start_y = self.map_manager.tile_width - 3, self.map_manager.tile_height - 2

        # ！！！修改：為 AI 玩家準備 sprite_config 並傳遞！！！
        # 假設 AI 使用不同的 spritesheet 和可能的配置
        # 如果 AI 使用與 P1 相同的動畫幀數和行映射，則 sprite_config 可以相同
        ai_spritesheet_path = settings.PLAYER2_AI_SPRITESHEET_PATH \
            if hasattr(settings, 'PLAYER2_AI_SPRITESHEET_PATH') and settings.PLAYER2_AI_SPRITESHEET_PATH \
            else settings.PLAYER1_SPRITESHEET_PATH # Fallback to P1 sheet if P2 not defined

        # 假設 AI 的 sprite sheet 佈局與 P1 相同
        # 如果不同，你需要在 settings.py 中為 PLAYER2_AI 定義類似的 ROW_MAP 和 NUM_FRAMES
        ai_sprite_config = {
            "ROW_MAP": settings.PLAYER_SPRITESHEET_ROW_MAP, # 或者 settings.PLAYER2_AI_ROW_MAP
            "NUM_FRAMES": settings.PLAYER_NUM_WALK_FRAMES   # 或者 settings.PLAYER2_AI_NUM_FRAMES
        }
        self.player2_ai = Player(self, p2_start_x, p2_start_y,
                                 spritesheet_path=ai_spritesheet_path,
                                 sprite_config=ai_sprite_config,
                                 is_ai=True)
        
        self.ai_controller_p2 = AIController(self.player2_ai, self)
        self.player2_ai.ai_controller = self.ai_controller_p2

        self.all_sprites.add(self.player2_ai)
        self.players_group.add(self.player2_ai)
        print(f"[DEBUG] Player 2 (AI) created at tile ({p2_start_x}, {p2_start_y}). Lives: {self.player2_ai.lives}")
        if self.ai_controller_p2:
            self.ai_controller_p2.target_player = self.player1
        
        self.game_state = "PLAYING"
        print(f"[DEBUG] Total sprites in all_sprites after setup: {len(self.all_sprites)}")
        print("[DEBUG] Game.setup_initial_state() finished.")

    # ... (run method) ...
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
                        print("[DEBUG] R key pressed in GAME_OVER state.") # <--- 確認事件被捕捉
                        self.setup_initial_state()

    def update(self):
        """
        Updates the game state based on the current self.game_state.
        Handles sprite updates, collisions, and game logic.
        """
        if self.game_state == "PLAYING":
            # ！！！修改開始：確保只調用一次 all_sprites.update，並傳遞正確的碰撞組！！！
            # Player.update 方法期望的第二個參數是包含所有固態障礙物的組
            self.all_sprites.update(self.dt, self.solid_obstacles_group)
            # ！！！修改結束！！！

            # AI Controller 的更新應該在所有 Sprite 的基礎 update 完成之後，
            # 或者在其自己的邏輯中處理與 Player Sprite 的交互。
            # 我們的 AIController.update() 內部會決定 AI 的 vx, vy，
            # 然後 Player.update() 會應用這些 vx, vy。
            if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2:
                self.ai_controller_p2.update() # AIController 決定 AI 玩家的 vx, vy

            # --- 後續的碰撞邏輯保持不變 ---
            # 2. 處理爆炸對玩家的傷害
            for player in list(self.players_group):
                if player.is_alive:
                    hit_explosions = pygame.sprite.spritecollide(player, self.explosions_group, False)
                    if hit_explosions:
                        player.take_damage()
            
            # 處理爆炸對可破壞牆壁的傷害
            if hasattr(self.map_manager, 'destructible_walls_group'):
                for d_wall in list(self.map_manager.destructible_walls_group):
                    hit_explosions_for_d_wall = pygame.sprite.spritecollide(d_wall, self.explosions_group, False)
                    if hit_explosions_for_d_wall:
                        d_wall.take_damage()
            
            # 3. 檢查玩家是否收集到道具
            for player in self.players_group:
                if player.is_alive:
                    items_collected = pygame.sprite.spritecollide(player, self.items_group, True)
                    for item in items_collected:
                        item.apply_effect(player)
                        # print(f"Player {id(player)} collected item type: {item.type}") # item.apply_effect 內部有 print
            
            # 4. 檢查遊戲結束條件
            # ... (遊戲結束條件邏輯保持不變) ...
            human_player_alive = self.player1 and self.player1.is_alive
            ai_player_alive = self.player2_ai and self.player2_ai.is_alive

            if not human_player_alive and self.game_state != "GAME_OVER":
                print("Game Over! Player 1 (Human) has been defeated.")
                self.game_state = "GAME_OVER"
            elif not ai_player_alive and human_player_alive and self.game_state != "GAME_OVER": # 確保 P1 還活著才算勝利
                print("Victory! Player 2 (AI) has been defeated.")
                self.game_state = "GAME_OVER" # 或者你可以定義一個 "VICTORY" 狀態
            # 如果需要平局判斷 (例如兩者同時死亡)，可以在 Player.die() 中設置一個標記給 Game 類檢查

        elif self.game_state == "GAME_OVER":
            pass
        elif self.game_state == "MENU":
            # 更新主選單的邏輯
            # 例如: self.ui_manager.update_menu_screen(self.dt)
            pass
        
        # (可以添加更多遊戲狀態，如 PAUSED, LEVEL_TRANSITION 等)
    
    def draw(self):
        self.screen.fill(settings.WHITE)
        self.all_sprites.draw(self.screen) # 繪製所有遊戲物件

        # --- 5. (可選) 調用 AIController 的 debug_draw_path ---
        if self.game_state == "PLAYING":
            if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2:
                if hasattr(self.ai_controller_p2, 'debug_draw_path'): # 確保方法存在
                    self.ai_controller_p2.debug_draw_path(self.screen)
        # --- debug_draw_path 結束 ---

        if self.game_state == "PLAYING":
            if self.player1:
                if not hasattr(self, 'hud_font'):
                    try: self.hud_font = pygame.font.Font(None, 28)
                    except: self.hud_font = pygame.font.SysFont("arial", 28)
                
                hud_texts = [] # 先收集所有要顯示的文本行
                p1_prefix = "P1 " # 為玩家1的資訊加上前綴
                hud_texts.append(f"{p1_prefix}Lives: {self.player1.lives}")
                hud_texts.append(f"{p1_prefix}Bombs: {self.player1.max_bombs - self.player1.bombs_placed_count}/{self.player1.max_bombs}")
                hud_texts.append(f"{p1_prefix}Range: {self.player1.bomb_range}")
                hud_texts.append(f"{p1_prefix}Score: {self.player1.score}")

                if self.player2_ai and self.player2_ai.is_alive: # 如果有 AI 玩家且存活
                    ai_prefix = "AI "
                    hud_texts.append(f"{ai_prefix}Lives: {self.player2_ai.lives}")
                    # 如果想顯示更多AI資訊，可以在這裡添加

                # ！！！修改開始：將 HUD 移到螢幕底部！！！
                hud_start_y = settings.SCREEN_HEIGHT - (len(hud_texts) * 22) - 5 # 計算起始 Y 座標，每行高度約22，底部留5像素邊距
                if hud_start_y < settings.SCREEN_HEIGHT * 0.75: # 確保不會太靠上
                    hud_start_y = settings.SCREEN_HEIGHT * 0.75

                # 可以選擇在底部繪製一個半透明的背景條，讓HUD更清晰
                # hud_panel_height = (len(hud_texts) * 22) + 10
                # hud_panel_rect = pygame.Rect(0, settings.SCREEN_HEIGHT - hud_panel_height, settings.SCREEN_WIDTH, hud_panel_height)
                # panel_surface = pygame.Surface(hud_panel_rect.size, pygame.SRCALPHA)
                # panel_surface.fill((50, 50, 50, 180)) # 深灰色半透明
                # self.screen.blit(panel_surface, hud_panel_rect.topleft)


                for i, text_line in enumerate(hud_texts):
                    if hasattr(self, 'hud_font') and self.hud_font:
                        text_surface = self.hud_font.render(text_line, True, settings.BLACK)
                        # 繪製在螢幕底部，水平居中或靠左
                        # text_rect = text_surface.get_rect(left=10, top=hud_start_y + i * 22)
                        text_rect = text_surface.get_rect(centerx=settings.SCREEN_WIDTH / 2, top=hud_start_y + i * 22)
                        self.screen.blit(text_surface, text_rect)
                    # ！！！修改結束：將 HUD 移到螢幕底部！！！

        elif self.game_state == "GAME_OVER":
            # 繪製遊戲結束畫面
            # self.ui_manager.draw_game_over_screen()
            # 暫時簡單顯示文字
            if not hasattr(self, 'game_over_font'): # 避免每幀都創建字型
                try:
                    self.game_over_font = pygame.font.Font(None, 74)
                except:
                    self.game_over_font = pygame.font.SysFont('arial', 74)
                try:
                    self.restart_font = pygame.font.Font(None, 30)
                except:
                    self.restart_font = pygame.font.SysFont('arial', 30)

            game_over_text = self.game_over_font.render("GAME OVER", True, settings.RED)
            text_rect = game_over_text.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 - 50))
            self.screen.blit(game_over_text, text_rect)

            restart_text = self.restart_font.render("Press 'R' to Restart", True, settings.BLACK)
            restart_rect = restart_text.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 + 20))
            self.screen.blit(restart_text, restart_rect)


        elif self.game_state == "MENU":
            # 繪製主選單畫面
            # self.ui_manager.draw_menu_screen()
            pass
            
        # self.map_manager.draw_grid(self.screen) # 可選調試
        pygame.display.flip()