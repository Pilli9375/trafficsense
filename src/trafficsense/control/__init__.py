from functools import partial

from trafficsense.control.fixedtime import FixedTimeController
from trafficsense.control.maxpressure import MaxPressureController

CONTROLLERS = {
    "fixedtime": partial(FixedTimeController, name="fixedtime"),
    "fixedtime_all_phases": partial(FixedTimeController, name="fixedtime_all_phases"),
    "maxpressure": MaxPressureController,
}


def make_controller(name: str, cfg):
    if name not in CONTROLLERS:
        raise KeyError(f"Unknown controller {name!r}; known: {list(CONTROLLERS)}")
    return CONTROLLERS[name](cfg)
