import pygame


class InvalidOpcode(Exception):
    def __init__(self, opcode):
        super().__init__(
            f"Encountered {hex(opcode)[2:].zfill(4).upper()} -- an invalid or not implemented opcode."
        )


class P8:
    def __init__(self, rom_path, screen, scaling_factor):
        self.screen = screen
        self.scaling_factor = scaling_factor

        self.bg_color = pygame.Color(255, 230, 238)
        self.fg_color = pygame.Color(52, 50, 49)

        self.pc = 0x200
        self.memory = [0 for _ in range(0xFFF)]
        with open(rom_path, "rb") as file:
            address = 0x200
            while next_byte := file.read(1):
                self.memory[address] = int.from_bytes(next_byte)
                address += 1

        self.data_registers = [0 for _ in range(16)]
        self.address_register = 0
        self.stack = []
        self.delay_timer = 0
        self.pressed_keys = {i: False for i in range(16)}

        # Related to FX0A, i.e. blocking input handling.
        self.await_key_press = False
        self.started_key_presses = set()
        self.completed_key_press = None

        self.display = [[0 for _ in range(64)] for _ in range(32)]

    # Some operations inspired by https://github.com/Janiczek/cfs-chip8.
    def next_cycle(self):
        opcode = self.memory[self.pc] << 8
        opcode |= self.memory[self.pc + 1]

        advance_pc = True
        match opcode & 0xF000:
            case 0x0000:
                match opcode & 0x00FF:
                    case 0x00E0:
                        self.clear_screen()
                        self.draw()
                    case 0x00EE:
                        self.pc = self.stack.pop()
                    case _:
                        raise InvalidOpcode(opcode)
            case 0x1000:
                self.pc = opcode & 0x0FFF
                advance_pc = False
            case 0x2000:
                self.stack.append(self.pc)
                self.pc = opcode & 0x0FFF
                advance_pc = False
            case 0x3000:
                x = (opcode & 0x0F00) >> 8
                if self.data_registers[x] == opcode & 0x00FF:
                    self.pc += 2
            case 0x4000:
                x = (opcode & 0x0F00) >> 8
                if self.data_registers[x] != opcode & 0x00FF:
                    self.pc += 2
            case 0x5000:
                vx = self.data_registers[(opcode & 0x0F00) >> 8]
                vy = self.data_registers[(opcode & 0x00F0) >> 4]
                if vx == vy:
                    self.pc += 2
            case 0x6000:
                x = (opcode & 0x0F00) >> 8
                self.data_registers[x] = opcode & 0x00FF
            case 0x7000:
                x = (opcode & 0x0F00) >> 8
                nn = opcode & 0x00FF
                if (result := (self.data_registers[x] + nn)) > 255:
                    self.data_registers[x] = result & 255
                else:
                    self.data_registers[x] = result
            case 0x8000:
                x = (opcode & 0x0F00) >> 8
                y = (opcode & 0x00F0) >> 4

                match opcode & 0x000F:
                    case 0x0000:
                        self.data_registers[x] = self.data_registers[y]
                    case 0x0001:
                        self.data_registers[x] = (
                            self.data_registers[x] | self.data_registers[y]
                        )
                    case 0x0002:
                        self.data_registers[x] = (
                            self.data_registers[x] & self.data_registers[y]
                        )
                    case 0x0003:
                        self.data_registers[x] = (
                            self.data_registers[x] ^ self.data_registers[y]
                        )
                    case 0x0004:
                        result = self.data_registers[x] + self.data_registers[y]
                        if result > 255:
                            self.data_registers[x] = result & 255
                            self.data_registers[0xF] = 1
                        else:
                            self.data_registers[x] = result
                            self.data_registers[0xF] = 0
                    case 0x0005:
                        result = self.data_registers[x] - self.data_registers[y]
                        if result < 0:
                            self.data_registers[x] = result & 255
                            self.data_registers[0xF] = 0
                        else:
                            self.data_registers[x] = result
                            self.data_registers[0xF] = 1
                    case 0x0006:
                        self.data_registers[x] = self.data_registers[y]
                        self.data_registers[x], lsb = (
                            self.data_registers[x] >> 1,
                            self.data_registers[x] & 1,
                        )
                        self.data_registers[0xF] = lsb
                    case 0x0007:
                        result = self.data_registers[y] - self.data_registers[x]
                        if result < 0:
                            self.data_registers[x] = result & 255
                            self.data_registers[0xF] = 0
                        else:
                            self.data_registers[x] = result
                            self.data_registers[0xF] = 1
                    case 0x000E:
                        self.data_registers[x] = self.data_registers[y]
                        self.data_registers[x], msb = (
                            (self.data_registers[x] << 1) & 255,
                            (self.data_registers[x] >> 7) & 1,
                        )
                        self.data_registers[0xF] = msb
                    case _:
                        raise InvalidOpcode(opcode)
            case 0x9000:
                vx = self.data_registers[(opcode & 0x0F00) >> 8]
                vy = self.data_registers[(opcode & 0x00F0) >> 4]
                if vx != vy:
                    self.pc += 2
            case 0xA000:
                self.address_register = opcode & 0x0FFF
            case 0xD000:
                self.data_registers[0xF] = 0

                vx = self.data_registers[(opcode & 0x0F00) >> 8]
                vy = self.data_registers[(opcode & 0x00F0) >> 4]
                width = 8
                height = opcode & 0x000F

                row_number = 0
                for y, row in enumerate(self.display[vy : vy + height], start=vy):
                    sprite = self.memory[self.address_register + row_number]

                    shift = 7
                    for x, pixel in enumerate(row[vx : vx + width], start=vx):
                        mask = 1 << shift
                        if sprite & mask:
                            if pixel:
                                # Flipping from set to unset, therefore setting VF to 1.
                                self.data_registers[0xF] = 1
                            self.display[y][x] ^= 1

                        shift -= 1

                    row_number += 1

                self.draw()
            case 0xE000:
                x = (opcode & 0x0F00) >> 8

                match opcode & 0x00FF:
                    case 0x009E:
                        if self.pressed_keys[self.data_registers[x] & 0x0F]:
                            self.pc += 2
                    case 0x00A1:
                        if not self.pressed_keys[self.data_registers[x] & 0x0F]:
                            self.pc += 2
                    case _:
                        raise InvalidOpcode(opcode)
            case 0xF000:
                x = (opcode & 0x0F00) >> 8

                match opcode & 0x00FF:
                    case 0x0007:
                        self.data_registers[x] = self.delay_timer
                    case 0x000A:
                        if len(self.started_key_presses) and self.completed_key_press:
                            self.data_registers[x] = self.completed_key_press
                            self.await_key_press = False
                            self.started_key_presses = set()
                            self.completed_key_press = None
                        else:
                            self.await_key_press = True
                            advance_pc = False
                    case 0x0015:
                        self.delay_timer = self.data_registers[x]
                    case 0x001E:
                        self.address_register += self.data_registers[x]
                    case 0x0033:
                        value = self.data_registers[x]
                        self.memory[self.address_register] = value // 100
                        self.memory[self.address_register + 1] = (value // 10) % 10
                        self.memory[self.address_register + 2] = value % 10
                    case 0x0055:
                        for i in range(x + 1):
                            self.memory[self.address_register + i] = (
                                self.data_registers[i]
                            )
                    case 0x0065:
                        for i in range(x + 1):
                            self.data_registers[i] = self.memory[
                                self.address_register + i
                            ]
                    case _:
                        raise InvalidOpcode(opcode)
            case _:
                raise InvalidOpcode(opcode)

        self.pc += 2 if advance_pc else 0

    def clear_screen(self):
        for y in range(len(self.display)):
            for x in range(len(self.display[0])):
                self.display[y][x] = 0

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
        pygame.display.flip()
