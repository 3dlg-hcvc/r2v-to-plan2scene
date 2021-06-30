from random import Random
import hashlib

from r2vstk.constants import RAND_MAX

ran = Random()


def generate_hole_id() -> str:
    """
    Generate id for a hole.
    """
    return "hole_" + str(ran.randint(0, RAND_MAX))


def generate_room_id(room_key, ordered_rooms):
    """
    Generate id for a room.
    """
    hash_object = hashlib.md5(str(room_key).encode("utf-8"))
    return "room_" + str(ordered_rooms.index(room_key)) + "_" + hash_object.hexdigest()


def generate_wall_id(room_id, wall):
    """
    Generate id for a wall.
    """
    if wall.id is not None:
        return wall.id
    wall.id = room_id + "_wall" + str(ran.randint(0, RAND_MAX))
    return wall.id
