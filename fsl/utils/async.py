#!/usr/bin/env python
#
# async.py - Run a function in a separate thread.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module provides functions and classes for running tasks
asynchronously, either in an idle loop, or on a separate thread.


.. note:: The *idle* functions in this module are intended to be run from
          within a ``wx`` application. However, they will still work without
          ``wx``, albeit with slightly modified behaviour.


Idle tasks
----------

.. autosummary::
   :nosignatures:

   idle
   inIdle


The :func:`idle` function is a simple way to run a task on an ``wx``
``EVT_IDLE`` event handler. This effectively performs the same job as the
:func:`run` function, but is more suitable for short tasks which do not
warrant running in a separate thread.


Thread tasks
------------

.. autosummary::
   :nosignatures:

   run
   wait
   TaskThread


The :func:`run` function simply runs a task in a separate thread.  This
doesn't seem like a worthy task to have a function of its own, but the
:func:`run` function additionally provides the ability to schedule another
function to run on the ``wx.MainLoop`` when the original function has
completed.  This therefore gives us a simple way to run a computationally
intensitve task off the main GUI thread (preventing the GUI from locking up),
and to perform some clean up/refresh afterwards.


The :func:`wait` function is given one or more ``Thread`` instances, and a
task to run. It waits until all the threads have finished, and then runs
the task (via :func:`idle`).


The :class:`TaskThread` class is a simple thread which runs a queue of tasks.


.. todo:: You could possibly use ``props.callqueue`` to drive the idle loop.
"""


import time
import logging
import threading
import collections

try:    import queue
except: import Queue as queue


log = logging.getLogger(__name__)


def _haveWX():
    """Returns ``True`` if wqe are running within a ``wx`` application,
    ``False`` otherwise.
    """
    
    try:
        import wx
        return wx.GetApp() is not None
    
    except ImportError:
        return False


def run(task, onFinish=None, onError=None, name=None):
    """Run the given ``task`` in a separate thread.

    :arg task:     The function to run. Must accept no arguments.

    :arg onFinish: An optional function to schedule (on the ``wx.MainLoop``,
                   via :func:`idle`) once the ``task`` has finished.

    :arg onError:  An optional function to be called (on the ``wx.MainLoop``,
                   via :func:`idle`) if the ``task`` raises an error. Passed
                   the ``Exception`` that was raised.

    :arg name:     An optional name to use for this task in log statements.

    :returns: A reference to the ``Thread`` that was created.

    .. note:: If a ``wx`` application is not running, the ``task`` and
              ``onFinish`` functions will simply be called directly, and
              the return value will be ``None``.
    """

    if name is None:
        name = getattr(task, '__name__', '<unknown>')

    haveWX = _haveWX()

    # Calls the onFinish or onError handler
    def callback(cb, *args, **kwargs):
        
        if cb is None:
            return
        
        if haveWX: idle(cb, *args, **kwargs)
        else:      cb(      *args, **kwargs)

    # Runs the task, and calls 
    # callback functions as needed.
    def wrapper():

        try:
            task()
            log.debug('Task "{}" finished'.format(name))
            callback(onFinish) 
            
        except Exception as e:
            
            log.warn('Task "{}" crashed'.format(name), exc_info=True)
            callback(onError, e)

    # If WX, run on a thread
    if haveWX:
        
        log.debug('Running task "{}" on thread'.format(name))

        thread = threading.Thread(target=wrapper)
        thread.start()
        return thread

    # Otherwise run directly
    else:
        log.debug('Running task "{}" directly'.format(name))
        wrapper()
        return None


_idleRegistered = False
"""Boolean flag indicating whether the :func:`wxIdleLoop` function has
been registered as a ``wx.EVT_IDLE`` event handler. Checked and set
in the :func:`idle` function.
"""


_idleQueue = queue.Queue()
"""A ``Queue`` of functions which are to be run on the ``wx.EVT_IDLE``
loop.
"""


_idleQueueSet = set()
"""A ``set`` containing the names of all named tasks which are
currently queued on the idle loop (see the ``name`` parameter to the
:func:`idle` function).
"""


class IdleTask(object):
    """Container object used by the :func:`idle` and :func:`_wxIdleLoop`
    functions.
    """

    def __init__(self,
                 name,
                 task,
                 schedtime,
                 after,
                 timeout,
                 args,
                 kwargs):
        self.name      = name
        self.task      = task
        self.schedtime = schedtime
        self.after     = after
        self.timeout   = timeout
        self.args      = args
        self.kwargs    = kwargs



def _wxIdleLoop(ev):
    """Function which is called on ``wx.EVT_IDLE`` events. If there
    is a function on the :attr:`_idleQueue`, it is popped and called.
    """

    global _idleQueue
    global _idleQueueSet
        
    ev.Skip()

    try:
        task = _idleQueue.get_nowait()
    except queue.Empty:
        return

    now     = time.time()
    elapsed = now - task.schedtime

    # Has enouggh time elapsed
    # since the task was scheduled?
    # If not, re-queue the task.
    if elapsed < task.after:
        log.debug('Re-queueing function ({}) on wx idle '
                  'loop'.format(getattr(task.task, '__name__', '<unknown>'))) 
        _idleQueue.put_nowait(task)

    # Has the task timed out?
    elif task.timeout == 0 or (elapsed < task.timeout):
        
        log.debug('Running function ({}) on wx idle '
                  'loop'.format(getattr(task.task, '__name__', '<unknown>')))
        task.task(*task.args, **task.kwargs)

        if task.name is not None:
            _idleQueueSet.discard(task.name)

    if _idleQueue.qsize() > 0:
        ev.RequestMore()


def inIdle(taskName):
    """Returns ``True`` if a task with the given name is queued on the
    idle loop (or is currently running), ``False`` otherwise. 
    """
    global _idleQueueSet
    return taskName in _idleQueueSet
    

def idle(task, *args, **kwargs):
    """Run the given task on a ``wx.EVT_IDLE`` event.

    :arg task:    The task to run.

    :arg name:    Optional. If provided, must be provided as a keyword
                  argument. Specifies a name that can be used to query
                  the state of this task via the :func:`inIdle` function.

    :arg after:   Optional. If provided, must be provided as a keyword
                  argument. A time, in seconds, which specifies the amount
                  of time to wait before running this task after it has
                  been scheduled.

    :arg timeout: Optional. If provided, must be provided as a keyword
                  argument. Specifies a time out, in seconds. If this
                  amount of time passes before the function gets
                  scheduled to be called on the idle loop, the function
                  is not called, and is dropped from the queue.

    
    All other arguments are passed through to the task function.

    
    If a ``wx.App`` is not running, the ``after`` and ``timeout`` arguments
    are ignored, and the task is called directly.


    .. note:: If the ``after`` argument is used, there is no guarantee that
              the task will be executed in the order that it is scheduled.
              This is because, if the required time has not elapsed when
              the task is poppsed from the queue, it will be re-queued.
    """

    global _idleRegistered
    global _idleQueue
    global _idleQueueSet

    schedtime = time.time()
    timeout   = kwargs.pop('timeout', 0)
    after     = kwargs.pop('after',   0)
    name      = kwargs.pop('name',    None)

    if _haveWX():
        import wx

        if not _idleRegistered:
            wx.GetApp().Bind(wx.EVT_IDLE, _wxIdleLoop)
            _idleRegistered = True

        log.debug('Scheduling idle task ({}) on wx idle '
                  'loop'.format(getattr(task, '__name__', '<unknown>')))

        idleTask = IdleTask(name,
                            task,
                            schedtime,
                            after,
                            timeout,
                            args,
                            kwargs)

        _idleQueue.put_nowait(idleTask)

        if name is not None:
            _idleQueueSet.add(name)
            
    else:
        log.debug('Running idle task directly') 
        task(*args, **kwargs)


def wait(threads, task, *args, **kwargs):
    """Creates and starts a new ``Thread`` which waits for all of the ``Thread``
    instances to finsih (by ``join``ing them), and then runs the given
    ``task`` via :func:`idle`.

    If a ``wx.App`` is not running, this function ``join``s the threads
    directly instead of creating a new ``Thread`` to do so.

    :arg threads: A ``Thread``, or a sequence of ``Thread`` instances to
                  join. Elements in the sequence may be ``None``.

    :arg task:    The task to run.

    All other arguments are passed to the ``task`` function.
    """

    if not isinstance(threads, collections.Sequence):
        threads = [threads]
    
    haveWX = _haveWX()

    def joinAll():
        log.debug('Wait thread joining on all targets')
        for t in threads:
            if t is not None:
                t.join()

        log.debug('Wait thread scheduling task on idle loop')
        idle(task, *args, **kwargs)

    if haveWX:
        thread = threading.Thread(target=joinAll)
        thread.start()
        return thread
    
    else:
        joinAll()
        return None


class Task(object):
    """Container object which encapsulates a task that is run by a
    :class:`TaskThread`.
    """
    def __init__(self, name, func, args, kwargs):
        self.name    = name
        self.func    = func
        self.args    = args
        self.kwargs  = kwargs
        self.enabled = True


class TaskThread(threading.Thread):
    """The ``TaskThread`` is a simple thread which runs tasks. Tasks may be
    enqueued and dequeued.

    .. note::
    """


    def __init__(self, *args, **kwargs):
        """Create a ``TaskThread`` """

        threading.Thread.__init__(self, *args, **kwargs)

        self.__q        = queue.Queue()
        self.__enqueued = {}
        self.__stop     = False

        log.debug('New task thread')


    def enqueue(self, name, func, *args, **kwargs):
        """Enqueue a task to be executed.

        :arg name: Task name. Does not necessarily have to be a string,
                    but must be hashable.
        :arg func: The task function.

        All other arguments will be passed through to the task when it is
        executed.
        """

        log.debug('Enqueueing task: {} [{}]'.format(
            name, getattr(func, '__name__', '<unknown>')))

        t = Task(name, func, args, kwargs)
        self.__enqueued[name] = t
        self.__q.put(t)


    def isQueued(self, name):
        """Returns ``True`` if a task with the given name is enqueued,
        ``False`` otherwise.
        """
        return name  in self.__enqueued


    def dequeue(self, name):
        """Dequeues a previously enqueued task.

        :arg name: The task to dequeue.
        """
        task = self.__enqueued.get(name, None)
        if task is not None:

            log.debug('Dequeueing task: {}'.format(name))
            task.enabled = False


    def stop(self):
        """Stop the ``TaskThread`` after any currently running task has
        completed.
        """
        log.debug('Stopping task thread')
        self.__stop = True


    def run(self):
        """Run the ``TaskThread``. """

        while True:

            try:
                task = self.__q.get(timeout=1)

            except queue.Empty:
                continue

            finally:
                if self.__stop:
                    break

            self.__enqueued.pop(task.name, None)

            if not task.enabled:
                continue

            log.debug('Running task: {} [{}]'.format(
                task.name,
                getattr(task.func, '__name__', '<unknown>')))

            task.func(*task.args, **task.kwargs)

            log.debug('Task completed: {} [{}]'.format(
                task.name,
                getattr(task.func, '__name__', '<unknown>')))

        self.__q        = None
        self.__enqueued = None
        log.debug('Task thread finished')
