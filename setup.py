from distutils.core import setup

setup(
    name="kubecert",
    version="1.0",
    package_dir={'': 'src'},
    packages=['kubecert'],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'kubecert = kubecert:main'
        ]
    },
)
