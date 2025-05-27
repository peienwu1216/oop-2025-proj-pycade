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

def draw_text_with_outline(screen, text, font, pos, text_color=(0,0,0), outline_color=(255,255,255)):
    x, y = pos
    of = 2
    offsets = [(-of,0),(of,0),(0,-of),(0,of),(-of,-of),(-of,of),(of,-of),(of,of)]
    for dx, dy in offsets:
        outline = font.render(text, True, outline_color)
        screen.blit(outline, (x + dx, y + dy))
    main_text = font.render(text, True, text_color)
    screen.blit(main_text, (x, y))