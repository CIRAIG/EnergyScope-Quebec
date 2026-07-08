set MATERIALS;

param material_intensity {YEARS,TECHNOLOGIES,MATERIALS} >= 0 default 0;
param limit_material {MATERIALS} >= 0 default Infinity;

var Material_content_year {YEARS,TECHNOLOGIES,MATERIALS} >= 0;

subject to material_content{y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}:
    Material_content_year[y,tec,mat] = material_intensity[y,tec,mat] * F_new[y,tec];

subject to material_content_limit{y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES, mat in MATERIALS}:
    sum{y in YEARS_WND diff YEAR_ONE, tec in TECHNOLOGIES} Material_content_year[y,tec,mat] <= limit_material[mat];