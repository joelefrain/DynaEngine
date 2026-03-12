# SeismoSoil Python - Quick Start Guide

## Installation

```bash
cd Python_Port/
pip install -r requirements.txt
```

## Basic Usage (5 minutes)

### 1. Create a Soil Profile

```python
from seismosoil_core import SoilLayer, VsProfile

layers = [
    SoilLayer(thickness=5.0, vs=250, damping_ratio=0.05, density=1800),
    SoilLayer(thickness=5.0, vs=300, damping_ratio=0.05, density=1850),
    SoilLayer(thickness=10.0, vs=400, damping_ratio=0.05, density=1900),
]
profile = VsProfile(layers=layers)
```

### 2. Create Ground Motion

```python
import numpy as np
from seismosoil_core import MotionRecord

# Create synthetic motion or load from file
dt = 0.01
t = np.arange(0, 10, dt)
accel = np.sin(2*np.pi*1*t) * np.exp(-t/5)  # Damped sinusoid

motion = MotionRecord(time=t, acceleration=accel, name="MyMotion")
```

### 3. Create Constitutive Model

```python
from seismosoil_core import H2Model, H4Model, HHModel, EPPModel

# Choose model
model = H2Model(gamma_ref=0.005, n=0.5, alpha=0.5)
# OR:
# model = H4Model(gamma_ref=0.005, n=0.5, alpha_g=0.5, alpha_x=0.5)
# model = HHModel(gamma_ref=0.005, n=0.5, alpha_g=0.5, alpha_x=0.5, beta=0.3)
# model = EPPModel(gamma_yield=0.01)
```

### 4. Run Analysis

```python
from seismosoil_core import NonlinearSiteResponse

analysis = NonlinearSiteResponse(
    profile=profile,
    model=model,
    dt=motion.dt,
    n_substeps=10
)

results = analysis.compute_response(motion, boundary_type='rigid')
```

### 5. Post-Process Results

```python
from seismosoil_io import ResultsAnalyzer

analyzer = ResultsAnalyzer()

# Get transfer function
freq, tf = analyzer.transfer_function(results)
print(f"Dominant frequency: {analyzer.resonant_frequency(freq, tf):.2f} Hz")

# Print summary
analyzer.print_summary(results, profile)

# Access results
print(f"Max surface acceleration: {results['acceleration'][:, -1].max():.3f} m/s²")
print(f"Max strain: {results['strain'].max():.2e}")
print(f"Max stress: {results['stress'].max():.0f} Pa")
```

## File I/O (MATLAB-compatible)

### Read Profile from File

```python
from seismosoil_io import SeismoSoilIO

# Format: thickness(m) vs(m/s) damping density(kg/m3) material_id
profile = SeismoSoilIO.read_vs_profile('profile.txt')
```

### Read Motion from File

```python
# Format: time(s) acceleration(m/s2)
motion = SeismoSoilIO.read_motion('motion.txt')
```

### Save Results

```python
SeismoSoilIO.write_results(results, 'output_directory', 'motion_name')
```

## Using AnalysisRunner (High-level API)

```python
from seismosoil_io import AnalysisRunner

# Create runner
runner = AnalysisRunner(
    profile_file='profile.txt',
    model_type='H2',
    model_params={'gamma_ref': 0.005, 'n': 0.5, 'alpha': 0.5}
)

# Run single analysis
results = runner.run_analysis('motion.txt', output_dir='results/')

# Or run batch analysis
motion_files = ['motion1.txt', 'motion2.txt', 'motion3.txt']
all_results = runner.batch_analysis(motion_files, 'results/')
```

## Available Models

| Model | Type | Use Case |
|-------|------|----------|
| **H2** | Masing - MKZ | Symmetric loading/unloading |
| **H4** | Non-Masing - MKZ | Asymmetric behavior (G/X separate) |
| **HH** | Hybrid Hyperbolic | Better damping characterization |
| **EPP** | Elastic-Perfectly-Plastic | Simple/conservative analysis |

## Complete Examples

Run all examples:
```bash
python examples.py
```

Individual examples:
```python
# Example 1: Basic H2 analysis
from examples import example_1_basic_h2_analysis
results, profile = example_1_basic_h2_analysis()

# Example 2: Compare models
from examples import example_2_model_comparison
results, profile = example_2_model_comparison()

# Example 3: Parameter study
from examples import example_3_parameter_study
results, profile = example_3_parameter_study()

# Example 4: File I/O demo
from examples import example_4_file_io
profile, motion, results = example_4_file_io()
```

## Plotting Results

```python
import matplotlib.pyplot as plt

# Time series
plt.figure()
plt.plot(results['time'], results['acceleration'][:, 0], label='Input')
plt.plot(results['time'], results['acceleration'][:, -1], label='Output')
plt.xlabel('Time (s)')
plt.ylabel('Acceleration (m/s²)')
plt.legend()
plt.grid(True)
plt.show()

# Depth profiles
fig, axes = plt.subplots(1, 2)
max_vals = analyzer.calculate_max_values(results)

axes[0].plot(max_vals['max_strain']*100, results['depth_layers'])
axes[0].set_xlabel('Max Strain (%)')
axes[0].set_ylabel('Depth (m)')
axes[0].invert_yaxis()

axes[1].plot(max_vals['max_stress']/1000, results['depth_layers'])
axes[1].set_xlabel('Max Stress (kPa)')
axes[1].set_ylabel('Depth (m)')
axes[1].invert_yaxis()

plt.show()
```

## Tips & Tricks

1. **Improve accuracy**: Increase `n_substeps` (default=5, try 10-20)
2. **Faster computation**: Decrease `n_substeps` or profile resolution
3. **Debug analysis**: Print intermediate results with `analyzer.print_summary()`
4. **Compare models**: Use same profile/motion for fair comparison
5. **Batch processing**: Use `AnalysisRunner.batch_analysis()` for multiple motions

## Differences from MATLAB Version

| Feature | MATLAB | Python |
|---------|--------|--------|
| Fortran engine | Required | Not needed |
| Code visibility | .p files (compiled) | Full source |
| Speed | Faster (Fortran) | Slightly slower (pure Python) |
| Portability | Requires MATLAB | Standard Python |
| Flexibility | Limited to GUI | Fully scriptable |

## Documentation

- `README.md` - Complete architecture documentation
- `examples.py` - 4 detailed working examples
- Docstrings in code for function/class details

## Troubleshooting

**Issue**: ImportError on modules  
**Solution**: `pip install -r requirements.txt` in Python_Port directory

**Issue**: Analysis runs too slow  
**Solution**: Reduce `n_substeps` or use shorter time histories

**Issue**: Results don't match MATLAB  
**Solution**: Check profile/motion inputs, model parameters, integration scheme

## Contact & Citation

Original MATLAB version:  
Asimaki et al., Caltech - https://asimaki.caltech.edu/SeismoSoil

Python port: 2025

## License

See LICENSE in parent directory
