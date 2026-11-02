# Heartbeat idle test (before job 8)

`scripts/aaai27/colab/heartbeat_test.sh NAME 21 LOG`: an A100 with only the heartbeat running for 21 minutes, the
keep-alive daemon killed after 6 minutes to check the restart, then `colab stop` to check the heartbeat exits.

| VM | Region | Pruned in 21 min | Beats ok / failed | Max gap | Keep-alive restarted | Exited after stop | Verdict |
|---|---|---|---|---|---|---|---|
| layahb1 | asia-southeast1 | no | 3 / 3 | 240 s | yes | yes | not a valid test of the final code |
| layahb2 | us-central1 | no | 6 / 0 | 242 s | yes | yes | pass |

layahb1: the CLI's kernel websocket took 19 to 33 s to connect (US VMs: 0 to 2 s) and `colab exec` sent its
command before the socket was ready, then hung. The commands still ran on the kernel (the CLI log shows each
execute_reply), but each beat timed out and left an orphaned CLI process. Fixes, tested on layahb2: newvm.sh keeps only
US-region VMs, and every CLI call runs in its own process group, killed on timeout (cli_util.py).

layahb2's script output says FAIL only because the first version of the test counted every session_terminated event,
including the two non-US VMs that newvm.sh released before getting a US one (both `user_requested`); there were 0
`pruned` events. The check now counts only prunes.
