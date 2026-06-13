# sdk/setup.py
from setuptools import find_packages, setup

setup(
    name="tracex-sdk",
    version="1.0.0",
    description="TRACE-X SDK — Flight recorder instrumentation for AI agents",
    long_description=open("README.md").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="TRACE-X Team",
    python_requires=">=3.10",
    packages=find_packages(exclude=["tests*"]),
    install_requires=[
        "httpx>=0.28.0",
        "google-cloud-pubsub>=2.27.0",
        "pydantic>=2.9.0",
        "structlog>=24.4.0",
        "tenacity>=9.0.0",
    ],
    extras_require={
        "dev": ["pytest", "pytest-asyncio"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
