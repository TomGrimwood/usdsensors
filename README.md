# usdsensors

Sensors and sensor rigs as USDA files, read into dataclasses and written back.

- **A sensor file** holds one sensor: a camera, an RTX lidar, an IMU or a GNSS antenna. It
  references its maker's asset (NVIDIA's OAK-4 D, a Hesai XT32) and sets over it what differs
  (a rate, a resolution), or is a plain one of its kind. It has no place of its own.
- **A rig file** holds sensor files, each placed rigidly about one origin (`Pose`: translate,
  then rotate about X, Y, Z) with what the rig sets differently. Attached under a frame (a
  pole's `Frames/SensorMount`, a drone's), the whole rig moves with it.

```python
import usdsensors as us

us.make_sensor("sensors/OAK4D_RGB.usda", "camera", ".../oak4_d.usd", "/Root/OAK4_D/Camera_rgb_imx586")
us.new_rig("rigs/Pole.usda")
us.add("rigs/Pole.usda", "front", "sensors/OAK4D_RGB.usda", us.Pose((0, 0.09, -0.04), (60, 0, 0)))
us.change("rigs/Pole.usda", "front", "omni:sensor:tickRate", 10.0)   # as its schema types it
us.mounts("rigs/Pole.usda")                  # [Mount(name, kind, sensor, pose, active, changed)]
us.properties("rigs/Pole.usda", "front")     # [Property(name, type, value, schema, label, group, doc, choices, set_here)]
us.attach(run_layer, "rigs/Pole.usda", "/World/Pole/Frames/SensorMount")
```

## Settings

A sensor's settings are its attributes, as its schemas define them: USD's `Camera`, NVIDIA's
OmniSensorAPI, OmniLens and OmniLidar, this library's. `properties` lists every one with its
type, value, label, group, doc and allowed values, so a form is made from it whatever the
schemas are; `change` sets one, typed as its schema has it. Three things no schema does are done
on `change`: a camera's lens switched between OpenCV's pinhole and fisheye (`LENSES`: its API
schema swapped, its image size and intrinsics carried over, its distortion from none); a calibrated OmniLens lens resized keeps its calibration (its intrinsics scaled,
its aperture down made to agree), and a camera's readout is written as the texture of row times
RTX reads, beside the rig.

## Schemas

A sensor is marked by an applied API schema of this library, codeless (two files USD reads,
nothing compiled, `src/usdsensors/schema/`), registered when `usdsensors` is imported:

| Schema | On | Says |
|---|---|---|
| `SensorCameraAPI` | a `Camera` | `sensor:camera:readoutSeconds` (0: a global shutter) |
| `SensorLidarAPI` | an `OmniLidar` | nothing more: it marks it |
| `SensorImuAPI` | an `Xform`: the IMU's axes | `sensor:imu:rateHz` (200) |
| `SensorGnssAPI` | an `Xform`: its origin the antenna's phase centre | `sensor:gnss:rateHz` (10) |

Everything else is NVIDIA's or USD's own, which this library leaves to do what they do: a
camera's rate is OmniSensorAPI's `omni:sensor:tickRate`, its lens OmniLens's (stored numbers:
this library works them out so they agree), a lidar's pattern OmniLidar's, a sensor off its
prim made inactive (`Mount.active`). A lens of a model it does not work out (f-theta,
Kannala-Brandt) is kept as its maker made it.

How it renders is NVIDIA's schemas' (OmniSensorAPI's rate, OmniLens, OmniLidar). USD takes
its schemas in once; where it did before `usdsensors` was imported (Kit, at its start), the
schemas are not registered, and reading and writing still work: a sensor is known by the
schema names its prim lists, and the fallbacks are the library's own.

To change the schemas, edit `schema/schema.usda` and run `tools/generate.sh` (OpenUSD's
`usdGenSchema.py`, from a clone of OpenUSD beside this one or at `$OPENUSD`). It is a bash
script: on Windows run it in Git Bash or WSL. Using the library needs neither.

## Commands

```bash
uv sync
make        # lint, format, types, the tests: seconds
make fmt
uv run python scripts/check.py   # what `make` runs, without make (Windows)
```
