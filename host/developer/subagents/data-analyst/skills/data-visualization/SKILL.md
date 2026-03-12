---
name: data-visualization
description: Create charts and visualizations from data using matplotlib or plotly
---

# Data Visualization Skill

Use this skill to create charts and visualizations from analyzed data.

## Capabilities
- Line charts, bar charts, scatter plots
- Matplotlib and Plotly support
- Save to PNG/SVG files

## Usage
```python
import matplotlib.pyplot as plt
import pandas as pd

# Create visualization
plt.figure(figsize=(10, 6))
plt.plot(data['x'], data['y'])
plt.title('Data Visualization')
plt.savefig('output.png')
```

## Output
Always save visualizations to `/tmp/workspace/` directory with descriptive filenames.
