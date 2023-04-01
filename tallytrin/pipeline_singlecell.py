##############################################################################
#
#   Botnar Resaerch Centre
#
#   $Id$
#
#   Copyright (C) 2020 Adam Cribbs
#
#   This program is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; either version 2
#   of the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
###############################################################################

"""
=================
Pipeline single-cell
=================


Overview
==================

The code is a python script that processes single-cell sequencing data from
scCOLOR-seq-homotrimerUMI nanopore fastq files and generates a gene level and
transcript level market matrix counts matrix. The code uses the CGAT-core
library for pipeline management and the Ruffus library for task management.

The code first reads the pipeline configuration from pipeline.yml file,
which can be found in the same directory as the script, in a parent 
directory, or in a directory specified in the data parameter. The pipeline 
then splits the input fastq file into smaller pieces, performs quality control 
on the split files, and generates gene-level and transcript-level counts 
matrices in market matrix format. The final outputs are saved in the mtx.dir/ 
and mtx_gene.dir/ directories, respectively. The results can be imported 
into R using the read_count_output() function within the library(BUSpaRse) 
package.

Usage
=====

To generate the config file to change the running of the pipeline you need to
run:

tallynn nanopore config

This will generate a pipeline.yml file that the user can modify to change the
output of the pipeline. Once the user has modified the pipeline.yml file the
pipeline can then be ran using the following commandline command:

tallynn nanopore make full -v5

You can run the pipeline locally (without a cluster) using --local

tallynn nanopore make full -v5 --local

Configuration
-------------

The pipeline uses CGAT-core as the pipeline language. Please see the
docuemntation for how to install tallynn.


Input files
-----------

The workflow requires the following inputs:
* a single fastq file generated by guppy basecalling
* a transcriptome genome of your choice
* a genome fasta file
* a minimap2 junction bed generated following minimap2 instructions: https://github.com/lh3/minimap2/blob/master/README.md
* a gtf file

Pipeline output
==================

There are two main outputs of the pipeline that are useful for downstream
analysis for standard single-cell RNA seq workflows
(Seurat, SingleCellExperiment e.c.t.). The first is a market matrix format (.mtx)
output of the counts for transcripts. This can be found within the directory
mtx.dir/ and the second is a .mtx file for the gene level analysis.

Each of these outputs can be easily imported into R using the read_count_output()
function within library(BUSpaRse) by pointing the directory to either mtx.dir/ or
mtx_gene.dir/.

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
@split('data/*.fastq.gz', "split_tmp.dir/out*")
def split_fastq(infile, outfiles):
    '''
    Split the fastq file before identifying perfect barcodes
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
    Look across all fastq files and correct the polyA so its on same strand
    '''

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/complement_polyA_singlecell.py --infile=%(infile)s --outname=%(outfile)s'''

    P.run(statement)


@follows(mkdir("polyA_umi.dir"))
@transform(correct_polyA,
           regex("polyA_correct.dir/(\S+)_correct_polya.fastq"),
           r"polyA_umi.dir/\1.fastq.gz")
def identify_bcumi(infile, outfile):
    '''
    Identify barcode and umi sequences
    '''

    name = outfile.replace("polyA_umi.dir/", "")
    name = name.replace(".fastq.gz", "")

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/identify_perfect_nano.py --outfile=%(outfile)s --infile=%(infile)s --whitelist=polyA_umi.dir/%(name)s.whitelist.txt'''

    P.run(statement)



@merge(identify_bcumi, "whitelist.txt")
def merge_whitelist(infiles, outfile):
    '''
    merge whitelists
    '''

    whitelists = []

    for i in infiles:

        whitelists.append(i.replace(".fastq.gz", ".whitelist.txt"))

    whitelist_files = " ".join(whitelists)

    statement = '''cat %(whitelist_files)s | sort | uniq > %(outfile)s'''

    P.run(statement)



@follows(mkdir("correct_reads.dir"))
@transform(identify_bcumi,
           regex("polyA_umi.dir/(\S+).fastq.gz"),
           r"correct_reads.dir/\1.fastq.gz")
def correct_reads(infile, outfile):
    '''Correct the barcodes using majority vote'''

    infile = infile

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")


    statement = '''python %(PYTHON_ROOT)s/correct_barcode_nano.py --infile=%(infile)s --outfile=%(outfile)s'''

    P.run(statement)


@merge(correct_reads, "merge_corrected.fastq.gz")
def merge_correct_reads(infiles, outfile):
    '''Merge the corrected reads '''

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
    '''Run minimap2 to map the fastq file'''


    cdna = PARAMS['minimap2_fasta_cdna']
    options = PARAMS['minimap2_options']

    statement = '''minimap2  %(options)s %(cdna)s  %(infile)s > %(outfile)s 2> %(outfile)s.log'''

    P.run(statement)


@transform(mapping,
           regex("final.sam"),
           r"final_sorted.bam")
def run_samtools(infile, outfile):
    '''convert sam to bam and sort -F 272'''

    statement = '''samtools view -bS %(infile)s > final.bam &&
                   samtools sort final.bam -o final_sorted.bam &&
                   samtools index final_sorted.bam'''

    P.run(statement)


@transform(run_samtools,
           regex("final_sorted.bam"),
           r"final_XT.bam")
def add_xt_tag(infile, outfile):
    '''Add trancript name to XT tag in bam file so umi-tools counts can be  perfromed'''

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/xt_tag_nano.py --infile=%(infile)s --outfile=%(outfile)s &&
                   samtools index %(outfile)s'''

    P.run(statement)


@transform(add_xt_tag,
           regex("final_XT.bam"),
           r"counts.tsv.gz")
def count(infile, outfile):
    '''use umi_tools to count the reads - need to adapt umi tools to double oligo'''

    statement = '''umi_tools count --method unique --per-gene --gene-tag=XT --per-cell  -I %(infile)s -S counts.tsv.gz'''

    P.run(statement)


@follows(mkdir("mtx.dir"))
@transform(count,
           regex("counts.tsv.gz"),
           r"mtx.dir/genes.mtx")
def convert_tomtx(infile, outfile):
    ''' '''
    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/save_mtx.py --data=%(infile)s --dir=mtx.dir/'''

    P.run(statement, job_memory="250G")


@merge(identify_bcumi, "merge_uncorrected.fastq.gz")
def merge_uncorrect_reads(infiles, outfile):
    '''Merge the reads that are still containing trimer barcode and umi'''

    infile = []

    for i in infiles:
        infile.append(str(i))

    infile_join = " ".join(infile)



    statement = '''cat %(infile_join)s > %(outfile)s'''

    P.run(statement)


@transform(merge_uncorrect_reads,
           regex("merge_uncorrected.fastq.gz"),
           r"final_uncorrected.sam")
def mapping_trimer(infile, outfile):
    '''Run minimap2 to map the fastq file'''


    cdna = PARAMS['minimap2_fasta_cdna']
    options = PARAMS['minimap2_options']

    statement = '''minimap2  %(options)s %(cdna)s  %(infile)s > %(outfile)s 2> %(outfile)s.log'''

    P.run(statement)


@follows(mkdir("collapse_reads.dir"))
@transform(identify_bcumi,
           regex("polyA_umi.dir/(\S+).fastq.gz"),
           r"collapse_reads.dir/\1.fastq.gz")
def collapse_reads(infile, outfile):
    '''Correct the barcodes by picking first ucleotide in the barcode and umi'''

    infile = infile

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")


    statement = '''python %(PYTHON_ROOT)s/single_nucleotide_select.py --infile=%(infile)s --outfile=%(outfile)s'''

    P.run(statement)


@merge(collapse_reads, "merge_collapsed.fastq.gz")
def merge_singlenuc_reads(infiles, outfile):
    '''Merge the reads that were collapsed into single nucleotides'''

    infile = []

    for i in infiles:
        infile.append(str(i))

    infile_join = " ".join(infile)



    statement = '''cat %(infile_join)s > %(outfile)s'''

    P.run(statement)


@transform(merge_singlenuc_reads,
           regex("merge_collapsed.fastq.gz"),
           r"final_collapsed.sam")
def mapping_collapsed(infile, outfile):
    '''Run minimap2 to map the fastq file'''


    cdna = PARAMS['minimap2_fasta_cdna']
    options = PARAMS['minimap2_options']

    statement = '''minimap2  %(options)s %(cdna)s  %(infile)s > %(outfile)s 2> %(outfile)s.log'''

    P.run(statement)



@transform(mapping_collapsed,
           regex("final_collapsed.sam"),
           r"final_sorted_collapsed.bam")
def run_samtools_collapsed(infile, outfile):
    '''convert sam to bam and sort -F 272'''

    statement = '''samtools view -bS %(infile)s > final_collapsed.bam &&
                   samtools sort final_collapsed.bam -o final_sorted_collapsed.bam &&
                   samtools index final_sorted_collapsed.bam'''

    P.run(statement)


@transform(run_samtools_collapsed,
           regex("final_sorted_collapsed.bam"),
           r"final_XT_collapsed.bam")
def add_xt_tag_collapsed(infile, outfile):
    '''Add trancript name to XT tag in bam file so umi-tools counts can be  perfromed'''

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/xt_tag_nano.py --infile=%(infile)s --outfile=%(outfile)s &&
                   samtools index %(outfile)s'''

    P.run(statement)


@transform(add_xt_tag_collapsed,
           regex("final_XT_collapsed.bam"),
           r"counts_collapsed.tsv.gz")
def count_collapsed(infile, outfile):
    '''use umi_tools to count the reads - need to adapt umi tools to double oligo'''

    statement = '''umi_tools count --method unique --per-gene --gene-tag=XT --per-cell  -I %(infile)s -S %(outfile)s'''

    P.run(statement)


@follows(mkdir("mtx_collapsed.dir"))
@transform(count_collapsed,
           regex("counts_collapsed.tsv.gz"),
           r"mtx_collapsed.dir/genes.mtx")
def convert_tomtx_collapsed(infile, outfile):
    ''' '''
    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/save_mtx.py --data=%(infile)s --dir=mtx_collapsed.dir/'''

    P.run(statement, job_memory="250G")



@transform(add_xt_tag_collapsed,
           regex("final_XT_collapsed.bam"),
           r"counts_collapsed_directional.tsv.gz")
def count_collapsed_direction(infile, outfile):
    '''use umi_tools to count the reads - need to adapt umi tools to double oligo'''

    statement = '''umi_tools count  --per-gene --gene-tag=XT --per-cell  -I %(infile)s -S %(outfile)s'''

    P.run(statement)


@follows(mkdir("mtx_collapsed_directional.dir"))
@transform(count_collapsed_direction,
           regex("counts_collapsed_directional.tsv.gz"),
           r"mtx_collapsed_directional.dir/genes.mtx")
def convert_tomtx_directional(infile, outfile):
    ''' '''
    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/save_mtx.py --data=%(infile)s --dir=mtx_collapsed_directional.dir/'''

    P.run(statement, job_memory="250G")


###########################################################################
# Correct the UMIs using greedy
###########################################################################

# Need to input the bam file without collapsing trimers - minimap with fastq before collapsing then
# running ILP


@merge(correct_reads, "merge_trimer.fastq.gz")
def merge_trimer_bcumi(infiles, outfile):
    '''Merge the fastq reads with uncollapsed trime reads '''

    infile = []

    for i in infiles:
        infile.append(str(i))

    infile_join = " ".join(infile)



    statement = '''cat %(infile_join)s > %(outfile)s'''

    P.run(statement)


@transform(merge_trimer_bcumi,
           regex("merge_trimer.fastq.gz"),
           r"final_trimer.sam")
def run_minimap2_trimer(infile, outfile):
    '''Run minimap2 using fastq files with trimer UMIs'''  

    cdna = PARAMS['minimap2_fasta_cdna']
    options = PARAMS['minimap2_options']

    statement = '''minimap2  %(options)s %(cdna)s  %(infile)s > %(outfile)s 2> %(outfile)s.log'''

    P.run(statement)


@transform(run_minimap2_trimer,
           regex("final_trimer.sam"),
           r"final_sorted_trimer.bam")
def run_samtools_trimer(infile, outfile):
    '''convert sam to bam and sort -F 272'''

    statement = '''samtools view -bS %(infile)s > final_trimer.bam &&
                   samtools sort final_trimer.bam -o final_sorted_trimer.bam &&
                   samtools index final_sorted_trimer.bam'''

    P.run(statement)


@transform(run_samtools_trimer,
           regex("final_sorted_trimer.bam"),
           r"final_XT_trimer.bam")
def add_xt_tag_trimer(infile, outfile):
    '''Add trancript name to XT tag in bam file so umi-tools counts can be  perfromed'''

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/xt_tag_nano.py --infile=%(infile)s --outfile=%(outfile)s &&
                   samtools index %(outfile)s'''

    P.run(statement)



@transform(add_xt_tag_trimer,
           regex("final_XT_trimer.bam"),
           r"greedy.csv")
def run_greedy(infile, outfile):
    '''Run greedy algorithm to collapse the UMIs'''

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/greedy_sc.py count -i %(infile)s -t XT-o %(outfile)s'''

    P.run(statement)


@follows(convert_tomtx_directional, convert_tomtx_collapsed, convert_tomtx, run_greedy)
def full():
    pass


def main(argv=None):
    if argv is None:
        argv = sys.argv
    P.main(argv)

if __name__ == "__main__":
    sys.exit(P.main(sys.argv))