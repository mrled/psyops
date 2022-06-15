import setuptools


long_description = """
# progfiguration

A PROGrammatic conFIGURATION for psyopsOS.
I'm tired of writing YAML when what I want to write is Python.
This is the base package I use to write Python to configure psyopsOS nodes.
"""


setuptools.setup(
    name="progfiguration",
    version="0.0.0",
    author="Micah R Ledbetter",
    author_email="me@micahrl.com",
    description="Programmatically configure psyopsOS nodes",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mrled/psyops/tree/master/psyopsOS",
    packages=["progfiguration"],
    python_requires=">=3.8",
    include_package_data=True,
    install_requires=["invoke"],
    entry_points={
        "console_scripts": ["psyopsOS-progfiguration=progfiguration.cli:main"],
    },
)
