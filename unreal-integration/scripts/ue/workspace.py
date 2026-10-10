"""A table the avatar arranges objects on, shown in the right half of a split screen (CAM_Workspace).

Run inside the editor (PyJobs, or the voice bridge's [[...]] actions):
  import workspace
  workspace.setup()                                  # table, box, plate, camera, colour materials (idempotent)
  workspace.do("place red sphere on box")            # spawn, or move if "red sphere" exists
  workspace.do("place blue cube left of red sphere") # relations: on, left of, right of, in front of, behind, next to
  workspace.do("remove red sphere"); workspace.do("clear")
  workspace.do("build small dog on table: brown cube 0 0 14 24 10 10; brown cube 14 0 22 9 9 9; ...")  # see build()
  workspace.do("place treasure chest left of box")    # game-ready asset from ASSETS
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
PART = "WS_PART"  # tag of the non-root parts of a built object (attached to its root, not listed in the scene)
STAGE = ORIGIN + unreal.Vector(0, 0, -1000)  # new objects are spawned here, then moved into place
MAX_PARTS = 30
FIT = (60.0, 40.0, 50.0)  # largest built object, cm along right / toward the viewer / up (table top is 140 x 90)
PART_RE = re.compile(r"([a-z]+)\s+([a-z]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)")
# Game-ready props: name -> (folder of its static meshes, scale). The treasure chest is Poly Haven's "Treasure Chest"
# (CC0, Rico Cilliers; 2k glTF, PBR textures), imported with Interchange into these 5 part meshes (bottom, lid, handles,
# lock) that share one origin, so the parts are spawned at one point and grouped like a built object. 96 x 52 x 62 cm
# in reality, 0.4 = 38 x 21 x 25 cm on the table. Its front (lock) is mesh +Y.
ASSETS = {"treasure chest": ("/Game/Workspace/Assets/TreasureChest/treasure_chest_2k/StaticMeshes", 0.4)}
ASSET_ALIAS = {"chest": "treasure chest", "treasure": "treasure chest", "treasure box": "treasure chest",
               "pirate chest": "treasure chest"}
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


def _spawn(label, shape, color, location, scale, tags=None, yaw=0.0):
    a = EAS.spawn_actor_from_object(unreal.load_asset(MESH[shape]), location, unreal.Rotator(0, 0, yaw))
    a.set_actor_label(label)
    a.set_actor_scale3d(scale)
    a.static_mesh_component.set_material(0, _material(color))
    a.tags = tags if tags is not None else [TAG, f"shape:{shape}", f"color:{color}"]
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
    render_fixes()
    return f"{face} -> {keys[0]}, CAM_Workspace -> {keys[1]}"


def render_fixes():
    """Hair look for the close-up (measured on 2x zooms of the face pane):
    - Each pane picks the MetaHuman LOD from its own camera (close: LOD 0, strand hair; far: LOD 2, card hair), so
      with two panes the hair swapped strands <-> cards every frame and flickered. Pin LOD 0.
    - The hair's shadow on the skin had 0.3 cm stair steps = the hair voxel size: voxels 0.1 cm, deep shadows on the
      sun (supersampled), sun angle 1 deg for a softer edge.
    - Peach fuzz drew a dotted bright/dark line along the jaw silhouette: hidden.
    - Shadow edges (hair on the face, box on the table) were saw-toothed: virtual shadow maps pick their resolution
      from the small panes. Directional LOD bias -1.5 = sharper pages; edges came out straight."""
    for cmd in ("r.HairStrands.Voxelization.Virtual.VoxelWorldSize 0.1", "r.HairStrands.DeepShadow.SuperSampling 1",
                "r.Shadow.Virtual.ResolutionLodBiasDirectional -1.5"):
        unreal.SystemLibrary.execute_console_command(None, cmd)
    for a in EAS.get_all_level_actors():
        sync = a.get_component_by_class(unreal.LODSyncComponent)
        if sync:
            sync.set_editor_property("forced_lod", 0)
            for g in a.get_components_by_class(unreal.GroomComponent):
                if g.get_name() == "Fuzz":
                    g.set_visibility(False)
        if isinstance(a, unreal.DirectionalLight):
            a.light_component.set_editor_property("cast_deep_shadow", True)
            a.light_component.set_editor_property("light_source_angle", 1.0)


def scene():
    return [a.get_actor_label() for a in _actors()]


def _group(a):
    """An object plus the parts attached to it (a built object moves and is removed as a whole)."""
    return [a] + list(a.get_attached_actors())


def _bounds(a):
    """Center and half extents of an object including its attached parts."""
    lo = hi = None
    for x in _group(a):
        o, e = x.get_actor_bounds(False)
        l, h = o - e, o + e
        lo = l if lo is None else unreal.Vector(min(lo.x, l.x), min(lo.y, l.y), min(lo.z, l.z))
        hi = h if hi is None else unreal.Vector(max(hi.x, h.x), max(hi.y, h.y), max(hi.z, h.z))
    return (lo + hi) * 0.5, (hi - lo) * 0.5


def _boxes(skip):
    return [_bounds(a) for a in _actors() if a not in skip and a.get_actor_label() != "table"]


def _free(loc, half, skip, boxes=None):
    """True if a box at loc with half extents half overlaps no object (the table doesn't count)."""
    for o, e in boxes if boxes is not None else _boxes(skip):
        if (abs(o.x - loc.x) < e.x + half.x + GAP and abs(o.y - loc.y) < e.y + half.y + GAP
                and abs(o.z - loc.z) < e.z + half.z):
            return False
    return True


def _nearest_free(want, half, skip, t_o, t_e, top):
    """The free spot on the table top closest to want (5 cm grid), or None if the table is full."""
    boxes, cands = _boxes(skip), []
    nx, ny = int(2 * (t_e.x - half.x) / 5), int(2 * (t_e.y - half.y) / 5)
    for i in range(nx + 1):
        for j in range(ny + 1):
            cands.append(unreal.Vector(t_o.x - t_e.x + half.x + 5 * i, t_o.y - t_e.y + half.y + 5 * j, top + half.z))
    cands.sort(key=lambda c: (c.x - want.x) ** 2 + (c.y - want.y) ** 2)
    return next((c for c in cands if _free(c, half, skip, boxes)), None)


def _axes():
    """Horizontal unit vectors (right, toward the camera) as the visitor sees the table through CAM_Workspace."""
    cam = _camera()
    right = cam.get_actor_right_vector() if cam else unreal.Vector(1, 0, 0)
    right = unreal.Vector(right.x, right.y, 0).normal()
    toward = unreal.Vector(-right.y, right.x, 0)
    if cam and (cam.get_actor_location() - ORIGIN).dot(toward) < 0:
        toward = toward * -1.0
    return right, toward


def _label(base):
    label, n = base, 2
    while _find(label):
        label, n = f"{base} {n}", n + 1
    return label


def _destroy(a):
    for x in _group(a):
        x.destroy_actor()


def _place(mover, rel, target_name):
    """Move mover (with its parts) rel of target, on the table. Returns (ok, "<relation> <target>" or error)."""
    table = _find("table")
    t_o, t_e = _bounds(table)
    top = t_o.z + t_e.z
    target = _find(target_name)
    if target is None:
        return False, f"no object called '{target_name}'"
    if mover == target:
        return False, "an object can't be placed relative to itself"
    m_o, h = _bounds(mover)
    right, toward = _axes()
    o, e = _bounds(target)
    if rel == "on" and target == table:
        loc = None
        for dy in (20, -20, 0):
            for dx in (35, -35, 55, -55, 15, -15):
                cand = unreal.Vector(t_o.x + dx, t_o.y + dy, top + h.z)
                if _free(cand, h, [mover]):
                    loc = cand
                    break
            if loc:
                break
        loc = loc or unreal.Vector(t_o.x, t_o.y, top + h.z)
    elif rel == "on":
        if len(_group(target)) > 1 and "asset" not in [str(t) for t in target.tags]:  # built: on its main part, not the ear tips
            o, e = target.get_actor_bounds(False)
        loc = unreal.Vector(o.x, o.y, o.z + e.z + h.z)
    else:
        d = {"left": right * -1.0, "right": right, "next": right, "front": toward, "behind": toward * -1.0}[rel]
        loc = unreal.Vector(o.x, o.y, top + h.z) + d * (abs(d.x) * (e.x + h.x) + abs(d.y) * (e.y + h.y) + GAP)
        for _ in range(6):  # occupied: step further out
            if _free(loc, h, [mover, target]):
                break
            loc = loc + d * (abs(d.x) * 2 * h.x + abs(d.y) * 2 * h.y + GAP)
    # keep it on the table; if that lands on something (e.g. the stepped-out spot was off the edge), take the
    # nearest free spot instead of overlapping
    loc.x = max(t_o.x - t_e.x + h.x, min(t_o.x + t_e.x - h.x, loc.x))
    loc.y = max(t_o.y - t_e.y + h.y, min(t_o.y + t_e.y - h.y, loc.y))
    if not (rel == "on" and target != table) and not _free(loc, h, [mover]):
        loc = _nearest_free(loc, h, [mover], t_o, t_e, top) or loc
    mover.set_actor_location(mover.get_actor_location() + (loc - m_o), False, False)
    return True, f"{SAY[rel]} {target.get_actor_label()}"


def import_gltf(path, dest="/Game/Workspace/Assets/TreasureChest"):
    """One-time import of a downloaded glTF (e.g. Poly Haven's treasure_chest_2k.gltf with its .bin and textures/)."""
    t = unreal.AssetImportTask()
    for k, v in (("filename", path), ("destination_path", dest), ("automated", True), ("save", True),
                 ("replace_existing", True)):
        t.set_editor_property(k, v)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    return list(t.get_editor_property("imported_object_paths"))


def _spawn_asset(name):
    """Spawn a game-ready prop from ASSETS at STAGE, facing the visitor; parts attached to the largest one."""
    folder, scale = ASSETS[name]
    meshes = [unreal.load_asset(p) for p in unreal.EditorAssetLibrary.list_assets(folder, False, False)]
    meshes = [m for m in meshes if isinstance(m, unreal.StaticMesh)]
    vol = lambda m: m.get_bounds().box_extent.x * m.get_bounds().box_extent.y * m.get_bounds().box_extent.z
    meshes.sort(key=vol, reverse=True)
    _, toward = _axes()
    yaw = math.degrees(math.atan2(-toward.x, toward.y))  # mesh +Y (the front) toward the viewer
    label = _label(name)
    actors = []
    for i, m in enumerate(meshes):
        a = EAS.spawn_actor_from_object(m, STAGE, unreal.Rotator(0, 0, yaw))
        a.set_actor_label(label if i == 0 else f"{label} {m.get_name().replace('treasure_chest_', '')}")
        a.set_actor_scale3d(unreal.Vector(scale, scale, scale))
        a.tags = [TAG, "asset"] if i == 0 else [PART]
        actors.append(a)
    for a in actors[1:]:
        a.attach_to_actor(actors[0], "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                          unreal.AttachmentRule.KEEP_WORLD, False)
    return actors[0]


def build(spec):
    """Build an object from primitives: "<name> [<relation> <target>]: <color> <shape> x y z w d h; ..."
    In cm, as the visitor sees it: x right, y toward the viewer, z up from the ground; x y z is the part's center,
    w d h its size along x y z. Scaled down to fit FIT. Parts are attached to the largest one, which carries the name."""
    head, _, body = spec.partition(":")
    rel = next(((p, k) for p, k in RELATIONS if f" {p} " in f" {head} "), None)
    name, target = ([x.strip() for x in f" {head} ".split(f" {rel[0]} ", 1)] if rel else (head.strip(), "table"))
    name = re.sub(r"^(the|a|an)\s+", "", name) or "thing"
    parts = []
    for m in PART_RE.finditer(body):
        shape = ALIAS.get(m.group(2), m.group(2))
        nums = [float(v) for v in m.groups()[2:]]
        parts.append((m.group(1) if m.group(1) in COLOR else "grey", shape if shape in MESH else "cube",
                      nums[:3], [max(0.5, v) for v in nums[3:]]))
    parts = parts[:MAX_PARTS]
    if not parts:
        return "no parts given (format: <color> <shape> x y z w d h; ...)"
    lo = [min(p[2][i] - p[3][i] / 2 for p in parts) for i in range(3)]
    hi = [max(p[2][i] + p[3][i] / 2 for p in parts) for i in range(3)]
    k = min([1.0] + [FIT[i] / (hi[i] - lo[i]) for i in range(3) if hi[i] > lo[i]])
    right, toward = _axes()
    yaw = math.degrees(math.atan2(right.y, right.x))  # local X = the visitor's right, local Y = toward the viewer
    label = _label(name)
    root_i = max(range(len(parts)), key=lambda i: parts[i][3][0] * parts[i][3][1] * parts[i][3][2])
    actors = []
    for i, (color, shape, (x, y, z), (w, d, h)) in enumerate(parts):
        loc = STAGE + right * (x * k) + toward * (y * k) + unreal.Vector(0, 0, z * k)
        tags = [TAG, "built"] if i == root_i else [PART]
        actors.append(_spawn(label if i == root_i else f"{label} part {i + 1}", shape, color, loc,
                             unreal.Vector(w * k / 100, d * k / 100, h * k / 100), tags, yaw))
    root = actors[root_i]
    for a in actors:
        if a != root:
            a.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                              unreal.AttachmentRule.KEEP_WORLD, False)
    ok, where = _place(root, rel[1] if rel else "on", target)
    if not ok:
        _destroy(root)
        return where
    scaled = "" if k == 1 else f" (scaled to {k:.0%})"
    return f"built {label} from {len(parts)} parts{scaled} {where}"


def do(command):
    """Parse and run one command: place <color> <shape|existing name> <relation> <target> | build <name> [<relation>
    <target>]: <parts> | remove <name> | clear."""
    c = command.strip().lower().rstrip(".!")
    try:
        if c == "clear":
            for a in _actors():
                if a.get_actor_label() not in ("table", "box", "plate"):
                    _destroy(a)
            for a in EAS.get_all_level_actors():  # parts left over from an interrupted build
                if PART in [str(t) for t in a.tags]:
                    a.destroy_actor()
            result = "cleared the table"
        elif c.startswith("build "):
            result = build(c[6:])
        elif c.startswith(("remove ", "delete ")):
            a = _find(c.split(" ", 1)[1])
            if a and a.get_actor_label() != "table":
                _destroy(a)
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
            asset = ASSET_ALIAS.get(what, what)
            if not existing and asset in ASSETS:
                a = _spawn_asset(asset)
                ok, where = _place(a, rel[1], target)
                if not ok:
                    _destroy(a)
                result = f"placed {a.get_actor_label()} {where}" if ok else where
            elif existing:
                ok, where = _place(existing, rel[1], target)
                result = f"moved {existing.get_actor_label()} {where}" if ok else where
            else:
                words = what.split()
                color = next((w for w in words if w in COLOR), "red")
                shape = next((ALIAS.get(w, w) for w in words if ALIAS.get(w, w) in MESH), None)
                if shape is None:  # "place red car ...": not a primitive, so no stand-in cube
                    return f"'{what}' is not a basic shape (use build) | scene: {', '.join(scene())}"
                a = _spawn(_label(f"{color} {shape}"), shape, color, STAGE,
                           unreal.Vector(SIZE / 100, SIZE / 100, SIZE / 100))
                ok, where = _place(a, rel[1], target)
                if not ok:
                    a.destroy_actor()
                result = f"placed {a.get_actor_label()} {where}" if ok else where
        else:
            result = f"unknown command '{command}'"
    except Exception as ex:  # report to the bridge instead of failing the job
        result = f"failed: {ex}"
    return f"{result} | scene: {', '.join(scene())}"
