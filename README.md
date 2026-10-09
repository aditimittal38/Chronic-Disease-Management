# Chronic Disease Management

Dataset-specific studies keep their patients, outcomes, and variables separate.

```text
Chronic-Disease-Management/
  datasets/
    uci/
      data/raw/           Original CSVs; unchanged
      data/processed/     Cleaned and feature CSVs
      scripts/            Five computational stages and method tests
      reports/            CSV/JSON results, plots, Markdown snapshots
      reference/          Original project presentation PDF
      run_pipeline.py     UCI workflow
      requirements*.txt   Environment dependencies
      README.md           UCI instructions
    nhanes/               Empty; reserved for later work
```

- [UCI instructions](datasets/uci/README.md)
- [Research findings](datasets/uci/reports/06_final_report/README.md)


From this repository root, using the interpreter containing the dependencies:

```powershell
python datasets/uci/run_pipeline.py
```

The workflow updates tabular outputs and plots, not Markdown reports. Reports are maintained snapshots.
Raw and large derived patient-level files are Git-ignored but remain local. Restore raw CSVs from UCI
when setting up a clone. Git does not track empty folders; recreate `datasets/nhanes` in a fresh clone.