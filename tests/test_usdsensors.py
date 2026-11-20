"""Sensor files, rigs of them, and what their schemas say they have."""

import struct

import numpy as np
import pytest
from pxr import Sdf, Usd, UsdGeom

import usdsensors as us

#: A maker's camera: a calibrated OmniLens pinhole at 4000 x 3000, 30 a second, placed in its
#: device (a transform the sensor file clears).
MAKER = """#usda 1.0
(defaultPrim = "Device")
def Xform "Device" {
    def Camera "Lens" (prepend apiSchemas = ["OmniLensDistortionOpenCvPinholeAPI"]) {
        float focalLength = 4
        float horizontalAperture = 6.4
        float verticalAperture = 4.8
        token omni:lensdistortion:model = "opencvPinhole"
        int2 omni:lensdistortion:opencvPinhole:imageSize = (4000, 3000)
        float omni:lensdistortion:opencvPinhole:fx = 2500
        float omni:lensdistortion:opencvPinhole:fy = 2500
        float omni:lensdistortion:opencvPinhole:cx = 2000
        float omni:lensdistortion:opencvPinhole:cy = 1500
        float omni:lensdistortion:opencvPinhole:k1 = 0.1
        float omni:sensor:tickRate = 30
        double3 xformOp:translate = (0.05, 0, 0)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
}
"""
LENS = "omni:lensdistortion:opencvPinhole:"


@pytest.fixture
def rig(tmp_path):
    """A rig with a maker's camera ahead and a plain IMU below its origin."""
    (tmp_path / "maker.usda").write_text(MAKER, encoding="utf-8")
    lens = us.make_sensor(
        tmp_path / "sensors" / "Lens.usda",
        "camera",
        tmp_path / "maker.usda",
        "/Device/Lens",
        "A lens.",
    )
    imu = us.make_sensor(tmp_path / "sensors" / "IMU.usda", "imu")
    rig = us.new_rig(tmp_path / "rigs" / "Pole.usda", "A pole's sensors.")
    us.add(rig, "front", lens, us.Pose((0.0, 0.1, -0.05), (60.0, 0.0, 0.0)))
    us.add(rig, "imu", imu, us.Pose((0.0, 0.0, -0.05)))
    return rig


def _prim(file, path):
    stage = Usd.Stage.Open(str(file))
    return stage, stage.GetPrimAtPath(path)


def test_a_sensor_file_is_its_makers_sensor_with_its_kinds_schema_and_no_place_of_its_own(rig):
    _, lens = _prim(rig.parent.parent / "sensors" / "Lens.usda", "/Lens")
    assert lens.IsA(UsdGeom.Camera) and us.kind_of(lens) == "camera"
    assert "SensorCameraAPI" in lens.GetAppliedSchemas()  # registered: USD knows it
    assert lens.GetAttribute("xformOpOrder").Get() == []
    _, imu = _prim(rig.parent.parent / "sensors" / "IMU.usda", "/IMU")
    assert us.kind_of(imu) == "imu" and imu.GetAttribute(us.RATE["imu"]).Get() == 200  # fallback


def test_a_rig_places_each_sensor_rigidly_and_moves_with_its_frame(rig, tmp_path):
    found = us.mounts(rig)
    assert [(m.name, m.kind, m.sensor.name) for m in found] == [
        ("front", "camera", "Lens.usda"),
        ("imu", "imu", "IMU.usda"),
    ]
    assert found[0].pose == us.Pose((0.0, 0.1, -0.05), (60.0, 0.0, 0.0)) and found[0].changed == ()
    layer = Sdf.Layer.FindOrOpen(str(rig))
    ref = layer.GetPrimAtPath("/Pole/front/front").referenceList.prependedItems[0]
    assert ref.assetPath == "../sensors/Lens.usda"
    scene = Usd.Stage.CreateNew(str(tmp_path / "scene.usda"))
    op = UsdGeom.Xform.Define(scene, "/Pole/Frames/SensorMount").AddTranslateOp()
    op.Set((0, 0, 0), 0)
    op.Set((4, 0, 0), 10)
    scene.Save()
    run = Sdf.Layer.CreateNew(str(tmp_path / "run.usda"))
    run.subLayerPaths.append("./scene.usda")
    path = us.attach(run, rig, "/Pole/Frames/SensorMount")
    run.Save()
    _, front = _prim(tmp_path / "run.usda", path.AppendChild("front").AppendChild("front"))
    moved = UsdGeom.Xformable(front).ComputeLocalToWorldTransform(5).ExtractTranslation()
    assert np.allclose(moved, (2, 0.1, -0.05))


def test_settings_are_set_over_the_sensor_file_as_its_schemas_type_them(rig):
    us.change(rig, "front", us.TICK_RATE, 10)
    us.change(rig, "imu", us.RATE["imu"], 100)
    changed = {m.name: m.changed for m in us.mounts(rig)}
    assert changed == {"front": (us.TICK_RATE,), "imu": (us.RATE["imu"],)}
    _, front = _prim(rig, "/Pole/front/front")
    assert front.GetAttribute(us.TICK_RATE).Get() == 10.0
    _, own = _prim(rig.parent.parent / "sensors" / "Lens.usda", "/Lens")
    assert own.GetAttribute(us.TICK_RATE).Get() == 30.0  # its file as it was
    with pytest.raises(ValueError, match="has no zoom"):
        us.change(rig, "front", "zoom", 2)


def test_a_lens_resized_keeps_its_calibration(rig):
    us.change(rig, "front", LENS + "imageSize", (640, 480))
    _, front = _prim(rig, "/Pole/front/front")
    fx, cx, cy = (front.GetAttribute(LENS + k).Get() for k in ("fx", "cx", "cy"))
    assert (fx, cx, cy) == pytest.approx((400.0, 320.0, 240.0))
    assert front.GetAttribute(LENS + "k1").Get() == pytest.approx(0.1)
    assert front.GetAttribute("verticalAperture").Get() == pytest.approx(4 * 480 / 400)
    us.change(rig, "front", "focalLength", 8.0)
    _, front = _prim(rig, "/Pole/front/front")
    assert front.GetAttribute(LENS + "fx").Get() == pytest.approx(800.0)


def test_a_rolling_shutter_is_a_texture_beside_the_rig(rig):
    us.change(rig, "front", us.TICK_RATE, 25)
    us.change(rig, "front", us.READOUT, 0.02)
    _, front = _prim(rig, "/Pole/front/front")
    assert front.GetAttribute("shutterTimeTexturePath").Get().path == "./Pole_front_readout.exr"
    assert (rig.parent / "Pole_front_readout.exr").is_file()
    with pytest.raises(ValueError, match="longer than a frame"):
        us.change(rig, "front", us.READOUT, 0.1)
    data = us.readout.write(rig.parent / "r.exr", [0.5, 1.0]).read_bytes()
    assert data[:4] == struct.pack("<i", 20000630) and struct.unpack("<f", data[-4:]) == (1.0,)


def test_a_rigs_sensors_are_moved_switched_renamed_and_taken_off(rig):
    us.place(rig, "imu", us.Pose(rotate=(0.0, 0.0, 90.0)))
    us.switch(rig, "imu", False)
    us.rename(rig, "front", "ahead")
    found = {m.name: m for m in us.mounts(rig)}
    assert found["imu"].pose.rotate == (0.0, 0.0, 90.0) and not found["imu"].active
    us.remove(rig, "imu")
    assert [m.name for m in us.mounts(rig)] == ["ahead"]
    with pytest.raises(ValueError, match="already"):
        us.add(rig, "ahead", rig.parent.parent / "sensors" / "Lens.usda")


def test_properties_are_what_the_schemas_say(rig):
    us.change(rig, "imu", us.RATE["imu"], 100)
    rate = {p.name: p for p in us.properties(rig, "imu")}[us.RATE["imu"]]
    assert (rate.type, rate.value, rate.schema) == ("double", 100.0, "SensorImuAPI")
    assert (rate.label, rate.set_here) == ("Rate (Hz)", True)
    camera = {p.name: p for p in us.properties(rig, "front")}
    assert camera["focalLength"].schema == "Camera" and camera["focalLength"].value == 4.0
    assert camera["projection"].choices == ("perspective", "orthographic")
    assert camera[us.READOUT].value == 0.0 and "visibility" not in camera


def test_a_lens_is_switched_to_a_fisheye_keeping_its_intrinsics(rig):
    us.change(rig, "front", "omni:lensdistortion:model", "opencvFisheye")
    us.change(rig, "front", "omni:lensdistortion:opencvFisheye:k1", 0.1)
    _, front = _prim(rig, "/Pole/front/front")
    assert "OmniLensDistortionOpenCvFisheyeAPI" in front.GetMetadata("apiSchemas").ApplyOperations(
        []
    )
    fisheye = "omni:lensdistortion:opencvFisheye:"
    assert front.GetAttribute(fisheye + "imageSize").Get() == (4000, 3000)
    assert front.GetAttribute(fisheye + "fx").Get() == 2500
    model = {p.name: p for p in us.properties(rig, "front")}["omni:lensdistortion:model"]
    assert model.value == "opencvFisheye" and model.choices == tuple(us.LENSES)
    with pytest.raises(ValueError, match="No lens model"):
        us.change(rig, "front", "omni:lensdistortion:model", "kannalaBrandt")


def test_a_file_no_relative_path_reaches_is_referenced_by_its_absolute_path(
    rig, tmp_path, monkeypatch
):
    def other_drive(path, start):  # as Windows says of a file on another drive
        raise ValueError("path is on mount 'D:', start on mount 'C:'")

    sensor = rig.parent.parent / "sensors" / "IMU.usda"
    monkeypatch.setattr(us.rigs.os.path, "relpath", other_drive)
    us.add(rig, "far", sensor)
    layer = Sdf.Layer.FindOrOpen(str(rig))
    ref = layer.GetPrimAtPath("/Pole/far/far").referenceList.prependedItems[0]
    assert ref.assetPath == sensor.resolve().as_posix()
    assert next(m for m in us.mounts(rig) if m.name == "far").sensor == sensor.resolve()
