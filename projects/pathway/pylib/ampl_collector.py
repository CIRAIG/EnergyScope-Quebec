#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr 08 2022

@author: rixhonx
"""

from pathlib import Path

import os, sys
import csv
import pickle
import warnings
import pandas as pd
from datetime import datetime
from time import time
warnings.filterwarnings('ignore', category=FutureWarning)

pylibPath = os.path.abspath("../pylib")
if pylibPath not in sys.path:
    sys.path.insert(0, pylibPath)


class AmplCollector:

    """

    The AmplCollector class allows to store interesting results/outputs along the
    different time windows

    Parameters
    ----------
    ampl_pre : AmplPreprocessor object of ampl_preprocessor module
        Ampl Preprocessor containing an Ampl object and its sets
    output_file : pathlib.Path
        Path towards the output file where to pickle the results
    expl_text : String
        Small description of the case study

    """

    def __init__(self, ampl_pre, output_file, expl_text = ''):

        self.ampl_pre = ampl_pre
        self.pth_output_all = Path(output_file).parent.parent
        self.output_file = output_file
        self.expl_text = expl_text
    
    def init_storage(self,ampl_obj):
        
        Years = ampl_obj.sets['YEARS'].copy()
        if 'YEAR_2015' in Years:
            Years.remove('YEAR_2015')
        if 'YEAR_2020' in Years:
            Years.remove('YEAR_2020')
        
        Phases = ampl_obj.sets['PHASE'].copy()

        self.results = dict.fromkeys(list(ampl_obj.results.keys()))

        for k in self.results:
            result = ampl_obj.results[k]
            if result is None:
                continue
            if k in ['TotalCost','TotalGwp','Transition_cost','C_tot_capex','C_tot_opex','GwpTransition',
                     'TotalLCIA_REQD','TotalLCIA_RHHD','TotalDIRECT_REQD','TotalDIRECT_RHHD',
                     'TotalTERRITORIAL_REQD','TotalTERRITORIAL_RHHD','TotalABROAD_REQD','TotalABROAD_RHHD']:
                self.results[k] = pd.DataFrame(index=Years,columns=result.columns)
            elif k == 'Cost_return':
                index_elem = result.index.get_level_values(1).unique()
                last_year_wnd = [years[-1] for years in self.ampl_pre.years_opti]
                multi_ind = pd.MultiIndex.from_product([last_year_wnd,index_elem],names = result.index.names)
                self.results[k] = pd.DataFrame(index=multi_ind,columns=result.columns)
            elif k in ['New_old_decom','C_inv_phase_tech','C_op_phase_tech','F_new','F_old']:
                index_elem = ampl_obj.sets['TECHNOLOGIES']
                phases_with_init = ['2015_2020'] + Phases if '2015_2020' not in Phases else Phases
                multi_ind = pd.MultiIndex.from_product([phases_with_init,index_elem],names = result.index.names)
                self.results[k] = pd.DataFrame(index=multi_ind,columns=result.columns)
            elif k in ['C_op_phase_res']:
                index_elem = ampl_obj.sets['RESOURCES']
                phases_with_init = ['2015_2020'] + Phases if '2015_2020' not in Phases else Phases
                multi_ind = pd.MultiIndex.from_product([phases_with_init,index_elem],names = result.index.names)
                self.results[k] = pd.DataFrame(index=multi_ind,columns=result.columns)
            elif k in ['F_decom']:
                index_elem = ampl_obj.sets['TECHNOLOGIES']
                multi_ind = pd.MultiIndex.from_product([Phases,Phases,index_elem],names = result.index.names)
                self.results[k] = pd.DataFrame(index=multi_ind,columns=result.columns)
            elif k in ['C_inv_phase']:
                self.results[k] = pd.DataFrame(index=Phases,columns=result.columns)
            elif k in ['LCIA_constr','LCIA_decom','LCIA_op','DIRECT_op',
                       'TERRITORIAL_constr','TERRITORIAL_decom','TERRITORIAL_op',
                       'ABROAD_constr','ABROAD_decom','ABROAD_op']:
                # Optional LCA variables indexed by (Phases, Indicators, Technologies)
                indicators = ampl_obj.sets['INDICATORS']
                index_elem = ampl_obj.sets['TECHNOLOGIES']
                phases_with_init = ['2015_2020'] + Phases if '2015_2020' not in Phases else Phases
                multi_ind = pd.MultiIndex.from_product([phases_with_init,indicators,index_elem],names = result.index.names)
                self.results[k] = pd.DataFrame(index=multi_ind,columns=result.columns)
            elif k in ['LCIA_res','TERRITORIAL_res','ABROAD_res']:
                # Optional LCA variables indexed by (Phases, Indicators, Resources)
                indicators = ampl_obj.sets['INDICATORS']
                index_elem = ampl_obj.sets['RESOURCES']
                phases_with_init = ['2015_2020'] + Phases if '2015_2020' not in Phases else Phases
                multi_ind = pd.MultiIndex.from_product([phases_with_init,indicators,index_elem],names = result.index.names)
                self.results[k] = pd.DataFrame(index=multi_ind,columns=result.columns)
            elif k in ['PhaseLCIA','PhaseDIRECT','PhaseTERRITORIAL','PhaseABROAD']:
                # Optional LCA variables indexed by (Phases, Indicators)
                indicators = ampl_obj.sets['INDICATORS']
                phases_with_init = ['2015_2020'] + Phases if '2015_2020' not in Phases else Phases
                multi_ind = pd.MultiIndex.from_product([phases_with_init,indicators],names = result.index.names)
                self.results[k] = pd.DataFrame(index=multi_ind,columns=result.columns)
            elif k in ['TotalLCIA','TotalDIRECT','TotalTERRITORIAL','TotalABROAD']:
                # Optional LCA variables indexed by (Indicators) only
                self.results[k] = pd.DataFrame(
                    index=pd.Index(ampl_obj.sets['INDICATORS'], name=result.index.name),
                    columns=result.columns)
            elif k in ['F_Mult_t', 'Monthly_Prod']:
                tech_elem   = ampl_obj.sets['TECHNOLOGIES']
                period_elem = result.index.get_level_values(2).unique()
                multi_ind = pd.MultiIndex.from_product([Years, tech_elem, period_elem], names=result.index.names)
                self.results[k] = pd.DataFrame(index=multi_ind, columns=result.columns)
            elif k in ['F_Mult_t_resources']:
                res_elem    = ampl_obj.sets['RESOURCES']
                period_elem = result.index.get_level_values(2).unique()
                multi_ind = pd.MultiIndex.from_product([Years, res_elem, period_elem], names=result.index.names)
                self.results[k] = pd.DataFrame(index=multi_ind, columns=result.columns)
            else:
                index_elem = result.index.get_level_values(1).unique()
                multi_ind = pd.MultiIndex.from_product([Years,index_elem],names = result.index.names)
                self.results[k] = pd.DataFrame(index=multi_ind,columns=result.columns)
    
    def update_storage(self, ampl_obj,curr_years_wnd,i):

        # Optional LCA variables indexed by (Phases, ...): follow the same
        # rolling-window filter as the other phase-indexed variables.
        phase_indexed_lca_vars = [
            'LCIA_constr','LCIA_decom','LCIA_op','DIRECT_op',
            'TERRITORIAL_constr','TERRITORIAL_decom','TERRITORIAL_op',
            'ABROAD_constr','ABROAD_decom','ABROAD_op',
            'LCIA_res','TERRITORIAL_res','ABROAD_res',
            'PhaseLCIA','PhaseDIRECT','PhaseTERRITORIAL','PhaseABROAD',
        ]
        # Optional LCA variables indexed by (Indicators) only: these are
        # cumulative totals over all phases processed so far in the current
        # window's solve, so there is no Years/Phases level to filter on -
        # simply keep the latest values.
        indicator_only_lca_vars = ['TotalLCIA','TotalDIRECT','TotalTERRITORIAL','TotalABROAD']

        for k in self.results:
            results = ampl_obj.results[k]
            if results is None:
                continue
            if k in indicator_only_lca_vars:
                self.results[k] = results.sort_index()
                continue
            if k in ['New_old_decom','F_decom','C_inv_phase','C_inv_phase_tech','C_op_phase_tech','C_op_phase_res','F_new','F_old'] \
                    + phase_indexed_lca_vars:
                phases_up_to = ['2015_2020','2020_2025'] + self.ampl_pre.phases_up_to[i]
                temp_res = results.loc[results.index.get_level_values('Phases').isin(phases_up_to),:]
            else:
                temp_res = results.loc[results.index.get_level_values('Years').isin(curr_years_wnd),:]
            temp = [self.results[k],temp_res]
            temp = pd.concat(temp)
            self.results[k] = temp.loc[~temp.index.duplicated(keep='last')]
            self.results[k] = self.results[k].sort_index()
    
    def clean_collector(self):
        for k in self.results:
            if self.results[k] is None:
                continue
            self.results[k].dropna(how='all',inplace=True)

    def pkl(self, write_in_recap = True):

        if write_in_recap:
            case_name = os.path.basename(os.path.normpath(Path(self.output_file).parent))
            recap_file = os.path.join(self.pth_output_all,'_Recap.csv')
            t = datetime.fromtimestamp(time())

            # --- extract summary metrics ---
            COLS = ['Case_study','Comment','Date_Time',
                    'TotalCost_M€','CAPEX_M€','OPEX_M€','CumulativeCO2_Mt']

            def _scalar(key, col):
                try: return round(float(self.results[key][col].iloc[0]), 1)
                except: return None

            total_cost = _scalar('Transition_cost', 'Transition_cost')
            capex      = _scalar('C_tot_capex',     'C_tot_capex')
            opex       = _scalar('C_tot_opex',      'C_tot_opex')

            gwp_tr = _scalar('GwpTransition', 'GwpTransition')
            cum_co2 = round(gwp_tr / 1000, 1) if gwp_tr is not None else None

            new_row = [case_name, self.expl_text, t, total_cost, capex, opex, cum_co2]

            if not os.path.exists(Path(recap_file)):
                Path(recap_file).parent.mkdir(parents=True, exist_ok=True)
                with open(recap_file, 'w+', encoding='utf-8') as f:
                    csv.writer(f).writerow(COLS)

            df = pd.read_csv(recap_file, encoding='utf-8')
            # add any missing columns
            for c in COLS:
                if c not in df.columns:
                    df[c] = None

            if case_name in df.Case_study.values:
                for col, val in zip(COLS[1:], new_row[1:]):
                    df.loc[df['Case_study'] == case_name, col] = val
                df.to_csv(recap_file, index=False, encoding='utf-8')
            else:
                with open(recap_file, 'a', encoding='utf-8') as f:
                    csv.writer(f).writerow(new_row)


        if not os.path.exists(Path(self.output_file).parent):
            os.makedirs(Path(self.output_file).parent)
        
        csv_folder = os.path.join(Path(self.output_file).parent,'csv')
        if not os.path.exists(csv_folder):
            os.makedirs(csv_folder)
        
        open_file = open(self.output_file,"wb")
        pickle.dump(self.results,open_file)
        open_file.close()
        
        results_to_csv = ['Assets','Resources']
        for r in self.results:
            if r in results_to_csv:
                path_csv = csv_folder+'/'+r+'.csv'
                self.results[r].to_csv(path_csv)
