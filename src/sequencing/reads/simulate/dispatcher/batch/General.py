__version__ = "v1.0"
__copyright__ = "Copyright 2021"
__license__ = "MIT"
__lab__ = "Adam Cribbs lab"

import numpy as np
from src.sequencing.reads.simulate.dispatcher.General import general as simugeneral
from Path import to


class general(object):

    def __init__(self, ):
        self.permutation_num = 10

        self.umi_unit_len_fixed = 10
        self.seq_len_fixed = 100
        self.umi_num_fixed = 50
        self.pcr_num_fixed = 17
        self.pcr_err_fixed = 1e-3
        self.seq_err_fixed = 1e-3
        self.ampl_rate_fixed = 0.85
        self.sim_thres_fixed = 3
        self.seq_sub_spl_rate = 0.3333

        self.ampl_rates = np.linspace(0.1, 1, 10)
        self.umi_unit_lens = np.arange(6, 36 + 1, 1)
        self.umi_nums = np.arange(20, 140 + 20, 20)
        self.pcr_nums = np.arange(1, 20 + 1, 1)
        self.pcr_errs, self.seq_errs = self.errors()
        print(self.pcr_errs, self.seq_errs)

        self.metrics = {
            'pcr_nums': self.pcr_nums,
            'pcr_errs': self.pcr_errs,
            'seq_errs': self.seq_errs,
            'ampl_rates': self.ampl_rates,
            'umi_lens': self.umi_unit_lens,
        }
        self.fastq_fn_pref = {
            'pcr_nums': 'pcr_',
            'pcr_errs': 'pcr_err_',
            'seq_errs': 'seq_err_',
            'ampl_rates': 'ampl_rate_',
            'umi_lens': 'umi_len_',
        }

    def errors(self, ):
        pcr_errs = []
        seq_errs = []
        e = 1e-5
        while e < 3e-1:
            pcr_errs.append(e)
            seq_errs.append(e)
            if 5 * e < 3e-1:
                pcr_errs.append(2.5 * e)
                pcr_errs.append(5 * e)
                pcr_errs.append(7.5 * e)
                seq_errs.append(2.5 * e)
                seq_errs.append(5 * e)

                seq_errs.append(7.5 * e)
            e = 10 * e
        pcr_errs.append(0.2)
        seq_errs.append(0.2)
        pcr_errs.append(0.3)
        seq_errs.append(0.3)
        # print(pcr_errs)
        # print(seq_errs)
        return pcr_errs, seq_errs

    def pcrNums(self, ):
        for pn in range(self.permutation_num):
            simu_params = {
                'init_seq_setting': {
                    'seq_num': self.umi_num_fixed,
                    'umi_unit_pattern': 1,
                    'umi_unit_len': self.umi_unit_len_fixed,
                    'seq_len': self.seq_len_fixed - self.umi_unit_len_fixed,
                    'is_seed': True,
                    'working_dir': to('data/simu/umi_seq/pcr_num/permute_') + str(pn) + '/',
                    'is_sv_umi_lib': True,
                    'umi_lib_fpn': to('data/simu/umi_seq/pcr_num/permute_') + str(pn) + '/umi.txt',
                    'is_sv_seq_lib': True,
                    'seq_lib_fpn': to('data/simu/umi_seq/pcr_num/permute_') + str(pn) + '/seq.txt',
                    'condis': ['umi', 'seq'],
                    'sim_thres': self.sim_thres_fixed,
                    'permutation': pn,
                },
                'ampl_rate': self.ampl_rate_fixed,
                'pcr_nums': self.pcr_nums,
                'err_num_met': 'nbinomial',
                'pcr_error': self.pcr_err_fixed,
                'seq_error': self.seq_err_fixed,
                'seq_sub_spl_rate': self.seq_sub_spl_rate,
                'use_seed': False,
                'seed': None,
                'write': {
                    'fastq_fp': to('data/simu/umi_seq/pcr_num/permute_') + str(pn) + '/',
                    'fastq_fn': '',
                }
            }
            p = simugeneral(simu_params)
            print(p.ondemandPCRErrs())
        return

    def pcrErrs(self, ):
        for pn in range(self.permutation_num):
            simu_params = {
                'init_seq_setting': {
                    'seq_num': self.umi_num_fixed,
                    'umi_unit_pattern': 1,
                    'umi_unit_len': self.umi_unit_len_fixed,
                    'seq_len': self.seq_len_fixed - self.umi_unit_len_fixed,
                    'is_seed': True,
                    'working_dir': to('data/simu/umi_seq/pcr_err/permute_') + str(pn) + '/',
                    'is_sv_umi_lib': True,
                    'umi_lib_fpn': to('data/simu/umi_seq/pcr_err/permute_') + str(pn) + '/umi.txt',
                    'is_sv_seq_lib': True,
                    'seq_lib_fpn': to('data/simu/umi_seq/pcr_err/permute_') + str(pn) + '/seq.txt',
                    'condis': ['umi', 'seq'],
                    'sim_thres': self.sim_thres_fixed,
                    'permutation': pn,
                },
                'ampl_rate': self.ampl_rate_fixed,
                'pcr_num': self.pcr_num_fixed,
                'err_num_met': 'nbinomial',
                'pcr_errors': self.pcr_errs,
                'seq_error': self.seq_err_fixed,
                'seq_sub_spl_rate': self.seq_sub_spl_rate,
                'use_seed': False,
                'seed': None,
                'write': {
                    'fastq_fp': to('data/simu/umi_seq/pcr_err/permute_') + str(pn) + '/',
                    'fastq_fn': '',
                }
            }
            p = simugeneral(simu_params)
            print(p.ondemandPCRErrs())
        return

    def seqErrs(self, ):
        for pn in range(self.permutation_num):
            simu_params = {
                'init_seq_setting': {
                    'seq_num': self.umi_num_fixed,
                    'umi_unit_pattern': 1,
                    'umi_unit_len': self.umi_unit_len_fixed,
                    'seq_len': self.seq_len_fixed - self.umi_unit_len_fixed,
                    'is_seed': True,
                    'working_dir': to('data/simu/umi_seq/seq_err/permute_') + str(pn) + '/',
                    'is_sv_umi_lib':True,
                    'umi_lib_fpn':to('data/simu/umi_seq/seq_err/permute_') + str(pn) + '/umi.txt',
                    'is_sv_seq_lib':True,
                    'seq_lib_fpn':to('data/simu/umi_seq/seq_err/permute_') + str(pn) + '/seq.txt',
                    'condis': ['umi', 'seq'],
                    'sim_thres': self.sim_thres_fixed,
                    'permutation': pn,
                },
                'ampl_rate': self.ampl_rate_fixed,
                'pcr_num': self.pcr_num_fixed,
                'err_num_met': 'nbinomial',
                'pcr_error': self.pcr_err_fixed,
                'seq_errors': self.seq_errs,
                'seq_sub_spl_rate': self.seq_sub_spl_rate,
                'use_seed': False,
                'seed': None,
                'write': {
                    'fastq_fp': to('data/simu/umi_seq/seq_err/permute_') + str(pn) + '/',
                    'fastq_fn': '',
                }
            }
            p = simugeneral(simu_params)
            print(p.ondemandSeqErrs())
        return

    def umiLens(self, ):
        for pn in range(self.permutation_num):
            simu_params = {
                'init_seq_setting': {
                    'seq_num': self.umi_num_fixed,
                    'umi_unit_pattern': 1,
                    'umi_unit_lens': self.umi_unit_lens,
                    'seq_len': self.seq_len_fixed,
                    'is_seed': True,
                    'working_dir': to('data/simu/umi_seq/umi_len/permute_') + str(pn) + '/',
                    'is_sv_umi_lib': True,
                    'umi_lib_fpn': to('data/simu/umi_seq/umi_len/permute_') + str(pn) + '/',
                    'is_sv_seq_lib': True,
                    'seq_lib_fpn': to('data/simu/umi_seq/umi_len/permute_') + str(pn) + '/',
                    'condis': ['umi', 'seq'],
                    'sim_thres': self.sim_thres_fixed,
                    'permutation': pn,
                },
                'ampl_rate': self.ampl_rate_fixed,
                'pcr_num': self.pcr_num_fixed,
                'err_num_met': 'nbinomial',
                'pcr_error': self.pcr_err_fixed,
                'seq_error': self.seq_err_fixed,
                'seq_sub_spl_rate': self.seq_sub_spl_rate,
                'use_seed': False,
                'seed': None,
                'write': {
                    'fastq_fp': to('data/simu/umi_seq/umi_len/permute_') + str(pn) + '/',
                    'fastq_fn': '',
                }
            }
            p = simugeneral(simu_params)
            print(p.ondemandPCRErrs())
        return

    def amplRates(self, ):
        for pn in range(self.permutation_num):
            simu_params = {
                'init_seq_setting': {
                    'seq_num': self.umi_num_fixed,
                    'umi_unit_pattern': 1,
                    'umi_unit_len': self.umi_unit_len_fixed,
                    'seq_len': self.seq_len_fixed - self.umi_unit_len_fixed,
                    'is_seed': True,
                    'working_dir': to('data/simu/umi_seq/ampl_rate/permute_') + str(pn) + '/',
                    'is_sv_umi_lib': True,
                    'umi_lib_fpn': to('data/simu/umi_seq/ampl_rate/permute_') + str(pn) + '/umi.txt',
                    'is_sv_seq_lib': True,
                    'seq_lib_fpn': to('data/simu/umi_seq/ampl_rate/permute_') + str(pn) + '/seq.txt',
                    'condis': ['umi', 'seq'],
                    'sim_thres': self.sim_thres_fixed,
                    'permutation': pn,
                },
                'ampl_rates': self.ampl_rates,
                'pcr_num': self.pcr_num_fixed,
                'err_num_met': 'nbinomial',
                'pcr_error': self.pcr_err_fixed,
                'seq_error': self.seq_err_fixed,
                'seq_sub_spl_rate': self.seq_sub_spl_rate,
                'use_seed': False,
                'seed': None,
                'write': {
                    'fastq_fp': to('data/simu/umi_seq/ampl_rate/permute_') + str(pn) + '/',
                    'fastq_fn': '',
                }
            }
            p = simugeneral(simu_params)
            print(p.ondemandPCRErrs())
        return


if __name__ == "__main__":
    p = general()

    # print(p.pcrNums())

    print(p.pcrErrs())

    # print(p.seqErrs())

    # print(p.umiLens())

    # print(p.amplRates())