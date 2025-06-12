# Pycade Bomber - Class Diagram  
  
This document provides a comprehensive class diagram for the Pycade Bomber game system, showing the relationships between all major components.  
  
## Overview  
  
Pycade Bomber is a Pygame-based Bomberman recreation featuring multiple AI personalities, a leaderboard system, and comprehensive game mechanics. The architecture follows object-oriented design principles with clear separation of concerns.  
  
## Class Diagram  
  
```mermaid  
classDiagram  
    %% Core Application Classes  
    class Game {  
        +screen: Surface  
        +clock: Clock  
        +running: bool  
        +restart_game: bool  
        +game_state: str  
        +dt: float  
        +time_elapsed_seconds: float  
        +player1: Player  
        +player2_ai: Player  
        +ai_controller_p2: AIControllerBase  
        +map_manager: MapManager  
        +leaderboard_manager: LeaderboardManager  
        +all_sprites: Group  
        +players_group: Group  
        +bombs_group: Group  
        +explosions_group: Group  
        +items_group: Group  
        +solid_obstacles_group: Group  
        +run_one_frame(events): Scene  
        +setup_initial_state()  
        +_process_events_internal(events)  
        +_update_internal()  
        +_draw_internal()  
    }  
  
    class Menu {  
        +screen: Surface  
        +buttons: list  
        +leaderboard_manager: LeaderboardManager  
        +selected_ai_archetype: str  
        +run_one_frame(events): Scene  
        +draw_leaderboard()  
        +handle_button_click(pos)  
    }  
  
    class ThankYouScene {  
        +screen: Surface  
        +run_one_frame(events): Scene  
    }  
  
    %% Game Object Hierarchy  
    class GameObject {  
        +original_image: Surface  
        +image: Surface  
        +rect: Rect  
        +__init__(x, y, width, height, color, image_path)  
        +update(*args, **kwargs)  
    }  
  
    class Player {  
        +game: Game  
        +tile_x: int  
        +tile_y: int  
        +lives: int  
        +score: int  
        +max_bombs: int  
        +bomb_range: int  
        +bombs_placed_count: int  
        +is_alive: bool  
        +is_ai: bool  
        +move(direction)  
        +place_bomb()  
        +take_damage()  
        +update(dt, solid_obstacles)  
    }  
  
    class Bomb {  
        +placed_by_player: Player  
        +game: Game  
        +timer: int  
        +exploded: bool  
        +current_tile_x: int  
        +current_tile_y: int  
        +is_solidified: bool  
        +explode()  
        +update(dt, *args)  
    }  
  
    class Item {  
        +type: str  
        +score_value: int  
        +apply_effect(player)  
    }  
  
    class ScoreItem {  
        +score_value: int  
        +apply_effect(player)  
    }  
  
    class LifeItem {  
        +apply_effect(player)  
    }  
  
    class BombCapacityItem {  
        +apply_effect(player)  
    }  
  
    class BombRangeItem {  
        +apply_effect(player)  
    }  
  
    class Wall {  
        +destructible: bool  
        +take_damage()  
    }  
  
    class Explosion {  
        +damage: int  
        +duration: int  
        +update(dt)  
    }  
  
    %% AI System  
    class AIControllerBase {  
        +ai_player: Player  
        +game: Game  
        +map_manager: MapManager  
        +current_state: str  
        +astar_planned_path: list  
        +current_movement_sub_path: list  
        +last_known_tile: tuple  
        +update()  
        +reset_state()  
        +astar_find_path(start, target): list  
        +is_safe_tile(x, y): bool  
        +find_nearest_item(): tuple  
        +evaluate_bomb_placement(): bool  
    }  
  
    class AIController {  
        +update()  
    }  
  
    class ConservativeAIController {  
        +safety_threshold: float  
        +update()  
    }  
  
    class AggressiveAIController {  
        +attack_range: int  
        +update()  
    }  
  
    class ItemFocusedAIController {  
        +item_priority_weight: float  
        +update()  
    }  
  
    %% World Management  
    class MapManager {  
        +map_data: list  
        +tile_width: int  
        +tile_height: int  
        +destructible_walls_group: Group  
        +get_randomized_map_layout(): list  
        +load_map_from_data(map_data)  
        +is_solid_wall_at(x, y): bool  
        +is_destructible_wall_at(x, y): bool  
        +destroy_wall_at(x, y)  
    }  
  
    %% Data Management  
    class LeaderboardManager {  
        +leaderboard_file_path: str  
        +load_leaderboard(): list  
        +save_leaderboard(data)  
        +add_score(player_name, score, ai_type)  
        +is_high_score(score): bool  
    }  
  
    %% Relationships  
    GameObject <|-- Player  
    GameObject <|-- Bomb  
    GameObject <|-- Item  
    GameObject <|-- Wall  
    GameObject <|-- Explosion  
  
    Item <|-- ScoreItem  
    Item <|-- LifeItem  
    Item <|-- BombCapacityItem  
    Item <|-- BombRangeItem  
  
    AIControllerBase <|-- AIController  
    AIControllerBase <|-- ConservativeAIController  
    AIControllerBase <|-- AggressiveAIController  
    AIControllerBase <|-- ItemFocusedAIController  
  
    Game --> Player : "manages"  
    Game --> MapManager : "uses"  
    Game --> LeaderboardManager : "uses"  
    Game --> AIControllerBase : "controls AI"  
    Game --> GameObject : "manages sprites"  
  
    Menu --> LeaderboardManager : "displays scores"  
    Menu --> Game : "creates"  
  
    Player --> Bomb : "places"  
    Bomb --> Explosion : "creates"  
    Explosion --> Wall : "destroys"  
    Wall --> Item : "drops"  
    Player --> Item : "collects"  
  
    AIControllerBase --> Player : "controls"  
    AIControllerBase --> MapManager : "queries"  
  
    MapManager --> Wall : "manages"