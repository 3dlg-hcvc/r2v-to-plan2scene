class RoomDescription:
    """
    Describes a room.
    """

    def __init__(self, room_key: frozenset, walls: list, room_id: str = None):
        """
        Initialize room description
        """
        assert isinstance(room_key, frozenset)
        assert isinstance(walls, list)

        self._room_key = room_key
        self._room_id = room_id
        self._walls = walls
        self._room_types = []
        self._wall_ids_map = {}  # Mapping from wall to wall id
        self._annotations = []  # Annotation AABBs assigned to the room

    @property
    def annotations(self) -> list:
        return self._annotations

    @property
    def wall_ids_map(self):
        return self._wall_ids_map

    @property
    def room_id(self) -> str:
        return self._room_id

    @room_id.setter
    def room_id(self, value: str):
        assert isinstance(value, str)
        self._room_id = value

    @property
    def walls(self) -> list:
        return self._walls

    @property
    def room_types(self) -> list:
        return self._room_types

    @room_types.setter
    def room_types(self, values: list):
        assert isinstance(values, list)
        self._room_types = values

    def get_room_type_as_str(self):
        if len(self.room_types) == 0:
            return None
        # assert len(self.room_types) == 1 # Multiple room type annotations

        return " and ".join([a.type for a in self.room_types])

    def __repr__(self):
        out = "RD"
        if self.get_room_type_as_str() is not None:
            out += " " + self.get_room_type_as_str()
        return out
