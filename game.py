# oop-2025-proj-pycade/game.py

import pygame
import settings #
from core.map_manager import MapManager #
from sprites.player import Player #
from core.ai_controller import AIController #

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
        self.solid_obstacles_group = pygame.sprite.Group()

        self.map_manager = MapManager(self) #
        self.player1 = None
        self.player2_ai = None
        self.ai_controller_p2 = None

        self.hud_font = None
        self.game_over_font = None
        self.restart_font = None
        self.ai_status_font = None # ！！！新增 AI 狀態字型變數！！！
        try:
            self.hud_font = pygame.font.Font(None, 28)
            self.game_over_font = pygame.font.Font(None, 74)
            self.restart_font = pygame.font.Font(None, 30)
            self.ai_status_font = pygame.font.Font(None, 24) # ！！！初始化 AI 狀態字型！！！
        except Exception as e:
            print(f"Error initializing fonts: {e}")
            self.hud_font = pygame.font.SysFont("arial", 28)
            self.game_over_font = pygame.font.SysFont('arial', 74)
            self.restart_font = pygame.font.SysFont('arial', 30)
            self.ai_status_font = pygame.font.SysFont("arial", 24) # ！！！Fallback AI 狀態字型！！！
        
        self.setup_initial_state()

    def setup_initial_state(self):
        # print("[DEBUG] Game.setup_initial_state() called.") # DEBUG
        self.all_sprites.empty()
        self.players_group.empty()
        self.bombs_group.empty()
        self.explosions_group.empty()
        self.items_group.empty() 
        self.solid_obstacles_group.empty()

        grid_width = settings.GRID_SIZE if hasattr(settings, 'GRID_SIZE') else 15 
        grid_height = settings.GRID_SIZE if hasattr(settings, 'GRID_SIZE') else 11 
        
        p1_start_tile = (1, 1)
        p2_start_tile = (grid_width - 2, grid_height - 2)
        safe_radius = 1 

        # print("[DEBUG] Generating randomized map layout...") # DEBUG
        random_map_layout = self.map_manager.get_randomized_map_layout(
            grid_width, grid_height,
            p1_start_tile, p2_start_tile,
            safe_radius
        ) #
        self.map_manager.load_map_from_data(random_map_layout) #
        
        # print(f"[DEBUG] Map loaded. Walls: {len(self.map_manager.walls_group)}, D_Walls: {len(self.map_manager.destructible_walls_group)}, Solid: {len(self.solid_obstacles_group)}") # DEBUG

        # print("[DEBUG] Recreating player 1 (Human)...") # DEBUG
        player1_sprite_config = {
            "ROW_MAP": settings.PLAYER_SPRITESHEET_ROW_MAP, #
            "NUM_FRAMES": settings.PLAYER_NUM_WALK_FRAMES #
        }
        self.player1 = Player(self, p1_start_tile[0], p1_start_tile[1],
                              spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH, #
                              sprite_config=player1_sprite_config,
                              is_ai=False) #
        self.all_sprites.add(self.player1)
        self.players_group.add(self.player1)
        # print(f"[DEBUG] Player 1 created at tile {p1_start_tile}. Lives: {self.player1.lives}") # DEBUG

        # print("[DEBUG] Recreating player 2 (AI)...") # DEBUG
        ai_image_set_path = settings.PLAYER2_AI_SPRITESHEET_PATH \
            if hasattr(settings, 'PLAYER2_AI_SPRITESHEET_PATH') and settings.PLAYER2_AI_SPRITESHEET_PATH \
            else settings.PLAYER1_SPRITESHEET_PATH #
        ai_sprite_config = {
            "ROW_MAP": settings.PLAYER_SPRITESHEET_ROW_MAP, #
            "NUM_FRAMES": settings.PLAYER_NUM_WALK_FRAMES #
        }
        self.player2_ai = Player(self, p2_start_tile[0], p2_start_tile[1],
                                 spritesheet_path=ai_image_set_path,
                                 sprite_config=ai_sprite_config,
                                 is_ai=True) #
        self.ai_controller_p2 = AIController(self.player2_ai, self) #
        self.player2_ai.ai_controller = self.ai_controller_p2 #
        self.all_sprites.add(self.player2_ai)
        self.players_group.add(self.player2_ai)
        # print(f"[DEBUG] Player 2 (AI) created at tile {p2_start_tile}. Lives: {self.player2_ai.lives}") # DEBUG
        if self.ai_controller_p2:
            self.ai_controller_p2.human_player_sprite = self.player1 # ！！！確保 AIController 知道人類玩家是誰！！！
        
        self.game_state = "PLAYING"
        # print(f"[DEBUG] Total sprites in all_sprites after setup: {len(self.all_sprites)}") # DEBUG
        # print("[DEBUG] Game.setup_initial_state() finished.") # DEBUG

    def run(self):
        while self.running:
            self.dt = self.clock.tick(settings.FPS) / 1000.0 #
            self.events()
            self.update()
            self.draw()

    def events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: self.running = False
                if self.game_state == "PLAYING":
                    if event.key == pygame.K_f: # 人類玩家放炸彈的按鍵
                        if self.player1 and self.player1.is_alive: self.player1.place_bomb() #
                elif self.game_state == "GAME_OVER":
                    if event.key == pygame.K_r: # 按 R 重新開始
                        # print("[DEBUG] R key pressed in GAME_OVER state.") # DEBUG
                        self.setup_initial_state()

    def update(self):
        if self.game_state == "PLAYING":
            # ！！！注意更新順序：先更新 AI 控制器，讓它設定 AI 玩家的移動意圖！！！
            if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2: #
                self.ai_controller_p2.update() #
            
            self.all_sprites.update(self.dt, self.solid_obstacles_group) # 這會調用包括玩家在內所有 sprite 的 update

            # --- 碰撞檢測 ---
            # 玩家與爆炸的碰撞
            for player in list(self.players_group): # 要用 list() 複製，因為可能在迴圈中移除 player
                if player.is_alive: #
                    hit_explosions = pygame.sprite.spritecollide(player, self.explosions_group, False)
                    if hit_explosions: player.take_damage() #
            
            # 可破壞牆壁與爆炸的碰撞
            if hasattr(self.map_manager, 'destructible_walls_group'): #
                for d_wall in list(self.map_manager.destructible_walls_group): #
                    # 確保 d_wall 還存在 (take_damage 可能 kill 它)
                    if d_wall.alive(): # pygame.sprite.Sprite.alive()
                        hit_explosions_for_d_wall = pygame.sprite.spritecollide(d_wall, self.explosions_group, False)
                        if hit_explosions_for_d_wall: 
                            d_wall.take_damage() #
            
            # 玩家與道具的碰撞
            for player in list(self.players_group):
                if player.is_alive: #
                    items_collected = pygame.sprite.spritecollide(player, self.items_group, True) # True 表示拾取後道具消失
                    for item in items_collected: 
                        item.apply_effect(player) #
            
            # --- 遊戲結束判斷 ---
            human_player_alive = self.player1 and self.player1.is_alive #
            ai_player_alive = self.player2_ai and self.player2_ai.is_alive #

            if not human_player_alive and self.game_state != "GAME_OVER":
                # print("Game Over! Player 1 (Human) has been defeated.") # DEBUG
                self.game_state = "GAME_OVER"
            elif not ai_player_alive and human_player_alive and self.game_state != "GAME_OVER": # AI死了但人類還活著
                # print("Victory! Player 2 (AI) has been defeated.") # DEBUG
                self.game_state = "GAME_OVER"
            # ！！！可以加入平局的判斷，例如雙方同時死亡！！！
            elif not human_player_alive and not ai_player_alive and self.game_state != "GAME_OVER":
                # print("Draw! Both players are defeated.") # DEBUG
                self.game_state = "GAME_OVER"


        elif self.game_state == "GAME_OVER": 
            pass # GAME_OVER 狀態下不更新遊戲邏輯

    def draw(self):
        self.screen.fill(settings.WHITE) #
        # ！！！可以先繪製地圖網格（調試用）！！！
        # self.map_manager.draw_grid(self.screen) # 如果 MapManager 有 draw_grid 方法

        self.all_sprites.draw(self.screen)

        if self.game_state == "PLAYING":
            # --- 繪製 AI 路徑 (調試用) ---
            if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2: #
                if hasattr(self.ai_controller_p2, 'debug_draw_path'): #
                    self.ai_controller_p2.debug_draw_path(self.screen) #
            
            # --- 繪製 HUD ---
            hud_texts = []
            # P1 Info
            if self.player1 and self.hud_font:
                hud_texts.extend([
                    f"P1 Lives: {self.player1.lives}", #
                    f"P1 Bombs: {self.player1.max_bombs - self.player1.bombs_placed_count}/{self.player1.max_bombs}", #
                    f"P1 Range: {self.player1.bomb_range}", #
                    f"P1 Score: {self.player1.score}" #
                ])
            # AI Info
            if self.player2_ai and self.hud_font: #
                 if self.player2_ai.is_alive: #
                    hud_texts.append(f"AI Lives: {self.player2_ai.lives}") #
                 else:
                    hud_texts.append("AI Defeated")
                 
                 # ！！！新增：顯示 AI 狀態！！！
                 if self.ai_controller_p2 and self.ai_status_font: #
                    ai_state_text = f"AI State: {self.ai_controller_p2.current_state}" #
                    # ！！！可以考慮加入顯示 AI 目標（如果有的話）！！！
                    # E.g., if self.ai_controller_p2.current_target_item_sprite:
                    #    ai_state_text += f" (Target: Item {self.ai_controller_p2.current_target_item_sprite.type})"
                    hud_texts.append(ai_state_text)

            # 統一繪製HUD文本
            line_height = 22
            start_y_offset = 10 # 從底部往上的起始偏移
            for i, text_line in enumerate(reversed(hud_texts)): # 從列表尾部開始，這樣第一項在最下面
                font_to_use = self.hud_font
                if "AI State:" in text_line and self.ai_status_font:
                    font_to_use = self.ai_status_font
                
                text_surface = font_to_use.render(text_line, True, settings.BLACK) #
                text_pos_y = settings.SCREEN_HEIGHT - start_y_offset - (i + 1) * line_height #
                self.screen.blit(text_surface, (10, text_pos_y))

        elif self.game_state == "GAME_OVER":
            if self.game_over_font and self.restart_font:
                msg = "GAME OVER"; color = settings.RED #
                # ！！！更明確的遊戲結束訊息！！！
                p1_alive = self.player1 and self.player1.is_alive #
                ai_alive = self.player2_ai and self.player2_ai.is_alive #

                if not p1_alive and not ai_alive:
                    msg = "DRAW!"
                    color = settings.GREY #
                elif not p1_alive:
                    msg = "GAME OVER - You Lost!"
                elif not ai_alive:
                    msg = "VICTORY - AI Defeated!"
                    color = settings.GREEN #
                
                game_over_text = self.game_over_font.render(msg, True, color)
                text_rect = game_over_text.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 - 50)) #
                self.screen.blit(game_over_text, text_rect)
                restart_text = self.restart_font.render("Press 'R' to Restart", True, settings.BLACK) #
                restart_rect = restart_text.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 + 20)) #
                self.screen.blit(restart_text, restart_rect)
        
        pygame.display.flip()