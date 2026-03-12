---
name: statistical-analysis
description: Perform statistical analysis including correlation, regression, and hypothesis testing
---

# Statistical Analysis Skill

Perform advanced statistical analysis on datasets.

## Capabilities
- Correlation analysis (Pearson, Spearman)
- Linear/Multiple regression
- Hypothesis testing (t-test, chi-square)
- Distribution analysis

## Usage
```python
import pandas as pd
import numpy as np
from scipy import stats

# Correlation analysis
correlation = df.corr()

# Regression
from sklearn.linear_model import LinearRegression
model = LinearRegression()
model.fit(X, y)
```

## Best Practices
- Check data normality before parametric tests
- Report p-values and confidence intervals
- Visualize distributions
