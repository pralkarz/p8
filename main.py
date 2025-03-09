import sys

import pygame

from src.p8 import P8

SCALING_FACTOR = 8
# 1 2 3 C
# 4 5 6 D
# 7 8 9 E
# A 0 B F
KEYPAD = [
    pygame.K_x,
    pygame.K_1,
    pygame.K_2,
    pygame.K_3,
    pygame.K_q,
    pygame.K_w,
    pygame.K_e,
    pygame.K_a,
    pygame.K_s,
    pygame.K_d,
    pygame.K_z,
    pygame.K_c,
    pygame.K_4,
    pygame.K_r,
    pygame.K_f,
    pygame.K_v,
]


def main():
    pygame.init()
    screen = pygame.display.set_mode((64 * SCALING_FACTOR, 32 * SCALING_FACTOR))
    pygame.display.set_caption("P8 -- CHIP-8 emulator/interpreter")

    p8 = P8(sys.argv[1], screen, SCALING_FACTOR)

    clock = pygame.time.Clock()
    delay_timer_tick = pygame.USEREVENT + 1

    running = True
    while running:
        for event in pygame.event.get():
            match event.type:
                case pygame.QUIT:
                    running = False
                case pygame.KEYDOWN:
                    try:
                        idx = KEYPAD.index(event.key)
                        p8.pressed_keys[idx] = True
                        if p8.await_key_press:
                            p8.started_key_presses.add(idx)
                    except ValueError:
                        print("Unsupported key pressed.")
                case pygame.KEYUP:
                    try:
                        idx = KEYPAD.index(event.key)
                        p8.pressed_keys[idx] = False
                        if idx in p8.started_key_presses:
                            p8.completed_key_press = idx
                    except ValueError:
                        print("Unsupported key released.")

        for _ in range(15):
            p8.next_cycle()

        if p8.delay_timer > 0:
            p8.delay_timer -= 1

        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
