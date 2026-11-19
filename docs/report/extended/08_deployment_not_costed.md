# What a real deployment would additionally need (not costed)

Cost analysis, the part that is not in the report's Chapter 3.

## What a Real Deployment Would Additionally Need (Not Costed)
The project is a simulation study, so a deployment at real junctions would need components the
project never had. **None of them was priced**: their cost depends on vendors, on the number of
junctions and on the city's existing equipment, and an estimate made here would be invented.

* **Cameras at every junction approach**, with poles, mounting and power. The detector was
  trained and tested on dash-camera images, so it would also need images from these cameras to
  be retrained and its errors measured again (section “Camera error model”).
* **Computing at the junction or in a control centre**, with a GPU for the detector and the LLM
  agents.
* **An interface to the existing signal controllers**, approved by the traffic authority, with a
  safe fallback to the controller's own fixed plan on any fault.
* **Network links** between neighbouring junctions (the agents share their neighbours' states)
  and to a control centre.
* **Ambulance positions from GPS or V2X**, which the simulation assumes (section “Ambulance Handling”).
* **Field trials and calibration** against counted traffic, maintenance, power backup, and
  protection of the camera footage.
