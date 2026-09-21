
### Fine-tuned monitor, success bar p < 0.865

| Source | scope | attack | n | @1 | @3 | @5 | @10 | @20 | @60 | 95% CI (last) | retokenized (last) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| InjecAgent | agent text | unconstrained | 87 | 0.01 | 0.03 | 0.09 | 0.24 | 0.44 | – | [0.34, 0.54] | 0.36 |
| InjecAgent | agent text | fluent | 87 | 0.00 | 0.01 | 0.06 | 0.30 | 0.47 | – | [0.37, 0.58] | 0.44 |
| InjecAgent | any token | unconstrained | 87 | 0.05 | 0.39 | 0.71 | 0.94 | 1.00 | – | [0.96, 1.00] | 0.91 |
| InjecAgent | any token | fluent | 87 | 0.01 | 0.28 | 0.56 | 0.84 | 0.97 | – | [0.90, 0.99] | 0.95 |
| ToolEmu | agent text | unconstrained | 21 | 0.10 | 0.38 | 0.52 | 0.90 | 0.90 | – | [0.71, 0.97] | 0.86 |
| ToolEmu | agent text | fluent | 21 | 0.05 | 0.48 | 0.76 | 1.00 | 1.00 | – | [0.85, 1.00] | 1.00 |
| ToolEmu | any token | unconstrained | 21 | 0.10 | 0.33 | 0.71 | 0.95 | 1.00 | – | [0.85, 1.00] | 1.00 |
| ToolEmu | any token | fluent | 21 | 0.10 | 0.52 | 0.86 | 1.00 | 1.00 | – | [0.85, 1.00] | 1.00 |
| R-Judge | agent text | unconstrained | 9 | 0.11 | 0.44 | 0.44 | 0.67 | 0.89 | – | [0.56, 0.98] | 0.89 |
| R-Judge | agent text | fluent | 9 | 0.22 | 0.33 | 0.67 | 1.00 | 1.00 | – | [0.70, 1.00] | 1.00 |
| R-Judge | any token | unconstrained | 9 | 0.56 | 0.89 | 1.00 | 1.00 | 1.00 | – | [0.70, 1.00] | 0.89 |
| R-Judge | any token | fluent | 9 | 0.56 | 0.67 | 0.89 | 1.00 | 1.00 | – | [0.70, 1.00] | 1.00 |
| SHADE | agent text | unconstrained | 20 | 0.00 | 0.00 | 0.00 | 0.05 | 0.10 | 0.15 | [0.05, 0.36] | 0.15 |
| SHADE | agent text | fluent | 20 | 0.00 | 0.00 | 0.00 | 0.05 | 0.05 | 0.10 | [0.03, 0.30] | 0.10 |
| SHADE | any token | unconstrained | 20 | 0.00 | 0.15 | 0.25 | 0.55 | 0.60 | 0.75 | [0.53, 0.89] | 0.55 |
| SHADE | any token | fluent | 20 | 0.00 | 0.10 | 0.15 | 0.35 | 0.55 | 0.75 | [0.53, 0.89] | 0.65 |

### Fine-tuned monitor, success bar p < 0.500

| Source | scope | attack | n | @1 | @3 | @5 | @10 | @20 | @60 | 95% CI (last) | retokenized (last) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| InjecAgent | agent text | unconstrained | 87 | 0.00 | 0.00 | 0.01 | 0.14 | 0.29 | – | [0.20, 0.39] | 0.26 |
| InjecAgent | agent text | fluent | 87 | 0.00 | 0.00 | 0.01 | 0.18 | 0.38 | – | [0.28, 0.48] | 0.33 |
| InjecAgent | any token | unconstrained | 87 | 0.01 | 0.25 | 0.49 | 0.80 | 0.91 | – | [0.83, 0.95] | 0.82 |
| InjecAgent | any token | fluent | 87 | 0.00 | 0.10 | 0.37 | 0.64 | 0.84 | – | [0.75, 0.90] | 0.77 |
| ToolEmu | agent text | unconstrained | 21 | 0.00 | 0.29 | 0.43 | 0.76 | 0.90 | – | [0.71, 0.97] | 0.90 |
| ToolEmu | agent text | fluent | 21 | 0.05 | 0.38 | 0.62 | 0.95 | 1.00 | – | [0.85, 1.00] | 0.95 |
| ToolEmu | any token | unconstrained | 21 | 0.05 | 0.24 | 0.43 | 0.76 | 0.86 | – | [0.65, 0.95] | 0.86 |
| ToolEmu | any token | fluent | 21 | 0.10 | 0.43 | 0.48 | 0.95 | 1.00 | – | [0.85, 1.00] | 0.95 |
| R-Judge | agent text | unconstrained | 9 | 0.00 | 0.00 | 0.22 | 0.33 | 0.44 | – | [0.19, 0.73] | 0.22 |
| R-Judge | agent text | fluent | 9 | 0.00 | 0.22 | 0.22 | 0.44 | 0.89 | – | [0.56, 0.98] | 0.89 |
| R-Judge | any token | unconstrained | 9 | 0.00 | 0.67 | 0.67 | 0.89 | 1.00 | – | [0.70, 1.00] | 0.89 |
| R-Judge | any token | fluent | 9 | 0.00 | 0.56 | 0.67 | 0.78 | 1.00 | – | [0.70, 1.00] | 1.00 |
| SHADE | agent text | unconstrained | 0 | – | – | – | – | – | – | – | – |
| SHADE | agent text | fluent | 20 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | [0.00, 0.16] | 0.00 |
| SHADE | any token | unconstrained | 20 | 0.00 | 0.00 | 0.00 | 0.10 | 0.20 | 0.55 | [0.34, 0.74] | 0.30 |
| SHADE | any token | fluent | 20 | 0.00 | 0.00 | 0.00 | 0.05 | 0.15 | 0.40 | [0.22, 0.61] | 0.20 |

### Checkpoints, fluent attack, common bar p < 0.5 (success @20; @60 for SHADE)

| Source | scope | fine-tuned (full set) | zero-shot (full set) | overlap n | fine-tuned on overlap | zero-shot on overlap | paired: both / FT-only / ZS-only / neither |
|---|---|---|---|---|---|---|---|
| InjecAgent | agent text | 33/87 = 0.38 [0.28, 0.48] | 67/86 = 0.78 [0.68, 0.85] | 85 | 31/85 = 0.36 [0.27, 0.47] | 66/85 = 0.78 [0.68, 0.85] | 30 / 1 / 36 / 18 |
| InjecAgent | any token | 73/87 = 0.84 [0.75, 0.90] | 83/86 = 0.97 [0.90, 0.99] | 85 | 71/85 = 0.84 [0.74, 0.90] | 82/85 = 0.96 [0.90, 0.99] | 70 / 1 / 12 / 2 |
| ToolEmu | agent text | 21/21 = 1.00 [0.85, 1.00] | 17/17 = 1.00 [0.82, 1.00] | 16 | 16/16 = 1.00 [0.81, 1.00] | 16/16 = 1.00 [0.81, 1.00] | 16 / 0 / 0 / 0 |
| ToolEmu | any token | 21/21 = 1.00 [0.85, 1.00] | 17/17 = 1.00 [0.82, 1.00] | 16 | 16/16 = 1.00 [0.81, 1.00] | 16/16 = 1.00 [0.81, 1.00] | 16 / 0 / 0 / 0 |
| R-Judge | agent text | 8/9 = 0.89 [0.56, 0.98] | 12/14 = 0.86 [0.60, 0.96] | 6 | 5/6 = 0.83 [0.44, 0.97] | 4/6 = 0.67 [0.30, 0.90] | 4 / 1 / 0 / 1 |
| R-Judge | any token | 9/9 = 1.00 [0.70, 1.00] | 14/14 = 1.00 [0.78, 1.00] | 6 | 6/6 = 1.00 [0.61, 1.00] | 6/6 = 1.00 [0.61, 1.00] | 6 / 0 / 0 / 0 |
| SHADE | agent text | 0/20 = 0.00 [0.00, 0.16] | 2/20 = 0.10 [0.03, 0.30] | 20 | 0/20 = 0.00 [0.00, 0.16] | 2/20 = 0.10 [0.03, 0.30] | 0 / 0 / 2 / 18 |
| SHADE | any token | 8/20 = 0.40 [0.22, 0.61] | 9/20 = 0.45 [0.26, 0.66] | 20 | 8/20 = 0.40 [0.22, 0.61] | 9/20 = 0.45 [0.26, 0.66] | 7 / 1 / 2 / 10 |
