# core/touch_controls.py
import pygame
import settings
import os

class TouchControls:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.buttons = {}
        self.images = {}

        # --- 步驟 1: 載入所有需要的圖片 ---
        ui_path = os.path.join(settings.IMAGES_DIR, "ui")
        image_files = {
            'UP': 'arrow_up.png', 'DOWN': 'arrow_down.png', 'LEFT': 'arrow_left.png', 'RIGHT': 'arrow_right.png', 'BOMB': 'button_bomb.png',
            'UP_pressed': 'arrow_up_pressed.png', 'DOWN_pressed': 'arrow_down_pressed.png', 'LEFT_pressed': 'arrow_left_pressed.png', 'RIGHT_pressed': 'arrow_right_pressed.png', 'BOMB_pressed': 'button_bomb_pressed.png'
        }

        try:
            for key, fname in image_files.items():
                full_path = os.path.join(ui_path, fname)
                self.images[key] = pygame.image.load(full_path).convert_alpha()
        except pygame.error as e:
            print(f"FATAL: Error loading touch control image '{full_path}'. Please check image files. Error: {e}")
            # 讓按鈕字典保持為空，這樣後續的函式呼叫會安全地失敗
            return

        # --- 步驟 2: 調整圖片大小 ---
        dpad_button_size = 80
        bomb_button_size = 120
        for key, img in self.images.items():
            size = bomb_button_size if 'BOMB' in key else dpad_button_size
            self.images[key] = pygame.transform.scale(img, (size, size))

        # --- 步驟 3: 設定按鍵位置與狀態 ---
        dpad_center_x = 120
        dpad_center_y = self.screen_height - 120
        # 注意：這裡的 gap 是指 D-pad 中心到各方向鍵中心的距離
        gap = 60

        self.buttons = {
            'UP':    {'rect': self.images['UP'].get_rect(center=(dpad_center_x, dpad_center_y - gap)), 'pressed': False},
            'DOWN':  {'rect': self.images['DOWN'].get_rect(center=(dpad_center_x, dpad_center_y + gap)), 'pressed': False},
            'LEFT':  {'rect': self.images['LEFT'].get_rect(center=(dpad_center_x - gap, dpad_center_y)), 'pressed': False},
            'RIGHT': {'rect': self.images['RIGHT'].get_rect(center=(dpad_center_x + gap, dpad_center_y)), 'pressed': False},
            'BOMB':  {'rect': self.images['BOMB'].get_rect(center=(self.screen_width - 120, self.screen_height - 120)), 'pressed': False}
        }

    def draw(self, surface):
        """繪製所有虛擬按鍵到畫面上。現在是繪製圖片而不是色塊。"""
        if not self.buttons: return # 如果初始化失敗，則不繪製

        for key, button_data in self.buttons.items():
            # 根據按鍵是否被按下，選擇對應的圖片
            img_key = f"{key}_pressed" if button_data['pressed'] else key
            surface.blit(self.images[img_key], button_data['rect'])

    def handle_event(self, event):
        """處理單次觸發的事件，並更新按鈕的持續按壓狀態。"""
        if not self.buttons: return None
        
        # 事件驅動的炸彈按鈕
        if event.type == pygame.MOUSEBUTTONDOWN:
            bomb_button = self.buttons['BOMB']
            if bomb_button['rect'].collidepoint(event.pos):
                bomb_button['pressed'] = True
                return 'BOMB'

            # 方向鍵的按下狀態
            for key in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
                button = self.buttons[key]
                if button['rect'].collidepoint(event.pos):
                    button['pressed'] = True
        
        elif event.type == pygame.MOUSEBUTTONUP:
            # 釋放所有按鍵
            for button in self.buttons.values():
                button['pressed'] = False
        
        return None

    def is_pressed(self, key):
        """檢查某個按鍵當前是否處於被按住的狀態。"""
        if key in self.buttons:
            return self.buttons[key]['pressed']
        return False