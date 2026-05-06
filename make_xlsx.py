import csv
import glob
import os
from openpyxl import Workbook

output_dir = "output_3x3"
out_file = "grades_combined.xlsx"

csv_files = sorted(glob.glob(f"{output_dir}/**/*.csv", recursive=True))

wb = Workbook()
wb.remove(wb.active)  # remove default sheet

for path in csv_files:
    # e.g. output_3x3/prompt_A/haiku/AP-Calc_grades.csv -> prompt_A_haiku_AP-Calc
    parts = path.replace("\\", "/").split("/")
    name = f"{parts[-3]}_{parts[-2]}_{parts[-1].replace('_grades.csv', '')}"
    name = name[:31]  # Excel tab name limit

    ws = wb.create_sheet(title=name)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            ws.append(row)

wb.save(out_file)
print(f"Saved {len(csv_files)} tabs to {out_file}")
