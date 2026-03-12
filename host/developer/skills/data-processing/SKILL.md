---
name: data-processing
description: Process CSV, JSON, and Excel files using pandas, matplotlib, and scipy
---

# Data Processing Skill

Use this skill to read, analyze, and transform data files in the sandbox.

## Reading Data

```python
import pandas as pd

# CSV
df = pd.read_csv("data.csv")

# JSON
df = pd.read_json("data.json")

# Excel
df = pd.read_excel("data.xlsx", engine="openpyxl")

# Quick overview
print(df.shape)
print(df.dtypes)
print(df.describe())
```

## Common Operations

```python
# Filter rows
filtered = df[df["column"] > 100]

# Group and aggregate
summary = df.groupby("category").agg({"value": ["mean", "sum", "count"]})

# Pivot table
pivot = df.pivot_table(values="sales", index="region", columns="month", aggfunc="sum")

# Handle missing values
df = df.fillna(0)
df = df.dropna(subset=["important_column"])
```

## Visualization

```python
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend (required in sandbox)
import matplotlib.pyplot as plt

# Bar chart
df.groupby("category")["value"].mean().plot(kind="bar")
plt.title("Average Value by Category")
plt.tight_layout()
plt.savefig("chart.png", dpi=150)
plt.close()

# Line chart
df.plot(x="date", y="value", kind="line")
plt.savefig("trend.png", dpi=150)
plt.close()
```

## Statistical Analysis

```python
from scipy import stats

# Correlation
corr = df[["col1", "col2"]].corr()

# T-test
t_stat, p_value = stats.ttest_ind(group_a, group_b)

# Basic statistics
print(df["column"].describe())
```

## Saving Results

```python
# Save to CSV
df.to_csv("result.csv", index=False)

# Save to Excel
df.to_excel("result.xlsx", index=False, engine="openpyxl")

# Save to JSON
df.to_json("result.json", orient="records", force_ascii=False)
```

## Workspace Rules

- All input/output files must be in `/tmp/workspace/`
- Use relative paths: `"data.csv"` (not `"/tmp/workspace/data.csv"`)
- Save charts as PNG: `plt.savefig("chart.png", dpi=150)`
- Always call `plt.close()` after saving to free memory
- Always use `matplotlib.use("Agg")` before importing pyplot
