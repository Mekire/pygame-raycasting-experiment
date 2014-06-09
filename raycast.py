import os
import sys
import math
import random
import pygame as pg

from collections import namedtuple


if sys.version_info[0] == 2:
    range = xrange


CAPTION = "Raytracing with Python"
SCREEN_SIZE = (1200, 600)
CIRCLE = 2*math.pi
SCALE = (SCREEN_SIZE[0]+SCREEN_SIZE[1])/1200.0
FIELD_OF_VIEW = math.pi*0.4
NO_WALL = float("inf")


RayInfo = namedtuple("RayInfo", ["sin", "cos", "range"])


class Image(object):
    def __init__(self, image):
        self.image = image
        self.rect = self.image.get_rect()
        self.width, self.height = self.rect.size


class Player(object):
    def __init__(self, x, y, direction):
        self.x = x
        self.y = y
        self.direction = direction
        self.speed = 3
        self.rotate_speed = CIRCLE/2  #180 degrees in a second.
        self.weapon = Image(KNIFE_IMAGE)
        self.paces = 0

    def rotate(self, angle):
        self.direction = (self.direction+angle+CIRCLE)%CIRCLE

    def walk(self, distance, game_map):
        dx = math.cos(self.direction)*distance
        dy = math.sin(self.direction)*distance
        if game_map.get(self.x+dx, self.y) <= 0:
            self.x += dx
        if game_map.get(self.x, self.y+dy) <= 0:
            self.y += dy
        self.paces += distance

    def update(self, keys, dt, game_map):
        if keys[pg.K_LEFT]:
            self.rotate(-self.rotate_speed*dt)
        if keys[pg.K_RIGHT]:
            self.rotate(self.rotate_speed*dt)
        if keys[pg.K_UP]:
            self.walk(self.speed*dt, game_map)
        if keys[pg.K_DOWN]:
            self.walk(-self.speed*dt, game_map)


class GameMap(object):
    def __init__(self, size):
        self.size = size
        self.wall_grid = self.randomize()
        self.sky_box = Image(SKY_BOX_IMAGE)
        self.wall_texture = Image(WALL_TEXTURE_IMAGE)
        self.light = 0

    def get(self, x, y):
        x = int(math.floor(x))
        y = int(math.floor(y))
        if x < 0 or x > self.size-1 or y < 0 or y > self.size-1:
            return -1
        return self.wall_grid[y*self.size+x]

    def randomize(self):
        return [1 if random.random()<0.3 else 0 for _ in range(self.size**2)]

    def cast(self, point, angle, cast_range):
        info = RayInfo(math.sin(angle), math.cos(angle), cast_range)
        return self.ray(info, Origin(point))

    def ray(self, info, origin):
        distance = origin.distance
        step_x = Step(info.sin, info.cos, origin.x, origin.y)
        step_y = Step(info.cos, info.sin, origin.y, origin.x, inverted=True)
        if step_x.length_sq < step_y.length_sq:
            next_step = self.inspect(info, step_x, 1, 0, distance, step_x.y)
        else:
            next_step = self.inspect(info, step_y, 0, 1, distance, step_y.x)
        if next_step.distance > info.range:
            return [origin]
        final = [origin]
        final.extend(self.ray(info, next_step))
        return final

    def inspect(self, info, step, shift_x, shift_y, distance, offset):
        dx = shift_x if info.cos<0 else 0
        dy = shift_y if info.sin<0 else 0
        step.height = self.get(step.x-dx, step.y-dy)
        step.distance = distance+math.sqrt(step.length_sq)
        if shift_x:
            step.shading = 2 if info.cos<0 else 0
        else:
            step.shading = 2 if info.sin<0 else 1
        step.offset = offset-math.floor(offset)
        return step

    def update(self, dt):
        if self.light > 0:
            self.light = max(self.light-10*dt, 0)
        elif random.random()*5 < dt:
            self.light = 2


class Origin(object):
    def __init__(self, point, height=0, distance=0):
        self.x = point[0]
        self.y = point[1]
        self.height = height
        self.distance = distance
        self.shading = None
        self.length_sq = None


class Step(object):
    def __init__(self, rise, run, x, y, inverted=False):
        self.shading = None
        self.distance = None
        try:
            dx = math.floor(x+1)-x if run > 0 else math.ceil(x-1)-x
            dy = dx*(rise/run)
            self.x = y+dy if inverted else x+dx
            self.y = x+dx if inverted else y+dy
            self.length_sq = dx**2+dy**2
        except ZeroDivisionError:
            self.x = self.y = None
            self.length_sq = NO_WALL


class Camera(object):
    def __init__(self, screen, resolution):
        self.screen = screen
        self.width, self.height = self.screen.get_size()
        self.resolution = float(resolution)
        self.spacing = self.width/resolution
        self.field_of_view = FIELD_OF_VIEW
        self.range = 10
        self.light_range = 5
        self.scale = (self.width+self.height)/1200.0

    def render(self, player, game_map):
        self.draw_sky(player.direction, game_map.sky_box)
        self.draw_columns(player, game_map)
        self.draw_weapon(player.weapon, player.paces)

    def draw_sky(self, direction, sky):
        left = -sky.width*direction/CIRCLE
        self.screen.blit(sky.image, (left,0))
        if left<sky.width-self.width:
            self.screen.blit(sky.image, (left+sky.width,0))

    def draw_columns(self, player, game_map):
        for column in range(int(self.resolution)):
            angle = self.field_of_view*(column/self.resolution-0.5)
            point = player.x, player.y
            ray = game_map.cast(point, player.direction+angle, self.range)
            self.draw_column(column, ray, angle, game_map)

    def draw_weapon(self, weapon, paces):
        bob_x = math.cos(paces*2)*self.scale*6
        bob_y = math.sin(paces*4)*self.scale*6
        left = self.width*0.66+bob_x
        top = self.height*0.6+bob_y
        self.screen.blit(weapon.image, (left, top))

    def draw_column(self, column, ray, angle, game_map):
        texture = game_map.wall_texture
        left = int(math.floor(column*self.spacing))
        width = int(math.ceil(self.spacing))
        hit = 0
        while hit < len(ray) and ray[hit].height <= 0:
            hit += 1
        for s in range(len(ray)-1, -1, -1):
            step = ray[s]
            rain_drops = int(random.random()**3*s)
            rain = rain_drops>0 and self.project(0.1, angle, step.distance)
            if s == hit:
                texture_x = int(math.floor(texture.width*step.offset))
                wall = self.project(step.height, angle, step.distance)
                image_location = pg.Rect(texture_x, 0, 1, texture.height)
                image_slice = texture.image.subsurface(image_location)
                scale = (width, wall[1])
                scaled = pg.transform.smoothscale(image_slice, scale)
                self.screen.blit(scaled, (left, wall[0]))
                shade_value = step.distance+step.shading
                max_light = shade_value/float(self.light_range-game_map.light)
                alpha = 255*min(1, max(max_light, 0))
                light_rect = pg.Rect(left, wall[0], width, wall[1])
                shade_slice = pg.Surface(light_rect.size).convert_alpha()
                shade_slice.fill((0,0,0,alpha))
                self.screen.blit(shade_slice, light_rect)
            for drop in range(rain_drops):
                drop = pg.Surface((1,rain[1])).convert_alpha()
                drop.fill((255,255,255,255*0.15))
                self.screen.blit(drop, (left, random.random()*rain[0]))

    def project(self, height, angle, distance):
        z = distance*math.cos(angle)
        wall_height = self.height*height/float(z)
        bottom = self.height/float(2)*(1+1/float(z))
        return (bottom-wall_height, int(wall_height))


class Control(object):
    def __init__(self):
        self.screen = pg.display.get_surface()
        self.clock = pg.time.Clock()
        self.fps = 60.0
        self.keys = pg.key.get_pressed()
        self.done = False
        self.player = Player(15.3, -1.2, math.pi*0.3)
        self.game_map = GameMap(32)
        self.camera = Camera(self.screen, 300)

    def event_loop(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.done = True
            elif event.type in (pg.KEYDOWN, pg.KEYUP):
                self.keys = pg.key.get_pressed()

    def main_loop(self):
        dt = self.clock.tick(self.fps)/1000.0
        while not self.done:
            self.event_loop()
            self.game_map.update(dt)
            self.player.update(self.keys, dt, self.game_map)
            self.camera.render(self.player, self.game_map)
            dt = self.clock.tick(self.fps)/1000.0
            pg.display.update()
            fps = self.clock.get_fps()
            pg.display.set_caption("{}: FPS - {:.2f}".format(CAPTION, fps))


def load_resources():
    global KNIFE_IMAGE, WALL_TEXTURE_IMAGE, SKY_BOX_IMAGE
    KNIFE_IMAGE = pg.image.load("knife_hand.png").convert_alpha()
    knife_w, knife_h = KNIFE_IMAGE.get_size()
    knife_scale = (int(knife_w*SCALE), int(knife_h*SCALE))
    KNIFE_IMAGE = pg.transform.smoothscale(KNIFE_IMAGE, knife_scale)
    WALL_TEXTURE_IMAGE = pg.image.load("wall_texture.jpg").convert()
    _SKY_SIZE = int(SCREEN_SIZE[0]*(CIRCLE/FIELD_OF_VIEW)), SCREEN_SIZE[1]
    SKY_BOX_IMAGE = pg.image.load("deathvalley_panorama.jpg").convert()
    SKY_BOX_IMAGE = pg.transform.smoothscale(SKY_BOX_IMAGE, _SKY_SIZE)


def main():
    global KNIFE_IMAGE, WALL_TEXTURE_IMAGE, SKY_BOX_IMAGE
    os.environ["SDL_VIDEO_CENTERED"] = "True"
    pg.init()
    screen = pg.display.set_mode(SCREEN_SIZE)
    load_resources()
    Control().main_loop()
    pg.quit()
    sys.exit()


if __name__ == "__main__":
    main()







