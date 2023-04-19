class BodyData:
    def __init__(self, name):
        self.name: str = name
        self.type: str = ''
        self.subclass: str = ''
        self.luminosity: str = ''
        self.terraformable: bool = False
        self.distance: float = 0
        self.base_value: tuple[int, int] = (0, 0)
        self.mapped_value: tuple[float, float] = (1.25, 1.25)
        self.honk_value: tuple[int, int] = (0, 0)
        self.mapped: bool = False
        self.bio_signals: int = 0
        self.is_a_star: bool = False

    def get_name(self):
        return self.name

    def get_base_values(self):
        return self.base_value[0], self.base_value[1]

    def set_base_values(self, value: int, min_value: int):
        self.base_value = (value, min_value)

    def get_mapped_values(self):
        return self.mapped_value[0], self.mapped_value[1]

    def set_mapped_values(self, value: float, min_value: float):
        self.mapped_value = (value, min_value)

    def get_honk_values(self):
        return self.honk_value[0], self.honk_value[1]

    def set_honk_values(self, value: int, min_value: int):
        self.honk_value = (value, min_value)

    def is_mapped(self):
        return self.mapped

    def set_mapped(self, value: bool):
        self.mapped = value

    def get_bio_signals(self):
        return self.bio_signals

    def set_bio_signals(self, value: int):
        self.bio_signals = value

    def get_distance(self):
        return self.distance

    def set_distance(self, value: float):
        self.distance = value

    def get_type(self):
        return self.type

    def set_type(self, value: str):
        self.type = value

    def get_subclass(self):
        return self.subclass

    def set_subclass(self, value: str):
        self.subclass = value

    def get_luminosity(self):
        return self.luminosity

    def set_luminosity(self, value: str):
        self.luminosity = value

    def is_terraformable(self):
        return self.terraformable

    def set_terraformable(self, value: bool):
        self.terraformable = value

    def is_star(self):
        return self.is_a_star

    def set_star(self, value: bool):
        self.is_a_star = value
