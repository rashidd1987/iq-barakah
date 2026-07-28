from setuptools import setup, find_packages

setup(
    name="iq-barakah-bot",
    version="20260615",
    packages=find_packages(include=["bot_v2", "bot_v2.*"]),
)
