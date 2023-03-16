"""===========================
Pipeline barcode
===========================

Overview
========

The aim of this pipeline is to take a nanopore input fastq and then process
the file so that it splits the files out into individual fastq files based
on the barcode sequences.

Usage
=====

See :ref:`PipelineSettingUp` and :ref:`PipelineRunning` on general
information how to use CGAT pipelines.

Configuration
-------------

The pipeline requires a configured :file:`pipeline.yml` file.
CGATReport report requires a :file:`conf.py` and optionally a
:file:`cgatreport.ini` file (see :ref:`PipelineReporting`).

Default configuration files can be generated by executing:

   python <srcdir>/pipeline_barcode.py config

Input files
-----------

fastq.gz file of nanopore reads that have been sequenced with trimer barcodes
at the polyA end.

Pipeline output
===============

Individual fastq files split based on the presence of the barcode 

Code
====

"""
import sys
import os
import pysam
import glob
import pandas as pd
from ruffus import *
import cgatcore.iotools as iotools
import cgatcore.pipeline as P
import cgatcore.experiment as E
from cgatcore.pipeline import cluster_runnable

# load options from the config file
PARAMS = P.get_parameters(
    ["%s/pipeline.yml" % os.path.splitext(__file__)[0],
     "../pipeline.yml",
     "pipeline.yml"])


SEQUENCESUFFIXES = ("*.fastq.gz")

FASTQTARGET = tuple([os.path.join("data.dir/", suffix_name)
                       for suffix_name in SEQUENCESUFFIXES])


@follows(mkdir("split_tmp.dir"))
@transform('data.dir/*.fastq.gz',
           regex('data.dir/(\S+).fastq.gz'),
           r"split_tmp.dir/\1.aa")
def split_fastq(infile, outfile):
    '''
    Split the fastq file before identifying perfect barcodes
    '''

    infile = "".join(infile)
    name = infile.replace('data.dir/','')
    name = name.replace('.fastq.gz','')

    statement = '''zcat %(infile)s | split -l %(split)s - %(name)s. &&
                   mv %(name)s*.* split_tmp.dir/'''

    P.run(statement)


@follows(split_fastq)
@follows(mkdir("polyA_correct.dir"))
@transform('split_tmp.dir/*',
           regex("split_tmp.dir/(\S+)"),
           r"polyA_correct.dir/\1_correct_polya.fastq")
def correct_polyA(infile, outfile):
    '''
    Look across all fastq files and correct the polyA so its on same strand
    '''

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/complement_polyA.py --infile=%(infile)s --outname=%(outfile)s'''

    P.run(statement)


@follows(mkdir("seperate_samples.dir"))
@transform('polyA_correct.dir/*',
           regex("polyA_correct.dir/(\S+)_correct_polya.fastq"),
           r"seperate_samples.dir/\1.fastq.gz")
def seperate_by_barcode(infile, outfile):
    '''
    Identify barcode and save to different samples
    '''

    name = outfile.replace("seperate_samples.dir/", "")
    name = name.replace(".fastq.gz", "")

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/identify_index.py --infile=%(infile)s --name=%(name)s'''

    P.run(statement)



@follows(seperate_by_barcode)
def full():
    pass


def main(argv=None):
    if argv is None:
        argv = sys.argv
    P.main(argv)


if __name__ == "__main__":
    sys.exit(P.main(sys.argv))    