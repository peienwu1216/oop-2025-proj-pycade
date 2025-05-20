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
        # Pass necessary arguments to player's update method
        # For now, player update doesn't need walls_group, but it will soon.
        self.all_sprites.update(self.dt, self.map_manager.walls_group) # Pass walls_group
        # --- 爆炸與玩家/牆壁的碰撞檢測將在這裡添加 ---
            # Check for explosion collisions with players
            # for player in self.players_group:
            #     hits = pygame.sprite.spritecollide(player, self.explosions_group, False)
            #     if hits:
            #         player.take_damage() # 假設 Player 有 take_damage 方法
            #         print(f"Player {id(player)} hit by explosion!")

            # Check for explosion collisions with destructible walls (LATER)
            # for d_wall in self.map_manager.destructible_walls_group: # 假設有這個 group
            #     hits = pygame.sprite.spritecollide(d_wall, self.explosions_group, False)
            #     if hits:
            #         d_wall.destroy() # 假設 DestructibleWall 有 destroy 方法
            #         print(f"Destructible wall at ({d_wall.rect.x}, {d_wall.rect.y}) hit!")

    def draw(self):
        self.screen.fill(settings.BLACK)
        self.all_sprites.draw(self.screen)
        # self.map_manager.draw_grid(self.screen)
        pygame.display.flip()