import sublime
import sys
import os
from os import path

gm_package_dir = path.dirname(path.dirname(path.realpath(__file__)))
gm_package_name = path.basename(gm_package_dir)

def gm_dir():
    return path.join(sublime.packages_path(), gm_package_name)
    
def gm_user_dir():
    gm_user_dir = path.join(sublime.packages_path(), 'User', gm_package_name)
    if not path.isdir(gm_user_dir):
        os.makedirs(gm_user_dir)
    return gm_user_dir

def gm_firmware_dir():
    firmware_dir = path.join(gm_user_dir(), 'firmware')
    if not path.isdir(firmware_dir):
        os.makedirs(firmware_dir)
    return firmware_dir

def gm_version_url():
    gm_settings = sublime.load_settings('gamemcu.sublime-settings')
    return gm_settings.get('version_url')
