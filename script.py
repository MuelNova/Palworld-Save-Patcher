import zlib
import platform
import json


from enum import Enum
from pathlib import Path
from subprocess import check_output

class SaveType(Enum):
    SINGLE = 0x31
    DOUBLE = 0x32


def fixHost(save_folder: Path | str, GUID: str):
    save_folder = Path(save_folder)
    if not save_folder.exists() and not save_folder.is_dir():
        raise FileNotFoundError(f"Folder {save_folder} not found")
    
    LEVEL = save_folder / "Level.sav"
    HOST_PLAYER = save_folder / "Players" / "00000000000000000000000000000001.sav"
    PLAYER = save_folder / "Players" / f"{GUID}.sav"
    FORMATTED_GUID = f"{GUID[:8]}-{GUID[8:12]}-{GUID[12:16]}-{GUID[16:20]}-{GUID[20:]}".lower()
    if not LEVEL.exists():
        raise FileNotFoundError(f"File {LEVEL} not found")
    if not HOST_PLAYER.exists():
        raise FileNotFoundError(f"File {HOST_PLAYER} not found")
    if not PLAYER.exists():
        raise FileNotFoundError(f"File {PLAYER} not found")
    
    print("[+] Fixing GUID...")
    host_player_data = sav_to_gvas(HOST_PLAYER)
    host_player_data = gvas_to_json(host_player_data)

    # Replace GUID
    host_player_data["root"]["properties"]["SaveData"]["Struct"]["value"]["Struct"]["PlayerUId"]["Struct"]["value"]["Guid"] = FORMATTED_GUID
    host_player_data["root"]["properties"]["SaveData"]["Struct"]["value"]["Struct"]["IndividualId"]["Struct"]["value"]["Struct"]["PlayerUId"]["Struct"]["value"]["Guid"] = FORMATTED_GUID
    instanceID = host_player_data["root"]["properties"]["SaveData"]["Struct"]["value"]["Struct"]["IndividualId"]["Struct"]["value"]["Struct"]["InstanceId"]["Struct"]["value"]["Guid"]

    host_player_data = json_to_gvas(host_player_data)
    gvas_to_sav(host_player_data, get_save_type(HOST_PLAYER), PLAYER)
    print("[√] Success...")
    del host_player_data

    # Replace Level
    print("[+] Fixing Level...")
    level_data = sav_to_gvas(LEVEL)
    level_data = gvas_to_json(level_data)
    length = len(level_data["root"]["properties"]["worldSaveData"]["Struct"]["value"]["Struct"]["CharacterSaveParameterMap"]["Map"]["value"])
    for i in range(length):
        if level_data["root"]["properties"]["worldSaveData"]["Struct"]["value"]["Struct"]["CharacterSaveParameterMap"]["Map"]["value"][i]["key"]["Struct"]["Struct"]["InstanceId"]["Struct"]["value"]["Guid"] == instanceID:
            level_data["root"]["properties"]["worldSaveData"]["Struct"]["value"]["Struct"]["CharacterSaveParameterMap"]["Map"]["value"][i]["key"]["Struct"]["Struct"]["PlayerUId"]["Struct"]["value"]["Guid"] = FORMATTED_GUID
            break

    level_data = json_to_gvas(level_data)
    gvas_to_sav(level_data, get_save_type(LEVEL), LEVEL)
    print("[√] Success...")
    HOST_PLAYER.unlink()
    print("[√] Done!")


    
    
    
    


def sav_to_gvas(sav_file: Path | str | bytes, gvas_file: Path | str = None) -> bytes:
    """
    提供 sav 文件路径或 bytes，返回 gvas 文件的 bytes。如果提供 gvas_file，则将 gvas 文件写入该路径。
    """
    if isinstance(sav_file, (str, Path)):
        if not Path(sav_file).exists():
            raise FileNotFoundError(f"File {sav_file} not found")
        with open(Path(sav_file), "rb") as f:
            data = f.read()
    elif isinstance(sav_file, bytes):
        data = sav_file
    else:
        raise TypeError(f"Invalid type {type(sav_file)}")
    
    save_type = get_save_type(data)
    
    try:
        decompressed_data = _decompress(data, save_type)
    except ValueError:
        raise ValueError(f"File {sav_file} is not a valid save file")
    
    if gvas_file is not None:
        if isinstance(gvas_file, (str, Path)):
            with open(Path(gvas_file), "wb") as f:
                f.write(decompressed_data)
        else:
            raise TypeError(f"Invalid type {type(gvas_file)}")
    return decompressed_data


def gvas_to_sav(gvas_file: Path | str | bytes, type_: SaveType, sav_file: Path | str = None) -> bytes:
    """
    提供 gvas 文件路径或 bytes，返回 sav 文件的 bytes。如果提供 sav_file，则将 sav 文件写入该路径。
    """
    if isinstance(gvas_file, (str, Path)):
        if not Path(gvas_file).exists():
            raise FileNotFoundError(f"File {gvas_file} not found")
        with open(Path(gvas_file), "rb") as f:
            data = f.read()
    elif isinstance(gvas_file, bytes):
        data = gvas_file
    else:
        raise TypeError(f"Invalid type {type(gvas_file)}")
    
    sav_data = _compress(data, type_)

    if sav_file is not None:
        if isinstance(sav_file, (str, Path)):
            with open(Path(sav_file), "wb") as f:
                f.write(sav_data)
        else:
            raise TypeError(f"Invalid type {type(sav_file)}")
    return sav_data


def gvas_to_json(gvas_file: Path | str | bytes, json_file: Path | str = None) -> dict:
    """
    提供 gvas 文件路径或 bytes，返回 json 文件的 dict。如果提供 json_file，则将 json 文件写入该路径。
    """
    if isinstance(gvas_file, (str, Path)):
        if not Path(gvas_file).exists():
            raise FileNotFoundError(f"File {gvas_file} not found")
        with open(Path(gvas_file), "rb") as f:
            data = f.read()
    elif isinstance(gvas_file, bytes):
        data = gvas_file
    else:
        raise TypeError(f"Invalid type {type(gvas_file)}")
    
    if len(data) < 4 or data[:4] != b'GVAS':
        raise ValueError(f"File {gvas_file} is not a valid gvas file")
    json_data = _uesave_to_json(data)

    if json_file is not None:
        if isinstance(json_file, (str, Path)):
            with open(Path(json_file), "w") as f:
                f.write(json_data)
        else:
            raise TypeError(f"Invalid type {type(json_file)}")
    return json.loads(json_data)


def json_to_gvas(json_file: Path | str | dict, gvas_file: Path | str = None) -> bytes:
    """
    提供 json 文件路径或 dict，返回 gvas 文件的 bytes。如果提供 gvas_file，则将 gvas 文件写入该路径。
    """
    if isinstance(json_file, (str, Path)):
        if not Path(json_file).exists():
            raise FileNotFoundError(f"File {json_file} not found")
        with open(Path(json_file), "rb") as f:
            data = json.load(f)
    elif isinstance(json_file, dict):
        data = json_file
    else:
        raise TypeError(f"Invalid type {type(json_file)}")
    
    gvas_data = _uesave_from_json(data)

    if gvas_file is not None:
        if isinstance(gvas_file, (str, Path)):
            with open(Path(gvas_file), "wb") as f:
                f.write(gvas_data)
        else:
            raise TypeError(f"Invalid type {type(gvas_file)}")
    return gvas_data


def _decompress(data: bytes, type_: SaveType = SaveType.SINGLE) -> bytes:
    uncompressed_length = int.from_bytes(data[:4], 'little')
    compressed_length = int.from_bytes(data[4:8], 'little')
    if type_ == SaveType.SINGLE:
        if len(data[12:]) != compressed_length:
            raise ValueError
        raw_data = zlib.decompress(data[12:])
        if len(raw_data) != uncompressed_length:
            raise ValueError
    elif type_ == SaveType.DOUBLE:
        if len(data[12:]) != compressed_length:
            raise ValueError
        fd = zlib.decompress(data[12:])
        if len(fd) != uncompressed_length:
            raise ValueError
        raw_data = zlib.decompress(fd)
    return raw_data
        

def _compress(data: bytes, type_: SaveType = SaveType.SINGLE) -> bytes:
    
    if type_ == SaveType.SINGLE:
        compressed_data = zlib.compress(data)
        uncompressed_length = len(data).to_bytes(4, "little")
        compressed_length = len(compressed_data).to_bytes(4, "little")
    elif type_ == SaveType.DOUBLE:
        compressed_data = zlib.compress(data)
        uncompressed_length = len(compressed_data).to_bytes(4, "little")
        compressed_data = zlib.compress(compressed_data)
        compressed_length = len(compressed_data).to_bytes(4, "little")

    return uncompressed_length + compressed_length \
        + b'PlZ' + type_.value.to_bytes(1, "little") + compressed_data
    

def _uesave_to_json(data: bytes) -> str:
    sys_ = platform.system()
    if sys_ not in ("Windows", "Linux"):
        raise NotImplementedError(f"System {sys_} is not supported")
    
    UESAVE_TYPE_MAPS = [
        ".worldSaveData.CharacterSaveParameterMap.Key=Struct",
        ".worldSaveData.FoliageGridSaveDataMap.Key=Struct",
        ".worldSaveData.FoliageGridSaveDataMap.ModelMap.InstanceDataMap.Key=Struct",
        ".worldSaveData.MapObjectSpawnerInStageSaveData.Key=Struct",
        ".worldSaveData.ItemContainerSaveData.Key=Struct",
        ".worldSaveData.CharacterContainerSaveData.Key=Struct"
    ]

    uesave = Path("bin") / ("uesave" + (".exe" if sys_ == "Windows" else ""))
    args = [str(uesave), "to-json"]
    for map_type in UESAVE_TYPE_MAPS:
        args.append('--type')
        args.append(map_type)
    json_ = check_output(args, input=data, stderr=None)
    return json_.decode("utf-8")

def get_save_type(f: str | Path | bytes) -> SaveType:
    if isinstance(f, bytes):
        data = f
    elif isinstance(f, (str, Path)):
        with open(Path(f), "rb") as f:
            data = f.read()
    else:
        raise TypeError(f"Invalid type {type(f)}")
    
    if len(data) < 12 or data[8:11] != b'PlZ':
        raise ValueError(f"File {f} is not a valid save file")
    
    try:
        save_type = SaveType(data[11])
    except ValueError:
        raise ValueError(f"File {f} is not a valid save file")
    return save_type
    
def _uesave_from_json(data: str | dict) -> bytes:
    if isinstance(data, dict):
        data = json.dumps(data)
    sys_ = platform.system()
    if sys_ not in ("Windows", "Linux"):
        raise NotImplementedError(f"System {sys_} is not supported")
    
    uesave = Path("bin") / ("uesave" + (".exe" if sys_ == "Windows" else ""))
    output = check_output([str(uesave), "from-json"], input=data.encode())
    return output


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <sav/gvas/json file> <sav/gvas/json file>")
        sys.exit(1)

    if len(sys.argv) == 3:
        """
        Convert
        """
        if sys.argv[1].endswith(".sav"):
            if sys.argv[2].endswith(".gvas"):
                sav_to_gvas(sys.argv[1], sys.argv[2])
            if sys.argv[2].endswith(".json"):
                gvas = sav_to_gvas(sys.argv[1])
                gvas_to_json(gvas, sys.argv[2])
        elif sys.argv[1].endswith(".gvas"):
            if sys.argv[2].endswith(".sav"):
                if "Level" in sys.argv[2]:
                    gvas_to_sav(sys.argv[1], SaveType.DOUBLE, sys.argv[2])
                else:
                    gvas_to_sav(sys.argv[1], SaveType.SINGLE, sys.argv[2])
            elif sys.argv[2].endswith(".json"):
                gvas_to_json(sys.argv[1], sys.argv[2])
        elif sys.argv[1].endswith(".json"):
            if sys.argv[2].endswith(".gvas"):
                json_to_gvas(sys.argv[1], sys.argv[2])
            elif sys.argv[2].endswith(".sav"):
                gvas = json_to_gvas(sys.argv[1])
                if "Level" in sys.argv[2]:
                    gvas_to_sav(gvas, SaveType.DOUBLE, sys.argv[2])
                else:
                    gvas_to_sav(gvas, SaveType.SINGLE, sys.argv[2])
        else:
            print("Invalid file extension")
            sys.exit(1)
    if len(sys.argv) == 4:
        """
        Fix GUID
        """
        if sys.argv[1] == 'fix-host':
            fixHost(sys.argv[2], sys.argv[3])
        else:
            print(f"{sys.argv[0]} fix-host <FOLDER> <GUID>")
            sys.exit(1)
    