from trafficsense.control.fixedtime import FixedTimeController
from trafficsense.control.maxpressure import MaxPressureController

CONTROLLERS = {
    "fixedtime": FixedTimeController,
    "maxpressure": MaxPressureController,
}


def make_controller(name: str, cfg):
    if name not in CONTROLLERS:
        raise KeyError(f"Unknown controller {name!r}; known: {list(CONTROLLERS)}")
    return CONTROLLERS[name](cfg)
