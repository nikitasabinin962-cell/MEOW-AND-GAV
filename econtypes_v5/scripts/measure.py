"""Запуск команды с измерением wall time и пикового RSS (дочерний процесс), запись в JSON."""
import json, resource, subprocess, sys, time, platform, os
out = sys.argv[1]; cmd = sys.argv[2:]
t = time.time()
p = subprocess.run(cmd)
wall = time.time() - t
ru = resource.getrusage(resource.RUSAGE_CHILDREN)
rec = dict(cmd=" ".join(cmd), returncode=p.returncode, wall_seconds=round(wall, 2), peak_rss_mib=round(ru.ru_maxrss / 1024, 1),
           cpu_user_s=round(ru.ru_utime, 1), host=dict(cpus=os.cpu_count(), platform=platform.platform(), python=platform.python_version()))
json.dump(rec, open(out, "w"), indent=1)
print(json.dumps(rec), file=sys.stderr)
sys.exit(p.returncode)
