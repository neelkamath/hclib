import setuptools

setuptools.setup(
    name="hclib",
    version="1.0.4",
    description="A library to connect to https://hack.chat/",
    long_description=open("./README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/neelkamath/hclib",
    author="Neel Kamath",
    author_email="neelkamath@icloud.com",
    py_modules=["hclib"],
    license="MIT",
    keywords="hack.chat library",
    install_requires=["websocket-client>=0.44,<1"],
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)
