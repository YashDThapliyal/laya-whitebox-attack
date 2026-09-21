| Source | n eval | AUROC trained [95% CI] | AUROC zero-shot [95% CI] | attacked n | success @1 | success @3 | success @5 | success @10 | success @20 | random @20 | any-token @20 | median start margin (logits) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| InjecAgent | 176 | 1.000 [1.00, 1.00] | 0.792 [0.72, 0.85] | 87 | 0.01 | 0.03 | 0.09 | 0.24 | 0.44 | 0.00 | 1.00 | 4.56 |
| ToolEmu | 44 | 1.000 [1.00, 1.00] | 0.787 [0.64, 0.92] | 21 | 0.10 | 0.38 | 0.52 | 0.90 | 0.90 | 0.14 | 1.00 | 3.83 |
| R-Judge | 35 | 0.520 [0.33, 0.72] | 0.477 [0.29, 0.67] | 9 | 0.11 | 0.44 | 0.44 | 0.67 | 0.89 | 0.11 | 1.00 | 1.93 |
| SHADE-Arena (MRT) | 1448 | 0.577 [0.55, 0.61] | 0.505 [0.47, 0.55] | 20 | 0.00 | 0.00 | 0.00 | 0.05 | 0.10 | 0.00 | 0.60 | 2.27 |

injecagent   agent         n= 87 succ=[0.01, 0.03, 0.09, 0.24, 0.44] ci20=(0.34,0.54) retok20=0.36 start_p=0.976 margin=4.56 edit=117 win=2
injecagent   agent_random  n= 87 succ=[0.0, 0.0, 0.0, 0.0, 0.0] ci20=(0.00,0.04) retok20=0.00 start_p=0.976 margin=4.56 edit=117 win=2
injecagent   all           n= 87 succ=[0.05, 0.39, 0.71, 0.94, 1.0] ci20=(0.96,1.00) retok20=0.91 start_p=0.976 margin=4.56 edit=358 win=2
toolemu      agent         n= 21 succ=[0.1, 0.38, 0.52, 0.9, 0.9] ci20=(0.71,0.97) retok20=0.86 start_p=0.968 margin=3.83 edit=43 win=1
toolemu      agent_random  n= 21 succ=[0.0, 0.0, 0.0, 0.1, 0.14] ci20=(0.05,0.35) retok20=0.14 start_p=0.968 margin=3.83 edit=43 win=1
toolemu      all           n= 21 succ=[0.1, 0.33, 0.71, 0.95, 1.0] ci20=(0.85,1.00) retok20=1.00 start_p=0.968 margin=3.83 edit=56 win=1
r-judge      agent         n=  9 succ=[0.11, 0.44, 0.44, 0.67, 0.89] ci20=(0.56,0.98) retok20=0.89 start_p=0.933 margin=1.93 edit=85 win=1
r-judge      agent_random  n=  9 succ=[0.0, 0.0, 0.0, 0.0, 0.11] ci20=(0.02,0.44) retok20=0.11 start_p=0.933 margin=1.93 edit=85 win=1
r-judge      all           n=  9 succ=[0.56, 0.89, 1.0, 1.0, 1.0] ci20=(0.70,1.00) retok20=0.89 start_p=0.933 margin=1.93 edit=303 win=1
shade-arena  agent         n= 20 succ=[0.0, 0.0, 0.0, 0.05, 0.1] ci20=(0.03,0.30) retok20=0.10 start_p=0.941 margin=2.27 edit=66 win=15 s60=0.15
shade-arena  agent_random  n= 20 succ=[0.0, 0.0, 0.0, 0.0, 0.0] ci20=(0.00,0.16) retok20=0.00 start_p=0.941 margin=2.27 edit=66 win=15 s60=0.00
shade-arena  all           n= 20 succ=[0.0, 0.15, 0.25, 0.55, 0.6] ci20=(0.39,0.78) retok20=0.55 start_p=0.940 margin=2.23 edit=2840 win=14 s60=0.75
