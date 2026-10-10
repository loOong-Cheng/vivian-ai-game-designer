"""A table the avatar arranges objects on, shown in the right half of a split screen (CAM_Workspace).

Run inside the editor (PyJobs, or the voice bridge's [[...]] actions):
  import workspace
  workspace.setup()                                  # table, box, plate, camera, colour materials (idempotent)
  workspace.do("place red sphere on box")            # spawn, or move if "red sphere" exists
  workspace.do("place blue cube left of red sphere") # relations: on, left of, right of, in front of, behind, next to
  workspace.do("remove red sphere"); workspace.do("clear")
Left/right/front/behind are from CAM_Workspace's point of view, i.e. the visitor's.
Every call returns "<what happened> | scene: name, name, ...".
"""
import math
import re

import unreal

ORIGIN = unreal.Vector(400.0, 0.0, 0.0)  # far outside CAM_Face's view (it looks along -Y at x ~ 0)
TAG = "WS"
FOLDER = "/Game/Workspace"
SIZE = 15.0  # cm, placed objects
GAP = 3.0
CAM_OFFSET, CAM_AIM, CAM_FOCAL = unreal.Vector(0, 140, 185), unreal.Vector(0, 0, 72), 24.0  # whole table in view
MESH = {"cube": "/Engine/BasicShapes/Cube.Cube", "sphere": "/Engine/BasicShapes/Sphere.Sphere",
        "cylinder": "/Engine/BasicShapes/Cylinder.Cylinder", "cone": "/Engine/BasicShapes/Cone.Cone"}
ALIAS = {"ball": "sphere", "box": "cube", "block": "cube", "cubes": "cube", "spheres": "sphere", "balls": "sphere",
         "can": "cylinder", "tube": "cylinder", "pillar": "cylinder", "pyramid": "cone"}
COLOR = {"red": (0.8, 0.03, 0.03), "green": (0.05, 0.55, 0.08), "blue": (0.03, 0.12, 0.8), "yellow": (0.9, 0.75, 0.02),
         "white": (0.85, 0.85, 0.85), "black": (0.02, 0.02, 0.02), "orange": (0.9, 0.3, 0.02),
         "purple": (0.4, 0.05, 0.6), "pink": (0.9, 0.35, 0.5), "brown": (0.35, 0.18, 0.07), "grey": (0.3, 0.3, 0.3)}
RELATIONS = [("on top of", "on"), ("on", "on"), ("to the left of", "left"), ("left of", "left"),
             ("to the right of", "right"), ("right of", "right"), ("in front of", "front"), ("behind", "behind"),
             ("next to", "next"), ("beside", "next")]
SAY = {"on": "on", "left": "left of", "right": "right of", "front": "in front of", "behind": "behind", "next": "next to"}
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _actors():
    return [a for a in EAS.get_all_level_actors() if TAG in [str(t) for t in a.tags]]


def _find(name):
    name = re.sub(r"^(the|a|an)\s+", "", name.strip().lower())
    for a in _actors():
        if a.get_actor_label().lower() == name:
            return a
    return None


def _camera():
    return next((a for a in EAS.get_all_level_actors() if a.get_actor_label() == "CAM_Workspace"), None)


def _material(color):
    path = f"{FOLDER}/MI_WS_{color}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.load_asset(path)
    mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        f"MI_WS_{color}", FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    unreal.MaterialEditingLibrary.set_material_instance_parent(mi, unreal.load_asset("/Engine/BasicShapes/BasicShapeMaterial"))
    r, g, b = COLOR[color]
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(r, g, b, 1.0))
    unreal.EditorAssetLibrary.save_asset(path)
    return mi


def _spawn(label, shape, color, location, scale):
    a = EAS.spawn_actor_from_object(unreal.load_asset(MESH[shape]), location, unreal.Rotator(0, 0, 0))
    a.set_actor_label(label)
    a.set_actor_scale3d(scale)
    a.static_mesh_component.set_material(0, _material(color))
    a.tags = [TAG, f"shape:{shape}", f"color:{color}"]
    return a


def setup():
    """Create the table scene and camera once; returns the scene list."""
    if not _find("table"):
        _spawn("table", "cube", "white", ORIGIN + unreal.Vector(0, 0, 37.5), unreal.Vector(1.4, 0.9, 0.75))
        _spawn("box", "cube", "brown", ORIGIN + unreal.Vector(0, 0, 75 + 15), unreal.Vector(0.3, 0.3, 0.3))
        _spawn("plate", "cylinder", "white", ORIGIN + unreal.Vector(-40, -15, 75 + 1.5), unreal.Vector(0.3, 0.3, 0.03))
    cam = _camera()
    if not cam:
        cam = EAS.spawn_actor_from_class(unreal.CineCameraActor, ORIGIN, unreal.Rotator(0, 0, 0))
        cam.set_actor_label("CAM_Workspace")
        fs = cam.get_cine_camera_component().get_editor_property("focus_settings")
        fs.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE)
        cam.get_cine_camera_component().set_editor_property("focus_settings", fs)
    loc, aim = ORIGIN + CAM_OFFSET, ORIGIN + CAM_AIM
    cam.set_actor_location_and_rotation(loc, unreal.MathLibrary.find_look_at_rotation(loc, aim), False, False)
    cam.get_cine_camera_component().set_editor_property("current_focal_length", CAM_FOCAL)
    return scene()


def split_screen(face="CAM_Face"):
    """Pilot the face camera in viewport 0 and CAM_Workspace in viewport 1 (set the Two Panes layout first:
    viewport toolbar, rightmost menu > TWO PANES; there is no Python API for the layout)."""
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    keys = les.get_viewport_config_keys()
    if len(keys) < 2:
        return "only one viewport: pick a TWO PANES layout first"
    cams = {a.get_actor_label(): a for a in EAS.get_all_level_actors()}
    les.pilot_level_actor(cams[face], keys[0])
    les.pilot_level_actor(_camera(), keys[1])
    # Each pane picks the MetaHuman LOD from its own camera (close: LOD 0, strand hair; far: LOD 2, card hair), so
    # with two panes the hair swapped strands <-> cards every frame and flickered. Pin LOD 0.
    for a in EAS.get_all_level_actors():
        sync = a.get_component_by_class(unreal.LODSyncComponent)
        if sync:
            sync.set_editor_property("forced_lod", 0)
    return f"{face} -> {keys[0]}, CAM_Workspace -> {keys[1]}"


def scene():
    return [a.get_actor_label() for a in _actors()]


def _bounds(a):
    o, e = a.get_actor_bounds(False)
    return o, e


def _free(loc, radius, skip):
    for a in _actors():
        if a in skip or a.get_actor_label() == "table":
            continue
        o, e = _bounds(a)
        if abs(o.z - loc.z) < e.z + radius and math.hypot(o.x - loc.x, o.y - loc.y) < max(e.x, e.y) + radius:
            return False
    return True


def _place(color, shape, rel, target_name, name=None):
    table = _find("table")
    t_o, t_e = _bounds(table)
    top = t_o.z + t_e.z
    h = SIZE / 2
    mover = _find(name) if name else None
    target = _find(target_name)
    if target is None:
        return f"no object called '{target_name}'"
    if mover is not None and mover == target:
        return "an object can't be placed relative to itself"
    cam = _camera()
    right = cam.get_actor_right_vector() if cam else unreal.Vector(1, 0, 0)
    right = unreal.Vector(right.x, right.y, 0).normal()
    toward = unreal.Vector(-right.y, right.x, 0)  # horizontal, pointing at the camera side
    if cam and (cam.get_actor_location() - t_o).dot(toward) < 0:
        toward = toward * -1.0
    o, e = _bounds(target)
    skip = [mover] if mover else []
    if rel == "on" and target == table:
        loc = None
        for dy in (20, -20, 0):
            for dx in (35, -35, 55, -55, 15, -15):
                cand = unreal.Vector(t_o.x + dx, t_o.y + dy, top + h)
                if _free(cand, h + GAP, skip):
                    loc = cand
                    break
            if loc:
                break
        loc = loc or unreal.Vector(t_o.x, t_o.y, top + h)
    elif rel == "on":
        loc = unreal.Vector(o.x, o.y, o.z + e.z + h)
    else:
        d = {"left": right * -1.0, "right": right, "next": right, "front": toward, "behind": toward * -1.0}[rel]
        reach = abs(d.x) * e.x + abs(d.y) * e.y + h + GAP
        loc = unreal.Vector(o.x, o.y, top + h) + d * reach
        for _ in range(6):  # occupied: step further out
            if _free(loc, h + GAP, skip + [target]):
                break
            loc = loc + d * (2 * h + GAP)
    # keep it on the table
    loc.x = max(t_o.x - t_e.x + h, min(t_o.x + t_e.x - h, loc.x))
    loc.y = max(t_o.y - t_e.y + h, min(t_o.y + t_e.y - h, loc.y))
    if mover:
        mover.set_actor_location(loc, False, False)
        return f"moved {mover.get_actor_label()} {SAY[rel]} {target.get_actor_label()}"
    label, n = f"{color} {shape}", 2
    while _find(label):
        label, n = f"{color} {shape} {n}", n + 1
    _spawn(label, shape, color, loc, unreal.Vector(SIZE / 100, SIZE / 100, SIZE / 100))
    return f"placed {label} {SAY[rel]} {target.get_actor_label()}"


def do(command):
    """Parse and run one command: place <color> <shape|existing name> <relation> <target> | remove <name> | clear."""
    c = command.strip().lower().rstrip(".!")
    try:
        if c == "clear":
            for a in _actors():
                if a.get_actor_label() not in ("table", "box", "plate"):
                    a.destroy_actor()
            result = "cleared the table"
        elif c.startswith(("remove ", "delete ")):
            a = _find(c.split(" ", 1)[1])
            if a and a.get_actor_label() != "table":
                a.destroy_actor()
                result = "removed " + c.split(" ", 1)[1]
            else:
                result = "nothing to remove called " + c.split(" ", 1)[1]
        elif c.startswith(("place ", "put ", "move ")):
            body = c.split(" ", 1)[1]
            rel = next(((phrase, key) for phrase, key in RELATIONS if f" {phrase} " in f" {body} "), None)
            if not rel:
                return f"no position in '{command}' | scene: {', '.join(scene())}"
            what, target = [s.strip() for s in f" {body} ".split(f" {rel[0]} ", 1)]
            what = re.sub(r"^(the|a|an)\s+", "", what)
            existing = _find(what)
            if existing:
                result = _place(None, None, rel[1], target, name=existing.get_actor_label())
            else:
                words = what.split()
                color = next((w for w in words if w in COLOR), "red")
                shape = next((ALIAS.get(w, w) for w in words if ALIAS.get(w, w) in MESH), "cube")
                result = _place(color, shape, rel[1], target)
        else:
            result = f"unknown command '{command}'"
    except Exception as ex:  # report to the bridge instead of failing the job
        result = f"failed: {ex}"
    return f"{result} | scene: {', '.join(scene())}"
