"""Sensor files and rigs of them: a few USD edits, and what a sensor's schemas say it has.

A sensor file's default prim is one sensor (a `Camera`, an `OmniLidar`, or an `Xform` for an
IMU or GNSS antenna) with its kind's schema applied (`SCHEMAS`), referencing its maker's asset,
its own transform cleared. A rig file's default prim is the origin (the frame that carries
it); each sensor is an Xform under it, placed by translate and rotateXYZ, holding the sensor
(named as it is) referencing a sensor file, and whatever the rig sets over the file is
authored on that. A sensor's own transform is left empty: outside Isaac Sim USD does not place
an OmniLidar by its own. Settings are the
attributes the sensor's schemas define: `properties` lists them, `set` sets one.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pxr import Sdf, Usd, UsdGeom

from . import readout

#: The API schema marking a prim as a sensor of each kind (this library's, `schema/`).
SCHEMAS = {
    "camera": "SensorCameraAPI",
    "lidar": "SensorLidarAPI",
    "imu": "SensorImuAPI",
    "gnss": "SensorGnssAPI",
}
#: An IMU's or a GNSS antenna's rate, Hz; a camera's and a lidar's is NVIDIA's `TICK_RATE`.
RATE = {"imu": "sensor:imu:rateHz", "gnss": "sensor:gnss:rateHz"}
TICK_RATE = "omni:sensor:tickRate"
#: How long a camera's rolling shutter takes to read its rows, seconds.
READOUT = "sensor:camera:readoutSeconds"
#: How each kind is turned to look along the origin's +Y, +Z up (a camera looks down its -Z,
#: a lidar along its +X).
AHEAD = {
    "camera": (90.0, 0.0, 0.0),
    "lidar": (0.0, 0.0, 90.0),
    "imu": (0.0, 0.0, 0.0),
    "gnss": (0.0, 0.0, 0.0),
}
#: The OmniLens models a camera's lens can be switched between (`change` its
#: `omni:lensdistortion:model`), with NVIDIA's API schema each is.
LENSES = {
    "opencvPinhole": "OmniLensDistortionOpenCvPinholeAPI",
    "opencvFisheye": "OmniLensDistortionOpenCvFisheyeAPI",
}
MODEL = "omni:lensdistortion:model"
_COEFFICIENTS = {
    "opencvPinhole": ("k1", "k2", "k3", "k4", "k5", "k6", "p1", "p2", "s1", "s2", "s3", "s4"),
    "opencvFisheye": ("k1", "k2", "k3", "k4"),
}
_PLAIN = {"camera": "Camera", "imu": "Xform", "gnss": "Xform"}
_OPS = ["xformOp:translate", "xformOp:rotateXYZ"]
#: What every prim has (visibility, purpose, ...): not a sensor's setting.
_EVERY_PRIM = frozenset(Usd.SchemaRegistry().FindConcretePrimDefinition("Xform").GetPropertyNames())


@dataclass(frozen=True)
class Pose:
    """From a rig's origin: `translate` (m), then `rotate` degrees about X, then Y, then Z."""

    translate: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotate: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class Mount:
    """A sensor on a rig: its name, kind, sensor file, pose, whether it is on (its prim active),
    and the attributes the rig sets over the file."""

    name: str
    kind: str
    sensor: Path
    pose: Pose
    active: bool
    changed: tuple[str, ...]


@dataclass(frozen=True)
class Property:
    """An attribute a sensor has, as its schema describes it: `type` USD's type name, `schema`
    the one defining it (None: in none), `choices` its allowed tokens, `set_here` whether the
    file asked about sets it."""

    name: str
    type: str
    value: Any
    schema: str | None
    label: str
    group: str
    doc: str
    choices: tuple[str, ...]
    set_here: bool


def kind_of(prim: Usd.Prim) -> str | None:
    """The kind of sensor `prim` is (its `SCHEMAS` applied, registered or not), else None."""
    listed = prim.GetMetadata("apiSchemas")
    applied = listed.ApplyOperations([]) if listed else []
    return next((k for k, s in SCHEMAS.items() if s in applied), None)


def make_sensor(
    file: str | Path,
    kind: str,
    maker: str | Path | None = None,
    prim: str | None = None,
    about: str = "",
) -> Path:
    """A sensor file of `kind`: referencing `prim` of `maker` (its default prim when None), or
    (no maker) a plain camera, IMU or GNSS antenna."""
    stage, file = Usd.Stage.CreateNew(str(file)), Path(file)
    if maker is None and kind not in _PLAIN:
        raise ValueError(f"A {kind} has to come from its maker's asset.")
    sensor = stage.DefinePrim(
        f"/{file.stem}", "" if maker else _PLAIN[kind]
    )  # else the maker's type
    if maker is not None:
        sensor.GetReferences().AddReference(_relative(maker, file), prim or Sdf.Path())
    sensor.AddAppliedSchema(SCHEMAS[kind])
    if maker is None and kind == "camera":  # a plain camera has a rate as NVIDIA's do
        sensor.AddAppliedSchema("OmniSensorAPI")
        sensor.CreateAttribute(TICK_RATE, Sdf.ValueTypeNames.Float).Set(30.0)
    UsdGeom.Xformable(sensor).ClearXformOpOrder()  # a rig places it
    if about:
        sensor.SetDocumentation(about)
    _finish(stage, sensor)
    return file


def new_rig(file: str | Path, about: str = "") -> Path:
    """An empty rig file: its default prim the origin."""
    stage, file = Usd.Stage.CreateNew(str(file)), Path(file)
    _finish(stage, stage.DefinePrim(f"/{file.stem}", "Xform"))
    if about:
        stage.GetRootLayer().documentation = about
        stage.Save()
    return file


def mounts(rig: str | Path) -> list[Mount]:
    """The rig's sensors, in order, those off too."""
    stage = _open(rig)
    layer = stage.GetRootLayer()
    found = []
    for holder in stage.GetDefaultPrim().GetFilteredChildren(Usd.PrimAllPrimsPredicate):
        name = holder.GetName()
        spec = layer.GetPrimAtPath(holder.GetPath().AppendChild(name))
        refs = spec.referenceList.prependedItems if spec else []
        sensor = Path(layer.ComputeAbsolutePath(refs[0].assetPath)) if refs else Path()
        ops = {op.GetOpName(): op.Get() for op in UsdGeom.Xformable(holder).GetOrderedXformOps()}
        pose = Pose(_three(ops.get(_OPS[0], (0, 0, 0))), _three(ops.get(_OPS[1], (0, 0, 0))))
        changed = tuple(a.name for a in spec.attributes) if spec else ()
        kind = (_kind_of_file(sensor) if sensor.is_file() else None) or ""
        found.append(Mount(name, kind, sensor, pose, holder.IsActive(), changed))
    return found


def add(rig: str | Path, name: str, sensor: str | Path, pose: Pose | None = None) -> None:
    """The sensor file `sensor` put on the rig as `name`, at `pose` (looking along +Y if None):
    an Xform `name` placed so, holding the sensor (`name` too) referencing the file."""
    stage = _open(rig)
    if not Sdf.Path.IsValidIdentifier(name):
        raise ValueError(f"{name!r}: a sensor's name is letters, digits and _.")
    path = stage.GetDefaultPrim().GetPath().AppendChild(name)
    if stage.GetPrimAtPath(path):
        raise ValueError(f"The rig has a {name} already.")
    holder = stage.DefinePrim(path, "Xform")
    stage.DefinePrim(path.AppendChild(name)).GetReferences().AddReference(
        _relative(sensor, Path(rig))
    )
    _pose(holder, pose or Pose(rotate=AHEAD[_kind_of_file(Path(sensor)) or "imu"]))
    stage.Save()


def place(rig: str | Path, name: str, pose: Pose) -> None:
    stage = _open(rig)
    _pose(_holder(stage, name), pose)
    stage.Save()


def switch(rig: str | Path, name: str, on: bool) -> None:
    stage = _open(rig)
    _holder(stage, name).SetActive(on)
    stage.Save()


def rename(rig: str | Path, name: str, to: str) -> None:
    stage = _open(rig)
    path = _holder(stage, name).GetPath()
    renamed = path.GetParentPath().AppendChild(to)
    edit = Sdf.BatchNamespaceEdit()
    edit.Add(path.AppendChild(name), path.AppendChild(to))
    edit.Add(path, renamed)
    if not Sdf.Path.IsValidIdentifier(to) or not stage.GetRootLayer().Apply(edit):
        raise ValueError(f"Can't rename {name} to {to!r}.")
    stage.Save()


def remove(rig: str | Path, name: str) -> None:
    stage = _open(rig)
    stage.RemovePrim(_holder(stage, name).GetPath())
    stage.Save()


def change(rig: str | Path, name: str, attribute: str, value: Any) -> None:
    """Attribute `attribute` of sensor `name` at `value`, in the rig (as its schema types it).
    A lens's image size or focal length scales its intrinsics with it (its calibration kept);
    a readout, rate or image size rewrites a rolling shutter's texture."""
    stage = _open(rig)
    prim = _mount(stage, name)
    found = prim.GetAttribute(attribute)
    if not found:
        raise ValueError(f"{name} has no {attribute}: `properties` lists what it has.")
    if attribute == MODEL:
        _switch_lens(prim, value)
    if attribute.endswith(":imageSize"):
        _resize(prim, attribute.rsplit(":", 1)[0], value)
    model = prim.GetAttribute("omni:lensdistortion:model").Get()
    if attribute == "focalLength" and model and found.Get():
        for k in ("fx", "fy"):  # what it sees narrows as its focal length grows
            fk = prim.GetAttribute(f"omni:lensdistortion:{model}:{k}")
            fk.Set(float(fk.Get() * value / found.Get()))
    found.Set(_usd_value(found, value))
    if attribute in (READOUT, TICK_RATE) or attribute.endswith(":imageSize"):
        _texture(prim, Path(rig))
    stage.Save()


def properties(file: str | Path, name: str | None = None) -> list[Property]:
    """Every attribute the sensor (sensor file `file`, or rig `file`'s `name`) has, as its
    schemas define them (its type's, then each applied API schema's), then any other authored.
    A schema USD has not registered is described only as authored."""
    stage = _open(file)
    prim = _mount(stage, name) if name else stage.GetDefaultPrim()
    here = stage.GetRootLayer().GetPrimAtPath(prim.GetPath())
    registry = Usd.SchemaRegistry()
    listed = prim.GetMetadata("apiSchemas")
    defined = [(prim.GetTypeName(), registry.FindConcretePrimDefinition(prim.GetTypeName()))]
    defined += [
        (s, registry.FindAppliedAPIPrimDefinition(s))
        for s in (listed.ApplyOperations([]) if listed else [])
    ]
    named = [
        (n, s, d.GetAttributeDefinition(n)) for s, d in defined if d for n in d.GetPropertyNames()
    ]
    named += [(a.GetName(), None, None) for a in prim.GetAuthoredAttributes()]
    found, seen = [], set()
    for attr, schema, spec in named:
        if (
            attr in seen
            or attr in _EVERY_PRIM
            or attr.startswith("xformOp")
            or (schema and not spec)
        ):
            continue
        seen.add(attr)
        a = prim.GetAttribute(attr)
        value = a.Get() if a else None
        value = spec.GetFallbackValue() if value is None and spec else value
        meta = (spec or a).GetMetadata
        doc = (
            spec
            and (spec.GetDocumentation() or spec.GetMetadataByDictKey("customData", "userDocBrief"))
        ) or ""
        found.append(
            Property(
                attr,
                str(a.GetTypeName() if a else spec.GetTypeName()),
                _plain(value),
                schema,
                meta("displayName") or attr.rsplit(":", 1)[-1],
                meta("displayGroup") or schema or "Other",
                doc,
                tuple(LENSES) if attr == MODEL else tuple(meta("allowedTokens") or ()),
                bool(
                    here and attr in here.attributes and here.attributes[attr].default is not None
                ),
            )
        )
    return found


def attach(
    layer: Sdf.Layer, rig: str | Path, frame: str | Sdf.Path, name: str | None = None
) -> Sdf.Path:
    """The rig file `rig` referenced under `frame` in `layer` (the frame need not be in it), as
    `name` (its stem unless given): it moves with the frame."""
    path = Sdf.Path(str(frame)).AppendChild(name or Path(rig).stem)
    spec = Sdf.CreatePrimInLayer(layer, path)
    spec.specifier = Sdf.SpecifierDef
    where = (
        _relative(rig, Path(layer.realPath)) if layer.realPath else Path(rig).resolve().as_posix()
    )
    spec.referenceList.Prepend(Sdf.Reference(where))
    return path


# Inside.


def _open(file: str | Path) -> Usd.Stage:
    layer = Sdf.Layer.FindOrOpen(str(file))
    if layer is None:
        raise FileNotFoundError(f"No USD file at {file}.")
    layer.Reload()
    stage = Usd.Stage.Open(layer, Usd.Stage.LoadNone)
    if not stage.GetDefaultPrim():
        raise ValueError(f"{Path(file).name} has no default prim.")
    return stage


def _holder(stage: Usd.Stage, name: str) -> Usd.Prim:
    """The Xform placing sensor `name` on the rig."""
    for prim in stage.GetDefaultPrim().GetFilteredChildren(Usd.PrimAllPrimsPredicate):
        if prim.GetName() == name:
            return prim
    raise KeyError(f"The rig has no sensor {name!r}.")


def _mount(stage: Usd.Stage, name: str) -> Usd.Prim:
    """Sensor `name` itself (on: an inactive one's settings are not composed)."""
    holder = _holder(stage, name)
    if not holder.IsActive():
        raise ValueError(f"{name} is off: switch it on to see or change its settings.")
    return holder.GetChild(name)


def _kind_of_file(sensor: Path) -> str | None:
    stage = Usd.Stage.Open(str(sensor), Usd.Stage.LoadNone)
    return kind_of(stage.GetDefaultPrim()) if stage.GetDefaultPrim() else None


def _finish(stage: Usd.Stage, root: Usd.Prim) -> None:
    stage.SetDefaultPrim(root)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.Save()


def _pose(prim: Usd.Prim, pose: Pose) -> None:
    xformable = UsdGeom.Xformable(prim)
    xformable.ClearXformOpOrder()
    xformable.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble).Set(pose.translate)
    xformable.AddRotateXYZOp().Set(pose.rotate)


def _resize(prim: Usd.Prim, lens: str, size: Any) -> None:
    """A calibrated lens at image size `size`: what it sees across, its pixels' shape and its
    middle kept; its aperture down made to agree."""
    old = prim.GetAttribute(f"{lens}:imageSize").Get()
    fx, fy, cx, cy = (prim.GetAttribute(f"{lens}:{k}").Get() for k in ("fx", "fy", "cx", "cy"))
    if old is None or None in (fx, fy, cx, cy):
        return
    across, down = size[0] / old[0], size[1] / old[1]
    for k, v in (("fx", fx * across), ("fy", fy * across), ("cx", cx * across), ("cy", cy * down)):
        prim.GetAttribute(f"{lens}:{k}").Set(float(v))
    focal = prim.GetAttribute("focalLength").Get()
    if focal:
        prim.GetAttribute("verticalAperture").Set(float(focal * size[1] / (fy * across)))


def _switch_lens(prim: Usd.Prim, model: str) -> None:
    """The camera's lens made a `model` lens: its API schema applied (the old one's taken off),
    its image size and intrinsics carried over, its distortion starting at none."""
    old = prim.GetAttribute(MODEL).Get()
    if model not in LENSES:
        raise ValueError(f"No lens model {model!r}: one of {', '.join(LENSES)}.")
    if model == old:
        return
    if old in LENSES:
        prim.RemoveAppliedSchema(LENSES[old])
    prim.AddAppliedSchema(LENSES[model])
    for k in ("imageSize", "fx", "fy", "cx", "cy"):
        was = prim.GetAttribute(f"omni:lensdistortion:{old}:{k}")
        if was and was.Get() is not None:
            prim.CreateAttribute(f"omni:lensdistortion:{model}:{k}", was.GetTypeName()).Set(
                was.Get()
            )
    for k in _COEFFICIENTS[model]:
        prim.CreateAttribute(f"omni:lensdistortion:{model}:{k}", Sdf.ValueTypeNames.Float).Set(0.0)


def _texture(prim: Usd.Prim, rig: Path) -> None:
    """A camera's rolling shutter as its texture of row times, beside the rig."""
    seconds = prim.GetAttribute(READOUT).Get() if prim.HasAttribute(READOUT) else None
    model = prim.GetAttribute("omni:lensdistortion:model").Get()
    size = prim.GetAttribute(f"omni:lensdistortion:{model}:imageSize").Get() if model else None
    rate = prim.GetAttribute(TICK_RATE).Get()
    if not seconds or size is None or not rate:
        return
    texture = rig.parent / f"{rig.stem}_{prim.GetName()}_readout.exr"
    readout.write(texture, readout.rows(int(size[1]), float(seconds), float(rate)))
    prim.CreateAttribute("shutterTimeTexturePath", Sdf.ValueTypeNames.Asset).Set(
        f"./{texture.name}"
    )


def _relative(target: str | Path, layer_file: Path) -> str:
    """`target` as an asset path written in `layer_file`, with forward slashes as USD's are:
    relative to the layer's folder (`./` or `../` first), or absolute where no relative path
    reaches it (another drive, on Windows)."""
    target, folder = Path(target).resolve(), Path(layer_file).resolve().parent
    try:
        found = Path(os.path.relpath(target, folder)).as_posix()
    except ValueError:  # Windows: the two are on different drives
        return target.as_posix()
    return found if found.startswith("../") else f"./{found}"


def _usd_value(attribute: Usd.Attribute, value: Any) -> Any:
    kind = attribute.GetTypeName()
    if isinstance(value, tuple | list) and not kind.isArray:
        return kind.type.pythonClass(*value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Sdf.AssetPath):
        return value.path
    if isinstance(value, str | bool | int | float) or value is None:
        return value
    return tuple(_plain(v) for v in value) if hasattr(value, "__len__") else value


def _three(v: Any) -> tuple[float, float, float]:
    return (float(v[0]), float(v[1]), float(v[2]))
