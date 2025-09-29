import pygame, math, typing, tkinter.messagebox
import tkinter.simpledialog, tkinter.filedialog
import tomllib
from enum import Flag, auto

try:
    with open("config.toml", "rb") as configfile:
        config = tomllib.load(configfile)
except (FileNotFoundError, tomllib.TOMLDecodeError):
    with open("resources/default.toml", "rb") as configfile:
        config = tomllib.load(configfile)

class Coordinate:
    def __init__(self: typing.Self, x: float = 0, y: float = 0) -> None:
        self.x = x
        self.y = y
    
    def set_root(self: typing.Self, root: pygame.Surface) -> None:
        self.root = root

    def set_pos(self: typing.Self, x: float, y: float) -> None:
        self.x = x
        self.y = y
        
    def set_pos_whole(self: typing.Self, x: int, y: int) -> None:
        self.x = x / self.root.get_width()
        self.y = y / self.root.get_height()

    def set_pos_whole_cartesian(self: typing.Self, x: int, y: int) -> None:
        self.set_pos_whole(
            x + self.root.get_width() // 2,
            y + self.root.get_height() // 2)

    def set_pos_grid(self: typing.Self, gridSize: int) -> None:
        x, y = self.get_pos()
        x = math.floor((x * gridSize) + 0.5) / gridSize
        y = math.floor((y * gridSize) + 0.5) / gridSize
        self.set_pos(x, y)
    
    def get_root(self: typing.Self) -> pygame.Surface:
        return self.root
    
    def get_pos(self: typing.Self) -> tuple[float, float]:
        return self.x, self.y
    
    def get_pos_whole(self: typing.Self) -> tuple[int, int]:
        return (math.floor(self.x * self.root.get_width()),
                math.floor(self.y * self.root.get_height()))
    
    def get_pos_cartesian(self: typing.Self) -> tuple[float, float]:
        return (self.x - 0.5, self.y - 0.5)
    
    def get_pos_whole_cartesian(self: typing.Self) -> tuple[int, int]:
        return (math.floor(self.x * self.root.get_width()) - self.root.get_width() // 2,
                math.floor(self.y * self.root.get_height()) - self.root.get_height() // 2)
    
    def copy(self: typing.Self) -> "Coordinate":
        c = Coordinate(self.x, self.y)
        c.set_root(self.root)
        return c

    def __str__(self: typing.Self) -> str:
        if self.root:
            pos = self.get_pos_whole()
            return f"({pos[0]}, {pos[1]})"
        return f"({self.x}, {self.y})"

    def __add__(self: typing.Self, other: "Coordinate") -> "Coordinate":
        c = Coordinate(self.x + other.x, self.y + other.y)
        if self.root: c.set_root(self.root)
        elif other.root: c.set_root(other.root)
        return c
    
    def __sub__(self: typing.Self, other: "Coordinate") -> "Coordinate":
        c = Coordinate(self.x - other.x, self.y - other.y)
        if self.root: c.set_root(self.root)
        elif other.root: c.set_root(other.root)
        return c

    def __mul__(self: typing.Self, other: "Coordinate") -> "Coordinate":
        c = Coordinate(self.x * other.x, self.y * other.y)
        if self.root: c.set_root(self.root)
        elif other.root: c.set_root(other.root)
        return c

    def __eq__(self: typing.Self, other: "Coordinate") -> bool:
        return self.get_pos() == other.get_pos()

class TextDirection(Flag):
    LEFT = auto()
    RIGHT = auto()
    UP = auto()
    DOWN = auto()

pygame.init()

window = pygame.display.set_mode((
    config.get("windowWidth", 1200),
    config.get("windowHeight", 800)))
icon = pygame.image.load("resources/icon.png")
icon = pygame.transform.scale(icon, (512, 512))

pygame.display.set_caption("KMetroMaker")

rect = icon.get_rect()
rect.center = window.get_rect().center

window.fill((255, 255, 255))
window.blit(icon, rect)

pygame.display.flip()
pygame.time.delay(2000)

lta = pygame.freetype.Font(config.get("font", "resources/Roboto.png"),
                           config.get("nameTextSize", 24))
textdis = config.get("nameDistance", 15)
stationSel: bool = False
terminus: int = -1
riverSel: bool = False
riverBegin: Coordinate | None = None
grid: int = config.get("gridSpace", 20)
running: bool = True

rightDown: bool = False
rightDownAt: Coordinate = Coordinate()
rightDownAt.set_pos(0, 0)

zoom: float = 1.0
pan: Coordinate = Coordinate()
pan.set_root(window)
orpan: Coordinate = pan.copy()

stations: list[dict[str, Coordinate]] = []
connections: list[dict[str, (Coordinate | tuple[int, int, int])]] = []
rivers: list[dict[str, (Coordinate | tuple[int, int, int])]] = []

def int2col(color: int) -> tuple[int, int, int]:
    return color // 65536 % 256, color // 256 % 256, color % 256

def col2int(color: tuple[int, int, int]) -> int:
    return color[0] * 65536 + color[1] * 256 + color[2]

def _find_conmap(termini: tuple[Coordinate]) -> int:
    def _t(connection: dict[str, Coordinate]) -> bool:
        try:
            a = connection["termini"].index(termini[0])
            b = connection["termini"].index(termini[1])
            return b != a
        except (ValueError, IndexError):
            return False
    return _t

def _text_pos(
        origin: Coordinate,
        rect: pygame.Rect,
        dir: TextDirection) -> pygame.Rect:
    origin: tuple[int, int] = origin.get_pos_whole()
    rect.center = origin
    
    if TextDirection.LEFT in dir:
        rect.right = origin[0] - textdis * zoom
    if TextDirection.RIGHT in dir:
        rect.left = origin[0] + textdis * zoom
    if TextDirection.UP in dir:
        rect.bottom = origin[1] - textdis * zoom
    if TextDirection.DOWN in dir:
        rect.top = origin[1] + textdis * zoom
    return rect

def usr_prompt_color(title: str, prompt: str) -> int | None:
    color = tkinter.simpledialog.askstring(title, prompt)
    
    if color is None: return
    
    if "paletteColors" in config.keys() and color.startswith("$"):
        paletteColor = config["paletteColors"].get(color[1:], None)
        if paletteColor is not None:
            color = int(paletteColor)
        else:
            tkinter.messagebox.showerror("Invalid color",
                                         "The pallete color entered does not exist.")
            return

    if not isinstance(color, int):
        if config.get("hexCompatible", True) and color.startswith("#"):
            try:
                color = int(color[1:], 16)
            except ValueError:
                pass

    if not isinstance(color, int):
        try:
            color = int(color)
        except ValueError:
            tkinter.messagebox.showerror("Invalid color",
                                         "The color entered is invalid.")
            return

    if color < 0: color = 0
    if color > 0xFFFFFF: color = 0xFFFFFF

    return color

def usr_coord_mouse() -> Coordinate:
    where = Coordinate(0, 0)
    where.set_root(window)
    where.set_pos_whole(
        pygame.mouse.get_pos()[0],
        pygame.mouse.get_pos()[1]
    )
    where.set_pos_grid(grid)
    return where

def find_station(where: Coordinate) -> int:
    try:
        return list(map(lambda a: a["where"].get_pos(), stations)).index(where.get_pos())
    except (ValueError, IndexError):
        return -1

def find_connection(termini: tuple[Coordinate, Coordinate]) -> int:
    try:
        return list(map(
            _find_conmap(termini),
            connections
        )).index(True)
    except (ValueError, IndexError):
        return -1
    
def find_all_connections(termini: tuple[Coordinate, Coordinate]) -> list[int]:
    return [i for i, j in enumerate(list(map(
        _find_conmap(termini),
        connections
    ))) if j]

def find_river(termini: tuple[Coordinate, Coordinate]) -> int:
    try:
        return list(map(
            _find_conmap(termini),
            rivers
        )).index(True)
    except (ValueError, IndexError):
        return -1

def add_station(where: Coordinate, name: str,
                dir: TextDirection = TextDirection.RIGHT) -> None:
    stations.append({"where": where, "name": name, "dir": dir})

def usr_add_station(*args, **kwargs) -> None:
    where: Coordinate = usr_coord_mouse()

    if find_station(where) >= 0: return

    name = tkinter.simpledialog.askstring("Enter station name",
                                        "What is the station name? (blank to cancel)")
    
    if name is None: return

    add_station(where, name)

def usr_remove_station(*args, **kwargs) -> None:
    global terminus
    global stationSel
    global connections

    where: Coordinate = usr_coord_mouse()
    station = find_station(where)

    if station < 0: return
    result = tkinter.messagebox.askyesno(
        "Remove station",
        f"Are you sure you want to remove the station \"{stations[station]["name"]}\"?")
    
    if not result: return
    stationCoord = stations.pop(station)
    if station == terminus:
        terminus = -1
        stationSel = False
    connections = list(filter(
        lambda a: stationCoord["where"].get_pos() not in 
            list(map(
                lambda b: b.get_pos(),
                a["termini"]
            )
        ),
        connections
    ))

def usr_rename_station(*args, **kwargs) -> None:
    where: Coordinate = usr_coord_mouse()
    station = find_station(where)

    if station < 0: return

    oldName = stations[station]["name"]

    name = tkinter.simpledialog.askstring(
        "Enter new station name",
        f"What is the new station name of \"{oldName}\"? (blank to cancel)")  
    
    if name is None: return
    stations[station]["name"] = name

def usr_change_text_dir_station(*args, **kwargs) -> None:
    global stations
    where: Coordinate = usr_coord_mouse()
    station = find_station(where)

    if station < 0: return

    dir = tkinter.simpledialog.askstring(
        "Enter new station text direction",
        "What is the new station text direction? (blank to cancel, any combination of CLRUD is valid)") 

    if not dir: return
    dirFlag = TextDirection(0)
    if "L" in dir: dirFlag |= TextDirection.LEFT
    if "R" in dir: dirFlag |= TextDirection.RIGHT
    if "U" in dir: dirFlag |= TextDirection.UP
    if "D" in dir: dirFlag |= TextDirection.DOWN

    if dirFlag == TextDirection(0):
        return

    stations[station]["dir"] = dirFlag

def draw_station(station: dict[str, Coordinate]) -> None:
    where = station["where"]
    cartesian = where.get_pos_whole_cartesian()
    where = Coordinate()
    where.set_root(window)
    where.set_pos_whole_cartesian(cartesian[0] * zoom, cartesian[1] * zoom)
    where += pan * Coordinate(zoom, zoom)

    pygame.draw.circle(
        window, (0, 0, 0),
        where.get_pos_whole(),
        zoom * (config.get("stationStroke", 2) + config.get("stationSize", 8)))
    
    pygame.draw.circle(
        window, (255, 255, 255),
        where.get_pos_whole(),
        zoom * config.get("stationSize", 8))

    rect: pygame.Rect = lta.get_rect(station["name"], size=24 * zoom)
    rect = _text_pos(where, rect, station["dir"])

    lta.render_to(window, rect, station["name"],
                  fgcolor=(0, 0, 0), size=24 * zoom)

def add_connection(termini: tuple[Coordinate], color: tuple[int, int, int]) -> None:
    if termini[0] == termini[1]: return
    connections.append({"termini": termini, "color": color})

def usr_add_connection(*args, **kwargs) -> None:
    global terminus
    global stationSel
    where: Coordinate = usr_coord_mouse()

    station = find_station(where)
    if station < 0: return

    if not stationSel:
        terminus = station
        stationSel = True
        return

    stationSel = False
    if terminus == station:
        terminus = -1
        return

    color = usr_prompt_color(
        "Enter connection color",
        "What is the connection color? (blank to cancel)"
    )
    
    if color is None: return

    color = int2col(color)

    add_connection(
        (stations[terminus]["where"],
         stations[station]["where"]),
         color
    )

    terminus = -1

def usr_remove_connection(*args, **kwargs) -> None:
    global terminus
    global stationSel
    global connections

    where: Coordinate = usr_coord_mouse()

    station = find_station(where)
    if station < 0: return

    if not stationSel:
        terminus = station
        stationSel = True
        return
    
    connIdx = find_connection((
        stations[terminus]["where"],
        stations[station]["where"]
    ))
    if connIdx < 0: return

    result = tkinter.messagebox.askyesno(
            "Remove connection",
            "Are you sure you want to remove the connection between"
            f"\"{stations[terminus]["name"]}\" and \"{stations[station]["name"]}\"?")
    
    if not result: return
    connections.pop(connIdx)

    terminus = -1
    stationSel = False

def usr_recolor_connection(*args, **kwargs) -> None:
    global terminus
    global stationSel
    global connections

    where: Coordinate = usr_coord_mouse()

    station = find_station(where)
    if station < 0: return

    if not stationSel:
        terminus = station
        stationSel = True
        return
    
    connIdx = find_connection((
        stations[terminus]["where"],
        stations[station]["where"]
    ))
    if connIdx < 0: return

    color = usr_prompt_color(
        "Enter new connection color",
        "What is the new connection color? (blank to cancel)"
    )
    
    if color is None: return
    
    color = int2col(color)
    connections[connIdx]["color"] = color

    terminus = -1
    stationSel = False

def draw_connection(connection: dict[str, Coordinate | tuple[int, int, int]], cidx: int) -> None:
    connections = find_all_connections(connection["termini"])

    try:
        idx = connections.index(cidx)
    except (ValueError, TypeError):
        idx = 0

    for termIdx in range(len(connection["termini"]) - 1):
        t1_c = list(connection["termini"][termIdx].get_pos_whole_cartesian())
        t2_c = list(connection["termini"][termIdx + 1].get_pos_whole_cartesian())

        angle = math.atan2((t2_c[1] - t1_c[1]), (t2_c[0] - t1_c[0]))
        si = math.sin(angle)
        co = math.cos(angle)

        su = idx - (( len(connections) - 1 ) / 2)

        t1coord = Coordinate()
        t1coord.set_root(window)
        t1coord.set_pos_whole_cartesian(t1_c[0] * zoom, t1_c[1] * zoom)
        t1coord += pan * Coordinate(zoom, zoom)

        t2coord = Coordinate()
        t2coord.set_root(window)
        t2coord.set_pos_whole_cartesian(t2_c[0] * zoom, t2_c[1] * zoom)
        t2coord += pan * Coordinate(zoom, zoom)

        offset = Coordinate()
        offset.set_root(window)
        offset.set_pos_whole(
            math.floor(config.get("connectionStroke", 6) * su * si + 0.5),
            math.floor(config.get("connectionStroke", 6) * su * co + 0.5)
        )

        t1 = (t1coord + offset).get_pos_whole()
        t2 = (t2coord + offset).get_pos_whole()

        pygame.draw.line(
            window, connection["color"], t1, t2, 
            pygame.math.clamp(math.floor(config.get("connectionStroke", 6) * zoom), 1, 10000)
        )

def add_river(termini: tuple[Coordinate], color: tuple[int, int, int]) -> None:
    if termini[0] == termini[1]: return
    rivers.append({"termini": termini, "color": color})

def usr_add_river(*args, **kwargs) -> None:
    global riverBegin
    global riverSel
    where: Coordinate = usr_coord_mouse()

    if not riverSel:
        riverBegin = where
        riverSel = True
        return

    riverSel = False
    if riverBegin == where:
        riverBegin = None
        return

    color = color = usr_prompt_color(
        "Enter river color",
        "What is the river color? (blank to cancel)"
    )
    
    if color is None: return

    color = int2col(color)

    add_river(
        (riverBegin, where), color
    )

    riverBegin = None

def usr_remove_river(*args, **kwargs) -> None:
    global riverBegin
    global riverSel
    global rivers

    where: Coordinate = usr_coord_mouse()

    if not riverSel:
        riverBegin = where
        riverSel = True
        return

    riverSel = False
    if riverBegin == where:
        riverBegin = None
        return
    
    rivIdx = find_river((
        riverBegin, where
    ))
    if rivIdx < 0: return

    result = tkinter.messagebox.askyesno(
            "Remove river",
            "Are you sure you want to remove the river between"
            f"\"{riverBegin}\" and \"{where}\"?")
    
    if not result: return
    rivers.pop(rivIdx)

    riverBegin = None

def usr_recolor_river(*args, **kwargs) -> None:
    global riverBegin
    global riverSel
    global rivers

    where: Coordinate = usr_coord_mouse()

    if not riverSel:
        riverBegin = where
        riverSel = True
        return

    riverSel = False
    if riverBegin == where:
        riverBegin = None
        return
    
    rivIdx = find_river((
        riverBegin, where
    ))
    if rivIdx < 0: return

    color = usr_prompt_color(
        "Enter new river color",
        "What is the new river color? (blank to cancel)"
    )
    
    if color is None: return
    
    color = int2col(color)
    rivers[rivIdx]["color"] = color

    riverBegin = None

def draw_river(river: dict[str, Coordinate | tuple[int, int, int]]) -> None:
    for termIdx in range(len(river["termini"]) - 1):
        t1 = river["termini"][termIdx]
        t2 = river["termini"][termIdx + 1]

        t1_c = list(t1.get_pos_whole_cartesian())
        t2_c = list(t2.get_pos_whole_cartesian())

        t1coord = Coordinate()
        t1coord.set_root(window)
        t1coord.set_pos_whole_cartesian(t1_c[0] * zoom, t1_c[1] * zoom)
        t1coord += pan * Coordinate(zoom, zoom)

        t2coord = Coordinate()
        t2coord.set_root(window)
        t2coord.set_pos_whole_cartesian(t2_c[0] * zoom, t2_c[1] * zoom)
        t2coord += pan * Coordinate(zoom, zoom)

        t1 = t1coord.get_pos_whole()
        t2 = t2coord.get_pos_whole()

        riverStroke = pygame.math.clamp(math.floor(config.get("riverStroke", 25) * zoom), 1, 1000)

        pygame.draw.line(
            window, river["color"], t1, t2,
            riverStroke
        )
        pygame.draw.circle(
            window, river["color"], t1,
            riverStroke / 2
        )
        pygame.draw.circle(
            window, river["color"], t2,
            riverStroke / 2
        )

def saveas_file() -> None:
    filename = tkinter.filedialog.asksaveasfilename(
        filetypes=[("KMetroMaker files", "*.kmm")])
    
    if not filename: return
    if not filename.endswith(".kmm"): filename += ".kmm"

    append: list[bytes] = [b"KMM.2\xfe"]
    for station in stations:
        append.append(bytes(station["name"], "utf-8"))
        append.append(b"\x00")
        append.append(
            bytes(str(station["where"].get_pos_whole()[0]),
                  "utf-8"))
        append.append(b"\x01")
        append.append(
            bytes(str(station["where"].get_pos_whole()[1]),
                  "utf-8"))
        append.append(b"\x02")
        append.append(
            bytes(str(station["dir"].value),
                  "utf-8"))
        append.append(b"\x03")
    append.append(b"\xff")
    for connection in connections:
        append.append(
            bytes(str(connection["termini"][0].get_pos_whole()[0]),
                  "utf-8"))
        append.append(b"\x00")
        append.append(
            bytes(str(connection["termini"][0].get_pos_whole()[1]),
                  "utf-8"))
        append.append(b"\x01")
        append.append(
            bytes(str(connection["termini"][1].get_pos_whole()[0]),
                  "utf-8"))
        append.append(b"\x02")
        append.append(
            bytes(str(connection["termini"][1].get_pos_whole()[1]),
                  "utf-8"))
        append.append(b"\x03")
        append.append(
            bytes(str(col2int(connection["color"])),
                  "utf-8"))
        append.append(b"\x04")
    append.append(b"\xff")
    for river in rivers:
        append.append(
            bytes(str(river["termini"][0].get_pos_whole()[0]),
                  "utf-8"))
        append.append(b"\x00")
        append.append(
            bytes(str(river["termini"][0].get_pos_whole()[1]),
                  "utf-8"))
        append.append(b"\x01")
        append.append(
            bytes(str(river["termini"][1].get_pos_whole()[0]),
                  "utf-8"))
        append.append(b"\x02")
        append.append(
            bytes(str(river["termini"][1].get_pos_whole()[1]),
                  "utf-8"))
        append.append(b"\x03")
        append.append(
            bytes(str(col2int(river["color"])),
                  "utf-8"))
        append.append(b"\x04")
    append.append(b"\xfeThank you for using KMetroMaker.\x04\x05")

    with open(filename, "wb") as file:
        file.write(b"".join(append))

def open_file_v1(data: bytes) -> None:
    global stations
    global connections
    global rivers

    stations.clear()
    connections.clear()
    rivers.clear()

    data = data.replace(b"\xff", b"\xfe")
    parts = data.split(b"\xfe")
    
    parts.extend([[], []])

    stationParts = parts[1].split(b"\x03")
    connectionParts = parts[2].split(b"\x04")

    for stationPart in stationParts:
        if not stationPart: continue
        subParts = stationPart.split(b"\x00")
        name = subParts[0]
        subParts = subParts[1].split(b"\x01")
        x = int(subParts[0])
        subParts = subParts[1].split(b"\x02")
        y = int(subParts[0])
        dir = TextDirection(int(subParts[1]))
        where = Coordinate(0, 0)
        where.set_root(window)
        where.set_pos_whole(x, y)
        add_station(where, name.decode(), dir)
    for connectionPart in connectionParts:
        if not connectionPart: continue
        subParts = connectionPart.split(b"\x00")
        x1 = int(subParts[0])
        subParts = subParts[1].split(b"\x01")
        y1 = int(subParts[0])
        subParts = subParts[1].split(b"\x02")
        x2 = int(subParts[0])
        subParts = subParts[1].split(b"\x03")
        y2 = int(subParts[0])
        color = int(subParts[1])
        t1 = Coordinate(0, 0)
        t1.set_root(window)
        t1.set_pos_whole(x1, y1)
        t2 = Coordinate(0, 0)
        t2.set_root(window)
        t2.set_pos_whole(x2, y2)
        add_connection((t1, t2), int2col(color))

def open_file_v2(data: bytes) -> None:
    global stations
    global connections
    global rivers

    stations.clear()
    connections.clear()
    rivers.clear()

    data = data.replace(b"\xff", b"\xfe")
    parts = data.split(b"\xfe")
    
    parts.extend([[], []])

    stationParts = parts[1].split(b"\x03")
    connectionParts = parts[2].split(b"\x04")
    riverParts = parts[3].split(b"\x04")

    for stationPart in stationParts:
        if not stationPart: continue
        subParts = stationPart.split(b"\x00")
        name = subParts[0]
        subParts = subParts[1].split(b"\x01")
        x = int(subParts[0])
        subParts = subParts[1].split(b"\x02")
        y = int(subParts[0])
        dir = TextDirection(int(subParts[1]))
        where = Coordinate(0, 0)
        where.set_root(window)
        where.set_pos_whole(x, y)
        add_station(where, name.decode(), dir)
    for connectionPart in connectionParts:
        if not connectionPart: continue
        subParts = connectionPart.split(b"\x00")
        x1 = int(subParts[0])
        subParts = subParts[1].split(b"\x01")
        y1 = int(subParts[0])
        subParts = subParts[1].split(b"\x02")
        x2 = int(subParts[0])
        subParts = subParts[1].split(b"\x03")
        y2 = int(subParts[0])
        color = int(subParts[1])
        t1 = Coordinate(0, 0)
        t1.set_root(window)
        t1.set_pos_whole(x1, y1)
        t2 = Coordinate(0, 0)
        t2.set_root(window)
        t2.set_pos_whole(x2, y2)
        add_connection((t1, t2), int2col(color))
    for riverPart in riverParts:
        if not riverPart: continue
        subParts = riverPart.split(b"\x00")
        x1 = int(subParts[0])
        subParts = subParts[1].split(b"\x01")
        y1 = int(subParts[0])
        subParts = subParts[1].split(b"\x02")
        x2 = int(subParts[0])
        subParts = subParts[1].split(b"\x03")
        y2 = int(subParts[0])
        color = int(subParts[1])
        t1 = Coordinate(0, 0)
        t1.set_root(window)
        t1.set_pos_whole(x1, y1)
        t2 = Coordinate(0, 0)
        t2.set_root(window)
        t2.set_pos_whole(x2, y2)
        add_river((t1, t2), int2col(color))
    
def open_file() -> None:
    filename = tkinter.filedialog.askopenfilename(
        filetypes=[("KMetroMaker files", "*.kmm")])
    
    if not filename: return

    with open(filename, "rb") as file:
        data = file.read()

    if data.startswith(b"KMM.1\xfe"):
        open_file_v1(data)
    elif data.startswith(b"KMM.2\xfe"):
        open_file_v2(data)
    else:
        tkinter.messagebox.showerror("Invalid file",
                                     "The file selected is not a valid KMetroMaker file.")
        return
    
    orpan.set_pos(0, 0)
    pan.set_pos(0, 0)

def export_image_file() -> None:
    filename = tkinter.filedialog.asksaveasfilename(
        filetypes=[("PNG files", "*.png")])
    
    if not filename: return
    if not filename.endswith(".png"): filename += ".png"

    pygame.image.save(window, filename)

def handle_skeys(keys: pygame.key.ScancodeWrapper) -> None:
    if keys[pygame.K_r]:
        usr_remove_station()
        return
    if keys[pygame.K_n]:
        usr_rename_station()
        return
    if keys[pygame.K_d]:
        usr_change_text_dir_station()
        return
    usr_add_station()
    return

def handle_ckeys(keys: pygame.key.ScancodeWrapper) -> None:
    if keys[pygame.K_r]:
        usr_remove_connection()
        return
    if keys[pygame.K_n]:
        usr_recolor_connection()
        return
    usr_add_connection()
    return

def handle_vkeys(keys: pygame.key.ScancodeWrapper) -> None:
    if keys[pygame.K_r]:
        usr_remove_river()
        return
    if keys[pygame.K_n]:
        usr_recolor_river()
        return
    usr_add_river()
    return

def handle_keys_left(keys: pygame.key.ScancodeWrapper) -> None:
    if keys[pygame.K_LALT] or keys[pygame.K_RALT]:
        if keys[pygame.K_c]:
            handle_ckeys(keys)
            return
        if keys[pygame.K_s]:
            handle_skeys(keys)
            return  
        if keys[pygame.K_v]:
            handle_vkeys(keys)
            return  

def scroll_right(mousePos: Coordinate) -> None:
    global pan
    pan = orpan + (mousePos - rightDownAt)
   
def handle_keys_keyboard(keys: pygame.key.ScancodeWrapper) -> None:
    global zoom
    if keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
        if keys[pygame.K_s]:
            saveas_file()
            return
        if keys[pygame.K_o]:
            open_file()
            return
        if keys[pygame.K_e]:
            export_image_file()
            return
        if keys[pygame.K_MINUS]:
            zoom /= 2
            if zoom < 0.03125: zoom = 0.03125
            return
        if keys[pygame.K_PLUS] or (
            (keys[pygame.K_EQUALS] and 
                (keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL])
            )
        ):
            zoom *= 2
            if zoom > 32: zoom = 32
            return
        if keys[pygame.K_0]:
            zoom = 1
            pan.set_pos(0, 0)
            orpan.set_pos(0, 0)
            return
        return
    
def handle_events_and_keys() -> None:
    global running
    global rightDown
    global rightDownAt
    global orpan

    get = pygame.event.get()
    keys = pygame.key.get_pressed()
    mousebuttons = pygame.mouse.get_pressed()

    mouseAt = Coordinate()
    mouseAt.set_root(window)
    mouseAt.set_pos_whole(
        pygame.mouse.get_pos()[0],
        pygame.mouse.get_pos()[1]
    )

    for event in get:
        if event.type == pygame.QUIT:
            running = False
            return
        
        if event.type == pygame.KEYDOWN:
            handle_keys_keyboard(keys)
            continue

        if event.type == pygame.MOUSEBUTTONDOWN:
            if mousebuttons[0]: continue
            if mousebuttons[2]:
                orpan = pan.copy()
                rightDownAt = mouseAt.copy()
                rightDown = True
                continue
            continue

        if event.type == pygame.MOUSEBUTTONUP:
            handle_keys_left(keys)
            if mousebuttons[2]:
                orpan = pan.copy()
                rightDownAt = None
                rightDown = False
                continue
            continue

        if event.type == pygame.MOUSEMOTION:
            if mousebuttons[0]: continue
            if mousebuttons[2]:
                scroll_right(mouseAt)
                continue
            continue

def main() -> None:
    while running:
        pygame.draw.rect(
            window, (255, 255, 255),
            (0, 0, window.get_width(), window.get_height())
        ) 
            
        for river in rivers:
            draw_river(river)

        for cidx, connection in enumerate(connections):
            draw_connection(connection, cidx)

        for station in stations:
            draw_station(station)

        handle_events_and_keys()

        pygame.display.flip()

main()
pygame.quit()
