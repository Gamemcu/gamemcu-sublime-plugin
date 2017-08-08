from __future__ import absolute_import, unicode_literals, print_function, division
import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)),'libs'))

import sublime

SUBLIMEGM_DIR = None
SUBLIMEGM_USER_DIR = None
VERSION_URL = None

def plugin_loaded():
    global SUBLIMEGM_DIR
    global SUBLIMEGM_USER_DIR
    SUBLIMEGM_DIR = os.path.join(sublime.packages_path(), 'gamemcu-sublime-plugin')
    SUBLIMEGM_USER_DIR = os.path.join(sublime.packages_path(), 'User', 'gamemcu-sublime-plugin')
    gm_settings = sublime.load_settings('gamemcu.sublime-settings')
    global VERSION_URL
    VERSION_URL = gm_settings.get('version_url')

def gm_dir():
    return SUBLIMEGM_DIR
    
def gm_user_dir():
    return SUBLIMEGM_USER_DIR

def gm_firmware_dir():
    path = os.path.join(SUBLIMEGM_USER_DIR, 'firmware')
    if not os.path.isdir(path):
        os.makedirs(path)
    return path

def gm_version_url():
    return VERSION_URL

__version__='1.0.0'