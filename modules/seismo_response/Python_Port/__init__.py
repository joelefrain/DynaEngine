"""
SeismoSoil Python - 1D Nonlinear Site Response Analysis

A pure Python port of SeismoSoil v1.3.4.2 (MATLAB version)
Enables nonlinear site response analysis without Fortran dependencies

Main modules:
- seismosoil_core: Core classes and constitutive models
- seismosoil_io: File I/O and analysis runners
- examples: Complete working examples

Quick start:
    from seismosoil_core import SoilLayer, VsProfile, MotionRecord, H2Model, NonlinearSiteResponse
    from seismosoil_io import AnalysisRunner, ResultsAnalyzer
    
    # Create profile
    layers = [SoilLayer(thickness=5, vs=250, damping_ratio=0.05, density=1800)]
    profile = VsProfile(layers=layers)
    
    # Create motion
    motion = MotionRecord(time=time_array, acceleration=accel_array)
    
    # Create model
    model = H2Model(gamma_ref=0.005)
    
    # Run analysis
    analysis = NonlinearSiteResponse(profile=profile, model=model)
    results = analysis.compute_response(motion)

For detailed documentation, see README.md
"""

__version__ = "0.1.0"
__author__ = "Python port of SeismoSoil (Asimaki et al., Caltech)"

from seismosoil_core import (
    SoilLayer,
    VsProfile,
    MotionRecord,
    ConstitutiveModel,
    H2Model,
    H4Model,
    HHModel,
    EPPModel,
    NonlinearSiteResponse,
    calculate_vs30,
    calculate_max_values,
)

from seismosoil_io import (
    SeismoSoilIO,
    AnalysisRunner,
    ResultsAnalyzer,
)

__all__ = [
    'SoilLayer',
    'VsProfile',
    'MotionRecord',
    'ConstitutiveModel',
    'H2Model',
    'H4Model',
    'HHModel',
    'EPPModel',
    'NonlinearSiteResponse',
    'calculate_vs30',
    'calculate_max_values',
    'SeismoSoilIO',
    'AnalysisRunner',
    'ResultsAnalyzer',
]
