
# python compile.py build_ext --inplace
from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

ext_modules = [
    # modules
    Extension("unitlab.core", ["src/unitlab/core.py"]),
]

for e in ext_modules:
    e.cython_directives = {'language_level': "3"}

setup(
    name = 'Unitlab Inc. (Python SDK)',
    cmdclass = {'build_ext': build_ext},
    ext_modules = ext_modules
)