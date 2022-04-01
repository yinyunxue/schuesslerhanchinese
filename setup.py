from setuptools import setup
import json


with open("metadata.json", encoding="utf-8") as fp:
    metadata = json.load(fp)


setup(
    name='lexibank_schuessleroldchinese',
    description=metadata['title'],
    license=metadata.get('license', ''),
    url=metadata.get('url', ''),
    py_modules=['lexibank_schuessleroldchinese'],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'lexibank.dataset': [
            'schuessleroldchinese=lexibank_schuessleroldchinese:Dataset',
        ]
    },
    install_requires=[
        'pylexibank>=2.0',
    ],
    extras_require={
        'test': [
            'pytest-cldf',
        ],
    },
)
