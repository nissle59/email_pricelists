# Source - https://stackoverflow.com/a
# Posted by Y4RD13
# Retrieved 2025-11-08, License - CC BY-SA 4.0

from setuptools import setup

class CONFIG:
    VERSION = 'v1.0.0'
    platform = 'darwin-x86_64'
    executable_stub = '/Library/Frameworks/Python.framework/Versions/3.12/lib/libpython3.12.dylib' # this is important, check where is your Python framework and get the `dylib`
    APP_NAME = f'PriceList_{VERSION}_{platform}'
    APP = ['main.py']
    DATA_FILES = [
        'emailparser.db',
        ('assets', ['assets/icon.ico']),
        # this modules are automatically added if you use __init__.py in your folder
        # ('modules', ['modules/scraper_module.py']),
        # ('modules', ['modules/gui_module.py']),
    ]

    OPTIONS = {
        'argv_emulation': False,
        'iconfile': 'assets/icon.ico',
        'plist': {
            'CFBundleName': APP_NAME,
            'CFBundleDisplayName': APP_NAME,
            'CFBundleGetInfoString': APP_NAME,
            'CFBundleVersion': VERSION,
            'CFBundleShortVersionString': VERSION,
            'PyRuntimeLocations': [
                executable_stub,
                # also the executable can look like this:
                #'@executable_path/../Frameworks/libpython3.4m.dylib',
            ]
        }
    }

def main():
    setup(
        name=CONFIG.APP_NAME,
        app=CONFIG.APP,
        data_files=CONFIG.DATA_FILES,
        options={'py2app': CONFIG.OPTIONS},
        setup_requires=['py2app'],
        maintainer='foo bar',
        author_email='foo@domain.com',
    )

if __name__ == '__main__':
    main()
