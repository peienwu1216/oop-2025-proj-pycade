# oop-2025-proj-pycade/game.py (REVISED FOR WEBGAME)

import pygame
import settings
from core.map_manager import MapManager
from sprites.player import Player
from core.leaderboard_manager import LeaderboardManager

# AI 控制器匯入
from core.ai_controller import AIController as OriginalAIController
from core.ai_conservative import ConservativeAIController
from core.ai_aggressive import AggressiveAIController
from core.ai_item_focused import ItemFocusedAIController
from sprites.draw_text import DIGIT_MAP
from sprites.draw_text import draw_text_with_shadow, draw_text_with_outline


class Game:
    def __init__(self, screen, clock, ai_archetype="original", headless=False):
        self.headless = headless 
        self.screen = screen
        self.clock = clock
        pygame.mixer.music.load(settings.GAME_MUSIC_PATH)
        pygame.mixer.music.set_volume(settings.MENU_MUSIC_VOLUME)
        pygame.mixer.music.play(-1) 
        self.running = True # 這個 self.running 仍然有用，用來標記 Game 場景是否應該繼續
        self.dt = 0 # dt 會在 run_one_frame 中更新
        self.restart_game = False # 這個旗標用來告訴 main.py 是否要回到選單
        self.game_state = "PLAYING"
        self.ai_archetype = ai_archetype
        
        self.victory_music_played = False
        self.game_over_played = False
        

        # --- Background ---
        self.brick_tile_image = pygame.image.load(settings.STONE_0_IMG).convert()
        self.brick_tile_image = pygame.transform.smoothscale(
            self.brick_tile_image,
            (settings.TILE_SIZE, settings.TILE_SIZE)
        )
        self.border_brick = pygame.image.load(settings.WALL_SOLID_IMG).convert()
        self.border_brick = pygame.transform.smoothscale(
            self.border_brick,
            (settings.TILE_SIZE, settings.TILE_SIZE)
        )
        self.beside_brick = pygame.image.load(settings.STONE_1_IMG).convert()
        self.beside_brick = pygame.transform.smoothscale(
            self.beside_brick,
            (settings.TILE_SIZE, settings.TILE_SIZE)
        )
        self.timer_brick = pygame.image.load(settings.STONE_2_IMG).convert()
        self.timer_brick = pygame.transform.smoothscale(
            self.timer_brick,
            (settings.TILE_SIZE, settings.TILE_SIZE)
        )
        self.text_brick = pygame.image.load(settings.STONE_3_IMG).convert()
        self.text_brick = pygame.transform.smoothscale(
            self.text_brick,
            (settings.TILE_SIZE, settings.TILE_SIZE)
        )

        # --- Sprite Groups ---
        self.all_sprites = pygame.sprite.Group()
        self.players_group = pygame.sprite.Group()
        self.bombs_group = pygame.sprite.Group()
        self.explosions_group = pygame.sprite.Group()
        self.items_group = pygame.sprite.Group()
        self.solid_obstacles_group = pygame.sprite.Group()

        # --- Managers and Player/AI instances ---
        self.map_manager = MapManager(self)
        self.player1 = None
        self.player2_ai = None
        self.ai_controller_p2 = None
        self.player1_bomb_toggle = 0


        # --- Timer related attributes ---
        self.time_elapsed_seconds = 0
        self.game_timer_active = False
        self.time_up_winner = None

        # --- Leaderboard Manager ---
        self.leaderboard_manager = LeaderboardManager()

        # --- Text Input related attributes ---
        self.player_name_input = ""
        self.input_box_active = False
        self.name_input_rect = pygame.Rect(
            settings.SCREEN_WIDTH // 2 - 140,
            settings.SCREEN_HEIGHT // 2 - 20,
            280, 40
        )
        self.score_to_submit = 0

        self.score_submitted_message_timer = 0.0
        self.score_submitted_message_duration = 3.0

        # --- Font attributes ---
        self.hud_font = None
        self.game_over_font = None
        self.restart_font = None
        self.ai_status_font = None
        self.timer_font_normal = None
        self.timer_font_urgent = None
        self.text_input_font = None
        self.prompt_font = None
        self.message_font = None

        try:
            font_size = 22
            # font_status_size = 18
            timer_font_size_normal = 28
            timer_font_size_urgent = 36
            text_input_font_size = getattr(settings, "TEXT_INPUT_FONT_SIZE", 32)
            prompt_font_size = 48
            message_font_size = 38

            default_font_path = None
            if hasattr(settings, 'CHINESE_FONT_PATH') and settings.CHINESE_FONT_PATH:
                try:
                    font_test = pygame.font.Font(settings.CHINESE_FONT_PATH, 10)
                    if font_test:
                        default_font_path = settings.CHINESE_FONT_PATH
                except pygame.error as e:
                    print(f"Game: 中文字體 '{settings.CHINESE_FONT_PATH}' 載入失敗 ({e})，將使用預設字體。")

            self.hud_font = pygame.font.Font(settings.PIXEL_FONT_PATH, font_size)
            self.ai_status_font = pygame.font.Font(settings.CHINESE_FONT_PATH, 18)
            self.timer_font_normal = pygame.font.Font(default_font_path, timer_font_size_normal)
            self.timer_font_urgent = pygame.font.Font(default_font_path, timer_font_size_urgent)
            self.text_input_font = pygame.font.Font(default_font_path, text_input_font_size)
            self.prompt_font = pygame.font.Font(default_font_path, prompt_font_size)
            self.message_font = pygame.font.Font(default_font_path, message_font_size)

            self.game_over_font = pygame.font.Font(settings.TITLE_FONT_PATH, 50)
            self.restart_font = pygame.font.Font(settings.SUB_TITLE_FONT_PATH, 25)

        except Exception as e:
            print(f"Error initializing fonts in Game: {e}")
            self.hud_font = pygame.font.SysFont("arial", 24)
            self.ai_status_font = pygame.font.SysFont("arial", 20)
            self.timer_font_normal = pygame.font.SysFont("arial", 30)
            self.timer_font_urgent = pygame.font.SysFont("arial", 38)
            self.text_input_font = pygame.font.SysFont("arial", getattr(settings, "TEXT_INPUT_FONT_SIZE", 32))
            self.prompt_font = pygame.font.SysFont("arial", 48)
            self.message_font = pygame.font.SysFont("arial", 38)
            self.game_over_font = pygame.font.SysFont('arial', 74)
            self.restart_font = pygame.font.SysFont('arial', 30)

        self.setup_initial_state()

    def start_timer(self):
        self.time_elapsed_seconds = 0
        self.game_timer_active = True
    
    def game_over(self):
        if self.game_over_played == False:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(settings.GAME_OVER_PATH)
            pygame.mixer.music.set_volume(settings.MENU_MUSIC_VOLUME)
            pygame.mixer.music.play(-1)  # 播放一次遊戲結束音樂
            self.game_over_played = True
    
    def victory(self):
        if self.victory_music_played == False:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(settings.GAME_VICTORY_PATH)
            pygame.mixer.music.set_volume(0.6)
            pygame.mixer.music.play(-1)
            self.victory_music_played = True
    
    def setup_initial_state(self):
        # (此函式保持不變)
        self.all_sprites.empty()
        self.players_group.empty()
        self.bombs_group.empty()
        self.explosions_group.empty()
        self.items_group.empty()
        self.solid_obstacles_group.empty()

        self.time_elapsed_seconds = 0.0
        self.game_timer_active = False
        self.time_up_winner = None
        self.game_state = "PLAYING"

        self.player_name_input = ""
        self.input_box_active = False
        self.score_to_submit = 0
        self.score_submitted_message_timer = 0.0

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
                              is_ai=False, is_player1=True)
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
        if self.ai_archetype == "original": ai_controller_class = OriginalAIController
        elif self.ai_archetype == "conservative": ai_controller_class = ConservativeAIController
        elif self.ai_archetype == "aggressive": ai_controller_class = AggressiveAIController
        elif self.ai_archetype == "item_focused": ai_controller_class = ItemFocusedAIController
        else: ai_controller_class = OriginalAIController

        self.ai_controller_p2 = ai_controller_class(self.player2_ai, self)

        if hasattr(self.ai_controller_p2, 'reset_state') and callable(getattr(self.ai_controller_p2, 'reset_state')):
            self.ai_controller_p2.reset_state()

        self.player2_ai.ai_controller = self.ai_controller_p2
        if self.ai_controller_p2:
            self.ai_controller_p2.human_player_sprite = self.player1
        
        # 【新增】重置 running 和 restart_game 旗標，確保每次 Game 場景開始時都是乾淨的狀態
        self.running = True
        self.restart_game = False


    # 【修改】移除舊的 run 方法
    # def run(self):
    #     self.clock.tick(settings.FPS)
    #     self.time_elapsed_seconds = 0.0
    #     self.game_timer_active = True
    #     while self.running:
    #         self.dt = self.clock.tick(settings.FPS) / 1000.0
    #         self.events()
    #         self.update()
    #         self.draw()
    #     return self.restart_game

    # 【新增】run_one_frame 方法，由 main.py 的主迴圈呼叫
    def run_one_frame(self, events_from_main_loop):
        # 如果 Game 場景已經設定為不再運行 (例如，玩家按 ESC 或遊戲結束)
        if not self.running:
            # 根據 restart_game 旗標決定返回 Menu 還是 "QUIT" 指令
            from core.menu import Menu
            return Menu(self.screen) if self.restart_game else "QUIT"

        # 計算 dt (delta time)
        if self.dt == 0:
            self.clock.tick()
            self.dt = 0.01
        else:
            self.dt = self.clock.tick(settings.FPS) / 1000.0

        # 處理事件
        self._process_events_internal(events_from_main_loop) # 使用內部方法處理事件

        # 更新遊戲邏輯
        self._update_internal() # 使用內部方法更新邏輯

        # 繪製畫面
        self._draw_internal() # 使用內部方法繪製

        # 檢查場景是否應該結束
        if not self.running:
            from core.menu import Menu
            return Menu(self.screen) if self.restart_game else "QUIT"
        
        return self # 返回 self 表示繼續運行 Game 場景


    # 【修改】將原本的 events() 改名為 _process_events_internal() 並接收外部傳入的事件
    def _process_events_internal(self, events_from_main_loop):
        for event in events_from_main_loop:
            # pygame.QUIT 事件已由 main.py 處理，這裡可以不用再處理
            # 但為了安全，保留也可以

            if self.game_state == "ENTER_NAME":
                self.handle_enter_name_state_events(event)
            elif self.game_state == "SCORE_SUBMITTED":
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    self.restart_game = True
                    self.running = False # 標記 Game 場景結束
            else:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False # 標記 Game 場景結束
                        self.restart_game = False # 不是要重新開始，是真的退出
                    
                    if self.game_state == "PLAYING":
                        if event.key == pygame.K_f:
                            if self.player1 and self.player1.is_alive:
                                self.player1.place_bomb()
                    
                    elif self.game_state == "GAME_OVER":
                        if self.game_over_played == False:
                            pygame.mixer.music.stop()
                            pygame.mixer.music.load(settings.GAME_OVER_PATH)
                            pygame.mixer.music.set_volume(settings.MENU_MUSIC_VOLUME)
                            pygame.mixer.music.play(-1)  # 播放一次遊戲結束音樂
                            self.game_over_played = True
                        if event.key == pygame.K_r:
                            self.restart_game = True
                            self.running = False # 標記 Game 場景結束

    # 【修改】將原本的 update() 改名為 _update_internal()
    def _update_internal(self):
        # (update 函式的內容保持不變)
        if self.game_state == "PLAYING":
            p1_won_by_ko = False
            p1_won_by_time = False

            if self.game_timer_active:
                self.time_elapsed_seconds += self.dt
                if self.time_elapsed_seconds >= settings.GAME_DURATION_SECONDS:
                    self.game_timer_active = False
                    if self.player1.is_alive and self.player2_ai.is_alive:
                        if self.player1.lives > self.player2_ai.lives:
                            self.time_up_winner = "P1"; p1_won_by_time = True
                        elif self.player2_ai.lives > self.player1.lives:
                            self.time_up_winner = "AI"
                        else:
                            if self.player1.score > self.player2_ai.score:
                                self.time_up_winner = "P1"; p1_won_by_time = True
                            elif self.player2_ai.score > self.player1.score:
                                self.time_up_winner = "AI"
                            else: self.time_up_winner = "DRAW"
                    elif self.player1.is_alive:
                        self.time_up_winner = "P1"; p1_won_by_time = True
                    elif self.player2_ai.is_alive: self.time_up_winner = "AI"
                    else: self.time_up_winner = "DRAW"
                    self.game_state = "GAME_OVER"
                    self.game_over() # 播放遊戲結束音樂
                    
                    

            if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2:
                self.ai_controller_p2.update()
            self.all_sprites.update(self.dt, self.solid_obstacles_group)
            self.bombs_group.update(self.dt, self.solid_obstacles_group)

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
                        bling = pygame.mixer.Sound(settings.BLING_PATH)
                        bling.set_volume(0.3)
                        bling.play()

            if self.game_timer_active:
                human_player_alive = self.player1 and self.player1.is_alive
                ai_player_alive = self.player2_ai and self.player2_ai.is_alive
                if not human_player_alive or not ai_player_alive:
                    self.game_state = "GAME_OVER"
                    self.game_over()
                    self.game_timer_active = False
                    if human_player_alive: p1_won_by_ko = True

            if self.game_state == "GAME_OVER":
                is_p1_winner = (p1_won_by_ko or p1_won_by_time)
                if is_p1_winner and self.player1 and self.leaderboard_manager.is_score_high_enough(self.player1.score):
                    self.score_to_submit = self.player1.score
                    self.player_name_input = ""
                    self.input_box_active = True
                    self.game_state = "ENTER_NAME"
                    self.victory()

        elif self.game_state == "ENTER_NAME":
            pass

        elif self.game_state == "SCORE_SUBMITTED":
            self.score_submitted_message_timer += self.dt
            if self.score_submitted_message_timer >= self.score_submitted_message_duration:
                self.restart_game = True
                self.running = False # 標記 Game 場景結束

    # 【修改】將原本的 draw() 改名為 _draw_internal()
    def _draw_internal(self):
        if self.headless:
            return
        # (draw 函式的內容保持不變)
        # self.screen.fill(settings.WHITE)
        tile_img = self.brick_tile_image
        tile_width, tile_height = tile_img.get_size()

        screen_width, screen_height = self.screen.get_size()

        for y in range(tile_height, tile_height*10, tile_height):
            for x in range(tile_width, tile_width*14, tile_width):
                self.screen.blit(tile_img, (x, y))
        for y in range(tile_height, tile_height*15, tile_height):
            for x in range(tile_width*15, screen_width-tile_width, tile_width):
                self.screen.blit(self.beside_brick, (x, y))
        for y in range(tile_height*11, screen_height-tile_height, tile_height):
            for x in range(tile_width, tile_width*15, tile_width):
                self.screen.blit(self.text_brick, (x, y))
        for y in range(tile_height*15, screen_height-tile_height, tile_height):
            for x in range(tile_width*15, screen_width-tile_width, tile_width):
                self.screen.blit(self.text_brick, (x, y))

        for y in range(0, screen_height, tile_height):
            self.screen.blit(self.border_brick, (0, y))
            self.screen.blit(self.border_brick, (screen_width - tile_width, y))
            self.screen.blit(self.border_brick, (tile_width*14, y))
        for x in range(0, screen_width, tile_width):
            self.screen.blit(self.border_brick, (x, 0))
            self.screen.blit(self.border_brick, (x, tile_height*18))
        for x in range(tile_width*15, screen_width-tile_width, tile_width):
            self.screen.blit(self.border_brick, (x, tile_height*14))


        if self.game_state == "ENTER_NAME":
            self.draw_enter_name_screen()
        elif self.game_state == "SCORE_SUBMITTED":
            self.draw_score_submitted_screen()
        else: 
            self.all_sprites.draw(self.screen) 
            self.bombs_group.draw(self.screen)
            for bomb in self.bombs_group:
                bomb.draw_timer_bar(self.screen)
            if self.game_state == "PLAYING":
                if self.player2_ai and self.player2_ai.is_alive and self.ai_controller_p2:
                    if hasattr(self.ai_controller_p2, 'debug_draw_path'):
                        self.ai_controller_p2.debug_draw_path(self.screen)
                self.draw_hud()
            elif self.game_state == "GAME_OVER":
                self.draw_game_over_screen()

        # pygame.display.flip() # 由 main.py 的主迴圈呼叫

    # handle_enter_name_state_events, draw_pixel_digit, draw_hud, draw_game_over_screen,
    # draw_enter_name_screen, draw_score_submitted_screen 這些方法保持不變，
    # 因為它們是被 _process_events_internal 或 _draw_internal 內部呼叫的。
    def handle_enter_name_state_events(self, event):
        # (此函式保持不變)
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.name_input_rect.collidepoint(event.pos):
                self.input_box_active = not self.input_box_active
            else:
                self.input_box_active = False
        
        if event.type == pygame.KEYDOWN:
            if self.input_box_active:
                if event.key == pygame.K_RETURN:
                    player_name_to_save = self.player_name_input.strip()
                    if not player_name_to_save:
                        player_name_to_save = "Player" 
                    
                    self.leaderboard_manager.add_score(
                        player_name=player_name_to_save,
                        score=self.score_to_submit,
                        ai_defeated_type=self.ai_archetype
                    )
                    self.game_state = "SCORE_SUBMITTED"
                    self.score_submitted_message_timer = 0.0 
                    self.input_box_active = False 
                                        
                elif event.key == pygame.K_BACKSPACE:
                    self.player_name_input = self.player_name_input[:-1]
                else:
                    if len(self.player_name_input) < getattr(settings, "TEXT_INPUT_MAX_LENGTH", 10):
                        if event.unicode.isprintable() and event.key not in (pygame.K_TAB, pygame.K_ESCAPE, pygame.K_RETURN):
                             self.player_name_input += event.unicode
            elif event.key == pygame.K_ESCAPE: 
                self.game_state = "GAME_OVER" # 這裡其實會被 _process_events_internal 的 ESC 處理覆蓋
                self.restart_game = True 
                self.running = False

    def draw_pixel_digit(self, digit_char, top_left_x, top_left_y, block_size=settings.TILE_SIZE):
        # (此函式保持不變)
        pattern = DIGIT_MAP.get(digit_char)
        if not pattern:
            return

        for row in range(len(pattern)):
            for col in range(len(pattern[0])):
                if pattern[row][col]:
                    dest_x = top_left_x + col * block_size
                    dest_y = top_left_y + row * block_size
                    self.screen.blit(self.timer_brick, (dest_x, dest_y))

    def draw_hud(self):
        # (此函式保持不變)
        if not self.hud_font or not self.timer_font_normal or not self.timer_font_urgent:
            return

        time_left = max(0, settings.GAME_DURATION_SECONDS - self.time_elapsed_seconds)
        minutes = int(time_left) // 60
        seconds = int(time_left) % 60
        timer_text_1 = f"{minutes:02d}"
        timer_text_2 = f"{seconds:02d}"
        
        start_x = settings.TILE_SIZE*16
        start_y = settings.TILE_SIZE*2
        block_size = self.border_brick.get_width()
        spacing = settings.TILE_SIZE

        for i, char in enumerate(timer_text_1):
            self.draw_pixel_digit(
                char,
                top_left_x=start_x + i * (3 * block_size + spacing),
                top_left_y=start_y,
            )
        for i, char in enumerate(timer_text_2):
            self.draw_pixel_digit(
                char,
                top_left_x=start_x + i * (3 * block_size + spacing),
                top_left_y=start_y + 5 * block_size + spacing,
            )

        line_height = self.hud_font.get_linesize()*1.3
        start_x_p1 = 48
        start_x_ai_offset = getattr(settings, "HUD_AI_OFFSET_X", 280)
        num_max_hud_lines = 5
        bottom_padding = 10
        hud_start_y = settings.SCREEN_HEIGHT - (num_max_hud_lines * line_height) - bottom_padding # 重新命名避免與上面的 start_y 衝突

        p1_texts = []
        if self.player1:
            p1_texts.append(f"P1 Lives: {self.player1.lives}")
            p1_texts.append(f"P1 Bombs: {self.player1.max_bombs - self.player1.bombs_placed_count}/{self.player1.max_bombs}")
            p1_texts.append(f"P1 Range: {self.player1.bomb_range}")
            p1_texts.append(f"P1 Score: {self.player1.score}")
        for i, text in enumerate(p1_texts):
            draw_text_with_outline(self.screen, text, self.hud_font, (start_x_p1, hud_start_y + i * line_height))


        ai_texts = []
        if self.player2_ai:
            if self.player2_ai.is_alive: ai_texts.append(f"AI Lives: {self.player2_ai.lives}")
            else: ai_texts.append("AI Defeated")
            ai_texts.append(f"AI Bombs: {self.player2_ai.max_bombs - self.player2_ai.bombs_placed_count}/{self.player2_ai.max_bombs}")
            ai_texts.append(f"AI Range: {self.player2_ai.bomb_range}")
            ai_texts.append(f"AI Score: {self.player2_ai.score}")
            ai_state_text = []
            if self.ai_controller_p2 and self.ai_status_font:
                class_name = self.ai_controller_p2.__class__.__name__
                ai_name = class_name.replace("AIController", "")
                if not ai_name and class_name == "AIController": ai_name = "Standard"
                state = getattr(self.ai_controller_p2, 'current_state', 'N/A')
                ai_state_text.append(f"AI ({ai_name}):")
                ai_state_text.append(f"{state}")
        for i, text in enumerate(ai_texts):
            font_to_use = self.hud_font
            if text.startswith("AI (") and self.ai_status_font: font_to_use = self.ai_status_font
            draw_text_with_outline(self.screen, text, font_to_use, (start_x_p1 + start_x_ai_offset, hud_start_y + i * line_height))
        if ai_state_text:
            draw_text_with_outline(self.screen, ai_state_text[0], self.ai_status_font, (490, 500), outline_color=(230,230,230), of=1)
            draw_text_with_outline(self.screen, ai_state_text[1], self.ai_status_font, (490, 530), outline_color=(230,230,230), of=1)


    def draw_game_over_screen(self):
        # (此函式保持不變)
        overlay = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, 180))  # R, G, B, A (180 ≈ 70% 不透明)
        self.screen.blit(overlay, (0, 0))
        if not self.game_over_font or not self.restart_font:
            return

        msg = "GAME OVER"; color = settings.RED
        p1_alive = self.player1 and self.player1.is_alive
        ai_alive = self.player2_ai and self.player2_ai.is_alive

        if self.time_up_winner:
            if self.time_up_winner == "P1": msg = "TIME'S UP! P1 WINS!"; color = settings.GREEN
            elif self.time_up_winner == "AI": msg = "TIME'S UP! AI WINS!"; color = settings.RED
            else: msg = "TIME'S UP! DRAW!"; color = settings.GREY
        else:
            if not p1_alive and not ai_alive: msg = "DRAW!"; color = settings.GREY
            elif not p1_alive: msg = "GAME OVER - YOU LOST!"; color = settings.RED
            elif not ai_alive: msg = "VICTORY - AI DEFEATED!"; color = settings.GREEN
        
        game_over_text = self.game_over_font.render(msg, True, color)
        text_rect = game_over_text.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 - 50))
        self.screen.blit(game_over_text, text_rect)
        
        restart_text = self.restart_font.render("Press 'R' to return to Menu", True, settings.BLACK)
        restart_rect = restart_text.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 + 20))
        self.screen.blit(restart_text, restart_rect)

    def draw_enter_name_screen(self):
        # (此函式保持不變)
        if not self.text_input_font or not self.prompt_font or not self.hud_font:
            return

        self.screen.fill((180, 200, 255))

        prompt_text = "VICTORY! New High Score!"
        prompt_surf = self.prompt_font.render(prompt_text, True, getattr(settings, "TEXT_INPUT_PROMPT_COLOR", settings.BLACK))
        prompt_rect = prompt_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 3))
        self.screen.blit(prompt_surf, prompt_rect)
        
        enter_name_text = "Enter Your Name:"
        enter_name_surf = self.hud_font.render(enter_name_text, True, getattr(settings, "TEXT_INPUT_PROMPT_COLOR", settings.BLACK))
        enter_name_rect = enter_name_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, prompt_rect.bottom + 40))
        self.screen.blit(enter_name_surf, enter_name_rect)

        self.name_input_rect.width = 300
        self.name_input_rect.height = 50
        self.name_input_rect.center = (settings.SCREEN_WIDTH / 2, enter_name_rect.bottom + 40)
        
        box_color = getattr(settings, "TEXT_INPUT_BOX_COLOR_ACTIVE", (0,100,255)) if self.input_box_active else getattr(settings, "TEXT_INPUT_BOX_COLOR_INACTIVE", (100,100,100))
        pygame.draw.rect(self.screen, box_color, self.name_input_rect, 0, border_radius=5)
        pygame.draw.rect(self.screen, settings.BLACK, self.name_input_rect, 2, border_radius=5)

        if self.text_input_font:
            text_surf = self.text_input_font.render(self.player_name_input, True, getattr(settings, "TEXT_INPUT_TEXT_COLOR", settings.BLACK))
            text_rect = text_surf.get_rect(midleft=(self.name_input_rect.x + 15, self.name_input_rect.centery))
            self.screen.blit(text_surf, text_rect)

            if self.input_box_active and pygame.time.get_ticks() % 1000 < 500:
                cursor_x_pos = text_rect.right + 3 if self.player_name_input else self.name_input_rect.x + 15
                pygame.draw.line(self.screen, getattr(settings, "TEXT_INPUT_TEXT_COLOR", settings.BLACK),
                                (cursor_x_pos, self.name_input_rect.y + 10),
                                (cursor_x_pos, self.name_input_rect.bottom - 10), 2)

        submit_prompt_text = "Press ENTER to Submit, ESC to Skip"
        if self.hud_font:
            submit_surf = self.hud_font.render(submit_prompt_text, True, settings.GREY)
            submit_rect = submit_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, self.name_input_rect.bottom + 40))
            self.screen.blit(submit_surf, submit_rect)

    def draw_score_submitted_screen(self):
        # (此函式保持不變)
        if not self.message_font or not self.hud_font :
            return

        self.screen.fill((200, 255, 200))

        message_text = "Score Recorded on Leaderboard!"
        message_surf = self.message_font.render(message_text, True, settings.BLACK)
        message_rect = message_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 - 30))
        self.screen.blit(message_surf, message_rect)

        continue_prompt_text = "Press any key or click to continue..."
        continue_surf = self.hud_font.render(continue_prompt_text, True, settings.GREY)
        continue_rect = continue_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, message_rect.bottom + 40))
        self.screen.blit(continue_surf, continue_rect)