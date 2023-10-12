from pydantic import BaseModel


def _to_camel_case(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class CamelCaseBaseModel(BaseModel):
    class Config:
        allow_population_by_field_name = True
        alias_generator = _to_camel_case


def _to_title_case(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_") if part)


class TitleCaseBaseModel(BaseModel):
    class Config:
        allow_population_by_field_name = True
        alias_generator = _to_title_case
