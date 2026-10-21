# Prime map source geometry

`PrimeFloorPlan.source_layers` keeps owned deep copies of the parsed `rooms`
and `borders` layers from the bundle used to construct that plan. It retains
GeoJSON components, interior rings, feature properties and the separate
`geometry` and `properties.simplifiedGeometry` variants. Source JSON values
and units are unchanged; this is not the original archive's byte encoding.

The existing projections remain in millimetres: `room_polygons` contains one
outline per room, while `borders` contains component exteriors. Existing card
attributes, geometry selection, rendered images and explicit `floor_plan`
paths are unchanged. An interior ring is an exclusion in an area, not evidence
that its boundary is a physical wall. Retaining the source does not infer
new walls or door closures; existing rendering behavior is untouched.

The snapshot is internal and is not added to HA state, diagnostics, logs or
storage. Its field is excluded from dataclass repr and equality. Missing
layers remain absent; present null/empty values are retained. Existing plan
constructors default to an independent empty snapshot. The frozen dataclass
does not recursively freeze nested JSON: consumers must treat it as read-only.
Input mutations cannot change the snapshot, or vice versa.

Only these two bundle layers are copied. Metadata-only geometry, topology
validation, renderer support and an expanded card contract are separate work.
An additional copy uses memory proportional to the retained layers. Future
consumers must select a geometry variant explicitly, associate it with the
correct map/version and track source changes independently of plan equality.
Do not serialize the whole plan for diagnostics: excluding a field from repr
is not a serialization or security boundary.
