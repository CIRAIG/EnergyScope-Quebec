# Tables pathway de main completees (sous-technologies PV/eolien, DEC_HP_ELEC_*) pour materials=True
import re
from pathlib import Path

AMPL_DIR = Path(__file__).resolve().parent / 'ampl_files'


# Blocs "[TECH, *, *] : ..." (8 lignes) du fichier years_active
def _years_active_blocks(text):
    lines = text.split('\n')
    return [(m.group(1), '\n'.join(lines[i:i + 8])) for i, l in enumerate(lines) if (m := re.match(r'\[(\w+), \*, \*\]', l))]


# main + ajouts avant le ';' final, en ignorant les techs deja presentes dans main
def _merge_param_table(main_file, extra_file, out_file, key_of_line):
    body = Path(main_file).read_text(encoding='utf-8').rstrip()
    assert body.endswith(';'), f"{main_file}: table sans ';' final"
    body = body[:-1].rstrip('\n')
    extra = [l for l in Path(extra_file).read_text(encoding='utf-8').rstrip('\n').split('\n')
             if l.startswith('#') or key_of_line(l) not in body]
    Path(out_file).write_text(body + '\n' + '\n'.join(extra) + '\n;\n', encoding='utf-8')
    return str(out_file)


# years_active: ajoute les blocs de techs absentes de main
def _merge_years_active(main_file, extra_file, out_file):
    body = Path(main_file).read_text(encoding='utf-8').rstrip()
    assert body.endswith(';'), f"{main_file}: table sans ';' final"
    present = {name for name, _ in _years_active_blocks(body)}
    comments = [l for l in Path(extra_file).read_text(encoding='utf-8').split('\n') if l.startswith('#')]
    new = [blk for name, blk in _years_active_blocks(Path(extra_file).read_text(encoding='utf-8')) if name not in present]
    Path(out_file).write_text(body[:-1].rstrip('\n') + '\n' + '\n'.join(comments + new) + '\n;\n', encoding='utf-8')
    return str(out_file)


# AGE: lignes `set AGE ['TECH','phase'] := ... ;` ajoutees si la cle n'existe pas deja dans main
def _merge_age(main_file, extra_file, out_file):
    body = Path(main_file).read_text(encoding='utf-8').rstrip('\n')
    extra = [l for l in Path(extra_file).read_text(encoding='utf-8').rstrip('\n').split('\n')
             if l.startswith('#') or (l.split(':=')[0].strip() not in body)]
    Path(out_file).write_text(body + '\n' + '\n'.join(extra) + '\n', encoding='utf-8')
    return str(out_file)


# Tables years_active, remaining_years et AGE de main + lignes de Subtechs_*.dat, ecrites dans out_dir
def merged_tables(pathway_model_dir, out_dir):
    model, out = Path(pathway_model_dir), Path(out_dir)
    years_active = _merge_years_active(model / 'PES_data_years_active.dat', AMPL_DIR / 'Subtechs_years_active.dat',
                                       out / 'PES_data_years_active_materials.dat')
    remaining = _merge_param_table(model / 'PES_data_remaining.dat', AMPL_DIR / 'Subtechs_remaining.dat',
                                   out / 'PES_data_remaining_materials.dat', lambda l: '\n' + l.split('\t')[0] + '\t')
    age = _merge_age(model / 'PES_data_set_AGE_2020.dat', AMPL_DIR / 'Subtechs_AGE_2020.dat',
                     out / 'PES_data_set_AGE_2020_materials.dat')
    return years_active, remaining, age
