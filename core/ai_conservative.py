# oop-2025-proj-pycade/core/ai_controller_conservative.py

import pygame
import settings
from collections import deque
import random
from .ai_controller_base import AIControllerBase, ai_log, DIRECTIONS # 確保從正確的基底類別匯入
class ConservativeAIController(AIControllerBase):
    """
    一個謹慎的 AI，主要行為是隨機安全漫遊，並伺機炸開障礙物以獲取道具。
    它會極力避免與玩家直接衝突，並優先確保自身安全。
    """
    def __init__(self, ai_player_sprite, game_instance):
        super().__init__(ai_player_sprite, game_instance)
        
        ai_log("ConservativeAIController (Roaming & Opportunistic) initialized.")
        # 這個版本的「保守」體現在：低攻擊性、高安全性要求、優先漫遊和獲取資源
        self.obstacle_bombing_chance = 0.2 # 每次決策時，考慮炸牆的基礎機率
        self.evasion_urgency_seconds = 0.8
        self.min_retreat_options_for_obstacle = 1 # 炸牆時至少需要的撤退點
        self.retreat_search_depth = 7
        
        self.roaming_target_tile = None # 當前漫遊目標點
        self.target_obstacle_to_bomb = None # 想要炸的牆

        self.change_state("ROAMING") # 初始狀態為漫遊

    def reset_state(self):
        super().reset_state()
        self.roaming_target_tile = None
        self.target_obstacle_to_bomb = None
        self.change_state("ROAMING")
        ai_log(f"ConservativeAIController (Roaming) reset. Current state: {self.current_state}")

    # --- 狀態處理邏輯 ---

    def handle_planning_path_state(self, ai_current_tile):
        """
        決策中樞：判斷是繼續漫遊、評估炸牆，還是有其他緊急事項。
        這個版本主要由 ROAMING 狀態驅動，PLANNING_PATH 作為一個備用或重新評估的入口。
        """
        ai_log(f"CONSERVATIVE (Roaming): In PLANNING_PATH at {ai_current_tile}. Re-evaluating...")
        # 預設行為是回到漫遊狀態
        self.change_state("ROAMING")

    def handle_roaming_state(self, ai_current_tile):
        """主要狀態：安全地隨機漫遊，並尋找炸牆機會。"""
        ai_log(f"CONSERVATIVE (Roaming): In ROAMING at {ai_current_tile}.")

        # 1. 檢查是否有正在執行的移動路徑
        if self.current_movement_sub_path:
            # 如果有路徑，基底類別的 update() 會處理移動，這裡不用做什麼
            # 等待路徑執行完畢，完成後 self.current_movement_sub_path 會變空
            return

        # 2. 如果漫遊路徑已走完，或沒有漫遊目標，則尋找下一個動作
        self.roaming_target_tile = None # 清除舊目標

        # 2a. 評估是否炸附近的牆
        # (此處的 target_obstacle_to_bomb 應該是一個 TileNode 物件)
        self.target_obstacle_to_bomb = self._find_nearby_worthwhile_obstacle(ai_current_tile)
        if self.target_obstacle_to_bomb and random.random() < self.obstacle_bombing_chance:
            ai_log(f"CONSERVATIVE (Roaming): Found obstacle {self.target_obstacle_to_bomb} to consider bombing.")
            self.change_state("ASSESSING_OBSTACLE")
            return

        # 2b. 如果不炸牆，則尋找新的漫遊目標點
        potential_roam_targets = self._find_safe_roaming_spots(ai_current_tile, count=5, depth=3)
        if potential_roam_targets:
            self.roaming_target_tile = random.choice(potential_roam_targets)
            path_to_roam_target = self.bfs_find_direct_movement_path(ai_current_tile, self.roaming_target_tile)
            
            if path_to_roam_target and len(path_to_roam_target) > 1:
                ai_log(f"CONSERVATIVE (Roaming): New roam target {self.roaming_target_tile}. Path: {path_to_roam_target}")
                self.set_current_movement_sub_path(path_to_roam_target)
                # 不需要切換狀態，繼續在 ROAMING 狀態下執行這個短路徑
            else:
                ai_log("CONSERVATIVE (Roaming): Could not find path to roam target. Staying idle briefly.")
                self.roaming_target_tile = None # 清除無效目標
                self.change_state("IDLE") # 短暫閒置
        else:
            ai_log("CONSERVATIVE (Roaming): No safe roaming spots found. Staying idle briefly.")
            self.change_state("IDLE")

    def handle_assessing_obstacle_state(self, ai_current_tile):
        """評估是否真的要炸目標牆壁。"""
        ai_log(f"CONSERVATIVE (Roaming): Assessing obstacle {self.target_obstacle_to_bomb} at {ai_current_tile}.")
        if not self.target_obstacle_to_bomb:
            self.change_state("ROAMING"); return

        bomb_spot, retreat_spot = self._find_optimal_bombing_spot_for_obstacle(self.target_obstacle_to_bomb, ai_current_tile)

        if bomb_spot and retreat_spot:
            ai_log(f"CONSERVATIVE (Roaming): Plan to bomb obstacle: Bomb at {bomb_spot}, retreat to {retreat_spot}.")
            self.chosen_bombing_spot_coords = bomb_spot
            self.chosen_retreat_spot_coords = retreat_spot
            self.change_state("MOVING_TO_BOMB_OBSTACLE")
        else:
            ai_log("CONSERVATIVE (Roaming): Cannot find safe way to bomb obstacle. Returning to roaming.")
            self.target_obstacle_to_bomb = None
            self.change_state("ROAMING")
            
    def handle_moving_to_bomb_obstacle_state(self, ai_current_tile):
        """移動到準備炸牆的位置。"""
        ai_log(f"CONSERVATIVE (Roaming): Moving to bomb spot {self.chosen_bombing_spot_coords}. At {ai_current_tile}.")
        if self.current_movement_sub_path: return # 正在移動

        # 已到達放置炸彈的地點
        if ai_current_tile == self.chosen_bombing_spot_coords:
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                ai_log("CONSERVATIVE (Roaming): At bombing spot. Placing bomb for obstacle.")
                self.ai_player.place_bomb() # Player 物件會處理 ai_just_placed_bomb
                # ai_just_placed_bomb 和 last_bomb_placed_time 會由 Player.place_bomb() 中的回呼設定
                # 或者，如果 Player.place_bomb() 沒有設定這些，我們需要在這裡手動設定：
                # self.ai_just_placed_bomb = True
                # self.last_bomb_placed_time = pygame.time.get_ticks()

                path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords)
                if path_to_retreat and len(path_to_retreat) > 1:
                    self.set_current_movement_sub_path(path_to_retreat)
                self.change_state("TACTICAL_RETREAT_AND_WAIT")
            else:
                ai_log("CONSERVATIVE (Roaming): At bombing spot, but no bombs available. Returning to roaming.")
                self.change_state("ROAMING")
        else: # 如果路徑走完了但沒到目標點（例如路徑被阻擋），重新規劃
            ai_log("CONSERVATIVE (Roaming): Path to bombing spot failed or ended prematurely. Re-assessing.")
            self.change_state("ROAMING")


    def handle_tactical_retreat_and_wait_state(self, ai_current_tile):
        """放置炸彈後的撤退與等待。"""
        ai_log(f"CONSERVATIVE (Roaming): Retreating/Waiting. At {ai_current_tile}. Target: {self.chosen_retreat_spot_coords}.")
        if self.current_movement_sub_path: return
        
        if ai_current_tile == self.chosen_retreat_spot_coords:
            if not self.is_bomb_still_active(self.last_bomb_placed_time):
                self.ai_just_placed_bomb = False # 確保清除
                self.target_obstacle_to_bomb = None # 清除炸過的目標
                self.change_state("ROAMING") # 回到漫遊
            return

        # 如果未在撤退點且無路徑，嘗試重新規劃到撤退點
        if self.chosen_retreat_spot_coords:
            path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords)
            if path_to_retreat and len(path_to_retreat) > 1:
                self.set_current_movement_sub_path(path_to_retreat)
            else: # 無法到達預期撤退點，緊急躲避
                ai_log("CONSERVATIVE (Roaming): CRITICAL - Cannot reach chosen retreat spot. Evading.")
                self.change_state("EVADING_DANGER")
        else: # 沒有設定撤退點，不應該發生
            ai_log("CONSERVATIVE (Roaming): ERROR - No retreat spot set in TACTICAL_RETREAT. Evading.")
            self.change_state("EVADING_DANGER")
            
    def handle_evading_danger_state(self, ai_current_tile):
        """使用更敏感的參數進行逃跑。"""
        ai_log(f"CONSERVATIVE (Roaming): EVADING DANGER at {ai_current_tile} with high urgency.")
        
        if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], self.evasion_urgency_seconds):
            ai_log("CONSERVATIVE (Roaming): Danger evaded. Returning to roaming.")
            self.change_state("ROAMING") # 逃離危險後，回到漫遊
            return

        target_is_dangerous = False
        if self.current_movement_sub_path:
            if self.is_tile_dangerous(self.current_movement_sub_path[-1][0], self.current_movement_sub_path[-1][1], 0.2):
                target_is_dangerous = True

        if not self.current_movement_sub_path or target_is_dangerous:
            safe_spots = self.find_safe_tiles_nearby_for_retreat(ai_current_tile, ai_current_tile, 0, self.retreat_search_depth)
            if safe_spots:
                # 尋找一個可達的安全點
                for spot in safe_spots:
                    path = self.bfs_find_direct_movement_path(ai_current_tile, spot)
                    if path and len(path) > 1:
                        self.set_current_movement_sub_path(path)
                        return
            ai_log("CONSERVATIVE (Roaming): CRITICAL - No evasion path found!")
            # 如果找不到路，AI 會卡在這裡，直到stuck detection觸發或情況改變

    def handle_idle_state(self, ai_current_tile):
        """短暫閒置，然後重新進入漫遊規劃。"""
        ai_log(f"CONSERVATIVE (Roaming): Briefly idling at {ai_current_tile}.")
        # 停留一小段時間後會自動因為決策計時器而重新進入 ROAMING (透過 PLANNING_PATH 中轉)
        # 為了確保它不會卡在 IDLE太久，可以強制一個短暫的延遲後切換
        if pygame.time.get_ticks() - self.state_start_time > 1000: # 閒置超過1秒
            self.change_state("ROAMING")


    # --- 特定輔助函式 ---
    def _find_nearby_worthwhile_obstacle(self, ai_current_tile, search_radius=3):
        """尋找附近是否有值得炸的可破壞牆壁。"""
        for r_offset in range(-search_radius, search_radius + 1):
            for c_offset in range(-search_radius, search_radius + 1):
                if abs(r_offset) + abs(c_offset) > search_radius : continue # 曼哈頓距離
                if r_offset == 0 and c_offset == 0: continue

                check_x, check_y = ai_current_tile[0] + c_offset, ai_current_tile[1] + r_offset
                node = self._get_node_at_coords(check_x, check_y)
                if node and node.is_destructible_box():
                    # 簡單起見，第一個找到的就認為值得 (未來可以加入更複雜的價值判斷)
                    return node
        return None

    def _find_optimal_bombing_spot_for_obstacle(self, wall_node, ai_current_tile):
        """為炸特定牆壁尋找最佳放置點和撤退點。"""
        # (這部分邏輯與之前的 _find_optimal_bombing_spot_conservative 類似，但目標明確是牆)
        for dx_wall_offset, dy_wall_offset in DIRECTIONS.values():
            bomb_spot_x = wall_node.x + dx_wall_offset
            bomb_spot_y = wall_node.y + dy_wall_offset
            bomb_spot_coords = (bomb_spot_x, bomb_spot_y)
            
            bomb_spot_node = self._get_node_at_coords(bomb_spot_x, bomb_spot_y)
            if not (bomb_spot_node and bomb_spot_node.is_empty_for_direct_movement()):
                continue # 放置點必須是空格

            # 確保能從當前位置走到放置點
            path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, bomb_spot_coords, max_depth=5)
            if not (path_to_bomb_spot and len(path_to_bomb_spot) > 0): # 即使是原地放，長度也是1
                continue

            # 檢查從該放置點是否有足夠安全的撤退路線
            retreat_spots = self.find_safe_tiles_nearby_for_retreat(bomb_spot_coords, bomb_spot_coords, self.ai_player.bomb_range, self.retreat_search_depth)
            if len(retreat_spots) >= self.min_retreat_options_for_obstacle:
                best_retreat_spot = retreat_spots[0] # 通常 find_safe_tiles... 會排序
                # 確保撤退點可達
                if self.bfs_find_direct_movement_path(bomb_spot_coords, best_retreat_spot, max_depth=self.retreat_search_depth):
                    return bomb_spot_coords, best_retreat_spot
        return None, None

    def _find_safe_roaming_spots(self, ai_current_tile, count=1, depth=3):
        """尋找附近幾個隨機、安全、可達的空格子作為漫遊目標。"""
        q = deque([(ai_current_tile, [ai_current_tile], 0)])
        visited = {ai_current_tile}
        potential_spots = []

        while q and len(potential_spots) < count * 5: # 找多一點候選
            (curr_x, curr_y), path, d = q.popleft()

            if d > 0 and d <= depth : # 不選擇起始點，且在深度範圍內
                if not self.is_tile_dangerous(curr_x, curr_y, future_seconds=self.evasion_urgency_seconds):
                    potential_spots.append((curr_x, curr_y))
            
            if d < depth:
                shuffled_directions = list(DIRECTIONS.values()); random.shuffle(shuffled_directions)
                for dx, dy in shuffled_directions:
                    next_x, next_y = curr_x + dx, curr_y + dy
                    next_coords = (next_x, next_y)
                    if next_coords not in visited:
                        node = self._get_node_at_coords(next_x, next_y)
                        if node and node.is_empty_for_direct_movement():
                             if not self.is_tile_dangerous(next_x, next_y, future_seconds=0.2): # 短期檢查路徑上的安全
                                visited.add(next_coords)
                                q.append((next_coords, path + [next_coords], d + 1))
        
        if not potential_spots: return []
        return random.sample(potential_spots, min(len(potential_spots), count))
    
    # In ai_controller_base.py (AIControllerBase class)

    def debug_draw_path(self, surface):
        """
        在螢幕上繪製 AI 的詳細除錯資訊，包括路徑、目標和狀態。
        此版本移除了在 AI 頭上顯示狀態文字的功能。
        """
        if not self.ai_player or not self.ai_player.is_alive:
            return
        
        ai_current_tile_coords = self._get_ai_current_tile()
        if not ai_current_tile_coords:
            return

        try:
            tile_size = settings.TILE_SIZE
            half_tile = tile_size // 2
            # font_size = tile_size // 2 # 移除了文字相關的字型大小設定
            
            # debug_font = None # 移除了字型載入
            # try:
            #     debug_font = pygame.font.Font(None, font_size)
            # except:
            #     debug_font = pygame.font.SysFont("arial", font_size - 2)

            # --- 顏色定義 ---
            COLOR_AI_POS = (0, 0, 255, 100)  # AI 當前位置 (藍色半透明)
            COLOR_ASTAR_PATH = (0, 128, 255, 180) # A* 長期路徑 (淺藍色)
            COLOR_SUB_PATH = (0, 255, 0, 220)     # 當前 BFS 短路徑 (綠色)
            COLOR_NEXT_STEP = (255, 255, 0, 255)  # BFS 下一步 (黃色)
            COLOR_BOMBING_SPOT = (255, 0, 0, 200) # 轟炸目標點 (紅色)
            COLOR_RETREAT_SPOT = (0, 200, 0, 200) # 撤退目標點 (深綠色)
            COLOR_TARGET_OBSTACLE = (255, 165, 0, 180) # 目標牆壁 (橙色)
            COLOR_DANGEROUS_TILE = (200, 0, 0, 70) # 感知到的危險格子 (深紅色半透明)
            # COLOR_TEXT = settings.BLACK # 移除了文字顏色
            # COLOR_AI_STATE_BG = (200, 200, 200, 180) # 移除了文字背景色

            # 1. 標記 AI 當前位置
            ai_rect_surface = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            ai_rect_surface.fill(COLOR_AI_POS)
            surface.blit(ai_rect_surface, (ai_current_tile_coords[0] * tile_size, ai_current_tile_coords[1] * tile_size))
            pygame.draw.rect(surface, (0,0,200), (ai_current_tile_coords[0] * tile_size, ai_current_tile_coords[1] * tile_size, tile_size, tile_size), 1)


            # 2. 繪製 A* 總體規劃路徑 (如果存在)
            if self.astar_planned_path and self.astar_path_current_segment_index < len(self.astar_planned_path):
                astar_points = [(ai_current_tile_coords[0] * tile_size + half_tile, ai_current_tile_coords[1] * tile_size + half_tile)]
                for i in range(self.astar_path_current_segment_index, len(self.astar_planned_path)):
                    node = self.astar_planned_path[i]
                    astar_points.append((node.x * tile_size + half_tile, node.y * tile_size + half_tile))
                
                if len(astar_points) > 1:
                    pygame.draw.lines(surface, COLOR_ASTAR_PATH, False, astar_points, 2)
                
                final_astar_target = self.astar_planned_path[-1]
                pygame.draw.circle(surface, COLOR_ASTAR_PATH, 
                                   (final_astar_target.x * tile_size + half_tile, final_astar_target.y * tile_size + half_tile), 
                                   tile_size // 4, 2)
                pygame.draw.line(surface, COLOR_ASTAR_PATH, 
                                 (final_astar_target.x * tile_size + half_tile - 5, final_astar_target.y * tile_size + half_tile - 5),
                                 (final_astar_target.x * tile_size + half_tile + 5, final_astar_target.y * tile_size + half_tile + 5), 2)
                pygame.draw.line(surface, COLOR_ASTAR_PATH,
                                 (final_astar_target.x * tile_size + half_tile - 5, final_astar_target.y * tile_size + half_tile + 5),
                                 (final_astar_target.x * tile_size + half_tile + 5, final_astar_target.y * tile_size + half_tile - 5), 2)


            # 3. 繪製當前移動子路徑 (BFS Path)
            if self.current_movement_sub_path and len(self.current_movement_sub_path) > self.current_movement_sub_path_index:
                sub_path_points = []
                sub_path_points.append((ai_current_tile_coords[0] * tile_size + half_tile, ai_current_tile_coords[1] * tile_size + half_tile))
                for i in range(self.current_movement_sub_path_index +1, len(self.current_movement_sub_path)):
                    tile_coords = self.current_movement_sub_path[i]
                    sub_path_points.append((tile_coords[0] * tile_size + half_tile, tile_coords[1] * tile_size + half_tile))

                if len(sub_path_points) > 1:
                    pygame.draw.lines(surface, COLOR_SUB_PATH, False, sub_path_points, 3)

                    # 4. 標記下一個移動目標點 (脈衝效果)
                    # 確保不會因為 current_movement_sub_path_index 越界而報錯
                    if self.current_movement_sub_path_index + 1 < len(self.current_movement_sub_path):
                        next_step_coords = self.current_movement_sub_path[self.current_movement_sub_path_index + 1]
                        next_px = next_step_coords[0] * tile_size + half_tile
                        next_py = next_step_coords[1] * tile_size + half_tile
                        
                        pulse_progress = (pygame.time.get_ticks() % 1000) / 1000.0
                        current_radius = int(half_tile * 0.3 + (half_tile * 0.2 * abs(0.5 - pulse_progress) * 2))
                        current_alpha = int(150 + 105 * abs(0.5 - pulse_progress) * 2)
                        
                        pulse_surface = pygame.Surface((current_radius * 2, current_radius * 2), pygame.SRCALPHA)
                        pygame.draw.circle(pulse_surface, (*COLOR_NEXT_STEP[:3], current_alpha), (current_radius, current_radius), current_radius)
                        surface.blit(pulse_surface, (next_px - current_radius, next_py - current_radius))


            # 5. 標記特殊目標點
            if hasattr(self, 'chosen_bombing_spot_coords') and self.chosen_bombing_spot_coords:
                bx, by = self.chosen_bombing_spot_coords
                bomb_spot_center_px = bx * tile_size + half_tile
                bomb_spot_center_py = by * tile_size + half_tile
                pygame.draw.circle(surface, COLOR_BOMBING_SPOT, (bomb_spot_center_px, bomb_spot_center_py), half_tile // 2, 0)
                pygame.draw.circle(surface, settings.BLACK, (bomb_spot_center_px, bomb_spot_center_py), half_tile // 2, 1)
                pygame.draw.line(surface, settings.BLACK, 
                                 (bomb_spot_center_px, bomb_spot_center_py - half_tile//2 - 2), 
                                 (bomb_spot_center_px, bomb_spot_center_py - half_tile//2 + 3), 2)

            if hasattr(self, 'chosen_retreat_spot_coords') and self.chosen_retreat_spot_coords and \
               (self.current_state == "TACTICAL_RETREAT_AND_WAIT" or self.current_state == "EVADING_DANGER" or self.ai_just_placed_bomb):
                rx, ry = self.chosen_retreat_spot_coords
                pygame.draw.rect(surface, COLOR_RETREAT_SPOT, (rx * tile_size + 4, ry * tile_size + 4, tile_size - 8, tile_size - 8), 0, border_radius=3)
                pygame.draw.rect(surface, settings.BLACK, (rx * tile_size + 4, ry * tile_size + 4, tile_size - 8, tile_size - 8), 1, border_radius=3)

            target_obstacle = getattr(self, 'target_obstacle_to_bomb', None) or \
                              getattr(self, 'target_destructible_wall_node_in_astar', None)
            if target_obstacle:
                ox, oy = target_obstacle.x, target_obstacle.y
                obstacle_rect_surface = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                obstacle_rect_surface.fill((*COLOR_TARGET_OBSTACLE[:3], 100))
                surface.blit(obstacle_rect_surface, (ox * tile_size, oy * tile_size))
                pygame.draw.rect(surface, COLOR_TARGET_OBSTACLE, (ox * tile_size, oy * tile_size, tile_size, tile_size), 2)


            # 6. 標記 AI 感知到的危險格子
            if self.current_state == "EVADING_DANGER" or (pygame.time.get_ticks() // 500) % 2 == 0:
                for r_offset in range(-3, 4):
                    for c_offset in range(-3, 4):
                        check_x, check_y = ai_current_tile_coords[0] + c_offset, ai_current_tile_coords[1] + r_offset
                        if 0 <= check_x < self.map_manager.tile_width and 0 <= check_y < self.map_manager.tile_height:
                            if self.is_tile_dangerous(check_x, check_y, future_seconds=self.evasion_urgency_seconds if hasattr(self, 'evasion_urgency_seconds') else 0.5):
                                danger_tile_surface = pygame.Surface((tile_size,tile_size), pygame.SRCALPHA)
                                danger_tile_surface.fill(COLOR_DANGEROUS_TILE)
                                surface.blit(danger_tile_surface, (check_x*tile_size, check_y*tile_size))
            
            # 7. 在 AI 頭上顯示當前狀態 (這一段被移除了)
            # if debug_font:
            #     state_text = f"{self.current_state}"
            #     text_surface = debug_font.render(state_text, True, COLOR_TEXT)
            #     text_rect = text_surface.get_rect(center=(ai_current_tile_coords[0] * tile_size + half_tile, 
            #                                               ai_current_tile_coords[1] * tile_size - font_size // 2))
                
            #     bg_rect = text_rect.inflate(6, 4)
            #     bg_surface = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
            #     bg_surface.fill(COLOR_AI_STATE_BG)
            #     surface.blit(bg_surface, bg_rect.topleft)
            #     surface.blit(text_surface, text_rect)

        except AttributeError as e:
            if 'TILE_SIZE' in str(e) or 'game' in str(e) or 'map_manager' in str(e):
                pass 
            else:
                ai_log(f"Debug Draw AttributeError: {e}")
        except Exception as e:
            ai_log(f"Error during AI debug_draw_path: {e}")