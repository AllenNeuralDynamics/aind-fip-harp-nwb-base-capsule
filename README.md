# Fiber NWB Packaging Capsule


FiberPhotometry Capsule which appends to an NWB subject file. Adds FiberPhotometry information if present.

[Capsule link here](https://codeocean.allenneuraldynamics.org/capsule/3393406/tree)

NOTE: This capsule is in development with the file format standards for Fiber Photometry defined here: [Fiber Photometry Acquisition File Standards](https://github.com/AllenNeuralDynamics/aind-file-standards/blob/main/docs/file_formats/fip.md).

### Input and Output
The input to this capsule is the raw data (see file formats link for more details). The capsule will then output a NWB file with the raw fiber data added to the NWB. Under the `acquisition` field in the NWB, the following should be present as of now (note: this is subject to change depending on feedback for naming, what to store, etc.):
### 📑 TimeSeries
- `G_0`
- `G_1`
- `G_2`
- `G_3`
- `Iso_0`
- `Iso_1`
- `Iso_2`
- `Iso_3`
- `R_0`
- `R_1`
- `R_2`
- `R_3`

Where G (green), R (red), and Iso are the respective channels with 4-fiber connections 0-indexed. Each timeseries module has timestamps (on the HARP clock) and the data. See the file standards link above for more details on raw data acquisition.
