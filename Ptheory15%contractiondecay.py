import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

# Parameters
V0 = 75000
p = 0.10
e = 0.05
d = 0.15
L0 = 0.90

years = np.arange(2026, 2047)
x = years - 2026

growth = (1 + p) / (1 - e)

V_base = V0 * (growth ** x)
lag = (1 - L0 * ((1 - d) ** x))
V_decay = V_base * lag

# Theme
neon = "#39ff14"
bg = "#000000"

fig = plt.figure(facecolor=bg, figsize=(12, 6), dpi=160)
ax = fig.add_subplot(111)
ax.set_facecolor(bg)

# Glow effect
ax.plot(years, V_base/1e6, color="blue", linewidth=8, alpha=0.08)
ax.plot(years, V_base/1e6, color="blue", linewidth=5, alpha=0.15)

ax.plot(years, V_decay/1e6, color="orange", linewidth=8, alpha=0.08)
ax.plot(years, V_decay/1e6, color="orange", linewidth=5, alpha=0.15)

# Main lines
ax.plot(years, V_base/1e6, color="blue", linewidth=2.8, label="P Theory Baseline")
ax.plot(years, V_decay/1e6, color="orange", linewidth=2.8, label="P Theory with 15% Contraction Decay")

# Styling
ax.set_title("Power Efficiency Compounding Scenarios", color=neon, pad=14)
ax.set_xlabel("Year", color=neon)
ax.set_ylabel("Millions USD", color=neon)

ax.tick_params(colors=neon)
for spine in ax.spines.values():
    spine.set_color(neon)

ax.grid(True, color=neon, alpha=0.12)

leg = ax.legend(facecolor=bg, edgecolor=neon)
for text in leg.get_texts():
    text.set_color(neon)

plt.tight_layout()
plt.show()
