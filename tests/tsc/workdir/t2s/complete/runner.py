import os
import subprocess
import tscdefs
import shutil

tripFile = 'twoPersonsOnly.csv'
net = os.path.join('scenario_workdir','mitte_net', 'net.net.xml')
iteration_dir = os.path.join('scenario_workdir','mitte_net', 'iteration000')

os.chdir("data")
subprocess.call(tscdefs.get_python_tool("t2s.py",None) + ['--net-file', net, '--iteration-dir', iteration_dir, '--tapas-trips', tripFile])