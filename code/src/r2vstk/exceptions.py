class StraightenWallsFailed(Exception):
    def __init__(self, house_path, iter_count):
        self.house_path = house_path
        self.iter_count = iter_count

    def __str__(self):
        return "Straighten wall failed at iteration %d :%s" % (self.iter_count, self.house_path)
