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
Pipeline illumina
=================


Overview
==================

This workflow processes trimer UMI illumina sequenced fastq files. The aim of
this pipeline is to process the fastq file, collapse the double barcodes/UMI
of read1 so that it is compatible with the downstream kallisto bustools
single-cell analysis.

Usage
=====

To generate the config file to change the running of the pipeline you need to
run:

tallynn illumina config

This will generate a pipeline.yml file that the user can modify to change the
output of the pipeline. Once the user has modified the pipeline.yml file the
pipeline can then be ran using the following commandline command:

tallynn illumina make full -v5

You can run the pipeline locally (without a cluster) using --local

tallynn illumina make full -v5 --local


Configuration
-------------

The pipeline uses CGAT-core as the pipeline language. Please see the
docuemntation for how to install tallynn.


Input files
-----------

The workflow requires the following input:
* a single fastq file generated by illumina based sequencing using scBUC-seq

Pipeline output
==================

The output of this pipeline is a "perfect_collapsed.fastq.[1-2].gz" fastq file.
this file has been barcode corrected an collapsed into single nucleotides so that
it is compatible with downstream workflows.    

Code
==================

"""
from ruffus import *

import sys
import os
import re
import sqlite3
import glob
import pandas as pd

import cgatcore.pipeline as P
import cgatcore.experiment as E

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
        DATADIR = "data.dir"
    else:
        DATADIR = PARAMS['data']


SEQUENCESUFFIXES = ("*.fastq.1.gz")
SEQUENCEFILES = tuple([os.path.join(DATADIR, suffix_name)
                       for suffix_name in SEQUENCESUFFIXES])



@follows(mkdir("corrected_umis.dir"))
@transform(SEQUENCEFILES,
           regex("data.dir/(\S+).fastq.1.gz"),
           r"corrected_umis.dir/\1_corrected.fastq.gz")
def correct_umis(infile, outfile):
    '''correct the umi sequences in the illumina data'''

    read1 = infile
    read2 = infile.replace(".fastq.1.gz", ".fastq.2.gz")

    name = infile.replace("", ".fastq.1.gz")
    name = name.replace("data.dir/", "")

    PYTHON_ROOT = os.path.join(os.path.dirname(__file__), "python/")

    statement = '''python %(PYTHON_ROOT)s/correct_illumina_umi.py --read1=%(read1)s --read2=%(read2)s --outname=%(outfile)s'''

    P.run(statement)


@transform(correct_umis,
           regex("corrected_umis.dir/(\S+)_corrected.fastq.gz"),
           r"mapped.dir/\1.sam")
def map_hisat2(infile, outfile):
    """map with hiat2"""

    statement = """hisat2 -x %(hisat2_index)s -U %(infile)s -S %(outfile)s"""

    P.run(statement)


@transform(map_hisat2,
           regex("mapped.dir/(\S+).sam"),
           r"mapped.dir/\1_sorted.bam")
def run_samtools(infile, outfile):
    """convert sam to bam and sort """

    statement = """samtools view -bh  %(infile)s > %(infile)s_final_gene.bam &&
                   samtools sort %(infile)s_final_gene.bam -o %(outfile)s &&
                   samtools index %(outfile)s"""
    
    P.run(statement)


@transform(run_samtools,
           regex("mapped.dir/(\S+)_sorted.bam"),
           r"mapped.dir/\1_Aligned_final_gene_sorted.bam")
def featurecounts(infile, outfile):
    """run featurecounts and output bam file"""

    name = outfile.replace("_Aligned_final_gene_sorted.bam", "_gene_assigned")

    statement = """featureCounts -a %(gtf)s -o %(name)s -R BAM %(infile)s &&
                   samtools sort %(infile)s.featureCounts.bam  -o %(outfile)s &&
                   samtools index %(outfile)s"""

    P.run(statement)


@follows(mkdir("featurecounts.dir"))
@transform(featurecounts,
           regex("mapped.dir/(\S+)_Aligned_final_gene_sorted.bam"),
           r"featurecounts.dir/\1_counts_genes.tsv.gz")
def count_genes(infile, outfile):
    '''use umi_tools to count the reads - need to adapt umi tools to double oligo'''

    statement = '''umi_tools count --per-gene --gene-tag=XT  -I %(infile)s -S %(outfile)s'''

    P.run(statement)


@transform(featurecounts,
           regex("mapped.dir/(\S+)_Aligned_final_gene_sorted.bam"),
           r"featurecounts.dir/\1_counts_genes_noumis.tsv.gz")
def count_genes_noumis(infile, outfile):
    '''use umi_tools to count the reads - need to adapt umi tools to double oligo'''

    statement = '''umi_tools count --method=unique --per-gene --gene-tag=XT  -I %(infile)s -S %(outfile)s'''

    P.run(statement)


def merge_featurecounts_data(infiles):
    '''will merge all of the input files from featurecounts count output'''

    final_df = pd.DataFrame()
    for infile in infiles:
    
        tmp_df = pd.read_table(infile, sep="\t", header=0, index_col=0, skiprows = 0, compression='gzip')
        tmp_df = tmp_df.iloc[:,-1:]
        tmp_df.columns = ["count"]
        final_df = final_df.merge(tmp_df, how="outer", left_index=True, right_index=True, suffixes=("","_drop"))

    names = [x.replace("", "") for x in infiles]
    final_df.columns = names
    return final_df

@follows(count_genes)
@originate("counts_gene.tsv.gz")
def merge_genes(outfile):
    ''' '''

    infiles = glob.glob("featurecounts.dir/*_counts_genes.tsv.gz")
    final_df = merge_featurecounts_data(infiles)
    names = [x.replace("_counts_genes.tsv.gz", "") for x in infiles]
    final_df.columns = names
    df = final_df.fillna(0)
    df.to_csv(outfile, sep="\t", compression="gzip")


@follows(count_genes_noumis)
@originate("counts_gene_unique.tsv.gz")
def merge_genes_noumi(outfile):
    ''' '''

    infiles = glob.glob("featurecounts.dir/*_counts_genes_noumis.tsv.gz")
    final_df = merge_featurecounts_data(infiles)
    names = [x.replace("_counts_genes_noumis.tsv.gz", "") for x in infiles]
    final_df.columns = names
    df = final_df.fillna(0)
    df.to_csv(outfile, sep="\t", compression="gzip")


@follows(featurecounts)
@originate("counts_gene_noumis.tsv.gz")
def merge_featurecounts(outfile):
    ''' '''

    infiles = glob.glob("mapped.dir/*_gene_assigned")
    final_df = pd.DataFrame()

    for infile in infiles:
    
        tmp_df = pd.read_table(infile, sep="\t", header=0, index_col=0, skiprows = 1)
        tmp_df = tmp_df.iloc[:,-1:]
        tmp_df.columns = ["count"]
        final_df = final_df.merge(tmp_df, how="outer", left_index=True, right_index=True, suffixes=("","_drop"))
    names = [x.replace("_gene_assigned", "") for x in infiles]
    final_df.columns = names
    
    df = final_df.fillna(0)
    df.to_csv(outfile, sep="\t", compression="gzip")

@follows(merge_genes, merge_genes_noumi, merge_featurecounts)
def full():
    pass


def main(argv=None):
    if argv is None:
        argv = sys.argv
    P.main(argv)

if __name__ == "__main__":
    sys.exit(P.main(sys.argv))
