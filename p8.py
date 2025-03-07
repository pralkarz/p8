import random
import sys

import pygame

SCALING_FACTOR = 8
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


class P8:
    def __init__(self, rom, screen, scaling_factor):
        self.screen = screen
        self.scaling_factor = scaling_factor

        self.bg_color = pygame.Color(255, 230, 238)
        self.fg_color = pygame.Color(52, 50, 49)

        self.pc = 0x200
        self.memory = [0 for _ in range(0xFFF)]
        with open(rom, "rb") as file:
            address = 0x200
            while next_byte := file.read(1):
                self.memory[address] = int.from_bytes(next_byte)
                address += 1

        self.data_registers = [0 for _ in range(16)]
        self.address_register = 0
        self.stack = []
        self.delay_timer = 0
        self.pressed_keys = {i: False for i in range(16)}
        self.await_key_press = False
        self.awaited_key_presses = set()
        self.continue_with = None
        self.display = [[0 for _ in range(64)] for _ in range(32)]

    def process_next_opcode(self):
        first_byte = self.memory[self.pc]
        second_byte = self.memory[self.pc + 1]
        opcode = hex(first_byte)[2:].zfill(2) + hex(second_byte)[2:].zfill(2)

        if opcode == "00e0":
            self.clear_screen()
            self.draw()
            self.pc += 2
        elif opcode == "00ee":
            self.pc = self.stack.pop() + 2
        elif opcode.startswith("1"):
            self.pc = int(opcode[1:], 16)
        elif opcode.startswith("2"):
            self.stack.append(self.pc)
            self.pc = int(opcode[1:], 16)
        elif opcode.startswith("3"):
            index = int(opcode[1], 16)
            if self.data_registers[index] == int(opcode[2:], 16):
                self.pc += 4
            else:
                self.pc += 2
        elif opcode.startswith("4"):
            index = int(opcode[1], 16)
            if self.data_registers[index] != int(opcode[2:], 16):
                self.pc += 4
            else:
                self.pc += 2
        elif opcode.startswith("5"):
            vx = self.data_registers[int(opcode[1], 16)]
            vy = self.data_registers[int(opcode[2], 16)]
            if vx == vy:
                self.pc += 4
            else:
                self.pc += 2
        elif opcode.startswith("6"):
            index = int(opcode[1], 16)
            self.data_registers[index] = int(opcode[2:], 16)
            self.pc += 2
        elif opcode.startswith("7"):
            index = int(opcode[1], 16)
            self.data_registers[index] += int(opcode[2:], 16)
            if self.data_registers[index] > 255:
                self.data_registers[index] &= 255
            self.pc += 2
        elif opcode.startswith("8"):
            match opcode[3]:
                case "0":
                    self.data_registers[int(opcode[1], 16)] = self.data_registers[
                        int(opcode[2], 16)
                    ]
                case "1":
                    self.data_registers[int(opcode[1], 16)] |= self.data_registers[
                        int(opcode[2], 16)
                    ]
                case "2":
                    self.data_registers[int(opcode[1], 16)] &= self.data_registers[
                        int(opcode[2], 16)
                    ]
                case "3":
                    self.data_registers[int(opcode[1], 16)] ^= self.data_registers[
                        int(opcode[2], 16)
                    ]
                case "4":
                    x = int(opcode[1], 16)
                    y = int(opcode[2], 16)

                    self.data_registers[x] += self.data_registers[y]
                    if self.data_registers[x] > 255:
                        self.data_registers[x] &= 255
                        self.data_registers[15] = 1
                    else:
                        self.data_registers[15] = 0
                case "5":
                    x = int(opcode[1], 16)
                    y = int(opcode[2], 16)

                    self.data_registers[x] -= self.data_registers[y]
                    if self.data_registers[x] < 0:
                        self.data_registers[x] &= 255
                        self.data_registers[15] = 0
                    else:
                        self.data_registers[15] = 1
                case "6":
                    x = int(opcode[1], 16)
                    y = int(opcode[2], 16)
                    self.data_registers[x] = self.data_registers[y]
                    self.data_registers[x], carry = (
                        self.data_registers[x] >> 1,
                        self.data_registers[x] & 1,
                    )
                    self.data_registers[15] = carry
                case "7":
                    x = int(opcode[1], 16)
                    y = int(opcode[2], 16)

                    self.data_registers[x] = (
                        self.data_registers[y] - self.data_registers[x]
                    )
                    if self.data_registers[x] < 0:
                        self.data_registers[x] &= 255
                        self.data_registers[15] = 0
                    else:
                        self.data_registers[15] = 1
                case "e":
                    x = int(opcode[1], 16)
                    y = int(opcode[2], 16)
                    self.data_registers[x] = self.data_registers[y]
                    self.data_registers[x], carry = (
                        self.data_registers[x] << 1,
                        (self.data_registers[x] >> 7) & 1,
                    )
                    self.data_registers[x] &= 255
                    self.data_registers[15] = carry
                case _:
                    raise NotImplementedError(
                        f"Encountered {opcode} -- an invalid or not implemented opcode."
                    )

            self.pc += 2
        elif opcode.startswith("9"):
            vx = self.data_registers[int(opcode[1], 16)]
            vy = self.data_registers[int(opcode[2], 16)]
            if vx != vy:
                self.pc += 4
            else:
                self.pc += 2
        elif opcode.startswith("a"):
            self.address_register = int(opcode[1:], 16)
            self.pc += 2
        elif opcode.startswith("c"):
            self.data_registers[int(opcode[1], 16)] = random.randint(0, 255) & int(
                opcode[2:], 16
            )
            self.pc += 2
        elif opcode.startswith("d"):
            vx = self.data_registers[int(opcode[1], 16)]
            vy = self.data_registers[int(opcode[2], 16)]
            width = 8
            height = int(opcode[3], 16)

            row_number = 0
            for y, row in enumerate(self.display[vy : vy + height], start=vy):
                sprite = self.memory[self.address_register + row_number]

                shift = 7
                for x, pixel in enumerate(row[vx : vx + width], start=vx):
                    mask = 1 << shift
                    if sprite & mask:
                        if pixel == 1:
                            # Flipping from set to unset, therefore setting VF to 1.
                            self.data_registers[15] = 1
                        self.display[y][x] ^= 1

                        self.draw()

                    shift -= 1

                row_number += 1

            self.pc += 2
        elif opcode.startswith("e"):
            match opcode[2:]:
                case "9e":
                    x = int(opcode[1], 16)
                    if self.pressed_keys[self.data_registers[x] & 0x0F]:
                        self.pc += 4
                    else:
                        self.pc += 2
                case "a1":
                    x = int(opcode[1], 16)
                    if not self.pressed_keys[self.data_registers[x] & 0x0F]:
                        self.pc += 4
                    else:
                        self.pc += 2
                case _:
                    raise NotImplementedError(
                        f"Encountered {opcode} -- an invalid or not implemented opcode."
                    )
        elif opcode.startswith("f"):
            match opcode[2:]:
                case "07":
                    self.data_registers[int(opcode[1], 16)] = self.delay_timer
                case "0a":
                    if len(self.awaited_key_presses) and self.continue_with:
                        self.data_registers[int(opcode[1], 16)] = self.continue_with
                        self.await_key_press = False
                        self.awaited_key_presses = set()
                        self.continue_with = None
                        self.pc += 2
                    else:
                        self.await_key_press = True

                    return
                case "15":
                    self.delay_timer = self.data_registers[int(opcode[1], 16)]
                case "1e":
                    self.address_register += self.data_registers[int(opcode[1], 16)]
                case "33":
                    vx = str(self.data_registers[int(opcode[1], 16)])

                    if len(vx) == 1:
                        self.memory[self.address_register] = 0
                        self.memory[self.address_register + 1] = 0
                        self.memory[self.address_register + 2] = int(vx)
                    elif len(vx) == 2:
                        self.memory[self.address_register] = 0
                        offset = 1
                        for digit in vx:
                            self.memory[self.address_register + offset] = int(digit)
                            offset += 1
                    else:
                        offset = 0
                        for digit in vx:
                            self.memory[self.address_register + offset] = int(digit)
                            offset += 1
                case "55":
                    up_to = int(opcode[1], 16)

                    for i in range(up_to + 1):
                        self.memory[self.address_register + i] = self.data_registers[i]
                case "65":
                    up_to = int(opcode[1], 16)

                    for i in range(up_to + 1):
                        self.data_registers[i] = self.memory[self.address_register + i]

                case _:
                    raise NotImplementedError(
                        f"Encountered {opcode} -- an invalid or not implemented opcode."
                    )

            self.pc += 2
        else:
            raise NotImplementedError(
                f"Encountered {opcode} -- an invalid or not implemented opcode."
            )

    def clear_screen(self):
        self.display = [[0 for _ in range(64)] for _ in range(32)]

    def draw(self):
        for y, row in enumerate(self.display):
            for x, pixel in enumerate(row):
                pygame.draw.rect(
                    self.screen,
                    self.fg_color if pixel else self.bg_color,
                    pygame.Rect(
                        x * self.scaling_factor,
                        y * self.scaling_factor,
                        self.scaling_factor,
                        self.scaling_factor,
                    ),
                )


def main():
    pygame.init()
    screen = pygame.display.set_mode((64 * SCALING_FACTOR, 32 * SCALING_FACTOR))
    pygame.display.set_caption("P8 -- CHIP-8 emulator/interpreter")

    p8 = P8(sys.argv[1], screen, SCALING_FACTOR)

    clock = pygame.time.Clock()
    delay_timer_tick = pygame.USEREVENT + 1
    pygame.time.set_timer(delay_timer_tick, 17)  # ~60 Hz

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
                            p8.awaited_key_presses.add(idx)
                    except ValueError:
                        print("Unsupported key pressed.")
                case pygame.KEYUP:
                    try:
                        idx = KEYPAD.index(event.key)
                        p8.pressed_keys[idx] = False
                        if idx in p8.awaited_key_presses:
                            p8.continue_with = idx
                    except ValueError:
                        print("Unsupported key released.")
                case delay_timer_tick:
                    if p8.delay_timer > 0:
                        p8.delay_timer -= 1

        p8.process_next_opcode()
        pygame.display.flip()
        clock.tick()

    pygame.quit()


if __name__ == "__main__":
    main()
