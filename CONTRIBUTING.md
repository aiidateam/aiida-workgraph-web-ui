
### Running tests

For running the tests you require only need start rabbitmq in the background.
The profile that is created during the tests will automatically check its configuration.
To run all tests use

```console
pytest
```

To run only backend tests run

```console
pytest -m backend
```

To run only frontend tests
```console
pytest -m frontend
```

To not run these tests you can use the markers in the following way

```console
pytest -m "not backend and not frontend"
```

#### Setting path for python executable for pythonjob tests

By default the pythonjob will use the executable `python3` to execute the calcjobs in the tests.
If you want to specify to use a different python path (e.g. from your environment manager).
To change the default python path you can set the environment variable
```console
PYTEST_PYTHONJOB_PYTHON_EXEC_PATH=/home/user/pyvenv/workgraph-dev/bin/python pytest tests/test_python.py
```

#### Running frontend tests in headed mode

To debug the frontend tests you often want to see what happens in the tests.
By default they are run in headless mode, so no browser is shown.
To run the frontend tests in headed mode for you have to set an environment variable like this
```console
PYTEST_PLAYWRIGHT_HEADLESS=no pytest -m frontend
```

For the frontend tests we start a web server at port `8000`, please free this address for before running the frontend tests.

### Development on the GUI

For the development on the GUI we use the [REACT](https://react.dev) library
which can automatically refresh on changes of the JS files. To start the backend
server please run

```console
python aiida_workgraph_web_ui/backend/main.py
```

then start the frontend server with
```console
npm --prefix aiida_workgraph_web_ui/frontend start
```

The frontend server will refresh

#### Tools for writing frontend tests

To determine the right commands for invoking DOM elements playwright offers a
tool that outputs commands while navigating through the GUI. It requires a
webserver to be running so it can be started with
```console
workgraph web start
playwright codegen
```

#### Troubleshooting

##### Tests are not updating after changes in code

You might want to clean your cache

```console
npm --prefix aiida_workgraph_web_ui/frontend cache clean
```

and also clear your browsers cache or try to start new private window.


### Building the docs

We use sphinx to build the docs. You need the requirements in the extra
`.[docs]` dependency and the `docs/requirements.txt`. We have a `docs/Makefile`
that runs sphinx-build to build the docs.

```console
pip install .[docs]
pip install -r docs/requirements.txt
make -C docs html
<YOUR-BROWSER> docs/build/html/index.html
```

#### Creating a new sphinx source file with executable code

We use sphinx-gallery to integrate executable code into the doc. For that we
need create a sphinx-gallery script (an extended python file that can be parsed by
sphinx-gallery to generate an `.rst` with more structure) instead of a `.rst`
file. One can create a sphinx-gallery script from a jupyter notebook using the
[script](https://gist.github.com/chsasank/7218ca16f8d022e02a9c0deb94a310fe).
To execute the script you might need to install pandoc
```console
pip install pypandoc pypandoc_binary
```
We put the converted sphinx-gallery script file `<SCRIPT>.py` to the gallery
source folder `docs/gallery/<FOLDER>/autogen`. where `<FOLDER>` is the folder
you want to attach the generated file in the sphinx source ( `docs/source`).
Then in the `docs/source/<FOLDER>/index.rst` add `autogen/<SCRIPT>` to the
toctree. The sphinx-gallery script will be converted to a `.rst` file during
building time.
