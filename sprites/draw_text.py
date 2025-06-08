DIGIT_MAP = {
    '0': [
        [1,1,1],
        [1,0,1],
        [1,0,1],
        [1,0,1],
        [1,1,1],
    ],
    '1': [
        [0,1,0],
        [1,1,0],
        [0,1,0],
        [0,1,0],
        [1,1,1],
    ],
    '2': [
        [1,1,1],
        [0,0,1],
        [1,1,1],
        [1,0,0],
        [1,1,1],
    ],
    '3': [
        [1,1,1],
        [0,0,1],
        [1,1,1],
        [0,0,1],
        [1,1,1],
    ],
    '4': [
        [1,0,1],
        [1,0,1],
        [1,1,1],
        [0,0,1],
        [0,0,1],
    ],
    '5': [
        [1,1,1],
        [1,0,0],
        [1,1,1],
        [0,0,1],
        [1,1,1],
    ],
    '6': [
        [1,1,1],
        [1,0,0],
        [1,1,1],
        [1,0,1],
        [1,1,1],
    ],
    '7': [
        [1,1,1],
        [1,0,1],
        [0,0,1],
        [0,0,1],
        [0,0,1],
    ],
    '8': [
        [1,1,1],
        [1,0,1],
        [1,1,1],
        [1,0,1],
        [1,1,1],
    ],
    '9': [
        [1,1,1],
        [1,0,1],
        [1,1,1],
        [0,0,1],
        [1,1,1],
    ],
    ':': [
        [0],
        [1],
        [0],
        [1],
        [0],
    ]
}


def draw_text_with_shadow(screen, text, font, pos, text_color=(255,255,255), shadow_color=(0,0,0), shadow_offset=(2,2)):
    x, y = pos
    shadow_surf = font.render(text, True, shadow_color)
    screen.blit(shadow_surf, (x + shadow_offset[0], y + shadow_offset[1]))
    text_surf = font.render(text, True, text_color)
    screen.blit(text_surf, (x, y))

def draw_text_with_outline(screen, text, font, pos, text_color=(0,0,0), outline_color=(200,200,200), of=2):
    x, y = pos
    offsets = [(-of,0),(of,0),(0,-of),(0,of),(-of,-of),(-of,of),(of,-of),(of,of)]
    for dx, dy in offsets:
        outline = font.render(text, True, outline_color)
        screen.blit(outline, (x + dx, y + dy))
    main_text = font.render(text, True, text_color)
    screen.blit(main_text, (x, y))
    
import pygame
    
class FloatingText(pygame.sprite.Sprite):
    def __init__(self, x, y, text, color=(255, 0, 0), duration=1000, rise_speed=1):
        super().__init__()
        self.font = pygame.font.Font(None, 32)  # 你也可以用自己的字體
        self.image = self.font.render(text, True, color)
        self.rect = self.image.get_rect(center=(x, y))
        self.start_time = pygame.time.get_ticks()
        self.duration = duration
        self.rise_speed = rise_speed

    def update(self):
        self.rect.y -= self.rise_speed  # 每幀往上飄
        if pygame.time.get_ticks() - self.start_time > self.duration:
            self.kill()  # 時間到自動移除
