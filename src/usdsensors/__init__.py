"""Sensors and sensor rigs as USDA files: a sensor file per sensor, over its maker's asset; a
rig of them, each placed rigidly about the frame that carries it; their settings as their
schemas define them (`properties`), for a form to be made from.

    import usdsensors as us
    us.make_sensor("sensors/OAK4D_RGB.usda", "camera", oak4_d_usd, "/Root/OAK4_D/Camera_rgb_imx586")
    us.new_rig("rigs/Pole.usda")
    us.add("rigs/Pole.usda", "front", "sensors/OAK4D_RGB.usda", us.Pose((0, 0.09, -0.04), (60, 0, 0)))
    us.change("rigs/Pole.usda", "front", "omni:sensor:tickRate", 10.0)
    us.properties("rigs/Pole.usda", "front")        # [Property, ...]
    us.attach(layer, "rigs/Pole.usda", "/World/Pole/Frames/SensorMount")

This library's schemas (`schema/`) are registered on import; others' (NVIDIA's OmniLens and
OmniSensor, which plain usd-core lacks) with `register`, or the folders in
`USDSENSORS_SCHEMAS`, before the first stage is opened.
"""

import os
from pathlib import Path

from pxr import Plug


def register(*folders: str | Path) -> None:
    """The schema plugins in `folders` (each with a `plugInfo.json` in or under it) made known
    to USD. Only those registered before USD first needs its schemas are known: register first."""
    for folder in folders:
        Plug.Registry().RegisterPlugins(str(folder))


register(Path(__file__).resolve().parent / "schema")
register(*(f for f in os.environ.get("USDSENSORS_SCHEMAS", "").split(os.pathsep) if f))

from . import readout  # noqa: E402 - after the schemas are registered
from .rigs import (  # noqa: E402
    AHEAD,
    LENSES,
    RATE,
    READOUT,
    SCHEMAS,
    TICK_RATE,
    Mount,
    Pose,
    Property,
    add,
    attach,
    change,
    kind_of,
    make_sensor,
    mounts,
    new_rig,
    place,
    properties,
    remove,
    rename,
    switch,
)

__all__ = [
    "AHEAD",
    "LENSES",
    "RATE",
    "READOUT",
    "SCHEMAS",
    "TICK_RATE",
    "Mount",
    "Pose",
    "Property",
    "add",
    "attach",
    "change",
    "kind_of",
    "make_sensor",
    "mounts",
    "new_rig",
    "place",
    "properties",
    "readout",
    "register",
    "remove",
    "rename",
    "switch",
]
