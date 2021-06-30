# This code assumes manhattan
# Code adapted from https://github.com/art-programmer/FloorplanTransformation/


def find_connections(l1, l2, gap):
    if l1[0][0] == l1[1][0]:
        r, p = _findConnections(l2, l1, gap=5)
        r[0], r[1] = r[1], r[0]
    else:
        r, p = _findConnections(l1, l2, gap=5)
    return r, p


def lineRange(line):
    direction = calcLineDirection(line)
    fixedValue = (line[0][1 - direction] + line[1][1 - direction]) // 2
    minValue = min(line[0][direction], line[1][direction])
    maxValue = max(line[0][direction], line[1][direction])
    return direction, fixedValue, minValue, maxValue


def calcLineDirection(line):
    return int(abs(line[0][0] - line[1][0]) < abs(line[0][1] - line[1][1]))


def pointDistance(point_1, point_2):
    # return np.sqrt(pow(point_1[0] - point_2[0], 2) + pow(point_1[1] - point_2[1], 2))
    return max(abs(point_1[0] - point_2[0]), abs(point_1[1] - point_2[1]))


def _findConnections(line_1, line_2, gap):
    connection_1 = -1
    connection_2 = -1
    pointConnected = False
    for c_1 in range(2):
        if pointConnected:
            break
        for c_2 in range(2):
            if pointDistance(line_1[c_1], line_2[c_2]) > gap:
                continue

            connection_1 = c_1
            connection_2 = c_2
            connectionPoint = ((line_1[c_1][0] + line_2[c_2][0]) // 2, (line_1[c_1][1] + line_2[c_2][1]) // 2)
            pointConnected = True
            break
        continue
    if pointConnected:
        return [connection_1, connection_2], connectionPoint
    direction_1, fixedValue_1, min_1, max_1 = lineRange(line_1)
    direction_2, fixedValue_2, min_2, max_2 = lineRange(line_2)
    if direction_1 == direction_2:
        return [-1, -1], (0, 0)

    # print(fixedValue_1, min_1, max_1, fixedValue_2, min_2, max_2)
    if min(fixedValue_1, max_2) < max(fixedValue_1, min_2) - gap or min(fixedValue_2, max_1) < max(fixedValue_2, min_1) - gap:
        return [-1, -1], (0, 0)

    if abs(min_1 - fixedValue_2) <= gap:
        return [0, 2], (fixedValue_2, fixedValue_1)
    if abs(max_1 - fixedValue_2) <= gap:
        return [1, 2], (fixedValue_2, fixedValue_1)
    if abs(min_2 - fixedValue_1) <= gap:
        return [2, 0], (fixedValue_2, fixedValue_1)
    if abs(max_2 - fixedValue_1) <= gap:
        return [2, 1], (fixedValue_2, fixedValue_1)
    return [2, 2], (fixedValue_2, fixedValue_1)
