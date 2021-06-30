from r2vstk.config_manager import ConfigManager
from r2vstk.constants import RAW_SKETCH_MARGIN, RAW_WALL_COLOR, RAW_ENTRANCE_COLOR, RAW_LABEL_COLOR, RAW_STAIR_COLOR, RAW_OBJECT_COLOR, RAW_DOOR_COLOR, \
    ROOM_SKETCH_MARGIN, ROOM_SKETCH_WALL_COLOR, ROOM_SKETCH_HOLE_COLOR, ROOM_SKETCH_WINDOW_COLOR, ROOM_SKETCH_DOOR_COLOR, ROOM_SKETCH_ROOM_ANNOTATION_COLOR, \
    ROOM_SKETCH_ROOM_ANNOTATION_LABEL_COLOR, ROOM_SKETCH_SELECTED_ROOM_COLOR, ROOM_SKETCH_DOOR_CONNECTED_ADJACENT_ROOM_COLOR

from r2vstk.id_gen import generate_room_id
from r2vstk.json_util import generate_ceiling_json, generate_floor_json, generate_wall_json
from r2vstk.room_description import RoomDescription
from r2vstk.util import find_room, line_contains_check, get_closest_and_furthest, manhattan_distance_between, \
    get_polyline, sq_distance, convert_int, rect_line_distance, hole_to_line
import math
import csv
from r2vstk.exceptions import StraightenWallsFailed

from PIL import Image, ImageDraw
from PIL import ImageFont
from shapely.geometry import Polygon, LineString
from r2vstk.floorplan import WallLinkageGraph, Corner, Hole, AABBAnnotation, LineSegment
import logging
import os.path as osp
from r2vstk.wall_split_utils import find_connections


class House:
    """
    In memory representation of a floorplan and associated configuration
    """

    def __init__(self):
        # Configuration
        self.file_name = None
        self.multiplication_factor = 1  # Scale factor to real world

        # Parsed raw data
        self.raw_room_annotations = []
        self.walls = []
        self.raw_objects = []
        self.openings = []
        self.entrances = []
        self.stairs = []

        self.wall_graph = None  # Wall-corner-wall linkage graph. This is used to identify rooms as polygons.

        # Bounds
        self.x_min = None
        self.y_min = None
        self.x_max = None
        self.y_max = None

        # High level annotations
        self.ordered_rooms = None  # Room keys in a fixed order used for indexing
        self.room_description_map = {}  # Mapping from room_key -> RoomDescription
        self.object_annotations = []  # AABBs of objects

        self.rdr = []  # Room door room edges

    def _load_data(self, data) -> None:
        """
        Load a parsed r2v file.
        :param data: Parsed R2V tsv file.
        """
        self.walls = [x for x in data if x["category"] == "wall"]
        self.raw_objects = [r for r in data if r["category"] not in ["wall", "door", "entrance"]]
        self.openings = [x for x in data if x["category"] == "door"]

        self.entrances = [x for x in data if x["category"] == "entrance"]
        self.stairs = [x for x in data if x["category"] == "stairs"]

        self.raw_room_annotations = [a for a in data if a["category"] not in ["wall", "door"]]

        self.x_min = min([x["x_min"] for x in data] + [x["x_max"] for x in data])
        self.y_min = min([x["y_min"] for x in data] + [x["y_max"] for x in data])
        self.x_max = max([x["x_min"] for x in data] + [x["x_max"] for x in data])
        self.y_max = max([x["y_min"] for x in data] + [x["y_max"] for x in data])

    def load_r2v_output_file(self, conf: ConfigManager, source_path: str) -> None:
        """
        Load a raster-to-vector output file.
        :param conf: Config Manager
        :param source_path: Path to r2v file.
        """
        category_list = conf.room_types
        data = []
        self.file_name = source_path
        wall_count = -1
        with open(source_path) as tsvfile:
            tsvreader = csv.reader(tsvfile, delimiter="\t")
            for i, line in enumerate(tsvreader):
                if i == 0:
                    continue  # We dont need width and height
                if i == 1:
                    wall_count = convert_int(line[0])
                    continue
                if i < wall_count + 2:
                    assert len(line) == 6
                    datum = {
                        "x_min": convert_int(line[0]),
                        "y_min": convert_int(line[1]),
                        "x_max": convert_int(line[2]),
                        "y_max": convert_int(line[3]),
                        "category": "wall",
                        "left_room_type": category_list[convert_int(line[4])],
                        "right_room_type": category_list[convert_int(line[5])]
                    }
                else:
                    assert len(line) == 7
                    datum = {
                        "x_min": convert_int(line[0]),
                        "y_min": convert_int(line[1]),
                        "x_max": convert_int(line[2]),
                        "y_max": convert_int(line[3]),
                        "category": line[4],
                        "dump_1": line[5],
                        "dump_2": line[6]
                    }
                data.append(datum)
        self._load_data(data)

    def load_r2v_annot_file(self, source_path: str):
        """
        Load a raster-to-vector annotation file.
        :param source_path: Path to raster-to-vector annotation file.
        """
        data = []
        self.file_name = source_path

        with open(source_path) as tsvfile:
            tsvreader = csv.reader(tsvfile, delimiter="\t")
            for line in tsvreader:
                datum = {
                    "x_min": convert_int(line[0]),
                    "y_min": convert_int(line[1]),
                    "x_max": convert_int(line[2]),
                    "y_max": convert_int(line[3]),
                    "category": line[4],
                    "dump_1": line[5],
                    "dump_2": line[6]
                }
                data.append(datum)
        self._load_data(data)

    def split_source_walls(self, conf: ConfigManager) -> None:
        """
        Split walls that intersect with other walls into separate wall segments.
        :param conf: ConfigManager
        """
        # Method adapted from raster-to-vector project.
        start_over = False
        changed = True
        left_iterations = conf.parser_config.split_walls.max_iter
        while changed and left_iterations > 0:
            left_iterations -= 1
            changed = False
            for i1, wall1 in enumerate(self.walls):
                if start_over:
                    start_over = False
                    break

                # Only apply for manhattan walls
                if wall1["x_min"] == wall1["x_max"] or wall1["y_min"] == wall1["y_max"]:
                    pass
                else:
                    continue

                for i2, wall2 in enumerate(self.walls):
                    # Only apply for manhattan walls
                    if wall2["x_min"] == wall2["x_max"] or wall2["y_min"] == wall2["y_max"]:
                        pass
                    else:
                        continue

                    if wall1 == wall2:
                        continue
                    t, p = find_connections(((wall1["x_min"], wall1["y_min"]), (wall1["x_max"], wall1["y_max"])),
                                            ((wall2["x_min"], wall2["y_min"]), (wall2["x_max"], wall2["y_max"])),
                                            conf.parser_config.wall_join_margin)

                    to_break = None
                    other = None
                    to_break_i = None
                    if t[0] == 2:
                        to_break = wall1
                        to_break_i = i1
                        other = wall2
                        logging.info("Break " + str(wall1))
                    elif t[1] == 2:
                        to_break = wall2
                        to_break_i = i2
                        other = wall1
                        logging.info("Break " + str(wall2))

                    if to_break is not None:
                        seg1 = {
                            "x_min": to_break["x_min"],
                            "y_min": to_break["y_min"],
                            "x_max": p[0],
                            "y_max": p[1],
                            "category": "wall"
                        }
                        seg2 = {
                            "x_min": p[0],
                            "y_min": p[1],
                            "x_max": to_break["x_max"],
                            "y_max": to_break["y_max"],
                            "category": "wall"
                        }
                        if "left_room_type" in to_break:
                            seg1["left_room_type"] = to_break["left_room_type"]
                            seg2["left_room_type"] = to_break["left_room_type"]

                        if "right_room_type" in to_break:
                            seg1["right_room_type"] = to_break["right_room_type"]
                            seg2["right_room_type"] = to_break["right_room_type"]

                        if "dump1" in to_break:
                            seg1["dump1"] = to_break["dump1"]
                            seg2["dump1"] = to_break["dump1"]

                        if "dump2" in to_break:
                            seg1["dump2"] = to_break["dump2"]
                            seg2["dump2"] = to_break["dump2"]

                        del self.walls[to_break_i]
                        self.walls.append(seg1)
                        self.walls.append(seg2)
                        start_over = True
                        changed = True
                        break
        if left_iterations == 0:
            logging.warning("Split walls iterations truncated: " + str(self.file_name))

    def _find_adjacent_rooms(self, wall):
        """
        Find adjacent rooms of to a wall.
        :return: List of adjacent rooms
        """
        adjacent_rooms = []
        for room_key in self.room_description_map:
            if wall in room_key:
                adjacent_rooms.append(room_key)
        return adjacent_rooms

    def compute_rdr(self) -> None:
        """
        Computer room-door-room connectivity graph
        """
        for wall in self.wall_graph.walls:
            for hole in wall.holes:
                assert isinstance(hole, Hole)
                if hole.type == "door":
                    # Find rdr connectivity for this door
                    adjacent_rooms_keys = self._find_adjacent_rooms(wall)
                    if len(adjacent_rooms_keys) == 0:
                        pass
                    elif len(adjacent_rooms_keys) == 1:
                        self.rdr.append((adjacent_rooms_keys[0], hole, None))
                    elif len(adjacent_rooms_keys) == 2:
                        self.rdr.append((adjacent_rooms_keys[0], hole, adjacent_rooms_keys[1]))
                        self.rdr.append((adjacent_rooms_keys[1], hole, adjacent_rooms_keys[0]))

    def classify_doors_and_windows(self) -> None:
        """
        Classify openings as doors and windows.
        """
        for wall in self.wall_graph.walls:
            # Check whether wall is internal
            wall_internal = False
            adjacent_rooms_keys = []
            for room_key in self.room_description_map:
                if wall in list(room_key):
                    adjacent_rooms_keys.append(room_key)
            assert len(adjacent_rooms_keys) <= 2
            if len(adjacent_rooms_keys) == 2:
                wall_internal = True
            if wall_internal:
                # If wall is internal, all opennings of it must be doors
                for hole in wall.holes:
                    hole.type = "door"

        for room_key, rd in self.room_description_map.items():
            annotations = rd.annotations
            for annotation in annotations:
                if annotation.type == "entrance":
                    # The closest exterior hole to entrance must be a door
                    closest_hole = None
                    closest_hole_distance = 10000000000000000
                    for wall in self.room_description_map[room_key].walls:
                        for hole in wall.holes:
                            if hole.type is None:
                                hole_line = hole_to_line(wall.p1.pos, wall.p2.pos, hole.min_x, hole.max_x)
                                hole_rect_dist = rect_line_distance(annotation.p1, annotation.p2, hole_line[0], hole_line[1])
                                if hole_rect_dist < closest_hole_distance:
                                    closest_hole_distance = hole_rect_dist
                                    closest_hole = hole

                    # assert closest_hole is not None # Assertion removed due to duplicate entrance annotation
                    if closest_hole is not None:
                        closest_hole.type = "door"
                    # print(closest_hole)

        # Any remaining holes are windows
        for wall in self.wall_graph.walls:
            for hole in wall.holes:
                if hole.type is None:
                    hole.type = "window"

    def straighten_walls(self, conf: ConfigManager) -> None:
        """
        Axis-align walls that are nearly axis aligned.
        :param conf: Config Manager
        """

        straighten_walls_cutoff_gradient = conf.parser_config.straighten_walls.cutoff_gradient
        max_iter_count = conf.parser_config.straighten_walls.max_iter
        iter_count = 0
        while iter_count < max_iter_count:
            try:
                found_wall = None
                for wall in self.wall_graph.walls:
                    if 0 < abs(wall.p1.pos[0] - wall.p2.pos[0]) / sq_distance(wall.p1.pos, wall.p2.pos) < straighten_walls_cutoff_gradient:
                        found_wall = wall
                        logging.info("Inclined Wall " + str(wall) + " : " + str(abs(wall.p1.pos[0] - wall.p2.pos[0]) / sq_distance(wall.p1.pos, wall.p2.pos)))
                        break

                    if 0 < abs(wall.p1.pos[1] - wall.p2.pos[1]) / sq_distance(wall.p1.pos, wall.p2.pos) < straighten_walls_cutoff_gradient:
                        found_wall = wall
                        logging.info("Inclined Wall " + str(wall) + " : " + str(abs(wall.p1.pos[1] - wall.p2.pos[1]) / sq_distance(wall.p1.pos, wall.p2.pos)))
                        break
                if found_wall is None:
                    break
                else:
                    found_key = str(found_wall)
                    moved_point_key = None
                    move_point = None
                    if 0 < abs(found_wall.p1.pos[0] - found_wall.p2.pos[0]) / sq_distance(found_wall.p1.pos,
                                                                                          found_wall.p2.pos) < straighten_walls_cutoff_gradient:
                        # This is a x axis correction. Move the top vertex
                        if found_wall.p1.pos[1] < found_wall.p2.pos[1]:
                            moved_point_key = str(found_wall.p1)
                            move_point = found_wall.p1
                            found_wall.p1.pos = (found_wall.p2.pos[0], found_wall.p1.pos[1])
                        else:
                            moved_point_key = str(found_wall.p2)
                            move_point = found_wall.p2
                            found_wall.p2.pos = (found_wall.p1.pos[0], found_wall.p2.pos[1])
                    else:
                        # This is a y axis correction. Move the left vertex
                        if found_wall.p1.pos[0] < found_wall.p2.pos[0]:
                            moved_point_key = str(found_wall.p1)
                            move_point = found_wall.p1
                            found_wall.p1.pos = (found_wall.p1.pos[0], found_wall.p2.pos[1])
                        else:
                            moved_point_key = str(found_wall.p2)
                            move_point = found_wall.p2
                            found_wall.p2.pos = (found_wall.p2.pos[0], found_wall.p1.pos[1])

                    del self.wall_graph.wall_corners[moved_point_key]
                    self.wall_graph.wall_corners[str(move_point)] = move_point
                iter_count += 1
            except Exception as e:
                raise StraightenWallsFailed(house_path=self.file_name, iter_count=iter_count) from e
        else:
            logging.warning("Straighten wall max iterations exceeded: " + self.file_name)

    def _eliminate_false_rooms(self, conf: ConfigManager) -> None:
        """
        The room detection algorithm erroneously detect the outer perimeter as a room. This method removes that 'false' room.
        :param conf: ConfigManager
        """
        eliminate_false_rooms_threshold = conf.parser_config.eliminate_false_rooms.threshold
        fully_contained_keys = []
        for parent_candidate_key in self.room_description_map:
            contained_children = []
            parent_polyline = get_polyline(self.room_description_map[parent_candidate_key].walls)
            if len(parent_polyline) < 3:
                continue
            try:
                parent_polygon = Polygon(parent_polyline)
            except:
                logging.error("exception in processing " + self.file_name, exc_info=1)
                continue

            for child_candidate_key in self.room_description_map:
                if child_candidate_key == parent_candidate_key:
                    continue
                child_polyline = get_polyline(self.room_description_map[child_candidate_key].walls)
                if len(child_polyline) < 3:
                    continue
                try:
                    child_polygon = Polygon(child_polyline)
                except:
                    logging.error("exception in processing " + self.file_name, exc_info=1)
                    continue

                intersection = parent_polygon.intersection(child_polygon)
                if isinstance(intersection, Polygon):
                    if intersection.area > 0:
                        contained_children.append((child_candidate_key, child_polygon.area, child_polygon))

            total_area = sum([a[1] for a in contained_children])
            if abs(total_area - parent_polygon.area) < parent_polygon.area * eliminate_false_rooms_threshold:
                fully_contained_keys.append(parent_candidate_key)
                logging.info("Fully contained " + str(parent_candidate_key) + " : " + str(total_area))
        for fck in fully_contained_keys:
            del self.room_description_map[fck]

    def generate_wall_graph(self, conf: ConfigManager) -> None:
        """
        Generate wall-corner-wall linkage graph
        :param conf: Config Manager
        """
        self.wall_graph = WallLinkageGraph(conf.parser_config.wall_join_margin)
        for wall in self.walls:
            left_room_type = None
            if "left_room_type" in wall:
                left_room_type = wall["left_room_type"]
            right_room_type = None
            if "right_room_type" in wall:
                right_room_type = wall["right_room_type"]
            self.wall_graph.add_wall((wall["x_min"], wall["y_min"]), (wall["x_max"], wall["y_max"]), left_room_type=left_room_type,
                                     right_room_type=right_room_type)

        # Detect rooms
        self.room_description_map = {}
        for wall in self.wall_graph.walls:
            r1 = find_room(wall.p1, wall)
            room_key1 = frozenset(r1)
            self.room_description_map[room_key1] = RoomDescription(room_key1, r1)

            r2 = find_room(wall.p2, wall)
            room_key2 = frozenset(r2)
            self.room_description_map[room_key2] = RoomDescription(room_key2, r2)

        # Eliminate false rooms
        if conf.parser_config.eliminate_false_rooms.enabled:
            self._eliminate_false_rooms(conf)

        self.ordered_rooms = list(self.room_description_map.keys())

        # Add doors
        w_doors = [LineSegment(Corner((p["x_min"], p["y_min"])), Corner((p["x_max"], p["y_max"]))) for p in self.openings]

        wall_door_pairs = []
        for door in w_doors:
            for wall in self.wall_graph.walls:
                line_contains, pd = line_contains_check(wall, door, conf.parser_config.max_door_perpendicular_offset)
                if line_contains:
                    wall_door_pairs.append((pd, door, wall))

        wall_door_pairs = sorted(wall_door_pairs, key=lambda x: x[0])

        added_doors = []
        for pd, door, wall in wall_door_pairs:
            if door in added_doors:
                continue
            # Convert hole coordinates to wall space
            min_point, max_point = get_closest_and_furthest(wall.p1.pos, door.p1.pos, door.p2.pos)
            new_door = Hole(manhattan_distance_between(wall.p1.pos, min_point), manhattan_distance_between(wall.p1.pos, max_point))
            wall.holes.append(new_door)
            added_doors.append(door)

        for door in w_doors:
            if door not in added_doors:
                logging.warning("Door not added: " + str(door) + " : " + self.file_name)

    def populate_object_annotations(self, conf: ConfigManager) -> None:
        """
        Populate the list of object annotations
        :param conf: ConfigManager
        """
        self.object_annotations = []
        for ro in self.raw_objects:
            if ro["category"] in conf.room_types:
                continue
            obj = AABBAnnotation(ro["category"])
            obj.p1 = (ro["x_min"], ro["y_min"])
            obj.p2 = (ro["x_max"], ro["y_max"])
            self.object_annotations.append(obj)

    def get_wall_mask(self):
        """
        Returns the shapely shape containing walls. The windows and doors are depicted by holes. This mask can be used for 2D ray hit tests.
        """
        processed_walls = []
        all_lines = []
        for room_key in self.room_description_map:
            room_walls = self.room_description_map[room_key].walls
            for wall in room_walls:
                if wall in processed_walls:
                    continue

                wall_length = math.sqrt((wall.p2.pos[0] - wall.p1.pos[0]) ** 2 + (wall.p2.pos[1] - wall.p1.pos[1]) ** 2)

                ls = LineString([(wall.p1.pos[0], wall.p1.pos[1]), (wall.p2.pos[0], wall.p2.pos[1])]).buffer(1)

                for hole in wall.holes:
                    h_start_x = ((wall.p2.pos[0] - wall.p1.pos[0]) / wall_length * hole.min_x) + wall.p1.pos[0]
                    h_end_x = ((wall.p2.pos[0] - wall.p1.pos[0]) / wall_length * hole.max_x) + wall.p1.pos[0]
                    h_start_y = ((wall.p2.pos[1] - wall.p1.pos[1]) / wall_length * hole.min_x) + wall.p1.pos[1]
                    h_end_y = ((wall.p2.pos[1] - wall.p1.pos[1]) / wall_length * hole.max_x) + wall.p1.pos[1]

                    hs = LineString([(h_start_x, h_start_y), (h_end_x, h_end_y)]).buffer(1)
                    ls = ls.difference(hs)

                all_lines.append(ls)

        from shapely.ops import cascaded_union
        u = cascaded_union(all_lines)
        return u

    def populate_room_annotations(self, conf: ConfigManager) -> None:
        """
        Populate room_key -> annotations map that indicate AABB annotations assigned to each room.
        :param conf: ConfigManager
        """
        annotations = []
        for ro in self.raw_room_annotations:
            obj = AABBAnnotation(ro["category"])
            obj.p1 = (ro["x_min"], ro["y_min"])
            obj.p2 = (ro["x_max"], ro["y_max"])
            annotations.append(obj)

        for room_key in self.room_description_map:
            room_poly = Polygon(get_polyline(self.room_description_map[room_key].walls))
            for annotation in annotations:
                annotation_polygon = Polygon(
                    [(annotation.p1[0], annotation.p1[1]), (annotation.p2[0], annotation.p1[1]),
                     (annotation.p2[0], annotation.p2[1]), (annotation.p1[0], annotation.p2[1])])
                intersection = room_poly.intersection(annotation_polygon)
                if isinstance(intersection, Polygon):
                    if abs(intersection.area - annotation_polygon.area) < annotation_polygon.area * conf.parser_config.room_label_assignment_overlap:
                        self.room_description_map[room_key].annotations.append(annotation)

    def get_room_json(self, conf: ConfigManager, room_key, include_walls: bool, skip_walls: dict = None, adjust_short_walls=False) -> tuple:
        """
        Obtain a json describing a room.
        :param conf: ConfigManager
        :param room_key: Key of interested room
        :param include_walls: Specify true to include walls in the results
        :param skip_walls: Dictionary of walls that are already generated. These walls will be skipped.
        :param adjust_short_walls: Specify true to make certain walls short. (E.g. balconies)
        :return: Tuple of (An arch.json file describing the room, dictionary of newly added walls)
        """
        if skip_walls is None:
            skip_walls = {}

        added_walls = {}
        room_walls = self.room_description_map[room_key].walls
        room_id = self.room_description_map[room_key].room_id
        polyline = get_polyline(room_walls)

        # Detect balcony rooms
        is_short_walled = False
        if adjust_short_walls:
            for rt in self.room_description_map[room_key].room_types:
                if rt.type in conf.arch_defaults.short_wall_room_types:
                    is_short_walled = True
                    break

        ceiling = generate_ceiling_json(conf, polyline, room_id, self.multiplication_factor)

        floor = generate_floor_json(conf, polyline, room_id, self.multiplication_factor)
        elements = [ceiling, floor]
        if include_walls:
            for i_wall, wall in enumerate(room_walls):
                if wall not in skip_walls:
                    # Check whether wall direction is needed to be swapped
                    next_wall = room_walls[(i_wall + 1) % len(room_walls)]

                    next_wall_connection = None
                    if next_wall.p1 == wall.p1 or next_wall.p1 == wall.p2:
                        next_wall_connection = next_wall.p1
                    elif next_wall.p2 == wall.p1 or next_wall.p2 == wall.p2:
                        next_wall_connection = next_wall.p2
                    else:
                        assert False

                    if wall.p2 != next_wall_connection:
                        should_swap_wall_endpoints = True
                    else:
                        should_swap_wall_endpoints = False

                    wall_json = generate_wall_json(conf, wall, room_id, self.multiplication_factor,
                                                   should_swap_wall_endpoints=should_swap_wall_endpoints,
                                                   is_short_walled=is_short_walled)
                    elements.append(wall_json)
                    added_walls[wall] = wall_json
                else:
                    skip_walls[wall]["roomId"].append(room_id)

        result = {
            "version": conf.arch_defaults.version,  # // Version
            "id": osp.splitext(osp.dirname(self.file_name))[0] + "_room_" + str(self.ordered_rooms.index(room_key)),  # // Scene ID
            "up": conf.arch_defaults.up,  # // Up vector (same as in house file)
            "front": conf.arch_defaults.front,  # // Front vector (same as in house file)
            "scaleToMeters": conf.arch_defaults.scale_to_meters,
            # // What unit the architecture is specified in (same as in house file)
            "defaults": {  # // Default depth for wall, ceiling, floor, ground
                "Wall": {
                    "depth": conf.arch_defaults.wall_depth,
                    "extraHeight": conf.arch_defaults.wall_extra_height  # // This height is added to wall to ensure no gaps
                },
                "Ceiling": {
                    "depth": conf.arch_defaults.ceiling_depth
                },
                "Floor": {
                    "depth": conf.arch_defaults.floor_depth
                }
            },
            "elements": elements,
        }
        return result, added_walls

    def get_objectaabb_json(self, conf: ConfigManager) -> dict:
        """
        Generate jsons describing object aabbs.
        :param conf: Config Manager
        :return: objectaabb.json file.
        """
        result_objects = []
        for obj in self.object_annotations:
            result_objects.append({
                "type": obj.type,
                "bound_box": {
                    "p1": [
                        obj.p1[0] * self.multiplication_factor,
                        obj.p1[1] * self.multiplication_factor
                    ],
                    "p2": [
                        obj.p2[0] * self.multiplication_factor,
                        obj.p2[1] * self.multiplication_factor
                    ]
                }
            })
        return {
            "objects": result_objects,
        }

    def get_scene_json(self, conf: ConfigManager, adjust_short_walls: bool) -> dict:
        """
        Get a scene.json describing the house.
        :param conf: ConfigManager
        :param adjust_short_walls: Specify true to keep certain walls short (e.g. balconies)
        :return: Scene.json file
        """
        arch_json = self.get_arch_json(conf, adjust_short_walls=adjust_short_walls)
        filtered_arch_json = {"elements": arch_json["elements"], "defaults": arch_json["defaults"], "rooms": arch_json["rooms"], "rdr": arch_json["rdr"],
                              "id": arch_json["id"]}
        result = {
            "format": "sceneState",
            "scene": {
                "up": {"x": conf.arch_defaults.up[0], "y": conf.arch_defaults.up[1], "z": conf.arch_defaults.up[2]},  # // Up vector (same as in house file)
                "front": {"x": conf.arch_defaults.front[0], "y": conf.arch_defaults.front[1], "z": conf.arch_defaults.front[2]},
                # // Front vector (same as in house file)
                "unit": conf.arch_defaults.scale_to_meters,  # // What unit the architecture is specified in (same as in house file)
                "assetSource": conf.arch_defaults.asset_source,
                "arch": filtered_arch_json,
                "object": [],
                "assetTransforms": conf.arch_defaults.asset_transforms.as_dict(),
            },
            "selected": [],
        }
        return result

    def get_arch_json(self, conf: ConfigManager, adjust_short_walls):
        """
        Get an arch.json describing the house.
        :param conf: ConfigManager
        :param adjust_short_walls: Specify true to keep certain walls short (e.g. balconies)
        :return: arch.json file
        """
        elements = []
        skip_walls = {}  # Avoid duplicating of walls that are shared between multiple rooms.

        # Move the balcony to the last in room_keys so that it will only assigned with the external walls
        room_keys = list(self.room_description_map.keys())
        if adjust_short_walls:
            short_wall_list = []
            for i, k in enumerate(room_keys):
                for t in self.room_description_map[k].room_types:
                    if t.type in conf.arch_defaults.short_wall_room_types:
                        short_wall_list.append(k)
                        break
            for b in short_wall_list:
                room_keys.remove(b)
                room_keys.append(b)

        # Populate room description jsons
        room_description_jsons = []
        for room_key in room_keys:
            room_json, used_walls = self.get_room_json(conf, room_key, True, skip_walls, adjust_short_walls=adjust_short_walls)

            # Update skip walls
            for k, v in used_walls.items():
                assert k not in skip_walls
                skip_walls[k] = v
            # skip_walls.extend(used_walls)
            elements.extend(room_json["elements"])

            room_description = self.room_description_map[room_key]
            room_description_jsons.append({
                "id": room_description.room_id,
                "types": [a.type for a in room_description.room_types]
            })

        # Populate rdr jsons
        rdr_jsons = []
        for source_room_key, hole, target_room_key in self.rdr:
            target_room_id = None
            if target_room_key is not None:
                target_room_id = self.room_description_map[target_room_key].room_id

            rdr_jsons.append((self.room_description_map[source_room_key].room_id, hole.id, target_room_id))

        result = {
            "version": conf.arch_defaults.version,  # // Version
            "id": osp.splitext(osp.dirname(self.file_name))[0],  # // Scene ID
            "up": conf.arch_defaults.up,  # // Up vector (same as in house file)
            "front": conf.arch_defaults.front,  # // Front vector (same as in house file)
            "scaleToMeters": conf.arch_defaults.scale_to_meters,  # // What unit the architecture is specified in (same as in house file)
            "defaults": {  # // Default depth for wall, ceiling, floor, ground
                "Wall": {
                    "depth": conf.arch_defaults.wall_depth,
                    "extraHeight": conf.arch_defaults.wall_extra_height  # // This height is added to wall to ensure no gaps
                },
                "Ceiling": {
                    "depth": conf.arch_defaults.ceiling_depth
                },
                "Floor": {
                    "depth": conf.arch_defaults.floor_depth
                },
            },
            "elements": elements,
            "rooms": room_description_jsons,
            "rdr": rdr_jsons
        }
        return result

    def sketch_raw_annotations(self, conf: ConfigManager, path: str):
        """
        Sketch raw annotations loaded.
        :param conf: ConfigManager
        :param path: Path to save output sketch.
        """

        fnt = ImageFont.truetype(conf.data_paths.pil_font.path, conf.data_paths.pil_font.size)

        image = Image.new('RGB', (self.x_max - self.x_min + 2 * RAW_SKETCH_MARGIN, self.y_max - self.y_min + 2 * RAW_SKETCH_MARGIN))
        offset_x = -self.x_min + RAW_SKETCH_MARGIN
        offset_y = -self.y_min + RAW_SKETCH_MARGIN
        draw = ImageDraw.Draw(image)
        for wall in self.walls:
            draw.line((wall["x_min"] + offset_x, wall["y_min"] + offset_y, wall["x_max"] + offset_x, wall["y_max"] + offset_y), fill=RAW_WALL_COLOR)

        for entrance in self.entrances:
            draw.rectangle((entrance["x_min"] + offset_x, entrance["y_min"] + offset_y, entrance["x_max"] + offset_x, entrance["y_max"] + offset_y),
                           fill=RAW_ENTRANCE_COLOR)
            draw.text(
                (offset_x + (entrance["x_min"] + entrance["x_max"]) / 2, offset_y + (entrance["y_min"] + entrance["y_max"]) / 2),
                entrance["category"],
                font=fnt, fill=RAW_LABEL_COLOR)

        for stair in self.stairs:
            draw.rectangle((offset_x + stair["x_min"], offset_y + stair["y_min"], offset_x + stair["x_max"], offset_y + stair["y_max"]),
                           fill=RAW_STAIR_COLOR)
            draw.text(
                (offset_x + (stair["x_min"] + stair["x_max"]) / 2, offset_y + (stair["y_min"] + stair["y_max"]) / 2),
                stair["category"],
                font=fnt, fill=RAW_LABEL_COLOR)

        for raw_object in self.raw_objects:
            draw.rectangle((offset_x + raw_object["x_min"], offset_y + raw_object["y_min"], offset_x + raw_object["x_max"], offset_y + raw_object["y_max"]),
                           fill=RAW_OBJECT_COLOR)
            draw.text((offset_x + (raw_object["x_min"] + raw_object["x_max"]) / 2, offset_y + (raw_object["y_min"] + raw_object["y_max"]) / 2),
                      raw_object["category"],
                      font=fnt, fill=RAW_LABEL_COLOR)

        for door in self.openings:
            draw.line((offset_x + door["x_min"], offset_y + door["y_min"], offset_x + door["x_max"], offset_y + door["y_max"]), fill=RAW_DOOR_COLOR)
        image.save(path)

    def sketch_room_annotations(self, conf: ConfigManager, room_key, path: str):
        """
        Sketch annotations of a room.
        :param conf: ConfigManager
        :param room_key: Key of interested room
        :param path: Path to save sketch
        """
        fnt = ImageFont.truetype(conf.data_paths.pil_font.path, conf.data_paths.pil_font.size)

        offset_x = -self.x_min + ROOM_SKETCH_MARGIN
        offset_y = -self.y_min + ROOM_SKETCH_MARGIN

        image = Image.new('RGB', (self.x_max - self.x_min + 2 * ROOM_SKETCH_MARGIN, self.y_max - self.y_min + 2 * ROOM_SKETCH_MARGIN))
        draw = ImageDraw.Draw(image)

        polyline = get_polyline(self.room_description_map[room_key].walls)
        polyline = [(a[0] + offset_x, a[1] + offset_y) for a in polyline]
        draw.polygon(polyline, fill=ROOM_SKETCH_SELECTED_ROOM_COLOR, outline=None)

        # Highlight neighbours
        neighbour_candidates = [a for a in self.rdr if a[0] == room_key]
        for _, _, neighbour_candidate in neighbour_candidates:
            if neighbour_candidate is not None:
                neighbour_polyline = get_polyline(self.room_description_map[neighbour_candidate].walls)
                neighbour_polyline = [(a[0] + offset_x, a[1] + offset_y) for a in neighbour_polyline]
                draw.polygon(neighbour_polyline, fill=ROOM_SKETCH_DOOR_CONNECTED_ADJACENT_ROOM_COLOR, outline=None)

        self.wall_graph.sketch(draw, ROOM_SKETCH_WALL_COLOR, hole_color=ROOM_SKETCH_HOLE_COLOR, window_color=ROOM_SKETCH_WINDOW_COLOR,
                               door_color=ROOM_SKETCH_DOOR_COLOR, selection=None, selection_fill=None, offset=(offset_x, offset_y))

        # Various annotations assigned to room
        for room_annotation in self.room_description_map[room_key].annotations:
            draw.rectangle(
                ((room_annotation.p1[0] + offset_x, room_annotation.p1[1] + offset_y), (room_annotation.p2[0] + offset_x, room_annotation.p2[1] + offset_y)),
                fill=ROOM_SKETCH_ROOM_ANNOTATION_COLOR, outline=None)
        for room_annotation in self.room_description_map[room_key].annotations:
            draw.text(((room_annotation.p1[0] + room_annotation.p2[0]) // 2 + offset_x, (room_annotation.p1[1] + room_annotation.p2[1]) // 2 + offset_y),
                      room_annotation.type, font=fnt, fill=ROOM_SKETCH_ROOM_ANNOTATION_LABEL_COLOR)

        image.save(path)

    def populate_room_descriptions_from_r2v_output(self) -> None:
        """
        Populate room description map from raster-to-vector outputs.
        """
        # Identify room types of each room
        for room_key, rd in self.room_description_map.items():
            room_type_candidates = []
            for i_wall, wall in enumerate(rd.walls):
                next_wall = rd.walls[(i_wall + 1) % len(rd.walls)]

                next_wall_connection = None
                if next_wall.p1 == wall.p1 or next_wall.p1 == wall.p2:
                    next_wall_connection = next_wall.p1
                elif next_wall.p2 == wall.p1 or next_wall.p2 == wall.p2:
                    next_wall_connection = next_wall.p2
                else:
                    assert False

                if wall.p2 != next_wall_connection:
                    should_swap_wall_endpoints = True
                    room_type_candidates.append(wall.left_room_type)
                else:
                    should_swap_wall_endpoints = False
                    room_type_candidates.append(wall.right_room_type)
                # print(should_swap_wall_endpoints)
            room_type_candidates = list(set(room_type_candidates))
            # assert len(room_type_candidates) == 1  # Test for consistent room type assignment
            assert room_type_candidates[0] != "outside"

            rd.room_id = generate_room_id(room_key, self.ordered_rooms)
            rd.room_types = [AABBAnnotation(a) for a in room_type_candidates]

    def populate_room_descriptions_from_r2v_annot(self, conf: ConfigManager) -> None:
        """
        Populate room description map from raster-to-vector annotations.
        :param conf: ConfigManager
        """
        for room_key, rd in self.room_description_map.items():
            rd.room_id = generate_room_id(room_key, self.ordered_rooms)
            for annotation in rd.annotations:
                if annotation.type in conf.room_types:
                    rd.room_types.append(annotation)
