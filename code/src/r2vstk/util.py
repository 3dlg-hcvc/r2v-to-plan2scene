import math


def find_angle(p):
    """
    Find angle of specified vector.
    Angles are measured with respect to positive x axis, on the counter clockwise direction. Negative y is considered up. Positive x is considered right.
    :param p: A 2d vector
    :return angle in degrees.
    """
    assert isinstance(p, tuple)
    assert len(p) == 2
    h = math.sqrt(p[0] ** 2 + p[1] ** 2)
    ang = math.acos(p[0] / h) * 180 / math.pi
    if p[1] > 0:
        ang = -ang
    return ang


def find_angle_between(p1, p2):
    """
    Find angle between two 2d vectors p1 and p2.
    """
    a2 = find_angle(p2)
    a1 = find_angle(p1)
    if a1 < 0:
        a1 = 360 + a1
    if a2 < 0:
        a2 = 360 + a2

    return a2 - a1


def _find_next_wall(vertex, in_wall):
    """
    Wall along the in-wall upto vertex and choose the next wall going out from the vertex.
    """
    if len(vertex.adj) == 1:
        return None
    else:
        in_other = in_wall.p1
        if in_other == vertex:
            in_other = in_wall.p2
        in_other_vector = (in_other.pos[0] - vertex.pos[0], in_other.pos[1] - vertex.pos[1])
        #         print(in_other_vector)

        walls_with_angles = []

        for wall in vertex.adj:
            if wall == in_wall:
                continue
            adj_other = wall.p1
            if adj_other == vertex:
                adj_other = wall.p2
            adj_other_vector = (adj_other.pos[0] - vertex.pos[0], adj_other.pos[1] - vertex.pos[1])

            angle_between = find_angle_between(in_other_vector, adj_other_vector)
            if angle_between < 0:
                angle_between += 360
            walls_with_angles.append((angle_between, wall))
            #             print(str(wall), adj_other_vector, angle_between)

        walls_with_angles = sorted(walls_with_angles, key=lambda a: a[0])
        return walls_with_angles[0][1]


def find_room(start_node, start_wall):
    """
    Detect a room given a vertex in the room and a wall adjacent to that vertex in the room.
    :return: List of walls in the found room.
    """
    walls = [start_wall]
    current_node = start_node
    iter_count = 0
    while iter_count < 500:
        next_wall = _find_next_wall(current_node, walls[-1])
        if next_wall == walls[0]:
            return walls  # We have completed a cycle

        if next_wall is None:
            # Special case
            new_current_wall = walls[-1]
            new_current_node = new_current_wall.p1
            if new_current_node == current_node:
                new_current_node = new_current_wall.p2
            walls.append(new_current_wall)
            current_node = new_current_node
        else:
            new_current_node = next_wall.p1
            if new_current_node == current_node:
                new_current_node = next_wall.p2
            current_node = new_current_node
            walls.append(next_wall)
        iter_count += 1
    return walls


def get_pd(grad, intercept, p):
    """
    Get perpendicular distance from p to a straight line.
    """
    return abs(-grad * p[0] + p[1] - intercept) / math.sqrt(grad ** 2 + 1)


def manhattan_distance_between(a, b):
    """
    Compute manhattan distance between 2 points
    """
    # return math.sqrt((a[0] - b[0])**2 + (a[1]- b[1])**2)
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def get_closest_and_furthest(target, p1, p2):
    """
    Identify the closest and further to a target point given 2 candidate points.
    """
    dp1 = sq_distance(target, p1)
    dp2 = sq_distance(target, p2)
    if dp1 < dp2:
        return p1, p2
    return p2, p1


def sq_distance(p1, p2):
    """
    Compute l2 distance between two points
    """
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def convert_int(str_num):
    """
    Convert string number to integer
    """
    if str_num.isnumeric():
        return int(str_num)
    else:
        return int(float(str_num))


def point_line_seg_distance(p1: tuple, p2: tuple, p: tuple, extend_line: bool = False):
    """
    Find shortest distance between a line segment (p1, p2) and a given point p.
    """
    assert isinstance(p1, tuple) and len(p1) == 2
    assert isinstance(p2, tuple) and len(p2) == 2
    assert isinstance(p, tuple) and len(p) == 2

    # Code adapted from https://stackoverflow.com/questions/849211/shortest-distance-between-a-point-and-a-line-segment
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p
    x1, x2, x3, y1, y2, y3 = float(x1), float(x2), float(x3), float(y1), float(y2), float(y3)
    px = x2 - x1
    py = y2 - y1

    norm = px * px + py * py
    if norm == 0:
        dx = x1 - x3
        dy = y1 - y3

        dist = (dx * dx + dy * dy) ** .5
        return dist, (x1, y1)

    u = ((x3 - x1) * px + (y3 - y1) * py) / float(norm)

    if not extend_line:
        if u > 1:
            u = 1
        elif u < 0:
            u = 0

    x = x1 + u * px
    y = y1 + u * py

    dx = x - x3
    dy = y - y3

    dist = (dx * dx + dy * dy) ** .5

    return dist, (x, y)


def rect_line_distance(rect_p1, rect_p2, line_p1, line_p2):
    """
    Find distance between a rectangle and a line segment.
    """
    c1 = (rect_p1[0], rect_p1[1])
    c2 = (rect_p2[0], rect_p1[1])
    c3 = (rect_p2[0], rect_p2[1])
    c4 = (rect_p1[0], rect_p2[1])
    cs = [c1, c2, c3, c4]
    min_distance = sq_distance(c1, line_p1)
    for c in cs:
        min_distance = min(min_distance, sq_distance(c, line_p1))
        min_distance = min(min_distance, sq_distance(c, line_p2))

    return min_distance


def hole_to_line(wall_p1, wall_p2, hole_start, hole_end):
    """
    Convert 1D on-wall coordinates to 2D world coordinates.
    """
    distance = math.sqrt(float((wall_p2[0] - wall_p1[0]) ** 2 + (wall_p2[1] - wall_p1[1]) ** 2))
    start_x = (wall_p2[0] - wall_p1[0]) / float(distance) * hole_start + wall_p1[0]
    start_y = (wall_p2[1] - wall_p1[1]) / float(distance) * hole_start + wall_p1[1]
    end_x = (wall_p2[0] - wall_p1[0]) / float(distance) * hole_end + wall_p1[0]
    end_y = (wall_p2[1] - wall_p1[1]) / float(distance) * hole_end + wall_p1[1]
    return (start_x, start_y), (end_x, end_y)


def line_contains_check(parent, child, pd_margin: bool):
    """
    Test whether a line segment is very close to another line segments. Used for pairing of openings (doors/windows) with walls.
    """
    if abs(parent.p2.pos[0] - parent.p1.pos[0]) > 0:
        parent_grad = float(parent.p2.pos[1] - parent.p1.pos[1]) / float(parent.p2.pos[0] - parent.p1.pos[0])
        parent_intercept = parent.p1.pos[1] - parent_grad * parent.p1.pos[0]
        pd1 = get_pd(parent_grad, parent_intercept, child.p1.pos)
        pd2 = get_pd(parent_grad, parent_intercept, child.p2.pos)
    else:
        pd1 = abs(child.p1.pos[0] - parent.p1.pos[0])
        pd2 = abs(child.p2.pos[0] - parent.p2.pos[0])

    if pd1 > pd_margin:
        #         print("PD1 failed", pd1)
        return False, None
    if pd2 > pd_margin:
        #         print("PD2 failed", pd2)
        return False, None

    # Now both are in same line
    p1_c1_distance = math.sqrt((parent.p1.pos[0] - child.p1.pos[0]) ** 2 + (parent.p1.pos[1] - child.p1.pos[1]) ** 2)
    p1_c2_distance = math.sqrt((parent.p1.pos[0] - child.p2.pos[0]) ** 2 + (parent.p1.pos[1] - child.p2.pos[1]) ** 2)
    p2_c1_distance = math.sqrt((parent.p2.pos[0] - child.p1.pos[0]) ** 2 + (parent.p2.pos[1] - child.p1.pos[1]) ** 2)
    p2_c2_distance = math.sqrt((parent.p2.pos[0] - child.p2.pos[0]) ** 2 + (parent.p2.pos[1] - child.p2.pos[1]) ** 2)

    if p1_c1_distance < p1_c2_distance and p2_c2_distance < p2_c1_distance:
        return True, min(pd1, pd2)

    if p1_c2_distance < p1_c1_distance and p2_c1_distance < p2_c2_distance:
        return True, min(pd1, pd2)

    return False, None


def get_polyline(walls):
    """
    Generate polyline given a list of walls.
    """
    points = []
    points.append(walls[0].p1)
    points.append(walls[0].p2)
    unvisited_walls = list(walls[1:])
    while len(unvisited_walls) > 0:
        for i, w in enumerate(unvisited_walls):
            if w.p1 == points[-1]:
                del unvisited_walls[i]
                points.append(w.p2)
                break
            elif w.p2 == points[-1]:
                del unvisited_walls[i]
                points.append(w.p1)
                break
        else:
            break

    return [p.pos for p in points]


def find_closest(target: tuple, other_nodes: list, cutoff_distance: float, exclude: list):
    """
    Find closest and 2nd closest node to a target node subjected to a cutoff distance and an exclusion list.
    """
    distance_tuples = []
    for other_node in other_nodes.values():
        if other_node in exclude:
            continue
        distance = manhattan_distance_between(other_node.pos, target)
        if distance < cutoff_distance:
            distance_tuples.append((distance, other_node))

    distance_tuples = sorted(distance_tuples, key=lambda x: x[0])
    if len(distance_tuples) > 1:
        return distance_tuples[0][1], distance_tuples[1][1]
    elif len(distance_tuples) == 1:
        return distance_tuples[0][1], None
    else:
        return None, None
