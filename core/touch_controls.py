# core/touch_controls.py
import pygame
import settings
import os

class TouchControls:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.buttons = {} # 先初始化，以防圖片載入失敗

        # --- 載入按鍵圖片 ---
        ui_path = os.path.join(settings.IMAGES_DIR, "ui")
        try:
            # 準備圖片名稱映射
            image_files = {
                'UP': 'arrow_up.png', 'DOWN': 'arrow_down.png', 'LEFT': 'arrow_left.png', 'RIGHT': 'arrow_right.png', 'BOMB': 'button_bomb.png',
                'UP_pressed': 'arrow_up_pressed.png', 'DOWN_pressed': 'arrow_down_pressed.png', 'LEFT_pressed': 'arrow_left_pressed.png', 'RIGHT_pressed': 'arrow_right_pressed.png', 'BOMB_pressed': 'button_bomb_pressed.png'
            }
            # 載入所有圖片
            self.images = {key: pygame.image.load(os.path.join(ui_path, fname)).convert_alpha() for key, fname in image_files.items()}

            # 調整圖片大小
            dpad_button_size = 80
            bomb_button_size = 120
            for key, img in self.images.items():
                size = bomb_button_size if 'BOMB' in key else dpad_button_size
                self.images[key] = pygame.transform.scale(img, (size, size))

        except pygame.error as e:
            print(f"FATAL: Error loading touch control images from '{ui_path}'. Please check image files. Error: {e}")
            return # 圖片載入失敗，直接返回

        # --- 按鍵佈局與狀態 ---
        dpad_center_x = 120
        dpad_center_y = self.screen_height - 120
        gap = 70

        self.buttons = {
            'UP': {'rect': self.images['UP'].get_rect(center=(dpad_center_x, dpad_center_y - gap)), 'pressed': False},
            'DOWN': {'rect': self.images['DOWN'].get_rect(center=(dpad_center_x, dpad_center_y + gap)), 'pressed': False},
            'LEFT': {'rect': self.images['LEFT'].get_rect(center=(dpad_center_x - gap, dpad_center_y)), 'pressed': False},
            'RIGHT': {'rect': self.images['RIGHT'].get_rect(center=(dpad_center_x + gap, dpad_center_y)), 'pressed': False},
            'BOMB': {'rect': self.images['BOMB'].get_rect(center=(self.screen_width - 120, self.screen_height - 120)), 'pressed': False}
        }

    def draw(self, surface):
        if not self.buttons: return

        for key, button_data in self.buttons.items():
            img_key = f"{key}_pressed" if button_data['pressed'] else key
            surface.blit(self.images[img_key], button_data['rect'])

    def handle_event(self, event):
        if not self.buttons: return None
        
        # 炸彈是事件驅動
        if event.type == pygame.MOUSEBUTTONDOWN:
            bomb_button = self.buttons['BOMB']
            if bomb_button['rect'].collidepoint(event.pos):
                bomb_button['pressed'] = True
                return 'BOMB'

            # 方向鍵也在此處更新按下的狀態
            for key in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
                button = self.buttons[key]
                if button['rect'].collidepoint(event.pos):
                    button['pressed'] = True
        
        elif event.type == pygame.MOUSEBUTTONUP:
            # 釋放所有按鍵
            for button in self.buttons.values():
                button['pressed'] = False
        
        return None

    # V---------- 新增這個遺漏的函式 ----------V
    def is_pressed(self, key):
        """
        檢查某個按鍵當前是否處於被按住的狀態。
        """
        if key in self.buttons:
            return self.buttons[key]['pressed']
        return False
    # ^---------- 新增這個遺漏的函式 ----------^