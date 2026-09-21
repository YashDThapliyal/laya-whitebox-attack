#!/bin/bash
# Recovery: re-provision an A100, restore the exact v2 monitor + synced partial attack results, resume attacks.
# Usage: scripts/recover_colab.sh <session-name>
set -u
NAME=${1:-laya3}
cd /Users/yash/Documents/laya-grad-break
S=/private/tmp/claude-501/-Users-yash-Documents-laya-grad-break/f71213ca-4ad3-457e-aec1-d749e91ea634/scratchpad
CLIPY=/Users/yash/.local/share/uv/tools/google-colab-cli/bin/python

# 1. provision (client often times out while the server still allocates) -> adopt any unregistered A100
colab new -s "$NAME" --gpu A100 2>&1 | tail -1
if ! colab sessions 2>&1 | grep -q "\[$NAME\]"; then
  sleep 60
  $CLIPY - "$NAME" <<'EOF'
import sys
from colab_cli.common import state
from colab_cli.commands.session import spawn_keep_alive, SessionState
name = sys.argv[1]
known = {s.endpoint for s in state.store.list().values()}
a = [x for x in state.client.list_assignments() if x.endpoint not in known]
if not a:
    sys.exit("no unregistered assignment to adopt")
x = a[0]
s = SessionState(name=name, token=x.runtime_proxy_info.token, url=x.runtime_proxy_info.url,
                 endpoint=x.endpoint, variant="GPU", accelerator=x.accelerator.value)
state.client.keep_alive_assignment(x.endpoint)
state.store.add(s)
s.keep_alive_pid = spawn_keep_alive(x.endpoint, name, auth_provider=state.auth_provider, config_path=state.config_path)
state.store.add(s)
print("adopted", x.endpoint, x.accelerator.value)
EOF
fi
colab sessions 2>&1 | grep -q "\[$NAME\]" || { echo "provisioning failed"; exit 1; }

# 2. code + data + v2 calibration/scores + synced partial attack results
rm -rf $S/rec && mkdir -p $S/rec/proj/{scripts,data,monitor/laya-monitor,results,attack}
cp scripts/*.py $S/rec/proj/scripts/
cp data/train_pool.jsonl data/eval_heldout.jsonl $S/rec/proj/data/
cp -r monitor/laya-monitor-v2/{encoder,tokenizer,rl_agent_config.json} $S/rec/proj/monitor/laya-monitor/
cp monitor/laya-monitor-v2/calibration.json $S/rec/proj/monitor/calibration.json
cp results/vm/results_heldout_scores_finetuned.jsonl $S/rec/proj/results/heldout_scores_finetuned.jsonl
for f in results/vm/attack_*; do cp "$f" "$S/rec/proj/attack/${f#results/vm/attack_}"; done
tar czf $S/rec.tgz -C $S/rec proj
colab upload -s "$NAME" $S/rec.tgz /content/rec.tgz 2>&1 | tail -1 | cut -c1-60

# 3. exact v2 weights in 50 MB chunks (single large uploads fail), verified by sha256
rm -rf $S/chunks && mkdir -p $S/chunks && split -b 50m monitor/laya-monitor-v2/model.safetensors $S/chunks/w_
for f in $S/chunks/w_*; do
  for try in 1 2 3; do colab upload -s "$NAME" $f /content/$(basename $f) 2>&1 | grep -q Uploaded && break; done
done
SHA=$(cat monitor/laya-monitor-v2/model.sha256)
cat > $S/rec_setup.py <<EOF
import subprocess
r = subprocess.run("cd /content && tar xzf rec.tgz && cat w_* > proj/monitor/laya-monitor/model.safetensors && rm w_* && sha256sum proj/monitor/laya-monitor/model.safetensors && pip install -q laya 2>&1 | tail -1", shell=True, capture_output=True, text=True)
print(r.stdout, r.stderr[-300:])
print("SHA_OK" if "$SHA" in r.stdout else "SHA_MISMATCH")
EOF
colab exec -s "$NAME" -f $S/rec_setup.py 2>&1 | tail -3

# 4. resume every run that hadn't finished (a run is finished if its log has 'done' or 'time cap')
cat > $S/rec_run.sh <<'EOF'
cd /content/proj; export PYTHONPATH=scripts
run() { log=attack/$1.log; shift; if grep -qE "^done|time cap" $log 2>/dev/null; then echo "skip $log"; return; fi
        python scripts/attack.py "$@" --resume >> $log 2>&1; }
V="--data data/train_pool.jsonl --scores compute --n 200 --budget 20"
M="--n 20 --budget 60 --max_windows 25"
( run val_agent $V --scope agent --max_minutes 35 --out attack/val_agent.jsonl
  run val_agent_random $V --scope agent --random_baseline --max_minutes 10 --out attack/val_agent_random.jsonl
  run val_all $V --scope all --max_minutes 35 --out attack/val_all.jsonl
  touch attack/VAL_DONE ) &
( run mrt_agent $M --scope agent --max_minutes 50 --out attack/mrt_agent.jsonl
  run mrt_agent_random $M --scope agent --random_baseline --max_minutes 10 --out attack/mrt_agent_random.jsonl
  run mrt_all $M --scope all --max_minutes 50 --out attack/mrt_all.jsonl
  touch attack/MRT_DONE ) &
wait
EOF
colab upload -s "$NAME" $S/rec_run.sh /content/rec_run.sh 2>&1 | tail -1 | cut -c1-60
echo 'import subprocess; subprocess.Popen("nohup bash /content/rec_run.sh > /content/rec_run.out 2>&1 &", shell=True); print("resumed")' > $S/rec_launch.py
colab exec -s "$NAME" -f $S/rec_launch.py 2>&1 | tail -1
