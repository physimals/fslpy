#!/usr/bin/env python
#
# bitmap.py - The Bitmap class
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module contains the :class:`Bitmap` class, for loading bitmap image
files. Pillow is required to use the ``Bitmap`` class.
"""


import os.path      as op
import                 logging
import                 six

import numpy        as np

from . import image as fslimage


log = logging.getLogger(__name__)


BITMAP_EXTENSIONS = ['.bmp', '.png',  '.jpg', '.jpeg',
                     '.tif', '.tiff', '.gif', '.rgba']
"""File extensions we understand. """


BITMAP_DESCRIPTIONS = [
    'Bitmap',
    'Portable Network Graphics',
    'JPEG',
    'JPEG',
    'TIFF',
    'TIFF',
    'Graphics Interchange Format',
    'Raw RGBA']
"""A description for each :attr:`BITMAP_EXTENSION`. """


class Bitmap(object):
    """The ``Bitmap`` class can be used to load a bitmap image. The
    :meth:`asImage` method will convert the bitmap into an :class:`.Image`
    instance.
    """

    def __init__(self, bmp):
        """Create a ``Bitmap``.

        :arg bmp: File name of an image, or a ``numpy`` array containing image
                  data.
        """

        try:
            import PIL.Image as Image
        except ImportError:
            raise RuntimeError('Install Pillow to use the Bitmap class')

        if isinstance(bmp, six.string_types):
            source = bmp
            data   = np.array(Image.open(source))

        elif isinstance(bmp, np.ndarray):
            source = 'array'
            data   = np.copy(bmp)

        else:
            raise ValueError('unknown bitmap: {}'.format(bmp))

        # Make the array (w, h, c)
        data = np.fliplr(data.transpose((1, 0, 2)))
        data = np.array(data, dtype=np.uint8, order='C')
        w, h = data.shape[:2]

        self.__data       = data
        self.__dataSource = source
        self.__name       = op.basename(source)


    def __hash__(self):
        """Returns a number which uniquely idenfities this ``Bitmap`` instance
        (the result of ``id(self)``).
        """
        return id(self)


    def __str__(self):
        """Return a string representation of this ``Bitmap`` instance."""
        return '{}({}, {})'.format(self.__class__.__name__,
                                   self.dataSource,
                                   self.shape)


    def __repr__(self):
        """See the :meth:`__str__` method. """
        return self.__str__()


    @property
    def name(self):
        """Returns the name of this ``Bitmap``, typically the base name of the
        file.
        """
        return self.__name


    @property
    def dataSource(self):
        """Returns the bitmap data source - typically the file name. """
        return self.__dataSource


    @property
    def data(self):
        """Convenience method which returns the bitmap data as a ``(w, h, c)``
        array, where ``c`` is either 3 or 4.
        """
        return self.__data


    @property
    def shape(self):
        """Returns the bitmap shape - ``(width, height, nchannels)``. """
        return self.__data.shape


    def asImage(self):
        """Convert this ``Bitmap`` into an :class:`.Image` instance. """

        width, height, nchannels = self.shape

        if nchannels == 1:
            dtype = np.uint8


        elif nchannels == 3:
            dtype = np.dtype([('R', 'uint8'),
                              ('G', 'uint8'),
                              ('B', 'uint8')])

        elif nchannels == 4:
            dtype = np.dtype([('R', 'uint8'),
                              ('G', 'uint8'),
                              ('B', 'uint8'),
                              ('A', 'uint8')])

        else:
            raise ValueError('Cannot convert bitmap with {} '
                             'channels into nifti image'.format(nchannels))

        if nchannels == 1:
            data = self.data.reshape((width, height))

        else:
            data = np.zeros((width, height), dtype=dtype)
            for ci, ch in enumerate(dtype.names):
                data[ch] = self.data[..., ci]

        data = np.array(data, order='F', copy=False)

        return fslimage.Image(data, name=self.name)
