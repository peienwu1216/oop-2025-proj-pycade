# oop-2025-proj-pycade/game.py

import pygame
import settings
from core.map_manager import MapManager
from sprites.player import Player # Import Player class

class Game:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock
        self.running = True
        self.game_state = "PLAYING"

        self.all_sprites = pygame.sprite.Group()
        self.players_group = pygame.sprite.Group() # Group specifically for players
        
        self.bombs_group = pygame.sprite.Group() 
        self.explosions_group = pygame.sprite.Group()
        self.map_manager = MapManager(self)
        self.player1 = None # Placeholder for player 1 instance

        # self.load_assets()
        self.setup_initial_state()

    def setup_initial_state(self):
        """Sets up the initial game state."""
        print(f"Map loaded. Number of walls: {len(self.map_manager.walls_group)}")

        start_tile_x, start_tile_y = 1, 1
        if self.map_manager.is_walkable(start_tile_x, start_tile_y):
            self.player1 = Player(self, start_tile_x, start_tile_y) # Pass 'self' (the game instance)
            self.all_sprites.add(self.player1)
            self.players_group.add(self.player1)
            print(f"Player 1 created at tile ({start_tile_x}, {start_tile_y})")
        else:
            print(f"Error: Could not find a walkable starting position for Player 1 at ({start_tile_x}, {start_tile_y})")
            self.player1 = Player(self, 2, 1) # Pass 'self'
            self.all_sprites.add(self.player1)
            self.players_group.add(self.player1)
        print(f"Total sprites in all_sprites: {len(self.all_sprites)}")

    # def load_assets(self):
    #     pass

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
                if self.game_state == "PLAYING": # 確保只在遊戲進行中才能放炸彈
                    if event.key == pygame.K_f: # 假設 F 鍵是玩家1的炸彈鍵
                        if self.player1:
                            self.player1.place_bomb()
                    # 如果有玩家2，在這裡添加玩家2的炸彈鍵響應
                    # elif event.key == pygame.K_j: # 假設 J 鍵是玩家2的炸彈鍵 (你的C++設定)
                    #     if self.player2: # 假設有 self.player2
                    #         self.player2.place_bomb()
            # We are using pygame.key.get_pressed() in Player.get_input()
            # so specific keydown events for movement are not strictly needed here,
            # unless you want single press actions.

    def update(self):
        """
        Updates the game state based on the current self.game_state.
        Handles sprite updates, collisions, and game logic.
        """
        if self.game_state == "PLAYING":
            # 1. 更新所有 Sprites
            #    - Player.update 會處理輸入、移動、與牆壁碰撞
            #    - Bomb.update 會處理倒數計時、視覺更新、時間到了調用 explode()
            #    - Explosion.update 會處理持續時間，時間到了 self.kill()
            #    - Wall.update (目前是 pass)
            self.all_sprites.update(self.dt, self.map_manager.walls_group)

            # 2. 處理爆炸對玩家的傷害
            #    迭代 players_group 中的每個活著的玩家
            for player in list(self.players_group): # 使用 list() 複製以允許在迭代中移除 player
                if player.is_alive:
                    # 檢測此玩家是否與 explosions_group 中的任何爆炸 Sprite 碰撞
                    hit_explosions = pygame.sprite.spritecollide(player, self.explosions_group, False) # False: 不移除爆炸
                    if hit_explosions:
                        # 只要碰撞到，就受到一次傷害 (take_damage 內部處理無敵時間)
                        player.take_damage()
                        # print(f"Player {id(player)} was in explosion area.") # 可選調試訊息
            if hasattr(self.map_manager, 'destructible_walls_group'): # 確保 MapManager 有這個組
                for d_wall in list(self.map_manager.destructible_walls_group): # 使用 list() 複製
                    # 檢測此可破壞牆壁是否與 explosions_group 中的任何爆炸 Sprite 碰撞
                    hit_explosions_for_d_wall = pygame.sprite.spritecollide(d_wall, self.explosions_group, False)
                    if hit_explosions_for_d_wall:
                        d_wall.take_damage() # DestructibleWall 的 take_damage 會處理 self.kill()
            # 3. 處理爆炸對可破壞牆壁的傷害 (我們稍後會添加 DestructibleWall)
            # if hasattr(self.map_manager, 'destructible_walls_group'):
            #     for d_wall in list(self.map_manager.destructible_walls_group):
            #         hit_explosions = pygame.sprite.spritecollide(d_wall, self.explosions_group, False)
            #         if hit_explosions:
            #             d_wall.take_damage() # 假設 DestructibleWall 也有 take_damage 或 destroy 方法

            # 4. 檢查遊戲結束條件
            #    例如，如果只有一個人類玩家 (self.player1)
            if self.player1 and not self.player1.is_alive:
                # 為了防止在同一幀內多次觸發 GAME_OVER 邏輯
                if self.game_state != "GAME_OVER": # 只有在狀態改變時才打印和切換
                    print("Game Over! Player 1 has been defeated.")
                    self.game_state = "GAME_OVER"
                    # 在這裡可以觸發 UIManager 顯示遊戲結束畫面
                    # self.ui_manager.show_game_over_screen()

            # (如果有多個玩家，遊戲結束條件會更複雜)

        elif self.game_state == "GAME_OVER":
            # 在遊戲結束狀態下，通常不會更新遊戲世界的邏輯
            # 可能會更新 UI 動畫或等待輸入
            # 例如: self.ui_manager.update_game_over_screen(self.dt)
            pass

        elif self.game_state == "MENU":
            # 更新主選單的邏輯
            # 例如: self.ui_manager.update_menu_screen(self.dt)
            pass
        
        # (可以添加更多遊戲狀態，如 PAUSED, LEVEL_TRANSITION 等)
    
    def draw(self):
        self.screen.fill(settings.BLACK)
        self.all_sprites.draw(self.screen) # 繪製所有遊戲物件

        if self.game_state == "PLAYING":
            # 在遊戲進行中，可能需要繪製 HUD (生命、分數等)
            # self.ui_manager.draw_hud() # 假設 UIManager 負責
            pass
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

            restart_text = self.restart_font.render("Press 'R' to Restart", True, settings.WHITE)
            restart_rect = restart_text.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 + 20))
            self.screen.blit(restart_text, restart_rect)


        elif self.game_state == "MENU":
            # 繪製主選單畫面
            # self.ui_manager.draw_menu_screen()
            pass
            
        # self.map_manager.draw_grid(self.screen) # 可選調試
        pygame.display.flip()