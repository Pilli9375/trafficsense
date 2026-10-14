from functools import partial

from trafficsense.control.fixedtime import FixedTimeController
from trafficsense.control.guided import LLMGuidedMPController
from trafficsense.control.llm import LLMController
from trafficsense.control.maxpressure import MaxPressureController
from trafficsense.control.preemption import PreemptionMPController
from trafficsense.control.webster import WebsterFixedTimeController

CONTROLLERS = {
    "fixedtime": partial(FixedTimeController, name="fixedtime"),
    "fixedtime_all_phases": partial(FixedTimeController, name="fixedtime_all_phases"),
    "fixedtime_webster": WebsterFixedTimeController,
    "maxpressure": partial(MaxPressureController, name="maxpressure"),
    "maxpressure_15s": partial(MaxPressureController, name="maxpressure_15s"),
    "maxpressure_5s": partial(MaxPressureController, name="maxpressure_5s"),
    "preemption_mp": partial(PreemptionMPController, name="preemption_mp"),
    "llm_v1": partial(LLMController, name="llm_v1"),
    "llm_cooperative": partial(LLMController, name="llm_cooperative"),
    "llm_isolated": partial(LLMController, name="llm_isolated"),
    "llm_guided_mp": partial(LLMGuidedMPController, name="llm_guided_mp"),
    "llm_v3": partial(LLMController, name="llm_v3"),
    "llm_guided_mp_v3": partial(LLMGuidedMPController, name="llm_guided_mp_v3"),
}


def make_controller(name: str, cfg):
    if name not in CONTROLLERS:
        raise KeyError(f"Unknown controller {name!r}; known: {list(CONTROLLERS)}")
    return CONTROLLERS[name](cfg)
