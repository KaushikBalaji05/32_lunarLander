import math
import random
import pygame

WIDTH, HEIGHT = 800, 600
STEP = 20

THRUST, ROTATE_SPEED, BURN_RATE, FUEL_MAX = 60.0, 2.4, 22.0, 300.0
MAX_SPEED_X, MAX_SPEED_Y, MAX_ANGLE = 25.0, 40.0, 0.25
FOOT = 12

# Landing fireworks are kept here because on_landing() intentionally receives
# only the score, not a Game/screen object.
FIREWORKS = []


def ship_color(fuel_ratio):
    """Return a hull colour that becomes increasingly red as fuel runs low."""
    fuel_ratio = max(0.0, min(1.0, float(fuel_ratio)))

    # Keep the original default colour when the tank is full.
    if fuel_ratio >= 0.999:
        return None

    normal = (230, 230, 240)
    critical = (255, 60, 60)
    t = 1.0 - fuel_ratio

    return tuple(round(a + (b - a) * t) for a, b in zip(normal, critical))


def on_landing(score):
    """Create a short fireworks burst after a successful landing."""
    # More points -> larger celebration. The function is deliberately
    # independent of Game/screen so its original signature remains unchanged.
    count = 18 if score < 500 else 30
    origin_x = WIDTH / 2
    origin_y = HEIGHT / 3

    for _ in range(count):
        angle = random.uniform(0.0, math.tau)
        speed = random.uniform(70.0, 180.0)
        FIREWORKS.append([
            origin_x,
            origin_y,
            math.cos(angle) * speed,
            math.sin(angle) * speed,
            random.uniform(0.7, 1.2),
            random.choice([
                (255, 90, 90),
                (255, 210, 80),
                (100, 220, 255),
                (170, 120, 255),
                (120, 255, 150),
            ]),
        ])


def update_fireworks(dt):
    """Advance and remove expired landing-firework particles."""
    alive = []
    for x, y, vx, vy, life, color in FIREWORKS:
        life -= dt
        if life > 0:
            vy += 90.0 * dt
            x += vx * dt
            y += vy * dt
            alive.append([x, y, vx, vy, life, color])
    FIREWORKS[:] = alive


def draw_fireworks(screen):
    """Draw active landing-firework particles."""
    for x, y, vx, vy, life, color in FIREWORKS:
        radius = max(1, min(4, int(1 + life * 2)))
        pygame.draw.circle(screen, color, (int(x), int(y)), radius)


def bonus_life_threshold():
    """Award one extra life whenever the score crosses another 1500 points."""
    return 1500


def make_terrain():
    heights, y = [], random.randint(430, 520)
    for _ in range(WIDTH // STEP + 1):
        y = max(380, min(560, y + random.randint(-32, 32)))
        heights.append(y)

    pads = []
    for start, length, mult in (
        (random.randint(2, 12), 4, 1),
        (random.randint(20, 35), 3, 3),
    ):
        for i in range(start, start + length):
            heights[i] = heights[start]
        pads.append((start * STEP, (start + length - 1) * STEP,
                     heights[start], mult))
    return heights, pads


def ground_y(heights, x):
    x = max(0, min(WIDTH - 1, x))
    i = int(x // STEP)
    t = (x - i * STEP) / STEP
    return heights[i] * (1 - t) + heights[i + 1] * t


def wrap_angle(angle):
    return (angle + math.pi) % math.tau - math.pi


class Game:
    def __init__(self):
        self.font = pygame.font.Font(None, 26)
        self.reset()

    def reset(self):
        self.level, self.score, self.lives = 1, 0, 3
        self.bonus_awarded = 0
        FIREWORKS.clear()
        self.new_round()

    def new_round(self):
        self.heights, self.pads = make_terrain()
        self.pos = pygame.Vector2(random.randint(100, 700), 70)
        self.vel = pygame.Vector2(random.uniform(-20, 20), 0)
        self.angle, self.fuel, self.thrusting = 0.0, FUEL_MAX, False
        self.state, self.message = "fly", ""

    def pad_under(self):
        for x1, x2, y, mult in self.pads:
            if x1 <= self.pos.x - 8 and self.pos.x + 8 <= x2:
                return (x1, x2, y, mult)
        return None

    def touchdown(self):
        pad = self.pad_under()
        angle = wrap_angle(self.angle)

        # A safe landing requires ALL three limits:
        # horizontal speed, vertical speed, and angle.
        if (
            pad
            and abs(self.vel.x) <= MAX_SPEED_X
            and abs(self.vel.y) <= MAX_SPEED_Y
            and abs(angle) <= MAX_ANGLE
        ):
            earned = int((100 + self.fuel) * pad[3])
            self.score += earned
            self.state = "landed"
            self.message = (
                f"Perfect landing! +{earned}  (Space = next level)"
            )
            on_landing(earned)
            return

        self.lives -= 1
        self.state = "crashed"

        if pad is None:
            reason = "missed the pad"
        elif abs(self.vel.x) > MAX_SPEED_X:
            reason = "too much sideways speed"
        elif abs(self.vel.y) > MAX_SPEED_Y:
            reason = "too much vertical speed"
        elif abs(angle) > MAX_ANGLE:
            reason = "bad angle"
        else:
            reason = "unsafe landing"

        self.message = (
            f"Crashed: {reason}!  "
            + ("Space = retry" if self.lives > 0
               else "Game over - R = restart")
        )

    def update(self, dt, keys):
        update_fireworks(dt)

        if self.state != "fly":
            return

        threshold = bonus_life_threshold()
        if threshold and self.score // threshold > self.bonus_awarded:
            self.bonus_awarded = self.score // threshold
            self.lives += 1

        self.angle += (
            (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT])
            * ROTATE_SPEED * dt
        )

        gravity = pygame.Vector2(0, 16 + 2 * self.level)
        self.thrusting = bool(keys[pygame.K_UP]) and self.fuel > 0

        acceleration = gravity
        if self.thrusting:
            acceleration = (
                gravity
                + pygame.Vector2(
                    math.sin(self.angle),
                    -math.cos(self.angle),
                ) * THRUST
            )
            self.fuel = max(0.0, self.fuel - BURN_RATE * dt)

        self.vel += acceleration * dt
        self.pos += self.vel * dt

        self.pos.x %= WIDTH
        self.pos.y = max(-200, self.pos.y)

        if self.pos.y + FOOT >= ground_y(self.heights, self.pos.x):
            self.touchdown()

    def ship_points(self):
        cos, sin = math.cos(self.angle), math.sin(self.angle)
        local = [(0, -16), (10, 10), (-10, 10)]
        return [
            (
                self.pos.x + x * cos - y * sin,
                self.pos.y + x * sin + y * cos,
            )
            for x, y in local
        ]

    def draw(self, screen):
        screen.fill((8, 8, 20))

        points = [(i * STEP, h) for i, h in enumerate(self.heights)]
        pygame.draw.polygon(
            screen,
            (70, 70, 85),
            points + [(WIDTH, HEIGHT), (0, HEIGHT)],
        )
        pygame.draw.lines(screen, (190, 190, 200), False, points, 2)

        for x1, x2, y, mult in self.pads:
            pygame.draw.line(
                screen, (90, 230, 120), (x1, y), (x2, y), 5
            )
            label = self.font.render(
                f"x{mult}", True, (90, 230, 120)
            )
            screen.blit(
                label,
                label.get_rect(midtop=((x1 + x2) / 2, y + 8)),
            )

        if self.state != "crashed":
            if self.thrusting:
                cos, sin = math.cos(self.angle), math.sin(self.angle)
                flame = [
                    (
                        self.pos.x - 5 * cos - 10 * sin,
                        self.pos.y - 5 * sin + 10 * cos,
                    ),
                    (
                        self.pos.x + 5 * cos - 10 * sin,
                        self.pos.y + 5 * sin + 10 * cos,
                    ),
                    (
                        self.pos.x - 22 * sin,
                        self.pos.y + 22 * cos,
                    ),
                ]
                pygame.draw.polygon(screen, (255, 170, 40), flame)

            color = ship_color(
                max(0.0, self.fuel) / FUEL_MAX
            ) or (230, 230, 240)
            pygame.draw.polygon(screen, color, self.ship_points())
        else:
            pygame.draw.circle(
                screen, (255, 120, 40), self.pos, 24, 3
            )

        draw_fireworks(screen)

        ok_x = abs(self.vel.x) <= MAX_SPEED_X
        ok_y = abs(self.vel.y) <= MAX_SPEED_Y
        ok_a = abs(wrap_angle(self.angle)) <= MAX_ANGLE

        good, bad = (120, 240, 140), (250, 110, 100)
        lines = [
            (f"Fuel {self.fuel:5.0f}", (240, 240, 240)),
            (f"Vx {self.vel.x:6.1f}", good if ok_x else bad),
            (f"Vy {self.vel.y:6.1f}", good if ok_y else bad),
            (
                f"Angle {math.degrees(wrap_angle(self.angle)):5.0f}",
                good if ok_a else bad,
            ),
            (
                f"Score {self.score}  Lives {self.lives}  Level {self.level}",
                (240, 240, 240),
            ),
        ]

        for i, (text, color) in enumerate(lines):
            screen.blit(
                self.font.render(text, True, color),
                (10, 8 + i * 22),
            )

        if self.message:
            label = self.font.render(
                self.message, True, (255, 255, 120)
            )
            screen.blit(
                label,
                label.get_rect(center=(WIDTH // 2, HEIGHT // 3)),
            )


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Lunar Lander")
    clock = pygame.time.Clock()

    game = Game()
    running = True

    while running:
        dt = min(clock.tick(60) / 1000, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    game.reset()
                elif event.key == pygame.K_SPACE and game.state == "landed":
                    game.level += 1
                    game.new_round()
                elif (
                    event.key == pygame.K_SPACE
                    and game.state == "crashed"
                    and game.lives > 0
                ):
                    game.new_round()

        game.update(dt, pygame.key.get_pressed())
        game.draw(screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
