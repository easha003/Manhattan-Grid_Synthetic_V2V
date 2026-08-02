# GRAIL-V Code Implementation Specification

**Status:** implementation contract

**Companion research plan:** [`GRAIL_V_WORK_PLAN_V2.md`](GRAIL_V_WORK_PLAN_V2.md)

**Initial implementation language:** Python

**Supported Python:** 3.11 and 3.12

**Detected local SUMO:** Eclipse SUMO 1.27.0 in a Python 3.11.8 environment

This document defines the software architecture that will implement GRAIL-V. It
describes module responsibilities, interfaces, data schemas, configuration,
execution flows, tests, artifacts, and implementation order. Runtime code should
not diverge from these contracts without updating this document and recording the
reason in the decision log.

---

## 1. Engineering objectives

The software must support five distinct activities without mixing their
responsibilities:

1. Generate and validate microscopic urban mobility traces.
2. Convert shared geometry into hidden RF and VLC channel state.
3. Expose causal, noisy, age-aware observations to deployable policies.
4. Train and evaluate RF/VLC/DUP policies under per-density reliability budgets.
5. Reproduce every table and figure from immutable configurations and artifacts.

The implementation must make it difficult to:

- leak simulator truth into a policy;
- treat random packets as independent when evaluating bursty failures;
- silently change units or service profiles;
- advance random-number streams differently for different policies;
- use an RF equation for VLC without an explicit adapter;
- call normalized activation cost “energy”;
- claim a constraint using only a point estimate;
- train on a physically infeasible packet profile; or
- produce an untraceable result without configuration and code hashes.

### 1.1 Fixed cross-module assumptions

| Contract | Implementation value |
|---|---:|
| Main information block | 300 bytes |
| Packet generation | Every 100 ms |
| Main radio-interface deadline | 3 ms |
| Main miss budget | \(10^{-4}\) per density |
| Secondary miss budget | \(10^{-5}\) at the same payload and deadline |
| Action set | RF, VLC, simultaneous DUP |
| Link attempts | At most one committed attempt per selected link |
| Feedback HARQ in deadline | Disabled |
| Synthetic network | 6 avenues × 12 cross streets |
| Grid spacing | 244 m × 61 m |
| Speed limit | 11.18 m/s |
| Training density | 20, 40, 60 vehicles/lane-km |
| Main activation costs | RF 1, VLC 1, DUP 2 |
| Policy timing | Immediately before known periodic packet generation |
| Primary evaluation | At least \(10^6\) packets and 200 trajectory/pair clusters per policy-density cell |
| Claimed \(10^{-5}\) evaluation | At least \(10^7\) packets plus qualifying one-sided cluster-aware bound |

These assumptions live in configuration rather than scattered constants, but
cross-module validation treats them as the headline contract.

---

## 2. Non-goals for the conference implementation

The initial code will not implement:

- multi-agent or network-wide resource control;
- feedback HARQ inside the radio-interface deadline (a 5.9 GHz FR1 round trip
  does not fit even at 60 kHz SCS);
- queuing across packet deadlines;
- perpendicular/intersection V-VLC with side-facing receivers;
- rain, fog, or snow;
- a recurrent neural policy;
- online SUMO/RL co-simulation during every training step;
- a complete NR protocol stack inside Python;
- a claim of exact NYC-wide traffic reproduction; or
- a formal safety verification engine.

These are possible extensions, not partially implemented hidden features.

---

## 3. Runtime and tooling decision

### 3.1 Python environment

The project will use Python 3.11 or 3.12. Python 3.14 is not the implementation
target because the detected SUMO/TraCI installation uses Python 3.11 and some
scientific/RL packages may not yet support 3.14 consistently.

The first local environment should reuse or mirror:

```text
/Users/eashraque/SUMO/sumo_test/bin/python
```

The absolute path is a local setup fact and must not be embedded in portable
configuration. Runtime discovery will use a user-supplied `SUMO_HOME` or explicit
CLI option.

### 3.2 Packaging

The repository will use:

- `pyproject.toml`;
- a `src/` package layout;
- editable development installation;
- console entry point `grailv`;
- lockable dependency groups for runtime, mobility, training, and development.

### 3.3 Expected dependencies

Core runtime:

- NumPy;
- SciPy;
- Pydantic;
- PyYAML;
- PyArrow;
- Shapely;
- Gymnasium;
- PyTorch;
- Typer;
- structured Python logging.

Analysis:

- pandas or Polars;
- Matplotlib;
- Seaborn;
- statsmodels only where its statistical routines are explicitly used.

Development:

- pytest;
- pytest-cov;
- Hypothesis for geometry/property tests;
- Ruff;
- mypy.

External tools:

- SUMO 1.27.0 or a manifest-recorded compatible release;
- 5G-LENA/NS-3 for offline NR-V2X Mode-2 calibration;
- optional Veins-VLC installation for offline optical cross-checking.

5G-LENA and Veins-VLC are external calibration systems, not hidden Python
dependencies.

---

## 4. Repository layout

```text
CMDP_PPO/
├── pyproject.toml
├── README.md
├── CODE_IMPLEMENTATION_SPEC.md
├── GRAIL_V_WORK_PLAN_V2.md
├── CHANGELOG.md
├── configs/
│   ├── project/
│   │   └── default.yaml
│   ├── mobility/
│   │   ├── synthetic_manhattan.yaml
│   │   └── nyc_osm.yaml
│   ├── service/
│   │   ├── ev2x_300B_3ms_1e-4.yaml
│   │   └── ev2x_300B_3ms_1e-5.yaml
│   ├── channel/
│   │   ├── rf_nr_v2x.yaml
│   │   └── vlc_vehicle.yaml
│   ├── observation/
│   │   └── causal_200ms_forecast.yaml
│   ├── training/
│   │   └── primal_dual_ppo.yaml
│   └── evaluation/
│       ├── primary.yaml
│       └── ultra_reliability.yaml
├── src/
│   └── grail_v/
│       ├── __init__.py
│       ├── cli.py
│       ├── core/
│       ├── config/
│       ├── mobility/
│       ├── geometry/
│       ├── channels/
│       │   ├── rf/
│       │   └── vlc/
│       ├── phy/
│       ├── prediction/
│       ├── observation/
│       ├── env/
│       ├── agents/
│       ├── baselines/
│       ├── evaluation/
│       ├── artifacts/
│       └── visualization/
├── tools/
│   ├── fiveg_lena/
│   └── veins_vlc/
├── scripts/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── statistical/
│   ├── regression/
│   └── fixtures/
├── artifacts/
│   ├── manifests/
│   ├── calibration/
│   ├── traces/
│   ├── checkpoints/
│   ├── evaluations/
│   └── figures/
├── paper/
└── research/
```

`artifacts/` contains generated data and will normally be ignored by version
control except for compact manifests and explicitly approved reference fixtures.

---

## 5. Dependency direction

Allowed dependency direction:

```text
core
  ↑
config
  ↑
mobility ──→ geometry
               ↑
       channels/rf  channels/vlc
               ↑
        prediction + observation
               ↑
              phy
               ↑
              env
        ↙              ↘
   baselines          agents
        ↘              ↙
          evaluation
               ↑
        visualization
```

Rules:

- `core` imports no project package.
- `mobility` does not import channels, policies, or training.
- RF and VLC modules do not import one another.
- `geometry` does not know which action a policy chooses.
- `observation` may read hidden truth only through sensor-model interfaces that
  explicitly add delay/noise and strip forbidden fields.
- `env` composes modules but contains no channel equations.
- `agents` use only environment/rollout contracts, never SUMO or geometry.
- `evaluation` may run policies but may not alter their checkpoints.
- `visualization` consumes saved results; it does not rerun experiments.

Circular imports are architectural errors.

---

## 6. Core module

Path: `src/grail_v/core/`

### 6.1 `enums.py`

Defines stable enums:

```python
class Action(IntEnum):
    RF = 0
    VLC = 1
    DUP = 2

class Link(StrEnum):
    RF = "rf"
    VLC = "vlc"

class RFPropagationState(StrEnum):
    LOS = "los"
    NLOSV = "nlosv"
    NLOS = "nlos"

class FailureCause(StrEnum):
    NONE = "none"
    RF_COLLISION = "rf_collision"
    RF_CHANNEL = "rf_channel"
    VLC_OCCLUSION = "vlc_occlusion"
    VLC_ALIGNMENT = "vlc_alignment"
    VLC_CHANNEL = "vlc_channel"
    PHY_INFEASIBLE = "phy_infeasible"
    DECODING_LATE = "decoding_late"
    JOINT_FAILURE = "joint_failure"

class DatasetSplit(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
```

Stored integer/string values are part of the artifact schema and cannot be
renumbered casually.

### 6.2 `types.py`

Contains immutable dataclasses used across modules:

```python
@dataclass(frozen=True, slots=True)
class VehicleState:
    vehicle_id: str
    time_s: float
    x_m: float
    y_m: float
    heading_rad: float
    speed_mps: float
    acceleration_mps2: float
    length_m: float
    width_m: float
    height_m: float
    lane_id: str
    edge_id: str
    route_id: str

@dataclass(frozen=True, slots=True)
class PairState:
    time_s: float
    tx: VehicleState
    rx: VehicleState
    distance_m: float
    same_route: bool

@dataclass(frozen=True, slots=True)
class ServiceProfile:
    name: str
    payload_bytes: int
    generation_period_s: float
    deadline_s: float
    miss_budget: float

@dataclass(frozen=True, slots=True)
class LinkAttemptResult:
    link: Link
    selected: bool
    success: bool
    arrival_time_s: float | None
    conditional_failure_probability: float
    failure_cause: FailureCause

@dataclass(frozen=True, slots=True)
class PacketOutcome:
    packet_id: str
    generation_time_s: float
    action: Action
    delivered: bool
    deadline_missed: bool
    delivery_time_s: float | None
    rf: LinkAttemptResult
    vlc: LinkAttemptResult
    activation_cost: float
```

Only universally shared structures belong here. Large arrays and implementation-
specific model tensors remain in their owning modules.

### 6.3 `protocols.py`

Defines behavior contracts using `typing.Protocol`:

```python
class Policy(Protocol):
    def reset(self, context: "EpisodeContext") -> None: ...
    def act(self, observation: NDArray[np.float32], *, deterministic: bool) -> Action: ...

class RFChannel(Protocol):
    def evaluate(self, request: "RFChannelRequest") -> "RFChannelResult": ...

class VLCChannel(Protocol):
    def evaluate(self, request: "VLCChannelRequest") -> "VLCChannelResult": ...

class BlockagePredictor(Protocol):
    def predict(self, tracks: "TrackSet", horizon_s: float) -> "BlockageForecast": ...
```

Protocols keep environment composition testable and allow analytical,
calibrated, or mocked implementations.

### 6.4 `units.py`

Policy:

- internal distance: meters;
- time: seconds;
- angle: radians;
- frequency: hertz;
- power at API boundaries: watts, with explicit dBm conversion helpers;
- probability: `[0, 1]`;
- density: vehicles per lane-kilometer.

Functions such as `dbm_to_w`, `w_to_dbm`, `db_to_linear`, and
`linear_to_db` live here. No module defines private conversion formulas.

### 6.5 `errors.py`

Project-specific exceptions:

- `ConfigurationError`;
- `ArtifactVersionError`;
- `PhysicalInfeasibilityError`;
- `ObservationLeakageError`;
- `TraceIntegrityError`;
- `CalibrationError`;
- `StatisticalPowerError`.

Errors must identify the relevant configuration hash and artifact path.

### 6.6 `randomness.py`

All random generators derive from a named root seed:

```python
RandomStreams(
    mobility=...,
    sensor=...,
    shadowing=...,
    fading=...,
    collision=...,
    decoding=...,
    policy=...,
    bootstrap=...,
)
```

Child seeds are derived by a stable hash of:

```text
(root_seed, stream_name, trace_id, episode_id, packet_index)
```

No module uses the global NumPy, Python, or PyTorch RNG implicitly.

---

## 7. Configuration module

Path: `src/grail_v/config/`

### 7.1 Responsibilities

- Parse layered YAML configuration.
- Validate types and physical cross-field invariants.
- Resolve relative paths against the project root.
- Produce a canonical JSON representation.
- Compute the configuration hash.
- Save the exact resolved configuration with every artifact.

### 7.2 Files

`models.py`
: Pydantic models for every configuration section.

`loader.py`
: Loads and merges explicit configuration files in a deterministic order.

`validation.py`
: Cross-section checks not expressible in one Pydantic model.

`hashing.py`
: Canonical serialization and SHA-256 hashes.

### 7.3 Top-level model

```python
class ProjectConfig(BaseModel):
    schema_version: str
    project: ProjectMetadataConfig
    mobility: MobilityConfig
    service: ServiceConfig
    geometry: GeometryConfig
    rf: RFConfig
    vlc: VLCConfig
    observation: ObservationConfig
    cost: CostConfig
    environment: EnvironmentConfig
    training: TrainingConfig
    evaluation: EvaluationConfig
    paths: PathConfig
```

### 7.4 Mandatory validation

The loader rejects configurations when:

- `payload_bytes <= 0`;
- generation period or deadline is nonpositive;
- miss budget is not in `(0, 1)`;
- a selected PHY cannot fit the configured information/coded block;
- mobility step exceeds the predictor update assumptions without interpolation;
- a sensor latency is negative;
- a training density lacks a multiplier definition;
- DUP cost is not the sum of its committed leg costs;
- train/validation/test trace IDs overlap;
- the evaluation target is \(10^{-5}\) but its required sample plan is absent;
- a policy observation requests a forbidden hidden field.

### 7.5 Resolved configuration example

```yaml
schema_version: "1.0"

project:
  name: "grail-v"
  experiment: "headline"

service:
  payload_bytes: 300
  generation_period_s: 0.1
  deadline_s: 0.001
  miss_budget: 0.0001
  predecision_lead_s: 0.0001
  harq_enabled: false

mobility:
  kind: "synthetic_manhattan"
  grid:
    avenues: 6
    cross_streets: 12
    avenue_spacing_m: 244.0
    cross_street_spacing_m: 61.0
  step_s: 0.05
  speed_limit_mps: 11.18
  target_densities_veh_per_lane_km: [20.0, 40.0, 60.0]

rf:
  carrier_hz: 5.9e9
  bandwidth_hz: 1.0e7
  subcarrier_spacing_hz: 3.0e4
  slot_s: 0.0005
  tx_power_dbm: 23.0
  calibration_artifact: "artifacts/calibration/rf/mode2-v1"

vlc:
  electrical_bandwidth_hz: 5.0e6
  pattern_artifact: "artifacts/calibration/vlc/headlamp-v1"
  complete_blockage_main: true

cost:
  rf_activation: 1.0
  vlc_activation: 1.0
  dup_activation: 2.0

observation:
  history_packets: 8
  track_update_s: 0.05
  track_latency_s: 0.05
  position_noise_std_m: 0.5
  speed_noise_std_mps: 0.2
  forecast_horizon_s: 0.2
```

---

## 8. Mobility module

Path: `src/grail_v/mobility/`

SUMO is used only here. Training and evaluation read saved traces and do not
require a live SUMO process.

### 8.1 `sumo_runtime.py`

Responsibilities:

- locate `sumo`, `sumo-gui`, `netgenerate`, `netconvert`, and TraCI;
- validate SUMO version;
- build safe subprocess argument arrays;
- record executable paths and versions in manifests;
- never invoke commands through shell string concatenation.

Public interface:

```python
@dataclass(frozen=True)
class SumoRuntime:
    sumo: Path
    sumo_gui: Path | None
    netgenerate: Path
    netconvert: Path
    version: str

def discover_sumo(explicit_home: Path | None = None) -> SumoRuntime: ...
```

### 8.2 `synthetic_grid.py`

Class: `SyntheticManhattanBuilder`

Does:

- generate the 6-avenue × 12-cross-street rectangular network;
- set 244 m and 61 m spacings;
- assign one lane per direction;
- set 11.18 m/s speed;
- configure signalized intersections;
- stagger traffic-light offsets;
- emit source configuration and generated `.net.xml`.

Does not:

- insert vehicles;
- calculate communication channels;
- select tagged pairs.

### 8.3 `vehicle_types.py`

Defines passenger car, van/SUV, and heavy-vehicle SUMO types. It converts the
research-plan mixture into explicit SUMO type distributions and stores all
dimensions in the trace.

### 8.4 `demand.py`

Class: `BoundaryDemandGenerator`

Inputs:

- network boundary edges;
- turn probabilities;
- requested flow scale;
- vehicle-type mixture;
- simulation duration;
- mobility seed.

Outputs:

- route/flow XML;
- route-generation manifest.

Arrivals may be exponential/Poisson at network boundaries. The module must not
claim that resulting vehicle positions are Poisson.

### 8.5 `density_calibration.py`

Class: `DensityCalibrator`

Purpose:

- run short SUMO simulations;
- measure post-warm-up vehicles per lane-km;
- tune boundary flow using bounded search;
- stop when realized density is within 5% of target;
- detect insertion saturation and gridlock.

Outputs:

```python
@dataclass(frozen=True)
class DensityCalibrationResult:
    target_density: float
    realized_density_mean: float
    realized_density_std: float
    flow_scale: float
    mean_speed_mps: float
    stopped_fraction: float
    insertion_failures: int
    stable: bool
```

### 8.6 `trace_generator.py`

Class: `SumoTraceGenerator`

Responsibilities:

- run 300 s warm-up;
- record 900–1,800 s after warm-up;
- sample at 50 ms;
- export all vehicle states and traffic-signal states;
- record route and vehicle-type metadata;
- write partitioned Parquet;
- produce integrity checks and manifest.

Trace storage:

```text
artifacts/traces/<trace_id>/
├── vehicles/
│   └── part-*.parquet
├── signals.parquet
├── network.net.xml
├── routes.rou.xml
├── resolved_config.yaml
└── manifest.json
```

Vehicle Parquet columns:

```text
trace_id, time_s, vehicle_id, x_m, y_m, heading_rad, speed_mps,
acceleration_mps2, length_m, width_m, height_m, lane_id, edge_id,
route_id, vehicle_type
```

### 8.7 `tagged_pairs.py`

Class: `TaggedPairExtractor`

Finds natural same-direction, same-route pair segments:

- initial separation 10–60 m;
- no forced position or teleportation;
- route remains shared;
- stores pair start/end and eligibility;
- records whether another vehicle lies between them.

Training episodes last for at most 60 s. An episode terminates early when the pair
leaves the 10–60 m range continuously for one second or the routes diverge.
Shorter eligible segments are never silently padded.

Output schema:

```text
trace_id, pair_id, tx_id, rx_id, start_s, end_s,
initial_distance_m, route_id, eligibility_reason
```

### 8.8 `nyc_osm.py`

Class: `NYCNetworkImporter`

Responsibilities:

- import a fixed OSM snapshot and bounding box;
- preserve source metadata and licensing;
- run SUMO network conversion;
- expose an audit report for connectivity, turn restrictions, directions, lane
  counts, signal programs, and teleportation;
- apply corrections from explicit patch files;
- never edit the imported network silently.

The selected region is a Gate-1 artifact, not a constant hidden in Python.

### 8.9 `nyc_demand.py`

Loads NYC DOT count data, filters the chosen date/time and locations, maps counts
to network approaches, and calibrates boundary flows. Raw municipal data remains
separate from derived SUMO flows.

---

## 9. Geometry module

Path: `src/grail_v/geometry/`

### 9.1 `primitives.py`

Defines:

- two-dimensional vectors;
- line segments;
- oriented vehicle rectangles;
- height intervals;
- angle normalization;
- polygon intersection wrappers.

Shapely is the initial correctness implementation. Performance-sensitive
operations may later receive vectorized NumPy implementations that must agree
with Shapely regression fixtures.

### 9.2 `spatial_index.py`

Maintains an STRtree or equivalent index for:

- building polygons, static per trace;
- vehicle rectangles, dynamic per snapshot.

It returns candidate blockers before exact intersection tests.

### 9.3 `pair_geometry.py`

Function:

```python
def compute_pair_geometry(
    tx: VehicleState,
    rx: VehicleState,
    tx_emitter_offset: NDArray[np.float64],
    rx_detector_offset: NDArray[np.float64],
) -> PairGeometry:
    ...
```

`PairGeometry` contains:

- center and optical range;
- relative bearing;
- heading difference;
- irradiance angle;
- incidence angle;
- lateral offset;
- FOV margin;
- transmitter and receiver world coordinates.

### 9.4 `vehicle_occlusion.py`

Class: `VehicleOcclusionEngine`

Determines whether the optical segment intersects a candidate blocker whose
height covers the emitter-detector line. It returns:

```python
@dataclass(frozen=True)
class OcclusionTruth:
    blocked: bool
    blocker_ids: tuple[str, ...]
    first_intersection_distance_m: float | None
```

Blocker IDs are hidden simulator metadata and never placed in policy
observations.

### 9.5 `rf_visibility.py`

Class: `RFVisibilityClassifier`

Decision:

- building intersection → `NLOS`;
- otherwise relevant vehicle obstruction → `NLOSV`;
- otherwise → `LOS`.

The exact priority and vehicle-height condition follow the selected 3GPP channel
implementation and are tested.

### 9.6 `intersection_context.py`

Computes:

- distance to next intersection;
- distance since previous intersection;
- current road segment class;
- signal phase visible from map/vehicle context if configured.

Only quantities plausibly known from onboard maps may pass to observation.

### 9.7 `engine.py`

Class: `SharedGeometryEngine`

One call returns all hidden geometric truth:

```python
@dataclass(frozen=True)
class GeometryTruth:
    pair: PairGeometry
    optical_occlusion: OcclusionTruth
    rf_state: RFPropagationState
    distance_to_intersection_m: float
    exact_neighbor_states: tuple[VehicleState, ...]

def evaluate(snapshot: TrafficSnapshot, pair: PairState) -> GeometryTruth: ...
```

This is the only common source for RF and VLC geometry.

---

## 10. RF channel module

Path: `src/grail_v/channels/rf/`

### 10.1 `pathloss_37885.py`

Implements the selected 3GPP TR 37.885 urban-grid path-loss expressions for:

- LOS;
- NLOSv;
- NLOS.

Each equation includes:

- source section/table identifier;
- input validity domain;
- unit test values;
- explicit carrier and distance units.

### 10.2 `shadowing.py`

Class: `SpatialShadowingProcess`

Maintains spatially correlated shadowing keyed by link and trace. It updates from
vehicle displacement rather than independent packet time alone.

The API receives an explicit random stream and returns both the current value and
state token needed for deterministic replay.

### 10.3 `fading.py`

Interface:

```python
class FadingModel(Protocol):
    def sample(
        self,
        *,
        propagation_state: RFPropagationState,
        relative_speed_mps: float,
        carrier_hz: float,
        delta_s: float,
        rng: np.random.Generator,
    ) -> FadingSample:
        ...
```

The initial implementation will be selected from a documented vehicular fading
model. It must preserve temporal correlation at 100-ms packet epochs.

### 10.4 `mode2_features.py`

Builds the features used by the offline collision/BLER surrogate:

- CBR;
- neighbor count;
- distance;
- propagation state;
- transport-block/MCS identifier;
- resource-pool load;
- optional relative speed.

The outcome model may use hidden propagation state; the policy observation does
not receive it directly.

### 10.5 `mode2_surrogate.py`

Class: `Mode2Surrogate`

Loads a versioned calibration artifact:

```text
artifacts/calibration/rf/mode2-v1/
├── model.*
├── feature_schema.json
├── train_cases.parquet
├── validation_cases.parquet
├── metrics.json
├── source_config/
└── manifest.json
```

Public API:

```python
def predict_collision_probability(
    self, features: Mode2Features
) -> ProbabilityEstimate: ...
```

The estimate includes probability, calibration-bin ID, and out-of-domain flag.
Out-of-domain inputs raise or use an explicit conservative fallback; they are
never silently extrapolated.

### 10.6 `bler.py`

Supports:

- calibrated transport-block BLER curves; and
- optional documented RF finite-blocklength approximation.

The chosen method is specified in configuration. VLC does not import this file.

### 10.7 `model.py`

Class: `NRV2XChannel`

Inputs:

```python
@dataclass(frozen=True)
class RFChannelRequest:
    packet: PacketRequest
    geometry: GeometryTruth
    cbr: float
    neighbor_count: int
    previous_state: RFMemoryState
    random_tape: RFPacketRandomness
```

Output:

```python
@dataclass(frozen=True)
class RFChannelResult:
    propagation_state: RFPropagationState
    pathloss_db: float
    shadowing_db: float
    fading_gain_linear: float
    sinr_db: float
    collision_probability: float
    decoding_failure_probability: float
    total_failure_probability: float
    success: bool
    arrival_time_s: float | None
    failure_cause: FailureCause
    next_memory: RFMemoryState
```

The model computes hidden truth and outcome. The observation module later
constructs delayed/noisy measurements.

---

## 11. RF calibration tools

Path: `tools/fiveg_lena/`

This folder contains:

- external simulator version manifest;
- scenario templates;
- parameter-design generator;
- runner wrapper;
- raw-output parser;
- calibration dataset builder;
- held-out split definition.

Python module:

`src/grail_v/channels/rf/calibration.py`

Responsibilities:

- validate raw 5G-LENA output schema;
- aggregate packet collision and BLER statistics;
- fit candidate surrogates;
- compare calibration error, Brier score, log loss, and rare-bin error;
- choose a model without reading final evaluation traces;
- export the immutable calibration artifact.

Candidate surrogates should begin simple:

1. multidimensional calibrated lookup/interpolation;
2. monotonic generalized additive/logistic model;
3. gradient-boosted model only if it materially improves held-out calibration.

The most predictive model is not automatically selected if it is poorly
calibrated or uninterpretable outside support.

---

## 12. V-VLC channel module

Path: `src/grail_v/channels/vlc/`

### 12.1 `headlamp_pattern.py`

Class: `HeadlampPattern`

Loads measured or empirically tabulated radiant intensity versus horizontal and
vertical angle. It provides:

```python
def radiant_intensity_w_per_sr(
    self, horizontal_angle_rad: float, vertical_angle_rad: float
) -> float: ...
```

Interpolation, extrapolation, symmetry assumptions, units, and pattern source
are stored in the artifact manifest.

A Lambertian pattern may exist only as an explicitly named comparison model.

### 12.2 `receiver.py`

Defines detector properties:

- active area;
- responsivity;
- FOV;
- filter transmission;
- concentrator gain;
- height and orientation;
- thermal-noise parameters.

All values require source IDs in the resolved parameter table.

### 12.3 `optical_gain.py`

Calculates direct-path received optical power from:

- measured radiant intensity;
- distance;
- incidence geometry;
- detector effective area;
- filter/concentrator;
- occlusion.

The output is zero/direct-floor according to the configured blockage model.

### 12.4 `noise.py`

Calculates:

- signal-dependent shot noise;
- ambient-light shot noise;
- thermal noise;
- total electrical noise.

Night and high-ambient/day conditions are separate configurations, not a runtime
boolean with undocumented constants.

### 12.5 `ook.py`

Implements the selected OOK/IM-DD BER expression and transforms bit error into
packet failure using the configured independence/coding assumption.

If FEC is modeled, code rate and decoded-block error must be explicit. The
uncoded shortcut:

\[
P_{\mathrm{packet\ fail}}=1-(1-P_b)^{N_b}
\]

is allowed only when its bit-error assumptions are declared.

### 12.6 `timing.py`

Validates:

- information bits;
- framing/coding bits;
- gross bit rate;
- available airtime;
- modulation bandwidth;
- decoding budget.

It raises `PhysicalInfeasibilityError` before training if the complete block
cannot fit.

### 12.7 `model.py`

Class: `VehicleVLCChannel`

Request:

```python
@dataclass(frozen=True)
class VLCChannelRequest:
    packet: PacketRequest
    geometry: GeometryTruth
    ambient: AmbientCondition
    random_tape: VLCPacketRandomness
```

Result:

```python
@dataclass(frozen=True)
class VLCChannelResult:
    aligned: bool
    occluded: bool
    received_optical_power_w: float
    electrical_snr_linear: float
    bit_error_probability: float
    packet_failure_probability: float
    success: bool
    arrival_time_s: float | None
    failure_cause: FailureCause
```

### 12.8 `validation.py`

Produces:

- availability versus separation;
- received-power/PER versus angle and distance;
- blocker transition cases;
- comparison with measured-pattern or Veins-VLC reference outputs;
- residual-floor sensitivity.

No RL module is imported.

---

## 13. Prediction module

Path: `src/grail_v/prediction/`

### 13.1 `sensor_model.py`

Converts hidden nearby-vehicle truth into noisy delayed tracks:

- 20 Hz update;
- 50 ms baseline latency;
- 0.5 m position standard deviation;
- 0.2 m/s speed standard deviation;
- explicit missed-detection extension point.

The sensor receives only vehicles within configured perception range and FOV.

### 13.2 `tracks.py`

Defines:

```python
@dataclass(frozen=True)
class ObjectTrack:
    track_id: str
    measured_time_s: float
    available_time_s: float
    x_m: float
    y_m: float
    vx_mps: float
    vy_mps: float
    position_covariance: NDArray[np.float64]
    velocity_covariance: NDArray[np.float64]
    estimated_length_m: float
    estimated_width_m: float
```

Track IDs may be synthetic but must not reveal the exact hidden blocker identity
through a special label.

### 13.3 `constant_velocity.py`

Class: `MonteCarloBlockagePredictor`

Algorithm:

1. sample track states from their covariance;
2. propagate constant velocity to 200 ms;
3. construct predicted footprint rectangles;
4. test the predicted optical segment;
5. estimate probability of any blockage;
6. return Monte Carlo standard error and track age.

Output:

```python
@dataclass(frozen=True)
class BlockageForecast:
    horizon_s: float
    probability: float
    monte_carlo_std_error: float
    oldest_track_age_s: float
    track_count: int
```

The predictor never reads future SUMO snapshots.

---

## 14. Observation module

Path: `src/grail_v/observation/`

### 14.1 `link_memory.py`

Class: `LinkMeasurementMemory`

Stores for each link:

- most recent measured quality;
- measurement time;
- last ACK/delivery result;
- history deque;
- age at current packet.

Update rule:

- RF or DUP refreshes RF measurement;
- VLC or DUP refreshes VLC measurement;
- unused link ages;
- CBR may update independently.

### 14.2 `builder.py`

Class: `CausalObservationBuilder`

Constructs a fixed-order float32 vector:

```text
rf_quality, rf_age,
vlc_quality, vlc_age,
rf_history[8], vlc_history[8],
cbr, neighbor_count,
distance, bearing, relative_speed, heading_difference,
fov_margin,
forecast_probability, forecast_uncertainty, forecast_track_age,
previous_action_one_hot[3],
last_delivery,
consecutive_misses
```

Every feature has:

- semantic name;
- unit before normalization;
- normalization rule;
- missing-value encoding;
- availability/age rule;
- deployability classification.

### 14.3 `schema.py`

`ObservationSchema` stores ordered feature metadata and a schema hash. A trained
checkpoint refuses observations with a different schema hash.

### 14.4 `leakage_guard.py`

Rejects forbidden feature names and checks that observations do not contain:

- exact current/future success;
- exact hidden propagation state;
- exact blocker ID;
- exact future position;
- counterfactual unselected-link outcome;
- oracle-only fields.

Integration tests compare policy observations against a whitelist.

---

## 15. PHY and packet module

Path: `src/grail_v/phy/`

### 15.1 `packet.py`

Defines:

```python
@dataclass(frozen=True)
class PacketRequest:
    packet_id: str
    pair_id: str
    generation_time_s: float
    payload_bytes: int
    deadline_s: float

    @property
    def absolute_deadline_s(self) -> float: ...
```

### 15.2 `scheduler.py`

The headline scheduler assumes:

- periodic generation known in advance;
- policy action selected immediately before generation;
- reserved RF opportunity;
- VLC opportunity available simultaneously;
- no feedback HARQ;
- one committed attempt per selected leg.

This module validates timing but does not choose the action.

### 15.3 `duplication.py`

Implements:

- one packet ID with two copy IDs;
- OR-success;
- earliest successful arrival;
- both committed activation costs;
- useful/unnecessary/insufficient DUP classification.

### 15.4 `lifecycle.py`

Class: `PacketLifecycle`

Composes scheduler and channel results into `PacketOutcome`. It is the single
source of truth for deadline misses.

No baseline or agent calculates delivery independently.

---

## 16. Environment module

Path: `src/grail_v/env/`

### 16.1 `trace_store.py`

Provides indexed, read-only access to:

- vehicle snapshots;
- pair episodes;
- building/network metadata;
- density and split labels.

It verifies trace and schema hashes on open.

### 16.2 `episode_sampler.py`

Samples:

- density group;
- trace ID;
- pair episode;
- start time;
- 60-s window;
- sensor/randomness root.

Sampling probabilities are configuration-controlled and logged.

### 16.3 `random_tape.py`

Creates per-packet exogenous random draws for:

- RF fading innovation;
- RF collision;
- RF decoding;
- VLC noise/decoding;
- sensor noise;
- predictor Monte Carlo.

The tape is indexed by packet and link whether or not that link is selected.
Consequences:

- policies evaluated on the same trace see matched randomness;
- unused-link random draws do not shift later random streams;
- the oracle can inspect counterfactual outcomes without changing them;
- deployable policies never receive the tape.

### 16.4 `grail_v_env.py`

Class: `GrailVEnv(gymnasium.Env)`

Spaces:

```python
action_space = gymnasium.spaces.Discrete(3)
observation_space = gymnasium.spaces.Box(
    low=observation_schema.low,
    high=observation_schema.high,
    dtype=np.float32,
)
```

Reset:

1. sample episode;
2. initialize channel and sensor memory;
3. warm observation history without future leakage;
4. return first causal observation and metadata.

Step:

1. validate action;
2. generate current packet;
3. evaluate hidden geometry;
4. evaluate RF and VLC counterfactual results from fixed random tape;
5. select results according to action;
6. run packet lifecycle;
7. assign activation reward and conditional reliability cost;
8. update measurement memory only for selected links;
9. advance to next packet;
10. build next causal observation;
11. return Gymnasium tuple.

Return contract:

```python
observation, reward, terminated, truncated, info
```

where:

```python
info = {
    "cost": conditional_miss_probability,
    "binary_miss": int(packet_outcome.deadline_missed),
    "density_group": density,
    "packet_outcome": packet_outcome,
    "action_cost": activation_cost,
    "trace_id": trace_id,
    "pair_id": pair_id,
    "packet_index": packet_index,
}
```

`reward = -activation_cost`. Reliability is never folded into this reward for the
constrained agent.

### 16.5 `vector_env.py`

Wraps independent environments for batched rollout. Each worker receives a
disjoint seed namespace. Worker order cannot affect random outcomes.

### 16.6 `counterfactual.py`

Holds oracle-only views. Importing this module from observation or deployable
policy code is prohibited by architecture tests.

---

## 17. Baseline module

Path: `src/grail_v/baselines/`

### 17.1 `fixed.py`

- `RFOnlyPolicy`;
- `VLCOnlyPolicy`;
- `AlwaysDuplicatePolicy`.

### 17.2 `forecast_gate.py`

`ForecastAwareGatePolicy` uses:

- predicted success/quality;
- blockage probability;
- feature age;
- hysteresis;
- configurable DUP threshold.

Thresholds are tuned on validation traces only.

### 17.3 `contextual.py`

`ConstrainedContextualPolicy` receives the current observation but not history or
action-dependent memory. It tests whether PPO is solving a real sequential
problem.

### 17.4 `oracle.py`

`CounterfactualOraclePolicy` receives `CounterfactualPacketView` and selects the
least-cost successful action:

1. cheapest successful single link;
2. cheapest single link if both links succeed;
3. least-cost action if both links fail and a miss is unavoidable.

It is non-deployable and never shares its input schema with learned policies.
Under the headline OR-success semantics, its delivery reliability equals the
best attainable with Always-DUP while its clairvoyant activation cost is a
non-deployable lower bound.

### 17.5 `registry.py`

Maps stable policy names to constructors. Saved evaluation data use registry IDs,
not Python class names.

---

## 18. Agent module

Path: `src/grail_v/agents/`

The PPO implementation will be project-owned rather than forcing the constraint
logic through an unconstrained library API.

### 18.1 `networks.py`

Defines:

- `CategoricalActor`;
- `RewardValueCritic`;
- `CostValueCritic`.

Default architecture: two 64-unit tanh layers. Initialization and output
distributions are deterministic from explicit PyTorch generators.

### 18.2 `rollout.py`

`ConstrainedRolloutBuffer` stores:

- observation;
- action;
- action log probability;
- activation reward;
- conditional cost;
- binary miss for monitoring;
- reward value estimate;
- cost value estimate;
- terminated/truncated flags;
- density-group ID;
- trace/pair/packet identifiers.

Reward and cost advantages are computed separately.

### 18.3 `gae.py`

Implements and tests generalized advantage estimation for reward and cost. A
constant-cost synthetic fixture verifies sign and terminal handling.

### 18.4 `dual.py`

Class: `GroupDualController`

Maintains one nonnegative multiplier per density:

```python
lambda_k = max(
    0.0,
    lambda_k + learning_rate * (estimated_group_cost - active_budget),
)
```

It logs:

- current multiplier;
- group cost estimate;
- active curriculum budget;
- number of group samples;
- update norm.

A density with insufficient samples cannot receive a silent update.

### 18.5 `curriculum.py`

Implements:

- 10% of transitions at \(10^{-2}\);
- 20% at \(10^{-3}\);
- 70% at \(10^{-4}\).

Progress is transition-based, not wall-clock based.

### 18.6 `primal_dual_ppo.py`

Class: `PrimalDualPPO`

Policy objective uses a documented sign convention. One acceptable form is:

\[
A_t^{L} = A_t^{r} - \lambda_{k(t)} A_t^{c},
\]

followed by PPO’s clipped surrogate. The implementation document and tests must
match the exact code sign.

Training loop:

1. collect on-policy vectorized rollout;
2. compute reward/cost advantages;
3. update actor and critics;
4. estimate conditional group costs;
5. update per-density multipliers;
6. update curriculum;
7. evaluate on fixed validation traces periodically;
8. save a versioned checkpoint.

### 18.7 `fixed_penalty_ppo.py`

Uses the same actor/critics and rollout implementation but replaces the dual
controller with a fixed tuned penalty. This isolates the contribution of
constraint adaptation.

### 18.8 `checkpoint.py`

Checkpoint includes:

```text
actor state
reward critic state
cost critic state
optimizer states
dual multipliers
curriculum state
observation normalization
observation schema hash
resolved configuration hash
training trace IDs
code version
transition count
policy seed
```

A checkpoint cannot be loaded against a different observation or action schema.

---

## 19. Training orchestration

Path: `src/grail_v/agents/trainer.py`

Responsibilities:

- build configuration and artifact context;
- verify Gate-2/Gate-3 feasibility artifacts;
- construct train and validation environments;
- run five policy seeds;
- log metrics to JSON Lines and compact Parquet;
- profile environment and network throughput;
- select checkpoints reliability-first.

Checkpoint selection:

1. reject checkpoints violating any validation density;
2. among feasible checkpoints, minimize mean activation cost;
3. break ties using worst-density cost;
4. never inspect final test results.

Training may not start unless a feasibility manifest explicitly identifies a
nonempty oracle-feasible region.

---

## 20. Evaluation module

Path: `src/grail_v/evaluation/`

### 20.1 `runner.py`

Runs immutable checkpoints and baselines over matched evaluation scenarios.
Policies cannot update parameters or normalization.

### 20.2 `records.py`

Per-packet evaluation schema:

```text
run_id, policy_id, policy_seed, scenario_seed, density,
trace_id, pair_id, packet_index, generation_time_s,
action, delivered, deadline_missed, delivery_time_s,
activation_cost, rf_selected, vlc_selected,
rf_success, vlc_success,
rf_failure_probability, vlc_failure_probability,
joint_counterfactual_failure,
rf_propagation_state_hidden, vlc_occluded_hidden,
forecast_probability, distance_m, intersection_distance_m,
consecutive_misses, dup_class
```

Hidden columns are written only to evaluation artifacts, never observations.

Storage is partitioned Parquet with Zstandard compression:

```text
artifacts/evaluations/<evaluation_id>/packets/
  policy=<id>/density=<value>/part-*.parquet
```

Training does not save every packet unless diagnostic mode is enabled.

### 20.3 `online_metrics.py`

Accumulates exact counts during evaluation:

- generated packets;
- misses;
- action counts;
- cost sums;
- DUP classifications;
- marginal/joint failures;
- run-length histogram.

This enables summary verification without loading all packet rows.

### 20.4 `bootstrap.py`

Provides trajectory-aware inference:

- cluster bootstrap by independent trace/pair;
- optional moving-block bootstrap within long trajectories;
- one-sided 95% upper confidence bound;
- paired policy-difference interval on matched clusters.

The implementation stores bootstrap seed, resample count, cluster definition, and
block length.

Packet-level Clopper–Pearson may be reported as a diagnostic only and must be
labeled as ignoring temporal dependence.

### 20.5 `rare_event.py`

Checks:

- required raw sample count;
- observed misses;
- cluster count;
- effective-sample diagnostics;
- whether a \(10^{-4}\) or \(10^{-5}\) claim is permitted.

It raises `StatisticalPowerError` when a figure/table attempts a prohibited
five-nines claim.

Primary claim checks require at least \(10^6\) raw outcomes and at least 200
independent trajectory/pair clusters per policy-density cell, supplemented by
within-trajectory blocks where justified. Ultra-reliability checks require at
least \(10^7\) raw outcomes in each claimed selected condition.

### 20.6 `burst.py`

Computes:

- consecutive-miss runs;
- survival probability by run length;
- quantiles;
- equal-exposure comparisons.

Raw maximum run length is not compared across unequal packet counts.

### 20.7 `dependence.py`

Computes:

\[
p_{\mathrm{RF}},\quad p_{\mathrm{VLC}},\quad p_{\mathrm{joint}},
\quad p_{\mathrm{joint}}/(p_{\mathrm{RF}}p_{\mathrm{VLC}})
\]

with stratification by:

- density;
- distance bin;
- intersection-distance bin;
- RF propagation class;
- predicted-blockage bin;
- ambient condition.

### 20.8 `generalization.py`

Evaluates:

- 30 and 50 vehicles/lane-km interpolation;
- optional 70 vehicles/lane-km extrapolation;
- real-Manhattan map-and-count calibrated traces;
- sensor delay/noise sensitivity;
- heavy-vehicle share sensitivity.

No fine-tuning occurs in the zero-shot generalization result.

### 20.9 `inference_benchmark.py`

Measures:

- preprocessing;
- actor forward pass;
- action sampling/argmax;
- complete observation-to-action path;
- p50, p95, p99;
- named CPU, Python, PyTorch, thread, and precision settings.

---

## 21. Artifact module

Path: `src/grail_v/artifacts/`

### 21.1 `manifest.py`

Every generated artifact uses:

```python
class ArtifactManifest(BaseModel):
    schema_version: str
    artifact_type: str
    artifact_id: str
    created_at_utc: datetime
    config_hash: str
    code_version: str
    input_artifacts: list[ArtifactReference]
    random_seeds: dict[str, int]
    software_versions: dict[str, str]
    files: list[FileDigest]
    notes: list[str]
```

### 21.2 `store.py`

Creates artifacts atomically:

1. write into a unique temporary directory under the target artifact family;
2. validate required files;
3. hash contents;
4. write manifest last;
5. rename to final immutable ID.

Partial artifacts are not treated as valid.

### 21.3 `provenance.py`

Produces a provenance graph from paper result back to:

- figure script;
- evaluation artifact;
- checkpoint;
- calibration artifacts;
- trace artifacts;
- raw/source configurations.

---

## 22. Visualization module

Path: `src/grail_v/visualization/`

### 22.1 `style.py`

Contains one paper style:

- colorblind-safe policy colors;
- consistent action markers;
- log-scale miss-probability formatting;
- constraint-line formatting;
- IEEE-compatible fonts and sizes.

### 22.2 Figure modules

`system_figure.py`
: F1 shared-geometry system/scenario diagram data export. Final graphical layout
may be prepared separately, but all plotted geometry comes from a saved example.

`calibration_figure.py`
: F2 RF surrogate calibration, VLC validation, and failure dependence.

`frontier_figure.py`
: F3 reliability upper bound versus activation cost and density.

`interpretation_figure.py`
: F4 blockage forecast/action behavior, burst survival, and real-map robustness.

### 22.3 Tables

`parameter_table.py`
: emits source-linked Table I from resolved configuration and calibration
manifests.

`results_table.py`
: emits Table II from verified summary artifacts.

No value is manually typed into a final results table.

---

## 23. Command-line interface

Path: `src/grail_v/cli.py`

Proposed commands:

```text
grailv doctor
grailv config validate
grailv mobility build-synthetic
grailv mobility calibrate-density
grailv mobility generate-traces
grailv mobility import-nyc
grailv pairs extract
grailv rf parse-fiveg-lena
grailv rf fit-surrogate
grailv rf validate-surrogate
grailv vlc validate
grailv feasibility run
grailv train
grailv evaluate
grailv stats summarize
grailv figures build
grailv artifact verify
```

Every mutating/generating command:

- requires explicit configuration;
- prints the resolved configuration hash;
- refuses to overwrite an immutable artifact;
- returns nonzero on failed validation;
- writes structured logs.

Thin files in `scripts/` may call the CLI for batch jobs but contain no business
logic.

---

## 24. End-to-end execution flows

### 24.1 Synthetic mobility

```text
mobility config
  → build network
  → generate demand
  → calibrate flow to target density
  → run warm-up and trace
  → validate mobility
  → extract tagged pairs
  → immutable trace artifact
```

### 24.2 RF calibration

```text
5G-LENA design
  → external campaigns
  → raw parser
  → train/held-out split
  → fit calibrated surrogate
  → held-out validation
  → immutable RF calibration artifact
```

### 24.3 VLC validation

```text
measured headlamp pattern + detector parameters
  → optical model
  → timing feasibility
  → distance/angle/blockage sweeps
  → Veins-VLC/empirical cross-check
  → immutable VLC calibration artifact
```

### 24.4 Feasibility

```text
trace + RF calibration + VLC calibration + service profile
  → RF-only/VLC-only/Always-DUP/oracle
  → joint-failure characterization
  → feasible density/profile manifest
```

### 24.5 Training

```text
feasibility manifest
  → train/validation trace stores
  → vectorized causal environments
  → curriculum + primal-dual PPO
  → validation checkpoints
  → reliability-first checkpoint selection
```

### 24.6 Evaluation

```text
frozen policies + test traces + matched random tapes
  → packet outcomes
  → online summaries
  → cluster/block bootstrap
  → claim eligibility checks
  → immutable evaluation artifact
```

### 24.7 Paper

```text
verified evaluation artifacts
  → four figure scripts + two table scripts
  → source-linked output
  → paper bundle manifest
```

---

## 25. Test plan

### 25.1 Unit tests

Core/config:

- dBm/watt conversions;
- angle wrapping;
- deterministic child seeds;
- canonical config hash;
- invalid service/config rejection.

Geometry:

- rotated rectangle corners;
- segment touching edge/corner;
- blocker in front/behind pair;
- blocker too short to intersect optical height;
- building takes precedence over NLOSv;
- FOV exactly inside/outside boundary.

RF:

- reference path-loss points;
- correlated shadowing reproducibility;
- surrogate in-domain/out-of-domain behavior;
- total failure probability composition.

VLC:

- measured-pattern interpolation;
- inverse-square trend in controlled geometry;
- zero direct power under complete blockage;
- ambient noise increases failure probability;
- packet-fit calculation.

PHY:

- deadline equality boundary;
- DUP OR-success;
- first-arrival selection;
- both legs charged under DUP;
- useful/unnecessary/insufficient DUP.

Observation:

- unselected-link age increments;
- selected-link update;
- eight-sample history order;
- exact hidden flags absent;
- schema hash changes with feature order.

Agent:

- GAE terminal cases;
- dual-update sign;
- multiplier projection at zero;
- separate density multipliers;
- curriculum transition fractions.

### 25.2 Property tests

- rigid translation/rotation preserves range and intersection decisions;
- swapping independent RNG execution order does not change packet tape;
- DUP delivery is never worse than both committed legs under identical outcomes;
- increasing blocker height cannot restore direct optical visibility;
- increasing deadline cannot turn a timely delivery into a miss;
- evaluation summaries equal raw record reductions.

### 25.3 Integration tests

- tiny SUMO network → trace → pair extraction;
- trace → geometry → channel → packet outcome;
- environment reset/step for all actions;
- two policies on one random tape receive matched hidden outcomes;
- one small PPO update without NaN;
- checkpoint save/load reproduces deterministic actions;
- evaluation → bootstrap → figure-data table.

### 25.4 Statistical tests

Use controlled synthetic processes with known:

- Bernoulli miss probability;
- clustered beta-binomial miss probability;
- geometric run-length distribution;
- known paired policy difference.

Verify interval coverage approximately over repeated simulations and ensure the
cluster-aware interval widens when correlation is introduced.

### 25.5 Regression tests

Store compact fixtures for:

- one mobility trace;
- one building/vehicle geometry scene;
- one RF calibration table;
- one headlamp pattern;
- one 100-packet matched evaluation.

Regression fixtures are small, versioned, and never reused as final test data.

---

## 26. Logging and diagnostics

### Training logs

At each update:

- transition count;
- active reliability curriculum;
- per-density conditional cost;
- per-density binary miss diagnostic;
- per-density multiplier;
- activation cost;
- entropy;
- actor/critic losses;
- KL divergence;
- clip fraction;
- explained variance;
- environment steps/s.

### Evaluation logs

- trace/pair completion;
- raw packet and miss count;
- invalid/out-of-domain channel inputs;
- action counts;
- current artifact partition;
- failed claim-eligibility checks.

### Error policy

- NaN/Inf in an observation, probability, loss, or channel result is fatal.
- Probability clipping is logged with source and magnitude.
- Missing calibration support is fatal unless a declared conservative fallback is
  active.
- Teleportation or missing pair state invalidates the affected mobility trace.

---

## 27. Performance and scale

The design target is up to:

- \(10^7\) training packet transitions per policy seed;
- five training seeds;
- \(10^6\) primary evaluation packets per policy-density cell;
- selected \(10^7\)-packet ultra-reliability cells.

Performance rules:

- no live SUMO in PPO rollout;
- read trace partitions lazily;
- cache static building indices;
- vectorize channel evaluation where correctness permits;
- aggregate training logs rather than saving all transitions;
- stream evaluation records to Parquet;
- compute exact online summary counts;
- never require all evaluation packets in RAM.

Optimization follows profiling. Geometry correctness and statistical
reproducibility are not traded for premature speed.

---

## 28. Code quality rules

- Public functions/classes have type hints and concise docstrings.
- Dataclasses are immutable unless state mutation is the explicit abstraction.
- No mutable global experiment state.
- No business logic in CLI wrappers or notebooks.
- No hardcoded absolute paths.
- All externally derived numerical parameters carry source metadata.
- All file formats have schema versions.
- All policies implement one common protocol.
- Hidden and observable types have different classes.
- Oracles require a different input type from deployable policies.
- Random generators are explicit dependencies.
- A module does one research responsibility.
- Tests accompany every physical equation and packet invariant.

Ruff, mypy, unit tests, integration smoke tests, and artifact-schema validation
must pass before a milestone is considered complete.

---

## 29. Gate-0 publication and overlap artifact

Before runtime implementation, add:

```text
paper/U0_OVERLAP_MATRIX.md
```

It records for U0 versus GRAIL-V:

- service profile;
- geometry/mobility;
- channel equations;
- observation/predictor;
- actions;
- objective/constraint;
- algorithm;
- code;
- data;
- figures;
- results;
- text.

The implementation must not import or copy U0 code unless that reuse is
explicitly authorized, disclosed, and technically appropriate. Conceptual
similarities are recorded rather than described as “zero overlap.”

---

## 30. Implementation milestones

### M0 — Governance and scaffold

Deliver:

- U0 overlap matrix;
- `pyproject.toml`;
- package skeleton;
- default configuration models;
- CLI `doctor`;
- lint/type/test configuration.

Exit:

- supported Python environment works;
- SUMO is discovered;
- config hash is reproducible;
- no runtime feature has been implemented prematurely.

### M1 — Synthetic mobility

Deliver:

- rectangular grid builder;
- demand generator;
- density calibrator;
- trace writer/reader;
- tagged-pair extractor;
- mobility validation report.

Exit:

- 20/40/60 vehicles/lane-km achieved within 5%;
- no unexplained teleportation;
- trace artifact verifies.

### M2 — Shared geometry and observations

Deliver:

- pair geometry;
- vehicle/building occlusion;
- RF visibility state;
- sensor tracks;
- blockage forecast;
- causal observation schema;
- leakage tests.

Exit:

- all geometry/property tests pass;
- no hidden field enters deployable observation.

### M3 — RF channel

Deliver:

- TR 37.885 path loss;
- shadowing/fading;
- 5G-LENA parser and surrogate;
- held-out calibration report.

Exit:

- surrogate passes declared calibration thresholds;
- out-of-domain behavior tested.

### M4 — V-VLC channel

Deliver:

- measured headlamp pattern;
- receiver/noise/OOK models;
- blockage;
- timing feasibility;
- empirical/Veins validation report.

Exit:

- complete 300-byte block fits the headline deadline within the declared
  optical bandwidth;
- optical trends pass validation.

### M5 — Packet environment and feasibility

Deliver:

- packet lifecycle;
- random tape;
- Gymnasium environment;
- fixed policies;
- oracle;
- feasibility and joint-failure report.

Exit:

- nonempty oracle-feasible \(10^{-4}\) region;
- all action semantics and matching tests pass.

### M6 — Strong baselines

Deliver:

- forecast gate;
- contextual policy;
- fixed-penalty PPO;
- validation-only tuning.

Exit:

- matched baseline result artifact;
- strongest nonlearned rival identified.

### M7 — Primal-dual PPO

Deliver:

- networks;
- rollout/GAE;
- group multipliers;
- curriculum;
- checkpoints;
- inference benchmark.

Exit:

- medium-density validation converges;
- dual sign and group constraints verified;
- p99 inference gate evaluated.

### M8 — Full evaluation

Deliver:

- five-seed training;
- primary and selected ultra-reliability evaluations;
- bootstrap and burst analysis;
- generalization and real-map test.

Exit:

- claim-eligibility checks pass or limitations are recorded.

### M9 — Publication bundle

Deliver:

- four figures;
- two tables;
- parameter/source export;
- artifact provenance graph;
- paper result manifest.

Exit:

- every result is reproducible from an immutable evaluation artifact.

---

## 31. First implementation task after this document

The first code change will implement M0, in this exact order:

1. create `paper/U0_OVERLAP_MATRIX.md`;
2. create `pyproject.toml` for Python 3.11/3.12;
3. create the `src/grail_v/` package skeleton;
4. implement core enums, units, errors, and deterministic randomness;
5. implement Pydantic configuration models and headline YAML;
6. implement `grailv doctor`;
7. add pytest/Ruff/mypy configuration and initial tests.

SUMO mobility code begins only after M0 passes.

---

## 32. Definition of implementation completeness

The conference implementation is complete when:

- all modules in the required repository tree exist;
- every physical and statistical gate has a machine-readable manifest;
- RF/VLC/DUP actions share one packet lifecycle;
- deployable policies see only the documented causal observation;
- per-density constrained training is reproducible across five seeds;
- primary evaluation has at least \(10^6\) raw outcomes per required cell;
- any five-nines claim has at least \(10^7\) outcomes and a qualifying
  correlation-aware upper bound;
- all paper figures and tables are generated from saved artifacts;
- U0 overlap/disclosure is complete;
- tests, lint, typing, artifact verification, and reproducibility smoke run pass.

Until those conditions hold, the code may be useful for development but is not
the publication implementation.
