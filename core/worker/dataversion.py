import os
import json
from typing import Dict, List, Union


def _jsonToDict(json_: str) -> dict:
    try:
        return json.loads(json_)
    except json.decoder.JSONDecodeError:
        return {}


class DataVariable:
    _varNamesMap: Dict[str, Dict[int, List[str]]] = {}

    def __init__(self, type_: Union[str, List[str]], version: int, variable: str):
        if isinstance(type_, list):
            for t in type_:
                self.__class__(t, version, variable)
        elif isinstance(type_, str):
            if type_ not in self._varNamesMap:
                self._varNamesMap[type_] = {}

            if version not in self._varNamesMap[type_]:
                self._varNamesMap[type_][version] = []

            self._varNamesMap[type_][version].append(variable)

    @classmethod
    def getVarNames(cls, type_: str, version: int):
        variables = []

        for ver in range(version + 1):
            for var in cls._varNamesMap.get(type_, {}).get(ver, []):
                variables.append(var)

        return variables


class DataMetaclass(type):
    def __new__(mcs, name, bases, attrs):
        def init(orig_init):
            def __init__(self, *args, **kwargs):
                for varName, annotation in self.__annotations__.items():
                    if getattr(self, varName, None) is not None:
                        continue

                    if annotation in (list, dict, str):
                        if getattr(self, varName, None) is None:
                            setattr(self, varName, annotation())
                    elif annotation == int:
                        if getattr(self, varName, None) is None:
                            setattr(self, varName, 0)
                    elif annotation == bool:
                        if getattr(self, varName, None) is None:
                            setattr(self, varName, False)
                    elif getattr(annotation, "__origin__", None) in (dict, list):
                        if getattr(self, varName, None) is None:
                            setattr(self, varName, getattr(annotation, "__origin__")())

                orig_init(self, *args, **kwargs)

            return __init__

        cls = super(DataMetaclass, mcs).__new__(mcs, name, bases, attrs)

        if "__init__" in attrs:
            cls.__init__ = init(cls.__init__)

        return cls


class DataClass(metaclass=DataMetaclass):
    formatVersion: int = 0
    formatType: str = ""

    def loadFromJson(self, json_: Union[str, dict], ignoredVars=None, allowedVars=None) -> bool:
        if ignoredVars is None:
            ignoredVars = []
        if allowedVars is None:
            allowedVars = []

        if isinstance(json_, str):
            data: dict = _jsonToDict(json_)
        else:
            data: dict = json_

        formatVersion = data.pop("formatVersion", None)

        if formatVersion is not None:
            for varName in DataVariable.getVarNames(self.formatType, formatVersion):
                if varName in ignoredVars + ["formatVersion"]:
                    continue

                if allowedVars and varName not in allowedVars:
                    continue

                var = data.get(varName)

                for baseClass in [self, *self.__class__.__mro__]:
                    if baseClass in (object, ):
                        break

                    if type_ := getattr(baseClass, "__annotations__", {}).get(varName, None):
                        if getattr(type_, "__origin__", None) in (dict,):
                            if type_.__args__[0] == int:
                                var = {int(k): v for k, v in var.items()}
                            break

                setattr(self, varName, var)

            return True

        return False

    def loadJsonFile(self, path, ignoredVars=None, allowedVars=None) -> bool:
        if ignoredVars is None:
            ignoredVars = []
        if allowedVars is None:
            allowedVars = []

        if os.path.exists(path):
            with open(path, "r") as file:
                loaded = self.loadFromJson(file.read(), ignoredVars, allowedVars)

            return loaded

        else:
            self.saveJsonFile(path)
            return False

    def getDict(self, ignoredVars=None):
        if ignoredVars is None:
            ignoredVars = []

        data = {}

        for varName in DataVariable.getVarNames(self.formatType, self.formatVersion):
            if varName in ignoredVars:
                continue

            if hasattr(self, varName):
                var = getattr(self, varName)
                data[varName] = var

        return data

    def getJson(self, ignoredVars=None, formatJson=False):
        if ignoredVars is None:
            ignoredVars = []

        data = self.getDict(ignoredVars)

        if formatJson:
            return json.dumps(data, indent=4, sort_keys=True)
        else:
            return json.dumps(data)

    def saveJsonFile(self, path, ignoredVars=None, formatJson=False):
        if ignoredVars is None:
            ignoredVars = []

        with open(path, "w") as file:
            file.write(self.getJson(ignoredVars, formatJson))
