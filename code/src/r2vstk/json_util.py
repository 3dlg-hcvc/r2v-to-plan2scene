import json
import logging
import copy

from r2vstk.config_manager import ConfigManager
from r2vstk.floorplan import Wall
from r2vstk.id_gen import generate_wall_id
import math

log = logging.getLogger(__name__)


def generate_wall_json(conf: ConfigManager, wall: Wall, room_id: str,  multiplication_factor: float, should_swap_wall_endpoints: bool,
                       is_short_walled: bool = False) -> dict:
    """
    Generate a json describing a wall.
    :param conf: ConfigManager
    :param wall: Described wall
    :param room_id: Room id
    :param room_wall_ids: Dictionary mapping from room_id -> wall -> wall_id
    :param multiplication_factor: Scale factor to real world units
    :param should_swap_wall_endpoints: Should the endpoints of the wall swap.
    :param is_short_walled: Specify true to make the wall short.
    :return: Wall json
    """
    hole_jsons = []
    old_wall_width = math.sqrt((wall.p2.pos[1] - wall.p1.pos[1]) ** 2 + (wall.p2.pos[0] - wall.p1.pos[0]) ** 2)
    new_wall_width = math.sqrt(((wall.p2.pos[1] * multiplication_factor) - (wall.p1.pos[1] * multiplication_factor)) ** 2 +
                               ((wall.p2.pos[0] * multiplication_factor) - (wall.p1.pos[0] * multiplication_factor)) ** 2)

    wall_p1 = wall.p1
    wall_p2 = wall.p2

    if should_swap_wall_endpoints:
        wall_p1, wall_p2 = wall_p2, wall_p1

    for hole in wall.holes:
        hole_minx = hole.min_x
        hole_maxx = hole.max_x
        if should_swap_wall_endpoints:
            hole_minx, hole_maxx = old_wall_width - hole_maxx, old_wall_width - hole_minx

        hole_type = None
        # Load defaults since we do not have a model
        min_y = conf.arch_defaults.door_min_y
        max_y = conf.arch_defaults.door_max_y

        if hole.type == "door":
            hole_type = "Door"
            min_y = conf.arch_defaults.door_min_y
            max_y = conf.arch_defaults.door_max_y
        elif hole.type == "window":
            hole_type = "Window"
            min_y = conf.arch_defaults.window_min_y
            max_y = conf.arch_defaults.window_max_y

        hole_json = {
            "id": hole.id,  # Node id of object creating hole in the wall
            "type": hole_type,  # hole type (`Door` or `Window`)
            "box": {  # cutout of hole as box on the wall
                "min": [(hole_minx / old_wall_width * new_wall_width), min_y],  # minimum point
                # x is distance from points[0] (toward points[1])
                # y is height from wall bottom (goes from 0 to wall height)
                "max": [(hole_maxx / old_wall_width * new_wall_width), max_y]  # maximum point
            }
        }
        hole_jsons.append(hole_json)

    wall_json = {
        "roomId": [room_id],
        "id": generate_wall_id(room_id, wall),
        "type": "Wall",
        "points": [[(wall_p1.pos[0] * multiplication_factor), 0.0, (wall_p1.pos[1] * multiplication_factor)],
                   [(wall_p2.pos[0] * multiplication_factor), 0.0, (wall_p2.pos[1] * multiplication_factor)]],
        "holes": hole_jsons,
        "height": conf.arch_defaults.wall_height if not is_short_walled else conf.arch_defaults.short_wall_height,
        "materials": copy.deepcopy(conf.arch_defaults.wall_materials),
        "depth": conf.arch_defaults.wall_depth,
        "extra_height": conf.arch_defaults.wall_extra_height
    }
    return wall_json


def generate_ceiling_json(conf: ConfigManager, polyline, room_id: str, multiplication_factor: float) -> dict:
    """
    Generate a json describing a ceiling.
    :param conf: ConfigManager
    :param polyline: Outline of the room
    :param room_id: id of the room
    :param multiplication_factor: Scale factor to real-world
    :return: Json description of the ceiling
    """
    r = {
        "id": room_id + "_c",
        "roomId": room_id,
        "points": [[[(p[0] * multiplication_factor), 0.0, (p[1] * multiplication_factor)] for p in polyline]],
        "type": "Ceiling",
        "materials": conf.arch_defaults.ceiling_materials[:],
        "offset": [0.0, conf.arch_defaults.wall_height, 0.0],
        "depth": conf.arch_defaults.ceiling_depth
    }
    return r


def generate_floor_json(conf: ConfigManager, polyline, room_id:str, multiplication_factor:float):
    """
    Generate a json describing the floor surface
    :param conf: ConfigManager
    :param polyline: Outline of the room
    :param room_id: id of the room
    :param multiplication_factor: Scale factor to real-world
    :return: Json description of the floor.
    """
    r = {
        "id": room_id + "_f",
        "roomId": room_id,
        "points": [[[(p[0] * multiplication_factor), 0.0, (p[1] * multiplication_factor)] for p in polyline]],
        "type": "Floor",
        "materials": conf.arch_defaults.floor_materials[:],
        "depth": conf.arch_defaults.floor_depth
    }
    return r
