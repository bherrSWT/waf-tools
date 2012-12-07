#!/usr/bin/env python
# encoding: utf-8

import os, sys, re
from waflib.TaskGen import feature, after_method
from waflib import Utils, Task, Logs, Options
testlock = Utils.threading.Lock()


class BasicRunner(Task.Task):
    """
    Execute a unit test
    """
    color = 'PINK'
    after = ['vnum', 'inst']
    run_type = ''
    vars = []

    def runnable_status(self):
        """
        Always execute the task if `waf --options=run_always` was used
        """

        ret = super(BasicRunner, self).runnable_status()
        if ret == Task.SKIP_ME:
            if self.generator.bld.has_tool_option('run_always'):
                return Task.RUN_ME
        return ret

    def setup_path(self):
        """
        Adds some common paths to the environment in which
        the executable will run.
        """
        try:
            fu = getattr(self.generator.bld, 'all_test_paths')
        except AttributeError:
            fu = os.environ.copy()
            self.generator.bld.all_test_paths = fu

            lst = []
            for g in self.generator.bld.groups:
                for tg in g:
                    if getattr(tg, 'link_task', None):
                        lst.append(tg.link_task.outputs[0].parent.abspath())

            def add_path(dct, path, var):
                dct[var] = os.pathsep.join(Utils.to_list(path) + [os.environ.get(var, '')])

            if Utils.is_win32:
                add_path(fu, lst, 'PATH')
            elif Utils.unversioned_sys_platform() == 'darwin':
                add_path(fu, lst, 'DYLD_LIBRARY_PATH')
                add_path(fu, lst, 'LD_LIBRARY_PATH')
            else:
                add_path(fu, lst, 'LD_LIBRARY_PATH')

                return fu

    def format_command(self, executable):
        """
        We allow the user to 'modify' the command to be executed.
        E.g. by specifying --option=runcmd='valgrind %s' this will
        replace %s with the executable name and thus run the executable
        under valgrind
        """
        bld = self.generator.bld
        
        if bld.has_tool_option('runcmd'):
            testcmd = bld.get_tool_option('runcmd') 
            cmd = testcmd % executable
        else:
            cmd  = executable

        return cmd

    def run(self):
        """
        Basic runner - simply spins a subprocess to run the executable.
        The execution is always successful, but the
        results are stored on ``self.generator.bld.runner_results`` for
        post processing.
        """
        fu = self.setup_path()
        cwd = self.inputs[0].parent.abspath()        
        cmd = self.format_command(self.inputs[0].abspath()).split(' ')

        Logs.debug("wr: running %r in %s" % (cmd, str(cwd)))

        proc = Utils.subprocess.Popen(
            cmd,
            cwd=cwd,
            env=fu,
            stderr=Utils.subprocess.PIPE,
            stdout=Utils.subprocess.PIPE)

        (stdout, stderr) = proc.communicate()

        result = (cmd, proc.returncode, stdout, stderr)
        self.save_result(result)

    def save_result(self, result):
        """
        Stores the result in the self.generator.bld.runner_results
        """
        testlock.acquire()
        try:
            bld = self.generator.bld
            Logs.debug("wr: %r", result)
            try:
                bld.runner_results.append(result)
            except AttributeError:
                bld.runner_results = [result]
        finally:
            testlock.release()
