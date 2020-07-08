import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pysplat",
    version="0.0.1",
    author="Alexandre Hajjar",
    author_email="alexandre.hajjar@gmail.com",
    description="A small wrapper around Splat!",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/lajarre/pysplat",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=["typing_extensions>=3.7.4"],
    python_requires=">=3.6",
)
