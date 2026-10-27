#***************************************************************
#SimLab Version 2026 
#Created at Wed Sep 16 17:28:26 2026
#***************************************************************
from hwx import simlab

# ---------------------------------------------------------------------------
# Read the design values straight from the HyperStudy params XML, instead of
# relying on the SimLab Parameter Manager (which was being reset to 0 m).
# ---------------------------------------------------------------------------
import os, sys, glob
import xml.etree.ElementTree as ET

MOVE_PARAMS = ["Cluster1_X", "Cluster1_Y", "Cluster2_X", "Cluster2_Y",
               "Cluster3_X", "Cluster3_Y", "Cluster4_X", "Cluster4_Y",
               "Capacitor_X", "Capacitor_Y"]

def _find_params_file():
    # 1) the path HyperStudy passed with -param
    args = [str(a) for a in sys.argv]
    for i, a in enumerate(args):
        if a.lower() in ("-param", "--param") and i + 1 < len(args):
            if os.path.isfile(args[i + 1]):
                return args[i + 1]
    # 2) fall back to the params file in the run folder (current directory)
    for pattern in ("hyper7_Params.xml", "*_Params.xml"):
        hits = glob.glob(os.path.join(os.getcwd(), pattern))
        if hits:
            return hits[0]
    raise Exception("hyper7.py: could not find the params XML. sys.argv=%s cwd=%s"
                    % (args, os.getcwd()))

def _read_params(path):
    values = {}
    for p in ET.parse(path).getroot().iter("Parameter"):
        name = p.findtext("Name") or p.findtext("n")
        value = p.findtext("Value")
        if name and value is not None:
            values[name.strip()] = value.strip()
    return values

PARAMS_FILE = _find_params_file()
PARAMS = _read_params(PARAMS_FILE)

missing = [k for k in MOVE_PARAMS if k not in PARAMS]
if missing:
    raise Exception("hyper7.py: missing in %s: %s" % (PARAMS_FILE, missing))

# Log what was actually used, so you can check it in the run folder.
with open("hyper7_params_used.txt", "w") as _f:
    _f.write("params file: %s\n" % PARAMS_FILE)
    for k in MOVE_PARAMS:
        _f.write("%s = %s\n" % (k, PARAMS[k]))

def sub(xml_text):
    """Replace $Cluster1_X etc. with the values read from the XML."""
    for k in MOVE_PARAMS:
        xml_text = xml_text.replace("$" + k, PARAMS[k])
    return xml_text
# ---------------------------------------------------------------------------


UnitSystem=''' <UnitSystem UUID="3aca8564-4d38-4b0b-887c-6a542d4001c6">
  <SetCurrentDisplaySystem Name="MMKS (mm kg N C s)"/>
 </UnitSystem>''';
simlab.execute(UnitSystem);

UnitSystem=''' <UnitSystem UUID="3aca8564-4d38-4b0b-887c-6a542d4001c6">
  <SetCurrentDisplaySystem Name="MMKS (mm kg N C s)"/>
 </UnitSystem>''';
simlab.execute(UnitSystem);

UnitSystem=''' <UnitSystem UUID="3aca8564-4d38-4b0b-887c-6a542d4001c6">
  <SetCurrentDisplaySystem Name="MKS (m kg N C s)"/>
 </UnitSystem>''';
simlab.execute(UnitSystem);

ImportSlb=''' <ImportSlb CheckBox="ON" UUID="C806F6DF-56FA-4134-9AD1-1010BF292183" gda="">
  <tag Value="1"/>
  <Name Value=""/>
  <FileName Value="$ImportSlbPath"/>
  <ImportOrOpen Value="0"/>
  <Output/>
 </ImportSlb>''';
simlab.execute(ImportSlb);


DeleteModel=''' <DeleteModel CheckBox="ON" UUID="AE031126-6421-4633-8FAE-77C8DE10C18F" updategraphics="0">
  <ModelName Value="ElectronicsThermal_Result_Model"/>
 </DeleteModel>''';
simlab.execute(DeleteModel);


# ---------------------------------------------------------------------------
# PCB COPPER LOSS - part 1: read the component centres BEFORE moving.
# The imported model is the original layout, whose PCB loss is P0_PCB.
#   P = P0 * L / L0,   L = L_in + (L1 + L2)/4,   l(i,j) = sqrt(dx^2 + dy^2)
#   L_in = l(F1,C) + l(C,F2)
#   L1   = l(C,a)+l(a,E2)+l(E1,d)+l(d,C) + l(C,a')+l(a',E2)+l(E1,d')+l(d',C)
#   L2   = l(C,b)+l(b,E1)+l(E2,c)+l(c,C) + l(C,b')+l(b',E1)+l(E2,c')+l(c',C)
# ---------------------------------------------------------------------------
import math, re, traceback

P0_PCB     = 10.0   # W, PCB loss of the original (imported) layout
MODEL_NAME = ""     # "" -> try $Geometry; otherwise the model name from the model browser

# Each point is one of:
#   [body names]                -> centre of the box around them, read every run
#   (x, y)                      -> fixed coordinates in the model's box units
#   ("m", x, y)                 -> fixed coordinates in METRES (converted automatically if
#                                  SimLab returns the boxes in mm)
#   ("frac", [bodies], u, v)    -> fixed point at fraction (u, v) of the ORIGINAL box around
#                                  the bodies: u from min-x to max-x, v from min-y to max-y.
#                                  Read once before moving, then kept fixed. Bodies that do not
#                                  exist are skipped.
# F1/F2 were picked in SimLab (Mesh > Modify > Nodes > Create, nodes 1457392 / 1478960):
#   F1 = (0.023584, 0.061300, -0.015720) m,  F2 = (0.076000, 0.071300, -0.015720) m
#   E1 = (0.159500, 0.059300, -0.012720) m,  E2 = (0.159500, 0.097300, -0.012720) m
PCB_POINTS = {
    "a":  ["M3"],
    "b":  ["M4"],
    "c":  ["M10"],
    "d":  ["M9"],
    "C3": ["M13", "M14", "M15", "M16", "Cluster3"],   # a' and c'
    "C4": ["Cluster4", "M17", "M18", "M19", "M20"],   # b' and d'
    "C":  ["Capacitor_T", "Capacitor"],               # DC-link capacitor (bus node)
    "F1": ("m", 0.023584, 0.061300),     # input terminal F1 (picked in SimLab)
    "F2": ("m", 0.076000, 0.071300),     # input terminal F2 (picked in SimLab)
    "E1": ("m", 0.159500, 0.059300),     # transformer terminal E1 (picked in SimLab)
    "E2": ("m", 0.159500, 0.097300),     # transformer terminal E2 (picked in SimLab)
}
PCB_PATHS = {
    "Lin": [("F1", "C"), ("C", "F2")],
    "L1":  [("C", "a"), ("a", "E2"), ("E1", "d"), ("d", "C"),
            ("C", "C3"), ("C3", "E2"), ("E1", "C4"), ("C4", "C")],
    "L2":  [("C", "b"), ("b", "E1"), ("E2", "c"), ("c", "C"),
            ("C", "C4"), ("C4", "E1"), ("E2", "C3"), ("C3", "C")],
}
PCB_WEIGHT = {"Lin": 1.0, "L1": 0.25, "L2": 0.25}
_PCB_CALL = []   # (model, entity format) that worked, reused for speed


def _pcb_numbers(obj):
    if isinstance(obj, str):
        return [float(v) for v in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", obj)]
    if isinstance(obj, (int, float)):
        return [float(obj)]
    out = []
    for item in obj:
        out += _pcb_numbers(item)
    return out


def _pcb_models():
    names = [MODEL_NAME] if MODEL_NAME else []
    if PARAMS.get("Geometry"):              # model name from the params XML (e.g. project1.x_t)
        names.append(PARAMS["Geometry"])
    try:
        g = simlab.getParameter("$Geometry")
        if isinstance(g, str) and g.strip():
            names.append(g.strip())
    except Exception:
        pass
    return names + ["$Geometry"]


def _pcb_box(body, log):
    tries = list(_PCB_CALL) + [(m, k) for m in _pcb_models() for k in (0, 1, 2)]
    for model, kind in tries:
        entity = [[body], [model, body], [(model, body)]][kind]
        try:
            raw = simlab.getBoxPointsForBodies(model, entity, [0, 0, 0], [0, 0, 0])
        except Exception as e:
            log.append("  %s model=%r entity=%r error: %s" % (body, model, entity, e))
            continue
        v = _pcb_numbers(raw)
        log.append("  %s model=%r entity=%r raw: %r" % (body, model, entity, raw))
        if v and len(v) % 3 == 0:
            if not _PCB_CALL:
                _PCB_CALL.append((model, kind))
            pts = [v[i:i + 3] for i in range(0, len(v), 3)]
            return ([min(p[k] for p in pts) for k in range(3)],
                    [max(p[k] for p in pts) for k in range(3)])
    raise Exception("could not read the box of body '%s'" % body)


def _pcb_bounds(bodies, log, skip_missing=False):
    boxes = []
    for b in bodies:
        try:
            boxes.append(_pcb_box(b, log))
        except Exception:
            if not skip_missing:
                raise
    if not boxes:
        raise Exception("none of the bodies %s could be read" % bodies)
    lo = [min(bx[0][k] for bx in boxes) for k in range(2)]
    hi = [max(bx[1][k] for bx in boxes) for k in range(2)]
    return lo, hi


def _pcb_read_points(log, when, before=None):
    log.append("-- reading centres %s moving" % when)
    xy = {}
    # body-based points first, so the box units are known before the fixed metre points
    order = sorted(PCB_POINTS, key=lambda n: isinstance(PCB_POINTS[n], tuple))
    for name in order:
        spec = PCB_POINTS[name]
        if spec is None:
            raise Exception("PCB_POINTS['%s'] is not filled in" % name)
        if isinstance(spec, tuple) and spec and spec[0] == "m":
            # boxes in mm give coordinates of tens/hundreds; boxes in m stay below ~1
            body_vals = [abs(c) for n, p in xy.items() for c in p]
            scale = 1000.0 if body_vals and max(body_vals) > 2.0 else 1.0
            if name == "F1":
                log.append("   box units look like %s -> metre points x%g" % ("mm" if scale > 1 else "m", scale))
            xy[name] = (spec[1] * scale, spec[2] * scale)
            continue
        if isinstance(spec, tuple) and spec and spec[0] == "frac":
            if before is not None:              # keep the point where it was originally
                xy[name] = before[name]
                continue
            lo, hi = _pcb_bounds(spec[1], log, skip_missing=True)
            xy[name] = (lo[0] + spec[2] * (hi[0] - lo[0]), lo[1] + spec[3] * (hi[1] - lo[1]))
            continue
        if isinstance(spec, tuple):
            xy[name] = (float(spec[0]), float(spec[1]))
            continue
        lo, hi = _pcb_bounds(spec, log)
        xy[name] = ((lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0)
    moving = [xy[n] for n in ("a", "b", "c", "d", "C3", "C4", "C")]
    if len(set(moving)) == 1:
        raise Exception("all centres are identical - SimLab boxed the whole model, not each body")
    return xy


def _pcb_lengths(xy):
    seg, grp = {}, {}
    for g, pairs in PCB_PATHS.items():
        grp[g] = 0.0
        for i, j in pairs:
            d = math.hypot(xy[i][0] - xy[j][0], xy[i][1] - xy[j][1])
            seg["%s:%s-%s" % (g, i, j)] = d
            grp[g] += d
    L = sum(PCB_WEIGHT[g] * grp[g] for g in grp)
    return L, grp, seg


PCB_LOG = []
try:
    PCB_XY0 = _pcb_read_points(PCB_LOG, "BEFORE")
except Exception as _e:
    PCB_XY0 = _e
# ---------------------------------------------------------------------------

Translation=''' <Translation CheckBox="ON" UUID="26b085e8-d9a3-4baf-95f2-9f3eb75ac454">
  <tag Value="-1"/>
  <Name Value=""/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"M1","M2","M3","M4","M5","M6","Cluster1",</Body>
   </Entities>
  </SupportEntities>
  <RegionObject>
   <TranslationDirection>
    <DirectionVector Value="1.000000000000 m,0.000000000000 m,0.000000000000 m,"/>
   </TranslationDirection>
  </RegionObject>
  <UnitVector Value="0"/>
  <Magnitude Value="1"/>
  <DistanceVector Value="$Cluster1_X"/>
  <CoorId Value="0"/>
  <Copy Value="0"/>
  <WithLBC Value="0"/>
  <No.Of.Copies Value="1"/>
  <LocalCoordinateSystem Value=""/>
  <Output/>
 </Translation>''';
simlab.execute(sub(Translation));

Translation=''' <Translation CheckBox="ON" UUID="26b085e8-d9a3-4baf-95f2-9f3eb75ac454">
  <tag Value="-1"/>
  <Name Value=""/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"M1","M2","M3","M4","M5","M6","Cluster1",</Body>
   </Entities>
  </SupportEntities>
  <RegionObject>
   <TranslationDirection>
    <DirectionVector Value="0.000000000000 m,1.000000000000 m,0.000000000000 m,"/>
   </TranslationDirection>
  </RegionObject>
  <UnitVector Value="0"/>
  <Magnitude Value="1"/>
  <DistanceVector Value="$Cluster1_Y"/>
  <CoorId Value="0"/>
  <Copy Value="0"/>
  <WithLBC Value="0"/>
  <No.Of.Copies Value="1"/>
  <LocalCoordinateSystem Value=""/>
  <Output/>
 </Translation>''';
simlab.execute(sub(Translation));

Translation=''' <Translation CheckBox="ON" UUID="26b085e8-d9a3-4baf-95f2-9f3eb75ac454">
  <tag Value="-1"/>
  <Name Value=""/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Cluster2","M7","M8","M9","M10","M11","M12",</Body>
   </Entities>
  </SupportEntities>
  <RegionObject>
   <TranslationDirection>
    <DirectionVector Value="1.000000000000 m,0.000000000000 m,0.000000000000 m,"/>
   </TranslationDirection>
  </RegionObject>
  <UnitVector Value="0"/>
  <Magnitude Value="1"/>
  <DistanceVector Value="$Cluster2_X"/>
  <CoorId Value="0"/>
  <Copy Value="0"/>
  <WithLBC Value="0"/>
  <No.Of.Copies Value="1"/>
  <LocalCoordinateSystem Value=""/>
  <Output/>
 </Translation>''';
simlab.execute(sub(Translation));

Translation=''' <Translation CheckBox="ON" UUID="26b085e8-d9a3-4baf-95f2-9f3eb75ac454">
  <tag Value="-1"/>
  <Name Value=""/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Cluster2","M7","M8","M9","M10","M11","M12",</Body>
   </Entities>
  </SupportEntities>
  <RegionObject>
   <TranslationDirection>
    <DirectionVector Value="0.000000000000 m,1.000000000000 m,0.000000000000 m,"/>
   </TranslationDirection>
  </RegionObject>
  <UnitVector Value="0"/>
  <Magnitude Value="1"/>
  <DistanceVector Value="$Cluster2_Y"/>
  <CoorId Value="0"/>
  <Copy Value="0"/>
  <WithLBC Value="0"/>
  <No.Of.Copies Value="1"/>
  <LocalCoordinateSystem Value=""/>
  <Output/>
 </Translation>''';
simlab.execute(sub(Translation));

Translation=''' <Translation CheckBox="ON" UUID="26b085e8-d9a3-4baf-95f2-9f3eb75ac454">
  <tag Value="-1"/>
  <Name Value=""/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"M13","M14","M15","M16","Cluster3",</Body>
   </Entities>
  </SupportEntities>
  <RegionObject>
   <TranslationDirection>
    <DirectionVector Value="1.000000000000 m,0.000000000000 m,0.000000000000 m,"/>
   </TranslationDirection>
  </RegionObject>
  <UnitVector Value="0"/>
  <Magnitude Value="1"/>
  <DistanceVector Value="$Cluster3_X"/>
  <CoorId Value="0"/>
  <Copy Value="0"/>
  <WithLBC Value="0"/>
  <No.Of.Copies Value="1"/>
  <LocalCoordinateSystem Value=""/>
  <Output/>
 </Translation>''';
simlab.execute(sub(Translation));

Translation=''' <Translation CheckBox="ON" UUID="26b085e8-d9a3-4baf-95f2-9f3eb75ac454">
  <tag Value="-1"/>
  <Name Value=""/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"M13","M14","M15","M16","Cluster3",</Body>
   </Entities>
  </SupportEntities>
  <RegionObject>
   <TranslationDirection>
    <DirectionVector Value="0.000000000000 m,1.000000000000 m,0.000000000000 m,"/>
   </TranslationDirection>
  </RegionObject>
  <UnitVector Value="0"/>
  <Magnitude Value="1"/>
  <DistanceVector Value="$Cluster3_Y"/>
  <CoorId Value="0"/>
  <Copy Value="0"/>
  <WithLBC Value="0"/>
  <No.Of.Copies Value="1"/>
  <LocalCoordinateSystem Value=""/>
  <Output/>
 </Translation>''';
simlab.execute(sub(Translation));

Translation=''' <Translation CheckBox="ON" UUID="26b085e8-d9a3-4baf-95f2-9f3eb75ac454">
  <tag Value="-1"/>
  <Name Value=""/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Cluster4","M17","M18","M19","M20",</Body>
   </Entities>
  </SupportEntities>
  <RegionObject>
   <TranslationDirection>
    <DirectionVector Value="1.000000000000 m,0.000000000000 m,0.000000000000 m,"/>
   </TranslationDirection>
  </RegionObject>
  <UnitVector Value="0"/>
  <Magnitude Value="1"/>
  <DistanceVector Value="$Cluster4_X"/>
  <CoorId Value="0"/>
  <Copy Value="0"/>
  <WithLBC Value="0"/>
  <No.Of.Copies Value="1"/>
  <LocalCoordinateSystem Value=""/>
  <Output/>
 </Translation>''';
simlab.execute(sub(Translation));

Translation=''' <Translation CheckBox="ON" UUID="26b085e8-d9a3-4baf-95f2-9f3eb75ac454">
  <tag Value="-1"/>
  <Name Value=""/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Cluster4","M17","M18","M19","M20",</Body>
   </Entities>
  </SupportEntities>
  <RegionObject>
   <TranslationDirection>
    <DirectionVector Value="0.000000000000 m,1.000000000000 m,0.000000000000 m,"/>
   </TranslationDirection>
  </RegionObject>
  <UnitVector Value="0"/>
  <Magnitude Value="1"/>
  <DistanceVector Value="$Cluster4_Y"/>
  <CoorId Value="0"/>
  <Copy Value="0"/>
  <WithLBC Value="0"/>
  <No.Of.Copies Value="1"/>
  <LocalCoordinateSystem Value=""/>
  <Output/>
 </Translation>''';
simlab.execute(sub(Translation));

Translation=''' <Translation CheckBox="ON" UUID="26b085e8-d9a3-4baf-95f2-9f3eb75ac454">
  <tag Value="-1"/>
  <Name Value=""/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Capacitor_T","Capacitor",</Body>
   </Entities>
  </SupportEntities>
  <RegionObject>
   <TranslationDirection>
    <DirectionVector Value="1.000000000000 m,0.000000000000 m,0.000000000000 m,"/>
   </TranslationDirection>
  </RegionObject>
  <UnitVector Value="0"/>
  <Magnitude Value="1"/>
  <DistanceVector Value="$Capacitor_X"/>
  <CoorId Value="0"/>
  <Copy Value="0"/>
  <WithLBC Value="0"/>
  <No.Of.Copies Value="1"/>
  <LocalCoordinateSystem Value=""/>
  <Output/>
 </Translation>''';
simlab.execute(sub(Translation));

Translation=''' <Translation CheckBox="ON" UUID="26b085e8-d9a3-4baf-95f2-9f3eb75ac454">
  <tag Value="-1"/>
  <Name Value=""/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Capacitor_T","Capacitor",</Body>
   </Entities>
  </SupportEntities>
  <RegionObject>
   <TranslationDirection>
    <DirectionVector Value="0.000000000000 m,1.000000000000 m,0.000000000000 m,"/>
   </TranslationDirection>
  </RegionObject>
  <UnitVector Value="0"/>
  <Magnitude Value="1"/>
  <DistanceVector Value="$Capacitor_Y"/>
  <CoorId Value="0"/>
  <Copy Value="0"/>
  <WithLBC Value="0"/>
  <No.Of.Copies Value="1"/>
  <LocalCoordinateSystem Value=""/>
  <Output/>
 </Translation>''';
simlab.execute(sub(Translation));


# ---------------------------------------------------------------------------
# PCB COPPER LOSS - part 2: read the centres AFTER moving, compute P and apply
# it as the heat source of the board. If anything fails, P0_PCB is applied,
# the error is written to pcb_length_detail.txt and pcb_loss.out is NOT written
# (so HyperStudy shows that run's P response as failed).
# ---------------------------------------------------------------------------
PCB_P, PCB_OK, _pcb_err = P0_PCB, False, ""
try:
    if isinstance(PCB_XY0, Exception):
        raise PCB_XY0
    PCB_XY1 = _pcb_read_points(PCB_LOG, "AFTER", before=PCB_XY0)
    PCB_L0, PCB_G0, PCB_S0 = _pcb_lengths(PCB_XY0)
    PCB_L1, PCB_G1, PCB_S1 = _pcb_lengths(PCB_XY1)
    PCB_P = P0_PCB * PCB_L1 / PCB_L0
    PCB_OK = True
except Exception:
    _pcb_err = traceback.format_exc()

with open("pcb_length_detail.txt", "w") as _f:
    if PCB_OK:
        _f.write("P = P0 * L / L0 = %.4f * %.6g / %.6g = %.4f W\n" % (P0_PCB, PCB_L1, PCB_L0, PCB_P))
        _f.write("original: Lin=%(Lin).6g  L1=%(L1).6g  L2=%(L2).6g\n" % PCB_G0)
        _f.write("new:      Lin=%(Lin).6g  L1=%(L1).6g  L2=%(L2).6g\n\n" % PCB_G1)
        _f.write("%-14s %12s %12s\n" % ("segment", "original", "new"))
        for _k in PCB_S1:
            _f.write("%-14s %12.6g %12.6g\n" % (_k, PCB_S0[_k], PCB_S1[_k]))
        _f.write("\n%-4s %26s %26s\n" % ("pt", "original (x, y)", "new (x, y)"))
        for _k in PCB_XY1:
            _f.write("%-4s %12.6g,%12.6g %12.6g,%12.6g\n" % ((_k,) + PCB_XY0[_k] + PCB_XY1[_k]))
    else:
        _f.write("P calculation FAILED - applied P0 = %.4f W\n\n%s" % (P0_PCB, _pcb_err))
    _f.write("\nraw SimLab output:\n" + "\n".join(PCB_LOG) + "\n")

if PCB_OK:
    with open("pcb_loss.out", "w") as _f:      # HyperStudy response: P in W
        _f.write("%.6f\n" % PCB_P)

# --- your recorded heat-source command, with $Power_pcb replaced by the new P ---
UnitSystem=''' <UnitSystem UUID="3aca8564-4d38-4b0b-887c-6a542d4001c6">
  <SetCurrentDisplaySystem Name="MKS (m kg N C s)"/>
 </UnitSystem>''';
simlab.execute(UnitSystem);

HeatSource=''' <HeatSource Auto="1" BCType="HeatSource" CheckBox="ON" UUID="925c662d-f9a8-4007-9cc3-ce9f16811005" isObject="2">
  <tag Value="45"/>
  <Name Value="HeatSource_pcb"/>
  <Entities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Board_1",</Body>
   </Entities>
  </Entities>
  <Option Value="4"/>
  <HeatFlux Value="1.5e09 W/m3"/>
  <TotalHeatSource Value="0 W"/>
  <DessipationFromEachBody Value="$Power_pcb"/>
  <fieldtable Index="0" Value="None"/>
  <OptionType Value="DessipationEachBody"/>
  <HeatSourceType Index="0" Value="Spherical"/>
  <Radius Value="0 m"/>
  <FrontLength Value="0 m"/>
  <RearLength Value="0 m"/>
  <Width Value="0 m"/>
  <Depth Value="0 m"/>
  <TimeDependentTable Index="0" Value="None"/>
  <SolutionName Value="ElectronicsThermal"/>
  <HeatMultiplier Value="None"/>
 </HeatSource>''';
simlab.execute(HeatSource.replace("$Power_pcb", "%.6f W" % PCB_P));
# ---------------------------------------------------------------------------

GeometryDiscretization=''' <CartesianHexMesh UUID="61d3b847-a7d3-4fe3-bcb7-dd3ccb1dc26a">
  <InputBodies>
   <Entities>
    <Model>$Geometry</Model>
    <Body></Body>
   </Entities>
  </InputBodies>
  <MeshSize Value="1"/>
  <Isotropic Value="0"/>
  <Anisotropic Value="1"/>
  <MeshSizeX Value="1"/>
  <MeshSizeY Value="1"/>
  <MeshSizeZ Value="1"/>
  <MinimumKeyPlaneDist Value="0.10000000000000001"/>
  <PreserveFacesParallelTo XYPlane="" YZPlane="" ZXPlane=""/>
  <CreateAirBody Value="0"/>
  <SolutionName Value="ElectronicsThermal"/>
  <UpdateSolution Value="1"/>
  <SkipGDbodyCreation Value="1"/>
 </CartesianHexMesh>''';
simlab.execute(GeometryDiscretization);

ExportandSolve=''' <ExportStaticSolverInput UUID="f009bc99-991f-43b7-8c87-cc606ef9c443" pixmap="solution">
  <FileName Value=""/>
  <SolutionName Value="ElectronicsThermal"/>
  <LoadCase Value=""/>
  <Renumber Value="0"/>
  <RunSolver Value="1"/>
  <DataCheck Value="0"/>
  <RemoveOrphanNodes Value="1"/>
  <Version Value="15"/>
  <ExportOptionsVersion Value="1"/>
  <RemoteSolve Value="0"/>
  <CopyIncludeFiles Value="1"/>
  <IsModelChanged Value="1"/>
  <ResultUpdateAlone Value="0"/>
 </ExportStaticSolverInput>''';
simlab.execute(ExportandSolve);

RemoveLoadFromSolution=''' <RemoveLoadFromSolution UUID="8f07ee4a-6359-4484-b9f0-c4362e8fd727">
  <Load BCType="Solution Response" Global="" Initial="" LoadType="-11" Loadcase="" Name="Temperature_Capacitor" Solution="ElectronicsThermal"/>
  <Load BCType="Solution Response" LoadType="-11" Name="Temperature_Board" Solution="ElectronicsThermal"/>
  <Load BCType="Solution Response" LoadType="-11" Name="Temperature_Inductor2" Solution="ElectronicsThermal"/>
  <Load BCType="Solution Response" LoadType="-11" Name="Temperature_Inductor1" Solution="ElectronicsThermal"/>
  <Load BCType="Solution Response" LoadType="-11" Name="Temperature_Cluster4" Solution="ElectronicsThermal"/>
  <Load BCType="Solution Response" LoadType="-11" Name="Temperature_Cluster3" Solution="ElectronicsThermal"/>
  <Load BCType="Solution Response" LoadType="-11" Name="Temperature_Cluster2" Solution="ElectronicsThermal"/>
  <Load BCType="Solution Response" LoadType="-11" Name="Temperature_Transformer" Solution="ElectronicsThermal"/>
  <Load BCType="Solution Response" LoadType="-11" Name="Temperature_Cluster1" Solution="ElectronicsThermal"/>
 </RemoveLoadFromSolution>''';
simlab.execute(RemoveLoadFromSolution);

Sensor=''' <CreateResponseNew BCType="Solution Response" UUID="a7326802-d869-41d4-a46d-d4d5c159d938">
  <tag Value="-1"/>
  <Name Value="Temperature_Cluster1"/>
  <Response Component="" LoadCase="" ModeIndex="" Type="Temperature"/>
  <AllBodies Value="0"/>
  <CoordinateAxisID Index="0" Value="Global"/>
  <Points Value="0"/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Cluster1",</Body>
   </Entities>
  </SupportEntities>
  <Regions/>
  <Sets Value=""/>
  <Interested_Regions/>
  <Ignore_Regions/>
  <ValueType Value="Maximum"/>
  <Sets Value=""/>
  <SurfaceOutputs Check="0" Value=""/>
  <ComputationType Value="0"/>
  <NormalModeNumber Value=""/>
  <RefBodyForSharedInput/>
  <SolutionName Value="ElectronicsThermal"/>
  <EFloResponse Value="1"/>
 </CreateResponseNew>''';
simlab.execute(Sensor);

Sensor=''' <CreateResponseNew BCType="Solution Response" UUID="a7326802-d869-41d4-a46d-d4d5c159d938">
  <tag Value="-1"/>
  <Name Value="Temperature_Cluster2"/>
  <Response Component="" LoadCase="" ModeIndex="" Type="Temperature"/>
  <AllBodies Value="0"/>
  <CoordinateAxisID Index="0" Value="Global"/>
  <Points Value="0"/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Cluster2",</Body>
   </Entities>
  </SupportEntities>
  <Regions/>
  <Sets Value=""/>
  <Interested_Regions/>
  <Ignore_Regions/>
  <ValueType Value="Maximum"/>
  <Sets Value=""/>
  <SurfaceOutputs Check="0" Value=""/>
  <ComputationType Value="0"/>
  <NormalModeNumber Value=""/>
  <RefBodyForSharedInput/>
  <SolutionName Value="ElectronicsThermal"/>
  <EFloResponse Value="1"/>
 </CreateResponseNew>''';
simlab.execute(Sensor);

Sensor=''' <CreateResponseNew BCType="Solution Response" UUID="a7326802-d869-41d4-a46d-d4d5c159d938">
  <tag Value="-1"/>
  <Name Value="Temperature_Cluster3"/>
  <Response Component="" LoadCase="" ModeIndex="" Type="Temperature"/>
  <AllBodies Value="0"/>
  <CoordinateAxisID Index="0" Value="Global"/>
  <Points Value="0"/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Cluster3",</Body>
   </Entities>
  </SupportEntities>
  <Regions/>
  <Sets Value=""/>
  <Interested_Regions/>
  <Ignore_Regions/>
  <ValueType Value="Maximum"/>
  <Sets Value=""/>
  <SurfaceOutputs Check="0" Value=""/>
  <ComputationType Value="0"/>
  <NormalModeNumber Value=""/>
  <RefBodyForSharedInput/>
  <SolutionName Value="ElectronicsThermal"/>
  <EFloResponse Value="1"/>
 </CreateResponseNew>''';
simlab.execute(Sensor);

Sensor=''' <CreateResponseNew BCType="Solution Response" UUID="a7326802-d869-41d4-a46d-d4d5c159d938">
  <tag Value="-1"/>
  <Name Value="Temperature_Cluster4"/>
  <Response Component="" LoadCase="" ModeIndex="" Type="Temperature"/>
  <AllBodies Value="0"/>
  <CoordinateAxisID Index="0" Value="Global"/>
  <Points Value="0"/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Cluster4",</Body>
   </Entities>
  </SupportEntities>
  <Regions/>
  <Sets Value=""/>
  <Interested_Regions/>
  <Ignore_Regions/>
  <ValueType Value="Maximum"/>
  <Sets Value=""/>
  <SurfaceOutputs Check="0" Value=""/>
  <ComputationType Value="0"/>
  <NormalModeNumber Value=""/>
  <RefBodyForSharedInput/>
  <SolutionName Value="ElectronicsThermal"/>
  <EFloResponse Value="1"/>
 </CreateResponseNew>''';
simlab.execute(Sensor);

Sensor=''' <CreateResponseNew BCType="Solution Response" UUID="a7326802-d869-41d4-a46d-d4d5c159d938">
  <tag Value="-1"/>
  <Name Value="Temperature_Capacitor"/>
  <Response Component="" LoadCase="" ModeIndex="" Type="Temperature"/>
  <AllBodies Value="0"/>
  <CoordinateAxisID Index="0" Value="Global"/>
  <Points Value="0"/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Capacitor",</Body>
   </Entities>
  </SupportEntities>
  <Regions/>
  <Sets Value=""/>
  <Interested_Regions/>
  <Ignore_Regions/>
  <ValueType Value="Maximum"/>
  <Sets Value=""/>
  <SurfaceOutputs Check="0" Value=""/>
  <ComputationType Value="0"/>
  <NormalModeNumber Value=""/>
  <RefBodyForSharedInput/>
  <SolutionName Value="ElectronicsThermal"/>
  <EFloResponse Value="1"/>
 </CreateResponseNew>''';
simlab.execute(Sensor);

Sensor=''' <CreateResponseNew BCType="Solution Response" UUID="a7326802-d869-41d4-a46d-d4d5c159d938">
  <tag Value="-1"/>
  <Name Value="Temperature_Inductor1"/>
  <Response Component="" LoadCase="" ModeIndex="" Type="Temperature"/>
  <AllBodies Value="0"/>
  <CoordinateAxisID Index="0" Value="Global"/>
  <Points Value="0"/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"DabInd1",</Body>
   </Entities>
  </SupportEntities>
  <Regions/>
  <Sets Value=""/>
  <Interested_Regions/>
  <Ignore_Regions/>
  <ValueType Value="Maximum"/>
  <Sets Value=""/>
  <SurfaceOutputs Check="0" Value=""/>
  <ComputationType Value="0"/>
  <NormalModeNumber Value=""/>
  <RefBodyForSharedInput/>
  <SolutionName Value="ElectronicsThermal"/>
  <EFloResponse Value="1"/>
 </CreateResponseNew>''';
simlab.execute(Sensor);

Sensor=''' <CreateResponseNew BCType="Solution Response" UUID="a7326802-d869-41d4-a46d-d4d5c159d938">
  <tag Value="-1"/>
  <Name Value="Temperature_Inductor2"/>
  <Response Component="" LoadCase="" ModeIndex="" Type="Temperature"/>
  <AllBodies Value="0"/>
  <CoordinateAxisID Index="0" Value="Global"/>
  <Points Value="0"/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"DabInd2",</Body>
   </Entities>
  </SupportEntities>
  <Regions/>
  <Sets Value=""/>
  <Interested_Regions/>
  <Ignore_Regions/>
  <ValueType Value="Maximum"/>
  <Sets Value=""/>
  <SurfaceOutputs Check="0" Value=""/>
  <ComputationType Value="0"/>
  <NormalModeNumber Value=""/>
  <RefBodyForSharedInput/>
  <SolutionName Value="ElectronicsThermal"/>
  <EFloResponse Value="1"/>
 </CreateResponseNew>''';
simlab.execute(Sensor);

Sensor=''' <CreateResponseNew BCType="Solution Response" UUID="a7326802-d869-41d4-a46d-d4d5c159d938">
  <tag Value="-1"/>
  <Name Value="Temperature_Transformer"/>
  <Response Component="" LoadCase="" ModeIndex="" Type="Temperature"/>
  <AllBodies Value="0"/>
  <CoordinateAxisID Index="0" Value="Global"/>
  <Points Value="0"/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Transformer",</Body>
   </Entities>
  </SupportEntities>
  <Regions/>
  <Sets Value=""/>
  <Interested_Regions/>
  <Ignore_Regions/>
  <ValueType Value="Maximum"/>
  <Sets Value=""/>
  <SurfaceOutputs Check="0" Value=""/>
  <ComputationType Value="0"/>
  <NormalModeNumber Value=""/>
  <RefBodyForSharedInput/>
  <SolutionName Value="ElectronicsThermal"/>
  <EFloResponse Value="1"/>
 </CreateResponseNew>''';
simlab.execute(Sensor);

Sensor=''' <CreateResponseNew BCType="Solution Response" UUID="a7326802-d869-41d4-a46d-d4d5c159d938">
  <tag Value="-1"/>
  <Name Value="Temperature_Board"/>
  <Response Component="" LoadCase="" ModeIndex="" Type="Temperature"/>
  <AllBodies Value="0"/>
  <CoordinateAxisID Index="0" Value="Global"/>
  <Points Value="0"/>
  <SupportEntities>
   <Entities>
    <Model>$Geometry</Model>
    <Body>"Board",</Body>
   </Entities>
  </SupportEntities>
  <Regions/>
  <Sets Value=""/>
  <Interested_Regions/>
  <Ignore_Regions/>
  <ValueType Value="Maximum"/>
  <Sets Value=""/>
  <SurfaceOutputs Check="0" Value=""/>
  <ComputationType Value="0"/>
  <NormalModeNumber Value=""/>
  <RefBodyForSharedInput/>
  <SolutionName Value="ElectronicsThermal"/>
  <EFloResponse Value="1"/>
 </CreateResponseNew>''';
simlab.execute(Sensor);

UpdateResponses=''' <UpdateResponses UUID="867bf814-69c7-43cb-8566-78bd2a3d4e5f"/>''';
try:
    simlab.execute(UpdateResponses);
except Exception:
    pass

ExportResponses=''' <ExportResponses UUID="a4588528-6526-4b0d-951c-6cc91eac83c4">
  <FileName Value="hyper7_Responses.slresponse"/>
 </ExportResponses>''';
simlab.execute(ExportResponses);

# Saves the moved, solved model into the run folder so you can open it and check
# the positions and temperatures. Delete this block for the full DOE (large files).
ExportSlb=''' <ExportSlb UUID="a155cd6e-8ae6-4720-8ab4-1f50d4a34d1c">
  <tag Value="-1"/>
  <Name Value=""/>
  <Option Value="1"/>
  <FileName Value="./hyper7_Database.slb"/>
 </ExportSlb>''';
try:
    simlab.execute(ExportSlb);
except Exception:
    pass
