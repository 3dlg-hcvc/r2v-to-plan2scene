import logging

import numpy as np

from r2vstk.constants import WALL_LINKAGE_SKETCH_HOLE_HIGHLIGHT_WIDTH, WALL_LINKAGE_SKETCH_THICK_HOLE_WIDTH, WALL_LINKAGE_SKETCH_HOLE_WIDTH, \
    WALL_LINKAGE_SKETCH_WALL_WIDTH
from r2vstk.util import manhattan_distance_between, find_closest
from r2vstk.id_gen import generate_hole_id
import numbers


class Corner:
    """
    A corner of a line segment
    """

    def __init__(self, pos):
        assert isinstance(pos, tuple)
        self._pos = pos
        self._adj = []

    def __hash__(self):
        return hash(str(self))

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return str(self._pos[0]) + "_" + str(self._pos[1])

    @property
    def adj(self):
        return self._adj

    @property
    def pos(self):
        return self._pos

    @pos.setter
    def pos(self, value):
        assert isinstance(value, tuple)
        self._pos = value


class Hole:
    """
    A hole line segment indicated on the floorplan
    """

    def __init__(self, min_x, max_x):
        assert isinstance(min_x, numbers.Number)
        assert isinstance(max_x, numbers.Number)

        self._min_x = min_x
        self._max_x = max_x
        self._type = None
        self._id = generate_hole_id()

    @property
    def id(self) -> str:
        return self._id

    @property
    def type(self) -> str:
        return self._type

    @type.setter
    def type(self, value: str):
        isinstance(value, str)
        self._type = value

    @property
    def min_x(self) -> float:
        return self._min_x

    @property
    def max_x(self) -> float:
        return self._max_x

    @min_x.setter
    def min_x(self, value: float):
        assert isinstance(value, float)
        self._min_x = value

    @max_x.setter
    def max_x(self, value: float):
        assert isinstance(value, float)
        self._max_x = value

    def __hash__(self):
        return hash(str(self))

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "[" + str(self._min_x) + ":" + str(self._max_x) + "]"


class LineSegment:
    """
    A line segment
    """

    def __init__(self, p1: Corner, p2: Corner):
        assert isinstance(p1, Corner)
        assert isinstance(p2, Corner)
        self._p1 = p1
        self._p2 = p2

    @property
    def p1(self):
        return self._p1

    @p1.setter
    def p1(self, value):
        assert isinstance(value, Corner)
        self._p1 = value

    @property
    def p2(self):
        return self._p2

    @p2.setter
    def p2(self, value):
        assert isinstance(value, Corner)
        self._p2 = value

    def __hash__(self):
        return hash(str(self))

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "<" + str(self.p1) + ":" + str(self.p2) + ">"


class Wall(LineSegment):
    """
    Wall line segment indicated in the floorplan
    """

    def __init__(self, p1: Corner, p2: Corner, left_room_type=None, right_room_type=None):
        super().__init__(p1, p2)
        self.holes = []
        self.left_room_type = left_room_type
        self.right_room_type = right_room_type
        self._id = None

    @property
    def id(self) -> str:
        return self._id

    @id.setter
    def id(self, value):
        assert isinstance(value, str)
        self._id = value


class AABBAnnotation:
    """
    Object AABB indicated in the floorplan
    """

    def __init__(self, type=None):
        self._type = type
        self._p1 = None
        self._p2 = None

    @property
    def p1(self) -> tuple:
        return self._p1

    @property
    def p2(self) -> tuple:
        return self._p2

    @p1.setter
    def p1(self, value: tuple):
        assert isinstance(value, tuple) and len(value) == 2
        self._p1 = value

    @p2.setter
    def p2(self, value: tuple):
        assert isinstance(value, tuple) and len(value) == 2
        self._p2 = value

    @property
    def type(self):
        return self._type

    def __hash__(self):
        return hash(str(self))

    def __repr__(self):
        return self.type + " <(" + str(self.p1[0]) + ", " + str(self.p1[1]) + ") : (" + str(self.p2[0]) + ", " + str(
            self.p2[1]) + ")>"

    def __eq__(self, other):
        return self.p1 == other.p1 and self.p2 == other.p2 and self.type == other.type


class WallLinkageGraph:
    """
    Represents connectivity among wall line segments of a floor plan as a graph.
    """

    def __init__(self, tolerance_distance: float):
        assert isinstance(tolerance_distance, float)
        self._wall_corners = {}
        self._tolerance_distance = tolerance_distance
        self._walls = []

    @property
    def tolerance_distance(self) -> float:
        return self._tolerance_distance

    @property
    def wall_corners(self) -> dict:
        return self._wall_corners

    @property
    def walls(self) -> list:
        return self._walls

    def add_wall(self, p1, p2, left_room_type=None, right_room_type=None):
        #         if str(p1[0]) + "_" + str(p1[1]) in self.nodes:

        if p1[0] == p2[0] and p1[1] == p2[1]:
            logging.info("Not adding wall (%d, %d) : (%d, %d)" % (p1[0], p1[1], p2[0], p2[1]))
            return

        n1, n1_backup = find_closest(p1, self.wall_corners, self.tolerance_distance, [])
        if n1 is None:
            n1 = Corner(p1)
            self.wall_corners[str(p1[0]) + "_" + str(p1[1])] = n1

        n2, n2_backup = find_closest(p2, self.wall_corners, self.tolerance_distance, [])
        if n2 is None:
            n2 = Corner(p2)
            self.wall_corners[str(p2[0]) + "_" + str(p2[1])] = n2

        if n1 == n2:
            # We have a rare scenario where both p1 and p2 are closest to the same node.
            # Now, tie break using the second closest
            if manhattan_distance_between(n1.pos, p1) < manhattan_distance_between(n1.pos, p2):
                n2 = n2_backup
            else:
                n1 = n1_backup

        # In case a second closest does not exist
        if n1 is None:
            n1 = Corner(p1)
            self.wall_corners[str(p1[0]) + "_" + str(p1[1])] = n1

        if n2 is None:
            n2 = Corner(p2)
            self.wall_corners[str(p2[0]) + "_" + str(p2[1])] = n2

        assert not (n1.pos[0] == n2.pos[0] and n1.pos[1] == n2.pos[1])

        wall = Wall(n1, n2, left_room_type=left_room_type, right_room_type=right_room_type)
        self.walls.append(wall)
        n1.adj.append(wall)
        n2.adj.append(wall)

    def sketch(self, draw, fill, hole_color, window_color, door_color, selection=None, selection_fill=None, offset=(0, 0)):
        """
        Sketch wall linkage graph.
        """
        offset_x = offset[0]
        offset_y = offset[1]

        highlights = []
        if selection is not None:
            if isinstance(selection, Corner):
                highlights.extend(selection.adj)
            elif isinstance(selection, set) or isinstance(selection, frozenset):
                for sel in selection:
                    if isinstance(sel, Wall):
                        highlights.append(sel)
                    elif isinstance(sel, Corner):
                        highlights.extend(selection.adj)

        for wall in self.walls:
            if wall in highlights:
                draw.line((offset_x + wall.p1.pos[0], offset_y + wall.p1.pos[1], offset_x + wall.p2.pos[0], offset_y + wall.p2.pos[1]), fill=selection_fill,
                          width=WALL_LINKAGE_SKETCH_WALL_WIDTH)

                wall_start_point = np.array(wall.p1.pos)
                wall_direction = np.array(wall.p2.pos) - np.array(wall.p1.pos)
                wall_direction = wall_direction / np.linalg.norm(wall_direction)
                for hole in wall.holes:
                    hole_start_point = wall_start_point + wall_direction * hole.min_x
                    hole_end_point = wall_start_point + wall_direction * hole.max_x
                    draw.line((offset_x + np.asscalar(hole_start_point[0]), offset_y + np.asscalar(hole_start_point[1]),
                               offset_x + np.asscalar(hole_end_point[0]), offset_y + np.asscalar(hole_end_point[1])), fill=selection_fill,
                              width=WALL_LINKAGE_SKETCH_HOLE_HIGHLIGHT_WIDTH)
                    h_color = hole_color
                    if hole.type == "door":
                        h_color = door_color
                    elif hole.type == "window":
                        h_color = window_color
                    draw.line((offset_x + np.asscalar(hole_start_point[0]), offset_y + np.asscalar(hole_start_point[1]),
                               offset_x + np.asscalar(hole_end_point[0]), offset_y + np.asscalar(hole_end_point[1])), fill=h_color,
                              width=WALL_LINKAGE_SKETCH_THICK_HOLE_WIDTH)

            else:
                draw.line((offset_x + wall.p1.pos[0], offset_y + wall.p1.pos[1], offset_x + wall.p2.pos[0], offset_y + wall.p2.pos[1]), fill=fill,
                          width=WALL_LINKAGE_SKETCH_WALL_WIDTH)

                wall_start_point = np.array(wall.p1.pos)
                wall_direction = np.array(wall.p2.pos) - np.array(wall.p1.pos)
                wall_direction = wall_direction / np.linalg.norm(wall_direction)
                for hole in wall.holes:
                    hole_start_point = wall_start_point + wall_direction * hole.min_x
                    hole_end_point = wall_start_point + wall_direction * hole.max_x
                    h_color = hole_color
                    if hole.type == "door":
                        h_color = door_color
                    elif hole.type == "window":
                        h_color = window_color

                    draw.line((offset_x + np.asscalar(hole_start_point[0]), offset_y + np.asscalar(hole_start_point[1]),
                               offset_x + np.asscalar(hole_end_point[0]), offset_y + np.asscalar(hole_end_point[1])), fill=h_color,
                              width=WALL_LINKAGE_SKETCH_HOLE_WIDTH)
