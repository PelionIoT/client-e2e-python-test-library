"""
Pelion e2e python test library
"""
from setuptools import setup

PACKAGE_NAME = "pelion_test_lib"
PACKAGE_LIST = ['pelion_test_lib',
                'pelion_test_lib.cloud',
                'pelion_test_lib.cloud.libraries',
                'pelion_test_lib.cloud.libraries.rest_api',
                'pelion_test_lib.fixtures',
                'pelion_test_lib.helpers',
                'pelion_test_lib.tools']

# Read packet requirements from requirements.txt to have those only in one place. This has some downsides but as long
# as we use this only internally and in the simple way it does not matter.
with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(name=PACKAGE_NAME,
      use_scm_version={'root': '.'},
      setup_requires=['setuptools_scm==3.2.0'],
      description="Pelion E2E Python Test Library",
      author="systest",
      author_email="iot-systestteam-testing@arm.com",
      url="git@github.com:ArmMbedCloud/pelion-e2e-python-test-library.git",
      license="proprietary",
      packages=PACKAGE_LIST,
      install_requires=required)
