import os
from setuptools import find_packages
from setuptools import setup

with open(os.path.join("evcharge_status", "VERSION")) as file:
    version = file.read().strip()

with open("README.rst") as file:
    long_description = file.read()

with open("requirements.txt") as file:
    requirements = [r for r in file.readlines() if r.strip()]

setup(
    name="evcharge-status",
    description="Output status of one or more EVCharge points to Slack. Or something.",
    long_description=long_description,
    version=version,
    author="Richard Mitchell",
    url="https://github.com/mitchellrj/evcharge-online-status",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "evcharge-status=evcharge_status.cli:status",
            "evcharge-status-update-to-slack=evcharge_status.slack:status"
        ]
    },
    extras_require={
        "DynamoDB": ["boto3"]
    }
)