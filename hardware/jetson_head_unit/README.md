# BEAN-Rider 10-inch Jetson head-unit print profile

A **printable test-fit kit**, not a finished crash-rated vehicle installation. Parts are OpenSCAD-parametric and dimensioned in millimeters.

| Part | Qty | Function |
|---|---:|---|
| `jetson_tray` | 1 | 160 x 126 mm ventilated universal Jetson mounting plate |
| `screen_tab` | 4 | Slotted bracket for the display **housing**, never bare glass |
| `cable_anchor` | 2 | Cable-tie anchors for routed USB/OBD adapter leads |

## Build STLs

```sh
openscad -o jetson_tray.stl -D 'part="jetson_tray"' head_unit.scad
openscad -o screen_tab.stl -D 'part="screen_tab"' head_unit.scad
openscad -o cable_anchor.stl -D 'part="cable_anchor"' head_unit.scad
```

The OpenSCAD defaults are for a **prototype**. Match a real Jetson's mounting holes with measured insulated standoffs and the adjustable slots. Do not treat the 103 x 90.5 mm Orin Nano devkit board envelope as mounting pitch. The screen is nominal 10.1-inch diagonal but the actual housing's external dimensions and attachment pattern are unspecified. Obtain physical measurements before cutting the dashboard or printing a custom fascia. Use retained structural mounts rather than printed brackets as the sole crash retention.

## Electrical and I/O profile

The Orin Nano developer kit uses **DisplayPort** for video and USB-A host ports for the touchscreen USB and wired OBD adapter; HDMI screens may require a compatible DP-to-HDMI converter. Older Nano boards require a revised tray and different power/video planning. The OBD-II interface is an **active J1962-to-USB diagnostic adapter**, not a passive cord. A right-angle OBD extension can improve clearance. Read-only OBD compatibility must be established for the adapter and vehicle.

**Power:** separate automotive-rated fused regulated supply, ignition sensing, clean shutdown and independent low-voltage disconnect. **Never power the Jetson from OBD pin 16.** Ensure the footwell and pedals stay unobstructed.

Android Auto and Apple CarPlay are **standard cockpit requirements**. The currently published receiver handoff software is not proof of working CarPlay/Android Auto projection hardware. Hardware receiver selection and in-car verification remain.

### Fit and print warning

PETG or ASA are appropriate prototype materials to evaluate, but a printed part is **not automatically heat, vibration, impact or flame certified**. Measure board fan clearance, airflow, connectors, cable strain, dash retention and screen visibility before road use.

References: [Orin Nano hardware](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/hardware_layout.html), [carrier specification](https://developer.nvidia.com/downloads/assets/embedded/secure/jetson/orin_nano/docs/jetson_orin_nano_devkit_carrier_board_specification_sp.pdf), [SAE J1962](https://saemobilus.sae.org/standards/j1962_201607-diagnostic-connector).
