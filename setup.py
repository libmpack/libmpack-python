import glob
import os
import os.path
import shutil
import sys

from setuptools import setup
from setuptools.extension import Extension
from setuptools.command.build_ext import build_ext
from setuptools.command.install import install
from setuptools.command.sdist import sdist
from distutils.command.clean import clean


VERSION = '1.1.0'
MPACK_VERSION = '1.0.5'
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


extension_src = 'mpack/_mpack.c'
extensions = [Extension("mpack._mpack", [extension_src])]


def _download_mpack():
    import tarfile
    import shutil
    if sys.version_info >= (3, 0):
        import urllib.request as urllib
    else:
        import urllib
    url = 'https://github.com/libmpack/libmpack/archive/{}.tar.gz'.format(
            MPACK_VERSION)
    print('downloading libmpack...')
    file_tmp = urllib.urlretrieve(url, filename=None)[0]
    print('extracting libmpack...')
    tar = tarfile.open(file_tmp)
    tar.extractall('mpack')
    directory = glob.glob('mpack/libmpack*')[0]
    shutil.move(directory, 'mpack/mpack-src')

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
    from Cython.Build import cythonize
    kwargs = {
        'gdb_debug': True,
        'language_level': 3
    }
    if os.getenv('NDEBUG', False):
        kwargs['gdb_debug'] = False
    cythonize([Extension('mpack._mpack', ['mpack/_mpack.pyx'])], **kwargs)

def _should_download_mpack():
    return not os.path.exists('mpack/mpack-src/src/mpack.c')

def _should_autopxd():
    return not os.path.exists('mpack/_cmpack.pxd')

def _should_cythonize():
    try:
        import Cython.Build
    except ImportError:
        return False
    return (not os.path.exists(extension_src)
            or os.environ.get('CYTHONIZE_MPACK', None) is not None)

def with_hooks(cmdclass):
    class Sub(cmdclass):
        def run(self):
            if _should_cythonize():
                _cythonize()
            cmdclass.run(self)

    return Sub


def datafiles():
    if _should_download_mpack():
        _download_mpack()
    if _should_autopxd():
        _autopxd()
    if _should_cythonize():
        _cythonize()
    dataexts  = (".c", ".h", ".pxd", ".pyx")
    datafiles = []
    getext = lambda filename: os.path.splitext(filename)[1]
    for datadir in ['mpack']:
        datafiles.extend([(
            root, [os.path.join(root, f)
            for f in files if getext(f) in dataexts])
            for root, dirs, files in os.walk(datadir)])
    return datafiles


if __name__ == '__main__':
    setup(
        name="mpack",
        version=VERSION,
        description="Python binding to libmpack",
        packages=['mpack'],
        ext_modules=extensions,
        data_files=datafiles(),
        install_requires=['future'],
        url=REPO,
        download_url='{0}/archive/{1}.tar.gz'.format(REPO, VERSION),
        license='MIT',
        cmdclass={
            'build_ext': with_hooks(build_ext),
            'clean': Clean,
        },
        author="Thiago de Arruda",
        author_email="tpadilha84@gmail.com"
    )
