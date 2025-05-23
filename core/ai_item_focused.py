# oop-2025-proj-pycade/core/ai_item_focused.py

import pygame
import settings
import random
from collections import deque
from .ai_controller_base import AIControllerBase, ai_log, DIRECTIONS, TileNode

class ItemFocusedAIController(AIControllerBase):
    """
    An AI that focuses on finding and picking up items, with its aggression
    increasing as it becomes more powerful.
    This version introduces a dynamic aggression level.
    """
    def __init__(self, ai_player_sprite, game_instance):
        super().__init__(ai_player_sprite, game_instance)
        
        ai_log("ItemFocusedAIController (v5 - Dynamic Aggression) initialized.")
        
        self.evasion_urgency_seconds = getattr(settings, "AI_ITEM_FOCUSED_EVASION_SECONDS", 0.5)
        self.retreat_search_depth = getattr(settings, "AI_ITEM_FOCUSED_RETREAT_DEPTH", 7)
        self.min_retreat_options_for_obstacle_bombing = 1
        
        self.max_walls_to_consider_for_items = getattr(settings, "AI_ITEM_MAX_WALL_TARGETS", 4)
        self.wall_scan_radius_for_items = getattr(settings, "AI_ITEM_WALL_SCAN_RADIUS", 6)
        self.item_bombing_chance = getattr(settings, "AI_ITEM_BOMBING_CHANCE", 0.65)

        self.target_item_on_ground = None 
        self.potential_wall_to_bomb_for_item = None 
        
        self.item_type_priority = {
            settings.ITEM_TYPE_BOMB_RANGE: 1,
            settings.ITEM_TYPE_BOMB_CAPACITY: 2,
            settings.ITEM_TYPE_LIFE: 3,
            settings.ITEM_TYPE_SCORE: 10 
        }
        
        self.default_planning_state_on_stuck = "PLANNING_ITEM_TARGET"
        self.default_state_after_evasion = "PLANNING_ITEM_TARGET"
        
        self.last_failed_bombing_target_wall = None
        self.last_failed_bombing_spot = None
        self.last_failed_roam_target = None
        self.roam_target_seek_depth = 10
        self.idle_duration_ms = 1500

        # Aggression related properties
        self.cqc_engagement_distance = getattr(settings, "AI_AGGRESSIVE_CQC_ENGAGE_DISTANCE", 2)
        self.cqc_bomb_chance = getattr(settings, "AI_AGGRESSIVE_CQC_BOMB_CHANCE", 0.75)


        self.change_state("PLANNING_ITEM_TARGET")

    @property
    def aggression_level(self):
        """Calculates a value from 0.0 to 1.0+ representing the AI's power."""
        # Start with base values
        base_bombs = settings.INITIAL_BOMBS
        base_range = settings.INITIAL_BOMB_RANGE

        # Calculate how much power has been gained
        bomb_power = (self.ai_player.max_bombs - base_bombs) * 0.4 
        range_power = (self.ai_player.bomb_range - base_range) * 0.6
        
        # Combine and normalize
        level = bomb_power + range_power
        return min(1.0, level / 4.0) # Cap at 1.0 for now, adjust divisor as needed

    def reset_state(self):
        super().reset_state()
        self.target_item_on_ground = None
        self.potential_wall_to_bomb_for_item = None
        self.last_failed_bombing_target_wall = None
        self.last_failed_bombing_spot = None
        self.last_failed_roam_target = None
        self.change_state("PLANNING_ITEM_TARGET")
        ai_log(f"ItemFocusedAIController (v5) reset. Current state: {self.current_state}")

    # --- State Handling ---

    def handle_planning_item_target_state(self, ai_current_tile):
        ai_log(f"ITEM_FOCUSED: In PLANNING_ITEM_TARGET at {ai_current_tile}. Aggression: {self.aggression_level:.2f}")
        self.target_item_on_ground = None
        self.potential_wall_to_bomb_for_item = None
        self.astar_planned_path = [] 

        # 1. Look for items on the ground
        best_item_on_ground = self._find_best_item_on_ground(ai_current_tile)
        if best_item_on_ground:
            self.target_item_on_ground = best_item_on_ground['item']
            item_coords = best_item_on_ground['coords']
            ai_log(f"ITEM_FOCUSED: Found item {self.target_item_on_ground.type} at {item_coords}. Pathing...")
            
            path_to_item = self.bfs_find_direct_movement_path(ai_current_tile, item_coords, max_depth=25)
            if path_to_item and len(path_to_item) > 1:
                self.set_current_movement_sub_path(path_to_item)
                self.change_state("MOVING_TO_COLLECT_ITEM")
                return

            self.astar_planned_path = self.astar_find_path(ai_current_tile, item_coords)
            if self.astar_planned_path:
                self.astar_path_current_segment_index = 0
                self.change_state("EXECUTING_ASTAR_PATH_TO_TARGET") 
                return
            
            ai_log(f"ITEM_FOCUSED: Cannot find any path to item {self.target_item_on_ground.type}.")
            self.target_item_on_ground = None 

        # 2. Decide whether to hunt the player based on aggression
        human_pos = self._get_human_player_current_tile()
        attack_chance = 0.05 + (self.aggression_level * 0.7) # Base 5% chance, scales up to 75%
        if human_pos and random.random() < attack_chance:
            ai_log(f"ITEM_FOCUSED: Aggression check passed (chance: {attack_chance:.2f}). Engaging player.")
            # Transition to direct combat states
            dist_to_human = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1])
            if dist_to_human <= self.cqc_engagement_distance:
                self.change_state("CLOSE_QUARTERS_COMBAT")
            else:
                self.change_state("ENGAGING_PLAYER")
            return

        # 3. Find a wall to bomb for items
        current_wall_target = self._find_best_wall_to_bomb_for_items(ai_current_tile, exclude_wall_node=self.last_failed_bombing_target_wall)
        if current_wall_target:
            self.potential_wall_to_bomb_for_item = current_wall_target
            if random.random() < self.item_bombing_chance:
                ai_log(f"ITEM_FOCUSED: Identified wall {self.potential_wall_to_bomb_for_item} to bomb.")
                self.change_state("ASSESSING_OBSTACLE_FOR_ITEM")
                return
        
        # 4. Roam if no other action is taken
        potential_roam_targets = self._find_safe_roaming_spots(ai_current_tile, count=1, depth=self.roam_target_seek_depth, exclude_target=self.last_failed_roam_target)
        if potential_roam_targets:
            roam_target = potential_roam_targets[0]
            if roam_target != ai_current_tile:
                path_to_roam = self.bfs_find_direct_movement_path(ai_current_tile, roam_target)
                if path_to_roam and len(path_to_roam) > 1:
                    self.set_current_movement_sub_path(path_to_roam)
                    self.roaming_target_tile = roam_target
                    self.change_state("ROAMING") 
                    return
        
        ai_log("ITEM_FOCUSED: No clear targets. Idling.")
        self.change_state("IDLE")
    
    # ... (handle_moving_to_collect_item_state and other item/obstacle states remain the same) ...
    def handle_moving_to_collect_item_state(self, ai_current_tile):
        if not self.target_item_on_ground or not self.target_item_on_ground.alive():
            self.change_state("PLANNING_ITEM_TARGET"); return

        item_coords = (self.target_item_on_ground.rect.centerx // settings.TILE_SIZE,
                       self.target_item_on_ground.rect.centery // settings.TILE_SIZE)
        ai_log(f"ITEM_FOCUSED: Moving to collect item {self.target_item_on_ground.type} at {item_coords}. Current: {ai_current_tile}")

        if self.current_movement_sub_path: return

        if ai_current_tile == item_coords: 
            self.target_item_on_ground = None 
            self.change_state("PLANNING_ITEM_TARGET")
        else: 
            ai_log(f"ITEM_FOCUSED: Sub-path to item ended or failed. Re-planning to item (A*).")
            self.astar_planned_path = self.astar_find_path(ai_current_tile, item_coords)
            if self.astar_planned_path:
                self.astar_path_current_segment_index = 0
                self.change_state("EXECUTING_ASTAR_PATH_TO_TARGET")
            else: 
                self.target_item_on_ground = None
                self.change_state("PLANNING_ITEM_TARGET")

    def handle_executing_astar_path_to_target_state(self, ai_current_tile):
        # ... (same as previous version) ...
        current_target_description = "UNKNOWN TARGET"
        target_coords = None

        if self.target_item_on_ground and self.target_item_on_ground.alive():
            current_target_description = f"item {self.target_item_on_ground.type}"
            target_coords = (self.target_item_on_ground.rect.centerx // settings.TILE_SIZE,
                             self.target_item_on_ground.rect.centery // settings.TILE_SIZE)
        elif self.astar_planned_path : 
            last_node = self.astar_planned_path[-1]
            target_coords = (last_node.x, last_node.y)
            human_tile = self._get_human_player_current_tile()
            if human_tile and target_coords == human_tile: current_target_description = "player"
            else: current_target_description = f"coords {target_coords}"
        else: self.change_state("PLANNING_ITEM_TARGET"); return

        ai_log(f"ITEM_FOCUSED: Executing A* path to {current_target_description}. At {ai_current_tile}.")
        if self.ai_just_placed_bomb: return

        if not self.astar_planned_path or self.astar_path_current_segment_index >= len(self.astar_planned_path):
            self.change_state("PLANNING_ITEM_TARGET"); return

        if self.current_movement_sub_path: return

        target_node_in_astar = self.astar_planned_path[self.astar_path_current_segment_index]

        if ai_current_tile == (target_node_in_astar.x, target_node_in_astar.y):
            self.astar_path_current_segment_index += 1 
            if self.astar_path_current_segment_index >= len(self.astar_planned_path):
                self.change_state("PLANNING_ITEM_TARGET") 
            else: self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval 
            return

        if target_node_in_astar.is_empty_for_direct_movement():
            path_to_node = self.bfs_find_direct_movement_path(ai_current_tile, (target_node_in_astar.x, target_node_in_astar.y))
            if path_to_node and len(path_to_node) > 1: self.set_current_movement_sub_path(path_to_node)
            else: self.change_state("PLANNING_ITEM_TARGET")
            return
        
        elif target_node_in_astar.is_destructible_box():
            self.target_destructible_wall_node_in_astar = target_node_in_astar 
            bomb_spot, retreat_spot = self._find_optimal_bombing_spot_for_obstacle(target_node_in_astar, ai_current_tile, self.min_retreat_options_for_obstacle_bombing)
            if bomb_spot and retreat_spot:
                self.chosen_bombing_spot_coords = bomb_spot
                self.chosen_retreat_spot_coords = retreat_spot
                if ai_current_tile == bomb_spot: 
                    if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                        self.ai_player.place_bomb()
                        path_to_retreat_immediately = self.bfs_find_direct_movement_path(ai_current_tile, retreat_spot)
                        if path_to_retreat_immediately and len(path_to_retreat_immediately) > 1:
                            self.set_current_movement_sub_path(path_to_retreat_immediately)
                        self.change_state("TACTICAL_RETREAT_AND_WAIT")
                    else: self.change_state("PLANNING_ITEM_TARGET")
                else: 
                    path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, bomb_spot)
                    if path_to_bomb_spot and len(path_to_bomb_spot) > 1: 
                        self.set_current_movement_sub_path(path_to_bomb_spot)
                    else: self.change_state("PLANNING_ITEM_TARGET")
            else: self.change_state("PLANNING_ITEM_TARGET")
            return
        else: self.change_state("PLANNING_ITEM_TARGET")

    def handle_assessing_obstacle_for_item_state(self, ai_current_tile):
        ai_log(f"ITEM_FOCUSED: Assessing obstacle {self.potential_wall_to_bomb_for_item} at {ai_current_tile} for items.")
        if not self.potential_wall_to_bomb_for_item or \
           not self._get_node_at_coords(self.potential_wall_to_bomb_for_item.x, self.potential_wall_to_bomb_for_item.y).is_destructible_box():
            self.potential_wall_to_bomb_for_item = None
            self.change_state("PLANNING_ITEM_TARGET"); return

        bomb_spot, retreat_spot = self._find_optimal_bombing_spot_for_obstacle(self.potential_wall_to_bomb_for_item, ai_current_tile, self.min_retreat_options_for_obstacle_bombing)

        if bomb_spot and retreat_spot:
            self.chosen_bombing_spot_coords = bomb_spot
            self.chosen_retreat_spot_coords = retreat_spot
            
            path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_bombing_spot_coords)
            if path_to_bomb_spot and len(path_to_bomb_spot) > 0:
                self.set_current_movement_sub_path(path_to_bomb_spot)
                self.change_state("MOVING_TO_BOMB_OBSTACLE")
            else:
                ai_log("ITEM_FOCUSED: Cannot path to chosen bombing spot for wall. Re-planning.")
                self.last_failed_bombing_target_wall = self.potential_wall_to_bomb_for_item
                self.potential_wall_to_bomb_for_item = None
                self.change_state("PLANNING_ITEM_TARGET")
        else:
            ai_log("ITEM_FOCUSED: Cannot find safe way to bomb wall for items. Re-planning.")
            self.last_failed_bombing_target_wall = self.potential_wall_to_bomb_for_item
            self.potential_wall_to_bomb_for_item = None
            self.change_state("PLANNING_ITEM_TARGET")

    def handle_moving_to_bomb_obstacle_state(self, ai_current_tile):
        if not self.chosen_bombing_spot_coords:
            self.change_state("PLANNING_ITEM_TARGET"); return

        if self.current_movement_sub_path: return

        if ai_current_tile == self.chosen_bombing_spot_coords:
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                self.ai_player.place_bomb()
                path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=self.retreat_search_depth + 2)
                if path_to_retreat and len(path_to_retreat) > 1:
                    self.set_current_movement_sub_path(path_to_retreat)
                self.change_state("TACTICAL_RETREAT_AND_WAIT")
            else:
                self.change_state("PLANNING_ITEM_TARGET")
        else: 
            self.last_failed_bombing_spot = self.chosen_bombing_spot_coords 
            if self.potential_wall_to_bomb_for_item:
                 self.last_failed_bombing_target_wall = self.potential_wall_to_bomb_for_item
            elif self.target_destructible_wall_node_in_astar:
                 self.last_failed_bombing_target_wall = self.target_destructible_wall_node_in_astar
            self.change_state("PLANNING_ITEM_TARGET")

    def handle_tactical_retreat_and_wait_state(self, ai_current_tile):
        if not self.chosen_retreat_spot_coords:
            self.change_state("EVADING_DANGER"); return

        if self.ai_just_placed_bomb and self.current_movement_sub_path: return
        
        if ai_current_tile == self.chosen_retreat_spot_coords:
            if not self.is_bomb_still_active(self.last_bomb_placed_time):
                self.ai_just_placed_bomb = False
                self.change_state("PLANNING_ITEM_TARGET")
            return

        if not self.current_movement_sub_path:
            path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=self.retreat_search_depth + 2)
            if path_to_retreat and len(path_to_retreat) > 1:
                self.set_current_movement_sub_path(path_to_retreat)
            else: 
                self.change_state("EVADING_DANGER")
            
    def handle_evading_danger_state(self, ai_current_tile):
        super().handle_evading_danger_state(ai_current_tile)

    def handle_idle_state(self, ai_current_tile):
        if pygame.time.get_ticks() - self.state_start_time > self.idle_duration_ms:
            self.change_state("PLANNING_ITEM_TARGET")

    # --- New/Adapted Aggressive States ---

    def handle_engaging_player_state(self, ai_current_tile):
        human_pos = self._get_human_player_current_tile()
        if not human_pos:
            self.change_state("PLANNING_ITEM_TARGET"); return

        dist_to_human = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1])

        if dist_to_human <= self.cqc_engagement_distance:
            self.change_state("CLOSE_QUARTERS_COMBAT"); return
        
        if self.current_movement_sub_path: return

        if not self.ai_just_placed_bomb and self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
            if self._is_tile_in_hypothetical_blast(human_pos[0], human_pos[1], ai_current_tile[0], ai_current_tile[1], self.ai_player.bomb_range):
                can_bomb, retreat_spot = self.can_place_bomb_and_retreat(ai_current_tile)
                if can_bomb or random.random() < self.aggression_level * 0.5: # Risky bomb based on aggression
                    self.chosen_bombing_spot_coords = ai_current_tile
                    self.chosen_retreat_spot_coords = retreat_spot 
                    self.ai_player.place_bomb()
                    if retreat_spot:
                        path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, retreat_spot)
                        if path_to_retreat and len(path_to_retreat) > 1:
                            self.set_current_movement_sub_path(path_to_retreat)
                    self.change_state("TACTICAL_RETREAT_AND_WAIT")
                    return

        if not self.current_movement_sub_path:
            path_to_human = self.bfs_find_direct_movement_path(ai_current_tile, human_pos, max_depth=10)
            if path_to_human and len(path_to_human) > 1:
                self.set_current_movement_sub_path(path_to_human)
            else: 
                self.change_state("PLANNING_ITEM_TARGET")

    def handle_close_quarters_combat_state(self, ai_current_tile):
        human_pos = self._get_human_player_current_tile()
        if not human_pos:
            self.change_state("PLANNING_ITEM_TARGET"); return

        dist_to_human = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1])
        if dist_to_human > self.cqc_engagement_distance + 1: 
            self.change_state("ENGAGING_PLAYER"); return
            
        if self.current_movement_sub_path: return 

        if not self.ai_just_placed_bomb and self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
            # Higher chance to bomb in CQC based on aggression
            if self._is_tile_in_hypothetical_blast(human_pos[0], human_pos[1], ai_current_tile[0], ai_current_tile[1], self.ai_player.bomb_range):
                if random.random() < (self.cqc_bomb_chance * (0.5 + self.aggression_level)):
                    can_bomb, retreat_spot = self.can_place_bomb_and_retreat(ai_current_tile) 
                    self.chosen_bombing_spot_coords = ai_current_tile
                    self.chosen_retreat_spot_coords = retreat_spot
                    
                    self.ai_player.place_bomb()
                    
                    if self.chosen_retreat_spot_coords:
                        path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords)
                        if path_to_retreat and len(path_to_retreat) > 1:
                            self.set_current_movement_sub_path(path_to_retreat)
                    
                    self.change_state("TACTICAL_RETREAT_AND_WAIT")
                    return

        if not self.current_movement_sub_path:
            available_reposition_spots = []
            for dx, dy in DIRECTIONS.values():
                next_x, next_y = ai_current_tile[0] + dx, ai_current_tile[1] + dy
                if (next_x, next_y) == human_pos: continue 
                node = self._get_node_at_coords(next_x, next_y)
                if node and node.is_empty_for_direct_movement() and not self.is_tile_dangerous(next_x, next_y, 0.1):
                    available_reposition_spots.append((next_x, next_y))
            
            if available_reposition_spots:
                reposition_target = random.choice(available_reposition_spots)
                self.set_current_movement_sub_path([ai_current_tile, reposition_target])

    # --- Helper Functions ---
    # ... (all _find... and other helper methods remain the same as your provided version) ...
    def _find_best_item_on_ground(self, ai_current_tile):
        if not self.game.items_group: return None
        best_item_found = None
        highest_priority_value = float('inf') 
        shortest_path_len_to_item = float('inf')

        for item_sprite in self.game.items_group:
            if not item_sprite.alive(): continue 

            priority = self.item_type_priority.get(item_sprite.type, 99)
            item_coords = (item_sprite.rect.centerx // settings.TILE_SIZE, item_sprite.rect.centery // settings.TILE_SIZE)
            
            dist_to_item_manhattan = abs(ai_current_tile[0] - item_coords[0]) + abs(ai_current_tile[1] - item_coords[1])
            
            if priority < highest_priority_value or \
               (priority == highest_priority_value and dist_to_item_manhattan < shortest_path_len_to_item) :
                
                if dist_to_item_manhattan < shortest_path_len_to_item + 5 :
                    temp_path_bfs = self.bfs_find_direct_movement_path(ai_current_tile, item_coords, max_depth=15) 
                    if temp_path_bfs and len(temp_path_bfs)>1: 
                        current_path_len = len(temp_path_bfs) -1
                        if priority < highest_priority_value or (priority == highest_priority_value and current_path_len < shortest_path_len_to_item):
                            highest_priority_value = priority
                            shortest_path_len_to_item = current_path_len
                            best_item_found = {'item': item_sprite, 'coords': item_coords, 'dist_bfs': current_path_len}
                    elif priority < highest_priority_value and best_item_found is None: 
                         if dist_to_item_manhattan < shortest_path_len_to_item : 
                            highest_priority_value = priority
                            shortest_path_len_to_item = dist_to_item_manhattan 
                            best_item_found = {'item': item_sprite, 'coords': item_coords, 'dist_bfs': float('inf')} 
        if best_item_found:
            ai_log(f"ITEM_FOCUSED: Found best item on ground: {best_item_found['item'].type} (Prio: {highest_priority_value}, Est.PathLen: {best_item_found.get('dist_bfs', shortest_path_len_to_item)})")
        return best_item_found

    def _find_best_wall_to_bomb_for_items(self, ai_current_tile, exclude_wall_node=None):
        potential_walls = []
        for r in range(self.map_manager.tile_height):
            for c in range(self.map_manager.tile_width):
                node = self._get_node_at_coords(c, r)
                if node and node.is_destructible_box():
                    if exclude_wall_node and node.x == exclude_wall_node.x and node.y == exclude_wall_node.y:
                        continue 

                    dist_to_wall = abs(ai_current_tile[0] - c) + abs(ai_current_tile[1] - r)
                    if dist_to_wall == 0: continue
                    if dist_to_wall <= self.wall_scan_radius_for_items:
                        open_sides = 0
                        can_reach_bomb_spot = False
                        for dx_wall_offset, dy_wall_offset in DIRECTIONS.values():
                            bomb_spot_x = node.x + dx_wall_offset
                            bomb_spot_y = node.y + dy_wall_offset
                            bomb_spot_node_check = self._get_node_at_coords(bomb_spot_x, bomb_spot_y)
                            if bomb_spot_node_check and bomb_spot_node_check.is_empty_for_direct_movement():
                                if self.bfs_find_direct_movement_path(ai_current_tile, (bomb_spot_x, bomb_spot_y), max_depth=7):
                                    can_reach_bomb_spot = True
                                    for dx_check, dy_check in DIRECTIONS.values():
                                        adj_node = self._get_node_at_coords(node.x + dx_check, node.y + dy_check)
                                        if adj_node and adj_node.is_empty_for_direct_movement():
                                            open_sides +=1
                                    break
                        
                        if can_reach_bomb_spot and open_sides > 0: 
                             score = (open_sides * 5) - dist_to_wall 
                             potential_walls.append({'node': node, 'dist': dist_to_wall, 'open': open_sides, 'score': score})
        
        if not potential_walls: return None
        potential_walls.sort(key=lambda w: w['score'], reverse=True) 
        
        chosen_wall_node = potential_walls[0]['node']
        ai_log(f"ITEM_FOCUSED: Found {len(potential_walls)} potential walls. Chosen: {chosen_wall_node} (Score: {potential_walls[0]['score']})")
        return chosen_wall_node

    def _find_optimal_bombing_spot_for_obstacle(self, wall_node, ai_current_tile, min_retreat_options=1):
        candidate_placements = []
        for dx_wall_offset, dy_wall_offset in DIRECTIONS.values():
            bomb_spot_x = wall_node.x + dx_wall_offset
            bomb_spot_y = wall_node.y + dy_wall_offset
            bomb_spot_coords = (bomb_spot_x, bomb_spot_y)
            
            if self.last_failed_bombing_spot and \
               bomb_spot_coords == self.last_failed_bombing_spot and \
               self.potential_wall_to_bomb_for_item == self.last_failed_bombing_target_wall:
                continue

            bomb_spot_node = self._get_node_at_coords(bomb_spot_x, bomb_spot_y)
            if not (bomb_spot_node and bomb_spot_node.is_empty_for_direct_movement()):
                continue

            path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, bomb_spot_coords, max_depth=7) 
            if not path_to_bomb_spot : continue

            retreat_spots = self.find_safe_tiles_nearby_for_retreat(
                bomb_spot_coords, bomb_spot_coords, self.ai_player.bomb_range, 
                self.retreat_search_depth, min_retreat_options 
            )
            if retreat_spots:
                best_retreat_spot = retreat_spots[0] 
                if self.bfs_find_direct_movement_path(bomb_spot_coords, best_retreat_spot, self.retreat_search_depth):
                    candidate_placements.append({
                        'bomb_spot': bomb_spot_coords, 
                        'retreat_spot': best_retreat_spot,
                        'path_to_bomb_len': len(path_to_bomb_spot)
                    })
        
        if not candidate_placements: return None, None
        candidate_placements.sort(key=lambda p: p['path_to_bomb_len'])
        return candidate_placements[0]['bomb_spot'], candidate_placements[0]['retreat_spot']

    def _find_safe_roaming_spots(self, ai_current_tile, count=1, depth=3, exclude_target=None):
        q = deque([(ai_current_tile, 0)]) 
        visited = {ai_current_tile}
        potential_spots = []

        while q and len(potential_spots) < count * 10:
            (curr_x, curr_y), d = q.popleft()

            if d > 0 and d <= depth: 
                if (curr_x, curr_y) == exclude_target: continue

                if not self.is_tile_dangerous(curr_x, curr_y, future_seconds=self.evasion_urgency_seconds * 0.3):
                    openness = self._get_tile_openness(curr_x, curr_y, radius=1)
                    if openness >= 1 : 
                        if (curr_x, curr_y) != ai_current_tile:
                           potential_spots.append(((curr_x, curr_y), openness))
            
            if d < depth: 
                shuffled_directions = list(DIRECTIONS.values()); random.shuffle(shuffled_directions) 
                for dx, dy in shuffled_directions: 
                    next_x, next_y = curr_x + dx, curr_y + dy 
                    next_coords = (next_x, next_y) 
                    if next_coords not in visited: 
                        node = self._get_node_at_coords(next_x, next_y) 
                        if node and node.is_empty_for_direct_movement(): 
                             if not self.is_tile_dangerous(next_x, next_y, future_seconds=0.05):
                                visited.add(next_coords) 
                                q.append((next_coords, d + 1)) 
        
        if not potential_spots: return [] 
        potential_spots.sort(key=lambda s: s[1], reverse=True) 
        
        final_choices = [spot[0] for spot in potential_spots if spot[0] != ai_current_tile]
        
        return final_choices[:count]