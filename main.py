# oop-2025-proj-pycade/main.py (FINAL VERSION - REVISED FOR ThankYouScene)

import pygame
import settings
import asyncio
from game import Game
from core.menu import Menu
from core.thank_you_scene import ThankYouScene # 【新增】在頂部匯入 ThankYouScene

async def main():
    await asyncio.sleep(0.1)
    pygame.display.init()
    pygame.font.init()
    
    screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    
    pygame.display.set_caption(settings.TITLE)
    clock = pygame.time.Clock()

    current_scene = Menu(screen)
    running_main_loop = True

    while running_main_loop:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running_main_loop = False
                break
        if not running_main_loop:
            break

        next_scene_candidate = None

        if isinstance(current_scene, Menu):
            next_scene_candidate = current_scene.update(events)
            if next_scene_candidate is current_scene:
                current_scene.draw()
            # 【修改】如果 Menu 返回 "QUIT"，我們現在讓它切換到 ThankYouScene
            elif next_scene_candidate == "QUIT": 
                # 這個 "QUIT" 實際上已經被 menu.py 改成返回 ThankYouScene 物件了
                # 但為了程式碼的健壯性，如果意外收到 "QUIT"，也轉到感謝畫面
                print("Menu requested QUIT, transitioning to ThankYouScreen.")
                current_scene = ThankYouScene(screen)
            elif isinstance(next_scene_candidate, ThankYouScene): # Menu 直接返回 ThankYouScene
                current_scene = next_scene_candidate
            else: # 應該是 Game 物件
                current_scene = next_scene_candidate

        elif isinstance(current_scene, Game):
            next_scene_candidate = current_scene.run_one_frame(events)
            if next_scene_candidate is current_scene:
                pass # Game 的 run_one_frame 內部已經繪製
            elif next_scene_candidate == "QUIT":
                 # 如果 Game 場景因為 ESC 等原因退出，也顯示感謝畫面
                print("Game requested QUIT, transitioning to ThankYouScreen.")
                current_scene = ThankYouScene(screen)
            else: # 應該是 Menu 物件
                current_scene = next_scene_candidate
        
        elif isinstance(current_scene, ThankYouScene):
            # ThankYouScene 的 update 通常只返回 self，除非您想讓它也能觸發真正的退出
            next_scene_candidate = current_scene.update(events)
            current_scene.draw()
            # 如果 ThankYouScene 設計成可以返回 "REAL_QUIT" 來結束應用程式：
            # if next_scene_candidate == "REAL_QUIT":
            #     running_main_loop = False
            # 目前的 ThankYouScene 會一直顯示，等待使用者關閉分頁

        pygame.display.flip()
        clock.tick(settings.FPS)
        await asyncio.sleep(0)

    pygame.quit()
    print("Pygame application ended.") # 可以在終端機看到這個訊息

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")