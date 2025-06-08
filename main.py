# oop-2025-proj-pycade/main.py

import pygame
import settings
import asyncio
from game import Game
from core.menu import Menu
from core.thank_you_scene import ThankYouScene
from core.audio_manager import AudioManager # 匯入 AudioManager

async def main():
    await asyncio.sleep(0.1)
    pygame.display.init()
    pygame.font.init()
    
    # AudioManager 會處理 mixer 的初始化
    
    screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    
    pygame.display.set_caption(settings.TITLE)
    clock = pygame.time.Clock()

    # 在這裡建立唯一的 AudioManager 實例
    audio_manager = AudioManager()

    # 將 audio_manager 和 clock 傳遞給第一個 Menu 場景
    current_scene = Menu(screen, audio_manager, clock)
    running_main_loop = True

    while running_main_loop:
        # 事件獲取移到迴圈頂部
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running_main_loop = False
                break
        if not running_main_loop:
            break

        # 由主迴圈統一計算 dt (時間差)，並移除迴圈末尾的 clock.tick()
        dt = clock.tick(settings.FPS) / 1000.0

        next_scene_candidate = None

        if isinstance(current_scene, Menu):
            next_scene_candidate = current_scene.update(events)
            if next_scene_candidate is current_scene:
                current_scene.draw()
            elif next_scene_candidate == "QUIT":
                print("Menu requested QUIT, transitioning to ThankYouScreen.")
                audio_manager.stop_music()
                audio_manager.stop_all_sounds()
                current_scene = ThankYouScene(screen, audio_manager)
            elif isinstance(next_scene_candidate, Game): # Menu 返回了 Game 物件
                current_scene = next_scene_candidate
            else: 
                 current_scene = next_scene_candidate

        elif isinstance(current_scene, Game):
            # 將 events 和 dt 都傳遞給 Game 場景
            next_scene_candidate = current_scene.run_one_frame(events, dt)
            if next_scene_candidate is current_scene:
                pass 
            # Game 場景結束後，返回的可能是 Menu 或 "QUIT"
            elif next_scene_candidate == "QUIT":
                print("Game requested QUIT, transitioning to ThankYouScreen.")
                # audio_manager.stop_music() # game.py 中已處理
                current_scene = ThankYouScene(screen, audio_manager)
            else: # 應該是 Menu 物件
                current_scene = next_scene_candidate
        
        elif isinstance(current_scene, ThankYouScene):
            next_scene_candidate = current_scene.update(events)
            current_scene.draw()

        pygame.display.flip()
        # clock.tick(settings.FPS) # 移到迴圈頂部計算 dt
        await asyncio.sleep(0)

    pygame.quit()
    print("Pygame application ended.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")