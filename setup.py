import glob
import os
import os.path
import shutil

from setuptools import setup
from setuptools.extension import Extension
from setuptools.command.build_ext import build_ext
from setuptools.command.install import install
from setuptools.command.sdist import sdist
from distutils.command.clean import clean


VERSION = '0.0.1'
REPO = 'https://github.com/libmpack/libmpack-python'


class Clean(clean):
    def run(self):
        files = []
        with open('.gitignore') as gitignore:
            for pattern in gitignore:
                for f in glob.glob(pattern.strip()):
                    if os.path.isdir(f): shutil.rmtree(f)
                    elif os.path.isfile(f): os.unlink(f)
        clean.run(self)


def with_hooks(cmdclass):
    def _autopxd():
        from autopxd import translate
        # due to some current limitations in autopxd, we must change
        # directories to ensure the pxd is generated with the correct includes
        cwd = os.getcwd()
        os.chdir('mpack')
        mpack_src = 'mpack-src/src/mpack.c'
        with open(mpack_src) as f:
            hdr = f.read()
        with open('_cmpack.pxd', 'w') as f:
            f.write(translate(hdr, mpack_src))
        os.chdir(cwd)

    def _cythonize():
        try:
            from Cython.Build import cythonize
        except ImportError:
            return
        kwargs = {
            'gdb_debug': True,
            'language_level': 3
        }
        if os.getenv('NDEBUG', False):
            kwargs['gdb_debug'] = False
        cythonize([Extension('mpack._mpack', ['mpack/_mpack.pyx'])], **kwargs)

    class Sub(cmdclass):
        def build_extensions(self):
            _autopxd()
            _cythonize()
            cmdclass.build_extensions(self)

        def run(self):
            cmdclass.run(self)
    return Sub


extensions = [Extension("mpack._mpack", ['mpack/_mpack.c'])]


setup(
    name="mpack",
    version=VERSION,
    description="Python binding to libmpack",
    packages=['mpack'],
    ext_modules=extensions,
    install_requires=['future'],
    url=REPO,
    download_url='{0}/archive/{1}.tar.gz'.format(REPO, VERSION),
    license='MIT',
    cmdclass={
        'build_ext': with_hooks(build_ext),
        'install': with_hooks(install),
        'sdist': with_hooks(sdist),
        'clean': Clean,
    },
    author="Thiago de Arruda",
    author_email="tpadilha84@gmail.com"
)
