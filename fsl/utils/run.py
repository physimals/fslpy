#!/usr/bin/env python
#
# run.py - Functions for running shell commands
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides some functions for running shell commands.

.. autosummary::
   :nosignatures:

   run
   runfsl
   wait
   dryrun
"""


import               sys
import               logging
import               threading
import               contextlib
import               collections
import subprocess as sp
import os.path    as op

import               six

from   fsl.utils.platform import platform as fslplatform
import fsl.utils.fslsub                   as fslsub
import fsl.utils.tempdir                  as tempdir


log = logging.getLogger(__name__)


DRY_RUN = False
"""If ``True``, the :func:`run` function will only log commands, but will not
execute them.
"""


class FSLNotPresent(Exception):
    """Error raised by the :func:`runfsl` function when ``$FSLDIR`` cannot
    be found.
    """
    pass


@contextlib.contextmanager
def dryrun(*args):
    """Context manager which causes all calls to :func:`run` to be logged but
    not executed. See the :data:`DRY_RUN` flag.

    The returned standard output will be equal to ``' '.join(args)``.
    """
    global DRY_RUN

    oldval  = DRY_RUN
    DRY_RUN = True

    try:
        yield
    finally:
        DRY_RUN = oldval


def _prepareArgs(args):
    """Used by the :func:`run` function. Ensures that the given arguments is a
    list of strings.
    """

    if len(args) == 1:

        # Argument was a command string
        if isinstance(args[0], six.string_types):
            args = args[0].split()

        # Argument was an unpacked sequence
        else:
            args = args[0]

    return list(args)


def run(*args, **kwargs):
    """Call a command and return its output. You can pass the command and
    arguments as a single string, or as a regular or unpacked sequence.

    The command can be run on a cluster by using the ``submit`` keyword
    argument.

    An exception is raised if the command returns a non-zero exit code, unless
    the ``ret`` option is set to ``True``.

    :arg submit: Must be passed as a keyword argument. Defaults to ``None``.
                 Accepted values are ``True`` or a
                 If ``True``, the command is submitted as a cluster job via
                 the :func:`.fslsub.submit` function.  May also be a
                 dictionary containing arguments to that function.

    :arg err:    Must be passed as a keyword argument. Defaults to
                 ``False``. If ``True``, standard error is captured and
                 returned. Ignored if ``submit`` is specified.

    :arg tee:    Must be passed as a keyword argument. Defaults to ``False``.
                 If ``True``, the command's standard output and error streams
                 are forward to the streams for this process, in addition to
                 being captured and returned. Ignored if ``submit`` is
                 specified.

    :arg ret:    Must be passed as a keyword argument. Defaults to ``False``.
                 If ``True``, and the command's return code is non-0, an
                 exception is not raised.  Ignored if ``submit`` is specified.

    :returns:    If ``submit`` is provided, the cluster job ID is returned.
                 Otherwise if ``err is False and ret is False`` (the default)
                 a string containing the command's standard output.  is
                 returned. Or, if ``err is True`` and/or ``ret is True``, a
                 tuple containing the standard output, standard error (if
                 ``err``), and return code (if ``ret``).
    """

    # Creates a thread which forwards the given
    # input stream to one or more output streams.
    # Used when tee is True - we have to read
    # the process stdout/err on separate threads
    # to avoid deadlocks.
    def forward(in_, *outs):

        # not all file-likes have a mode attribute -
        # if not present, assume a string stream
        omodes = [getattr(o, 'mode', 'w') for o in outs]

        def realForward():
            for line in in_:
                for i, o in enumerate(outs):
                    if 'b' in omodes[i]: o.write(line)
                    else:                o.write(line.decode('utf-8'))

        t = threading.Thread(target=realForward)
        t.daemon = True
        t.start()
        return t

    err    = kwargs.get('err',    False)
    ret    = kwargs.get('ret',    False)
    tee    = kwargs.get('tee',    False)
    submit = kwargs.get('submit', None)
    args   = _prepareArgs(args)

    if not bool(submit):
        submit = None

    if submit is not None:
        err = False
        ret = False
        tee = False

        if submit is True:
            submit = dict()

    if submit is not None and not isinstance(submit, collections.Mapping):
        raise ValueError('submit must be a mapping containing '
                         'options for fsl.utils.fslsub.submit')

    if DRY_RUN: log.debug('dryrun: {}'.format(' '.join(args)))
    else:       log.debug('run: {}'   .format(' '.join(args)))

    # dry run - just echo back the command
    if DRY_RUN:
        stderr = ''
        if submit is None:
            stdout = ' '.join(args)
        else:
            stdout = '[submit] ' + ' '.join(args)

        results = [stdout]
        if err: results.append(stderr)
        if ret: results.append(0)

        if len(results) == 1: return results[0]
        else:                 return tuple(results)

    # submit - delegate to fslsub
    if submit is not None:
        return fslsub.submit(' '.join(args), **submit)

    # Start the command, directing its
    # stdout/stderr to temporary files
    # and, if tee is True, to sys.stdout
    # stderr.
    proc = sp.Popen(args, stdout=sp.PIPE, stderr=sp.PIPE)
    with tempdir.tempdir(changeto=False) as td:

        stdoutf = op.join(td, 'stdout')
        stderrf = op.join(td, 'stderr')

        with open(stdoutf, 'wb') as stdout, \
             open(stderrf, 'wb') as stderr:  # noqa

            if tee:
                stdoutt = forward(proc.stdout, stdout, sys.stdout)
                stderrt = forward(proc.stderr, stderr, sys.stderr)
            else:
                stdoutt = forward(proc.stdout, stdout)
                stderrt = forward(proc.stderr, stderr)

            # Wait until the forwarding threads
            # have finished cleanly, and the
            # command has terminated.
            stdoutt.join()
            stderrt.join()
            proc.communicate()

        # Read in the command's stdout/stderr
        with open(stdoutf, 'rb') as f: stdout = f.read()
        with open(stderrf, 'rb') as f: stderr = f.read()

    retcode = proc.returncode
    stdout  = stdout.decode('utf-8')
    stderr  = stderr.decode('utf-8')

    if not ret and (retcode != 0):
        raise RuntimeError('{} returned non-zero exit code: {}'.format(
            args[0], retcode))

    results = [stdout]

    if err: results.append(stderr)
    if ret: results.append(retcode)

    if len(results) == 1: return results[0]
    else:                 return tuple(results)


def runfsl(*args, **kwargs):
    """Call a FSL command and return its output. This function simply prepends
    ``$FSLDIR/bin/`` to the command before passing it to :func:`run`.
    """

    if fslplatform.fsldir is None:
        raise FSLNotPresent('$FSLDIR is not set - FSL cannot be found!')

    args    = _prepareArgs(args)
    args[0] = op.join(fslplatform.fsldir, 'bin', args[0])

    return run(*args, **kwargs)


def wait(job_ids):
    """Proxy for :func:`.fslsub.wait`. """
    return fslsub.wait(job_ids)
