from setuptools import setup, find_packages

setup(
    name='plexrr',
    version='0.1.0',
    description='CLI tool to manage movies across Plex and Radarr',
    author='Your Name',
    author_email='your.email@example.com',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click>=8.0.0',
        'pyyaml>=6.0',
        'plexapi>=4.15.4',
        'arrapi>=1.4.2',
        'tabulate>=0.9.0',
        'python-dateutil>=2.8.2',
        'humanize>=4.6.0',
    ],
    entry_points={
        'console_scripts': [
            'plexrr=plexrr.cli:cli',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.9',
)
