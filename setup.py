import setuptools

setuptools.setup(
        name='genlisp',
        packages=['genlisp'],
        python_requires='>=3.7',
        install_requires=["attrs"],
        tests_require=['pytest']
        )
