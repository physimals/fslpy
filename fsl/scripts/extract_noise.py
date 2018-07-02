#!/usr/bin/env python
#
# extract_noise.py - Extract ICA component time courses from a MELODIC
#                    directory.
#
# Author: Paul McCarthy <pauldmccarthy@gmail.com>
#
"""This module defines the ``extract_noise`` script, for extracting component
time series from a MELODIC ``.ica`` directory.
"""


from __future__ import print_function

import os.path as op
import            sys
import            argparse
import            warnings

import numpy   as np

# See atlasq.py for explanation
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=FutureWarning)

    import fsl.data.fixlabels       as fixlabels
    import fsl.data.melodicanalysis as melanalysis


DTYPE = np.float64


usage = """
Usage:
  extract_noise <.ica directory> [-o outfile] <fixfile>
  extract_noise <.ica directory> [-o outfile] <component> [<component> ...]
""".strip()


desc = 'Extract component time series from a MELODIC .ica directory'


helps = {
    'outfile' :
    'File to save time series to',

    'overwrite' :
    'Overwrite output file if it exists',

    'icadir' :
    '.ica directory to extract time series from.',

    'component' :
    'Component number or FIX/AROMA file specifying components to extract.',

    'confound' :
    'Extra files to append to output file.',
}


def parseArgs(args):
    """Parses command line arguments.

    :arg args: Sequence of command line arguments.
    :returns:  An ``argparse.Namespace`` object containing parsed arguments.
    """

    if len(args) == 0:
        print(usage)
        sys.exit(0)

    parser = argparse.ArgumentParser(prog='extract_noise',
                                     usage=usage,
                                     description=desc)

    parser.add_argument('-o', '--outfile',
                        help=helps['outfile'],
                        default='confound_timeseries.txt')
    parser.add_argument('-ow', '--overwrite',
                        action='store_true',
                        help=helps['overwrite'])
    parser.add_argument('-c', '--conffile',
                        action='append',
                        help=helps['confound'])
    parser.add_argument('icadir',
                        help=helps['icadir'])
    parser.add_argument('components',
                        nargs='+',
                        help=helps['component'])

    args = parser.parse_args(args)

    # Error if ica directory does not exist
    if not op.exists(args.icadir):
        print('ICA directory {} does not exist'.format(args.icadir))
        sys.exit(1)

    # Error if output exists, but overwrite not specified
    if op.exists(args.outfile) and not args.overwrite:
        print('Output file {} already exists and --overwrite not '
              'specified'.format(args.outfile))
        sys.exit(1)

    # Convert components into integers,
    # or absolute file paths, and error
    # if any are not one of these.
    for i, c in enumerate(args.components):
        if op.exists(c):
            args.components[i] = op.abspath(c)
        else:
            try:
                args.components[i] = int(c)
            except ValueError:
                print('Bad component: {}. Components must either be component '
                      'indices (starting from 1), or paths to FIX/AROMA '
                      'files.')
                sys.exit(1)

    # Convert confound files to absolute
    # paths, error if any do not exist.
    for i, cf in enumerate(args.conffile):
        if not op.exists(cf):
            print('Confound file does not exist: {}'.format(cf))
            sys.exit(1)
        args.conffile[i] = op.abspath(cf)

    args.outfile = op.abspath(args.outfile)
    args.icadir  = op.abspath(args.icadir)

    return args


def genComponentIndexList(comps, ncomps):
    """Turns the given sequence of integers and file paths into a list
    of 0-based component indices.

    :arg comps:  Sequence containing 1-based component indices, and/or paths
                 to FIX/AROMA label text files.

    :arg ncomps: Number of components in the input data - indices larger than
                 this will be ignored.

    :returns:    List of 0-based component indices.
    """

    allcomps = []
    badcomps = []

    for c in comps:
        if isinstance(c, int):
            ccomps = [c]
        else:
            ccomps = fixlabels.loadLabelFile(c, returnIndices=True)[2]

        badcomps.extend([cc     for cc in ccomps if cc >= ncomps])
        allcomps.extend([cc - 1 for cc in ccomps if cc <  ncomps])

    if len(badcomps) > 0:
        print('Warning: Ignoring components: {}'.format(badcomps),
              file=sys.stderr)

    return list(sorted(set(allcomps)))


def loadConfoundFiles(conffiles, npts):
    """Loads the given confound files, and copies them all into a single 2D
    ``(npoints, nconfounds)`` matrix.

    :arg conffiles: Sequence of paths to files containing confound time series
                    (where each row corresponds to a time point, and each
                    column corresponds to a single confound).

    :arg npts:      Expected number of time points

    :returns:       A ``(npoints, nconfounds)`` ``numpy`` matrix.
    """

    matrices = []

    for cfile in conffiles:

        mat = np.loadtxt(cfile, dtype=DTYPE)

        if len(mat.shape) == 1:
            mat = np.atleast_2d(mat).T

        if mat.shape[0] != npts:
            print('Warning: confound file {} does not have correct number of '
                  'points (expected {}, has {}). Output will be truncated or '
                  'padded with NaNs.'.format(cfile, npts, mat.shape[1]),
                  file=sys.stderr)
            matrices.append(mat)

    totalcols = sum([m.shape[0] for m in matrices])
    confounds = np.zeros((npts, totalcols), dtype=DTYPE)

    coli = 0
    for mat in matrices:
        ncols = mat.shape[1]

        # too many timepoints - truncate
        if mat.shape[0] > npts:
            mat = mat[:npts, :]

        # too few timepoints - pad with NaN
        elif mat.shape[0] < npts:
            tmat           = mat
            mat            = np.zeros((npts, ncols), dtype=DTYPE)
            mat[:npts,  :] = tmat
            mat[ npts:, :] = np.nan

        confounds[:, coli:coli + ncols] = mat
        coli = coli + ncols

    return confounds


def main(argv=None):
    """Entry point for the ``extract_noise`` script.

    Identifies component time series to extract, extracts them, loads extra
    confound files, and saves them out to a file.
    """

    if argv is None:
        argv = sys.argv[1:]

    args  = parseArgs(argv)
    comps = genComponentIndexList(args.components)
    ts    = melanalysis.getComponentTimeSeries(args.icadir)
    ts    = ts[:, comps]
    confs = loadConfoundFiles(args.conffiles, ts.shape[0])
    ts    = np.hstack((ts, confs))

    np.savetxt(args.outfile, ts, fmt='%10.5f')


if __name__ == '__main__':
    sys.exit(main())
