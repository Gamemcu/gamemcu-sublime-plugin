import sublime

class HistoryMatchList(object):
    def __init__(self, command_prefix, commands):
        self._command_prefix = command_prefix
        self._commands = commands
        self._cur = len(commands)  # no '-1' on purpose

    def current_command(self):
        if not self._commands:
            return ""
        return self._commands[self._cur]

    def prev_command(self):
        self._cur = max(0, self._cur - 1)
        return self.current_command()

    def next_command(self):
        self._cur = min(len(self._commands) - 1, self._cur + 1)
        return self.current_command()


class History(object):
    def __init__(self):
        self._last = None

    def push(self, command):
        cmd = command.rstrip()
        if not cmd or cmd == self._last:
            return
        self.append(cmd)
        self._last = cmd

    def append(self, cmd):
        raise NotImplementedError()

    def match(self, command_prefix):
        raise NotImplementedError()


class MemHistory(History):
    def __init__(self):
        super(MemHistory, self).__init__()
        self._stack = []

    def append(self, cmd):
        self._stack.append(cmd)

    def match(self, command_prefix):
        matching_commands = []
        for cmd in self._stack:
            if cmd.startswith(command_prefix):
                matching_commands.append(cmd)
        return HistoryMatchList(command_prefix, matching_commands)

class GmPanel(object):
    def __init__(self,window,consumer,syntax):
        self._window=window
        self._consumer=consumer
        self._name='gm_panel'
        panel=window.create_output_panel(self._name)
        if syntax:
            panel.set_syntax_file(syntax)
        view = window.active_view()
        color_scheme = view.settings().get('color_scheme', '')
        if not color_scheme:
            color_scheme = 'Packages/Color Scheme - Default/Monokai.tmTheme'
        panel.settings().set('color_scheme', color_scheme)
        panel.settings().set("history_arrows", True)
        panel.settings().set('gm', True)
        panel.set_name(self._name)
        panel.set_scratch(True)
        self._panel = panel
        self._output_end = panel.size()
        self._prompt_size = 0
        self._history = MemHistory()
        self._history_match = None

    @property
    def name(self):
        return self._name

    def is_gm_panel(self,view):
        return self._panel==view
    
    def clear(self, edit):
        self.escape(edit)
        self._panel.erase(edit, self.output_region)
        self._output_end = self._panel.sel()[0].begin()

    def escape(self, edit):
        self._panel.set_read_only(False)
        self._panel.erase(edit, self.input_region)
        self._panel.show(self.input_region)

    def previous_command(self, edit):
        self._panel.set_read_only(False)
        self.ensure_history_match()
        self.replace_current_input(edit, self._history_match.prev_command())
        self._panel.show(self.input_region)

    def next_command(self, edit):
        self._panel.set_read_only(False)
        self.ensure_history_match()
        self.replace_current_input(edit, self._history_match.next_command())
        self._panel.show(self.input_region)

    def replace_current_input(self, edit, cmd):
        if cmd:
            self._panel.replace(edit, self.input_region, cmd)
            self._panel.sel().clear()
            self._panel.sel().add(sublime.Region(self._panel.size()))

    def write(self,unistr):
        self._panel.run_command("gm_insert_text", {"pos": self._output_end - self._prompt_size, "text": unistr})
        self._output_end += len(unistr)
        self._panel.show(self.input_region)
    
    def show(self):
        panel_name = 'output.' + self._name
        self._window.run_command("show_panel", {"panel": panel_name})
        self._window.focus_view(self._panel)

    def push_history(self, command):
        self._history.push(command)
        self._history_match = None

    def ensure_history_match(self):
        user_input = self.user_input
        if self._history_match is not None:
            if user_input != self._history_match.current_command():
                # user did something! reset
                self._history_match = None
        if self._history_match is None:
            self._history_match = self._history.match(user_input)

    def on_selection_modified(self):
        self._panel.set_read_only(self.delta > 0)

    def adjust_end(self):
        self._output_end = self._panel.size()

    def enter(self):
        p = self._panel
        if p.sel()[0].begin() != p.size():
            p.sel().clear()
            p.sel().add(sublime.Region(p.size()))

        l = self._output_end    
        self.push_history(self.user_input)  # don't include cmd_postfix in history
        command = self.user_input
        p.run_command("insert", {"characters": '\n'})
        self.adjust_end()
        self._consumer(command)

    def allow_deletion(self):
        # returns true if all selections falls in user input
        # and can be safetly deleted
        output_end = self._output_end
        for sel in self._panel.sel():
            if sel.begin() == sel.end() and sel.begin() == output_end:
                # special case, when single selecion
                # is at the very beggining of prompt
                return False
            # i don' really know if end() is always after begin()
            if sel.begin() < output_end or sel.end() < output_end:
                return False
        return True

    @property
    def delta(self):
        """Return a repl_view and number of characters from current selection
        to then begging of user_input (otherwise known as _output_end)"""
        return self._output_end - self._panel.sel()[0].begin()

    @property
    def user_input(self):
        """Returns text entered by the user"""
        return self._panel.substr(self.input_region)

    @property
    def input_region(self):
        return sublime.Region(self._output_end, self._panel.size())

    @property
    def output_region(self):
        return sublime.Region(0, self._output_end - 2)