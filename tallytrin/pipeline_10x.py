"""
============
Pipeline 10X
============


Overview
==================

This Python code is a pipeline for processing 10X single-cell sequencing data using the primer sequence as a common molecular identifier to show the accuracy of single-cell sequencing. The goal of this pipeline is to generate both a gene-level and transcript-level market matrix count matrix (.mtx).

Input files
-----------

The pipeline requires the following inputs:

* a single fastq file generated by guppy basecalling
* a transcriptome genome of your choice
* a genome fasta file
* a minimap2 junction bed generated following minimap2 instructions
* a gtf file

Pipeline Tasks
==============

The pipeline performs the following tasks:

* Split the fastq file before identifying perfect barcodes
* Correct the polyA so it's on the same strand
* Identify barcode and UMI sequences
* Merge whitelists
* Align the barcodes to the closest barcode
* Merge the corrected reads
* Map the fastq file using minimap2
* Convert SAM to BAM and sort the file
* Add transcript name to XT tag in the BAM file
* Count the reads using umi_tools
* Convert the count matrix to .mtx format


Pipeline output
===============

The two main outputs of the pipeline are:

* A .mtx file for the transcript-level analysis, which can be found within the directory mtx.dir/
* A .mtx file for the gene-level analysis, which can be found within the directory mtx_gene.dir/


These outputs can be easily imported into R using the read_count_output() function within library(BUSpaRse).


Usage
=====

To generate the config file to change the running of the pipeline you need to
run:

tallytrin 10x config

This will generate a pipeline.yml file that the user can modify to change the
output of the pipeline. Once the user has modified the pipeline.yml file the
pipeline can then be ran using the following commandline command:

tallytrin 10x make full -v5

You can run the pipeline locally (without a cluster) using --local

tallytrin 10x make full -v5 --local



Code
==================

"""
from ruffus import *

import sys
import os
import re
import sqlite3
import glob

import cgatcore.pipeline as P
import cgatcore.experiment as E
import cgatcore.database as database

# Load options from the config file

PARAMS = P.get_parameters(
    ["%s/pipeline.yml" % os.path.splitext(__file__)[0],
     "../pipeline.yml",
     "pipeline.yml"])


# Determine the location of the input fastq files

try:
    PARAMS['data']
except NameError:
    DATADIR = "."
else:
    if PARAMS['data'] == 0:
        DATADIR = "."
    elif PARAMS['data'] == 1:
        DATADIR = "data"
    else:
        DATADIR = PARAMS['data']


def connect():
    ''' Connect to database'''

    dbh = sqlite3.connect('csvdb')

    return dbh


SEQUENCESUFFIXES = ("*.fastq")
SEQUENCEFILES = tuple([os.path.join(DATADIR, suffix_name)
                       for suffix_name in SEQUENCESUFFIXES])


@follows(mkdir("split_tmp.dir"))
@split('%s/*.fastq.gz'% (PARAMS['data']), "split_tmp.dir/out*")
def split_fastq(infile, outfiles):
    '''
    Splits the input fastq file into smaller chunks. 
    The number of lines per chunk is determined by the split 
    parameter from the config file. The output files are 
    stored in the "split_tmp.dir" directory.
    '''

    infile = "".join(infile)

    statement = '''zcat %(infile)s | split -l %(split)s - out. &&
                   mv out*.* split_tmp.dir/'''

    P.run(statement)


@follows(mkdir("polyA_correct.dir"))
@transform(split_fastq,
           regex("split_tmp.dir/out.(\S+)"),
           r"polyA_correct.dir/\1_correct_polya.fastq")
def correct_polyA(infile, outfile):
    '''
    Corrects the polyA tail sequence in each input fastq file,
    ensuring it is on the same strand. The output is stored in
    the "polyA_correct.dir" directory.
    '''

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/complement_polyA_singlecell.py --infile=%(infile)s --outname=%(outfile)s'''

    P.run(statement, job_options='-t 24:00:00')


@follows(mkdir("polyA_umi.dir"))
@transform(correct_polyA,
           regex("polyA_correct.dir/(\S+)_correct_polya.fastq"),
           r"polyA_umi.dir/\1.fastq.gz")
def identify_bcumi(infile, outfile):
    '''
    Identifies the barcode and UMI sequences in the input fastq files.
    The output is stored in the "polyA_umi.dir" directory. Additionally,
    a whitelist file containing the barcodes is generated.
    '''

    name = outfile.replace("polyA_umi.dir/", "")
    name = name.replace(".fastq.gz", "")

    cmimode = PARAMS['cmi_mode']

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/10x_identify_barcode.py --outfile=%(outfile)s --infile=%(infile)s --whitelist=polyA_umi.dir/%(name)s.whitelist.txt
                   --cmimode=%(cmimode)s --barcode=%(barcode)s'''

    P.run(statement, job_options='-t 24:00:00')



@merge(identify_bcumi, "whitelist.txt")
def merge_whitelist(infiles, outfile):
    '''
    Merges the whitelist files generated by the
    identify_bcumi function. The output is a single
    file called "whitelist.txt".
    '''

    whitelists = []

    for i in infiles:

        whitelists.append(i.replace(".fastq.gz", ".whitelist.txt"))

    whitelist_files = " ".join(whitelists)

    statement = '''cat %(whitelist_files)s  > %(outfile)s'''

    P.run(statement)



@follows(merge_whitelist)
@follows(mkdir("correct_reads.dir"))
@transform(identify_bcumi,
           regex("polyA_umi.dir/(\S+).fastq.gz"),
           r"correct_reads.dir/\1.fastq.gz")
def correct_reads(infile, outfile):
    '''
    Aligns the barcodes in the input fastq files to the closest
    barcode using the "whitelist.txt" file. The output is
    stored in the "correct_reads.dir" directory.
    '''

    infile = infile
    cells = PARAMS['cells']

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    cmimode = PARAMS['cmi_mode']

    statement = '''python %(PYTHON_ROOT)s/correct_10xbarcode.py --infile=%(infile)s --outfile=%(outfile)s --cells=%(cells)s --whitelist=whitelist.txt  --cmimode=%(cmimode)s'''

    P.run(statement, job_options='-t 24:00:00')


@merge(correct_reads, "merge_corrected.fastq.gz")
def merge_correct_reads(infiles, outfile):
    '''
    Merges the corrected fastq files generated by
    the correct_reads function. The output is a single
    file called "merge_corrected.fastq.gz".
    '''

    infile = []

    for i in infiles:
        infile.append(str(i))

    infile_join = " ".join(infile)



    statement = '''cat %(infile_join)s > %(outfile)s'''

    P.run(statement)


@transform(merge_correct_reads,
           regex("merge_corrected.fastq.gz"),
           r"final.sam")
def mapping(infile, outfile):
    '''
    Maps the input fastq file to the reference transcriptome
    using minimap2. The output is a SAM file called "final.sam".
    '''


    cdna = PARAMS['minimap2_fasta_cdna']
    options = PARAMS['minimap2_options']
    run_options = PARAMS['job_options']

    statement = '''minimap2  %(options)s %(cdna)s  %(infile)s > %(outfile)s 2> %(outfile)s.log'''

    P.run(statement, job_options=run_options, job_threads=4)


@transform(mapping,
           regex("final.sam"),
           r"final_sorted.bam")
def run_samtools(infile, outfile):
    '''Converts the input SAM file to a BAM file, sorts it, and indexes it.
    The output is a sorted BAM file called "final_sorted.bam".'''

    statement = '''samtools view -bS %(infile)s > final.bam &&
                   samtools sort final.bam -o final_sorted.bam &&
                   samtools index final_sorted.bam'''

    P.run(statement, job_options='-t 24:00:00')


@transform(run_samtools,
           regex("final_sorted.bam"),
           r"final_XT.bam")
def add_xt_tag(infile, outfile):
    '''Adds the transcript name to the XT tag in the input BAM
    file so that umi-tools can perform read counting. The output
    is a BAM file called "final_XT.bam".'''

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/xt_tag_nano.py --infile=%(infile)s --outfile=%(outfile)s &&
                   samtools index %(outfile)s'''

    P.run(statement, job_options='-t 24:00:00')


@transform(add_xt_tag,
           regex("final_XT.bam"),
           r"counts.tsv.gz")
def count(infile, outfile):
    '''Counts the reads in the input BAM file using umi_tools with
    unique method, per gene and per cell. The output is a compressed
    TSV file called "counts.tsv.gz".'''

    statement = '''umi_tools count --method unique --per-gene --gene-tag=XT --per-cell  -I %(infile)s -S counts.tsv.gz'''

    P.run(statement, job_options='-t 24:00:00')


@follows(mkdir("mtx.dir"))
@transform(count,
           regex("counts.tsv.gz"),
           r"mtx.dir/genes.mtx")
def convert_tomtx(infile, outfile):
    '''
    Converts the count matrix in the input TSV file to a .mtx format.
    The output is stored in the "mtx.dir" directory.
    '''
    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/save_mtx.py --data=%(infile)s --dir=mtx.dir/'''

    P.run(statement, job_memory="100G", job_options='-t 24:00:00')


@follows(convert_tomtx)
def full():
    '''
    A placeholder function that serves as a checkpoint
    to run all previous ruffus tasks and ensure that all
    previous tasks are completed.
    '''
    pass


def main(argv=None):
    '''
    The main function that runs the pipeline using the cgatcore.pipeline module.
    Takes an optional argument list (default is sys.argv).

    Please note that some of these functions use external Python scripts or
    tools. For a complete understanding of their functionality, it is
    necessary to examine the code of those scripts as well.
    '''
    if argv is None:
        argv = sys.argv
    P.main(argv)

if __name__ == "__main__":
    sys.exit(P.main(sys.argv))
