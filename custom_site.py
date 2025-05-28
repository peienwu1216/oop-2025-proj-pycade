# custom_site.py

import asyncio
import pygame
import settings
from main import main as real_main  # ✅ 真正進入遊戲的函數

async def custom_site():
    print("🎮 custom_site(): Waiting for user interaction...")

    pygame.display.init()
    screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    pygame.display.set_caption("點一下開始遊戲")

    font = pygame.font.SysFont(None, 48)
    clock = pygame.time.Clock()

    clicked = False

    while not clicked:
        screen.fill((255, 255, 200))  # 淡黃色背景
        text = font.render("👉 點一下畫面開始遊戲 👈", True, (50, 50, 200))
        rect = text.get_rect(center=(settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2))
        screen.blit(text, rect)
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                clicked = True

        await asyncio.sleep(0)
        clock.tick(60)

    print("🎮 custom_site(): User clicked. Launching game main().")
    await real_main()

if __name__ == "__main__":
    import asyncio
    asyncio.run(custom_site())
