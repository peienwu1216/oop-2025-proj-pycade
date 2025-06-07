# core/touch_controls.py
import pygame
import settings

class TouchControls:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # 按鍵顏色
        self.BUTTON_COLOR = (128, 128, 128, 150)  # 半透明灰色
        self.BUTTON_PRESSED_COLOR = (100, 100, 100, 200) # 按下時的顏色

        # --- D-Pad (方向鍵) ---
        dpad_center_x = 120
        dpad_center_y = self.screen_height - 120
        button_size = 50
        gap = 55 # 按鍵中心間的距離

        self.buttons = {
            'UP': {'rect': pygame.Rect(dpad_center_x - button_size / 2, dpad_center_y - gap, button_size, button_size), 'pressed': False},
            'DOWN': {'rect': pygame.Rect(dpad_center_x - button_size / 2, dpad_center_y + gap - button_size, button_size, button_size), 'pressed': False},
            'LEFT': {'rect': pygame.Rect(dpad_center_x - gap, dpad_center_y - button_size / 2, button_size, button_size), 'pressed': False},
            'RIGHT': {'rect': pygame.Rect(dpad_center_x + gap - button_size, dpad_center_y - button_size / 2, button_size, button_size), 'pressed': False},
        }

        # --- Action Button (放置炸彈) ---
        action_button_center_x = self.screen_width - 120
        action_button_center_y = self.screen_height - 120
        action_button_radius = 60

        # 我們用一個圓形的 rect 來偵測碰撞
        self.action_button_rect = pygame.Rect(
            action_button_center_x - action_button_radius,
            action_button_center_y - action_button_radius,
            action_button_radius * 2,
            action_button_radius * 2
        )
        self.buttons['BOMB'] = {'rect': self.action_button_rect, 'pressed': False, 'radius': action_button_radius}
