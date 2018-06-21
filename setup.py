import os.path
from distutils.core import setup

setup(
    name="kubecert",
    version="1.0",
    package_dir={'': 'src'},
    packages=['kubecert'],
    entry_points={
        'console_scripts': [
            'kubecert = kubecert:main'
        ]
    },
    install_requires= [
        'effect',
    ],
    data_files=[
        ('templates', list(map(
            lambda file: os.path.join('src', 'kubecert', 'configs', file),
            ['server-openssl.conf', 'client-openssl.conf']
        )))
    ],
    include_package_data=True,
)
