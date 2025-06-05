# 自訂 Gymnasium 環境

import numpy as np
import pygame
import gymnasium as gym
from gymnasium import spaces

import settings
from game import Game


class BombermanEnv(gym.Env):
    """Gymnasium environment wrapper for the Pycade Bomber game."""

    metadata = {"render_modes": ["human", None], "render_fps": settings.FPS}

    def __init__(self, render_mode: str | None = None, ai_archetype: str = None):
        self.render_mode = render_mode
        pygame.init()

        if render_mode == "human":
            self.screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
        else:
            # Off-screen surface for headless mode
            self.screen = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))

        self.clock = pygame.time.Clock()
        archetype = ai_archetype or getattr(settings, "AI_OPPONENT_ARCHETYPE", "original")
        self.game = Game(self.screen, self.clock, ai_archetype=archetype)
        self.game.player1.is_ai = True  # control via RL

        self._action_map = {
            0: (0, -1),  # Up
            1: (0, 1),   # Down
            2: (-1, 0),  # Left
            3: (1, 0),   # Right
            4: "bomb",   # Place bomb
            5: "wait",   # No-op
        }
        self.action_space = spaces.Discrete(len(self._action_map))

        grid_h = getattr(settings, "GRID_HEIGHT", 11)
        grid_w = getattr(settings, "GRID_WIDTH", 15)
        self.observation_space = spaces.Box(low=0, high=7, shape=(grid_h, grid_w), dtype=np.int8)
        self.prev_score = 0

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _get_observation(self) -> np.ndarray:
        width = self.game.map_manager.tile_width
        height = self.game.map_manager.tile_height
        obs = np.zeros((height, width), dtype=np.int8)

        for y, row in enumerate(self.game.map_manager.map_data):
            for x, ch in enumerate(row):
                if ch == "W":
                    obs[y, x] = 1
                elif ch == "D":
                    obs[y, x] = 2

        for bomb in self.game.bombs_group:
            if not bomb.exploded:
                obs[bomb.current_tile_y, bomb.current_tile_x] = 3

        for exp in self.game.explosions_group:
            tx = exp.rect.x // settings.TILE_SIZE
            ty = exp.rect.y // settings.TILE_SIZE
            obs[ty, tx] = 4

        for item in self.game.items_group:
            tx = item.rect.x // settings.TILE_SIZE
            ty = item.rect.y // settings.TILE_SIZE
            obs[ty, tx] = 5

        if self.game.player1.is_alive:
            obs[self.game.player1.tile_y, self.game.player1.tile_x] = 6
        if self.game.player2_ai.is_alive:
            obs[self.game.player2_ai.tile_y, self.game.player2_ai.tile_x] = 7
        return obs

    def _compute_reward(self) -> float:
        reward = float(self.game.player1.score - self.prev_score)
        self.prev_score = self.game.player1.score
        return reward

    def _render_frame(self) -> None:
        self.game._draw_internal()
        if self.render_mode == "human":
            pygame.display.flip()
            self.clock.tick(self.metadata["render_fps"])

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------
    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        self.game.setup_initial_state()
        self.game.player1.is_ai = True
        self.prev_score = 0
        observation = self._get_observation()
        info = {}
        if self.render_mode == "human":
            self._render_frame()
        return observation, info

    def step(self, action: int):
        assert self.action_space.contains(action)
        mapped = self._action_map[int(action)]
        player = self.game.player1
        if mapped == "bomb":
            player.place_bomb()
        elif mapped != "wait":
            dx, dy = mapped
            player.move(dx, dy)

        self.game.dt = 1 / self.metadata.get("render_fps", settings.FPS)
        self.game._update_internal()

        observation = self._get_observation()
        reward = self._compute_reward()
        terminated = False
        if self.game.game_state == "GAME_OVER":
            terminated = True
            if self.game.time_up_winner == "P1" or (self.game.player1.is_alive and not self.game.player2_ai.is_alive):
                reward += 100
            elif self.game.time_up_winner == "AI" or (self.game.player2_ai.is_alive and not self.game.player1.is_alive):
                reward -= 100

        info = {}
        if self.render_mode == "human":
            self._render_frame()
        return observation, reward, terminated, False, info

    def render(self) -> None:
        if self.render_mode == "human":
            self._render_frame()

    def close(self) -> None:
        pygame.quit()
