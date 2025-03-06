import sys

import pygame


class P8:
    def __init__(self):
        self.scaling_factor = 8
        self.bg_color = pygame.Color(255, 230, 238)
        self.fg_color = pygame.Color(52, 50, 49)

        self.memory = [0 for _ in range(0xFFF)]
        with open(sys.argv[1], "rb") as file:
            address = 0x200
            while next_byte := file.read(1):
                self.memory[address] = next_byte.hex()
                address += 1

        self.instruction_pointer = 0x200
        self.data_registers = [0 for _ in range(16)]
        self.address_register = 0
        self.display = [[0 for _ in range(64)] for _ in range(32)]

    def next_opcode(self):
        first_byte = self.memory[self.instruction_pointer]
        second_byte = self.memory[self.instruction_pointer + 1]
        opcode = first_byte + second_byte

        if opcode == "00e0":
            self.clear_screen()
            self.render()
            self.instruction_pointer += 2
        elif opcode.startswith("1"):
            self.instruction_pointer = int(opcode[1:], 16)
        elif opcode.startswith("6"):
            index = int(opcode[1], 16)
            self.data_registers[index] = int(opcode[2:], 16)
            self.instruction_pointer += 2
        elif opcode.startswith("7"):
            index = int(opcode[1], 16)
            self.data_registers[index] += int(opcode[2:], 16)
            self.instruction_pointer += 2
        elif opcode.startswith("a"):
            self.address_register = int(opcode[1:], 16)
            self.instruction_pointer += 2
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
                    if int(sprite, 16) & mask:
                        if pixel == 1:
                            # Flipping from set to unset, therefore setting VF to 1.
                            self.data_registers[15] = 1
                        self.display[y][x] ^= 1
                    shift -= 1

                row_number += 1

            self.instruction_pointer += 2

            self.render()
        else:
            raise NotImplementedError(
                f"Encountered {opcode} -- an opcode that isn't implemented."
            )

    def clear_screen(self):
        self.display = [[0 for _ in range(64)] for _ in range(32)]

    def render(self):
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
    app = P8()

    pygame.init()
    app.screen = pygame.display.set_mode(
        (64 * app.scaling_factor, 32 * app.scaling_factor)
    )
    pygame.display.set_caption("P8")
    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        app.next_opcode()

        pygame.display.flip()

        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
