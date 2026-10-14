from functools import partial

from trafficsense.control.fixedtime import FixedTimeController
from trafficsense.control.maxpressure import MaxPressureController
from trafficsense.control.webster import WebsterFixedTimeController

CONTROLLERS = {
    "fixedtime": partial(FixedTimeController, name="fixedtime"),
    "fixedtime_all_phases": partial(FixedTimeController, name="fixedtime_all_phases"),
    "fixedtime_webster": WebsterFixedTimeController,
    "maxpressure": partial(MaxPressureController, name="maxpressure"),
    "maxpressure_5s": partial(MaxPressureController, name="maxpressure_5s"),
}


def make_controller(name: str, cfg):
    if name not in CONTROLLERS:
        raise KeyError(f"Unknown controller {name!r}; known: {list(CONTROLLERS)}")
    return CONTROLLERS[name](cfg)
