import sublime
import sublime_plugin

import os
try:
    #ST3
    from .libs import gm_manager 
except Exception as e:
    #ST2
    import gm_manager


manager=gm_manager.GmManager()

def plugin_loaded():
    manager.refresh_serial_port()
    
class SublimeGmListener(sublime_plugin.EventListener):
    def on_selection_modified(self, view):
        mp=manager.panel
        if mp and mp.is_gm_panel(view):
            mp.on_selection_modified()
    
    def on_text_command(self, view, command_name, args):
        mp=manager.panel
        if not mp:
            return None

        if command_name == 'gm_open':
            return 'gm_open', {}

        if mp.is_gm_panel(view):
            if command_name == 'left_delete':
                # stop backspace on ST3 w/o breaking brackets
                if not mp.allow_deletion():
                    return 'gm_pass', {}

            if command_name == 'delete_word' and not args.get('forward'):
                # stop ctrl+backspace on ST3 w/o breaking brackets
                if not mp.allow_deletion():
                    return 'gm_pass', {}
        return None

class GmResetDevCommand(sublime_plugin.WindowCommand):
    def run(self):
        manager.serial_monitor.reset_dev()

    def is_enabled(self):
        state=False
        if manager.serial_monitor.is_ready:
            state = True
        return state

class GmFirmwareUpdateCommand(sublime_plugin.WindowCommand):
    def run(self):
        manager.firmware_update()

    def is_enabled(self):
        state=False
        if manager.serial_monitor.is_ready:
            state = True
        return state

class GmOpenCommand(sublime_plugin.WindowCommand):
    def run(self,encoding='utf8',syntax=None):
        manager.open(self.window,syntax)

class GmPanelShowCommand(sublime_plugin.WindowCommand):
    def run(self,encoding='utf8',syntax=None):
        manager.panel_show(self.window,syntax)

class GmRefreshCommand(sublime_plugin.WindowCommand):
    def run(self):
        manager.refresh_serial_port()

class GmUploadCommand(sublime_plugin.WindowCommand):
    def run(self, files=[]):
        manager.panel.show()
        if len(files)>0:
            for f in files:
                manager.serial_monitor.upload(f)
        else:
            f=self.window.active_view().file_name()
            if f.endswith('.lua') or f.endswith('.elua'):
                manager.serial_monitor.upload(f)
                    
    def is_enabled(self):
        state=False
        if manager.serial_monitor.is_ready:
            state = True
        return state

    def is_visible(self):
        state=False
        f=self.window.active_view().file_name()
        if f and (f.endswith('.lua') or f.endswith('.elua')):
            state=True
        return state

class GmSerialPortCommand(sublime_plugin.WindowCommand):
    def run(self, serial_port):
        manager.serial_monitor.port=serial_port
            
    def is_checked(self, serial_port):
        state=False
        if serial_port == manager.serial_monitor.port:
            state=True
        return state

class GmBaudrateCommand(sublime_plugin.WindowCommand):
    def run(self, baudrate):
        manager.serial_monitor.baudrate=baudrate
            
    def is_checked(self, baudrate):
        state=False
        if baudrate == manager.serial_monitor.baudrate:
            state=True
        return state

class GmPassCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        pass

class GmInsertTextCommand(sublime_plugin.TextCommand):
    def run(self, edit, pos, text):
        self.view.set_read_only(False)  # make sure view is writable
        self.view.insert(edit, int(pos), text)

class GmViewPreviousCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        mp = manager.panel
        if mp:
            mp.previous_command(edit)

class GmViewNextCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        mp = manager.panel
        if mp:
            mp.next_command(edit)

class GmClearCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        mp = manager.panel
        if mp:
            mp.clear(edit)

class GmEnterCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if manager.panel:
            manager.panel.enter()


