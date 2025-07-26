from setuptools import setup, find_packages

# Read requirements from requirements.txt
def read_requirements():
    with open('requirements.txt', 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name='plexrr',
    version='0.1.0',
    description='CLI tool to manage movies across Plex and Radarr',
    author='Your Name',
    author_email='your.email@example.com',
    packages=find_packages(),
    include_package_data=True,
    install_requires=read_requirements(),
    entry_points={
        'console_scripts': [
            'plexrr=plexrr.cli:cli',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
            'feedparser>=6.0.0',
    ],
    python_requires='>=3.9',
)