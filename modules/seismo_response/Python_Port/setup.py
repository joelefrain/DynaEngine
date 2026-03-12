"""
setup.py - Compilar extensiones Cython
"""

from setuptools import setup, Extension
import numpy as np

# Define Cython extensions
extensions = [
    Extension(
        "seismosoil_kernel_cython",
        sources=["seismosoil_kernel_cython.pyx"],
        include_dirs=[np.get_include()],
        extra_compile_args=['-O3', '-march=native'],  # Optimización máxima
        language='c'
    )
]

setup(
    name="SeismoSoil",
    ext_modules=extensions,
)
