from typing import TypedDict, List, Dict


class MetadataTyped(TypedDict):
    formatVersion: int
    formatType: str


class ModDataSwfsTyped(TypedDict):
    scripts: Dict[str, str]
    sounds: List[str]
    sprites: List[str]


class ModDataTyped(MetadataTyped):
    gameVersion: str
    name: str
    author: str
    version: str
    description: str
    tags: List[str]
    previewsIds: Dict[str, str]
    hash: str
    swfs: Dict[str, ModDataSwfsTyped]
    files: Dict[str, str]
    authorId: int
    modId: int
    platform: str


class ModloaderCoreMods(TypedDict):
    mod: str
    modHashSum: str
