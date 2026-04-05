from setuptools import setup, find_packages

setup(
    name='yeeko_xlsx_export',
    version='2.0.4',
    description='Declarative Django model → Excel export framework',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='vash Lucian',
    author_email='lucian@yeeko.org',
    url='https://github.com/yeeko-org/xlsx_export',
    packages=find_packages(),
    install_requires=[
        "django>=4.1",
        "djangorestframework>=3.14",
        "XlsxWriter>=3.0.2",
    ],
    python_requires='>=3.9',
)
