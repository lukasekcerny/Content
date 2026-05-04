import os
import tempfile

from app.mobile.touch_recorder import (
    RecordedAction,
    Recording,
    RecordingStore,
    TouchRecorder,
)


class TestTouchRecorderParsing:
    """Drive _parse_line directly and verify the resulting action list."""

    def _make_recorder(self) -> TouchRecorder:
        return TouchRecorder(adb_path="adb", device_id="emulator-5554")

    def test_single_tap(self):
        r = self._make_recorder()
        for line in (
            "[   1234.000] /dev/input/event2: EV_ABS       ABS_MT_TRACKING_ID   00000001",
            "[   1234.000] /dev/input/event2: EV_ABS       ABS_MT_POSITION_X    00000540",
            "[   1234.000] /dev/input/event2: EV_ABS       ABS_MT_POSITION_Y    00000900",
            "[   1234.000] /dev/input/event2: EV_SYN       SYN_REPORT           00000000",
            "[   1234.100] /dev/input/event2: EV_ABS       ABS_MT_TRACKING_ID   ffffffff",
        ):
            r._parse_line(line)
        assert len(r._actions) == 1
        a = r._actions[0]
        assert a.type == "tap"
        assert a.x == 0x540
        assert a.y == 0x900

    def test_swipe(self):
        r = self._make_recorder()
        for line in (
            "[   1000.000] /dev/input/event2: EV_ABS       ABS_MT_TRACKING_ID   00000002",
            "[   1000.000] /dev/input/event2: EV_ABS       ABS_MT_POSITION_X    00000100",
            "[   1000.000] /dev/input/event2: EV_ABS       ABS_MT_POSITION_Y    00000200",
            "[   1000.050] /dev/input/event2: EV_ABS       ABS_MT_POSITION_X    00000800",
            "[   1000.050] /dev/input/event2: EV_ABS       ABS_MT_POSITION_Y    00000200",
            "[   1000.500] /dev/input/event2: EV_ABS       ABS_MT_TRACKING_ID   ffffffff",
        ):
            r._parse_line(line)
        assert len(r._actions) == 1
        a = r._actions[0]
        assert a.type == "swipe"
        assert a.x == 0x100
        assert a.x2 == 0x800

    def test_two_taps_with_gap(self):
        r = self._make_recorder()
        for line in (
            "[   1000.000] /dev/input/event2: EV_ABS       ABS_MT_TRACKING_ID   00000001",
            "[   1000.000] /dev/input/event2: EV_ABS       ABS_MT_POSITION_X    00000100",
            "[   1000.000] /dev/input/event2: EV_ABS       ABS_MT_POSITION_Y    00000200",
            "[   1000.080] /dev/input/event2: EV_ABS       ABS_MT_TRACKING_ID   ffffffff",
            "[   1002.500] /dev/input/event2: EV_ABS       ABS_MT_TRACKING_ID   00000002",
            "[   1002.500] /dev/input/event2: EV_ABS       ABS_MT_POSITION_X    00000300",
            "[   1002.500] /dev/input/event2: EV_ABS       ABS_MT_POSITION_Y    00000400",
            "[   1002.580] /dev/input/event2: EV_ABS       ABS_MT_TRACKING_ID   ffffffff",
        ):
            r._parse_line(line)
        assert len(r._actions) == 2
        assert r._actions[0].type == "tap"
        assert r._actions[1].type == "tap"
        assert 200 <= r._actions[0].delay_after_ms <= 8000


class TestRecordingStore:

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as data_dir:
            store = RecordingStore(data_dir)
            actions = [
                RecordedAction(type="tap", x=10, y=20, delay_after_ms=500),
                RecordedAction(type="swipe", x=10, y=20, x2=300, y2=20, duration_ms=200),
            ]
            store.save("instagram:set_profile_picture", actions)

            loaded = store.load("instagram:set_profile_picture")
            assert loaded is not None
            assert len(loaded.actions) == 2
            assert loaded.actions[0].type == "tap"
            assert loaded.actions[0].x == 10
            assert loaded.actions[1].type == "swipe"

    def test_load_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as data_dir:
            store = RecordingStore(data_dir)
            assert store.load("nope:nope") is None

    def test_clear(self):
        with tempfile.TemporaryDirectory() as data_dir:
            store = RecordingStore(data_dir)
            store.save("k", [RecordedAction(type="tap", x=1, y=1)])
            assert store.has("k")
            store.clear("k")
            assert not store.has("k")

    def test_list_keys(self):
        with tempfile.TemporaryDirectory() as data_dir:
            store = RecordingStore(data_dir)
            store.save("a:b", [RecordedAction(type="tap", x=1, y=1)])
            store.save("c:d", [RecordedAction(type="tap", x=2, y=2)])
            keys = set(store.list_keys())
            assert keys == {"a:b", "c:d"}

    def test_overwrite(self):
        with tempfile.TemporaryDirectory() as data_dir:
            store = RecordingStore(data_dir)
            store.save("k", [RecordedAction(type="tap", x=1, y=1)])
            store.save("k", [
                RecordedAction(type="tap", x=2, y=2),
                RecordedAction(type="tap", x=3, y=3),
            ])
            loaded = store.load("k")
            assert len(loaded.actions) == 2
            assert loaded.actions[0].x == 2
