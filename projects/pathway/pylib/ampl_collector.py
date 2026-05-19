#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr 08 2022

@author: rixhonx
"""

from pathlib import Path

import os,sys
import csv
import pickle
import pandas as pd
from datetime import datetime
from time import time

pylibPath = os.path.abspath("../pylib")
if pylibPath not in sys.path:
    sys.path.insert(0, pylibPath)

def _generate_recap_html(recap_csv_path):
    """Read _Recap.csv and write a styled sortable _Recap.html next to it."""
    try:
        df = pd.read_csv(recap_csv_path)
    except Exception:
        return

    df = df.sort_values('Date_Time', ascending=False).reset_index(drop=True)

    # --- format columns for display ---
    display = df.copy()
    for col in ['TotalCost_M€', 'CAPEX_M€', 'OPEX_M€']:
        if col in display.columns:
            display[col] = pd.to_numeric(display[col], errors='coerce')
            display[col] = display[col].apply(
                lambda v: f'{v/1e6:.3f} T€' if pd.notna(v) else '—')
    if 'CumulativeCO2_Mt' in display.columns:
        display['CumulativeCO2_Mt'] = pd.to_numeric(display['CumulativeCO2_Mt'], errors='coerce')
        display['CumulativeCO2_Mt'] = display['CumulativeCO2_Mt'].apply(
            lambda v: f'{v/1000:.3f} Gt' if pd.notna(v) else '—')
    if 'Date_Time' in display.columns:
        display['Date_Time'] = pd.to_datetime(display['Date_Time'], errors='coerce') \
                                 .dt.strftime('%Y-%m-%d %H:%M')

    col_labels = {
        'Case_study':        'Case study',
        'Comment':           'Comment',
        'Date_Time':         'Date',
        'TotalCost_M€':      'Total cost',
        'CAPEX_M€':          'CAPEX',
        'OPEX_M€':           'OPEX',
        'CumulativeCO2_Mt':  'Cumul. CO₂',
    }
    display = display.rename(columns=col_labels)
    cols = [col_labels.get(c, c) for c in col_labels if col_labels[c] in display.columns]
    display = display[[c for c in cols if c in display.columns]]

    rows_html = ''
    for _, row in display.iterrows():
        cells = ''.join(f'<td>{v}</td>' for v in row)
        rows_html += f'<tr>{cells}</tr>\n'

    headers_html = ''.join(
        f'<th onclick="sortTable({i})">{h} <span class="arrow">↕</span></th>'
        for i, h in enumerate(display.columns)
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>EnergyScope — Case study recap</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 30px; background: #f5f5f5; }}
  h1   {{ color: #333; }}
  table {{ border-collapse: collapse; width: 100%; background: white;
           box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }}
  th   {{ background: #2c3e50; color: white; padding: 12px 16px; cursor: pointer;
           text-align: left; white-space: nowrap; user-select: none; }}
  th:hover {{ background: #34495e; }}
  td   {{ padding: 10px 16px; border-bottom: 1px solid #eee; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f0f7ff; }}
  .arrow {{ font-size: 0.75em; opacity: 0.6; }}
  td:nth-child(n+4) {{ text-align: right; font-family: monospace; }}
</style>
</head>
<body>
<h1>EnergyScope — Case study comparison</h1>
<p style="color:#666">Click a column header to sort. Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<table id="recap">
  <thead><tr>{headers_html}</tr></thead>
  <tbody>{rows_html}</tbody>
</table>
<script>
function sortTable(col) {{
  const table = document.getElementById('recap');
  const tbody = table.tBodies[0];
  const rows  = Array.from(tbody.rows);
  const asc   = table.dataset.sortCol == col && table.dataset.sortDir == 'asc';
  rows.sort((a, b) => {{
    const va = a.cells[col].innerText.trim();
    const vb = b.cells[col].innerText.trim();
    const na = parseFloat(va.replace(/[^0-9.\-]/g,'')), nb = parseFloat(vb.replace(/[^0-9.\-]/g,''));
    if (!isNaN(na) && !isNaN(nb)) return asc ? nb - na : na - nb;
    return asc ? vb.localeCompare(va) : va.localeCompare(vb);
  }});
  rows.forEach(r => tbody.appendChild(r));
  table.dataset.sortCol = col;
  table.dataset.sortDir = asc ? 'desc' : 'asc';
}}
</script>
</body>
</html>"""

    html_path = str(recap_csv_path).replace('.csv', '.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)


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
            if k in ['TotalCost','TotalGwp','Transition_cost','C_tot_capex','C_tot_opex']:
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
        for k in self.results:
            results = ampl_obj.results[k]
            if results is None:
                continue
            if k in ['New_old_decom','F_decom','C_inv_phase','C_inv_phase_tech','C_op_phase_tech','C_op_phase_res','F_new','F_old']:
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

            try:
                gwp = self.results['TotalGwp']['TotalGWP']
                cum_co2 = round(float(gwp.sum() * 5 / 1000), 1)  # kt×5y → Mt
            except:
                cum_co2 = None

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

            _generate_recap_html(recap_file)

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
