from typing import Self


class BodyValueData:
    def __init__(self, name: str, body_id: int):
        self.name: str = name
        self.body_id: int = body_id
        self.base_value: tuple[int, int] = (0, 0)
        self.mapped_value: tuple[float, float] = (1.25, 1.25)
        self.honk_value: tuple[int, int] = (0, 0)

    def get_base_values(self) -> tuple[int, int]:
        return self.base_value[0], self.base_value[1]

    def set_base_values(self, value: int, min_value: int) -> Self:
        self.base_value = (value, min_value)
        return self

    def get_mapped_values(self) -> tuple[float, float]:
        return self.mapped_value[0], self.mapped_value[1]

    def set_mapped_values(self, value: float, min_value: float) -> Self:
        self.mapped_value = (value, min_value)
        return self

    def get_honk_values(self) -> tuple[int, int]:
        return self.honk_value[0], self.honk_value[1]

    def set_honk_values(self, value: int, min_value: int) -> Self:
        self.honk_value = (value, min_value)
        return self